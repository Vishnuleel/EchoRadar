# EchoRadar

### What should your company know this week, and who could help you build what comes next?

**An evidence-first innovation radar for Blue Science Park.** Built for the BUILD Hackathon 2026 · Virtual Science Park challenge.

EchoRadar turns scattered funding calls, research, test environments and member information into a company-specific briefing. It then connects companies with complementary capabilities and turns a potential collaboration into an **Innovation Blueprint** with sources, uncertainties and a first experiment.

**56 member profiles · 5 discovery areas · 161 passing automated tests · No API key required for the core demo**

[Three-minute jury walkthrough](#a-three-minute-jury-walkthrough) · [Run locally](#run-locally) · [Evidence and evaluation](#evidence-you-can-inspect) · [Full demo script](docs/demo_script.md)

![EchoRadar's newspaper-style front page, showing a company-specific funding lead, test environments and a weekly briefing](assets/screenshots/01_front_page.png)

*The Njord X edition: a personalised newspaper with source links, retrieval dates and suggested next steps. Screenshot from the stored November 2026 snapshot.*

## The problem

A member company needs a funding call, somewhere to test its product and a partner with the right expertise. The answers sit across funding portals, research databases, park websites and company pages. Finding a result is only the start: someone still has to decide whether it fits and what to do next.

EchoRadar starts with a public-source company profile, so a member has something useful before filling in a questionnaire. It uses that profile to answer three practical questions:

- **What is relevant to us?** Ranked funding, testing, events, research and news.
- **Who could complement us?** Potential partners supported by public capability evidence.
- **What could we try together?** A brief connecting the team, the opportunity and a first experiment.

For Blue Science Park staff, the same evidence reveals shared interests, gaps in profile coverage and connections worth facilitating.

## The differentiator: capabilities that fit together

EchoRadar's collaboration engine looks for different capabilities that can contribute to a shared application. For example, acoustic sensing, underwater vehicles and cable operations can fill distinct roles in a subsea inspection concept.

The engine checks explicit capability relationships, builds pairs and three-company combinations, reports missing roles, and connects the proposal to research, funding and test environments. Each proposal remains a **hypothesis**: public capability evidence does not imply that a company wants to collaborate.

An **Innovation Blueprint** brings the result together in 13 sections: the problem, proposed team, capability fit, supporting research, potential funding, test environments, first experiment, requirements, risks and sources. Export it as Markdown or PDF for a conversation with a member or park staff.

![Innovation Blueprint and Ask EchoRadar in the paper interface](assets/screenshots/03_spread_blueprint_ask.png)

## A three-minute jury walkthrough

Start the app, open [localhost:8000](http://localhost:8000), and use this sequence. The stored snapshot supports the walkthrough without live source access.

| Time | Open | What to inspect |
|---|---|---|
| 0:00–0:20 | **Latest**, select Njord X | A company-specific briefing: the finding, why it fits, its source and next step. |
| 0:20–0:50 | **Company profile** | Open a capability's evidence. Compare FACT and INFERENCE labels; inspect missing information. Use stored copies for the source-reading demonstration. |
| 0:50–1:30 | **Review and refine**, reading as Baltic Offshore | Choose Testing opportunities, then **See changes before saving**. Compare the proposed ranking. Leave the preview unsaved to preserve the snapshot. |
| 1:30–2:10 | **Innovation Blueprint** | Inspect a proposed team, the quoted capability evidence, missing roles, supporting opportunities and first experiment. Export the brief. |
| 2:10–2:40 | **Ask EchoRadar** | Try “We develop sensors. We need somewhere to test them.” Then try “Write a romantic poem.” and the supplied private-data override example. |
| 2:40–3:00 | **Method and evaluation** | Inspect test results, the baseline comparison and its caveats. Show the next step: validation with members and staff. |

For a six-minute pitch with expected results and recovery steps, use the [demo script](docs/demo_script.md). The [jury evidence guide](docs/judging_evidence.md) maps the project to the judging criteria.

## Evidence you can inspect

The shipped database contains retrieved public records. Fictional companies are confined to test fixtures. Snapshot figures below were recorded on **14 November 2026**; they are not promises about current source coverage.

| Evidence | Result | What it establishes |
|---|---|---|
| Working data pipeline | 56 member profiles, 92 funding calls, 200 research records, 4 test-environment pages, 11 events and 22 news items | The system joins real public sources. Five profiles include company-website enrichment; the rest use directory information. |
| Current automated suite | **161 passed, 0 failed**; 3 live-service tests excluded | Deterministic checks cover matching, evidence, privacy, boundaries, monitoring, exports and API behavior. [Recorded results](data/test_results.json). |
| Partner-ranking comparison | Precision@5 **1.00**, versus **0.40** for a similarity baseline | A sanity check on 36 team-labelled pairs. The same team wrote the relation table and labels; independent validation is still needed. [Methodology](docs/innovation_methodology.md). |
| Profile-claim audit | 40 sampled claims: **36 supported, 4 partly supported, 0 unsupported** | A team audit with AI assistance against source quotes. Companies have not confirmed the profiles. [Validation details](docs/technical_validation.md). |
| Boundary evaluation | **60 of 60** labelled requests handled as expected | A check of known cases, written by the same team as the rules. It does not establish protection against every wording. [Cases](data/eval/boundary_cases.json). |

**A concrete member example:** the documented Njord X snapshot brings 20 ranked findings and 5 proposed partnerships into one view, from a source pool of roughly 385 records. This is a record-count comparison; no user time savings or usefulness improvement has been measured. See the [worked comparison](docs/user_value_evaluation.md).

## What is built

| Capability | Member or staff experience |
|---|---|
| Company DNA | Source-linked facts, separate inferences, missing information, profile refinement, change preview and revision history. |
| Opportunity Radar | Funding, testing, events, research and news with filters, saved items and useful / not useful feedback. Closed calls and past events are filtered from recommendations. |
| Innovation Blueprint | Explained pair and three-company proposals with evidence, missing capabilities, risks and exportable next steps. |
| Connections graph | Explore companies, capabilities and opportunities; generated collaboration edges are visibly labelled hypotheses. |
| Staff desk | Inspect coverage, source monitoring, changes, shared interests and connections to facilitate. |
| Ask EchoRadar | A scope-checked question router retrieves answers from stored records, including contact and referral routes. |
| Evaluation and Task test | Inspect quality checks and run a timed comparison of the discovery task with and without EchoRadar. No participant study has been completed. |
| Automatic monitoring | While the app runs online, due sources are rechecked in the background and changed data triggers re-ranking. |

## Run locally

**Requirements:** Python 3.11+ and Node.js 18+, with about 3 GB of disk space. The latest local verification used Python 3.14 and Node.js 24 on Windows. Internet access is needed to install dependencies; the core app can then run from the bundled snapshot without an account, API key or paid service.

### Windows / PowerShell

Use a short checkout path on Windows to avoid deeply nested PyTorch paths.

```powershell
git clone https://github.com/Vishnuleel/EchoRadar.git
cd EchoRadar
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build

# Reproducible snapshot demo: no live checks or model download.
$env:NEXUS_OFFLINE = "1"
$env:NEXUS_EMBEDDINGS = "hash"
.venv\Scripts\python.exe -m api
```

Open **[http://localhost:8000](http://localhost:8000)**. One process serves the API and the built React app.

### macOS / Linux

```bash
git clone https://github.com/Vishnuleel/EchoRadar.git
cd EchoRadar
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
NEXUS_OFFLINE=1 NEXUS_EMBEDDINGS=hash .venv/bin/python -m api
```

The `hash` backend uses character n-gram embeddings. To use multilingual semantic embeddings and live monitoring, set `NEXUS_OFFLINE=0` and `NEXUS_EMBEDDINGS=auto`. The first semantic-model load downloads approximately 470 MB into `data/models/`; `auto` falls back to hashing if loading fails. The interface reports the active backend. Rankings can differ between backends.

For frontend development, keep the API running and use `npm --prefix web run dev` in another terminal. Vite serves the interface on port 5173 and proxies API requests to port 8000.

## How it works

```mermaid
flowchart TD
    A[Member directory and company websites] --> C[Profiles with claims and source evidence]
    B[Vinnova, OpenAlex, BSP and MTC sources] --> D[Funding, research, testing, events and news]
    C --> E[Complementarity engine: pairs and triads]
    D --> F[Opportunity matching and ranking]
    E --> F
    F --> G[Evidence, freshness and structure checks]
    G --> H[FastAPI and React: briefing, radar, graph and blueprints]
    I[Member refinements and feedback] --> F
```

The Python engine stores records in SQLite through SQLAlchemy. Ranking combines complementarity (35%), opportunity fit (25%), research fit (20%) and evidence quality (20%); missing components remain visible. These are initial design weights, not learned probabilities of success.

The default pipeline uses rules and multilingual embeddings. Assistant answers are assembled from stored records rather than written by a language model. Two optional Gemini paths support website-claim extraction and question routing; both are off by default and fall back to rules. Extracted claims must pass a source-quote check, which establishes that the quote exists, not that its interpretation is correct.

**Built for this project:** the agents, capability taxonomy and relation table, matching and ranking logic, question router, evidence and privacy handling, evaluation, API and interface. **Reused:** open-source libraries, pretrained models and public source data. Details: [architecture](docs/architecture.md), [matching methodology](docs/innovation_methodology.md), [requirements traceability](docs/partner_requirements_traceability.md).

<details>
<summary><strong>Configuration, refresh commands and tests</strong></summary>

Copy [.env.example](.env.example) to `.env` to configure the optional settings.

| Setting | Purpose |
|---|---|
| `NEXUS_OFFLINE=1` | Use the stored snapshot and cached source responses; disable live monitoring. |
| `NEXUS_EMBEDDINGS=auto`, `st` or `hash` | Choose semantic embeddings with fallback, semantic-only mode, or the lightweight offline backend. |
| `NEXUS_AUTO_MONITOR`, `NEXUS_MONITOR_INTERVAL` | Enable background checks and set the scheduler interval in seconds; default 900. Each source has its own due schedule. |
| `OPENALEX_API_KEY` | Optional key for an individual OpenAlex quota. |
| `NEXUS_LLM_EXTRACTION=gemini`, `NEXUS_LLM_ROUTING=gemini` | Enable optional model-assisted extraction or question routing; requires `GEMINI_API_KEY`. |
| `NEXUS_AUTH_MODE=token`, `NEXUS_AUTH_TOKENS` | Use a server-side company-token mapping instead of the simulated selector. |
| `NEXUS_DATABASE_URL` | Override the default SQLite database. |

Run Python commands with the virtual environment activated, or substitute its Python executable:

```bash
python -m nexus.monitor --once          # Run source checks that are due
python -m nexus.monitor --loop 300      # Check for due work every five minutes
python scripts/sync_directory.py        # Reconcile the directory and audited seed
python scripts/ingest.py                # Retrieve sources and rebuild derived results
python scripts/translate.py             # Translate new Swedish display text locally
python scripts/run_tests.py             # Deterministic tests; refresh the Evaluation report
python scripts/run_tests.py --live      # Also test external services
```

Live refreshes need `NEXUS_OFFLINE=0`. Results are stored in [data/test_results.json](data/test_results.json); live outcomes depend on external services. Source text and original evidence remain available alongside labelled machine translations.

Core stack: Python, FastAPI, SQLAlchemy, NetworkX, sentence-transformers, scikit-learn, NumPy and ReportLab; React, Vite, Tailwind CSS, TanStack Query and react-force-graph. Local translation uses transformers and sentencepiece.

The product was originally called NEXUS. The `nexus/` package, `NEXUS_` settings and database filename retain that name.

</details>

## Trust, limits and the next step

Facts, inferences, user input and collaboration hypotheses are labelled separately. Private company refinements, needs, saved items, ratings and questions are excluded from other companies' results and shared views. Aggregate feedback counts are visible anonymously.

**The demo's “Reading as” selector simulates sign-in.** It is not production authentication. Token mode exists, but identity-provider integration and a login flow remain pilot work.

The prototype has clear limits: only 5 of 56 profiles include company-website enrichment; 11 members have no confirmed capability; funding coverage is Vinnova only; matching rules and weights need domain review; translations can contain errors; and proposed partners have not expressed an interest. No user study or measured time saving is claimed. See the [full limitations](docs/known_limitations.md).

**Next: a four-week pilot with one park staff member and five member companies.** Extend website coverage, have members review their profiles, ask staff to rate proposed connections, and use the built-in task test to measure relevance and discovery time. The [pilot plan](docs/feasibility.md) defines the assumptions still to validate.
