"""Tests 17, 23, 24: blueprint generation, export, and the full discovery journey incl. UI smoke tests."""
import os
from datetime import timedelta

import pytest

from nexus import pipeline
from nexus.agents import company_agent, monitoring_agent
from nexus.core import blueprint_generator as bg
from nexus.core import evaluation, radar
from nexus.core import graph_engine as ge
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, Event, NewsUpdate, Opportunity
from nexus.integrations import bsp_sources
from nexus.utils.validators import utcnow
from tests.conftest import FakeClient


def top_hypothesis(s, slug):
    return repo.recommendations(s, repo.company_by_slug(s, slug).id, 1)[0].hypothesis


def test_innovation_blueprint_generation(seeded):
    hyp = top_hypothesis(seeded, "sensora")
    bp = bg.build_blueprint(seeded, hyp)
    for key in ("title", "problem", "capability_areas", "companies", "complementarity", "research", "funding", "testbeds",
                "first_experiment", "technical_requirements", "risks", "sources", "next_steps"):
        assert bp[key], f"blueprint section '{key}' is empty"
    assert bp["validation_status"] == "hypothesis" and "NOT A CONFIRMED COLLABORATION" in bp["disclaimer"]
    assert bp["problem"]["basis"] == "HYPOTHESIS" and all(c["basis"] == "SOURCED" for c in bp["companies"])
    assert all(e["urls"] for c in bp["complementarity"] for e in c["evidence"] if e["basis"] == "SOURCED")
    assert all(f["status"] in ("open", "upcoming") and "NOT checked" in f["note"] for f in bp["funding"])
    assert all(s_["url"].startswith("http") for s_ in bp["sources"])
    assert any("generated hypothesis" in r["text"] for r in bp["risks"])


def test_export_functionality(seeded):
    bp = bg.build_blueprint(seeded, top_hypothesis(seeded, "cablelay"))
    md = bg.to_markdown(bp)
    for n in range(1, 14):
        assert f"### {n}. " in md
    assert "HYPOTHESIS - NOT A CONFIRMED COLLABORATION" in md and "https://" in md and bp["title"] in md
    pdf = bg.to_pdf(bp)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 3000


def test_unsupported_combinations_are_not_invented(seeded, embedder):
    ids = [repo.company_by_slug(seeded, s).id for s in ("finbank", "sensora")]
    hyp, msg = pipeline.adhoc_hypothesis(seeded, ids, embedder)
    assert hyp is None and "No evidence-backed capabilities" in msg
    hyp, msg = pipeline.adhoc_hypothesis(seeded, [repo.company_by_slug(seeded, s).id for s in ("mindworks", "codehaus")], embedder)
    assert hyp is None or hyp.score_breakdown["complementarity"] < 40
    hyp, _ = pipeline.adhoc_hypothesis(seeded, [repo.company_by_slug(seeded, s).id for s in ("sensora", "robotix", "cablelay")], embedder)
    assert hyp is not None and hyp.kind == "triad" and hyp.verification["status"] != "rejected"


def test_verification_rejects_unsupported_facts(seeded, embedder):
    from nexus.agents import combination_agent, ranking_agent, verification_agent
    from nexus.core import matching_engine as me

    profiles = {p.id: p for p in combination_agent.load_profiles(seeded, embedder)}
    a, b = (repo.company_by_slug(seeded, s).id for s in ("sensora", "cablelay"))
    for claim in profiles[a].capabilities.values():
        claim.source_urls = []  # simulate facts that lost their sources
    ctx = pipeline.build_context(seeded, embedder)
    sc = ranking_agent.score_candidate(me.score_pair(profiles[a], profiles[b]), profiles, ctx)
    ver = verification_agent.verify(sc, profiles, "Some title")
    assert ver["status"] == "rejected" and any("Unsupported fact" in i for i in ver["issues"])


