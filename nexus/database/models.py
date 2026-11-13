"""SQLAlchemy data model (schema version 1).

Public data (companies, claims, evidence, research, funding) is separated from private data
(PrivateInteraction, UserFeedback) which is always scoped to an owning company.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from nexus.utils.validators import utcnow

SCHEMA_VERSION = 2


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Company(Base):
    __tablename__ = "company"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    directory_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)  # original public description
    user_description: Mapped[str | None] = mapped_column(Text)  # user refinement (kept separately)
    industry: Mapped[str | None] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300))
    employees: Mapped[str | None] = mapped_column(String(50))
    founded: Mapped[str | None] = mapped_column(String(20))
    profile_depth: Mapped[str] = mapped_column(String(20), default="directory")  # directory | website
    priority_domains: Mapped[list] = mapped_column(JSON, default=list)  # user-set priorities
    need_priorities: Mapped[list] = mapped_column(JSON, default=list)  # user-set: funding|testing|events|knowledge|partners
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    capabilities: Mapped[list["CompanyCapability"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    revisions: Mapped[list["CompanyProfileRevision"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class Capability(Base):
    __tablename__ = "capability"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)  # taxonomy id or custom:<slug>
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), index=True)  # value-chain role
    description: Mapped[str | None] = mapped_column(Text)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str | None] = mapped_column(String(800), index=True)
    source_type: Mapped[str] = mapped_column(String(40))  # member_directory | company_website | user | derived
    evidence_text: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime)
    verification_status: Mapped[str] = mapped_column(String(30), default="source_verified")
    # source_verified | corroborated | inferred | user_supplied | unsupported


class CompanyCapability(Base):
    """A claim that a company has a capability / interest, always tied to one evidence record."""
    __tablename__ = "company_capability"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    capability_id: Mapped[int | None] = mapped_column(ForeignKey("capability.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    claim_category: Mapped[str] = mapped_column(String(40), index=True)
    # description | industry | capability | market | development_activity | interest
    classification: Mapped[str] = mapped_column(String(12), index=True)  # FACT | INFERENCE | USER
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"))
    origin: Mapped[str] = mapped_column(String(12), default="public")  # public | user
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # users can deactivate, nothing is deleted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="capabilities")
    capability: Mapped[Capability | None] = relationship()
    evidence: Mapped[Evidence | None] = relationship()

    __table_args__ = (Index("ix_cc_company_active", "company_id", "active"),)


class ResearchPublication(Base):
    __tablename__ = "research_publication"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # OpenAlex ID
    doi: Mapped[str | None] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    abstract: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime)
    venue: Mapped[str | None] = mapped_column(String(300))
    cited_by_count: Mapped[int | None] = mapped_column(Integer)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    query: Mapped[str | None] = mapped_column(String(300))
    capability_keys: Mapped[list] = mapped_column(JSON, default=list)
    source_url: Mapped[str] = mapped_column(String(500))
    source_name: Mapped[str] = mapped_column(String(40), default="OpenAlex")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class FundingOpportunity(Base):
    __tablename__ = "funding_opportunity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(60), unique=True, index=True)  # Vinnova diarienummer
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(12), default="unknown")  # as computed at retrieval
    eligibility: Mapped[str | None] = mapped_column(Text)
    funding_terms: Mapped[str | None] = mapped_column(Text)
    capability_keys: Mapped[list] = mapped_column(JSON, default=list)
    source_url: Mapped[str] = mapped_column(String(500))
    apply_url: Mapped[str | None] = mapped_column(String(500))
    source_name: Mapped[str] = mapped_column(String(40), default="Vinnova")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Testbed(Base):
    __tablename__ = "testbed"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)  # evidence excerpt from the source
    kind: Mapped[str] = mapped_column(String(30), default="testbed")  # testbed | event | support
    capability_keys: Mapped[list] = mapped_column(JSON, default=list)
    source_url: Mapped[str] = mapped_column(String(500))
    source_name: Mapped[str] = mapped_column(String(80))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("name", "source_url"),)


class Opportunity(Base):
    """Company-specific relevance of one research / funding / testbed record (Opportunity Radar)."""
    __tablename__ = "opportunity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # research | funding | testbed | event | news
    base_relevance: Mapped[float] = mapped_column(Float, default=0.0)  # before priority / feedback adjustment
    adjustments: Mapped[list] = mapped_column(JSON, default=list)  # human-readable reasons for the adjustment
    ref_id: Mapped[int] = mapped_column(Integer)
    relevance: Mapped[float] = mapped_column(Float)
    semantic: Mapped[float] = mapped_column(Float, default=0.0)
    matched_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    why: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_opp_company_kind", "company_id", "kind"),)


class CollaborationHypothesis(Base):
    __tablename__ = "collaboration_hypothesis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(10))  # pair | triad
    title: Mapped[str] = mapped_column(Text)
    participating_companies: Mapped[list] = mapped_column(JSON)  # company ids
    required_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    missing_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    proposed_application: Mapped[str] = mapped_column(Text)
    concept_id: Mapped[str | None] = mapped_column(String(60))
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # links with claim/evidence ids
    uncertainty: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[float] = mapped_column(Float, index=True)
    score_breakdown: Mapped[dict] = mapped_column(JSON)
    research_ids: Mapped[list] = mapped_column(JSON, default=list)
    funding_ids: Mapped[list] = mapped_column(JSON, default=list)
    testbed_ids: Mapped[list] = mapped_column(JSON, default=list)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_status: Mapped[str] = mapped_column(String(30), default="hypothesis")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Recommendation(Base):
    """A hypothesis seen from one company's perspective (personalised ranking)."""
    __tablename__ = "recommendation"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("collaboration_hypothesis.id"))
    target_type: Mapped[str] = mapped_column(String(20), default="hypothesis")
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    score_breakdown: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    hypothesis: Mapped[CollaborationHypothesis] = relationship()
    __table_args__ = (Index("ix_rec_company_rank", "company_id", "rank"),)


