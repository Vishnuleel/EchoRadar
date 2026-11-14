# Technical validation

Figures measured on 2026-11-13 (ingest) and re-measured on 2026-11-14 (tests, quality checks, stored data).

## What was executed

| Check | Result |
|---|---|
| Live ingest from all sources | 56 profiles, 200 OpenAlex works (25 queries), 92 Vinnova calls, 4 test-environment pages, 11 events, 22 news items |
| Automated tests (2026-11-14) | 158 passed, 0 failed: 155 deterministic (mocked network, temporary database, hashing embedder) and 3 live (OpenAlex, Vinnova, member directory). Recorded in `data/test_results.json` and shown on the Evaluation page |
| Interaction limits (2026-11-14) | 60 labelled questions (relevant, Swedish, contact route, unrelated, unclear, override, private data, human decision, follow-up) run through the real Ask NEXUS pipeline: 60 of 60 handled as labelled, and no refusal showed any record. The first run found one failure ("Help me with AI" searched instead of asking a clarifying question); the rule was fixed, not the label. Labels and rules were written by the same team: a check of stated behaviour, not proof against new wording |
| Profile accuracy (2026-11-14) | 40 of the 106 stored capability facts drawn at random (seed 20261114) and each quote checked against its capability: 36 supported, 4 partly (two public agencies that use rather than supply surveillance systems, one fact resting only on an industry label, one broad IT-services sentence), 0 unsupported. Reviewed by the team with AI assistance, not by the companies. A live re-read of softhouse.se found two wrong matches that were not stored ("Radar Group", a survey firm, read as radar; "your investments" read as financing); both terms were tightened |
| Live profile check (2026-11-14) | The profiling agent re-run in the open from the Company profile page: Njord X read live (directory page and 5 website pages) in 14.8 s, 5 capabilities found, all already in the stored profile; nothing saved |
| UI | The React paper interface (page turns, reader, sidebar, Ask NEXUS, Evaluation) checked in a browser at 1440 x 900 and at phone width on 2026-11-14 without console errors. The Streamlit fallback loads headless without exceptions |
| Profile-edit journey through the real UI | For Baltic Offshore: setting "Testing opportunities" as a need moved three test-environment items to the top of the radar; adding the interest "machine learning for cable fault detection" was mapped to AI & machine learning and changed 2 of the top 5 partner recommendations |
| Assistant | 21 varied questions (contact, location, members by name, counts, periods, how to apply, help, Swedish, off-topic) each answered by the right kind of answer after the question router was added; before it, about half were not |

## Stored data

| Measure | Value |
|---|---|
| Companies | 56 (5 with website evidence; 45 with at least one confirmed capability) |
| Fact claims | 292, all with a valid URL and an evidence excerpt |
| Capability claims | 106 |
| Inferred interests | 97, stored separately |
| Funding calls | 92: 15 open, 75 closed, 2 without dates |
| Hypotheses stored | 251, all with every capability claim sourced; 241 with at least one open call matched |
| Radar items (public) | 710 |
| Companies with recommendations | 38 of 56; no two companies share an identical top-5 list |
| Demo or simulated records | 0 |

## Test map

| Required test | Where |
|---|---|
| Profile creation, update, persistence, evidence URLs, FACT vs INFERENCE, missing evidence, database persistence, schema migration | `tests/test_company_profiles.py` |
| OpenAlex and Vinnova parsing, API failures, duplicate research, stale calls, HTTP cache, live calls | `tests/test_integrations.py` |
| Similarity, complementarity, triads, score calculation, missing components, different rankings | `tests/test_matching_engine.py` |
| Relevant, unrelated, unclear and escalation requests, prompt injection, role persistence, malicious web content, privacy | `tests/test_boundaries.py` |
| Question router: kinds of question, member names and typos, periods, contact route, follow-ups, optional model sorting (mocked) | `tests/test_question_router.py` |
| Live profile check, interaction-limits check, profile-accuracy audit | `tests/test_quality_checks.py` |
| Blueprint generation, export, unsupported combinations, verification rejection, full journey, events and news, graph, mocked ingest, UI pages | `tests/test_end_to_end.py` |

## Error handling

- Each connector raises a typed error with the service's own message; the agent logs it in RetrievalLog, reports
  it in the trace and stores nothing. Verified by `test_api_failure_handling`.
- If a live fetch fails and a cached copy exists, the cached copy is used and the failure is recorded.
- During development OpenAlex returned HTTP 429 (shared anonymous budget exhausted). The connector reported this
  rather than returning data; research was retrieved after a key was configured.

## Not verified

- Behaviour on macOS and Linux (development and all runs were on Windows 11).
- Performance beyond 56 companies.
- The fallback embedding's match quality on the real data (it is exercised only in tests).
- Accuracy of the extracted profiles against the companies' own view: no company has reviewed its profile; the
  accuracy sample above was reviewed by the team.
- The optional model-assisted question sorting against the live Gemini API (tested only with recorded responses).
