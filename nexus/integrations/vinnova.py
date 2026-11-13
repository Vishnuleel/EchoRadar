"""Vinnova open data connector (https://data.vinnova.se/api/...).

The open-data API needs no authentication. Endpoint `ansokningsomgangar/<date>` returns application
rounds ("calls") changed since <date>, including opening and closing dates and, for most current
calls, short English texts about scope, who can apply and the funding offered.

Status is always derived from the dates relative to *now*: a call is never shown as open after its
closing date, and calls without dates are labelled "unknown".
"""
from __future__ import annotations

from datetime import datetime, timedelta

from nexus.integrations.http_cache import HttpClient
from nexus.utils.validators import parse_date, utcnow

API_BASE = "https://data.vinnova.se/api"


class VinnovaError(RuntimeError):
    pass


def call_status(opens_at: datetime | None, deadline: datetime | None, now: datetime | None = None) -> str:
    now = now or utcnow()
    if deadline is None:
        return "unknown"
    if deadline < now:
        return "closed"
    if opens_at is not None and opens_at > now:
        return "upcoming"
    return "open"


def _clean(text) -> str:
    t = (text or "").strip()
    return "" if t.upper() in ("N/A", "XX", "X") or len(t) < 3 else t


def parse_call(rec: dict, retrieved_at: datetime, now: datetime | None = None) -> dict | None:
    """Convert one API record into a FundingOpportunity dict. Returns None for unusable records."""
    dnr = rec.get("Diarienummer")
    title = _clean(rec.get("TitelEngelska")) or _clean(rec.get("Titel"))
    if not dnr or not title or rec.get("Publik") == 0:
        return None
    web = {w.get("TextID"): (_clean(w.get("TextEn")) or _clean(w.get("TextSv")))
           for w in rec.get("WebTextLista") or []}
    desc_parts = [_clean(rec.get("BeskrivningEngelska")) or _clean(rec.get("Beskrivning")), web.get(1, "")]
    description = " ".join(p for p in desc_parts if p and p != title).strip()
    opens_at, deadline = parse_date(rec.get("Oppningsdatum")), parse_date(rec.get("Stangningsdatum"))
    apply_url = next((l.get("URL") for l in rec.get("LankLista") or [] if l.get("URL")), None)
    return {
        "external_id": dnr,
        "title": title,
        "description": description or None,
        "opens_at": opens_at,
        "deadline": deadline,
        "status": call_status(opens_at, deadline, now),
        "eligibility": web.get(2) or None,   # "who can apply" text as published by Vinnova
        "funding_terms": web.get(3) or None,
        "source_url": f"{API_BASE}/ansokningsomgangar/{dnr}",
        "apply_url": apply_url,
        "retrieved_at": retrieved_at,
    }


def fetch_calls(client: HttpClient, changed_since_days: int = 150, keep_closed_days: int = 365,
                now: datetime | None = None) -> list[dict]:
    """Retrieve calls changed in the last N days. Raises VinnovaError if the API cannot be read."""
    now = now or utcnow()
    since = (now - timedelta(days=changed_since_days)).strftime("%Y-%m-01")
    url = f"{API_BASE}/ansokningsomgangar/{since}"
    res = client.get(url, ttl_hours=12, timeout=180)
    if not res.ok:
        raise VinnovaError(f"Vinnova open data API not available ({res.error}); URL {url}")
    try:
        data = res.json()
    except ValueError as exc:
        raise VinnovaError(f"Vinnova API returned non-JSON content: {exc}") from exc
    if not isinstance(data, list):
        raise VinnovaError("Vinnova API returned an unexpected structure")
    out, seen = [], set()
    for rec in data:
        call = parse_call(rec, res.retrieved_at, now)
        if call is None or call["external_id"] in seen:
            continue
        if call["deadline"] and call["deadline"] < now - timedelta(days=keep_closed_days):
            continue  # very old rounds add noise, not opportunities
        seen.add(call["external_id"])
        out.append(call)
    return out
