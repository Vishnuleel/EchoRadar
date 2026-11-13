# Feasibility

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
| 2. Hardening (weeks 5–8) | Real sign-in (for example Microsoft Entra ID), nightly `ingest` via cron or a scheduler, "what changed" report, e-mail digest |
| 3. Breadth (weeks 9–12) | More funders (EU Funding & Tenders, Energimyndigheten), more event sources, member news feeds |
| 4. Scale | PostgreSQL + pgvector, FastAPI service around `nexus/core`, React front end if Streamlit becomes limiting |

## Migration notes

- **PostgreSQL:** set `NEXUS_DATABASE_URL`; models use portable SQLAlchemy types. Move `EmbeddingCache.vector`
  to a pgvector column to search items in the database instead of in memory.
- **FastAPI / React:** `nexus/core` and `nexus/agents` have no Streamlit imports; expose `pipeline.recompute`,
  `radar.company_items`, `pipeline.answer_request` and `blueprint_generator.build_blueprint` as endpoints.
- **Neo4j:** not justified at this size; the graph is rebuilt from SQL in milliseconds.
- **Background jobs:** `scripts/ingest.py` is idempotent and cache-aware, so it can run from cron as is.

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
