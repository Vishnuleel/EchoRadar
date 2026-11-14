"""Ranking Agent: adds opportunity, research and evidence components to each candidate and
produces the final evidence-aware score."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from nexus.core import matching_engine as me
from nexus.core import scoring
from nexus.core import taxonomy as tx


@dataclass
class ItemSet:
    """Research, funding or testbed records prepared for bridging."""
    rows: list = field(default_factory=list)
    vectors: np.ndarray | None = None
    caps: list[set] = field(default_factory=list)

    def __len__(self):
        return len(self.rows)


@dataclass
class RankingContext:
    research: ItemSet
    funding: ItemSet  # ONLY calls that are open or upcoming right now
    testbeds: ItemSet
    cap_vectors: dict
    concept_vectors: dict
    semantic: bool = True
    now: datetime | None = None


def score_candidate(cand: me.Candidate, profiles: dict[int, me.CompanyProfile], ctx: RankingContext) -> dict:
    used = sorted({c for caps in cand.capabilities_used().values() for c in caps})
    vec = me.combination_vector(cand, ctx.cap_vectors, ctx.concept_vectors)

    def best(items: ItemSet, k: int, floor: float):
        if vec is None or not len(items):
            return None, []
        scored = me.bridge(vec, set(used), items.vectors, items.caps, ctx.semantic)
        scored.sort(key=lambda d: -d["relevance"])
        return me.aggregate_relevance(scored), [d for d in scored[:k] if d["relevance"] >= floor]

    o_score, o_top = best(ctx.funding, 4, 20.0)
    r_score, r_top = best(ctx.research, 5, 20.0)
    _, t_top = best(ctx.testbeds, 2, 15.0)
    ev = me.evidence_quality(cand, profiles, ctx.now)
    breakdown = scoring.combine(cand.complementarity, o_score, r_score, ev["score"])
    return {
        "candidate": cand, "breakdown": breakdown, "evidence": ev, "capabilities_used": used,
        "funding": [{"id": ctx.funding.rows[d["index"]].id, **d} for d in o_top],
        "research": [{"id": ctx.research.rows[d["index"]].id, **d} for d in r_top],
        "testbeds": [{"id": ctx.testbeds.rows[d["index"]].id, **d} for d in t_top],
    }


def explain(scored: dict, profiles: dict[int, me.CompanyProfile], perspective: int | None = None) -> str:
    """Deterministic explanation: why these companies, which capabilities, what is missing."""
    cand: me.Candidate = scored["candidate"]
    b = scored["breakdown"]
    names = [profiles[c].name for c in cand.company_ids]
    if perspective in cand.company_ids:
        others = [profiles[c].name for c in cand.company_ids if c != perspective]
        head = f"{profiles[perspective].name} with {' and '.join(others)}"
    else:
        head = " + ".join(names)
    parts = [f"{head}: capability complementarity {b.complementarity:.0f}/100."]
    for l in cand.links[:3]:
        a, bb = profiles[l.company_a].name, profiles[l.company_b].name
        if l.kind == "stated_interest":
            parts.append(f"{a} stated an interest in {tx.CAPABILITIES[l.cap_a].name}; {bb} has evidenced it.")
        else:
            parts.append(f"{a} ({tx.CAPABILITIES[l.cap_a].name}) and {bb} ({tx.CAPABILITIES[l.cap_b].name}): "
                         f"{l.rationale}.")
    if cand.missing_slots:
        parts.append("Not covered by these companies: " + ", ".join(cand.missing_slots) + ".")
    ev = scored["evidence"]
    parts.append(f"{ev['with_source']} of {ev['claims']} capability claims used have a public source.")
    if b.missing:
        parts.append("Not scored (no data): " + ", ".join(scoring.LABELS[m].lower() for m in b.missing) + ".")
    return " ".join(parts)


INTEREST_BOOST = 8.0


def personal_boost(scored: dict, profile: me.CompanyProfile | None) -> tuple[float, str | None]:
    """Extra points when a hypothesis brings in a capability the company said it is looking for.

    The boost only affects this company's own ordering; the hypothesis score itself is unchanged.
    """
    if profile is None or not profile.interests:
        return 0.0, None
    cand: me.Candidate = scored["candidate"]
    partner_caps = {c for cid, caps in cand.capabilities_used().items() if cid != profile.id for c in caps}
    partner_caps |= {l.cap_b for l in cand.links if l.kind == "stated_interest" and l.company_a == profile.id}
    hit = sorted(set(profile.interests) & partner_caps)
    if not hit:
        return 0.0, None
    names = ", ".join(tx.CAPABILITIES[c].name for c in hit[:2])
    return INTEREST_BOOST, f"Ranked higher for you (+{INTEREST_BOOST:.0f}) because it involves {names}, which you stated as an interest."


def rank_for_company(company_id: int, scored: list[dict], limit: int = 12, max_triads: int = 5,
                     max_per_partner: int = 3, max_per_concept: int = 1,
                     profile: me.CompanyProfile | None = None) -> list[dict]:
    """Personalised list: hypotheses that include the company, best first.

    Diversity rules keep the list useful: a partner appears at most `max_per_partner` times and a
    concept at most `max_per_concept` times, so one strong partner cannot fill the whole list.
    Returns shallow copies carrying `personal_score` and `personal_note`.
    """
    mine = []
    for s in scored:
        if company_id in s["candidate"].company_ids:
            boost, note = personal_boost(s, profile)
            mine.append({**s, "personal_score": min(100.0, round(s["breakdown"].final + boost, 1)), "personal_note": note})
    mine.sort(key=lambda s: -s["personal_score"])
    out, n_triads, partner_n, concept_n = [], 0, {}, {}
    for s in mine:
        cand = s["candidate"]
        partners = [c for c in cand.company_ids if c != company_id]
        if any(partner_n.get(p, 0) >= max_per_partner for p in partners):
            continue
        if cand.concept_id and concept_n.get(cand.concept_id, 0) >= max_per_concept:
            continue
        if cand.kind == "triad":
            if n_triads >= max_triads:
                continue
            n_triads += 1
        for p in partners:
            partner_n[p] = partner_n.get(p, 0) + 1
        if cand.concept_id:
            concept_n[cand.concept_id] = concept_n.get(cand.concept_id, 0) + 1
        out.append(s)
        if len(out) >= limit:
            break
    return out
