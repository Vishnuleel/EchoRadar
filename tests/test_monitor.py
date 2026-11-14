"""Scheduled monitoring: fair rotation, restart-safe schedules, change detection without duplicate alerts,
and failures that keep previous evidence. Deterministic: a fake runner and a fake clock, no network.
The 40-query rotation below is a scheduling test, NOT 40 live integrations."""
from datetime import datetime, timedelta

from sqlalchemy import select

from nexus import monitor
from nexus.database.models import ChangeEvent, FundingOpportunity, MonitorTask, SchedulerLock

T0 = datetime(2026, 11, 14, 8, 0)


def tasks(session, n=40, source="openalex"):
    for i in range(n):
        session.add(MonitorTask(source=source, target=f"q{i:02d}", interval_hours=24 * 7, next_due_at=T0))
    session.commit()


def no_defaults(monkeypatch):
    monkeypatch.setattr(monitor, "ensure_tasks", lambda s, now=None: 0)


def test_forty_query_rotation_is_fair(session, monkeypatch):
    no_defaults(monkeypatch)
    tasks(session)
    order = []
    ok_runner = lambda s, task, client: order.append(task.target) or {"seen": [f"W-{task.target}"], "errors": []}
    for tick in range(8):  # 8 wake-ups x 5 = 40: every query exactly once, longest-waiting first
        monitor.run_due(session, now=T0 + timedelta(minutes=tick), batch=5, runner=ok_runner, owner="w1")
    assert sorted(order) == sorted(f"q{i:02d}" for i in range(40)) and len(order) == 40
    assert order[:5] == ["q00", "q01", "q02", "q03", "q04"]
    assert monitor.run_due(session, now=T0 + timedelta(hours=1), batch=5, runner=ok_runner, owner="w1")["ran"] == []


def test_schedule_survives_a_restart_and_overlapping_workers_are_blocked(session, monkeypatch):
    no_defaults(monkeypatch)
    tasks(session, 10)
    ok = lambda s, task, client: {"seen": [f"W-{task.target}"], "errors": []}
    monitor.run_due(session, now=T0, batch=4, runner=ok, owner="w1")
    session.close()  # the worker process "restarts": state is in the database
    due = session.scalars(select(MonitorTask).where(MonitorTask.next_due_at <= T0)).all()
    assert len(due) == 6  # the 4 that ran are scheduled a week later
    session.add(SchedulerLock(name=monitor.LOCK, owner="crashed-worker", until=T0 + timedelta(minutes=20)))
    session.commit()
    blocked = monitor.run_due(session, now=T0 + timedelta(minutes=5), batch=4, runner=ok, owner="w2")
    assert blocked["ran"] == [] and "another monitor worker" in blocked["skipped"]
    resumed = monitor.run_due(session, now=T0 + timedelta(minutes=30), batch=10, runner=ok, owner="w2")  # lease expired
    assert len(resumed["ran"]) == 6 and session.get(SchedulerLock, monitor.LOCK) is None


def funding(session, ext, title, deadline):
    row = session.scalar(select(FundingOpportunity).where(FundingOpportunity.external_id == ext))
    if row is None:
        session.add(FundingOpportunity(external_id=ext, title=title, deadline=deadline, source_url=f"https://v.se/{ext}"))
    else:
        row.title, row.deadline = title, deadline
    session.flush()


def test_changes_are_detected_once_and_failures_keep_previous_evidence(session, monkeypatch):
    no_defaults(monkeypatch)
    session.add(MonitorTask(source="vinnova", target="", interval_hours=24, next_due_at=T0))
    session.commit()
    world = {"calls": [("A", "Call A", T0 + timedelta(days=30)), ("B", "Call B", T0 + timedelta(days=60))], "down": False}

    def runner(s, task, client):
        if world["down"]:
            return {"seen": [], "errors": ["HTTP 503"]}
        for ext, title, deadline in world["calls"]:
            funding(s, ext, title, deadline)
        return {"seen": [c[0] for c in world["calls"]], "errors": []}

    kinds = lambda: [(e.kind, e.record_key) for e in session.scalars(select(ChangeEvent).order_by(ChangeEvent.id))]
    monitor.run_due(session, now=T0, runner=runner, owner="w")
    assert kinds() == [], "the first scan records a baseline instead of calling everything new"
    monitor.run_due(session, now=T0 + timedelta(days=1), runner=runner, owner="w")  # unchanged scan
    assert kinds() == [], "an unchanged scan must not create alerts"

    world["down"] = True  # the source fails: nothing disappears, the error is visible, retry comes sooner
    rep = monitor.run_due(session, now=T0 + timedelta(days=2), runner=runner, owner="w")
    task = session.scalar(select(MonitorTask))
    assert rep["failed"] == 1 and "503" in task.last_error and kinds() == []
    assert task.last_success_at == T0 + timedelta(days=1) and task.next_due_at == T0 + timedelta(days=2, minutes=30)
    assert session.query(FundingOpportunity).count() == 2  # previous records kept

    world["down"] = False  # A's deadline moved, B is no longer published, C is new
    world["calls"] = [("A", "Call A", T0 + timedelta(days=45)), ("C", "Call C", T0 + timedelta(days=90))]
    monitor.run_due(session, now=T0 + timedelta(days=3), runner=runner, owner="w")
    assert sorted(kinds()) == [("new", "C"), ("not_observed", "B"), ("updated", "A")]
    assert session.query(FundingOpportunity).count() == 3  # B is flagged, never deleted
    monitor.run_due(session, now=T0 + timedelta(days=4), runner=runner, owner="w")
    assert len(kinds()) == 3, "the same change is not alerted twice"
    st = monitor.status(session)
    assert st["tasks"][0]["consecutive_failures"] == 0 and st["events"][0]["kind"] in ("updated", "not_observed")


def test_each_research_query_has_its_own_baseline(session):
    from nexus.database.models import ResearchPublication

    for w in ("W1", "W2", "W3"):
        session.add(ResearchPublication(external_id=w, title=w, source_url=f"https://openalex.org/{w}"))
    session.flush()
    assert monitor.detect_changes(session, "openalex", ["W1", "W2"], False, T0, scope="sonar") == []  # baseline
    assert monitor.detect_changes(session, "openalex", ["W2", "W3"], False, T0, scope="cable") == []  # its own baseline
    new = monitor.detect_changes(session, "openalex", ["W1", "W2", "W3"], False, T0 + timedelta(days=7), scope="sonar")
    assert [(e.kind, e.record_key) for e in new] == [("new", "W3")]


def test_a_crashing_collector_does_not_stop_the_batch(session, monkeypatch):
    no_defaults(monkeypatch)
    tasks(session, 3)

    def runner(s, task, client):
        if task.target == "q01":
            raise RuntimeError("parser broke")
        return {"seen": [f"W-{task.target}"], "errors": []}

    rep = monitor.run_due(session, now=T0, batch=3, runner=runner, owner="w")
    assert [r["ok"] for r in rep["ran"]] == [True, False, True] and "parser broke" in rep["ran"][1]["error"]
