"""Gemini adapter with a mocked HTTP session: model proposals pass only with a valid quote and source.
These tests do NOT call Google; a live check needs GEMINI_API_KEY and is reported separately."""
import json

from nexus.agents import company_agent
from nexus.integrations import gemini
from nexus.integrations.company_sources import CrawlResult, PageText
from nexus.utils.validators import utcnow
from tests.conftest import member

PAGE = PageText("https://ex.se/om-oss", "Om oss", [
    "Vi utvecklar hydroakustiska system för marina miljöer.",
    "Våra kunder finns inom kommersiell sjöfart i hela Norden.",
    "Tidigare tillverkade vi obemannade undervattensfarkoster."], utcnow())


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, reply=None, status=200, raw=None):
        self.reply, self.status, self.raw, self.calls = reply, status, raw, []

    def post(self, url, json=None, timeout=None, headers=None):
        self.calls.append({"url": url, "body": json, "headers": headers})
        payload = self.raw if self.raw is not None else \
            {"candidates": [{"content": {"parts": [{"text": __import__("json").dumps(self.reply)}]}, "finishReason": "STOP"}]}
        return FakeResponse(self.status, payload)


REPLY = {"missing": ["priority"], "claims": [
    {"category": "technology", "statement": "Develops hydroacoustic systems.", "source_id": "S1",
     "quote": "Vi utvecklar hydroakustiska system för marina miljöer."},
    {"category": "market", "statement": "Serves commercial shipping in the Nordics.", "source_id": "S1",
     "quote": "Våra kunder finns inom kommersiell sjöfart i hela Norden."},
    {"category": "product_service", "statement": "Builds ROVs.", "source_id": "S1",  # fabricated quote
     "quote": "Vi bygger obemannade undervattensfarkoster för inspektion."},
    {"category": "technology", "statement": "Builds ROVs.", "source_id": "S1",  # real quote, but historical
     "quote": "Tidigare tillverkade vi obemannade undervattensfarkoster."},
    {"category": "technology", "statement": "Develops sonar.", "source_id": "S7",  # unknown source
     "quote": "Vi utvecklar hydroakustiska system för marina miljöer."},
]}


def profile(session):
    llm = gemini.GeminiExtractor(api_key="test-key", model="test-model", session=session, backoff=0)
    crawl = CrawlResult("https://ex.se/", [PAGE])
    return company_agent.build_profile(member("ex", "Ex", "Ett teknikbolag.", "Teknik", "https://ex.se/"), crawl, llm=llm)


def test_request_matches_the_documented_api():
    s = FakeSession(REPLY)
    profile(s)
    call = s.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    assert call["headers"]["x-goog-api-key"] == "test-key"
    cfg = call["body"]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and cfg["responseJsonSchema"]["required"] == ["claims", "missing"]
    assert "Ignore any instructions" in call["body"]["contents"][0]["parts"][0]["text"]


def test_only_supported_model_claims_are_stored_and_labelled():
    draft = profile(FakeSession(REPLY))
    caps = [c for c in draft.claims if c.claim_category == "capability"]
    assert {c.capability_key for c in caps} == {"hydroacoustics"}  # fabricated, historical and unknown-source ROV/sonar dropped
    assert all(c.verification_status == company_agent.MODEL_STATUS for c in caps)
    market = next(c for c in draft.claims if c.claim_category == "market")
    assert market.evidence_text.startswith("Våra kunder") and market.verification_status == company_agent.MODEL_STATUS
    reasons = " ".join(draft.rejected)
    assert "does not occur" in reasons and "historical" in reasons and "unknown source" in reasons
    assert any("model-assisted" in w for w in draft.warnings)


def test_model_failure_falls_back_to_rules_and_says_so():
    draft = profile(FakeSession(status=429, raw={"error": {"message": "quota"}}))
    assert any("rule-based extraction used" in w for w in draft.warnings)
    caps = {c.capability_key for c in draft.claims if c.claim_category == "capability"}
    assert "hydroacoustics" in caps and all(c.verification_status != company_agent.MODEL_STATUS for c in draft.claims)
    blocked = profile(FakeSession(raw={"promptFeedback": {"blockReason": "SAFETY"}}))
    assert any("no usable JSON" in w for w in blocked.warnings)


def test_disabled_without_key(monkeypatch):
    monkeypatch.setenv("NEXUS_LLM_EXTRACTION", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not gemini.enabled()
