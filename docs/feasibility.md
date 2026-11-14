# Feasibility

## In one paragraph

**Next step:** a four-week pilot with Blue Science Park: one staff member and five member companies. Read all 56
members' websites (today 5), let the five members review their profiles and mark their top 10 radar findings,
and let staff rate 20 proposed connections. Proposed success thresholds, to be agreed with Blue Science Park:
most profile facts confirmed by the company, and at least half of each member's top 5 findings marked useful.
**Biggest remaining risk:** profile accuracy at scale. If the extracted profiles are wrong, every ranking built on
them is wrong and members stop trusting the service. It is managed, not solved: every fact shows its quote, a
member can remove a fact (the removal survives re-reading), a random sample is audited (36 of 40 supported, none
wrong), and the profile check shows a re-read before anything changes. The pilot measures it with the people who
know the answer.

## Critical assumptions and how they were tested

| Assumption | Tested? | Result |
|---|---|---|
| Public information gives a usable starting profile without a questionnaire | Yes, on all 56 public members | 45 of 56 (80%) get at least one evidenced capability; 11 do not and need the company's own input |
| The extracted facts are correct | Partly: team review of a random sample | 36 of 40 supported, 4 partly, 0 wrong. Not yet confirmed by the companies |
| The sources can be read and kept current automatically | Yes | Live tests against OpenAlex, Vinnova and the member directory pass; the monitor ran against live sources; failures are logged and fall back to the last copy |
| Different companies get different results | Yes, on stored data | Mean top-5 overlap between companies 0.006; no two of 38 companies share a top-5 list |
| The service stays inside its remit | Yes, with a caveat | 60 of 60 labelled questions handled as labelled; the labels were written by the team that wrote the rules |
| It runs without paid services or special hardware | Yes | One laptop; re-ranking about one second; no key required except an optional free OpenAlex key |
| Members find the results useful and act on them | **No** | Not tested; the pilot's main question |
| Staff trust generated partner proposals enough to make an introduction | **No** | Not tested; staff rating in the pilot |

## What exists now

A working application that runs on one laptop with Python and no paid services. Data retrieval for all 56
members takes under three minutes on first run and seconds afterwards (cached). Re-ranking takes about one
second.

## Dependencies

Python 3.11+, the packages in `requirements.txt`, and outbound HTTPS to api.openalex.org, data.vinnova.se,
bluesciencepark.se, mtcos.se, member websites and (once) huggingface.co for the embedding model.

## Resources for a 40+ member pilot

| Item | Need |
|---|---|
| Hosting | One small virtual machine (2 vCPU, 4 GB RAM) or a staff laptop |
| Storage | Under 1 GB (database 4 MB, cache 64 MB, embedding model 470 MB) |
| External costs | None required. OpenAlex key is free; Vinnova open data needs no key |
| People | About two weeks of a developer to add authentication, scheduling and more sources; a staff member 2–3 hours to review the relation table and label test pairs |

## Bottlenecks, in order

1. **Profile depth, not compute.** Five members have website-based profiles because each site had to be checked
   and allowed individually during the hackathon. Reading all members' sites is a configuration task (list of
   slugs in `pipeline.DEFAULT_DEEP_SLUGS`), about 8 page requests per member.
2. **Taxonomy coverage.** 11 members match no capability. Extending keywords and relations is manual work; an
   LLM-based extractor with the same evidence rules would scale better.
3. **Source breadth.** One funder, two event sources.
4. Pair scoring is O(n²): 1,540 pairs for 56 members, about 20,000 for 200. Still well under a second per
   recompute; triad search is bounded independent of n.

## Rollout plan

| Phase | Content |
|---|---|
| 1. Pilot (weeks 1–4) | Read all members' websites; staff review of taxonomy; 5 members review their profiles; collect ratings |
| 2. Hardening (weeks 5–8) | Real sign-in (for example Microsoft Entra ID; token mode exists), run the API as a service (it already re-checks the sources itself while it runs), show change events per member ("what changed since your last visit"), e-mail digest |
| 3. Breadth (weeks 9–12) | More funders (EU Funding & Tenders, Energimyndigheten), more event sources, member news feeds |
| 4. Scale | PostgreSQL + pgvector behind the existing FastAPI layer; hosted deployment of the React interface |

## Migration notes

- **PostgreSQL:** set `NEXUS_DATABASE_URL`; models use portable SQLAlchemy types. Move `EmbeddingCache.vector`
  to a pgvector column to search items in the database instead of in memory.
- **FastAPI / React:** done during the hackathon: `api/` exposes the engine, `web/` is the React interface.
- **Neo4j:** not justified at this size; the graph is rebuilt from SQL in milliseconds.
- **Background jobs:** `python -m nexus.monitor --once` (or `--loop N`) runs due checks with a lease lock;
  `scripts/ingest.py` is idempotent and cache-aware, so either can run from cron or Windows Task Scheduler as is.

## Risks and mitigation

| Risk | Mitigation |
|---|---|
| Wrong capability attributed to a member | Evidence sentence shown; member can remove it; removal survives re-ingest |
| Members distrust generated proposals | Hypothesis labelling everywhere; staff make first contact; ratings collected |
| Source pages change layout | Parsers fail visibly (logged, reported in trace); tests cover the parsers |
| A closed call shown as open | Status recomputed from dates at display time; verification rejects closed calls |
| Private data leaks between members | Ownership check in one module; tests cover denial; real authentication needed before pilot |
| Public source terms | robots.txt respected, polite rate, identifying user agent; only public pages |

## Open technical questions

- Is an LLM-based extractor more accurate than keyword rules on Swedish company sites, measured against
  member-reviewed profiles?
- Which weights best reflect what staff consider a good introduction?
- How should conflicting statements between the directory and a company's website be resolved?
