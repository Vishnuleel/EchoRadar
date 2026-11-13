"""Opportunity Radar: every monitoring area, ranked for one company, with save and feedback."""
import streamlit as st
from sqlalchemy import select

from nexus import pipeline, ui
from nexus.core import radar
from nexus.database.models import Company, Event

names = ui.setup("Opportunity Radar")
ui.header("Discovery", "Opportunity Radar",
          "Funding, test environments, events, research and regional news from public sources, ranked for one company.")
ids = sorted(names, key=lambda i: names[i].lower())
acting = st.session_state.get("acting_company")
default = acting or st.session_state.get("dna_company") or ids[0]
LABEL = {"funding": "Funding", "testbed": "Testing opportunities", "event": "Events", "research": "Research", "news": "Regional news"}
f1, f2, f3, f4 = st.columns([2, 3, 1.3, 1.5])
cid = f1.selectbox("Company", ids, index=ids.index(default) if default in ids else 0, format_func=lambda i: names[i])
kinds = f2.multiselect("Monitoring area", list(LABEL), default=list(LABEL), format_func=LABEL.get)
min_rel = f3.slider("Minimum relevance", 0, 100, 25, 5)
view = f4.selectbox("Show", ["All items", "Saved by us", "Funding: open only"])

with ui.db() as s:
    if st.session_state.pop("radar_dirty", False):
        with st.spinner("Updating the ranking with your feedback..."):
            pipeline.save_trace(pipeline.recompute(s, ui.embedder()), ui.embedder().backend)
    company = s.get(Company, cid)
    items = radar.company_items(s, cid, kinds or None, min_rel)
    if view == "Saved by us":
        items = [i for i in items if "saved" in i["marks"]] if acting == cid else []
        if acting != cid:
            st.info("Saved items are private. Select this company under 'Acting as' to see its saved items.")
    elif view == "Funding: open only":
        items = [i for i in items if i["kind"] != "funding" or i["status"] == "open"]
    if company.need_priorities:
        st.caption("Company priorities applied to the ranking: " + ", ".join(company.need_priorities)
                   + ". Change them on the Company DNA page.")
    cols = st.columns(2, gap="large")
    for n, it in enumerate(items):
        with cols[n % 2]:
            ui.item_card(it, f"r{n}", acting if acting == cid else None, s, actions=True)
    if not items:
        st.info("No stored item matches these filters. Companies without evidence-backed capabilities have no radar items.")
    st.caption(f"{len(items)} items. Relevance = 70% text similarity (multilingual embeddings) + 30% shared capability tags, "
               "then adjusted for the company's stated priorities and feedback (shown as a ranking note). Closed funding "
               "calls and items the company marked 'not useful' are never listed.")
    past = [e for e in s.scalars(select(Event).order_by(Event.starts_at.desc())) if e.starts_at and radar.describe("event", e)["status"] == "past"]
    if past and "event" in kinds:
        with st.expander(f"Past events found on the source pages ({len(past)}) - not offered as opportunities"):
            for e in past:
                st.markdown(f"- {e.starts_at:%Y-%m-%d} - {e.title} - {e.location or 'location not stated'} "
                            f"([source]({e.source_url})). {e.date_note or ''}")