class CompanyProfileRevision(Base):
    __tablename__ = "company_profile_revision"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    author: Mapped[str] = mapped_column(String(80), default="user")
    change_summary: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    company: Mapped[Company] = relationship(back_populates="revisions")


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)  # owner (private)
    hypothesis_key: Mapped[str] = mapped_column(String(200), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..5 human relevance
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PrivateInteraction(Base):
    """Private per-company data: questions asked, notes. Never shown to another company."""
    __tablename__ = "private_interaction"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # query | note
    text: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RetrievalLog(Base):
    __tablename__ = "retrieval_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    url: Mapped[str] = mapped_column(String(800))
    status: Mapped[str] = mapped_column(String(30))  # ok | cached | error | blocked_robots | offline
    http_status: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    records: Mapped[int | None] = mapped_column(Integer)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Event(Base):
    """A conference, workshop, lunch seminar or networking format published by a public source."""
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    date_text: Mapped[str | None] = mapped_column(String(200))  # exactly as published
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    date_note: Mapped[str | None] = mapped_column(String(200))  # e.g. "year not stated on the page"
    time_text: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(300))
    format: Mapped[str] = mapped_column(String(20), default="unknown")  # in_person | online | unknown
    audience: Mapped[str | None] = mapped_column(Text)
    organiser: Mapped[str] = mapped_column(String(120))
    capability_keys: Mapped[list] = mapped_column(JSON, default=list)
    source_url: Mapped[str] = mapped_column(String(500))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class NewsUpdate(Base):
    """A dated public news item: regional development, ecosystem news or member development."""
    __tablename__ = "news_update"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)  # first sentences of the article, verbatim
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    source_name: Mapped[str] = mapped_column(String(120))
    mentioned_company_ids: Mapped[list] = mapped_column(JSON, default=list)
    capability_keys: Mapped[list] = mapped_column(JSON, default=list)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class SavedItem(Base):
    """Private: an opportunity a company saved, or marked useful / not useful."""
    __tablename__ = "saved_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    ref_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(12))  # saved | useful | not_useful
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("company_id", "kind", "ref_id", "action"),)


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    backend: Mapped[str] = mapped_column(String(120), primary_key=True)
    vector: Mapped[bytes] = mapped_column(LargeBinary)
