"""Tests 6-9, 16: OpenAlex and Vinnova parsing, API failure handling, duplicates, stale calls.
Tests named test_live_* call the real services and are marked `live`."""
import json
from datetime import datetime, timedelta

import pytest

from nexus.agents import opportunity_agent, research_agent
from nexus.database.models import FundingOpportunity, ResearchPublication, RetrievalLog
from nexus.integrations import company_sources, openalex, vinnova
from nexus.integrations.http_cache import HttpClient
from nexus.utils.validators import utcnow
from tests.conftest import FakeClient

OPENALEX_PAYLOAD = {"results": [
    {"id": "https://openalex.org/W100", "doi": "https://doi.org/10.1000/abc", "title": "Sonar based seabed monitoring",
     "publication_date": "2023-04-05", "cited_by_count": 7,
     "authorships": [{"author": {"display_name": "Ada Lovelace"}}, {"author": {"display_name": "Alan Turing"}}],
     "primary_location": {"landing_page_url": "https://example.org/p", "source": {"display_name": "Ocean Eng."}},
     "abstract_inverted_index": {"monitoring": [2], "Seabed": [0], "sonar": [1]}, "topics": [{"display_name": "Underwater acoustics"}]},
    {"id": "https://openalex.org/W100", "doi": "https://doi.org/10.1000/abc", "title": "Sonar based seabed monitoring", "authorships": []},
    {"id": "https://openalex.org/W101", "doi": None, "title": "No abstract work", "publication_date": None, "authorships": [],
     "primary_location": None, "abstract_inverted_index": None, "topics": []},
    {"id": "https://openalex.org/W102", "title": None},
]}
VINNOVA_PAYLOAD = [
    {"Diarienummer": "2026-1", "Titel": "Öppen utlysning", "TitelEngelska": "Open call", "BeskrivningEngelska": "Autonomous systems",
     "Oppningsdatum": "2026-01-01T00:00:00", "Stangningsdatum": "2099-01-01T14:00:00", "Publik": 1,
     "LankLista": [{"Beskrivning": "Ansök", "URL": "https://ansok.vinnova.se/x"}],
     "WebTextLista": [{"TextID": 1, "TextEn": "Develop sensors."}, {"TextID": 2, "TextEn": "Only legal entities."}, {"TextID": 3, "TextEn": "Max 1 MSEK."}]},
    {"Diarienummer": "2025-2", "Titel": "Stängd", "TitelEngelska": "N/A", "Oppningsdatum": "2026-01-01T00:00:00", "Stangningsdatum": "2026-03-01T00:00:00", "Publik": 1},
    {"Diarienummer": "2027-3", "Titel": "Kommande", "Oppningsdatum": "2098-01-01T00:00:00", "Stangningsdatum": "2099-01-01T00:00:00", "Publik": 1},
    {"Diarienummer": "2026-4", "Titel": "Utan datum", "Publik": 1},
    {"Diarienummer": "2026-5", "Titel": "Not public", "Publik": 0},
    {"Diarienummer": "2026-1", "Titel": "Duplicate", "Publik": 1},
]


