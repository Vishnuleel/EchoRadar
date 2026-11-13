# User value evaluation

## Status

**No user evaluation has been carried out.** No time savings, usefulness ratings or relevance ratings have been
measured, and none are claimed. This document describes the comparison that should be run and what is in place
to run it.

## Baseline: discovery without NEXUS

Steps a member would take today to answer "is there a funding call, a test environment and a possible partner
for our product?" (counted from the sources NEXUS reads, not timed with users):

1. Open Vinnova's call listing and read titles and descriptions of the open calls (15 open at retrieval).
2. For each plausible call, open it and read who can apply and the deadline.
3. Open Blue Science Park's and Marine Technology Center's pages on testing and events.
4. Read the member directory (56 entries) and guess who might complement the company.
5. Open candidate members' websites to check what they actually do.
6. Search for research on the topic.

## With NEXUS

1. Open Home and select the company: funding, testing, events, knowledge and potential partners are listed
   with reason, source, uncertainty and next step.
2. Open one recommendation as a Blueprint to see the partner evidence, research and calls together.

## What can be said without a study

- NEXUS reduces the number of sources to open from several sites to one page. Whether that saves meaningful
  time depends on whether the ranking is good enough that users trust the top items, which is untested.
- On the 36 team-labelled pairs, the complementarity engine puts complementary pairs first more often than text
  similarity does (see `docs/innovation_methodology.md`, including why this evidence is weak).

## Planned evaluation

| Question | Method | Measure |
|---|---|---|
| Is the generated profile accurate? | Each of 5 members reviews its profile | Share of claims confirmed, corrected, missing |
| Are radar items relevant? | Members rate their top 10 items | "Useful" share; precision@5 |
| Are partner hypotheses plausible? | Staff rate 20 hypotheses blind against 20 similarity-based suggestions | Mean rating 1–5, share rated 4 or 5 |
| Does it save time? | Same task with and without NEXUS, 5 participants | Minutes to find one actionable opportunity |

## What is already built for this

- "Useful" / "Not useful" / "Save" on every radar item, and a 1–5 rating on every Blueprint, stored per company.
- The Evaluation page shows the anonymous mean rating and count as soon as ratings exist. It currently shows
  "no ratings collected".

### Results

_None yet._
