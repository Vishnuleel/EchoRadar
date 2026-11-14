"""Monitoring Agent: events and dated ecosystem / member news.

Covers the brief's "Events", "Knowledge and trends (regional developments)" and "Member
developments" areas with what the public sources actually publish. Items are de-duplicated by key
/ URL, tagged with capabilities, and news is linked to the member companies it names.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import Event, NewsUpdate
from nexus.integrations import bsp_sources
from nexus.integrations.http_cache import HttpClient
from nexus.security.boundary_guard import scan_untrusted


def _tags(text: str) -> list[str]:
    return sorted({c for c, _ in tx.detect_capabilities(text)})


def collect_events(s: Session, client: HttpClient) -> dict:
    summary = {"new": 0, "updated": 0, "errors": [], "seen": []}
    events, errors = bsp_sources.fetch_events(client)
    summary["errors"] = errors
    for ev in events:
        if scan_untrusted(f"{ev['title']} {ev.get('description') or ''}"):
            continue  # instruction-like text in external content is never stored as an event
        summary["seen"].append(ev["key"])
        ev["capability_keys"] = _tags(f"{ev['title']} {ev.get('description') or ''}")
        row = s.scalar(select(Event).where(Event.key == ev["key"]))
        if row is None:
            s.add(Event(**ev))
            summary["new"] += 1
        else:
            for k, v in ev.items():
                setattr(row, k, v)
            summary["updated"] += 1
    s.flush()
    repo.log_retrieval(s, "events", bsp_sources.EVENT_PROGRAMME_URL, "error" if errors and not events else "ok",
                       records=len(events), detail="; ".join(errors) or None)
    return summary


def mentioned_companies(text: str, companies: list) -> list[int]:
    """Members named in a text. Short or generic names need a whole-word, case-sensitive match."""
    ids = []
    for c in companies:
        name = c.name.split(" - ")[0].strip()
        if len(name) < 3:
            continue
        if re.search(r"(?<![\wåäöÅÄÖ])" + re.escape(name) + r"(?![\wåäöÅÄÖ])", text):
            ids.append(c.id)
    return ids


def collect_news(s: Session, client: HttpClient) -> dict:
    summary = {"new": 0, "updated": 0, "member_mentions": 0, "errors": [], "seen": []}
    items, errors = bsp_sources.fetch_news(client)
    summary["errors"] = errors
    companies = repo.companies(s)
    for item in items:
        summary["seen"].append(item["source_url"])
        body = item.pop("body", "")
        text = f"{item['title']} {item.get('summary') or ''} {body}"
        if scan_untrusted(text):
            item["summary"] = None  # keep the headline and link, drop the suspicious body text
            text = item["title"]
        item["capability_keys"] = _tags(text)
        item["mentioned_company_ids"] = mentioned_companies(f"{item['title']} {item.get('summary') or ''}", companies)
        summary["member_mentions"] += len(item["mentioned_company_ids"])
        row = s.scalar(select(NewsUpdate).where(NewsUpdate.source_url == item["source_url"]))
        if row is None:
            s.add(NewsUpdate(**item))
            summary["new"] += 1
        else:
            for k, v in item.items():
                setattr(row, k, v)
            summary["updated"] += 1
    s.flush()
    repo.log_retrieval(s, "news", bsp_sources.BSP_NEWS_URL, "error" if errors and not items else "ok",
                       records=len(items), detail="; ".join(errors) or None)
    return summary