def test_end_to_end_company_discovery_workflow(seeded, embedder):
    """Steps 2-15 of the user journey on fixture data."""
    s = seeded
    company = repo.company_by_slug(s, "cablelay")
    facts = [c for c in repo.claims(s, company.id) if c.classification == "FACT"]
    assert facts and all(c.evidence.source_url and c.evidence.retrieved_at for c in facts)  # 2-4 review profile
    before = [(r.hypothesis.key, r.score) for r in repo.recommendations(s, company.id, 10)]
    radar_before = [(i["kind"], i["ref_id"], i["relevance"]) for i in radar.company_items(s, company.id)]

    # 5-6: the user adds an interest and a current need
    company_agent.add_user_claim(s, company, "machine learning for cable fault prediction", "interest", embedder)
    company.need_priorities = ["funding"]
    repo.add_revision(s, company, "added interest in machine learning; funding is a priority", author="CableLay")
    s.commit()
    trace = pipeline.recompute(s, embedder)  # 7-11
    assert [t["agent"] for t in trace][:3] == ["Innovation Combination Agent", "Ranking Agent", "Verification Agent"]

    after = [(r.hypothesis.key, r.score) for r in repo.recommendations(s, company.id, 10)]
    assert after != before, "recommendations must respond to the profile edit"
    ai_ids = {repo.company_by_slug(s, x).id for x in ("mindworks", "codehaus")}
    recs = repo.recommendations(s, company.id, 10)
    assert any(ai_ids & set(r.hypothesis.participating_companies) and
               any(l["kind"] == "stated_interest" for l in r.hypothesis.evidence) for r in recs)
    radar_after = radar.company_items(s, company.id)
    before_by_ref = {(k, ref): rel for k, ref, rel in radar_before}
    funding_after = [i for i in radar_after if i["kind"] == "funding"]
    assert funding_after
    for i in funding_after:  # the stated need re-ranks the radar, and the reason is shown
        assert i["relevance"] == min(100.0, round(i["base_relevance"] + radar.PRIORITY_BOOST, 1))
        assert any("priority" in a for a in i["adjustments"])
        if ("funding", i["ref_id"]) in before_by_ref:
            assert i["relevance"] > before_by_ref[("funding", i["ref_id"])]
    assert all(not i["adjustments"] for i in radar_after if i["kind"] == "research")
    assert radar_after[0]["kind"] == "funding" and radar_after[0]["priority_area"]  # priority area is listed first
    assert [i["kind"] for i in radar_after] != [k for k, _, _ in radar_before]
    boosted = [r for r in recs if r.score_breakdown.get("personal_note")]
    assert boosted and "stated as an interest" in boosted[0].explanation and boosted[0].score > boosted[0].hypothesis.score

    for r in recs:  # 12: every shown hypothesis is verified and explained
        h = r.hypothesis
        assert h.validation_status == "hypothesis" and h.verification["status"] in ("passed", "passed_with_warnings")
        assert r.explanation and h.score_breakdown["coverage"] <= 1 and set(h.score_breakdown["weights"]) == {
            "complementarity", "opportunity", "research", "evidence"}
        assert r.score >= h.score
        assert abs(h.score - sum(h.score_breakdown["weights"][k] * (h.score_breakdown[k] or 0)
                                 for k in h.score_breakdown["weights"])) < 0.11
    bp = bg.build_blueprint(s, recs[0].hypothesis)  # 13-15
    assert bp["next_steps"] and bp["sources"] and bg.to_markdown(bp)

    # feedback loop: an item marked not useful disappears, saved items stay private
    first = radar_after[0]
    radar.mark(s, company.id, first["kind"], first["ref_id"], "not_useful")
    s.commit()
    pipeline.recompute(s, embedder)
    assert (first["kind"], first["ref_id"]) not in {(i["kind"], i["ref_id"]) for i in radar.company_items(s, company.id)}
    cov = evaluation.evidence_coverage(s)
    assert cov["profile_coverage"] == 1.0 and cov["user_claims"] >= 1


def test_events_and_news_monitoring(seeded, embedder):
    html_events = """<html><body><h2>Höstens tillfällen</h2><h3>Framtidens sonar och AI</h3><p>Onsdagen den 9 december
    Tid: 11:45-12:50 (talare 12:15) Plats: Villa Oscar, Karlskrona Föreläsningen hålls på svenska. Om sonar.</p>
    <h3>Mallrubrik</h3><p>Onsdagen den 7 oktober Tid: 12:00-12:50 Lorem ipsum dolor sit amet.</p></body></html>"""
    events = bsp_sources.parse_event_programme(html_events, "https://www.bluesciencepark.se/x/", utcnow())
    assert len(events) == 1  # the Lorem ipsum template block is not an event
    e = events[0]
    assert e["title"] == "Onsdagslunch: Framtidens sonar och AI" and e["format"] == "in_person" and e["location"].startswith("Villa Oscar")
    assert (e["starts_at"].month, e["starts_at"].day, e["starts_at"].hour) == (12, 9, 11) and "no year" in e["date_note"]
    news_html = """<html><body><a href="https://www.bluesciencepark.se/aktuellt/sensora-nytt/">2 nov 2026 Sensora startar projekt om undervattenssensorer</a>
    <a href="https://www.bluesciencepark.se/aktuellt/annat/">Kort</a></body></html>"""
    items = bsp_sources.parse_news_listing(news_html, r"bluesciencepark\.se/aktuellt/[^/]+/?$")
    assert len(items) == 1 and items[0]["title"].startswith("Sensora startar") and items[0]["published_at"].day == 2

    client = FakeClient({bsp_sources.EVENT_PROGRAMME_URL: html_events, bsp_sources.BSP_NEWS_URL: news_html,
                         "https://www.bluesciencepark.se/aktuellt/sensora-nytt/": "<html><body><p>Sensora har startat ett nytt projekt om undervattenssensorer i Östersjön tillsammans med forskare.</p></body></html>"})
    monitoring_agent.collect_events(seeded, client)
    out = monitoring_agent.collect_news(seeded, client)
    seeded.add(Event(key="future", title="Workshop on underwater sensor systems", description="Sensors and sonar.",
                     starts_at=utcnow() + timedelta(days=20), date_text="in 20 days", format="online", organiser="Test",
                     source_url="https://example.org/e", capability_keys=["underwater_sensors"]))
    seeded.commit()
    assert seeded.query(Event).count() == 2 and seeded.query(NewsUpdate).count() == 1 and out["member_mentions"] == 1
    monitoring_agent.collect_events(seeded, client)  # second run updates, never duplicates
    assert seeded.query(Event).count() == 2
    pipeline.recompute(seeded, embedder)
    sensora = repo.company_by_slug(seeded, "sensora")
    items = radar.company_items(seeded, sensora.id)
    news = [i for i in items if i["kind"] == "news"]
    assert news and news[0]["relevance"] >= 90 and "names your company" in news[0]["adjustments"]
    ev = [i for i in items if i["kind"] == "event"]
    assert ev and all(i["status"] != "past" for i in ev) and any("online" in i["date_label"] for i in ev)
    digest = radar.weekly_digest(seeded, sensora.id)
    assert digest["funding"] and digest["events"] and digest["knowledge"] and digest["total"] == len(items)


