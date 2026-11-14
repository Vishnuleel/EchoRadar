"""Missed calls ("the opportunity you never saw"), complete the team, and the timed task test.
Fixture data and the hashing embedder; nothing touches the network."""
from datetime import timedelta

from nexus.agents import combination_agent
from nexus.core import blueprint_generator as bgen
from nexus.core import insights
from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, FundingOpportunity
from nexus.utils.validators import utcnow
from tests.test_api import api  # noqa: F401  (fixture)


def test_rounds_of_one_programme_share_a_key():
    a = insights.programme_key("Accelerera FFI system demonstrators – spring 2026")
    assert a == insights.programme_key("Accelerera FFI system demonstrators – autumn 2026")
    assert insights.programme_key("Eurostars call 11") == insights.programme_key("Eurostars call 12")
    assert a != insights.programme_key("Cirkularitet FFI – spring 2026")


def _add_calls(s):
    now = utcnow()
    s.add_all([
        FundingOpportunity(external_id="2026-0101", title="Underwater sensor networks for marine monitoring 2026",
                           description="Develop underwater sensor systems for environmental monitoring of the sea.",
                           opens_at=now - timedelta(days=120), deadline=now - timedelta(days=40), status="closed",
                           capability_keys=["underwater_sensors"], source_url="https://data.vinnova.se/x/2026-0101", retrieved_at=now),
        FundingOpportunity(external_id="2027-0101", title="Underwater sensor networks for marine monitoring 2027",
                           description="Next round.", opens_at=now - timedelta(days=5), deadline=now + timedelta(days=60),
                           status="open", capability_keys=["underwater_sensors"], source_url="https://data.vinnova.se/x/2027-0101",
                           retrieved_at=now),
    ])
    s.commit()


def test_missed_calls_only_closed_within_a_year_and_names_the_next_round(seeded, embedder, monkeypatch):
    _add_calls(seeded)
    monkeypatch.setattr(insights, "MISSED_MIN", 0.0)  # the threshold is tuned for the real embedding model
    sensora = next(p for p in combination_agent.load_profiles(seeded, embedder) if p.name == "Sensora")
    r = insights.missed_calls(seeded, sensora, embedder)
    titles = [i["title"] for i in r["items"]]
    assert "Underwater sensor networks for marine monitoring 2026" in titles
    assert "Underwater sensor systems call 2020" not in titles  # closed more than a year ago
    assert all("2027" not in t for t in titles)  # an open call is not "missed"
    hit = next(i for i in r["items"] if i["title"].endswith("2026"))
    assert hit["next_round"]["title"].endswith("2027") and hit["next_round"]["status"] == "open"
    assert hit["open_days"] == 80 and [i["relevance"] for i in r["items"]] == sorted((i["relevance"] for i in r["items"]), reverse=True)


def test_missed_overview_counts_members_and_calls(seeded, embedder, monkeypatch):
    _add_calls(seeded)
    monkeypatch.setattr(insights, "MISSED_MIN", 0.0)
    o = insights.missed_overview(seeded, combination_agent.load_profiles(seeded, embedder), embedder)
    assert o["closed_calls"] == 1 and o["fitted_at_least_one_member"] == 1
    assert o["members_with_a_missed_call"] == len(o["per_member"]) >= 1 and o["of_which_public_authorities"] == 0


def test_complete_the_team_names_members_outside_the_proposal(seeded):
    sensora, robotix = repo.company_by_slug(seeded, "sensora"), repo.company_by_slug(seeded, "robotix")
    # a concept role that Sensora's evidenced capabilities can fill
    caps = {c.capability.key for c in repo.claims(seeded, sensora.id) if c.classification == "FACT" and c.capability}
    concept, slot = next((c, sl) for c in tx.CONCEPTS for sl, ids in c.slots.items() if caps & set(ids))
    hyp = CollaborationHypothesis(key="test:gap", kind="pair", title="t", participating_companies=[robotix.id],
                                  missing_capabilities=[slot], concept_id=concept.id, proposed_application="", evidence=[],
                                  score=50, score_breakdown={})
    roles = insights.role_candidates(seeded, hyp)
    assert roles[0]["role"] == slot and "Sensora" in [c["name"] for c in roles[0]["candidates"]]
    assert all(c["url"] and c["excerpt"] for c in roles[0]["candidates"])
    hyp.participating_companies = [robotix.id, sensora.id]  # a member inside the proposal is never proposed again
    assert "Sensora" not in [c["name"] for c in insights.role_candidates(seeded, hyp)[0]["candidates"]]


def test_team_gaps_and_blueprint_carry_the_candidates(seeded):
    t = insights.team_gaps(seeded)
    assert t["proposals"] >= t["proposals_missing_a_role"] >= 0
    assert all(set(g) >= {"key", "name", "research", "open_calls", "proposals_needing_it"} for g in t["real_gaps"])
    hyp = seeded.scalar(repo.public_hypotheses(seeded).limit(1))
    bp = bgen.build_blueprint(seeded, hyp)
    assert "complete_the_team" in bp and len(bp["complete_the_team"]) == len(hyp.missing_capabilities or [])
    assert "Missing capabilities" in bgen.to_markdown(bp) or not hyp.missing_capabilities


def test_task_test_is_stored_without_names_and_summarised(api):  # noqa: F811
    client, _, _ = api
    assert client.get("/api/study").json()["n"] == 0
    base = {"role": "bsp_staff", "order": "without_first", "without_seconds": 300, "without_result": "found",
            "without_fit": "partly", "with_seconds": 120, "with_result": "found", "with_fit": "yes", "prefer": "nexus"}
    client.post("/api/study", json=base)
    client.post("/api/study", json={**base, "role": "member", "order": "with_first", "without_seconds": 400,
                                    "with_seconds": 100})
    client.post("/api/study", json={**base, "practice": True})
    s = client.get("/api/study").json()
    assert s["n"] == 2 and s["practice_runs"] == 1 and s["paired_n"] == 2
    assert s["without"]["median_seconds"] == 350 and s["with"]["median_seconds"] == 110
    assert s["paired_median_saving_seconds"] == 240 and s["order"] == {"without_first": 1, "with_first": 1}
    assert s["next_order"] == "without_first"  # alternates with the number of counted sessions
    assert client.post("/api/study", json={**base, "role": "Anna Svensson"}).status_code == 422  # a role, never a name
    assert client.get("/api/evaluation").json()["study"]["n"] == 2
