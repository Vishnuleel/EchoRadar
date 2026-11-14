"""Page 6 - Evaluation and Quality. Every figure is computed from stored data when the page loads."""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from nexus import ui
from nexus.agents import combination_agent
from nexus.core import evaluation as ev
from nexus.database import repository as repo
from nexus.security import privacy
from nexus.utils.config import DATA_DIR

names = ui.setup("Evaluation")
ui.header("Quality", "Evaluation and Quality", "Measured on the stored data. Nothing on this page is typed in by hand.")

with ui.db() as s:
    emb = ui.embedder()
    cov = ev.evidence_coverage(s)
    diff = ev.ranking_differentiation(s)
    fresh = ev.freshness(s)
    fb = privacy.aggregate_feedback(s)
    profiles = combination_agent.load_profiles(s, emb)
    cmp_ = ev.compare_with_baseline(profiles, {c.slug: c.id for c in repo.companies(s)})

pct = lambda x: "n/a" if x is None else f"{x * 100:.0f}%"
ui.tiles([(pct(cov["profile_coverage"]), "Profile evidence coverage", f"{cov['fact_claims_with_url_and_excerpt']} of {cov['fact_claims']} facts have URL + excerpt"),
          (pct(cov["recommendation_coverage"]), "Recommendation evidence coverage", f"{cov['hypotheses_fully_sourced']} of {cov['hypotheses']} hypotheses fully sourced"),
          (f"{diff['mean_jaccard_overlap_top_k']}", "Top-5 list overlap between companies", "Jaccard; 0 = fully different, 1 = identical"),
          (f"{fb['mean'] if fb['n'] else 'n/a'}", "Mean human relevance rating", f"{fb['n']} ratings collected in the app")])
if not emb.is_semantic:
    st.markdown(f'<div class="nx-sim">Embedding FALLBACK active ({ui.esc(emb.backend)}): {ui.esc(emb.fallback_reason)}</div>', unsafe_allow_html=True)
st.write("")

