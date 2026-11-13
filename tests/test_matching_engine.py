"""Tests 10-15: similarity, complementarity, triads, scoring, missing components, different rankings."""
import numpy as np
import pytest

from nexus.core import matching_engine as me
from nexus.core import scoring
from nexus.core import taxonomy as tx
from nexus.core.evaluation import ndcg_at_k, precision_at_k, rank_metrics, recall_at_k
from nexus.utils.validators import utcnow


def profile(pid, name, caps, interests=None, priorities=None, conf=0.9, cls="FACT", urls=("https://a.example/1", "https://a.example/2")):
    return me.CompanyProfile(id=pid, name=name, capabilities={
        c: me.CapabilityClaim(c, conf, cls, list(urls), [1], utcnow(), f"evidence for {c}") for c in caps},
        interests=interests or {}, priority_domains=priorities or [])


SENSOR = lambda: profile(1, "Sensor Co", ["underwater_sensors", "hydroacoustics"])
ROBOT = lambda: profile(2, "Robot Co", ["underwater_vehicles"])
AI = lambda: profile(3, "AI Co", ["ai_ml"])
CABLE = lambda: profile(4, "Cable Co", ["subsea_cable_ops"])
AI2 = lambda: profile(5, "AI Two", ["ai_ml", "software_development"])
BANK = lambda: profile(6, "Bank", [])


def test_semantic_similarity_calculation(embedder):
    vecs = embedder.encode(["underwater sonar sensor systems", "sonar sensors for underwater use", "retail banking and savings"])
    a, b, c = (me.CompanyProfile(i, str(i), vector=v) for i, v in enumerate(vecs))
    sim = me.similarity_matrix([a, b, c])
    assert sim.shape == (3, 3) and np.allclose(np.diag(sim), 1.0) and np.allclose(sim, sim.T, atol=1e-6)
    assert sim[0, 1] > sim[0, 2] and -1.0 <= sim.min() and sim.max() <= 1.0 + 1e-6
    assert me.similarity_matrix([a, me.CompanyProfile(9, "no vector")])[0, 1] == 0.0


def test_capability_normalisation(embedder):
    hits = me.normalise_capability("marine environmental sensing with underwater sensor systems", embedder)
    assert {"underwater_sensors"} <= {h["capability"] for h in hits} and all(h["method"] == "keyword" for h in hits)
    assert me.normalise_capability("ekolod och sonar")[0]["capability"] == "hydroacoustics"
    assert me.normalise_capability("zzzz qqqq", None) == []  # unknown text is never forced into a category


def test_complementarity_calculation():
    links = me.pair_links(SENSOR(), CABLE())
    assert links and links[0].kind == "explicit" and links[0].strength > 0.7 and "cable" in links[0].rationale
    strong = me.complementarity_score(links)
    assert 50 < strong <= 100
    # identical capabilities are similar, not complementary
    assert me.complementarity_score(me.pair_links(AI(), profile(7, "AI Clone", ["ai_ml"]))) == 0
    # different is not automatically complementary: no relation defined between these two
    assert tx.relation("water_treatment", "naval_architecture") is None
    assert me.pair_links(profile(8, "W", ["water_treatment"]), profile(9, "N", ["naval_architecture"])) == []
    # enablers are not scored as technology complements
    assert me.pair_links(profile(8, "F", ["funding_advisory"]), SENSOR()) == []
    # one relationship alone can reach at most 50
    assert me.complementarity_score(me.pair_links(ROBOT(), profile(8, "H", ["hydroacoustics"]))) <= 50
    # weaker evidence -> weaker link
    weak = me.pair_links(profile(1, "S", ["underwater_sensors"], conf=0.4), CABLE())[0].strength
    assert weak < me.pair_links(profile(1, "S", ["underwater_sensors"]), CABLE())[0].strength


def test_stated_interest_and_priority_change_the_score():
    base = me.complementarity_score(me.pair_links(CABLE(), AI()))
    with_interest = me.complementarity_score(me.pair_links(profile(4, "Cable Co", ["subsea_cable_ops"], interests={"ai_ml": 0.5}), AI()))
    assert with_interest > base
    assert any(l.kind == "stated_interest" for l in me.pair_links(profile(4, "Cable Co", ["subsea_cable_ops"], interests={"ai_ml": 0.5}), AI()))
    plain = me.pair_links(profile(1, "S", ["underwater_sensors"], conf=0.7), profile(4, "C", ["subsea_cable_ops"], conf=0.7))[0].strength
    boosted = me.pair_links(profile(1, "S", ["underwater_sensors"], conf=0.7, priorities=["offshore_energy"]),
                            profile(4, "C", ["subsea_cable_ops"], conf=0.7))[0].strength
    assert boosted > plain


