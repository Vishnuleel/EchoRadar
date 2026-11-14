"""Scheduled monitoring with change detection. Runs as its own process; no browser needed.

    python -m nexus.monitor --once            # run the checks that are due now, then exit
    python -m nexus.monitor --loop 300        # keep running, waking every 300 seconds

How it works
* Every source (and every research query) is a MonitorTask row with its own due time, so schedules
  survive restarts. Each wake-up runs a bounded batch of the tasks that have waited longest: every
  task gets its turn before any task runs twice.
* One worker at a time: a lease row (SchedulerLock) prevents overlapping scans; a crashed worker's
  lease expires and the next worker continues. Each task commits on its own, so a restart loses at
  most the task that was running.
* Change detection compares a hash of each record's meaningful fields with the last observed hash:
  new, updated and "no longer observed" records become ChangeEvents. An unchanged scan creates none.
* A failed check keeps every previous record and its dates, records the error and retries with
  backoff. An empty answer from a source counts as a failure, never as "everything disappeared".
* Funding and event status is still evaluated at display time (closed calls and past events are not
  offered), whatever the monitor last saw.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.database.models import (ChangeEvent, Company, Event, FundingOpportunity, MonitorTask, NewsUpdate,
                                   RecordState, ResearchPublication, SchedulerLock, Testbed)
from nexus.utils.logging import get_logger
from nexus.utils.validators import utcnow

log = get_logger(__name__)
LOCK = "monitor"
# source -> (interval hours, full listing?) A full listing can show that a record is no longer published.
SOURCES = {"directory": (24.0, True), "vinnova": (24.0, True), "events": (24.0, True), "news": (24.0, True),
           "testbeds": (24.0 * 7, True), "openalex": (24.0 * 7, False)}
MAX_BACKOFF_HOURS = 24.0


# ---- what a record "means": the fields whose change is worth telling a member about ----------------
def _h(*parts) -> str:
    return hashlib.sha256(json.dumps([str(p) for p in parts], ensure_ascii=False).encode()).hexdigest()


def snapshot(s: Session, source: str, keys: list[str]) -> dict[str, tuple[str, str, str | None]]:
    """{record key: (content hash, title, url)} for the given keys of one source."""
    out = {}
    if source == "vinnova":
        for r in s.scalars(select(FundingOpportunity).where(FundingOpportunity.external_id.in_(keys))):
            out[r.external_id] = (_h(r.title, r.description, r.opens_at, r.deadline, r.eligibility, r.funding_terms),
                                  r.title, r.source_url)
    elif source == "testbeds":
        for r in s.scalars(select(Testbed).where(Testbed.source_url.in_(keys))):
            out[r.source_url] = (_h(r.name, r.description), r.name, r.source_url)
    elif source == "events":
        for r in s.scalars(select(Event).where(Event.key.in_(keys))):
            out[r.key] = (_h(r.title, r.date_text, r.starts_at, r.location, r.description), r.title, r.source_url)
    elif source == "news":
        for r in s.scalars(select(NewsUpdate).where(NewsUpdate.source_url.in_(keys))):
            out[r.source_url] = (_h(r.title, r.summary, r.published_at), r.title, r.source_url)
    elif source == "openalex":
        for r in s.scalars(select(ResearchPublication).where(ResearchPublication.external_id.in_(keys))):
            out[r.external_id] = (_h(r.title, r.abstract, r.publication_date), r.title, r.source_url)
    elif source == "directory":
        for r in s.scalars(select(Company).where(Company.slug.in_(keys))):
            out[r.slug] = (_h(r.name, r.description, r.industry, r.employees, r.founded, r.location, r.website),
                           r.name, r.directory_url)
    return out


def detect_changes(s: Session, source: str, seen: list[str], full_listing: bool, now: datetime,
                   scope: str = "") -> list[ChangeEvent]:
    """Compare what this successful scan saw with the last observed state; store events and the new state.

    `scope` separates baselines within a source (one research query must not count another query's
    results as new)."""
    current = snapshot(s, source, list(dict.fromkeys(seen)))
    state_key = f"{source}:{scope}" if scope else source
    state = {r.record_key: r for r in s.scalars(select(RecordState).where(RecordState.source == state_key))}
    source = state_key
    baseline = not state  # the first successful scan only records what exists; alerts start with the next one
    events = []
    for k, (h, title, url) in current.items():
        old = state.get(k)
        if old is None:
            s.add(RecordState(source=source, record_key=k, content_hash=h, first_seen_at=now, last_seen_at=now,
                              last_changed_at=now))
            if not baseline:
                events.append(ChangeEvent(source=source, record_key=k, kind="new", title=title, url=url, detected_at=now))
            continue
        if old.content_hash != h or old.status != "observed":
            events.append(ChangeEvent(source=source, record_key=k, kind="updated", title=title, url=url, detected_at=now))
            old.content_hash, old.last_changed_at = h, now
        old.status, old.last_seen_at = "observed", now
    if full_listing:  # only a complete listing can show that something is no longer published
        for k, old in state.items():
            if k not in current and old.status == "observed":
                old.status = "not_observed"
                events.append(ChangeEvent(source=source, record_key=k, kind="not_observed", title=None, url=None,
                                          detected_at=now))
    s.add_all(events)
    s.flush()
    return events


# ---- tasks ---------------------------------------------------------------------------------------
def ensure_tasks(s: Session, now: datetime | None = None) -> int:
    """Create the default tasks once (one per source, one per research query). Existing schedules are kept."""
    from nexus.core import taxonomy as tx
    from nexus.database import repository as repo

    now = now or utcnow()
    have = {(t.source, t.target) for t in s.scalars(select(MonitorTask))}
    wanted = [(src, "") for src in SOURCES if src != "openalex"]
    present = sorted({c.capability.key for c in repo.all_claims(s)
                      if c.capability and c.claim_category == "capability" and c.capability.key in tx.CAPABILITIES})
    wanted += [("openalex", k) for k in present if tx.CAPABILITIES[k].openalex_query]
    n = 0
    for src, target in wanted:
        if (src, target) not in have:
            s.add(MonitorTask(source=src, target=target, interval_hours=SOURCES[src][0], next_due_at=now))
            n += 1
    s.flush()
    return n


def default_runner(s: Session, task: MonitorTask, client) -> dict:
    """Run one task with the existing collectors. Returns {"seen", "errors", "records"}."""
    from nexus import pipeline
    from nexus.agents import monitoring_agent, opportunity_agent, research_agent

    if task.source == "vinnova":
        out = opportunity_agent.collect_funding(s, client)
    elif task.source == "testbeds":
        out = opportunity_agent.collect_testbeds(s, client)
    elif task.source == "events":
        out = monitoring_agent.collect_events(s, client)
    elif task.source == "news":
        out = monitoring_agent.collect_news(s, client)
    elif task.source == "openalex":
        out = research_agent.collect_research(s, client, [task.target])
    elif task.source == "directory":
        summary, _ = pipeline.sync_directory(s, client)
        out = {"seen": _profile_slugs(s, summary),
               "errors": [f"{f['url']}: {f['status']}" for f in summary["failed_urls"]] + summary["listing_errors"],
               "complete": summary["stable_end"]}  # only a confirmed end of the listing can show a removal
    else:
        raise ValueError(f"unknown source {task.source}")
    return {"seen": out.get("seen", []), "errors": out.get("errors", []), "complete": out.get("complete", True)}


def _profile_slugs(s: Session, summary: dict) -> list[str]:
    return [c.slug for c in s.scalars(select(Company).where(Company.directory_snapshot_id == summary["snapshot_id"]))]


# ---- the lock ------------------------------------------------------------------------------------
def acquire(s: Session, owner: str, now: datetime, minutes: float = 30) -> bool:
    lock = s.get(SchedulerLock, LOCK)
    if lock is not None and lock.until > now and lock.owner != owner:
        return False  # another worker is running and its lease is still valid
    if lock is None:
        s.add(SchedulerLock(name=LOCK, owner=owner, until=now + timedelta(minutes=minutes)))
    else:
        lock.owner, lock.until = owner, now + timedelta(minutes=minutes)
    s.commit()
    return True


def release(s: Session, owner: str) -> None:
    lock = s.get(SchedulerLock, LOCK)
    if lock is not None and lock.owner == owner:
        s.delete(lock)
        s.commit()


# ---- one wake-up -------------------------------------------------------------------------------------
def run_due(s: Session, now: datetime | None = None, batch: int = 6, client=None, runner=None,
            owner: str | None = None) -> dict:
    """Run up to `batch` due tasks, longest-waiting first. Returns a report for the log and the UI."""
    now = now or utcnow()
    owner = owner or f"{socket.gethostname()}:{os.getpid()}"
    ensure_tasks(s, now)
    s.commit()
    if not acquire(s, owner, now):
        return {"ran": [], "skipped": "another monitor worker holds the lock", "changes": 0}
    runner = runner or default_runner
    if client is None and runner is default_runner:
        from nexus.integrations.http_cache import HttpClient

        client = HttpClient()
    report = {"ran": [], "changes": 0, "failed": 0}
    try:
        due = list(s.scalars(select(MonitorTask).where(MonitorTask.enabled.is_(True), MonitorTask.next_due_at <= now)
                             .order_by(MonitorTask.next_due_at, MonitorTask.last_attempt_at.is_not(None),
                                       MonitorTask.last_attempt_at, MonitorTask.id).limit(batch)))
        for task in due:
            task.last_attempt_at = now
            try:
                res = runner(s, task, client)
                ok = bool(res["seen"])  # an empty answer is a failure, never "everything disappeared"
                error = None if ok else ("; ".join(res["errors"])[:1000] or "the source returned no records")
            except Exception as exc:  # a broken collector must not stop the other tasks
                s.rollback()
                task = s.get(MonitorTask, task.id)
                task.last_attempt_at = now
                ok, res, error = False, {"seen": [], "errors": [str(exc)]}, f"{type(exc).__name__}: {str(exc)[:500]}"
            if ok:
                full = SOURCES[task.source][1] and res.get("complete", True) and not res["errors"]
                events = detect_changes(s, task.source, res["seen"], full, now, scope=task.target)
                task.last_success_at, task.last_error, task.consecutive_failures = now, None, 0
                task.next_due_at = now + timedelta(hours=task.interval_hours)
                task.last_result = {"records": len(res["seen"]), "changes": len(events), "warnings": res["errors"][:5]}
                report["changes"] += len(events)
            else:  # keep the previous records and dates; retry sooner, with backoff
                task.consecutive_failures += 1
                task.last_error = error
                task.next_due_at = now + timedelta(hours=min(MAX_BACKOFF_HOURS, task.interval_hours,
                                                             0.5 * 2 ** (task.consecutive_failures - 1)))
                task.last_result = {"records": 0, "changes": 0, "error": error}
                report["failed"] += 1
            report["ran"].append({"source": task.source, "target": task.target, "ok": ok,
                                  "records": task.last_result.get("records", 0), "changes": task.last_result.get("changes", 0),
                                  "error": None if ok else error})
            s.commit()  # each task on its own: a restart loses at most the task that was running
            acquire(s, owner, utcnow())  # extend the lease while working
    finally:
        release(s, owner)
    return report


def status(s: Session, limit_events: int = 25) -> dict:
    """For the interface: every task's schedule and outcome, and the latest changes."""
    tasks = list(s.scalars(select(MonitorTask).order_by(MonitorTask.source, MonitorTask.target)))
    events = list(s.scalars(select(ChangeEvent).order_by(ChangeEvent.detected_at.desc(), ChangeEvent.id.desc())
                            .limit(limit_events)))
    lock = s.get(SchedulerLock, LOCK)
    return {
        "tasks": [{"source": t.source, "target": t.target, "interval_hours": t.interval_hours, "enabled": t.enabled,
                   "next_due_at": t.next_due_at, "last_attempt_at": t.last_attempt_at,
                   "last_success_at": t.last_success_at, "last_error": t.last_error,
                   "consecutive_failures": t.consecutive_failures, "last_result": t.last_result} for t in tasks],
        "events": [{"source": e.source, "kind": e.kind, "title": e.title, "url": e.url, "detected_at": e.detected_at,
                    "record_key": e.record_key} for e in events],
        "worker": {"running": bool(lock and lock.until > utcnow()), "owner": lock.owner if lock else None},
    }


def main() -> None:
    from nexus import pipeline
    from nexus.core.embeddings import get_embedder
    from nexus.database.database import get_sessionmaker

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run the due checks once and exit")
    mode.add_argument("--loop", type=float, metavar="SECONDS", help="wake up every SECONDS")
    ap.add_argument("--batch", type=int, default=6, help="tasks per wake-up (default 6)")
    args = ap.parse_args()
    while True:
        s = get_sessionmaker()()
        try:
            report = run_due(s, batch=args.batch)
            for r in report["ran"]:
                print(f"{utcnow():%Y-%m-%d %H:%M} {r['source']}{(':' + r['target']) if r['target'] else ''}: "
                      + (f"{r['records']} records, {r['changes']} changes" if r["ok"] else f"FAILED ({r['error']})"))
            if report.get("skipped"):
                print(report["skipped"])
            if report["changes"]:  # new information: re-rank and translate, once per wake-up
                trace = [pipeline.translate_new_texts(s)] + pipeline.recompute(s, get_embedder())
                pipeline.save_trace(trace, get_embedder().backend)
                print(f"re-ranked after {report['changes']} changes")
        finally:
            s.close()
        if args.once:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
