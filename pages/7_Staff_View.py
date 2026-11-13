"""Staff view for Blue Science Park: shared interests across members and where to support collaboration."""
from collections import Counter, defaultdict

import pandas as pd
import streamlit as st
from sqlalchemy import select

from nexus import ui
from nexus.agents import company_agent
from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, NewsUpdate
from nexus.security import privacy

names = ui.setup("Staff View")
ui.header("Blue Science Park staff", "Ecosystem View",
          "Shared interests across members, connections worth facilitating, and where profiles need attention.")
st.markdown('<div class="nx-sim">SIMULATED: this page has no staff login in the prototype. It only shows public profile '
            'data and anonymous aggregates; no company\'s private questions, saved items or ratings are exposed.</div>',
            unsafe_allow_html=True)

with ui.db() as s:
    comps = repo.companies(s)
    claims = repo.all_claims(s)
    by_cap, by_domain = defaultdict(set), defaultdict(set)
    for c in claims:
        if c.claim_category == "capability" and c.capability and c.capability.key in tx.CAPABILITIES and c.classification == "FACT":
            by_cap[c.capability.key].add(c.company_id)
            if tx.CAPABILITIES[c.capability.key].role != "ENABLER":
                for d in tx.CAPABILITIES[c.capability.key].domains:
                    by_domain[d].add(c.company_id)
    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("Shared interest areas")
        st.caption("Application areas where several members have evidenced capabilities: candidates for a theme meeting.")
        rows = [{"Application area": tx.DOMAINS[d], "Members": len(ids), "Who": ", ".join(sorted(names[i] for i in ids))}
                for d, ids in sorted(by_domain.items(), key=lambda kv: -len(kv[1]))]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=390,
                     column_config={"Who": st.column_config.TextColumn(width="large")})
    with b:
        st.subheader("Connections worth facilitating")
        ui.hypothesis_notice()
        hyps = list(s.scalars(select(CollaborationHypothesis).order_by(CollaborationHypothesis.score.desc()).limit(60)))
        seen, shown = set(), 0
        for h in hyps:
            key = (h.concept_id, frozenset(h.participating_companies))
            if h.concept_id in {k[0] for k in seen} or shown >= 5:
                continue
            seen.add(key)
            shown += 1
            st.markdown(f'<div class="nx-card">{ui.badge("HYPOTHESIS")}<span class="nx-meta">score {h.score:.0f} - {h.kind}</span>'
                        f'<h4>{ui.esc(h.title)}</h4><p>{ui.esc(" + ".join(names[i] for i in h.participating_companies))}</p>'
                        + (f'<p class="nx-meta">Missing: {ui.esc(", ".join(h.missing_capabilities))}</p>' if h.missing_capabilities else "")
                        + '</div>', unsafe_allow_html=True)
        st.caption("Suggested staff action: check interest with each company separately before any introduction.")

    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("Profiles that need attention")
        rows = []
        for c in comps:
            mine = [x for x in claims if x.company_id == c.id]
            gaps = company_agent.missing_information(c, mine)
            n_caps = len({x.capability.key for x in mine if x.claim_category == "capability" and x.capability})
            rows.append({"Company": c.name, "Capabilities": n_caps, "Depth": c.profile_depth, "Open gaps": len(gaps),
                         "Refined by company": "yes" if any(x.classification == "USER" for x in mine) or c.user_description else "no",
                         "Last updated": c.updated_at.strftime("%Y-%m-%d")})
        df = pd.DataFrame(rows).sort_values(["Capabilities", "Open gaps"], ascending=[True, False])
        st.dataframe(df, hide_index=True, width="stretch", height=360)
        st.caption(f"{sum(1 for r in rows if r['Capabilities'] == 0)} of {len(rows)} members have no confirmed capability: "
                   "their public text is too general for the taxonomy, so a short conversation or the member's own refinement is needed.")
    with b:
        st.subheader("Member developments in the news")
        news = [n for n in s.scalars(select(NewsUpdate).order_by(NewsUpdate.published_at.desc())) if n.mentioned_company_ids]
        for n in news[:6]:
            st.markdown(f'<div class="nx-card"><span class="nx-meta">{n.published_at:%Y-%m-%d} - {ui.esc(n.source_name)} - names '
                        f'{ui.esc(", ".join(names[i] for i in n.mentioned_company_ids if i in names))}</span>'
                        f'<p style="color:#e6edf7">{ui.esc(n.title)}</p><p>{ui.esc((n.summary or "")[:240])}</p>'
                        f'<p class="nx-meta">{ui.link(n.source_url)}</p></div>', unsafe_allow_html=True)
        if not news:
            st.info("No retrieved news item names a member company.")
        fb = privacy.aggregate_feedback(s)
        st.caption(f"Feedback collected in the app: {fb['n']} hypothesis ratings"
                   + (f", mean {fb['mean']} of 5" if fb["n"] else "") + " (anonymous aggregate).")
