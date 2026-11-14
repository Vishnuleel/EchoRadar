"""Company Intelligence Agent.

Turns public text (member directory entry + official website pages) into a structured profile in
which every claim carries its source URL, the supporting excerpt, the retrieval time, a FACT /
INFERENCE classification, a confidence indicator and a verification status.

Extraction is deterministic: a claim is created only when a retrieved sentence matches the
capability taxonomy, and the sentence itself is stored as the evidence. Nothing is generated.
Inferred interests are derived from the evidenced capabilities and are always labelled INFERENCE.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nexus.core import taxonomy as tx
from nexus.core.evidence import mask_name, statement_status
from nexus.database import repository as repo
from nexus.database.models import Company, CompanyCapability, Evidence
from nexus.integrations.company_sources import CrawlResult, MemberRecord
from nexus.security.boundary_guard import filter_untrusted
from nexus.utils.validators import is_valid_url

_MARKET_RE = re.compile(r"(kundsegment|customers include|kunder inom|våra kunder är|our customers are|we serve|"
                        r"statliga myndigheter|kommersiell sjöfart)", re.I)
_ACTIVITY_RE = re.compile(r"(pilot|awarded|eu funding|eu-finansier|forskningsprojekt|research project|"
                          r"demonstrator|prototyp|innovation project|innovationsprojekt)", re.I)
_NEWS_URL = re.compile(r"(news|nyheter|aktuellt|innovation)", re.I)
_GEO_RE = re.compile(r"(över hela världen|världsomspännande|worldwide|globalt|\bglobal(?:ly)?\b|internationell|"
                     r"norden|nordic|östersjö|baltic sea|europ[ae]|skandinav|scandinavia|levererar globalt)", re.I)
_COLLAB_RE = re.compile(r"(samarbete[nt]? med|i samverkan med|partnerskap med|in collaboration with|"
                        r"partnership with|samarbeten med)", re.I)
NEED_AREAS = {"funding": "Funding opportunities", "testing": "Testing opportunities", "events": "Events",
              "knowledge": "Knowledge and trends", "partners": "Potential partners"}
# Pages that mostly talk about other organisations or events: never used for capability claims.
_NON_SELF_URL = re.compile(r"(news|nyheter|aktuellt|partner|referen[sc]|reference|/\?post_type)", re.I)
_SELF_REF = re.compile(r"(?<![\wåäö])(vi|vår|våra|vårt|oss|we|our|us|erbjuder|tjänster inom|services)(?![\wåäö])", re.I)


def is_self_description(sentence: str, company_name: str) -> bool:
    """True when a website sentence talks about the company itself (first person, or by name)."""
    if sentence.rstrip().endswith(("...", "…")):
        return False  # truncated teaser text
    first = re.escape(company_name.split()[0])
    return bool(_SELF_REF.search(sentence) or re.search(first, sentence, re.I))


class Claim(BaseModel):
    claim_text: str
    claim_category: str  # description | industry | capability | market | development_activity | interest
    classification: str  # FACT | INFERENCE
    confidence: float = Field(ge=0.0, le=1.0)
    verification_status: str
    evidence_url: str | None
    evidence_text: str
    source_type: str
    retrieved_at: datetime | None
    capability_key: str | None = None

    @field_validator("classification")
    @classmethod
    def _cls(cls, v):
        if v not in ("FACT", "INFERENCE", "USER"):
            raise ValueError("classification must be FACT, INFERENCE or USER")
        return v

    @field_validator("evidence_url")
    @classmethod
    def _url(cls, v):
        if v is not None and not is_valid_url(v):
            raise ValueError(f"invalid evidence URL: {v}")
        return v


class ProfileDraft(BaseModel):
    slug: str
    name: str
    website: str | None
    directory_url: str | None
    description: str | None
    industry: str | None
    location: str | None
    employees: str | None
    founded: str | None
    profile_depth: str
    claims: list[Claim]
    quarantined: list[str] = []
    warnings: list[str] = []
    rejected: list[str] = []  # statements that matched a capability but are negated, historical or about others


def build_profile(member: MemberRecord, crawl: CrawlResult | None = None) -> ProfileDraft:
    claims: list[Claim] = []
    warnings: list[str] = list(crawl.errors) if crawl else []
    quarantined: list[str] = []

    # --- verified facts straight from the member directory
    if member.description:
        claims.append(Claim(claim_text=member.description, claim_category="description", classification="FACT",
                            confidence=0.8, verification_status="source_verified",
                            evidence_url=member.directory_url, evidence_text=member.description,
                            source_type="member_directory", retrieved_at=member.retrieved_at))
    if member.industry:
        claims.append(Claim(claim_text=f"Industry as listed in the member directory: {member.industry}",
                            claim_category="industry", classification="FACT", confidence=0.8,
                            verification_status="source_verified", evidence_url=member.directory_url,
                            evidence_text=f"Bransch: {member.industry}", source_type="member_directory",
                            retrieved_at=member.retrieved_at))

    # --- sentences from all sources: (text, url, source_type, retrieved_at)
    sources: list[tuple[str, str, str, datetime]] = []
    if member.description:
        sources.append((member.description, member.directory_url, "member_directory", member.retrieved_at))
    if member.industry:
        sources.append((member.industry, member.directory_url, "member_directory", member.retrieved_at))
    website_sentences = 0
    for page in (crawl.pages if crawl else []):
        safe, bad = filter_untrusted(page.sentences)
        quarantined.extend(f"{page.url}: {b[:200]}" for b in bad)
        for sent in safe:
            sources.append((sent, page.url, "company_website", page.retrieved_at))
            website_sentences += 1
    if crawl and not website_sentences:
        warnings.append("Website could not be read; profile is based on the member directory only.")

    # --- capability claims: one per (capability, distinct source URL), at most 3 per capability
    by_cap: dict[str, list[tuple[str, str, str, datetime]]] = defaultdict(list)
    rejected: list[str] = []
    for sent, url, stype, ts in sources:
        if stype == "company_website" and (_NON_SELF_URL.search(url) or not is_self_description(sent, member.name)):
            continue  # only self-descriptive statements on the company's own offer/about pages count
        for cap_id, term in tx.detect_capabilities(mask_name(sent, member.name)):
            status = statement_status(sent, term)
            if status != "current":  # "we no longer build X", "our customer builds X": not a current capability
                rejected.append(f"{tx.CAPABILITIES[cap_id].name} ({status.replace('_', ' ')}): {sent[:160]} [{url}]")
                continue
            if all(u != url for _, u, _, _ in by_cap[cap_id]) and len(by_cap[cap_id]) < 3:
                by_cap[cap_id].append((sent, url, stype, ts))
    for cap_id, evs in by_cap.items():
        cap = tx.CAPABILITIES[cap_id]
        corroborated = len({u for _, u, _, _ in evs}) >= 2
        for sent, url, stype, ts in evs:
            claims.append(Claim(
                claim_text=f"Public source describes activity in: {cap.name}", claim_category="capability",
                classification="FACT", confidence=0.9 if corroborated else (0.75 if stype == "company_website" else 0.7),
                verification_status="corroborated" if corroborated else "source_verified",
                evidence_url=url, evidence_text=sent, source_type=stype, retrieved_at=ts, capability_key=cap_id))

    # --- geographical focus: the listed location plus literally stated reach
    if member.location:
        claims.append(Claim(claim_text=f"Located in: {member.location}", claim_category="geography", classification="FACT",
                            confidence=0.8, verification_status="source_verified", evidence_url=member.directory_url,
                            evidence_text=f"Ort: {member.location}", source_type="member_directory",
                            retrieved_at=member.retrieved_at))
    n_geo = n_col = 0
    for sent, url, stype, ts in sources:
        if sent.rstrip().endswith(("...", "…")) or (stype == "company_website" and not is_self_description(sent, member.name)):
            continue
        status = statement_status(sent)
        if status != "current" and not (status == "third_party" and _COLLAB_RE.search(sent)):
            continue  # a collaboration naturally names the partner; everything else must be first-party and current
        if n_geo < 2 and _GEO_RE.search(sent) and not (stype == "company_website" and _NON_SELF_URL.search(url)):
            n_geo += 1
            claims.append(Claim(claim_text=sent, claim_category="geography", classification="FACT", confidence=0.7,
                                verification_status="source_verified", evidence_url=url, evidence_text=sent,
                                source_type=stype, retrieved_at=ts))
        elif n_col < 3 and stype == "company_website" and _COLLAB_RE.search(sent):
            n_col += 1
            claims.append(Claim(claim_text=sent, claim_category="collaboration", classification="FACT", confidence=0.7,
                                verification_status="source_verified", evidence_url=url, evidence_text=sent,
                                source_type=stype, retrieved_at=ts))

    # --- markets and development activities (only when literally stated on the website)
    n_market = n_act = 0
    for sent, url, stype, ts in sources:
        if stype != "company_website":
            continue
        if sent.rstrip().endswith(("...", "…")) or statement_status(sent) != "current":
            continue
        if n_market < 3 and _MARKET_RE.search(sent) and not _NON_SELF_URL.search(url):
            n_market += 1
            claims.append(Claim(claim_text=sent, claim_category="market", classification="FACT", confidence=0.7,
                                verification_status="source_verified", evidence_url=url, evidence_text=sent,
                                source_type=stype, retrieved_at=ts))
        elif n_act < 4 and _NEWS_URL.search(url) and _ACTIVITY_RE.search(sent):
            n_act += 1
            claims.append(Claim(claim_text=sent, claim_category="development_activity", classification="FACT",
                                confidence=0.7, verification_status="source_verified", evidence_url=url,
                                evidence_text=sent, source_type=stype, retrieved_at=ts))

    # --- inferred interests (clearly separated from facts)
    domain_support: dict[str, list[str]] = defaultdict(list)
    for cap_id in by_cap:
        if tx.CAPABILITIES[cap_id].role == "ENABLER":
            continue
        for d in tx.CAPABILITIES[cap_id].domains:
            domain_support[d].append(cap_id)
    ranked = sorted(domain_support.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    min_support = 2 if any(len(v) >= 2 for _, v in ranked) else 1
    for domain, caps in [r for r in ranked if len(r[1]) >= min_support][:3]:
        names = ", ".join(tx.CAPABILITIES[c].name for c in caps[:4])
        first = by_cap[caps[0]][0]
        claims.append(Claim(
            claim_text=f"May be interested in: {tx.DOMAINS[domain]}", claim_category="interest",
            classification="INFERENCE", confidence=round(min(0.6, 0.25 + 0.1 * len(caps)), 2),
            verification_status="inferred",
            evidence_url=first[1],
            evidence_text=f"Inferred by NEXUS from evidenced capabilities ({names}). "
                          f"Not stated by the company. Domain key: {domain}",
            source_type="derived", retrieved_at=first[3]))

    return ProfileDraft(slug=member.slug, name=member.name, website=member.website,
                        directory_url=member.directory_url, description=member.description,
                        industry=member.industry, location=member.location, employees=member.employees,
                        founded=member.founded, profile_depth="website" if website_sentences else "directory",
                        claims=claims, quarantined=quarantined, warnings=warnings, rejected=rejected)


def persist_profile(s: Session, draft: ProfileDraft, is_demo: bool = False) -> Company:
    """Insert or refresh a public profile. User refinements and deactivations survive a refresh."""
    caps = repo.sync_taxonomy(s)
    company = repo.company_by_slug(s, draft.slug)
    if company is None:
        company = Company(slug=draft.slug, name=draft.name, priority_domains=[])
        s.add(company)
        s.flush()
    deactivated = {(c.capability.key if c.capability else None, c.claim_category, c.claim_text)
                   for c in repo.claims(s, company.id, active_only=False) if c.origin == "public" and not c.active}
    old = list(s.scalars(select(CompanyCapability).where(CompanyCapability.company_id == company.id,
                                                         CompanyCapability.origin == "public")))
    old_ev = [c.evidence_id for c in old if c.evidence_id]
    for c in old:
        s.delete(c)
    s.flush()
    if old_ev:
        s.execute(delete(Evidence).where(Evidence.id.in_(old_ev)))
    for field in ("name", "website", "directory_url", "description", "industry", "location", "employees",
                  "founded", "profile_depth"):
        setattr(company, field, getattr(draft, field))
    company.is_demo = is_demo
    for cl in draft.claims:
        ev = repo.add_evidence(s, source_url=cl.evidence_url, source_type=cl.source_type,
                               evidence_text=cl.evidence_text, retrieved_at=cl.retrieved_at,
                               verification_status=cl.verification_status)
        key = (cl.capability_key, cl.claim_category, cl.claim_text)
        s.add(CompanyCapability(company_id=company.id,
                                capability_id=caps[cl.capability_key].id if cl.capability_key else None,
                                claim_text=cl.claim_text, claim_category=cl.claim_category,
                                classification=cl.classification, confidence=cl.confidence, evidence_id=ev.id,
                                origin="public", active=key not in deactivated))
    s.flush()
    return company


# ---- user refinements ---------------------------------------------------------------------------
def add_user_claim(s: Session, company: Company, text: str, category: str, embedder=None) -> list[CompanyCapability]:
    """Add a user-supplied capability ("we have") or interest ("we are looking for").

    The text is normalised to taxonomy capabilities where possible. User claims are classified
    USER, never FACT: they are not independently verified and are scored accordingly.
    """
    from nexus.core.matching_engine import normalise_capability

    if category not in ("capability", "interest"):
        raise ValueError("category must be 'capability' or 'interest'")
    text = " ".join((text or "").split())[:300]
    if not text:
        raise ValueError("text is empty")
    caps = repo.sync_taxonomy(s)
    hits = normalise_capability(text, embedder, s) or [{"capability": None, "method": "none", "score": 0.0}]
    rows = []
    for hit in hits[:3]:
        ev = repo.add_evidence(
            s, source_url=None, source_type="user",
            evidence_text=f"Entered by the company user: \"{text}\"" + (
                f" (mapped to '{tx.CAPABILITIES[hit['capability']].name}' by {hit['method']} match)"
                if hit["capability"] else " (no taxonomy match; kept as free text and not used in matching)"),
            retrieved_at=None, verification_status="user_supplied")
        row = CompanyCapability(company_id=company.id,
                                capability_id=caps[hit["capability"]].id if hit["capability"] else None,
                                claim_text=text, claim_category=category, classification="USER", confidence=0.5,
                                evidence_id=ev.id, origin="user", active=True)
        s.add(row)
        rows.append(row)
    s.flush()
    return rows


def set_claim_active(s: Session, claim_id: int, active: bool) -> None:
    row = s.get(CompanyCapability, claim_id)
    if row is not None:
        row.active = active
        s.flush()


def missing_information(company, claims: list) -> list[str]:
    """What the public sources did NOT provide. Shown on the profile so gaps are explicit, not guessed."""
    cats = {c.claim_category for c in claims if c.active and c.classification == "FACT"}
    gaps = []
    if company.profile_depth != "website":
        gaps.append("The company's own website has not been read; the profile rests on the member directory entry only.")
    if "capability" not in cats:
        gaps.append("No technology or expertise could be confirmed from public text.")
    if "market" not in cats:
        gaps.append("Markets, industries and customer groups are not stated in the sources read.")
    if not any(c.claim_category == "geography" and not c.claim_text.startswith("Located in") for c in claims if c.active):
        gaps.append("Geographical focus beyond the office location is not stated.")
    if "development_activity" not in cats:
        gaps.append("No publicly stated development priorities or projects were found.")
    if "collaboration" not in cats:
        gaps.append("No publicly stated collaborations were found.")
    single = sum(1 for c in claims if c.active and c.claim_category == "capability" and c.classification == "FACT"
                 and c.evidence and c.evidence.verification_status != "corroborated")
    if single:
        gaps.append(f"{single} capability statement(s) rest on a single source and are uncertain until confirmed.")
    return gaps
