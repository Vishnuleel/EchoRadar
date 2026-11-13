"""Page 2 - Company DNA: evidence-backed profile, review and refinement."""
import pandas as pd
import streamlit as st

from nexus import pipeline, ui
from nexus.agents import company_agent
from nexus.core import radar
from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import Company
from nexus.security import privacy

names = ui.setup("Company DNA")
ui.header("Profile", "Company DNA", "What public sources say about a company, what NEXUS infers, and what the company has added.")

ids = sorted(names, key=lambda i: names[i].lower())
default = st.session_state.get("acting_company") or st.session_state.get("dna_company") or ids[0]
cid = st.selectbox("Company (type to search)", ids, index=ids.index(default) if default in ids else 0,
                   format_func=lambda i: names[i])
st.session_state["dna_company"] = cid
acting = st.session_state.get("acting_company")
can_edit = acting == cid


def claim_card(cl, show_toggle=False):
    ev = cl.evidence
    b = ui.badge(cl.classification)
    conf = f'confidence {cl.confidence:.2f}'
    status = (ev.verification_status if ev else "unsupported").replace("_", " ")
    when = f"retrieved {ev.retrieved_at:%Y-%m-%d %H:%M} UTC" if ev and ev.retrieved_at else "no retrieval date"
    head = cl.capability.name if (cl.capability and cl.claim_category == "capability" and cl.classification == "FACT") else cl.claim_text
    quote = f'<div class="nx-quote">"{ui.esc(ev.evidence_text[:420])}"</div>' if ev and cl.classification != "INFERENCE" else \
        (f'<p>{ui.esc(ev.evidence_text.split(" Domain key:")[0])}</p>' if ev else "")
    src = ui.link(ev.source_url) if ev else ""
    st.markdown(f'<div class="nx-card">{b}<span class="nx-meta">{conf} - {ui.esc(status)} - {when}</span>'
                f'<h4>{ui.esc(head)}</h4>{quote}<p class="nx-meta">{src}</p></div>', unsafe_allow_html=True)


