"""Page 3 - Innovation Connection Graph."""
import pandas as pd
import streamlit as st

from nexus import ui
from nexus.agents import combination_agent
from nexus.core import graph_engine as ge
from nexus.core import matching_engine as me

names = ui.setup("Innovation Graph")
ui.header("Knowledge graph", "Innovation Connection Graph",
          "Solid edges are backed by a source or calculated from text. Dashed edges are generated hypotheses.")

ids = sorted(names, key=lambda i: names[i].lower())
c1, c2 = st.columns([2, 3])
default = st.session_state.get("acting_company") or st.session_state.get("dna_company")
focus = c1.selectbox("Focus company", [None] + ids, index=([None] + ids).index(default) if default in ids else 0,
                     format_func=lambda i: "Whole ecosystem (strongest hypotheses)" if i is None else names[i])
edge_types = c2.multiselect("Relationship types", ge.EDGE_TYPES, default=ge.EDGE_TYPES)

with ui.db() as s:
    profiles = combination_agent.load_profiles(s, ui.embedder())
    sim = me.similarity_matrix(profiles)
    g = ge.build_graph(s, profiles, sim, focus, edge_types)
    if g.number_of_nodes() == 0:
        st.info("Nothing to show for this selection.")
        st.stop()
    event = st.plotly_chart(ge.figure(g), width="stretch", on_select="rerun", selection_mode="points",
                            key="graph", config={"displayModeBar": False})
    st.caption(f"{g.number_of_nodes()} nodes, {g.number_of_edges()} relationships. Hover for details, click a node to inspect it. "
               "Shapes: circle = company / capability, diamond = potential application (hypothesis), square = funding, "
               "hexagon = research, triangle = test environment.")

    selected = None
    pts = (event or {}).get("selection", {}).get("points", []) if event else []
    if pts and pts[0].get("customdata") in g.nodes:
        selected = pts[0]["customdata"]
    node_ids = sorted(g.nodes, key=lambda n: (g.nodes[n]["type"], g.nodes[n]["label"]))
    selected = st.selectbox("Inspect node", node_ids, index=node_ids.index(selected) if selected in node_ids else
                            (node_ids.index(f"company:{focus}") if focus and f"company:{focus}" in node_ids else 0),
                            format_func=lambda n: f"{g.nodes[n]['type']}: {g.nodes[n]['label']}")
    nd = g.nodes[selected]
    left, right = st.columns([2, 3], gap="large")
    with left:
        st.markdown(f'<div class="nx-card"><span class="nx-meta">{ui.esc(nd["type"].upper())}</span>'
                    f'<h4>{ui.esc(nd["label"])}</h4><p>{ui.esc(nd.get("detail") or "")}</p>'
                    f'<p class="nx-meta">{ui.link(nd.get("url"), "open source")}</p></div>', unsafe_allow_html=True)
        if nd["type"] == "application":
            st.session_state["bp_key"] = nd.get("key")
            st.page_link("pages/5_Innovation_Blueprint.py", label="Open this hypothesis as an Innovation Blueprint",
                         icon=":material/description:")
    with right:
        st.markdown("**Connected relationships and their explanations**")
        rows = []
        for u, v, d in g.edges(selected, data=True):
            other = v if u == selected else u
            rows.append({"Relationship": d["type"], "Status": d["status"], "Connected to": g.nodes[other]["label"],
                         "Explanation / evidence": d["explanation"], "Source": d.get("url")})
        rows.sort(key=lambda r: (r["Status"] != "evidence", r["Relationship"]))
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                         column_config={"Source": st.column_config.LinkColumn("Source", display_text="open"),
                                        "Explanation / evidence": st.column_config.TextColumn(width="large")})
        else:
            st.caption("No relationships with the current filter.")
    ui.hypothesis_notice()
