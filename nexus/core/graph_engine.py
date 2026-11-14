"""Knowledge graph (NetworkX) built from stored records, with a Plotly renderer.

Edge status tells the user how much to trust a relationship:
  evidence   - backed by a public source (HAS_CAPABILITY)
  computed   - calculated by NEXUS from text (SIMILAR_TO, RELEVANT_TO, SUPPORTED_BY)
  hypothesis - generated proposal (COMPLEMENTS, POTENTIAL_COLLABORATION); drawn dashed
"""
from __future__ import annotations

import networkx as nx
import numpy as np
import plotly.graph_objects as go
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import (CollaborationHypothesis, FundingOpportunity, Opportunity, ResearchPublication,
                                   Testbed)

NODE_STYLE = {  # validated categorical order (dataviz palette, dark surface); shape is a second encoding
    "company": ("#3987e5", 20), "application": ("#d95926", 17), "capability": ("#199e70", 13),
    "funding": ("#c98500", 13), "testbed": ("#d55181", 13), "research": ("#9085e9", 11),
}
EDGE_STYLE = {
    "HAS_CAPABILITY": ("#199e70", "solid", "evidence"), "SIMILAR_TO": ("#8a94a6", "dot", "computed"),
    "COMPLEMENTS": ("#3987e5", "dash", "hypothesis"), "RELEVANT_TO": ("#c98500", "solid", "computed"),
    "SUPPORTED_BY": ("#9085e9", "solid", "computed"), "POTENTIAL_COLLABORATION": ("#d95926", "dash", "hypothesis"),
}
EDGE_TYPES = list(EDGE_STYLE)


def build_graph(s: Session, profiles=None, similarity=None, focus_company: int | None = None,
                edge_types: list[str] | None = None, max_hypotheses: int = 5, max_radar: int = 3) -> nx.Graph:
    edge_types = set(edge_types or EDGE_TYPES)
    g = nx.Graph()
    companies = {c.id: c for c in repo.companies(s)}
    # the graph is a shared view: public hypotheses and public radar rows only
    hyps = list(s.scalars(repo.public_hypotheses(s).order_by(CollaborationHypothesis.score.desc())))
    if focus_company:
        hyps = [h for h in hyps if focus_company in h.participating_companies][:max_hypotheses]
        scope = {focus_company} | {c for h in hyps for c in h.participating_companies}
    else:
        triads = [h for h in hyps if h.kind == 'triad'][:4]
        hyps = triads + [h for h in hyps if h.kind == 'pair'][:6]
        scope = {c for h in hyps for c in h.participating_companies}

    def add_company(cid):
        c = companies[cid]
        g.add_node(f"company:{cid}", type="company", label=c.name, url=c.directory_url,
                   detail=(c.description or "")[:220], focus=cid == focus_company)

    for cid in scope:
        add_company(cid)

    if "HAS_CAPABILITY" in edge_types:
        for cl in repo.all_claims(s):
            if cl.company_id in scope and cl.claim_category == "capability" and cl.capability \
                    and cl.capability.key in tx.CAPABILITIES:
                node = f"capability:{cl.capability.key}"
                g.add_node(node, type="capability", label=cl.capability.name, url=None,
                           detail=tx.ROLES[cl.capability.category])
                if not g.has_edge(f"company:{cl.company_id}", node):
                    g.add_edge(f"company:{cl.company_id}", node, type="HAS_CAPABILITY",
                               status="evidence" if cl.classification == "FACT" else "user",
                               explanation=(cl.evidence.evidence_text[:200] if cl.evidence else ""),
                               url=cl.evidence.source_url if cl.evidence else None, weight=cl.confidence)

    for h in hyps:
        ids = h.participating_companies
        if h.kind == "pair" and "COMPLEMENTS" in edge_types:
            top = h.evidence[0] if h.evidence else {}
            g.add_edge(f"company:{ids[0]}", f"company:{ids[1]}", type="COMPLEMENTS", status="hypothesis",
                       explanation=f"{h.title}: {top.get('rationale', '')} (score {h.score:.0f})", url=None,
                       weight=h.score / 100, key=h.key)
        if h.kind == "triad" and "POTENTIAL_COLLABORATION" in edge_types:
            app = f"application:{h.key}"
            g.add_node(app, type="application", label=h.title, url=None,
                       detail=f"HYPOTHESIS (score {h.score:.0f}): {h.proposed_application}"[:260], key=h.key)
            for cid in ids:
                g.add_edge(f"company:{cid}", app, type="POTENTIAL_COLLABORATION", status="hypothesis",
                           explanation=f"Potential contributor to: {h.title}", url=None, weight=h.score / 100)
            if "SUPPORTED_BY" in edge_types:
                for r in h.research_ids[:1]:
                    row = s.get(ResearchPublication, r["id"])
                    if row:
                        node = f"research:{row.id}"
                        g.add_node(node, type="research", label=row.title[:70], url=row.source_url,
                                   detail=f"{', '.join(row.authors[:3])} ({row.publication_date:%Y})" if row.publication_date else "")
                        g.add_edge(app, node, type="SUPPORTED_BY", status="computed", url=row.source_url,
                                   explanation=f"Research relevance {r['relevance']:.0f}/100", weight=r["relevance"] / 100)
                for f in h.funding_ids[:1]:
                    row = s.get(FundingOpportunity, f["id"])
                    if row:
                        node = f"funding:{row.id}"
                        g.add_node(node, type="funding", label=row.title[:70], url=row.source_url,
                                   detail=f"Vinnova call, deadline {row.deadline:%Y-%m-%d}" if row.deadline else "Vinnova call")
                        g.add_edge(app, node, type="SUPPORTED_BY", status="computed", url=row.source_url,
                                   explanation=f"Potentially relevant funding ({f['relevance']:.0f}/100); eligibility not checked",
                                   weight=f["relevance"] / 100)

    if "RELEVANT_TO" in edge_types and focus_company:
        for kind, model in (("research", ResearchPublication), ("funding", FundingOpportunity), ("testbed", Testbed)):
            ops = s.scalars(select(Opportunity).where(Opportunity.company_id == focus_company, Opportunity.kind == kind,
                                                      Opportunity.audience == "public")
                            .order_by(Opportunity.relevance.desc()).limit(max_radar))
            for o in ops:
                row = s.get(model, o.ref_id)
                if row is None:
                    continue
                label = getattr(row, "title", None) or row.name
                node = f"{kind}:{row.id}"
                g.add_node(node, type=kind, label=label[:70], url=row.source_url, detail=o.why)
                g.add_edge(f"company:{focus_company}", node, type="RELEVANT_TO", status="computed", url=row.source_url,
                           explanation=f"{o.why} Relevance {o.relevance:.0f}/100.", weight=o.relevance / 100)

    if "SIMILAR_TO" in edge_types and profiles is not None and similarity is not None:
        idx = {p.id: i for i, p in enumerate(profiles)}
        for cid in list(scope):
            if cid not in idx:
                continue
            sims = [(float(similarity[idx[cid], idx[o]]), o) for o in idx if o != cid]
            for sim, other in sorted(sims, reverse=True)[:2 if focus_company == cid else 1]:
                if sim >= 0.55 and (other in scope or cid == focus_company):
                    if other not in scope:
                        add_company(other)
                    if not g.has_edge(f"company:{cid}", f"company:{other}"):
                        g.add_edge(f"company:{cid}", f"company:{other}", type="SIMILAR_TO", status="computed", url=None,
                                   explanation=f"Profile text similarity {sim:.2f} (similar, not necessarily complementary)",
                                   weight=sim)
    return g


