# Problem validation

## Problem statement

Member companies of Blue Science Park need to follow funding calls, test environments, events, research and
potential partners. This information is spread over many websites, and assessing its relevance takes time that
a small company busy building its product does not have. Blue Science Park staff face the same search problem
across 40+ members when they try to spot shared interests and broker collaborations.

## Users

| User | Need | Where EchoRadar addresses it |
|---|---|---|
| Member company (primary) | "What should we know this week?" with a reason and a next step | Home digest, Opportunity Radar |
| Member company | A starting profile without filling in a questionnaire | Company DNA |
| Member company | Possible partners with complementary capabilities | Recommendations, Innovation Blueprint |
| Blue Science Park staff (internal) | Shared interests, connections to facilitate, thin profiles | Staff View |
| Other interested companies (secondary) | Explore the ecosystem | Public view of all pages |

## Confirmed by the challenge material

These statements come directly from the challenge brief and the kick-off presentation (13 November 2026):

- Information "is scattered across websites, research publications, and other channels. Finding it and assessing
  its relevance takes time."
- "A personalised service should have a useful starting point before a company fills in a detailed questionnaire."
- The service is for 40+ member companies, other interested users, and staff who want to "identify
  opportunities, understand shared interests across members, and support collaboration."
- Facts must be distinguished from inferred interests; inferred interests must not be treated as priorities.
- A suggested collaboration must be explained "without assuming that either company has expressed an interest."

## Symptoms and causes

What a member experiences (symptoms) is not what has to be fixed (causes). Each line says where the support comes
from: **B** = the challenge brief, **O** = observed in the public data while building (2026-11-13/14), **A** =
an assumption not yet checked with members.

| Symptom | Cause behind it | Support |
|---|---|---|
| A call, test environment or event is found too late, or not at all | The information sits in many places with different formats: one funder's API, several web pages, a research database. Nothing joins them | B; O: EchoRadar needs 9 separate sources for one weekly answer. O: of the 75 Vinnova calls that closed in the last 12 months, 28 fitted at least one member's public profile (fit 45 or more), and 23 of 56 members had at least one such call (3 of them public authorities). Whether the members saw them is unknown (A) |
| Most of what a member finds is not usable | Listings are not filtered for the reader: 75 of Vinnova's 92 recent calls were already closed; 9 of 11 published events were already past; the event page gives no year | O |
| Judging relevance takes time | Relevance depends on what the company does, and there is no structured description of that: the directory has one or two sentences per member, and for 11 of 56 they name no technology at all | B; O |
| A personalised service would need a long questionnaire first | No starting profile exists, so a service cannot be personal until the company invests time | B |
| Members do not find partners whose strengths complement theirs | Members describe what they do, not what they need; complementarity is only visible when profiles are compared side by side | A (the brief asks for "potential connections between companies", but does not say members miss them today) |
| Staff cannot see shared interests across 40+ members | The same missing structure, multiplied by the number of members | B |

## Why this problem is the one to solve

The causes share one root: **there is no evidence-based, comparable description of each member.** Every
monitoring area in the brief (knowledge, events, testing, funding, member developments) depends on it, because
relevance can only be judged against what a company does. So EchoRadar solves that first (a profile from public
sources, facts kept apart from inferences, editable by the company) and only then ranks the scattered sources
against it. Solving the root once makes every monitoring area cheaper to add; solving one area without it (a
better funding search, for example) would still need a questionnaire per member.

Within the brief's freedom to "choose one or two monitoring areas", EchoRadar goes deepest on **testing and funding**,
the two areas in the brief's own example journey ("we develop sensors; we need somewhere to test them") and in the
kick-off presentation, and adds **potential partners**, because the brief asks to "identify potential connections
between companies" and the same profiles make that possible.

## Observed while building

- **The opportunity you never saw (measured on 2026-11-14).** Every Vinnova call that closed in the last 12 months was
  scored against every member's current public profile with the radar's matching. 28 of 75 fitted at least one member
  (fit 45 or more; below that, unrelated calls start to appear). Example: three calls fitted EmbeddedArt and closed
  between May and October 2026, among them "Needs-driven defense innovation for a secure Baltic Sea region" (open
  24 March to 26 May). This shows the opportunities existed and fitted on paper; it does not show that anyone missed
  them, or would have been eligible. Shown per member on the radar and for the whole park on the Staff desk.
- **Proposals are short of a partner, the park is not.** 92 of 251 generated proposals lack a role; for every one
  of the 30 missing roles at least one other member has public evidence of it (for example: 17 proposals lack a
  vessel operator, and Stena Line and Affärsverken operate vessels). The only capability no member shows publicly is
  seabed survey and inspection.

- The member directory lists 56 organisations with one or two sentences each. For 11 of them that text is too
  general to identify any technology or expertise. Blue Science Park states it has over 80 members, so about a
  third are not in the public directory at all.
- Vinnova's open data returned 92 recent calls, of which 15 were open. Relevance has to be judged call by call;
  the data has no subject categories a small company could filter on.
- Every dated event on the published programme was already in the past when retrieved. A member checking the
  page that day would have found nothing upcoming.
- Almost all member and regional sources are in Swedish (125 texts needed translation for an English interface),
  while most research and many EU calls are in English: a member has to read both.
- Company websites describe products and markets in marketing language; the same technology appears under
  different words ("hydroakustik", "sonar", "ekolod"), which is why a shared capability vocabulary is needed
  before profiles can be compared.

## Assumptions not yet validated

1. Members would act on a weekly digest (rather than ignore it like a newsletter).
2. Capability complementarity is a useful basis for introductions, compared with staff's personal knowledge.
3. Members are willing to review and correct an automatically generated profile.
4. Staff want generated collaboration hypotheses, and trust them enough to make a first contact.
5. The public website text of a member reflects what it actually wants to work on.

## Interviews

No interviews have been conducted. Proposed questions:

**Member companies**
1. How did you find the last funding call, test environment or partner you acted on?
2. How much time per month goes into looking for such opportunities? Who does it?
3. Which opportunity did you learn about too late?
4. Looking at your generated profile: what is wrong, what is missing?
5. Looking at your top three radar items: would you act on any of them? Why or why not?
6. Would you want Blue Science Park to introduce you to the proposed partner?

**Blue Science Park staff**
1. How do you decide today which members to introduce to each other?
2. Which of these proposed connections did you already know about? Which are new and plausible? Which are wrong?
3. What would you need to see before contacting the companies?

### Findings

_To be filled in after interviews. Nothing has been entered because nothing has been collected._
