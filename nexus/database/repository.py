"""Query helpers. Keeps SQL out of agents and UI pages."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from nexus.core.taxonomy import CAPABILITIES
from nexus.database.models import (Capability, CollaborationHypothesis, Company, CompanyCapability, Event, NewsUpdate,
                                   CompanyProfileRevision, Evidence, FundingOpportunity, Opportunity,
                                   Recommendation, ResearchPublication, RetrievalLog, Testbed, UserFeedback)
from nexus.utils.validators import utcnow


def sync_taxonomy(s: Session) -> dict[str, Capability]:
    existing = {c.key: c for c in s.scalars(select(Capability))}
    for cap in CAPABILITIES.values():
        row = existing.get(cap.id)
        if row is None:
            row = Capability(key=cap.id, name=cap.name, category=cap.role, description=cap.description)
            s.add(row)
            existing[cap.id] = row
        else:
            row.name, row.category, row.description = cap.name, cap.role, cap.description
    s.flush()
    return existing


def companies(s: Session) -> list[Company]:
    return list(s.scalars(select(Company).order_by(Company.name)))


def company_by_slug(s: Session, slug: str) -> Company | None:
    return s.scalar(select(Company).where(Company.slug == slug))


def claims(s: Session, company_id: int, active_only: bool = True) -> list[CompanyCapability]:
    q = (select(CompanyCapability).where(CompanyCapability.company_id == company_id)
         .options(selectinload(CompanyCapability.evidence), selectinload(CompanyCapability.capability))
         .order_by(CompanyCapability.claim_category, CompanyCapability.id))
    if active_only:
        q = q.where(CompanyCapability.active.is_(True))
    return list(s.scalars(q))


def all_claims(s: Session) -> list[CompanyCapability]:
    return list(s.scalars(select(CompanyCapability).where(CompanyCapability.active.is_(True))
                          .options(selectinload(CompanyCapability.evidence),
                                   selectinload(CompanyCapability.capability))))


def add_evidence(s: Session, **kw) -> Evidence:
    ev = Evidence(**kw)
    s.add(ev)
    s.flush()
    return ev


def add_revision(s: Session, company: Company, summary: str, author: str = "user") -> CompanyProfileRevision:
    snap = {
        "description": company.description,
        "user_description": company.user_description,
        "priority_domains": list(company.priority_domains or []),
        "claims": [
            {"id": c.id, "text": c.claim_text, "category": c.claim_category, "classification": c.classification,
             "origin": c.origin, "active": c.active, "capability": c.capability.key if c.capability else None}
            for c in claims(s, company.id, active_only=False)
        ],
    }
    rev = CompanyProfileRevision(company_id=company.id, change_summary=summary, snapshot=snap, author=author)
    s.add(rev)
    company.updated_at = utcnow()
    s.flush()
    return rev


def clear_derived(s: Session) -> None:
    """Remove computed rows before a recompute. Source data and user data are never touched."""
    s.execute(delete(Recommendation))
    s.execute(delete(CollaborationHypothesis))
    s.execute(delete(Opportunity))


def log_retrieval(s: Session, source: str, url: str, status: str, http_status=None, detail=None, records=None):
    s.add(RetrievalLog(source=source, url=url[:800], status=status, http_status=http_status,
                       detail=(detail or "")[:1000] or None, records=records))


def counts(s: Session) -> dict[str, int]:
    def n(q):
        return int(s.scalar(q) or 0)

    return {
        "companies": n(select(func.count(Company.id))),
        "companies_website": n(select(func.count(Company.id)).where(Company.profile_depth == "website")),
        "fact_claims": n(select(func.count(CompanyCapability.id)).where(
            CompanyCapability.active.is_(True), CompanyCapability.classification == "FACT")),
        "verified_capabilities": n(select(func.count(CompanyCapability.id)).where(
            CompanyCapability.active.is_(True), CompanyCapability.classification == "FACT",
            CompanyCapability.claim_category == "capability")),
        "inferences": n(select(func.count(CompanyCapability.id)).where(
            CompanyCapability.active.is_(True), CompanyCapability.classification == "INFERENCE")),
        "user_claims": n(select(func.count(CompanyCapability.id)).where(
            CompanyCapability.active.is_(True), CompanyCapability.classification == "USER")),
        "research": n(select(func.count(ResearchPublication.id))),
        "funding": n(select(func.count(FundingOpportunity.id))),
        "testbeds": n(select(func.count(Testbed.id))),
        "hypotheses": n(select(func.count(CollaborationHypothesis.id))),
        "events": n(select(func.count(Event.id))),
        "news": n(select(func.count(NewsUpdate.id))),
        "feedback": n(select(func.count(UserFeedback.id))),
        "demo_records": (n(select(func.count(Company.id)).where(Company.is_demo.is_(True)))
                         + n(select(func.count(ResearchPublication.id)).where(ResearchPublication.is_demo.is_(True)))
                         + n(select(func.count(FundingOpportunity.id)).where(FundingOpportunity.is_demo.is_(True)))
                         + n(select(func.count(Testbed.id)).where(Testbed.is_demo.is_(True)))),
    }


def recommendations(s: Session, company_id: int, limit: int = 20) -> list[Recommendation]:
    return list(s.scalars(select(Recommendation).where(Recommendation.company_id == company_id)
                          .options(selectinload(Recommendation.hypothesis))
                          .order_by(Recommendation.rank).limit(limit)))


def recent_logs(s: Session, limit: int = 30) -> list[RetrievalLog]:
    return list(s.scalars(select(RetrievalLog).order_by(RetrievalLog.retrieved_at.desc()).limit(limit)))