with ui.db() as s:
    c = s.get(Company, cid)
    claims = repo.claims(s, cid, active_only=False)
    active = [x for x in claims if x.active]
    facts = [x for x in active if x.classification == "FACT"]
    caps = [x for x in facts if x.claim_category == "capability"]
    inferred = [x for x in active if x.classification == "INFERENCE"]
    user = [x for x in active if x.classification == "USER"]

    top = st.columns([3, 2], gap="large")
    with top[0]:
        st.subheader(c.name)
        st.markdown(f'{ui.badge("FACT")}<span class="nx-meta">from the Blue Science Park member directory - '
                    f'{ui.link(c.directory_url, "directory entry")}</span>', unsafe_allow_html=True)
        st.write(c.description or "No public description found.")
        if c.user_description:
            st.markdown(f'{ui.badge("USER")}<span class="nx-meta">company refinement (not independently verified)</span>',
                        unsafe_allow_html=True)
            st.write(c.user_description)
    with top[1]:
        ui.tiles([(len({x.capability.key for x in caps if x.capability}), "Capabilities", "with public source"),
                  (len(inferred), "Inferred interests", "derived, not stated"),
                  (len(user), "User refinements", "unverified")])
        st.write("")
        st.markdown(f"**Industry** {ui.esc(c.industry or '-')}  \n**Location** {ui.esc(c.location or '-')}  \n"
                    f"**Employees** {ui.esc(c.employees or '-')} - **Founded** {ui.esc(c.founded or '-')}  \n"
                    f"**Website** {c.website or '-'}")
        gaps = company_agent.missing_information(c, claims)
        if gaps:
            with st.expander(f"Missing or uncertain information ({len(gaps)})"):
                st.markdown("\n".join(f"- {g}" for g in gaps))
                st.caption("Gaps are stated, not filled in. The company can add what is missing under 'Review and refine'.")
        depth = "member directory + official website" if c.profile_depth == "website" else "member directory only"
        st.caption(f"Profile depth: {depth}. Last updated {c.updated_at:%Y-%m-%d %H:%M} UTC.")

    t_fact, t_inf, t_edit, t_rec, t_hist = st.tabs(
        [f"Verified facts ({len(facts)})", f"Inferred interests ({len(inferred)})",
         f"Review and refine ({len(user)})", "Recommendations", "History and private data"])

    with t_fact:
        st.caption("Each fact is a statement found in a public source. The quoted sentence is the evidence.")
        by_cap = {}
        for x in caps:
            by_cap.setdefault(x.capability.key if x.capability else "?", []).append(x)
        if by_cap:
            st.markdown("**Technology capabilities**")
            cols = st.columns(2, gap="medium")
            for i, (key, rows) in enumerate(by_cap.items()):
                with cols[i % 2]:
                    with st.expander(f"{tx.CAPABILITIES[key].name}  -  {len(rows)} source(s), confidence {rows[0].confidence:.2f}", expanded=i < 2):
                        st.caption(tx.ROLES[tx.CAPABILITIES[key].role])
                        for r in rows:
                            claim_card(r)
        else:
            st.info("No capability could be confirmed from public text. NEXUS does not guess from the company name.")
        other = [x for x in facts if x.claim_category != "capability"]
        if other:
            st.markdown("**Description, industry, geography, markets, collaborations and development activities**")
            for x in other:
                claim_card(x)

    with t_inf:
        st.caption("Interests are inferred from the evidenced capabilities. They are never presented as facts and "
                   "are not used as evidence in rankings.")
        for x in inferred:
            claim_card(x)
        if not inferred:
            st.info("Nothing inferred: there are too few evidenced capabilities.")

    with t_edit:
        if not can_edit:
            st.info(f"Select **{c.name}** under 'Acting as' in the sidebar to refine this profile. "
                    "Public facts stay visible to everyone; refinements are attributed to the company.")
        else:
            st.caption("Your changes are stored as refinements next to the public information. Nothing public is overwritten.")
            before = [r.hypothesis.key for r in repo.recommendations(s, cid, 5)]
            radar_before = [(i["kind"], i["title"][:60]) for i in radar.company_items(s, cid)[:5]]
            with st.form("refine"):
                desc = st.text_area("Company description (your wording)", value=c.user_description or "", height=80,
                                    placeholder=c.description or "")
                needs = st.multiselect("What do you need most right now? (re-ranks your radar)", list(company_agent.NEED_AREAS),
                                       default=[x for x in (c.need_priorities or []) if x in company_agent.NEED_AREAS],
                                       format_func=company_agent.NEED_AREAS.get)
                prio = st.multiselect("Priority application areas (boosts partner matching in these areas)", list(tx.DOMAINS),
                                      default=[d for d in (c.priority_domains or []) if d in tx.DOMAINS],
                                      format_func=lambda d: tx.DOMAINS[d])
                c1, c2 = st.columns(2)
                new_interest = c1.text_input("Add an interest (something you are looking for)",
                                             placeholder="e.g. machine learning for sonar data")
                new_cap = c2.text_input("Add a capability (something you can offer)", placeholder="e.g. ROV inspection")
                st.markdown("**Keep or remove existing claims** (removed claims are hidden and ignored, not deleted)")
                toggles = {}
                for x in [k for k in claims if k.claim_category in ("capability", "interest")]:
                    label = f"[{x.classification}] " + (x.capability.name + ": " if x.capability and x.classification != "USER" else "") + x.claim_text[:70]
                    toggles[x.id] = st.checkbox(label, value=x.active, key=f"claim_{x.id}")
                save = st.form_submit_button("Save profile and recalculate recommendations", type="primary")
            if save:
                changes = []
                if (desc or None) != c.user_description:
                    c.user_description = desc.strip() or None
                    changes.append("description refined")
                if list(needs) != list(c.need_priorities or []):
                    c.need_priorities = list(needs)
                    changes.append("current needs: " + (", ".join(company_agent.NEED_AREAS[x] for x in needs) or "none"))
                if list(prio) != list(c.priority_domains or []):
                    c.priority_domains = list(prio)
                    changes.append("priorities: " + (", ".join(tx.DOMAINS[d] for d in prio) or "none"))
                for text, cat in ((new_interest, "interest"), (new_cap, "capability")):
                    if text.strip():
                        rows = company_agent.add_user_claim(s, c, text, cat, ui.embedder())
                        mapped = ", ".join(r.capability.name for r in rows if r.capability) or "no taxonomy match"
                        changes.append(f"added {cat} '{text.strip()}' ({mapped})")
                for claim_id, keep in toggles.items():
                    row = next(k for k in claims if k.id == claim_id)
                    if row.active != keep:
                        company_agent.set_claim_active(s, claim_id, keep)
                        changes.append(("restored: " if keep else "removed: ") + row.claim_text[:50])
                if changes:
                    repo.add_revision(s, c, "; ".join(changes), author=c.name)
                    s.commit()
                    with st.spinner("Combination, Ranking and Verification agents are recalculating..."):
                        trace = pipeline.recompute(s, ui.embedder())
                        pipeline.save_trace(trace, ui.embedder().backend)
                    after = [r.hypothesis.key for r in repo.recommendations(s, cid, 5)]
                    radar_after = [(i["kind"], i["title"][:60]) for i in radar.company_items(s, cid)[:5]]
                    st.session_state["dna_diff"] = {"company": cid, "changes": changes, "before": before, "after": after,
                                                    "radar_before": radar_before, "radar_after": radar_after}
                    st.rerun()
                else:
                    st.info("No changes to save.")
        diff = st.session_state.get("dna_diff")
        if diff and diff["company"] == cid:
            moved = len(set(diff["after"]) - set(diff["before"]))
            st.success("Saved: " + "; ".join(diff["changes"]))
            st.caption(f"Partner recommendations, top 5: {moved} new entr{'y' if moved == 1 else 'ies'} after recalculation"
                       + ("" if diff["before"] != diff["after"] else " (order and content unchanged)") + ".")
            if diff.get("radar_before") != diff.get("radar_after"):
                b1, b2 = st.columns(2)
                b1.markdown("**Radar top 5 before**\n" + "\n".join(f"{i}. {k}: {t}" for i, (k, t) in enumerate(diff["radar_before"], 1)))
                b2.markdown("**Radar top 5 after**\n" + "\n".join(f"{i}. {k}: {t}" for i, (k, t) in enumerate(diff["radar_after"], 1)))
            else:
                st.caption("Radar top 5 unchanged by this edit.")
        if user:
            st.markdown("**Current refinements**")
            for x in user:
                claim_card(x)

    with t_rec:
        ui.hypothesis_notice()
        recs = repo.recommendations(s, cid, 8)
        if not recs:
            st.info("No recommendation: this company has no evidence-backed capability with a known complementary relationship.")
        for r in recs:
            h = r.hypothesis
            partners = " + ".join(names[i] for i in h.participating_companies if i != cid)
            with st.container(border=True):
                a, b = st.columns([3, 2])
                a.markdown(f'{ui.badge("HYPOTHESIS")}<span class="nx-meta">#{r.rank} - {h.kind}</span>'
                           f'<h4 style="margin:.3rem 0">{ui.esc(h.title)}</h4><b>with {ui.esc(partners)}</b>',
                           unsafe_allow_html=True)
                a.caption(r.explanation)
                b.markdown(f'<div class="nx-score">{r.score:.0f}<span class="nx-meta"> /100 - data coverage '
                           f'{r.score_breakdown["coverage"] * 100:.0f}%</span></div>' + ui.score_bars(r.score_breakdown),
                           unsafe_allow_html=True)
        st.caption("Scores express strength of fit and evidence, not probability of commercial success. "
                   "Open the Innovation Blueprint page for the full brief.")

    with t_hist:
        revs = sorted(c.revisions, key=lambda r: r.created_at, reverse=True)
        st.markdown("**Profile revisions** (public information vs. company refinements)")
        if revs:
            st.dataframe(pd.DataFrame([{"When (UTC)": r.created_at.strftime("%Y-%m-%d %H:%M"), "By": r.author,
                                        "Change": r.change_summary} for r in revs]), hide_index=True, width="stretch")
        else:
            st.caption("No refinements yet: the profile shows only what public sources state.")
        st.markdown("**Private interactions**")
        try:
            rows = privacy.get_private_interactions(s, acting, cid)
            fb = privacy.get_feedback(s, acting, cid)
            st.caption(f"Visible only to {c.name}: {len(rows)} questions asked, {len(fb)} feedback entries.")
            if rows:
                st.dataframe(pd.DataFrame([{"When (UTC)": r.created_at.strftime("%Y-%m-%d %H:%M"), "Type": r.kind,
                                            "Text": r.text[:120], "Boundary result": r.outcome} for r in rows[:30]]),
                             hide_index=True, width="stretch")
        except privacy.PrivacyError as exc:
            st.error(str(exc))
