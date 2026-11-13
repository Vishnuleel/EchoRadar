# Partner requirements traceability

Status: **Done** = implemented and exercised, **Partial** = implemented with a stated gap, **Not done**.

## Prototype requirements (challenge brief)

| # | Requirement | Status | Where | Evidence |
|---|---|---|---|---|
| 1 | Baseline profiles for at least three companies from websites and public sources | Done | Company DNA; `agents/company_agent.py` | 56 directory profiles; 5 with own-website evidence |
| 2 | Show evidence; distinguish facts from inferred interests | Done | Company DNA tabs "Verified facts" / "Inferred interests" | 295 facts, all with URL and excerpt; 97 inferences stored separately |
| 3 | User can review and refine a profile | Done | Company DNA → Review and refine | Persisted with revision history; verified through the UI |
| 4 | Opportunities from at least two distinct public sources | Done | Opportunity Radar | Vinnova, OpenAlex, Blue Science Park, Marine Technology Center |
| 5 | Different recommendations for different profiles | Done | Home, Radar, Company DNA → Recommendations | No two companies share a top-5 list |
| 6 | Source links and relevant dates | Done | Every card | Link, published date or deadline, retrieval date |
| 7 | Appropriate response to relevant, unrelated and override requests | Done | Home → Ask the assistant | Browser run and `tests/test_boundaries.py` |
| 8 | Clearly label simulated data or functionality | Done | Sidebar, Staff View, assistant box | Simulated sign-in and rule-based assistant labelled; no simulated data stored |

## Profile content

| Requirement | Status | Note |
|---|---|---|
| What the company does, products and services | Done | Directory description and website sentences |
| Technologies, expertise, application areas | Done | 37-capability taxonomy with application domains |
| Markets, industries, customer groups | Partial | Industry always; markets only when stated with recognised wording |
| Geographical focus | Partial | Location always; stated reach rarely captured |
| Stated priorities, projects, collaborations | Partial | Captured when literally stated; few hits |
| Topics that may be relevant | Done | Inferred interests |
| Source links and retrieval date | Done | |
| Flag missing or uncertain information | Done | "Missing or uncertain information" on each profile |
| Do not infer confidential plans | Done | Only public pages are read; inferences limited to application areas implied by evidenced capabilities |

## Monitoring areas

| Area | Status | Note |
|---|---|---|
| Funding | Done | Vinnova calls with purpose, deadline, "who can apply" text, potential match vs eligibility |
| Testing opportunities | Done | BSP and MTC environments, match explanation and next step; access terms not published |
| Events | Partial | Format, audience, date, place parsed; all dated events were past at retrieval, so only recurring formats are offered |
| Knowledge and trends | Partial | Research (OpenAlex) and regional news (BSP, MTC); no industry news; no "what changed" narrative |
| Personalised member monitoring | Partial | Matching, refinement, feedback, potential connections done; change detection between runs not done |
| Presentation and interaction | Done | Dashboard, digest, assistant |

## Boundaries

| Rule | Status | Where |
|---|---|---|
| Out-of-scope: explain remit and redirect | Done | `boundary_guard.classify_request` |
| Unclear connection: ask a focused clarification question | Done | Category `needs_clarification` |
| External content never treated as instructions | Done | `filter_untrusted`; no LLM reads web text |
| Role persistence across follow-ups and role requests | Done | Per-turn classification; role requests blocked |
| No disclosure of other companies' non-public data | Done | `security/privacy.py` |
| Distinguish information from advice, eligibility decisions, commitments | Done | Disclaimer on results; eligibility questions escalated |
| Refer human decisions to staff | Done | Category `escalation` with the public contact route |

## Deliverables

| Deliverable | Where |
|---|---|
| Working demo | `streamlit run app.py`; `docs/demo_script.md` |
| Solution explanation | `README.md`, `docs/architecture.md`, `docs/innovation_methodology.md` |
| Quality and boundary check | Evaluation page; `docs/technical_validation.md` |
| Handover package | Code, setup instructions, `docs/known_limitations.md`, `docs/feasibility.md` |