def test_knowledge_graph_construction(seeded, embedder):
    from nexus.agents import combination_agent
    from nexus.core import matching_engine as me

    profiles = combination_agent.load_profiles(seeded, embedder)
    focus = repo.company_by_slug(seeded, "sensora").id
    g = ge.build_graph(seeded, profiles, me.similarity_matrix(profiles), focus)
    types = {d["type"] for _, d in g.nodes(data=True)}
    assert {"company", "capability"} <= types and g.nodes[f"company:{focus}"]["focus"]
    edges = {d["type"]: d for _, _, d in g.edges(data=True)}
    assert "HAS_CAPABILITY" in edges and edges["HAS_CAPABILITY"]["status"] == "evidence" and edges["HAS_CAPABILITY"]["url"]
    assert all(d["status"] == "hypothesis" for _, _, d in g.edges(data=True) if d["type"] in ("COMPLEMENTS", "POTENTIAL_COLLABORATION"))
    only = ge.build_graph(seeded, profiles, None, focus, ["HAS_CAPABILITY"])
    assert {d["type"] for _, _, d in only.edges(data=True)} == {"HAS_CAPABILITY"}
    assert len(ge.figure(g).data) >= 2


def test_pipeline_ingest_with_mocked_sources(session, embedder):
    """Company agent -> opportunity agent -> recompute using canned HTTP responses only."""
    import json

    page = lambda name, desc, ind: (f"<html><head><title>{name} - Blue Science Park</title></head><body>Till medlemmar {name} {desc} "
                                    f"Bransch Antal anställda Grundat Ort Webb {ind} 1-10 2010 Karlskrona x.se Fler medlemmar</body></html>")
    index = '<a href="https://www.bluesciencepark.se/medlem/alpha/">a</a><a href="https://www.bluesciencepark.se/medlem/beta/">b</a>'
    vin = [{"Diarienummer": "2026-9", "Titel": "Sjökabel och sonar", "TitelEngelska": "Subsea cable sonar inspection call",
            "Oppningsdatum": "2026-01-01T00:00:00", "Stangningsdatum": "2099-01-01T00:00:00", "Publik": 1}]
    client = FakeClient({"https://www.bluesciencepark.se/medlem/alpha/": page("Alpha", "Erbjuder sonar och hydroakustiska system.", "Marinteknik"),
                         "https://www.bluesciencepark.se/medlem/beta/": page("Beta", "Installation av sjökabel.", "Sjökabelinstallation"),
                         "https://www.bluesciencepark.se/robots.txt": "User-agent: *\\nDisallow:",
                         "https://www.bluesciencepark.se/": index, "https://data.vinnova.se/api": json.dumps(vin)})
    trace = pipeline.ingest(session, client, deep_slugs=[], research=False)
    assert "2 profiles" in trace[0]["result"] and repo.counts(session)["funding"] == 1
    pipeline.recompute(session, embedder)
    hyp = session.query(CollaborationHypothesis).one()
    assert hyp.kind == "pair" and hyp.score_breakdown["research"] is None and "research" in hyp.score_breakdown["missing"]
    assert hyp.score_breakdown["coverage"] == 0.75 and hyp.funding_ids
    assert session.query(Opportunity).filter_by(kind="funding").count() == 2


@pytest.mark.parametrize("page", ["pages/0_Home.py", "pages/1_Innovation_Overview.py", "pages/2_Company_DNA.py",
                                  "pages/3_Innovation_Graph.py", "pages/4_Opportunity_Radar.py",
                                  "pages/5_Innovation_Blueprint.py", "pages/6_Evaluation.py", "pages/7_Staff_View.py"])
def test_ui_pages_render_without_exceptions(seeded, page):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", page), default_timeout=90).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.markdown) > 0
