**Data and profiles**

- The public member directory listed 56 profiles; the crawl followed its pagination to the end (4 pages, the
  fifth empty). Blue Science Park states it has over 80 members, so some members are not in the public directory.
  Member versus partner status is not published per organisation and is not stated.
- Five of the 56 profiles are enriched from the company's own website (Njord X, EmbeddedArt, C Marine, Baltic
  Offshore, Lassen Construction). The others rest on the short member-directory entry only.
- 11 members have no confirmed capability because their public text does not match the capability taxonomy
  (mostly public authorities and general consultancies). They get no radar until a capability or interest is added.
- Capability extraction is rule-based on sentences that describe the company itself. Since 2026-11-14 it rejects
  negated, historical and third-party statements and navigation text, and hides the company's own name before
  matching. The checks are conservative word rules: they can reject a true statement (the claim is then missing)
  and do not catch every misleading sentence.
- Manual audit of the five website profiles (2026-11-14): three EmbeddedArt "embedded systems" claims came from the
  company name, and Baltic Offshore "Telecom networks" / "Offshore wind" came from a 1989 history sentence. Both were
  fixed and are regression tests. The remaining quotes were read and support their claims; one is a judgement call
  (Baltic Offshore "Hydroacoustics & sonar" rests on owning a multibeam echo sounder, not a stated service).
- Random accuracy sample (2026-11-14, Evaluation page): 40 of the 106 stored capability facts checked against their
  quotes by the team with AI assistance: 36 supported, 4 partly, none wrong. The partly supported ones show the
  limits of word matching: two public agencies "responsible for" maritime surveillance are listed as having that
  capability (they use such systems, they do not supply them), and one fact rests only on an industry label.
- The live profile check on a page that was never ingested (softhouse.se) produced two wrong matches: the survey firm
  "Radar Group" read as radar, and "your investments" read as financing. Both terms were tightened; other such
  words certainly remain, which is why the check shows every quote and saves nothing.
- The live profile check reads at most five pages, skips language and country copies of a site, and does not save:
  rebuilding the stored profile is a separate step (`scripts/ingest.py`).
- Exact quote checking proves that an excerpt exists in its source. It does not prove that the excerpt means what
  the claim says; that still needs a person.
- The audited seed supplied with the project differs from the live official pages on 15 websites, 5 descriptions
  and 1 location (paraphrased or normalised values). The official wording is shown; seed values are kept for review.

**Language**

- Swedish source text is shown in English through a local machine translation (Helsinki-NLP/opus-mt-sv-en),
  labelled as such, with the original one click away. 125 texts are translated; one is flagged because a number
  did not survive. A manual check of a sample found mostly faithful translations and at least one meaning error
  (Försäkringskassan's "trygghetssystemen" became "public security systems" instead of "social insurance systems").
- Evidence quotes stay in their original language. Texts added after the last translation run show the Swedish
  original with a note until `scripts/translate.py` (or the monitor) runs.

**Monitoring sources**

- Funding covers Vinnova only. EU, Energimyndigheten, Almi and regional programmes are not connected.
- Of the 11 events found, 9 were already past at retrieval and are not offered; two recurring formats have no date.
  The event page states no year; the year is assumed from the retrieval date and this is shown next to the date.
- Event and news parsing is tailored to the current layout of bluesciencepark.se and mtcos.se.
- Test environments come from four pages; access terms are not published there, and NEXUS says so.
- Research relevance has little discriminating power: publications were retrieved by capability keyword.
- The monitor (`python -m nexus.monitor`) has run once against the live sources (Vinnova, the events page and two
  OpenAlex queries answered over the network on 2026-11-14; the other checks used responses cached within 24 hours).
  It is not registered as an operating-system service; someone has to start it. The first scan of each source only
  records a baseline, so change alerts begin with the second scan.

**Matching and scoring**

- The 77 capability relations, 18 role relations and 11 application concepts are hand-written by the team and have
  not been reviewed by Blue Science Park or domain experts.
- Score weights (0.35 / 0.25 / 0.20 / 0.20) are initial settings, not tuned against outcomes. A score expresses fit
  and evidence, not usefulness, eligibility or likelihood of success.
- The baseline comparison uses 36 pairs labelled by the development team, who also wrote the relation table. It
  is a sanity check, not a validation.

**Assistant and boundaries**

- The assistant is rule-based: a boundary check, a question router (park, member, comparison, count, period,
  how to apply, help) and retrieval from stored records. It is not a conversational language model and cannot
  hold a long conversation; a short follow-up ("and events?") reuses the previous subject only.
- Boundary and routing rules are pattern-based. The 60-question check on the Evaluation page passes 60 of 60, but
  the same team wrote the rules and the questions; a determined user can probably phrase an off-topic request that
  passes as in scope. Answers are still built only from stored records.
- What NEXUS does not store about Blue Science Park itself (address, opening hours, staff) it says it does not
  store. The contact email shown was copied from the contact page by hand and is not re-checked automatically.
- Optional model-assisted sorting of unplaced questions (Gemini, off by default) has been tested only with recorded
  responses, never against the live API.
- The untrusted-content filter drops sentences with known instruction patterns; it does not detect every attempt.

**Privacy and identity**

- Sign-in is simulated by a selector: the server trusts the company id the browser sends. This is a demonstration,
  not authentication; use only public or synthetic private data with it. Token mode (`NEXUS_AUTH_MODE=token`)
  ignores the client-supplied id, but there is no login screen for it and no identity provider integration.
- Private refinements, needs, feedback and saved items are kept out of every shared view and of other companies'
  results (tested). Aggregate counts (for example the number of ratings) are still shown anonymously.

**Product**

- The optional Gemini extraction (off by default) was run once against the live API on 2026-11-14 for Njord X
  (`scripts/check_gemini.py`; the first attempt got HTTP 503 "high demand" and fell back to the rules as designed).
  It proposed 21 website claims, all with valid quotes, against 14 from the rules, including markets, geography and
  collaborations the rules miss. A manual read found 3 of 21 filed under the wrong category (a marketing claim as
  geography, a supplier policy and a slogan as development priorities): the quote check cannot catch that.
- No user study, time measurement or human relevance rating has been carried out. The feedback functions work,
  but the stored database contains no ratings.
- Tested on Windows 11 with Python 3.13 and Node.js 22.
