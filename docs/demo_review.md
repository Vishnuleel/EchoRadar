# Demo review: findings and connections

Date: 2026-11-14. Data: the shipped database after the directory sync and re-ranking of that day.

**Who reviewed:** the development team, working with an AI coding assistant. This is a developer quality review of
whether each item is supported by its sources and makes sense. It is **not** user feedback: no member company or
Blue Science Park representative has rated these findings, and no rating has been entered in the app on anyone's
behalf. Human usefulness feedback is **pending**.

Companies: the three website-backed profiles used in the demo, Njord X, EmbeddedArt and Lassen Construction.

## What was checked

For each company, the top three radar findings and the top connection (collaboration hypothesis):

1. Does the finding follow from the company's evidenced profile, and does the stated reason match?
2. Funding: purpose, dates and stated eligibility; is eligibility presented as unchecked?
3. Connection: does every participant's contribution have its own public evidence; is a shared topic kept apart
   from a specific complementary relationship; does a cited publication support both sides or only one?
4. Does any output assume that a company is interested or has agreed to participate?

## Results

### Njord X (hydroacoustics, navigation, maritime communication)

| Finding | Assessment |
|---|---|
| Research: autonomous underwater monitoring with computer vision (relevance 79) | Fits: sonar and navigation are evidenced. Topic-level match only; the paper was not read by a person, as the card says. |
| Research: maritime communication networks with IoT (77) | Fits the evidenced maritime communication capability. |
| Research: underwater robots and operation control (75) | Partial fit: navigation is relevant, the robotics focus is closer to EmbeddedArt than to Njord X. |
| Connection: *Verified cyber-secure maritime on-board systems* with EmbeddedArt and Knowit (77) | Each slot has evidence: Njord X navigation and type-approval surveys (website and directory), Knowit IT security (directory "IT-säkerhet"), EmbeddedArt defence systems (directory and website). Plausible question: could a reference configuration for on-board OT security be tested together? Unknown: whether any of the three wants this, and whether Knowit's IT security covers ship OT. |

### EmbeddedArt (embedded systems, underwater sensors, IoT, defence)

| Finding | Assessment |
|---|---|
| Research: AI-powered sonar detection (99) | Strong fit with hydroacoustics, embedded systems and IoT. |
| Research: autonomous underwater monitoring (87) | Fits; also matches their underwater vehicle (submarine Malen). |
| Research: IoT underwater wireless sensor networks (82) | Fits IoT and underwater sensors. |
| Connection: same triad as Njord X (77) | As above. The paper evidence supports the Njord X and EmbeddedArt side (sonar, underwater vehicles) but not Knowit's; the blueprint now says so. |

### Lassen Construction (marine contracting, diving, dredging)

| Finding | Assessment |
|---|---|
| News: "Lassen Construction AB blir ny medlem i Blue Science Park" (90) | Correctly found (the article names the company) but of little use as an opportunity. The suggested next step was wrong ("consider contacting the actor behind it"); fixed. |
| Research: ROVs for inspecting offshore wind farms (61) | Plausible: underwater works and inspection; matched through the commercial-diving capability. |
| Research: ROV/AUV use in offshore wind O&M (48) | Weaker; the relevance score says so. |
| Connection: *Remote inspection support for underwater construction* with EmbeddedArt and Njord X (76) | Each slot has evidence (Lassen diving and marine works, EmbeddedArt vehicle and software, Njord X sonar and communication). Plausible question: could a sonar-guided, remotely documented inspection reduce diver time on a real worksite? Unknown: cost, availability of Malen, and interest of all three. |

Funding shown with these connections: *The Baltic Marine Watchdog Challenge* (Vinnova, open, deadline 2026-12-02,
"only legal entities are eligible") and *Cybersecurity, AI and resilience* (deadline 2027-01-19, consortia with at
least one Swedish industry company). Both purposes match the connection; eligibility is shown as Vinnova's text
and marked as not checked.

No output states or implies that a company has expressed interest or agreed to anything; every connection
carries the hypothesis notice and the uncertainty list.

## Problems found and fixed

1. **Repeated connections.** Each company's top three contained the same concept twice with a different third
   partner (for example "Verified cyber-secure maritime on-board systems" with Knowit and again with Nexer). A
   company's list now shows each concept once.
2. **Explanations that did not match the concept.** A triad listed its strongest pair links first, so the
   cyber-security connection was explained with sensor-to-communication reasons. Links between the capabilities
   that fill the concept's slots are now listed first.
3. **Contributions without their own evidence.** Slot assignments named a capability but carried no quote. Every
   contribution now carries its quote and source, and the blueprint shows it (or says it is unknown).
4. **One-sided research.** The blueprint now states which participants a publication relates to and which it does
   not, instead of implying it supports the whole connection.
5. **News about the member itself.** The next step now asks the member to check that the article describes it
   correctly, instead of suggesting a contact.

Each fix has a regression test (`tests/test_review_findings.py`).

## Priority change: before and after

Acting as Njord X, selecting "I'm looking for: Funding opportunities" and pressing "See changes before saving"
moves funding calls into the whole top five of the radar (before: four research papers and one test environment;
after: five Vinnova calls, led by the Baltic Marine Watchdog Challenge). Nothing was saved by the preview.

## Not done

- Human relevance and evidence-support ratings from a member or Blue Science Park representative: pending.
- Research relevance still has little discriminating power (most research items for a capability score high);
  the radar's default view is dominated by research for Njord X and EmbeddedArt, while the Home digest shows each
  area separately.
