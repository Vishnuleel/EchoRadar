"""The AI radar: one uniform, explainable item format for every monitoring area.

Every item answers the three questions from the challenge brief
  * why it fits        - the match with the company profile
  * what supports it   - source link, published terms, retrieval date
  * what to do next    - one concrete step
and states what is uncertain. Items are built from stored Opportunity rows (ranking) joined with
the source records, so nothing here is generated free text.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.agents.opportunity_agent import current_status
from nexus.core import taxonomy as tx
from nexus.database.models import (Company, Event, FundingOpportunity, NewsUpdate, Opportunity, ResearchPublication, SavedItem,
                                   Testbed)
from nexus.utils.validators import utcnow

MODEL = {"funding": FundingOpportunity, "research": ResearchPublication, "testbed": Testbed, "event": Event,
         "news": NewsUpdate}
AREA = {"funding": "Funding", "testbed": "Testing opportunities", "event": "Events", "research": "Knowledge and trends",
        "news": "Knowledge and trends"}
# which radar kinds a stated need priority boosts
NEED_TO_KINDS = {"funding": ["funding"], "testing": ["testbed"], "events": ["event"], "knowledge": ["research", "news"],
                 "partners": []}
PRIORITY_BOOST = 15.0
FEEDBACK_BOOST = 5.0


def describe(kind: str, row, now: datetime | None = None) -> dict | None:
    """Source-derived fields of one record. Returns None for items that must not be offered (closed calls)."""
    now = now or utcnow()
    d = {"kind": kind, "area": AREA[kind], "ref_id": row.id, "url": row.source_url, "retrieved_at": row.retrieved_at,
         "status": None, "flags": [], "terms": [], "apply_url": None}
    if kind == "funding":
        status = current_status(row, now)
        if status == "closed":
            return None
        d.update(title=row.title, source="Vinnova open data", status=status, excerpt=(row.description or "")[:360],
                 date_label=(f"opens {row.opens_at:%Y-%m-%d}, " if status == "upcoming" and row.opens_at else "")
                 + (f"deadline {row.deadline:%Y-%m-%d}" if row.deadline else "no deadline published"),
                 sort_date=row.deadline, apply_url=row.apply_url,
                 uncertainty="Potential match only. Eligibility has not been checked against the call criteria.")
        if row.eligibility:
            d["terms"].append(("Who can apply (Vinnova's text)", row.eligibility[:340]))
        if row.funding_terms:
            d["terms"].append(("Funding (Vinnova's text)", row.funding_terms[:280]))
        if row.deadline and row.deadline - now <= timedelta(days=30):
            d["flags"].append(f"closes in {(row.deadline - now).days} days")
        if row.opens_at and timedelta(0) <= now - row.opens_at <= timedelta(days=45):
            d["flags"].append("recently opened")
    elif kind == "testbed":
        d.update(title=row.name, source=row.source_name, excerpt=row.description[:360], date_label="no dates published",
                 sort_date=None, uncertainty="Access terms, cost and availability are not published on the source page.")
    elif kind == "event":
        upcoming = row.starts_at is not None and row.starts_at >= now
        fmt = {"in_person": "in person", "online": "online", "unknown": "format not stated"}[row.format]
        d.update(title=row.title, source=row.organiser, excerpt=(row.description or "")[:360],
                 status="upcoming" if upcoming else ("past" if row.starts_at else "recurring"),
                 date_label=(row.date_text or "date not published") + f" - {fmt}" + (f" - {row.location}" if row.location else ""),
                 sort_date=row.starts_at, uncertainty=row.date_note or "")
        if row.audience:
            d["terms"].append(("Intended audience", row.audience))
    elif kind == "research":
        authors = ", ".join(row.authors[:3]) + (" et al." if len(row.authors) > 3 else "")
        d.update(title=row.title, source="OpenAlex", excerpt=(row.abstract or "No abstract available from OpenAlex.")[:360],
                 date_label=f"published {row.publication_date:%Y-%m-%d}" if row.publication_date else "date not published",
                 sort_date=row.publication_date,
                 uncertainty="Relevance is estimated from text similarity; the paper has not been read by a person.")
        if authors:
            d["terms"].append(("Authors", authors + (f" - {row.venue}" if row.venue else "")))
    else:  # news
        d.update(title=row.title, source=row.source_name, excerpt=(row.summary or "No summary could be read.")[:360],
                 date_label=f"published {row.published_at:%Y-%m-%d}" if row.published_at else "date not published",
                 sort_date=row.published_at, uncertainty="Only the opening of the article is quoted; read the source for context.")
        if row.published_at and now - row.published_at <= timedelta(days=30):
            d["flags"].append("new this month")
    return d


def company_items(s: Session, company_id: int, kinds: list[str] | None = None, min_relevance: float = 0.0,
                  include_past_events: bool = False, now: datetime | None = None) -> list[dict]:
    """Ranked radar items for one company, most relevant first."""
    now = now or utcnow()
    q = select(Opportunity).where(Opportunity.company_id == company_id, Opportunity.relevance >= min_relevance)
    if kinds:
        q = q.where(Opportunity.kind.in_(kinds))
    marks = {}
    for m in s.scalars(select(SavedItem).where(SavedItem.company_id == company_id)):
        marks.setdefault((m.kind, m.ref_id), set()).add(m.action)
    out = []
    ops = list(s.scalars(q.order_by(Opportunity.relevance.desc())))
    # one query per monitoring area instead of one per item
    ref_ids: dict[str, set] = {}
    for o in ops:
        ref_ids.setdefault(o.kind, set()).add(o.ref_id)
    rows = {(kind, r.id): r for kind, ids in ref_ids.items()
            for r in s.scalars(select(MODEL[kind]).where(MODEL[kind].id.in_(ids)))}
    for o in ops:
        row = rows.get((o.kind, o.ref_id))
        d = describe(o.kind, row, now) if row is not None else None
        if d is None or (d["status"] == "past" and not include_past_events):
            continue
        caps = [tx.CAPABILITIES[c].name for c in o.matched_capabilities[:3] if c in tx.CAPABILITIES]
        d.update(relevance=o.relevance, base_relevance=o.base_relevance, adjustments=list(o.adjustments or []),
                 why=o.why, next_action=o.next_action, matched=caps, marks=sorted(marks.get((o.kind, o.ref_id), [])))
        out.append(d)
    # areas the company marked as a current need come first; within a tier, most relevant first
    company = s.get(Company, company_id)
    first = {k for n in (company.need_priorities or []) for k in NEED_TO_KINDS.get(n, [])} if company else set()
    for d in out:
        d["priority_area"] = d["kind"] in first
    out.sort(key=lambda d: (not d["priority_area"], -d["relevance"]))
    return out


def weekly_digest(s: Session, company_id: int, now: datetime | None = None) -> dict:
    """'What should this company know this week?' - the best few items per monitoring area."""
    items = company_items(s, company_id, now=now)
    by_kind = {}
    for it in items:
        by_kind.setdefault(it["kind"], []).append(it)
    urgent = [it for it in items if any("closes in" in f for f in it["flags"])]
    return {
        "headline": items[:1],
        "priority_kinds": sorted({i["kind"] for i in items if i["priority_area"]}),
        "urgent": urgent[:3],
        "funding": by_kind.get("funding", [])[:3],
        "testing": by_kind.get("testbed", [])[:2],
        "events": sorted(by_kind.get("event", []), key=lambda i: (i["sort_date"] is None, i["sort_date"] or now))[:3],
        "knowledge": (by_kind.get("news", [])[:2] + by_kind.get("research", [])[:2]),
        "total": len(items),
    }


def mark(s: Session, acting_company_id: int | None, kind: str, ref_id: int, action: str, on: bool = True) -> None:
    """Save an item or record useful / not useful. Private to the acting company."""
    from nexus.security.privacy import PrivacyError

    if acting_company_id is None:
        raise PrivacyError("Select the company you are acting as before saving or rating items.")
    if action not in ("saved", "useful", "not_useful") or kind not in MODEL:
        raise ValueError("unknown action or kind")
    existing = s.scalar(select(SavedItem).where(SavedItem.company_id == acting_company_id, SavedItem.kind == kind,
                                                SavedItem.ref_id == ref_id, SavedItem.action == action))
    if on and existing is None:
        opposite = {"useful": "not_useful", "not_useful": "useful"}.get(action)
        if opposite:
            for row in s.scalars(select(SavedItem).where(SavedItem.company_id == acting_company_id, SavedItem.kind == kind,
                                                         SavedItem.ref_id == ref_id, SavedItem.action == opposite)):
                s.delete(row)
        s.add(SavedItem(company_id=acting_company_id, kind=kind, ref_id=ref_id, action=action))
    elif not on and existing is not None:
        s.delete(existing)
    s.flush()
