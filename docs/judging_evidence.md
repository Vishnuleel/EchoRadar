# Judging evidence

One answer per "Judges note" in the jury's criteria, where the jury can see the evidence, and what is still
missing. Figures were measured on 2026-11-14 on the stored data; each is shown live in the app or in the named file.

## Problem understanding (20%)

**Which problem, and what evidence supports the scope.** Members cannot see which funding calls, test
environments, events and partners fit them, because the information is scattered and there is no comparable,
evidence-based description of what each member does. We solve that root first (a profile from public sources) and
rank the scattered sources against it, going deepest on testing, funding and partners.

- Evidence: the brief, quoted; what we observed in the public data (75 of 92 Vinnova calls already closed, 9 of 11
  events already past, 11 of 56 directory entries naming no technology, about a third of members not in the
  public directory). Symptoms are separated from causes in `docs/problem_validation.md`.
- The symptom measured, not assumed: of the 75 calls that closed in the last 12 months, 28 fitted at least one
  member's public profile and 23 members had at least one (Staff desk; per member on the radar, for example three
  for EmbeddedArt). It shows the opportunities existed; it does not show anyone missed them.
- Gap: no interviews yet. Every assumption that only members can confirm is marked as an assumption.

## Feasibility (15%)

**One concrete next step:** a four-week pilot with one staff member and five members: read all 56 websites,
members review their profiles and mark their top findings, staff rate 20 proposed connections.
**Biggest remaining risk:** profile accuracy at scale; managed by showing every quote, member corrections that
survive re-reading, a random audit, and a re-read that never saves silently.

- Evidence: runs on one laptop with no paid service; critical assumptions and how each was tested in
  `docs/feasibility.md` (six tested, two not: whether members find the results useful, and whether staff trust the
  proposals).

## Technical quality (15%)

**What ran, was tested or was shown.**

- Shown live: the profiling agents re-reading Njord X's directory page and website (about 15 s, nothing saved);
  ranking that responds to a changed priority; Ask EchoRadar answering, declining and refusing.
- Automated test results are recorded in `data/test_results.json` and shown on the Evaluation page.
  Live checks against OpenAlex, Vinnova and the member directory run separately with `--live`.
  60 of 60 labelled boundary questions run through the real pipeline.
  40 random profile facts audited: 36 supported, 4 partly, 0 wrong.
- Structure: agents, engine, API and interface are separate (`docs/architecture.md`); the answers are built from
  stored records, so there is no language model to re-instruct.
- Backup: screenshots of every page in `assets/screenshots/`. **To do: record a backup video of the demo** (see
  "Before the presentation" below).

## User value (20%)

**Who benefits, what improvement, how it was checked.** A member company gets a starting profile it did not have
to write and, for Njord X, 20 ranked findings and 5 proposed partnerships instead of about 385 records across 9
sources, with closed calls and past events already removed and a reason, source, date and next step on each.
Blue Science Park staff get shared interests and connections worth facilitating.

- Checked: by counting (the worked comparison in `docs/user_value_evaluation.md`), not with users. Drawbacks are
  listed there: the time saving is not measured, recall is unknown, and Njord X has not confirmed its profile.
- Gap: no member has rated a finding yet. The ratings are built in and counted on the Evaluation page.
- Ready to close the gap: the **Task test** page times the brief's own task without and with EchoRadar (alternating
  order, role only, practice runs excluded) and feeds the Evaluation page. Run it with Blue Science Park staff and
  any member at the event.

## Innovation (10%)

**What is new.** Most recommenders suggest similar companies. EchoRadar proposes members whose different capabilities
complement each other (77 written capability relations, gated by a shared application area), including
three-company combinations, and connects each proposal to an open call, research and a test environment in an
Innovation Blueprint. Everything rests on quoted public evidence and is labelled as a hypothesis.

