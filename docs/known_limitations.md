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

- The assistant is rule-based retrieval, not a conversational language model.
- Boundary rules are pattern-based and tested against `tests/test_boundaries.py`; a determined user can probably
  phrase an off-topic request that passes as in scope. Answers are still built only from stored records.
- The untrusted-content filter drops sentences with known instruction patterns; it does not detect every attempt.

**Privacy and identity**

- Sign-in is simulated by a selector: the server trusts the company id the browser sends. This is a demonstration,
  not authentication; use only public or synthetic private data with it. Token mode (`NEXUS_AUTH_MODE=token`)
  ignores the client-supplied id, but there is no login screen for it and no identity provider integration.
- Private refinements, needs, feedback and saved items are kept out of every shared view and of other companies'
  results (tested). Aggregate counts (for example the number of ratings) are still shown anonymously.

**Product**

- The optional Gemini extraction is implemented behind quote validation and tested with recorded responses only;
  it has not been run against the live API.
- No user study, time measurement or human relevance rating has been carried out. The feedback functions work,
  but the stored database contains no ratings.
- Tested on Windows 11 with Python 3.13 and Node.js 22.
