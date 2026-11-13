**Data and profiles**

- Five of the 56 member profiles are enriched from the company's own website (Njord X, EmbeddedArt, C Marine, Baltic
  Offshore, Lassen Construction). The others rest on the short member-directory entry only.
- 11 members have no confirmed capability because their public text does not match the capability taxonomy
  (for example public authorities and general consultancies). They get no radar and no recommendations until
  someone refines the profile.
- Capability extraction is keyword-based on sentences that describe the company itself. It misses capabilities
  phrased in unexpected ways and can still pick up a wrong one (example in the current data: Baltic Offshore is
  tagged with "Telecom networks" from a sentence about the history of its cable unit). The review-and-refine step
  exists to correct this.
- "Markets", "geography", "collaborations" and "development activities" are captured only when literally stated
  with recognisable wording; for most members they are listed as missing.
- Website text is mostly Swedish and is shown verbatim, not translated.

**Monitoring sources**

- Funding covers Vinnova only. EU, Energimyndigheten, Almi and regional programmes are not connected.
- All dated events found on the source pages (the autumn 2026 Onsdagslunch programme) were already in the past
  at retrieval time, so the Events area currently shows two recurring formats without dates. The event page
  states no year; the year is assumed from the retrieval date and this is shown next to the date.
- Event and news parsing is tailored to the current layout of bluesciencepark.se and mtcos.se and will need
  adjustment if those pages change. One event title is cut short ("Malvacom").
- Test environments come from four pages; access terms are not published there, and NEXUS says so.
- Industry news beyond Blue Science Park and Marine Technology Center of Sweden is not monitored.
- Research relevance has little discriminating power: publications were retrieved by capability keyword, so most
  score high for the companies holding that capability.

**Matching and scoring**

- The 77 capability relations, 18 role relations and 11 application concepts are hand-written by the team. They
  have not been reviewed by Blue Science Park or domain experts.
- Score weights (0.35 / 0.25 / 0.20 / 0.20) and the similarity calibration bounds are initial settings, not tuned
  against outcomes. The score expresses fit and evidence, not likelihood of commercial success.
- Companies with many detected capabilities (EmbeddedArt) appear in many hypotheses.
- The baseline comparison uses 36 pairs labelled by the development team, who also wrote the relation table. It
  is a sanity check, not a validation, and too small for statistical conclusions. It shows at least one clear
  false positive (two similar consultancies scoring 48).

**Assistant and boundaries**

- The assistant is rule-based retrieval, not a conversational language model. It understands a limited set of
  intents and cannot summarise or reason about documents.
- Boundary rules are pattern-based. They were tested against the cases in `tests/test_boundaries.py`; a
  determined user can probably phrase an off-topic request that passes as in scope. Because answers are built
  only from stored records, such a request still returns records, not free text.
- The untrusted-content filter drops sentences with known instruction patterns; it does not detect every
  manipulation attempt.

**Product**

- Sign-in is simulated by a selector. The ownership checks behind it are real, but there is no authentication.
- No LLM integration is implemented, although the configuration file reserves a key for it.
- No scheduler: data is refreshed by running `scripts/ingest.py`.
- No user study, time measurement or human relevance rating has been carried out. The feedback functions work,
  but the stored database contains no ratings.
- Tested on Linux with Python 3.13 only.