- Evidence: on 36 team-labelled pairs the complementarity ranking scores precision@5 1.0 against 0.4 for a
  similarity-only baseline (Evaluation page). The caveat is on the page: the team also wrote the relation table.
- Complete the team: for every role a proposal lacks, EchoRadar names members elsewhere in the park with public evidence
  of it (all 30 missing roles are covered by at least one member), and names the one real gap in the ecosystem.

## Presentation and demo (10%)

**Clarity and what was shown.** `docs/demo_script.md` follows the brief's own four demo steps in about six
minutes: a website becomes a profile, a user changes a priority, an opportunity becomes actionable, a boundary
holds. It ends with the measured quality check and the limitations.

## Partner relevance (10%)

**Which goals and requirements are met.** Every "Your prototype should" item of the brief is met and traced in
`docs/partner_requirements_traceability.md`: profiles for all 56 public members (at least three were required),
facts kept apart from inferences, editable profiles, six public sources (two were required), different rankings
for different profiles, source links and dates, the three boundary cases plus contact routes and referral to
staff, and labelled simulated sign-in. **Path to use:** the Staff desk for Blue Science Park, and the pilot above.

## What we built and what we reused

Say this plainly at the start or the end of the pitch. Written for this project: the agents, capability taxonomy
and relation table, matching and ranking, question router, profile check, evaluation, API and interface. Reused:
open-source libraries and models (SQLAlchemy, FastAPI, React, sentence-transformers and the models listed in the
README), and public data (the member directory, member websites, Vinnova open data, OpenAlex, Blue Science Park
and Marine Technology Center pages). The git history starts on 2026-11-13 with the Streamlit version; **the team
should state in its own words which parts were written during the hackathon weekend**, since the history alone
does not show when the first version was written.

## Questions the jury is likely to ask

| Question | Precise answer |
|---|---|
| Is this an LLM? | No language model writes any answer or profile. Extraction and answers are rules plus a multilingual embedding model for similarity. Two optional Gemini paths exist and are off by default; both fall back to the rules. |
| How do you know the profiles are right? | Every fact shows the sentence it came from. A random sample of 40 was checked: 36 supported, 4 partly, none wrong. The companies themselves have not reviewed them yet; that is the pilot. |
| What if a website tries to manipulate the agent? | Sentences that read like instructions are set aside before extraction (visible as the "Boundary filter" step) and logged; there is no model reading them that could obey. Tested with a planted page. |
| How does it stay current? | While the site runs, a background worker wakes every 15 minutes and re-checks the sources that are due (each has its own interval), records what changed, re-ranks when something did, and the open page refreshes its data without a reload; any profile can be re-read on demand, which shows what is new or no longer found before anything is saved. |
| Does it scale to 40+ members? | It already holds all 56 public members. Re-ranking takes about a second; the limit is profile depth (5 of 56 websites read), not compute. |
| Is a company told it is eligible? | Never. Each call shows Vinnova's own text and "eligibility has not been checked"; eligibility questions are referred to staff. |
| What can another company see about us? | Only public facts. Refinements, saved items, ratings and questions stay with the company (tested); sharing refinements is opt-in. Sign-in is simulated in the demo and labelled as such. |
| What did you test with real users? | Nothing yet, and we do not claim a time saving. The comparison we show is counted, not timed. |
| What would you build next? | The pilot: all member websites, member review of profiles, ratings, staff rating of proposals; then real sign-in and a "what changed since your last visit" view per member. |

## Before the presentation

0. **Run the Task test** with at least two or three people (Blue Science Park staff, a member, a mentor).
1. **Record a backup video** of the demo script on the demo machine (Windows 11: Snipping Tool's Record, or
   Game Bar with Win+Alt+R). The jury counts "a recorded backup demo" as evidence.
2. Rehearse the script twice against a clock.
3. If possible, run even one short session with a member company or a staff member and add what they said to
   `docs/problem_validation.md` and `docs/user_value_evaluation.md`. It is the largest remaining gap.