t1, t2, t3, t4 = st.tabs(["Baseline comparison", "Coverage and freshness", "Automated tests", "Method and limitations"])
with t1:
    st.subheader("Complementarity engine vs similarity-only baseline")
    st.markdown(f'<div class="nx-notice"><b>Read with care.</b> {ui.esc(cmp_["caveat"])}<br>Labelled by: {ui.esc(cmp_["labelled_by"])}</div>',
                unsafe_allow_html=True)
    st.caption(f"{cmp_['n_pairs']} labelled pairs ({cmp_['n_relevant']} labelled complementary). Both methods rank the same pairs; "
               "metrics show how well each ranking puts complementary pairs first.")
    if not cmp_["rows"]:
        st.info("None of the labelled company pairs exist in this database, so the comparison cannot be computed.")
    else:
        metrics = ["precision@5", "precision@10", "recall@10", "ndcg@10", "spearman"]
        fig = go.Figure()
        for name, key, color in (("EchoRadar complementarity", "nexus", "#3987e5"), ("Similarity baseline", "baseline", "#d95926")):
            fig.add_trace(go.Bar(name=name, x=metrics, y=[cmp_[key][m] for m in metrics], marker=dict(color=color, cornerradius=4),
                                 text=[f"{cmp_[key][m]:.2f}" for m in metrics], textposition="outside",
                                 textfont=dict(color="#c3cee0"), hovertemplate="%{x}: %{y:.2f}<extra>" + name + "</extra>"))
        fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, height=340, margin=dict(l=0, r=0, t=10, b=0),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c3cee0"),
                          yaxis=dict(range=[min(0, cmp_["baseline"]["spearman"], cmp_["nexus"]["spearman"]) - 0.05, 1.15], gridcolor="#1c2a44", zeroline=True, zerolinecolor="#2a3a58"),
                          legend=dict(orientation="h", y=1.12), hoverlabel=dict(bgcolor="#101a2e", font_color="#e8eef9"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        c1, c2 = st.columns(2)
        c1.metric("Mean label of top-5 (0-2), EchoRadar", cmp_["nexus"]["mean_label_top5"])
        c2.metric("Mean label of top-5 (0-2), baseline", cmp_["baseline"]["mean_label_top5"])
        df = pd.DataFrame(cmp_["rows"]).sort_values("nexus_complementarity", ascending=False)
        st.dataframe(df.rename(columns={"a": "Company A", "b": "Company B", "label": "Label (0-2)", "rationale": "Labelling rationale",
                                        "nexus_complementarity": "EchoRadar complementarity", "baseline_similarity": "Baseline cosine"}),
                     hide_index=True, width="stretch", height=420)
        wrong = df[(df["label"] == 0) & (df["nexus_complementarity"] >= 30)]
        missed = df[(df["label"] >= 1) & (df["nexus_complementarity"] == 0)]
        st.caption(f"Visible errors on this set: {len(wrong)} pair(s) labelled 'not complementary' still score 30 or more, and "
                   f"{len(missed)} pair(s) labelled complementary score 0 (no relation defined or capability not detected).")


with t2:
    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("Evidence coverage")
        st.dataframe(pd.DataFrame([
            {"Measure": "Fact claims", "Value": cov["fact_claims"]},
            {"Measure": "Fact claims with valid URL and excerpt", "Value": cov["fact_claims_with_url_and_excerpt"]},
            {"Measure": "Inferred interests (kept separate)", "Value": cov["inferences"]},
            {"Measure": "User-supplied claims (unverified)", "Value": cov["user_claims"]},
            {"Measure": "Stored hypotheses", "Value": cov["hypotheses"]},
            {"Measure": "Hypotheses whose capability claims all have a source", "Value": cov["hypotheses_fully_sourced"]},
            {"Measure": "Hypotheses with at least one research record", "Value": cov["hypotheses_with_research"]},
            {"Measure": "Hypotheses with at least one open/upcoming call", "Value": cov["hypotheses_with_open_funding"]},
        ]), hide_index=True, width="stretch")
        st.subheader("Ranking differentiation")
        st.write(f"{diff['companies_with_recommendations']} of {diff['companies_total']} companies have recommendations. "
                 f"Across {diff['pairs_compared']} company pairs, {diff['identical_list_pairs']} have identical top-{diff['top_k']} lists; "
                 f"{diff['distinct_top1']} distinct hypotheses appear as someone's number one.")
        st.caption("Companies without recommendations have no evidence-backed capability that the taxonomy recognises.")
    with b:
        st.subheader("Source freshness")
        st.dataframe(pd.DataFrame([{"Source": k, "Records": v["records"], "Newest (days)": v["newest_days"],
                                    "Oldest (days)": v["oldest_days"], f"Stale (> {v['stale_limit_days']} d)": v["stale"]}
                                   for k, v in fresh.items()]), hide_index=True, width="stretch")
        st.caption("Stale sources lower the evidence-quality score and are flagged by the Verification Agent.")
        st.subheader("Human feedback")
        if fb["n"]:
            st.write(f"{fb['n']} ratings, mean {fb['mean']} of 5 (anonymous aggregate).")
        else:
            st.info("No human ratings have been collected yet. Ratings entered on the Blueprint page appear here. "
                    "No rating has been invented to fill this space.")

with t3:
    st.subheader("Automated test results")
    p = DATA_DIR / "test_results.json"
    if p.exists():
        r = json.loads(p.read_text())
        ui.tiles([(r["passed"], "Passed", ""), (r["failed"], "Failed", ""), (r["skipped"], "Skipped", ""),
                  (f"{r['seconds']:.0f} s", "Duration", r["run_at"])])
        st.caption(f"Command: python -m {r['command']}. Live integration tests included: {'yes' if r['live_included'] else 'no'}.")
        st.dataframe(pd.DataFrame([{"File": c["file"], "Test": c["name"], "Outcome": c["outcome"],
                                    "Type": "LIVE external call" if c["live"] else "deterministic / mocked"} for c in r["cases"]]),
                     hide_index=True, width="stretch", height=460)
    else:
        st.info("No test run recorded yet. Run `python scripts/run_tests.py` to execute the suite and record the results.")

with t4:
    st.subheader("How the score is built")
    st.markdown("""
**S = 0.35 C + 0.25 O + 0.20 R + 0.20 E** (each 0-100; weights are initial hypotheses, not tuned on outcomes)

- **C - Capability complementarity.** Explicit relations between *different* capabilities (77 hand-written capability relations
  and 18 generic value-chain relations), gated by a shared application area and scaled by evidence confidence. The same capability
  on both sides counts as similarity, not complementarity.
- **O - Opportunity relevance.** Best three currently open or upcoming Vinnova calls: 70% multilingual text similarity + 30% shared capability tags.
- **R - Research relevance.** Same method against OpenAlex works.
- **E - Evidence quality.** Share and strength of the capability claims used: two independent sources > one source > user-supplied; stale sources are discounted.

A component without data counts as 0 and lowers the displayed *data coverage*; it is never filled in.
""")
    st.subheader("Known limitations")
    st.markdown((DATA_DIR.parent / "docs" / "known_limitations.md").read_text(encoding="utf-8")
                if (DATA_DIR.parent / "docs" / "known_limitations.md").exists() else "See docs/known_limitations.md")