def test_multi_company_combination_generation():
    profiles = [SENSOR(), ROBOT(), AI(), CABLE(), AI2(), BANK()]
    triads = me.discover_triads(profiles)
    assert triads and all(t.kind == "triad" and len(set(t.company_ids)) == 3 for t in triads)
    best = next(t for t in triads if t.concept_id == "cable_inspection")
    assert 6 not in best.company_ids  # a company without capabilities never appears
    assert len({v["company"] for v in best.slot_assignment.values()}) == 3  # everyone contributes a slot
    assert best.coverage >= 0.6 and len(best.links) >= 2
    concept = tx.CONCEPTS_BY_ID["cable_inspection"]
    assert set(best.missing_slots) == set(concept.slots) - set(best.slot_assignment)
    # bounded search: never more than per_concept results per concept
    assert max(sum(1 for t in triads if t.concept_id == c.id) for c in tx.CONCEPTS) <= 6
    # no triad when companies cannot each contribute
    assert me.discover_triads([AI(), AI2(), profile(7, "AI3", ["ai_ml"])]) == []


def test_ranking_score_calculation():
    b = scoring.combine(80, 60, 40, 100)
    assert b.final == pytest.approx(0.35 * 80 + 0.25 * 60 + 0.20 * 40 + 0.20 * 100) and b.coverage == 1.0 and not b.missing
    assert scoring.combine(150, -5, 50, 50).complementarity == 100 and scoring.combine(150, -5, 50, 50).opportunity == 0
    with pytest.raises(ValueError):
        scoring.combine(1, 1, 1, 1, {"complementarity": 0.5, "opportunity": 0.5, "research": 0.5, "evidence": 0.5})
    assert scoring.top_k_relevance([90]) == pytest.approx(54.0)  # one match earns only the first share


def test_missing_component_handling():
    b = scoring.combine(80, None, None, 90)
    assert b.missing == ["opportunity", "research"] and b.coverage == 0.5
    assert b.final == pytest.approx(0.35 * 80 + 0.20 * 90)  # missing parts add nothing; no renormalisation
    assert b.opportunity is None and b.research is None
    assert me.aggregate_relevance([]) is None and me.bridge(np.ones(4), set(), np.zeros((0, 4)), []) == []


def test_evidence_quality_reflects_sources():
    cand = me.score_pair(SENSOR(), CABLE())
    full = me.evidence_quality(cand, {1: SENSOR(), 4: CABLE()})
    assert full["score"] == 100 and full["coverage"] == 1.0
    single = profile(1, "Sensor Co", ["underwater_sensors", "hydroacoustics"], urls=("https://a.example/1",))
    user = profile(1, "Sensor Co", ["underwater_sensors", "hydroacoustics"], cls="USER", urls=())
    q_single = me.evidence_quality(me.score_pair(single, CABLE()), {1: single, 4: CABLE()})["score"]
    q_user = me.evidence_quality(me.score_pair(user, CABLE()), {1: user, 4: CABLE()})
    assert full["score"] > q_single > q_user["score"] and q_user["unsupported"]
    assert scoring.claim_quality("FACT", 2, False, utcnow()) == 0.0  # a fact without a source is worth nothing
    old = utcnow().replace(year=utcnow().year - 2)
    assert scoring.claim_quality("FACT", 2, True, old) < scoring.claim_quality("FACT", 2, True, utcnow())


def test_opportunity_bridge_prefers_related_items(embedder):
    vecs = embedder.encode(["underwater sensor systems for subsea cable monitoring", "autonomous underwater sensor monitoring call",
                            "food systems and agriculture call"])
    scored = me.bridge(vecs[0], {"underwater_sensors"}, vecs[1:], [{"underwater_sensors"}, set()], semantic=False)
    assert scored[0]["relevance"] > scored[1]["relevance"] and scored[0]["shared_capabilities"] == ["underwater_sensors"]
    assert all(0 <= s["relevance"] <= 100 for s in scored)


def test_different_company_ranking_results(seeded):
    from nexus.database import repository as repo

    lists = {}
    for slug in ("sensora", "cablelay", "mindworks"):
        c = repo.company_by_slug(seeded, slug)
        recs = repo.recommendations(seeded, c.id, 5)
        assert recs and [r.rank for r in recs] == sorted(r.rank for r in recs)
        assert all(c.id in r.hypothesis.participating_companies for r in recs)
        lists[slug] = [r.hypothesis.key for r in recs]
    assert lists["sensora"] != lists["cablelay"] != lists["mindworks"]
    assert repo.recommendations(seeded, repo.company_by_slug(seeded, "finbank").id) == []


def test_ranking_metrics_helpers():
    assert precision_at_k([2, 0, 1, 0], 2) == 0.5 and recall_at_k([2, 0, 1, 0], 2) == 0.5
    assert ndcg_at_k([2, 1, 0], 3) == pytest.approx(1.0) and ndcg_at_k([0, 1, 2], 3) < 1.0
    m = rank_metrics([0.9, 0.1, 0.8, 0.2], [2, 0, 1, 0])
    assert m["precision@5"] == 0.5 and m["spearman"] > 0.8
