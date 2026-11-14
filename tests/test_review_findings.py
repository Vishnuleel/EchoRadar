"""Regressions from the manual review of findings and connections (2026-11-14)."""
from sqlalchemy import select

from nexus.core import blueprint_generator as bg
from nexus.core import matching_engine as me
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, Company


def test_a_concept_appears_once_in_each_companys_list(seeded):
    for c in seeded.scalars(select(Company)):
        concepts = [r.hypothesis.concept_id for r in repo.recommendations(seeded, c.id, 12) if r.hypothesis.concept_id]
        assert len(concepts) == len(set(concepts)), c.name


def test_every_contribution_carries_its_own_evidence_and_research_says_whom_it_supports(seeded):
    hyps = list(seeded.scalars(select(CollaborationHypothesis)))
    triads = [h for h in hyps if h.required_capabilities]
    assert triads
    for h in triads:
        for slot in h.required_capabilities:
            ev = slot["evidence"]
            assert ev and ev["excerpt"] and (ev["urls"] or ev["classification"] == "USER"), (h.title, slot["slot"])
        bp = bg.build_blueprint(seeded, h)
        for area in bp["capability_areas"]:
            assert area["excerpt"] and area["basis"] in ("SOURCED", "USER")
        for r in bp["research"]:
            assert set(r["supports"]) | set(r["not_covered"]) == {c["name"] for c in bp["companies"]}
        assert "Relates to the contribution of" in bg.to_markdown(bp) or not bp["research"]


def test_triad_links_between_slot_capabilities_come_first():
    def profile(i, name, caps):
        return me.CompanyProfile(id=i, name=name, capabilities={c: me.CapabilityClaim(c, 0.9, "FACT") for c in caps})

    profiles = [profile(1, "S", ["underwater_sensors", "iot_telematics"]), profile(2, "R", ["underwater_vehicles"]),
                profile(3, "C", ["subsea_cable_ops"]), profile(4, "A", ["ai_ml"])]
    for t in me.discover_triads(profiles):
        slot_caps = {(v["company"], v["capability"]) for v in t.slot_assignment.values()}
        in_concept = [(l.company_a, l.cap_a) in slot_caps and (l.company_b, l.cap_b) in slot_caps for l in t.links]
        assert in_concept == sorted(in_concept, reverse=True), t.concept_id  # all concept links before any other