def figure(g: nx.Graph, height: int = 700) -> go.Figure:
    fig = go.Figure()
    if g.number_of_nodes() == 0:
        return fig
    pos = nx.spring_layout(g, seed=7, k=2.6 / np.sqrt(max(1, g.number_of_nodes())), iterations=200, weight=None)
    for etype, (color, dash, status) in EDGE_STYLE.items():
        xs, ys, mx, my, texts = [], [], [], [], []
        for u, v, d in g.edges(data=True):
            if d["type"] != etype:
                continue
            xs += [pos[u][0], pos[v][0], None]
            ys += [pos[u][1], pos[v][1], None]
            mx.append((pos[u][0] + pos[v][0]) / 2)
            my.append((pos[u][1] + pos[v][1]) / 2)
            texts.append(f"<b>{etype}</b> ({d['status']})<br>{g.nodes[u]['label']} - {g.nodes[v]['label']}<br>{d['explanation'][:180]}")
        if xs:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", hoverinfo="skip", legendgroup=etype,
                                     line=dict(color=color, width=2 if status == "hypothesis" else 1.2, dash=dash),
                                     name=f"{etype} ({status})", opacity=0.75))
            fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", marker=dict(size=7, color=color, opacity=0.01),
                                     hovertext=texts, hoverinfo="text", showlegend=False, legendgroup=etype))
    for ntype, (color, size) in NODE_STYLE.items():
        nodes = [n for n, d in g.nodes(data=True) if d["type"] == ntype]
        if not nodes:
            continue
        show_label = ntype in ("company", "application") or (ntype == "capability" and g.number_of_nodes() <= 45)
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes],
            mode="markers+text" if show_label else "markers", name=ntype.capitalize(),
            text=[g.nodes[n]["label"][:30] + ("..." if len(g.nodes[n]["label"]) > 30 else "") for n in nodes] if show_label else None, textposition="top center",
            textfont=dict(size=11 if ntype != "capability" else 9, color="#dce6f5"),
            customdata=nodes,
            hovertext=[f"<b>{g.nodes[n]['label']}</b><br>{ntype}<br>{(g.nodes[n].get('detail') or '')[:220]}" for n in nodes],
            hoverinfo="text",
            marker=dict(size=[size + (8 if g.nodes[n].get("focus") else 0) for n in nodes], color=color,
                        line=dict(width=2, color="#0d1526"),
                        symbol={"application": "diamond", "funding": "square", "testbed": "triangle-up",
                                "research": "hexagon"}.get(ntype, "circle"))))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c3cee0"), hovermode="closest",
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=-0.02, font=dict(size=11)),
                      hoverlabel=dict(bgcolor="#101a2e", font_size=12, font_color="#e8eef9"))
    return fig
