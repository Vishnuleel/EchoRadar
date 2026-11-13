"""Deterministic fixtures. Unit tests never touch the network or the real database:
they use a temporary SQLite file, the hashing embedder and a fake HTTP client."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEXUS_EMBEDDINGS"] = "hash"
os.environ["NEXUS_SEED_PATH"] = ""  # tests pass their own seed explicitly

from nexus.integrations.company_sources import CrawlResult, MemberRecord, PageText  # noqa: E402
from nexus.integrations.http_cache import FetchResult  # noqa: E402
from nexus.utils.validators import utcnow  # noqa: E402


class FakeClient:
    """Stands in for HttpClient: returns canned responses by URL prefix, records calls."""

    def __init__(self, responses: dict | None = None, fail: bool = False):
        self.responses, self.fail, self.calls, self.events = responses or {}, fail, [], []

    def get(self, url, **kw):
        self.calls.append(url)
        if self.fail:
            return FetchResult(url, False, "error", 503, "", None, error="HTTP 503")
        for prefix, body in self.responses.items():
            if url.startswith(prefix):
                if isinstance(body, tuple):
                    return FetchResult(url, False, "error", body[0], body[1], None, error=f"HTTP {body[0]}")
                return FetchResult(url, True, "ok", 200, body, utcnow(), url)
        return FetchResult(url, False, "error", 404, "", None, error="HTTP 404")

    def allowed_by_robots(self, url):
        return True


def member(slug, name, description, industry, website=None):
    return MemberRecord(slug=slug, name=name, description=description, industry=industry, employees="1-10",
                        founded="2010", location="Karlskrona", website=website,
                        directory_url=f"https://www.bluesciencepark.se/medlem/{slug}/", retrieved_at=utcnow())


# TEST FIXTURE companies (fictional, used only in tests; never stored in the application database)
FIXTURE_MEMBERS = [
    (member("sensora", "Sensora", "Vi utvecklar undervattenssensorer och marina mätstationer för miljöövervakning.",
            "Marinteknik", "https://sensora.example.com/"),
     CrawlResult("https://sensora.example.com/", [PageText(
         "https://sensora.example.com/om-oss", "Om oss",
         ["Vi har lång erfarenhet av hydroakustik och sensorsystem för undervattensmiljöer.",
          "Våra kunder inom kommersiell sjöfart använder våra inbyggda system varje dag."], utcnow())])),
    (member("robotix", "Robotix", "Erbjuder obemannade undervattensfarkoster (ROV) för inspektion.", "Undervattensrobotik"), None),
    (member("mindworks", "Mindworks", "Erbjuder tjänster inom AI och maskininlärning samt dataanalys.", "Konsultverksamhet"), None),
    (member("cablelay", "CableLay", "Installation och reparation av sjökabel och undervattenskablar.", "Sjökabelinstallation"), None),
    (member("codehaus", "Codehaus", "Erbjuder tjänster inom AI, maskininlärning och mjukvaruutveckling.", "Konsultverksamhet"), None),
    (member("finbank", "Finbank", "Gör sparande enkelt genom en automatiserad investeringstjänst.", "Finansbolag"), None),
]


@pytest.fixture()
def session(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'nexus_test.db'}"
    monkeypatch.setenv("NEXUS_DATABASE_URL", url)
    from nexus.core import embeddings
    from nexus.database.database import get_sessionmaker

    embeddings.reset_embedder()
    s = get_sessionmaker(url)()
    yield s
    s.close()


@pytest.fixture()
def embedder():
    from nexus.core.embeddings import Embedder

    return Embedder("hash")


@pytest.fixture()
def seeded(session, embedder):
    """Database with fixture companies, two research records and three funding calls, recomputed."""
    from nexus import pipeline
    from nexus.agents import company_agent
    from nexus.database.models import FundingOpportunity, ResearchPublication, Testbed

    for m, crawl in FIXTURE_MEMBERS:
        company_agent.persist_profile(session, company_agent.build_profile(m, crawl))
    now = utcnow()
    session.add_all([
        ResearchPublication(external_id="W1", doi="https://doi.org/10.1/a", title="Autonomous underwater vehicle inspection of subsea cables with sonar",
                            authors=["A. Author"], abstract="We use an AUV and machine learning on sonar data to inspect submarine cable routes.",
                            publication_date=datetime(2024, 5, 1), source_url="https://doi.org/10.1/a",
                            capability_keys=["underwater_vehicles", "hydroacoustics", "ai_ml"], retrieved_at=now),
        ResearchPublication(external_id="W2", title="Machine learning anomaly detection in underwater sensor networks", authors=["B. Author"],
                            abstract="Anomaly detection for marine sensor data.", publication_date=datetime(2023, 3, 1),
                            source_url="https://openalex.org/W2", capability_keys=["ai_ml", "underwater_sensors"], retrieved_at=now),
        FundingOpportunity(external_id="2026-0001", title="Autonomous systems for maritime surveillance and underwater monitoring",
                           description="Develop and demonstrate autonomous underwater sensor systems.", opens_at=now - timedelta(days=10),
                           deadline=now + timedelta(days=30), status="open", eligibility="Only legal entities can apply.",
                           capability_keys=["underwater_sensors", "maritime_surveillance"],
                           source_url="https://data.vinnova.se/api/ansokningsomgangar/2026-0001", retrieved_at=now),
        FundingOpportunity(external_id="2020-0002", title="Underwater sensor systems call 2020", description="Closed call about underwater sensor systems.",
                           opens_at=now - timedelta(days=900), deadline=now - timedelta(days=800), status="closed",
                           capability_keys=["underwater_sensors"], source_url="https://data.vinnova.se/api/ansokningsomgangar/2020-0002",
                           retrieved_at=now),
        FundingOpportunity(external_id="2026-0003", title="Programme without published dates", description="Sensors and AI.",
                           status="unknown", capability_keys=["ai_ml"], source_url="https://data.vinnova.se/api/ansokningsomgangar/2026-0003",
                           retrieved_at=now),
        Testbed(name="Test harbour", description="A marine test environment where technology is tested.", kind="testbed",
                capability_keys=[], source_url="https://example.org/testbed", source_name="Example", retrieved_at=now),
    ])
    session.commit()
    pipeline.recompute(session, embedder)
    return session
