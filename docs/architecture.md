# Architecture

## Agents and how they work together

A plain sequential orchestrator (`nexus/pipeline.py`) runs the agents. Each step writes a trace entry (agent,
duration, counts, warnings) that the interface shows. By default no agent calls a language model; two optional,
off-by-default paths use Gemini (website extraction behind quote validation, and sorting of Ask EchoRadar questions
the rules cannot place), and both fall back to the rules.

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
| Paper as PDF | `core/paper_pdf.py` | One company's findings, proposals, missed calls and profile, as the site shows them | A two-column newspaper PDF with every source link; the public edition, or the company's own when it reads as itself |
| Boundary guard and privacy | `security/` | User requests, retrieved text, data access | Scope decision, quarantined text, ownership checks |
| Question router and answer builder | `core/question_router.py`, `core/answer_builder.py` | An in-scope (or unclear) question | The kind of question (park, help, member, comparison, count, opportunities with a period, partners, how to apply), the members it names and the period; an answer assembled from stored records and fixed sentences |
| Profile check | `agents/profile_check.py` | One member, on demand from its profile page | The profiling agents re-run in the open (directory page, website, boundary filter, extraction), compared with the stored profile: new, unchanged and no longer found. Saves nothing |
| Monitoring scheduler | `nexus/monitor.py` | Due monitor tasks (directory, Vinnova, events, news, test environments, OpenAlex per capability) | Fresh records, change events (new, updated, no longer observed), a lease lock so only one run works at a time |

## Data flow

`ingest()` retrieves and stores source data. `recompute()` rebuilds everything derived (hypotheses,
recommendations, radar items) from stored data; it runs after ingest and after every profile edit or feedback.
On the shipped data a recompute takes about one second once embeddings are cached.

## Storage

SQLite through SQLAlchemy (`database/models.py`, schema version 6 with a small migration mechanism in
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
- While the API runs, a background worker (`api/background.py`) wakes every 15 minutes (`NEXUS_MONITOR_INTERVAL`)
  and runs the monitoring checks that are due; each source keeps its own interval (24 hours for the directory,
  Vinnova, events and news; a week for test environments and research). What changed is recorded as change
  events, and any change triggers translation of new texts and a re-rank. The re-rank rewrites
  `data/last_run.json`, which drops the API's cached pages; the browser sees the new ranking time through
  `/api/health` (polled every 30 seconds) and refetches its data, so new information appears without a restart
  or reload. Off in offline mode or with `NEXUS_AUTO_MONITOR=0`. `python -m nexus.monitor --once` (or `--loop N`)
  does the same from the command line; a lease lock stops two workers scanning at once.
- On any member's profile page, "Read the sources live" re-runs the profiling agents and shows what is new,
  unchanged or no longer found compared with the stored profile. It does not save: rebuilding the stored
  profile is still a deliberate step (`scripts/ingest.py`), so a bad page cannot silently change a profile.

## Service boundaries

1. `boundary_guard.classify_request` — rule-based categories: in scope, needs clarification, out of scope,
   escalation to staff, prompt injection, privacy violation. Every turn is classified on its own text; a previous
   turn can only help interpret a short follow-up.
2. The question router decides what kind of question it is; the answer is built only from stored records and fixed
   sentences, so there is no model to re-instruct. The optional model sorting runs only after the boundary check,
   only for anonymous visitors, and may only choose from fixed lists.
6. The interaction limits are measured, not asserted: 60 labelled questions run through the real pipeline on the
   Evaluation page (`data/eval/boundary_cases.json`).
3. `boundary_guard.filter_untrusted` — sentences from web pages that look like instructions are quarantined
   before extraction and logged.
4. `privacy.assert_owner` — private data requires the acting company to be the owner.
5. All external text is HTML-escaped before display.

## Migration path

The engine (`nexus/`) sits behind a FastAPI layer (`api/`) with a React interface (`web/`).
See `docs/feasibility.md` for PostgreSQL, pgvector and authenticated deployment.
