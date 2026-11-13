# Technical validation

All figures were measured on 2026-11-13 on the shipped database.

## What was executed

| Check | Result |
|---|---|
| Live ingest from all sources | 56 profiles, 200 OpenAlex works (25 queries), 92 Vinnova calls, 4 test-environment pages, 11 events, 22 news items |
| Automated tests | 55 passed, 0 failed: 52 deterministic (mocked network, temporary database, hashing embedder) and 3 live (OpenAlex, Vinnova, member directory) |
| UI | All eight pages rendered in a headless browser without exceptions; each page also runs in the test suite on fixture data |
| Profile-edit journey through the real UI | For Baltic Offshore: setting "Testing opportunities" as a need moved three test-environment items to the top of the radar; adding the interest "machine learning for cable fault detection" was mapped to AI & machine learning and changed 2 of the top 5 partner recommendations |
| Assistant in a browser | Relevant request → `in_scope`; "Write a romantic poem." → `out_of_scope`; override attempt → `prompt_injection` |

## Stored data

| Measure | Value |
|---|---|
| Companies | 56 (5 with website evidence; 45 with at least one confirmed capability) |
| Fact claims | 295, all with a valid URL and an evidence excerpt |
| Capability claims | 108 |
| Inferred interests | 97, stored separately |
| Funding calls | 92: 15 open, 75 closed, 2 without dates |
| Hypotheses stored | 292, all with every capability claim sourced; 281 with at least one open call matched |
| Radar items | 703 |
| Companies with recommendations | 38 of 56; no two companies share an identical top-5 list |
| Demo or simulated records | 0 |

## Test map

| Required test | Where |
|---|---|
| Profile creation, update, persistence, evidence URLs, FACT vs INFERENCE, missing evidence, database persistence, schema migration | `tests/test_company_profiles.py` |
| OpenAlex and Vinnova parsing, API failures, duplicate research, stale calls, HTTP cache, live calls | `tests/test_integrations.py` |
| Similarity, complementarity, triads, score calculation, missing components, different rankings | `tests/test_matching_engine.py` |
| Relevant, unrelated, unclear and escalation requests, prompt injection, role persistence, malicious web content, privacy | `tests/test_boundaries.py` |
| Blueprint generation, export, unsupported combinations, verification rejection, full journey, events and news, graph, mocked ingest, UI pages | `tests/test_end_to_end.py` |

## Error handling

- Each connector raises a typed error with the service's own message; the agent logs it in RetrievalLog, reports
  it in the trace and stores nothing. Verified by `test_api_failure_handling`.
- If a live fetch fails and a cached copy exists, the cached copy is used and the failure is recorded.
- During development OpenAlex returned HTTP 429 (shared anonymous budget exhausted). The connector reported this
  rather than returning data; research was retrieved after a key was configured.

## Not verified

- Behaviour on Windows and macOS.
- Performance beyond 56 companies.
- The fallback embedding's match quality on the real data (it is exercised only in tests).
- Accuracy of the extracted profiles against the companies' own view: no company has reviewed its profile.
