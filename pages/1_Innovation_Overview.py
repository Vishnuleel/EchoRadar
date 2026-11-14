"""Page 1 - Innovation Overview: ecosystem statistics computed from stored records."""
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select

from nexus import ui
from nexus.agents.opportunity_agent import current_status
from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, FundingOpportunity, ResearchPublication
from nexus.utils.validators import utcnow

names = ui.setup("Innovation Overview")
ui.header("Ecosystem", "Innovation Overview", "Every number on this page is counted from stored records at page load.")

with ui.db() as s:
    n = repo.counts(s)
    funding = list(s.scalars(select(FundingOpportunity)))
    status = Counter(current_status(f) for f in funding)
    claims = [c for c in repo.all_claims(s) if c.claim_category == "capability" and c.capability]
    hyps = list(s.scalars(repo.public_hypotheses(s).order_by(CollaborationHypothesis.score.desc()).limit(8)))
    logs = repo.recent_logs(s, 12)
    newest_research = list(s.scalars(select(ResearchPublication).order_by(ResearchPublication.publication_date.desc()).limit(5)))

    ui.tiles([(n["companies"], "Profiled companies", f"{n['companies_website']} with website evidence"),
              (n["verified_capabilities"], "Verified capability claims", f"{n['inferences']} inferred interests kept separate"),
              (n["research"], "Research records discovered", "OpenAlex"),
              (f"{status['open'] + status['upcoming']}", "Open or upcoming funding calls",
               f"{status['closed']} closed, {status['unknown']} unknown of {n['funding']}"),
              (n["testbeds"] + n["events"] + n["news"], "Test environments, events, news", f"{n['testbeds']} / {n['events']} / {n['news']}"),
              (n["hypotheses"], "Collaboration hypotheses", "generated, not confirmed")])
    if n["demo_records"]:
        st.markdown(f'<div class="nx-sim">{n["demo_records"]} stored records are DEMO data and are labelled as such.</div>',
                    unsafe_allow_html=True)
    else:
        st.caption("No demo or simulated records are stored: all companies, research, calls and test environments "
                   "were retrieved from public sources.")
    st.write("")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Capabilities in the ecosystem")
        st.caption("Number of member companies with at least one public source for each capability.")
        per_cap = Counter()
        for key in {(c.company_id, c.capability.key) for c in claims if c.capability.key in tx.CAPABILITIES}:
            per_cap[key[1]] += 1
        top = per_cap.most_common(16)[::-1]
        fig = go.Figure(go.Bar(
            x=[v for _, v in top], y=[tx.CAPABILITIES[k].name for k, _ in top], orientation="h",
            marker=dict(color="#3987e5", cornerradius=4), width=0.62,
            customdata=[tx.ROLES[tx.CAPABILITIES[k].role] for k, _ in top],
            hovertemplate="<b>%{y}</b><br>%{x} companies<br>%{customdata}<extra></extra>"))
        fig.update_layout(height=470, margin=dict(l=0, r=10, t=6, b=0), paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c3cee0", size=12),
                          xaxis=dict(gridcolor="#1c2a44", zeroline=False, title="companies", dtick=1 if top and top[-1][1] < 8 else None),
                          yaxis=dict(showgrid=False), bargap=0.3,
                          hoverlabel=dict(bgcolor="#101a2e", font_color="#e8eef9"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with st.expander("View as table"):
            st.dataframe(pd.DataFrame([{"Capability": tx.CAPABILITIES[k].name, "Role": tx.CAPABILITIES[k].role, "Companies": v}
                                       for k, v in per_cap.most_common()]), hide_index=True, width="stretch")

    with right:
        st.subheader("Strongest hypotheses")
        ui.hypothesis_notice()
        for h in hyps[:6]:
            st.markdown(f'<div class="nx-card">{ui.badge("HYPOTHESIS")}<span class="nx-meta">{h.kind} - score {h.score:.0f}/100</span>'
                        f'<h4>{ui.esc(h.title)}</h4><p>{ui.esc(" + ".join(names[i] for i in h.participating_companies))}</p></div>',
                        unsafe_allow_html=True)

    st.subheader("Recent intelligence updates")
    a, b, c = st.columns(3, gap="large")
    with a:
        st.markdown("**Latest funding calls opened**")
        now = utcnow()
        recent = sorted([f for f in funding if f.opens_at and f.opens_at <= now], key=lambda f: f.opens_at, reverse=True)[:5]
        for f in recent:
            stt = current_status(f)
            st.markdown(f'<div class="nx-card">{ui.badge(stt)}<span class="nx-meta">opened {f.opens_at:%Y-%m-%d}'
                        f'{" - deadline " + f.deadline.strftime("%Y-%m-%d") if f.deadline else ""}</span>'
                        f'<p>{ui.esc(f.title[:110])}</p><p class="nx-meta">{ui.link(f.source_url, "Vinnova open data")}</p></div>',
                        unsafe_allow_html=True)
    with b:
        st.markdown("**Most recent research retrieved**")
        for r in newest_research:
            st.markdown(f'<div class="nx-card"><span class="nx-meta">published {r.publication_date:%Y-%m-%d}</span>'
                        f'<p>{ui.esc(r.title[:120])}</p><p class="nx-meta">{ui.link(r.source_url, "OpenAlex record source")}</p></div>',
                        unsafe_allow_html=True)
    with c:
        st.markdown("**Retrieval log**")
        if logs:
            st.dataframe(pd.DataFrame([{"When (UTC)": l.retrieved_at.strftime("%m-%d %H:%M"), "Source": l.source,
                                        "Status": l.status, "Records": l.records} for l in logs]),
                         hide_index=True, width="stretch", height=330)
        st.caption("Every external retrieval is logged with its status, including failures.")
