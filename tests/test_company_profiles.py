"""Tests 1-5, 22: profile creation, persistence, evidence URLs, FACT vs INFERENCE, missing evidence."""
import pytest
from pydantic import ValidationError

from nexus.agents import company_agent
from nexus.database import repository as repo
from nexus.database.models import Company, CompanyCapability
from nexus.integrations.company_sources import CrawlResult, PageText, parse_member_page
from nexus.utils.validators import is_valid_url, utcnow
from tests.conftest import FIXTURE_MEMBERS, member


def test_company_profile_creation():
    m, crawl = FIXTURE_MEMBERS[0]
    draft = company_agent.build_profile(m, crawl)
    caps = {c.capability_key for c in draft.claims if c.claim_category == "capability"}
    assert {"underwater_sensors", "hydroacoustics", "environmental_monitoring"} <= caps
    assert draft.profile_depth == "website"
    assert any(c.claim_category == "market" for c in draft.claims)


def test_every_claim_has_required_evidence_fields():
    for m, crawl in FIXTURE_MEMBERS:
        for c in company_agent.build_profile(m, crawl).claims:
            assert c.claim_text and c.evidence_text and c.retrieved_at is not None
            assert is_valid_url(c.evidence_url), c
            assert c.classification in ("FACT", "INFERENCE") and 0 <= c.confidence <= 1 and c.verification_status


def test_evidence_url_validation_rejects_bad_urls():
    assert is_valid_url("https://www.bluesciencepark.se/medlem/x/")
    for bad in ("", None, "javascript:alert(1)", "ftp://x.y", "not a url", "https://nodot"):
        assert not is_valid_url(bad)
    with pytest.raises(ValidationError):
        company_agent.Claim(claim_text="x", claim_category="capability", classification="FACT", confidence=0.5,
                            verification_status="source_verified", evidence_url="javascript:alert(1)",
                            evidence_text="x", source_type="company_website", retrieved_at=utcnow())


def test_fact_versus_inference_classification():
    draft = company_agent.build_profile(*FIXTURE_MEMBERS[0])
    facts = [c for c in draft.claims if c.classification == "FACT"]
    inferences = [c for c in draft.claims if c.classification == "INFERENCE"]
    assert facts and inferences
    assert all(c.claim_category == "interest" and c.verification_status == "inferred" and c.confidence <= 0.6
               and "Not stated by the company" in c.evidence_text for c in inferences)
    assert all(c.claim_category != "interest" for c in facts)
    # corroborated by two different URLs -> higher confidence than a single source
    sens = [c for c in facts if c.capability_key == "underwater_sensors"]
    assert {c.verification_status for c in sens} == {"corroborated"} and sens[0].confidence == 0.9


def test_missing_evidence_creates_no_claims():
    """A company whose public text matches nothing gets no capabilities; the name alone proves nothing."""
    draft = company_agent.build_profile(member("sonar-ai", "Sonar AI Robotics", "Vi säljer kaffe och bakverk.", "Café"))
    assert not [c for c in draft.claims if c.claim_category in ("capability", "interest")]
    unreadable = company_agent.build_profile(member("x", "X", "Kaffe.", None, "https://x.example.com/"),
                                             CrawlResult("https://x.example.com/", [], ["https://x.example.com/: HTTP 503"]))
    assert unreadable.profile_depth == "directory" and any("could not be read" in w for w in unreadable.warnings)


def test_only_self_descriptions_become_capabilities():
    crawl = CrawlResult("https://c.example.com/", [
        PageText("https://c.example.com/partners", "Partners", ["Vår partner Acme bygger sonar och ROV för hela världen."], utcnow()),
        PageText("https://c.example.com/om-oss", "Om", ["Acme Corporation is a world leader in sonar technology products."], utcnow())])
    draft = company_agent.build_profile(member("c", "Cafeteria", "Lunchrestaurang.", "Restaurang", "https://c.example.com/"), crawl)
    assert not [c for c in draft.claims if c.claim_category == "capability"]


