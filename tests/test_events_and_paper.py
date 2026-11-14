"""Event speakers and sponsors (only when a page names them), and the paper as a PDF."""
from datetime import datetime

from nexus.core import question_router as qr
from nexus.core import radar
from nexus.database.models import Event
from nexus.integrations import bsp_sources as b
from tests.test_api import api, as_  # noqa: F401  (fixture)

PROGRAMME = """<html><body>
<h2>Onsdagsluncher</h2>
<h3>Sensorer till havs</h3>
<p>Onsdagen den 2 december Tid: 11:45-12:50 Plats: Villa Oscar. Hur testar man sensorer i Östersjön? Lunchen sponsras av
Havsbolaget och Kustteknik som bjuder på mat.</p>
<p>Till anmälan</p>
<h5>Talare</h5><p>Anna Ek</p><h5>Sensora</h5>
<h3>AI i praktiken – så arbetar Sensora</h3>
<p>Onsdagen den 9 december Tid: 11:45-12:50 Plats: Villa Oscar. Föreläsningen hålls på svenska. Arrangeras tillsammans med lokala samarbetspartners.</p>
<p>Till anmälan</p>
<h5>Talare</h5><p>Bo Berg</p><h5>Robotix</h5>
</body></html>"""


def test_sponsors_are_named_only_when_the_page_names_them():
    assert [(x["name"], x["role"]) for x in b.find_sponsors("Lunchen sponsras av Saab och NKT som bjuder på mat.")] == \
        [("Saab", "sponsor"), ("NKT", "sponsor")]
    assert [x["name"] for x in b.find_sponsors("Sponsorer: Ericsson, Roxtec och Blekinge Tekniska Högskola. Välkommen!")] == \
        ["Ericsson", "Roxtec", "Blekinge Tekniska Högskola"]
    assert [(x["name"], x["role"]) for x in b.find_sponsors("Arrangeras i samarbete med Region Blekinge och Almi.")] == \
        [("Region Blekinge", "partner"), ("Almi", "partner")]
    # unnamed partners and ordinary guests are never turned into sponsors
    assert b.find_sponsors("Eventet arrangeras av MTC tillsammans med lokala samarbetspartners.") == []
    assert b.find_sponsors("Vi gästas av experter från Knowit.") == []


def test_programme_gives_each_occasion_its_own_title_speaker_and_sponsors():
    events = b.parse_event_programme(PROGRAMME, "https://example.org/prog", datetime(2026, 11, 14))
    first, second = events
    assert first["title"] == "Onsdagslunch: Sensorer till havs" and first["speakers"] == "Anna Ek Sensora"
    assert [x["name"] for x in first["sponsors"]] == ["Havsbolaget", "Kustteknik"]
    # an organisation heading that only ends a longer title does not replace the title
    assert second["title"] == "Onsdagslunch: AI i praktiken – så arbetar Sensora"
    assert second["speakers"] == "Bo Berg Robotix" and second["sponsors"] == []


def test_event_cards_show_organiser_speaker_and_an_honest_sponsor_line(session):
    now = datetime(2026, 11, 14)
    named = Event(key="e1", title="Sensorer till havs", organiser="Blue Science Park", speakers="Anna Ek Sensora",
                  sponsors=[{"name": "Havsbolaget", "role": "sponsor", "quote": "sponsras av Havsbolaget"}],
                  starts_at=datetime(2026, 12, 2, 11, 45), source_url="https://example.org/e1")
    plain = Event(key="e2", title="Nätverksträff", organiser="Tech Concept Lab", sponsors=[], source_url="https://example.org/e2")
    session.add_all([named, plain])
    session.commit()
    t1, t2 = dict(radar.describe("event", named, now)["terms"]), dict(radar.describe("event", plain, now)["terms"])
    assert t1["Sponsors"] == "Havsbolaget" and t1["Speaker (as published)"] == "Anna Ek Sensora"
    assert t1["Organised by"] == "Blue Science Park"
    assert t2["Sponsors"] == "None is named on the source page." and "Speaker (as published)" not in t2


def test_the_new_name_is_understood_in_questions():
    for q in ("What is EchoRadar?", "how does echo radar work", "What can EchoRadar do?", "what is nexus"):
        assert qr.route(q, None, datetime(2026, 11, 14)).kind == "help", q


def test_paper_pdf_for_visitor_and_owner(api):  # noqa: F811
    client, ids, _ = api
    cid = ids["sensora"]
    r = client.get("/api/paper.pdf", params={"company_id": cid})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and len(r.content) > 3000
    assert r.headers["content-type"] == "application/pdf" and 'filename="echoradar-sensora-' in r.headers["content-disposition"]
    own = client.get("/api/paper.pdf", params={"company_id": cid, "inline": "true"}, headers=as_(cid))
    assert own.status_code == 200 and own.headers["content-disposition"].startswith("inline")
    assert client.get("/api/paper.pdf", params={"company_id": 99999}).status_code == 404
    empty = client.get("/api/paper.pdf", params={"company_id": ids["finbank"]})  # a member with no confirmed capability
    assert empty.status_code == 200 and empty.content[:5] == b"%PDF-"
