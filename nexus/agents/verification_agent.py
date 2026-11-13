"""Verification and Boundary Agent (output side).

Checks every scored hypothesis before it can be shown:
* structure   - validated with a Pydantic model
* evidence    - every capability used must trace to a claim; FACT claims need a source URL
* freshness   - sources older than the configured limit are flagged as stale
* funding     - closed calls must never be attached as current opportunities
* honesty     - missing score components and uncovered concept slots are surfaced

A hypothesis is REJECTED (not shown) when it relies on unsupported facts or has no relationship
left to explain. Otherwise it passes, possibly with warnings that are displayed with it.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ValidationError

from nexus.core import matching_engine as me
from nexus.integrations.vinnova import call_status
from nexus.utils.config import get_settings
from nexus.utils.validators import age_days, is_valid_url


class HypothesisRecord(BaseModel):
    key: str = Field(min_length=3)
    kind: str = Field(pattern="^(pair|triad)$")
    title: str = Field(min_length=5)
    company_ids: list[int] = Field(min_length=2, max_length=3)
    final_score: float = Field(ge=0, le=100)
    complementarity: float = Field(ge=0, le=100)
    coverage: float = Field(ge=0, le=1)
    validation_status: str = Field(pattern="^hypothesis$")  # generated output is always a hypothesis
    n_links: int = Field(ge=1)


def verify(scored: dict, profiles: dict[int, me.CompanyProfile], title: str, funding_rows: dict | None = None,
           now: datetime | None = None) -> dict:
    cand: me.Candidate = scored["candidate"]
    b = scored["breakdown"]
    issues, warnings = [], []
    stale_limit = get_settings().stale_after_days

    try:
        HypothesisRecord(key=cand.key, kind=cand.kind, title=title, company_ids=list(cand.company_ids),
                         final_score=b.final, complementarity=b.complementarity or 0.0, coverage=b.coverage,
                         validation_status="hypothesis", n_links=len(cand.links))
    except ValidationError as exc:
        issues.append("Structure validation failed: " + "; ".join(e["msg"] for e in exc.errors()[:3]))

    n_claims = n_sourced = n_stale = n_user = 0
    for cid, caps in cand.capabilities_used().items():
        for cap in caps:
            claim = profiles[cid].capabilities.get(cap)
            if claim is None:
                issues.append(f"Capability '{cap}' is used but company {profiles[cid].name} has no claim for it.")
                continue
            n_claims += 1
            urls = [u for u in claim.source_urls if is_valid_url(u)]
            if claim.classification == "FACT":
                if not urls:
                    issues.append(f"Unsupported fact: '{cap}' for {profiles[cid].name} has no source URL.")
                else:
                    n_sourced += 1
                    age = age_days(claim.retrieved_at, now)
                    if age is None or age > stale_limit:
                        n_stale += 1
            else:
                n_user += 1
    if n_stale:
        warnings.append(f"{n_stale} source(s) were retrieved more than {stale_limit} days ago (stale).")
    if n_user:
        warnings.append(f"{n_user} capability claim(s) are user-supplied and not independently verified.")
    if n_claims and n_sourced / n_claims < 0.5:
        issues.append("Fewer than half of the capability claims used have a public source.")
    if all(l.kind == "role" for l in cand.links):
        warnings.append("Only generic value-chain relationships were found; no specific capability relationship.")
    if cand.missing_slots:
        warnings.append("Capabilities not covered by the proposed companies: " + ", ".join(cand.missing_slots) + ".")
    if b.missing:
        warnings.append("Score components without data (counted as 0): " + ", ".join(b.missing) + ".")
    for f in scored.get("funding", []):
        row = (funding_rows or {}).get(f["id"])
        if row is not None and call_status(row.opens_at, row.deadline, now) == "closed":
            issues.append(f"Closed call attached as a current opportunity: {row.title[:60]}")
    if scored.get("funding"):
        warnings.append("Funding programmes are potentially relevant only; eligibility has not been checked.")

    status = "rejected" if issues else ("passed_with_warnings" if warnings else "passed")
    return {"status": status, "issues": issues, "warnings": warnings,
            "checks": {"claims_used": n_claims, "claims_with_source": n_sourced, "stale_sources": n_stale,
                       "user_supplied": n_user, "relationships": len(cand.links)}}
