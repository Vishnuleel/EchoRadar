# Architecture

## Agents and how they work together

A plain sequential orchestrator (`nexus/pipeline.py`) runs the agents. Each step writes a trace entry (agent,
duration, counts, warnings) that the Home page shows. No agent calls a language model.

| Agent | Module | Input | Output |
|---|---|---|---|
| Company Intelligence | `agents/company_agent.py` | Member directory page, company website pages | Profile with claims; each claim has URL, excerpt, retrieval time, FACT/INFERENCE, confidence, verification status. Lists missing information. |
| Research Intelligence | `agents/research_agent.py` | OpenAlex search per capability present in the ecosystem | Publications, de-duplicated by OpenAlex ID and DOI |
| Opportunity Intelligence | `agents/opportunity_agent.py` | Vinnova open data; BSP and MTC test-environment pages | Funding calls with status derived from dates; test environments |
| Monitoring | `agents/monitoring_agent.py` | BSP event programme, BSP and MTC news | Events (date, time, place, format, audience), dated news linked to the members they name |
| Innovation Combination | `agents/combination_agent.py` + `core/matching_engine.py` | Active claims of all companies | Complementary pairs and three-company combinations |
| Ranking | `agents/ranking_agent.py` + `core/scoring.py` | Candidates, research, open calls | Score with four visible components; personalised list per company |
| Verification | `agents/verification_agent.py` | Scored candidates | Pass / pass with warnings / reject; checks evidence, freshness, structure, closed calls |
| Brief Generator | `core/blueprint_generator.py` | One verified hypothesis | 13-section blueprint, Markdown and PDF |
| Boundary guard and privacy | `security/` | User requests, retrieved text, data access | Scope decision, quarantined text, ownership checks |

## Data flow

`ingest()` retrieves and stores source data. `recompute()` rebuilds everything derived (hypotheses,
recommendations, radar items) from stored data; it runs after ingest and after every profile edit or feedback.
On the shipped data a recompute takes about one second once embeddings are cached.

## Storage

SQLite through SQLAlchemy (`database/models.py`, schema version 2 with a small migration mechanism in
`database/database.py`). Entities: Company, Capability, CompanyCapability (claim), Evidence, ResearchPublication,
FundingOpportunity, Testbed, Event, NewsUpdate, Opportunity (radar item), CollaborationHypothesis,
Recommendation, CompanyProfileRevision, UserFeedback, SavedItem, PrivateInteraction, RetrievalLog,
EmbeddingCache, SchemaVersion.

Public data (profiles, sources) is separated from private data (PrivateInteraction, UserFeedback, SavedItem).
Private rows always carry the owning company and are read only through `security/privacy.py`.

## How profiles stay current

- Every HTTP response is cached with its retrieval time (`integrations/http_cache.py`); a new `ingest` run
  re-fetches pages older than their time-to-live (1–3 days for member pages, 12 hours for Vinnova).
- Re-profiling replaces the public claims of a company but keeps user refinements and the claims a user removed.
- News that names a member is attached to that member and ranked high on its radar.
- Sources older than 120 days are marked stale: they lower the evidence score and raise a verification warning.
- Not implemented: a scheduler and a change report ("what changed in this profile since last run").

## Service boundaries

1. `boundary_guard.classify_request` — rule-based categories: in scope, needs clarification, out of scope,
   escalation to staff, prompt injection, privacy violation. Every turn is classified on its own text; a previous
   turn can only help interpret a short follow-up.
2. The assistant builds answers only from stored records, so there is no model to re-instruct.
3. `boundary_guard.filter_untrusted` — sentences from web pages that look like instructions are quarantined
   before extraction and logged.
4. `privacy.assert_owner` — private data requires the acting company to be the owner.
5. All external text is HTML-escaped before display.

## Migration path

The matching engine (`core/`) has no Streamlit or database imports, so it can sit behind a FastAPI service
unchanged. See `docs/feasibility.md`.
