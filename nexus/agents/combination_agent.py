"""Innovation Combination Agent: builds matching profiles from stored, evidence-backed claims and
runs the deterministic matching engine to produce pair and triad candidates."""
from __future__ import annotations

import itertools

from sqlalchemy.orm import Session

from nexus.core import matching_engine as me
from nexus.core import taxonomy as tx
from nexus.database import repository as repo


def has_private_inputs(company, user_claims: bool, marked: bool) -> bool:
    """True when the company's own view would differ from the public one."""
    unshared = not company.share_refinements and (bool(company.user_description) or user_claims)
    return unshared or bool(company.need_priorities) or bool(company.priority_domains) or marked


def load_profiles(s: Session, embedder=None, private_for=()) -> list[me.CompanyProfile]:
    """One CompanyProfile per company, using only ACTIVE claims.

    Public profiles (the default) contain public evidence plus refinements the company chose to share.
    For company ids in `private_for` (or every company when it is True) the company's own private
    refinements and priority areas are included as well; such a profile may only feed that company's
    own, owner-only results.
    """
    profiles = []
    by_company: dict[int, list] = {}
    for claim in repo.all_claims(s):
        by_company.setdefault(claim.company_id, []).append(claim)
    for company in repo.companies(s):
        private = private_for is True or company.id in (private_for or ())
        shared = private or bool(company.share_refinements)
        p = me.CompanyProfile(id=company.id, name=company.name,
                              priority_domains=list(company.priority_domains or []) if private else [])
        excerpts, free_text = [], []
        for cl in by_company.get(company.id, []):
            if cl.classification == "USER" and not shared:
                continue  # an unshared refinement never reaches another company's results
            key = cl.capability.key if cl.capability else None
            if cl.claim_category == "capability" and key in tx.CAPABILITIES:
                cc = p.capabilities.get(key)
                if cc is None:
                    cc = p.capabilities[key] = me.CapabilityClaim(key, 0.0, "USER")
                cc.confidence = max(cc.confidence, cl.confidence)
                if cl.classification == "FACT":
                    cc.classification = "FACT"
                if cl.evidence:
                    cc.evidence_ids.append(cl.evidence.id)
                    if cl.evidence.source_url:
                        cc.source_urls.append(cl.evidence.source_url)
                        if cc.retrieved_at is None or (cl.evidence.retrieved_at and cl.evidence.retrieved_at > cc.retrieved_at):
                            cc.retrieved_at = cl.evidence.retrieved_at
                    if not cc.excerpt:
                        cc.excerpt = cl.evidence.evidence_text
                    if cl.classification == "FACT" and len(excerpts) < 6:
                        excerpts.append(cl.evidence.evidence_text)
            elif cl.claim_category == "interest" and cl.classification == "USER":
                if key in tx.CAPABILITIES:
                    p.interests[key] = max(p.interests.get(key, 0.0), cl.confidence)
                free_text.append(cl.claim_text)
            elif cl.claim_category == "capability" and cl.classification == "USER":
                free_text.append(cl.claim_text)
        names = ", ".join(tx.CAPABILITIES[k].name for k in p.capabilities)
        description = (company.user_description if shared else None) or company.description or ""
        p.text = " ".join(x for x in [description, names,
                                      " ".join(excerpts), " ".join(free_text)] if x).strip() or company.name
        profiles.append(p)
    if embedder is not None and profiles:
        vecs = embedder.encode([p.text for p in profiles], s)
        for p, v in zip(profiles, vecs):
            p.vector = v
    return profiles


def generate_candidates(profiles: list[me.CompanyProfile], min_pair_score: float = 12.0, top_m: int = 8):
    """Return (pairs, triads, similarity matrix). Pairs below `min_pair_score` are dropped."""
    sim = me.similarity_matrix(profiles) if profiles and profiles[0].vector is not None else None
    index = {p.id: i for i, p in enumerate(profiles)}
    pair_cache: dict = {}
    pairs = []
    for a, b in itertools.combinations(profiles, 2):
        if not a.capabilities or not b.capabilities:
            continue
        s_ab = float(sim[index[a.id], index[b.id]]) if sim is not None else None
        cand = me.score_pair(a, b, s_ab)
        pair_cache[(min(a.id, b.id), max(a.id, b.id))] = me.pair_links(
            *(sorted((a, b), key=lambda p: p.id)))
        if cand.complementarity >= min_pair_score:
            pairs.append(cand)
    triads = me.discover_triads(profiles, top_m=top_m, pair_cache=pair_cache)
    pairs.sort(key=lambda c: -c.complementarity)
    return pairs, triads, sim