def test_openalex_response_parsing():
    works = openalex.search_works(FakeClient({openalex.API: json.dumps(OPENALEX_PAYLOAD)}), "sonar", per_page=8)
    assert [w["external_id"] for w in works] == ["W100", "W101"]  # duplicate and title-less records dropped
    w = works[0]
    assert w["title"] == "Sonar based seabed monitoring" and w["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert w["abstract"] == "Seabed sonar monitoring" and w["publication_date"] == datetime(2023, 4, 5)
    assert w["source_url"] == "https://doi.org/10.1000/abc" and w["venue"] == "Ocean Eng." and w["retrieved_at"] is not None
    assert works[1]["abstract"] is None and works[1]["publication_date"] is None  # missing stays missing
    assert works[1]["source_url"] == "https://openalex.org/W101"


def test_vinnova_response_parsing():
    now = datetime(2026, 11, 13)
    calls = {c["external_id"]: c for c in vinnova.fetch_calls(FakeClient({vinnova.API_BASE: json.dumps(VINNOVA_PAYLOAD)}), now=now)}
    assert set(calls) == {"2026-1", "2025-2", "2027-3", "2026-4"}
    c = calls["2026-1"]
    assert c["title"] == "Open call" and c["status"] == "open" and c["eligibility"] == "Only legal entities."
    assert c["funding_terms"] == "Max 1 MSEK." and c["apply_url"] == "https://ansok.vinnova.se/x"
    assert c["source_url"] == "https://data.vinnova.se/api/ansokningsomgangar/2026-1" and "Develop sensors." in c["description"]
    old = [{"Diarienummer": "2019-1", "Titel": "Very old round", "Stangningsdatum": "2019-03-01T00:00:00", "Publik": 1}]
    assert vinnova.fetch_calls(FakeClient({vinnova.API_BASE: json.dumps(old)}), now=now) == []  # long-closed rounds are noise
    assert calls["2025-2"]["title"] == "Stängd" and calls["2025-2"]["status"] == "closed"  # "N/A" English title ignored
    assert calls["2027-3"]["status"] == "upcoming" and calls["2026-4"]["status"] == "unknown"


def test_api_failure_handling(session):
    with pytest.raises(openalex.OpenAlexError, match="429"):
        openalex.search_works(FakeClient({openalex.API: (429, "rate limited")}), "x")
    with pytest.raises(openalex.OpenAlexError):
        openalex.search_works(FakeClient({openalex.API: "<html>not json</html>"}), "x")
    with pytest.raises(vinnova.VinnovaError):
        vinnova.fetch_calls(FakeClient(fail=True))
    with pytest.raises(vinnova.VinnovaError):
        vinnova.fetch_calls(FakeClient({vinnova.API_BASE: '{"unexpected": true}'}))
    # agents report the failure, log it, and store nothing
    r = research_agent.collect_research(session, FakeClient(fail=True), ["hydroacoustics", "ai_ml"])
    f = opportunity_agent.collect_funding(session, FakeClient(fail=True))
    t = opportunity_agent.collect_testbeds(session, FakeClient(fail=True))
    assert r["errors"] and f["errors"] and t["errors"] and r["new"] == 0
    assert session.query(ResearchPublication).count() == 0 and session.query(FundingOpportunity).count() == 0
    assert session.query(RetrievalLog).filter_by(status="error").count() >= 2
    members, errors = company_sources.fetch_member_directory(FakeClient(fail=True))
    assert members == [] and company_sources.crawl_company_site(FakeClient(fail=True), "https://x.example.com/").errors


def test_duplicate_research_detection(session):
    client = FakeClient({openalex.API: json.dumps(OPENALEX_PAYLOAD)})
    first = research_agent.collect_research(session, client, ["hydroacoustics"])
    second = research_agent.collect_research(session, client, ["underwater_sensors"])
    assert first["new"] == 2 and second["new"] == 0 and second["duplicates"] == 2
    assert session.query(ResearchPublication).count() == 2
    row = session.query(ResearchPublication).filter_by(external_id="W100").one()
    assert {"hydroacoustics", "underwater_sensors"} <= set(row.capability_keys)  # tags merged, record not duplicated
    same_doi = {**openalex.parse_work(OPENALEX_PAYLOAD["results"][0], utcnow()), "external_id": "W999"}
    _, created = research_agent.upsert_publication(session, same_doi)
    assert not created


def test_stale_opportunity_handling(seeded):
    """A call whose deadline has passed is closed whatever was stored, and never offered as current."""
    from nexus.database.models import CollaborationHypothesis, Opportunity

    now = utcnow()
    assert vinnova.call_status(now - timedelta(days=5), now - timedelta(seconds=1), now) == "closed"
    assert vinnova.call_status(None, None, now) == "unknown"
    closed = seeded.query(FundingOpportunity).filter_by(external_id="2020-0002").one()
    closed.status = "open"  # even a wrong stored status must not leak through
    seeded.commit()
    assert opportunity_agent.current_status(closed) == "closed"
    assert "closed" in opportunity_agent.funding_next_action(closed).lower()
    used = {f["id"] for h in seeded.query(CollaborationHypothesis) for f in h.funding_ids}
    assert closed.id not in used and used
    assert closed.id not in {o.ref_id for o in seeded.query(Opportunity).filter_by(kind="funding")}
    # a call that closes after ranking is still caught when displayed
    open_call = seeded.query(FundingOpportunity).filter_by(external_id="2026-0001").one()
    assert opportunity_agent.current_status(open_call, now + timedelta(days=60)) == "closed"


def test_http_cache_reuses_and_offline(tmp_path):
    class Resp:
        status_code, text, url, encoding, apparent_encoding = 200, "hello", "https://e.example.com/a", "utf-8", "utf-8"

    class Sess:
        n = 0

        def get(self, *a, **k):
            Sess.n += 1
            return Resp()

    c = HttpClient(cache_dir=tmp_path, offline=False, min_interval=0, session=Sess())
    assert c.get("https://e.example.com/a").status == "ok" and c.get("https://e.example.com/a").status == "cached" and Sess.n == 1
    off = HttpClient(cache_dir=tmp_path, offline=True, session=Sess())
    assert off.get("https://e.example.com/a").text == "hello" and off.get("https://e.example.com/missing").status == "offline"
    assert Sess.n == 1


# ---- live integration tests (real network) -----------------------------------------------------
@pytest.mark.live
def test_live_openalex_search(tmp_path):
    works = openalex.search_works(HttpClient(cache_dir=tmp_path, offline=False), "wave energy converter", per_page=5)
    assert works and all(w["title"] and w["source_url"].startswith("http") for w in works)


@pytest.mark.live
def test_live_vinnova_calls(tmp_path):
    calls = vinnova.fetch_calls(HttpClient(cache_dir=tmp_path, offline=False), changed_since_days=60)
    assert calls and all(c["status"] in ("open", "closed", "upcoming", "unknown") for c in calls)
    assert all(c["source_url"].startswith("https://data.vinnova.se/api/") for c in calls)


@pytest.mark.live
def test_live_member_directory(tmp_path):
    members, errors = company_sources.fetch_member_directory(HttpClient(cache_dir=tmp_path, offline=False), limit=3)
    assert len(members) == 3 and all(m.description and m.directory_url.startswith("https://www.bluesciencepark.se/medlem/") for m in members)