def test_profile_update_and_persistence(session, embedder):
    m, crawl = FIXTURE_MEMBERS[0]
    company = company_agent.persist_profile(session, company_agent.build_profile(m, crawl))
    session.commit()
    company.user_description = "Refined by the company"
    company.priority_domains = ["offshore_energy"]
    rows = company_agent.add_user_claim(session, company, "machine learning for sonar data", "interest", embedder)
    assert rows[0].classification == "USER" and rows[0].capability.key in ("ai_ml", "hydroacoustics")
    public = next(c for c in repo.claims(session, company.id) if c.claim_category == "capability" and c.origin == "public")
    company_agent.set_claim_active(session, public.id, False)
    repo.add_revision(session, company, "refined", author="Sensora")
    session.commit()
    cid, removed = company.id, (public.capability.key, public.claim_text)
    session.expire_all()

    again = session.get(Company, cid)
    assert again.user_description == "Refined by the company" and again.priority_domains == ["offshore_energy"]
    assert again.description.startswith("Vi utvecklar")  # the original public text is kept separately
    assert len(again.revisions) == 1 and again.revisions[0].snapshot["claims"]
    assert any(c.classification == "USER" for c in repo.claims(session, cid))

    # refreshing from public sources keeps user refinements and the user's removal
    company_agent.persist_profile(session, company_agent.build_profile(m, crawl))
    session.commit()
    all_claims = repo.claims(session, cid, active_only=False)
    assert any(c.classification == "USER" and c.active for c in all_claims)
    assert any((c.capability.key if c.capability else None, c.claim_text) == removed and not c.active for c in all_claims)


def test_database_persistence_across_sessions(tmp_path, monkeypatch):
    from nexus.database.database import get_sessionmaker
    from nexus.database.models import SchemaVersion

    url = f"sqlite:///{tmp_path / 'nexus_test_persist.db'}"
    s1 = get_sessionmaker(url)()
    company_agent.persist_profile(s1, company_agent.build_profile(*FIXTURE_MEMBERS[1]))
    s1.commit()
    s1.close()
    s2 = get_sessionmaker(url)()
    c = repo.company_by_slug(s2, "robotix")
    assert c is not None and s2.query(CompanyCapability).filter_by(company_id=c.id).count() >= 2
    from nexus.database.models import SCHEMA_VERSION

    assert max(v.version for v in s2.query(SchemaVersion)) == SCHEMA_VERSION
    s2.close()


def test_member_directory_page_parsing():
    html = """<html><head><title>Njord X - Blue Science Park</title></head><body><a href="https://www.bluesciencepark.se/">home</a>
    <div>Till medlemmar Njord X NjordX levererar hydroakustiska system. Bransch Antal anställda Grundat Ort Webb
    Marinteknik 11-50 1963 Karlskrona njordx.com Fler medlemmar</div><a href="https://www.njordx.com/">njordx.com</a></body></html>"""
    rec = parse_member_page(html, "njord-x", "https://www.bluesciencepark.se/medlem/njord-x/", utcnow())
    assert (rec.name, rec.industry, rec.employees, rec.founded, rec.location) == ("Njord X", "Marinteknik", "11-50", "1963", "Karlskrona")
    assert rec.website == "https://www.njordx.com/" and rec.description.startswith("NjordX levererar")
    assert parse_member_page("<html><title>x</title><body>nothing</body></html>", "x", "https://e.x/", utcnow()) is None


def test_schema_migration_from_v1(tmp_path):
    """A version-1 database gains the version-2 columns without losing data."""
    import sqlite3

    from nexus.database import database
    from nexus.database.models import SCHEMA_VERSION, Company

    path = tmp_path / "nexus_test_v1.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at DATETIME);
        INSERT INTO schema_version VALUES (1, '2026-01-01 00:00:00');
        CREATE TABLE company (id INTEGER PRIMARY KEY, slug VARCHAR(120), name VARCHAR(200), website VARCHAR(500),
            directory_url VARCHAR(500), description TEXT, user_description TEXT, industry VARCHAR(300), location VARCHAR(300),
            employees VARCHAR(50), founded VARCHAR(20), profile_depth VARCHAR(20), priority_domains JSON, is_demo BOOLEAN,
            created_at DATETIME, updated_at DATETIME);
        INSERT INTO company (id, slug, name, profile_depth, priority_domains, is_demo) VALUES (1, 'old', 'Old Co', 'directory', '[]', 0);
    """)
    con.commit()
    con.close()
    s = database.get_sessionmaker(f"sqlite:///{path}")()
    c = s.get(Company, 1)
    assert c.name == "Old Co" and (c.need_priorities or []) == []
    c.need_priorities = ["testing"]
    s.commit()
    assert max(v.version for v in s.query(database.SchemaVersion)) == SCHEMA_VERSION
    s.close()
