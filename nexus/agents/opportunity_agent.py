"""Opportunity Intelligence Agent: Vinnova calls plus test environments and events published by
Blue Science Park and Marine Technology Center of Sweden."""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import FundingOpportunity, Testbed
from nexus.integrations import vinnova
from nexus.integrations.company_sources import html_to_sentences
from nexus.integrations.http_cache import HttpClient
from nexus.security.boundary_guard import filter_untrusted
from nexus.utils.validators import utcnow

TESTBED_SOURCES = [
    ("https://www.bluesciencepark.se/vara-tjanster/test-utveckling/", "Blue Science Park", "support"),
    ("https://www.bluesciencepark.se/event/", "Blue Science Park", "event"),
    ("https://www.mtcos.se/en/", "Marine Technology Center of Sweden", "testbed"),
    ("https://www.mtcos.se/news/har-vaxer-en-ny-miljo-fram-i-karlskrona-dar-framtidens-marinteknik-testas-i-verkligheten/",
     "Marine Technology Center of Sweden", "testbed"),
]
_TEST_RE = re.compile(r"(testb[eä]d|testmilj|test environment|testas|test och experiment|testa[rs]? |verifiera|"
                      r"hackat|utvecklingssprint|innovation day|onsdagslunch|konsortier|TCL & Friends|test technology|"
                      r"marine environments)", re.I)


def current_status(f: FundingOpportunity, now: datetime | None = None) -> str:
    """Status is recomputed from the dates every time it is shown."""
    return vinnova.call_status(f.opens_at, f.deadline, now)


def collect_funding(s: Session, client: HttpClient) -> dict:
    summary = {"new": 0, "updated": 0, "errors": [], "seen": []}
    try:
        calls = vinnova.fetch_calls(client)
    except vinnova.VinnovaError as exc:
        summary["errors"].append(str(exc))
        repo.log_retrieval(s, "vinnova", vinnova.API_BASE, "error", detail=str(exc))
        return summary
    for call in calls:
        text = f"{call['title']} {call.get('description') or ''}"
        call["capability_keys"] = sorted({c for c, _ in tx.detect_capabilities(text)})
        summary["seen"].append(call["external_id"])
        row = s.scalar(select(FundingOpportunity).where(FundingOpportunity.external_id == call["external_id"]))
        if row is None:
            s.add(FundingOpportunity(**call))
            summary["new"] += 1
        else:
            for k, v in call.items():
                setattr(row, k, v)
            summary["updated"] += 1
    s.flush()
    repo.log_retrieval(s, "vinnova", f"{vinnova.API_BASE}/ansokningsomgangar", "ok", 200, records=len(calls))
    return summary


def collect_testbeds(s: Session, client: HttpClient) -> dict:
    summary = {"new": 0, "updated": 0, "errors": [], "seen": []}
    for url, source_name, kind in TESTBED_SOURCES:
        res = client.get(url, ttl_hours=72, check_robots=True)
        if not res.ok:
            summary["errors"].append(f"{url}: {res.error}")
            repo.log_retrieval(s, "testbeds", url, res.status, res.http_status, res.error)
            continue
        title, sentences, _ = html_to_sentences(res.text)
        sentences, _bad = filter_untrusted(sentences)
        hits = [x for x in sentences if _TEST_RE.search(x)][:4]
        if not hits:
            continue
        name = re.sub(r"\s*[|\-–]\s*(Blue Science Park|Marine Technology Center.*|Hem)\s*$", "", title).strip() or source_name
        description = " ".join(hits)
        tags = sorted({c for c, _ in tx.detect_capabilities(description + " " + title)})
        summary["seen"].append(url)
        row = s.scalar(select(Testbed).where(Testbed.source_url == url))
        if row is None:
            s.add(Testbed(name=f"{source_name}: {name}"[:300], description=description, kind=kind,
                          capability_keys=tags, source_url=url, source_name=source_name,
                          retrieved_at=res.retrieved_at or utcnow()))
            summary["new"] += 1
        else:
            row.description, row.capability_keys, row.retrieved_at = description, tags, res.retrieved_at or utcnow()
            summary["updated"] += 1
        repo.log_retrieval(s, "testbeds", url, res.status, res.http_status, records=1)
    s.flush()
    return summary


def funding_next_action(f: FundingOpportunity, now: datetime | None = None) -> str:
    status = current_status(f, now)
    if status == "open":
        return (f"Read the call text and check the eligibility criteria before the deadline "
                f"{f.deadline:%Y-%m-%d}. EchoRadar has not checked eligibility.")
    if status == "upcoming":
        return f"Call opens {f.opens_at:%Y-%m-%d}. Prepare a consortium and check the eligibility criteria."
    if status == "closed":
        return "This round is closed. Use it as a signal of programme interest and watch for the next round."
    return "No dates published in the open data. Check the status with Vinnova before planning."
