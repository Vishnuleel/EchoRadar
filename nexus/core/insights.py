"""Insights that make the problem visible in the stored data, and help staff act on it.

missed_calls()     "The opportunity you never saw": funding calls that fitted a member and have already closed
                   (deadline in the last 12 months), scored with the member's current public profile, with the
                   next round of the same programme when one is open now.
missed_overview()  The same across all members: how many closed calls fitted at least one member.
team_gaps()        "Complete the team": for proposals that miss a role, members elsewhere in the park with public
                   evidence of it; and the real gaps, capabilities no member shows at all.
role_candidates()  The same for one proposal (used by the Innovation Blueprint).

Everything is computed from stored records with the same matching as the radar. A fit is not an eligibility
decision, and a candidate partner has not been contacted.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.agents.opportunity_agent import current_status
from nexus.core import matching_engine as me
from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, FundingOpportunity, ResearchPublication
from nexus.utils.validators import utcnow

# Set after reading the 2026 calls by hand: below 45, matches such as aerospace research for a marine
# electronics company start to appear. A strict threshold keeps "you missed this" believable.
MISSED_MIN = 45.0
WINDOW_DAYS = 365
# Government agencies, the municipality, the region and the county board are members too, but are not typical
# applicants for these calls. They are counted and flagged rather than hidden.
PUBLIC_AUTHORITIES = {"forsvarsmakten", "kustbevakningen", "energimyndigheten", "forsakringskassan", "fmv",
                      "lansstyrelsen-blekinge", "karlskrona-kommun", "region-blekinge"}

_ROUND_WORDS = re.compile(r"\b(?:19|20)\d\d\b|\b(?:spring|autumn|fall|summer|winter|vår|höst|sommar|vinter)\b|"
                          r"\b(?:call|round|omgång|utlysning|ansökningsomgång)\s*\d+\b|\b\d+\b", re.I)


def programme_key(title: str) -> str:
    """A call's title without year, season or round number: two rounds of one programme share it."""
    t = _ROUND_WORDS.sub(" ", (title or "").lower())
    return " ".join(re.sub(r"[^\wåäö]+", " ", t).split())


def _closed_calls(s: Session, now: datetime) -> list[FundingOpportunity]:
    return [f for f in s.scalars(select(FundingOpportunity))
            if current_status(f, now) == "closed" and f.deadline and f.deadline >= now - timedelta(days=WINDOW_DAYS)]


def _next_rounds(s: Session, now: datetime) -> dict[str, FundingOpportunity]:
    out = {}
    for f in s.scalars(select(FundingOpportunity)):
        if current_status(f, now) in ("open", "upcoming"):
            out.setdefault(programme_key(f.title), f)
    return out


def _score(profile: me.CompanyProfile, items, semantic: bool) -> list[dict]:
    if profile.vector is None or not len(items):
        return []
    return me.bridge(profile.vector, set(profile.capabilities), items.vectors, items.caps, semantic)


def missed_calls(s: Session, profile: me.CompanyProfile, embedder, now: datetime | None = None) -> dict:
    from nexus import pipeline  # item embeddings are shared with the radar (late import: pipeline imports a lot)

    now = now or utcnow()
    rows = _closed_calls(s, now)
    items = pipeline._item_set(s, rows, embedder)
    nxt = _next_rounds(s, now)
    found = []
    for d in sorted(_score(profile, items, embedder.is_semantic), key=lambda d: -d["relevance"]):
        if d["relevance"] < MISSED_MIN:
            break
        f = items.rows[d["index"]]
        follow = nxt.get(programme_key(f.title))
        shared = [tx.CAPABILITIES[c].name for c in d["shared_capabilities"] if c in tx.CAPABILITIES]
        found.append({
            "ref_id": f.id, "title": f.title, "url": f.source_url, "relevance": d["relevance"],
            "opened": f.opens_at, "closed": f.deadline,
            "open_days": (f.deadline - f.opens_at).days if f.opens_at else None,
            "why": f"Matches the profile on {', '.join(shared[:3])}." if shared else
                   f"Close to the profile's wording (text similarity {d['cosine']:.2f}).",
            "next_round": {"title": follow.title, "url": follow.source_url, "status": current_status(follow, now),
                           "deadline": follow.deadline} if follow else None,
        })
    return {"company": {"id": profile.id, "name": profile.name}, "min_fit": MISSED_MIN, "window_days": WINDOW_DAYS,
            "closed_calls_checked": len(rows), "items": found}


