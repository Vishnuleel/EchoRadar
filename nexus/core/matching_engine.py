"""NEXUS Innovation Matching Engine (deterministic, no LLM).

Pipeline
1. Capability normalisation   - free text -> taxonomy capabilities (keywords + embeddings)
2. Similarity matching        - cosine similarity of profile embeddings (the BASELINE)
3. Complementarity matching   - explicit/role relations between DIFFERENT capabilities,
                                gated by shared application domain and evidence confidence
4. Multi-company discovery    - bounded search for 3-company combinations that jointly cover
                                the capability slots of an application concept
5. Opportunity bridge         - hybrid semantic + taxonomy relevance to research and funding
6. Evidence-aware ranking     - see scoring.py

The module has no database or network dependency: it works on plain dataclasses so the same code
can sit behind a FastAPI service later.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from nexus.core import taxonomy as tx
from nexus.core.scoring import claim_quality, top_k_relevance

NON_COMPLEMENTARY_ROLES = {"ENABLER"}  # support actors: shown, but not scored as technology fit
MIN_LINK_STRENGTH = 0.25


@dataclass
class CapabilityClaim:
    capability: str
    confidence: float
    classification: str = "FACT"  # FACT | USER
    source_urls: list[str] = field(default_factory=list)
    evidence_ids: list[int] = field(default_factory=list)
    retrieved_at: datetime | None = None
    excerpt: str = ""


@dataclass
class CompanyProfile:
    id: int
    name: str
    text: str = ""
    capabilities: dict[str, CapabilityClaim] = field(default_factory=dict)
    interests: dict[str, float] = field(default_factory=dict)  # capability the company is LOOKING for
    priority_domains: list[str] = field(default_factory=list)
    vector: np.ndarray | None = None


@dataclass
class Link:
    """One explainable complementary relationship between two companies."""
    company_a: int
    cap_a: str
    company_b: int
    cap_b: str
    weight: float
    rationale: str
    kind: str  # explicit | role | stated_interest
    domains: list[str]
    strength: float

    def to_dict(self) -> dict:
        return {"company_a": self.company_a, "cap_a": self.cap_a, "company_b": self.company_b,
                "cap_b": self.cap_b, "weight": round(self.weight, 2), "rationale": self.rationale,
                "kind": self.kind, "domains": self.domains, "strength": round(self.strength, 3)}


@dataclass
class Candidate:
    """A pair or triad of companies with everything needed to explain and score it."""
    kind: str  # pair | triad
    company_ids: tuple[int, ...]
    complementarity: float
    links: list[Link]
    concept_id: str | None = None
    slot_assignment: dict[str, dict] = field(default_factory=dict)  # slot -> {company, capability}
    missing_slots: list[str] = field(default_factory=list)
    coverage: float = 0.0
    domain: str | None = None
    similarity: float | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}:{'-'.join(map(str, sorted(self.company_ids)))}:{self.concept_id or 'open'}"

    def capabilities_used(self) -> dict[int, set[str]]:
        used: dict[int, set[str]] = {cid: set() for cid in self.company_ids}
        for l in self.links:
            if l.kind != "stated_interest":
                used[l.company_a].add(l.cap_a)
            used[l.company_b].add(l.cap_b)
        for slot in self.slot_assignment.values():
            used[slot["company"]].add(slot["capability"])
        return used


# 1. Capability normalisation -------------------------------------------------------------------
def normalise_capability(text: str, embedder=None, session=None, min_cosine: float = 0.45) -> list[dict]:
    """Map a free-text capability/interest to taxonomy capabilities.

    Keyword hits come first (precise). If there are none, the nearest capability description in
    embedding space is used when it is similar enough; otherwise nothing is returned and the
    caller keeps the text as an un-normalised custom entry (it is never forced into a category).
    """
    hits = [{"capability": cid, "method": "keyword", "score": 1.0, "matched": term}
            for cid, term in tx.detect_capabilities(text)]
    if hits or embedder is None:
        return hits
    caps = list(tx.CAPABILITIES.values())
    vecs = embedder.encode([text] + [f"{c.name}. {c.description}" for c in caps], session)
    sims = vecs[1:] @ vecs[0]
    best = int(np.argmax(sims))
    threshold = min_cosine if embedder.is_semantic else 0.30
    if sims[best] >= threshold:
        return [{"capability": caps[best].id, "method": "embedding", "score": float(sims[best]), "matched": text}]
    return []


# 2. Similarity baseline ------------------------------------------------------------------------
def similarity_matrix(profiles: list[CompanyProfile]) -> np.ndarray:
    """Cosine similarity between profile vectors (0 where a vector is missing)."""
    n = len(profiles)
    dim = next((p.vector.shape[0] for p in profiles if p.vector is not None), 1)
    m = np.vstack([p.vector if p.vector is not None else np.zeros(dim, dtype=np.float32) for p in profiles])
    norms = np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)
    sim = (m / norms) @ (m / norms).T
    np.fill_diagonal(sim, 1.0)
    return sim if n else np.zeros((0, 0))


# 3. Complementarity ----------------------------------------------------------------------------
def pair_links(a: CompanyProfile, b: CompanyProfile) -> list[Link]:
    """All complementary relationships between two companies, strongest first."""
    links: list[Link] = []
    priorities = set(a.priority_domains) | set(b.priority_domains)
    for ca, claim_a in a.capabilities.items():
        if tx.CAPABILITIES[ca].role in NON_COMPLEMENTARY_ROLES:
            continue
        for cb, claim_b in b.capabilities.items():
            if ca == cb or tx.CAPABILITIES[cb].role in NON_COMPLEMENTARY_ROLES:
                continue  # the same capability on both sides is similarity, not complementarity
            rel = tx.relation(ca, cb)
            if rel is None:
                continue  # different is not automatically complementary
            weight, rationale, kind = rel
            domains = tx.shared_domains(ca, cb)
            domain_factor = 1.0 if domains else 0.4  # no shared application -> weak
            a_has_b, b_has_a = cb in a.capabilities, ca in b.capabilities
            overlap = 0.4 if (a_has_b and b_has_a) else 0.75 if (a_has_b or b_has_a) else 1.0
            boost = 1.2 if priorities & set(domains) else 1.0
            strength = min(1.0, weight * domain_factor * overlap * boost
                           * min(claim_a.confidence, claim_b.confidence))
            links.append(Link(a.id, ca, b.id, cb, weight, rationale, kind, domains, strength))
    # stated interests: A says it is looking for X, B has evidenced X (and vice versa)
    for seeker, holder in ((a, b), (b, a)):
        for cap, conf in seeker.interests.items():
            if cap in holder.capabilities and cap not in seeker.capabilities:
                strength = min(1.0, 0.85 * min(1.0, conf + 0.4) * holder.capabilities[cap].confidence)
                links.append(Link(seeker.id, cap, holder.id, cap, 0.85,
                                  f"{seeker.name} has stated an interest in this area and "
                                  f"{holder.name} has evidenced capability in it",
                                  "stated_interest", list(tx.CAPABILITIES[cap].domains[:2]), strength))
    links.sort(key=lambda l: -l.strength)
    return links


def _diverse_top(links: list[Link], k: int = 3) -> list[Link]:
    """Pick the strongest links while using each capability at most twice (avoids one-trick scores)."""
    chosen, use = [], {}
    for l in links:
        ka, kb = (l.company_a, l.cap_a), (l.company_b, l.cap_b)
        if use.get(ka, 0) >= 2 or use.get(kb, 0) >= 2:
            continue
        chosen.append(l)
        use[ka] = use.get(ka, 0) + 1
        use[kb] = use.get(kb, 0) + 1
        if len(chosen) == k:
            break
    return chosen


def complementarity_score(links: list[Link]) -> float:
    """0..100. Weighted sum of the three strongest diverse links (0.5 / 0.3 / 0.2).

    A single relationship can therefore reach at most 50: strong complementarity needs several
    independent relationships.
    """
    top = _diverse_top([l for l in links if l.strength >= MIN_LINK_STRENGTH])
    return round(100.0 * sum(w * l.strength for w, l in zip((0.5, 0.3, 0.2), top)), 1)


def best_concept_for(profiles: list[CompanyProfile]) -> tuple[tx.Concept | None, dict, list[str]]:
    """Concept whose slots the given companies cover best, with every company contributing."""
    best, best_assign, best_missing, best_cov = None, {}, [], 0.0
    for concept in tx.CONCEPTS:
        assign, missing = assign_slots(concept, profiles)
        contributors = {v["company"] for v in assign.values()}
        cov = len(assign) / len(concept.slots)
        if len(contributors) == len(profiles) and len(assign) >= 2 and cov >= 0.5 and cov > best_cov:
            best, best_assign, best_missing, best_cov = concept, assign, missing, cov
    return best, best_assign, best_missing


def score_pair(a: CompanyProfile, b: CompanyProfile, similarity: float | None = None) -> Candidate:
    links = pair_links(a, b)
    concept, assign, missing = best_concept_for([a, b])
    domains = [d for l in links[:3] for d in l.domains]
    domain = concept.domain if concept else (max(set(domains), key=domains.count) if domains else None)
    return Candidate("pair", (a.id, b.id), complementarity_score(links), links[:8],
                     concept.id if concept else None, assign, missing,
                     round(len(assign) / len(concept.slots), 2) if concept else 0.0, domain, similarity)


# 4. Multi-company discovery ---------------------------------------------------------------------
def company_slots(concept: tx.Concept, p: CompanyProfile) -> dict[str, tuple[str, float]]:
    """Slots of a concept this company can fill -> (best capability, confidence)."""
    out = {}
    for slot, alts in concept.slots.items():
        held = [(p.capabilities[c].confidence, c) for c in alts if c in p.capabilities]
        if held:
            conf, cap = max(held)
            out[slot] = (cap, conf)
    return out


def assign_slots(concept: tx.Concept, profiles: list[CompanyProfile]) -> tuple[dict, list[str]]:
    """Give each slot to one company. First guarantee every company a slot, then fill by confidence."""
    options = {p.id: company_slots(concept, p) for p in profiles}
    assign: dict[str, dict] = {}
    # companies with the fewest options choose first, so everyone contributes where possible
    for p in sorted(profiles, key=lambda q: len(options[q.id])):
        free = [(conf, slot, cap) for slot, (cap, conf) in options[p.id].items() if slot not in assign]
        if free:
            conf, slot, cap = max(free)
            assign[slot] = {"company": p.id, "capability": cap, "confidence": conf}
    for slot in concept.slots:
        if slot in assign:
            continue
        holders = [(options[p.id][slot][1], p.id, options[p.id][slot][0]) for p in profiles if slot in options[p.id]]
        if holders:
            conf, pid, cap = max(holders)
            assign[slot] = {"company": pid, "capability": cap, "confidence": conf}
    ordered = {s: assign[s] for s in concept.slots if s in assign}
    return ordered, [s for s in concept.slots if s not in assign]


def discover_triads(profiles: list[CompanyProfile], top_m: int = 8, per_concept: int = 6,
                    min_coverage: float = 0.6, pair_cache: dict | None = None) -> list[Candidate]:
    """Bounded search for three-company combinations.

    For each concept only the `top_m` companies that fill the most slots are considered, so the
    work is at most len(CONCEPTS) * C(top_m, 3) triples regardless of the number of members
    (11 concepts * 56 = 616 triples for top_m = 8).

    A triad is kept only if
      * every company fills at least one slot of its own,
      * at least `min_coverage` of the slots (and at least three) are covered, and
      * at least two of the three company pairs have a complementary relationship.
    """
    pair_cache = pair_cache if pair_cache is not None else {}
    by_id = {p.id: p for p in profiles}

    def links_for(x: int, y: int) -> list[Link]:
        k = (min(x, y), max(x, y))
        if k not in pair_cache:
            pair_cache[k] = pair_links(by_id[k[0]], by_id[k[1]])
        return pair_cache[k]

    results: list[Candidate] = []
    for concept in tx.CONCEPTS:
        ranked = []
        for p in profiles:
            slots = company_slots(concept, p)
            if slots:
                ranked.append((len(slots), sum(c for _, c in slots.values()) / len(slots), p))
        ranked.sort(key=lambda t: (-t[0], -t[1], t[2].name))
        pool = [p for _, _, p in ranked[:top_m]]
        found = []
        for trio in itertools.combinations(pool, 3):
            assign, missing = assign_slots(concept, list(trio))
            contributors = {v["company"] for v in assign.values()}
            coverage = len(assign) / len(concept.slots)
            if len(contributors) < 3 or len(assign) < 3 or coverage < min_coverage:
                continue
            pair_best, all_links = [], []
            for x, y in itertools.combinations(trio, 2):
                ls = [l for l in links_for(x.id, y.id) if l.strength >= MIN_LINK_STRENGTH]
                if ls:
                    pair_best.append(ls[0].strength)
                    all_links.extend(ls[:2])
            if len(pair_best) < 2:
                continue  # needs at least two complementary relationships
            slot_sets = [set(company_slots(concept, p)) for p in trio]
            redundancy = float(np.mean([len(s & t) / max(1, len(s | t))
                                        for s, t in itertools.combinations(slot_sets, 2)]))
            mean_conf = float(np.mean([v["confidence"] for v in assign.values()]))
            score = 100.0 * (0.45 * coverage * mean_conf + 0.35 * (sum(pair_best) / 3.0)
                             + 0.20 * (1.0 - redundancy))
            # links between the capabilities that fill the concept's slots explain THIS concept: show them first
            slot_caps = {(v["company"], v["capability"]) for v in assign.values()}
            all_links.sort(key=lambda l: (not ((l.company_a, l.cap_a) in slot_caps and (l.company_b, l.cap_b) in slot_caps),
                                          -l.strength))
            found.append(Candidate("triad", tuple(p.id for p in trio), round(score, 1), all_links[:8],
                                   concept.id, assign, missing, round(coverage, 2), concept.domain))
        found.sort(key=lambda c: -c.complementarity)
        results.extend(found[:per_concept])
    results.sort(key=lambda c: -c.complementarity)
    return results


# 5. Opportunity bridge --------------------------------------------------------------------------
def calibrate(cos: float, semantic: bool = True) -> float:
    """Map cosine similarity to 0..1 relevance. Bounds were set from the observed score ranges
    of each backend on the stored corpus (see docs/innovation_methodology.md)."""
    lo, hi = (0.20, 0.70) if semantic else (0.05, 0.45)
    return float(min(1.0, max(0.0, (cos - lo) / (hi - lo))))


def bridge(query_vec: np.ndarray, query_caps: set[str], item_vecs: np.ndarray, item_caps: list[set[str]],
           semantic: bool = True) -> list[dict]:
    """Hybrid relevance of items (research or funding) to a company or combination.

    relevance = 100 * (0.7 * calibrated cosine + 0.3 * capability-tag overlap)
    """
    if len(item_vecs) == 0:
        return []
    q = query_vec / max(1e-9, float(np.linalg.norm(query_vec)))
    cos = item_vecs @ q
    out = []
    for i, c in enumerate(cos):
        shared = sorted(query_caps & item_caps[i])
        tag = min(1.0, len(shared) / max(1, min(3, len(query_caps))))
        out.append({"index": i, "relevance": round(100.0 * (0.7 * calibrate(float(c), semantic) + 0.3 * tag), 1),
                    "cosine": round(float(c), 3), "shared_capabilities": shared})
    return out


def aggregate_relevance(scored: list[dict]) -> float | None:
    """Component score from the best three matches; None when there is nothing to match against."""
    if not scored:
        return None
    return round(top_k_relevance([s["relevance"] for s in scored]), 1)


# 6. Evidence quality ----------------------------------------------------------------------------
def evidence_quality(candidate: Candidate, profiles: dict[int, CompanyProfile], now: datetime | None = None) -> dict:
    """E component (0..100) plus the coverage figures shown in the UI."""
    qualities, with_source, total, unsupported = [], 0, 0, []
    for cid, caps in candidate.capabilities_used().items():
        for cap in caps:
            claim = profiles[cid].capabilities.get(cap)
            if claim is None:
                continue
            total += 1
            has_url = bool(claim.source_urls)
            with_source += has_url
            if not has_url:
                unsupported.append({"company": cid, "capability": cap, "classification": claim.classification})
            qualities.append(claim_quality(claim.classification, len(set(claim.source_urls)), has_url,
                                           claim.retrieved_at, now))
    if not total:
        return {"score": None, "claims": 0, "with_source": 0, "coverage": 0.0, "unsupported": []}
    return {"score": round(100.0 * float(np.mean(qualities)), 1), "claims": total, "with_source": with_source,
            "coverage": round(with_source / total, 2), "unsupported": unsupported}


def combination_vector(candidate: Candidate, cap_vectors: dict[str, np.ndarray],
                       concept_vectors: dict[str, np.ndarray]) -> np.ndarray | None:
    """Represent a combination by the capabilities it actually uses (plus its concept, if any)."""
    caps = sorted({c for s in candidate.capabilities_used().values() for c in s})
    vecs = [cap_vectors[c] for c in caps if c in cap_vectors]
    if candidate.concept_id and candidate.concept_id in concept_vectors:
        vecs += [concept_vectors[candidate.concept_id]] * max(1, len(vecs) // 2)
    if not vecs:
        return None
    v = np.mean(vecs, axis=0)
    return v / max(1e-9, float(np.linalg.norm(v)))