def missed_overview(s: Session, profiles: list[me.CompanyProfile], embedder, now: datetime | None = None) -> dict:
    from nexus import pipeline

    now = now or utcnow()
    rows = _closed_calls(s, now)
    items = pipeline._item_set(s, rows, embedder)
    fitted: dict[int, list[str]] = defaultdict(list)  # call index -> member names
    slugs = {c.id: c.slug for c in repo.companies(s)}
    per_member = []
    for p in profiles:
        hits = [d for d in _score(p, items, embedder.is_semantic) if d["relevance"] >= MISSED_MIN]
        for d in hits:
            fitted[d["index"]].append(p.name)
        if hits:
            per_member.append({"company_id": p.id, "name": p.name, "calls": len(hits),
                               "public_authority": slugs.get(p.id) in PUBLIC_AUTHORITIES})
    calls = [{"title": items.rows[i].title, "url": items.rows[i].source_url, "closed": items.rows[i].deadline,
              "members": sorted(names)} for i, names in sorted(fitted.items(), key=lambda kv: -len(kv[1]))]
    return {"min_fit": MISSED_MIN, "window_days": WINDOW_DAYS, "closed_calls": len(rows),
            "fitted_at_least_one_member": len(fitted), "members_with_a_missed_call": len(per_member),
            "of_which_public_authorities": sum(m["public_authority"] for m in per_member),
            "members_checked": sum(1 for p in profiles if p.vector is not None),
            "per_member": sorted(per_member, key=lambda m: -m["calls"]), "calls": calls[:12]}


# ---- complete the team -------------------------------------------------------------------------
def _providers(s: Session) -> dict[str, dict[int, object]]:
    """capability id -> {company id: one evidence claim} from public capability facts."""
    out: dict[str, dict[int, object]] = defaultdict(dict)
    for c in repo.all_claims(s):
        if c.classification == "FACT" and c.claim_category == "capability" and c.capability and c.evidence \
                and c.origin == "public":
            out[c.capability.key].setdefault(c.company_id, c)
    return out


def _slot_caps(hyp: CollaborationHypothesis, slot: str) -> tuple[str, ...]:
    concept = tx.CONCEPTS_BY_ID.get(hyp.concept_id or "")
    if concept and slot in concept.slots:
        return concept.slots[slot]
    return tuple({c for con in tx.CONCEPTS for name, caps in con.slots.items() if name == slot for c in caps})


def role_candidates(s: Session, hyp: CollaborationHypothesis, providers=None, limit: int = 3) -> list[dict]:
    """For each role a proposal misses: members outside it with public evidence of a capability that fills it."""
    providers = providers if providers is not None else _providers(s)
    names = {c.id: c.name for c in repo.companies(s)}
    inside = set(hyp.participating_companies or [])
    out = []
    for slot in hyp.missing_capabilities or []:
        seen, cands = set(), []
        for cap in _slot_caps(hyp, slot):
            for cid, claim in providers.get(cap, {}).items():
                if cid in inside or cid in seen:
                    continue
                seen.add(cid)
                cands.append({"company_id": cid, "name": names.get(cid, "?"), "capability": tx.CAPABILITIES[cap].name,
                              "excerpt": claim.evidence.evidence_text[:200], "url": claim.evidence.source_url})
        out.append({"role": slot, "candidates": sorted(cands, key=lambda c: c["name"])[:limit], "count": len(cands)})
    return out


def team_gaps(s: Session, now: datetime | None = None) -> dict:
    now = now or utcnow()
    providers = _providers(s)
    names = {c.id: c.name for c in repo.companies(s)}
    hyps = list(s.scalars(repo.public_hypotheses(s).order_by(CollaborationHypothesis.score.desc())))
    roles: dict[str, dict] = {}
    for h in hyps:
        for slot in h.missing_capabilities or []:
            r = roles.setdefault(slot, {"role": slot, "proposals": 0, "examples": [], "providers": set()})
            r["proposals"] += 1
            if len(r["examples"]) < 2:
                r["examples"].append({"key": h.key, "title": h.title, "score": h.score})
            for cap in _slot_caps(h, slot):
                r["providers"].update(cid for cid in providers.get(cap, {}) if cid not in set(h.participating_companies))
    role_list = [{**r, "providers": sorted(names.get(i, "?") for i in r["providers"])}
                 for r in sorted(roles.values(), key=lambda r: -r["proposals"])]
    research = list(s.scalars(select(ResearchPublication)))
    live_calls = [f for f in s.scalars(select(FundingOpportunity)) if current_status(f, now) in ("open", "upcoming")]
    gaps = []
    for cap_id, cap in tx.CAPABILITIES.items():
        if providers.get(cap_id):
            continue
        needed_by = sum(1 for h in hyps for slot in h.missing_capabilities or [] if cap_id in _slot_caps(h, slot))
        gaps.append({"key": cap_id, "name": cap.name,
                     "research": sum(1 for r in research if cap_id in (r.capability_keys or [])),
                     "open_calls": sum(1 for f in live_calls if cap_id in (f.capability_keys or [])),
                     "proposals_needing_it": needed_by})
    return {"proposals": len(hyps), "proposals_missing_a_role": sum(1 for h in hyps if h.missing_capabilities),
            "roles": role_list, "roles_without_any_provider": [r["role"] for r in role_list if not r["providers"]],
            "real_gaps": gaps}
