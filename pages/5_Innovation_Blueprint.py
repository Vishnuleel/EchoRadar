"""Page 5 - Innovation Blueprint: one hypothesis turned into an evidence-linked brief."""
import streamlit as st
from sqlalchemy import select

from nexus import pipeline, ui
from nexus.core import blueprint_generator as bg
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis
from nexus.security import privacy

names = ui.setup("Innovation Blueprint")
ui.header("Brief", "Innovation Opportunity Blueprint",
          "Select a recommendation, or test your own combination of two or three companies.")
ids = sorted(names, key=lambda i: names[i].lower())
mode = st.radio("Start from", ["A company's recommendations", "My own combination"], horizontal=True,
                label_visibility="collapsed")

with ui.db() as s:
    hyp, note = None, ""
    if mode == "A company's recommendations":
        default = st.session_state.get("acting_company") or st.session_state.get("dna_company") or ids[0]
        a, b = st.columns([1, 2])
        cid = a.selectbox("Company", ids, index=ids.index(default) if default in ids else 0, format_func=lambda i: names[i])
        recs = repo.recommendations(s, cid, 12, "owner" if st.session_state.get("acting_company") == cid else "public")
        if not recs:
            st.info("No recommendation exists for this company: it has no evidence-backed capability with a known "
                    "complementary relationship. Add a capability or interest on the Company DNA page.")
            st.stop()
        keys = [r.hypothesis.key for r in recs]
        pre = st.session_state.get("bp_key")
        if pre and pre not in keys:
            extra = s.scalar(repo.public_hypotheses(s).where(CollaborationHypothesis.key == pre))
            if extra and cid in extra.participating_companies:
                keys.append(pre)
        by_key = {r.hypothesis.key: r.hypothesis for r in recs}
        pick = b.selectbox("Recommendation", keys, index=keys.index(pre) if pre in keys else 0,
                           format_func=lambda k: (lambda h: f"{h.score:.0f} - {h.title} - with " + " + ".join(
                               names[i] for i in h.participating_companies if i != cid))(
                               by_key.get(k) or s.scalar(select(CollaborationHypothesis).where(CollaborationHypothesis.key == k))))
        hyp = by_key.get(pick) or s.scalar(select(CollaborationHypothesis).where(CollaborationHypothesis.key == pick))
    else:
        chosen = st.multiselect("Companies (two or three)", ids, format_func=lambda i: names[i], max_selections=3)
        if len(chosen) >= 2:
            with st.spinner("Running the matching engine, ranking and verification for this combination..."):
                hyp, note = pipeline.adhoc_hypothesis(s, chosen, ui.embedder())
            if hyp is None:
                st.warning(note)
                st.caption("NEXUS does not write a blueprint when it cannot support the combination with evidence.")
                st.stop()
        else:
            st.stop()

    bp = bg.build_blueprint(s, hyp)
    st.markdown(f'<div class="nx-notice"><b>{ui.esc(bp["disclaimer"])}</b></div>', unsafe_allow_html=True)
    if note:
        st.caption(note)
    top = st.columns([3, 2], gap="large")
    with top[0]:
        st.markdown(f'{ui.badge("HYPOTHESIS")}<span class="nx-meta">1. Proposed innovation</span>', unsafe_allow_html=True)
        st.header(bp["title"])
        st.write(bp["proposed_application"]["text"])
        st.markdown(f'{ui.badge("HYPOTHESIS")}<span class="nx-meta">2. Problem being addressed</span>', unsafe_allow_html=True)
        st.write(bp["problem"]["text"])
    with top[1]:
        sc = bp["score"]
        st.markdown(f'<div class="nx-card"><div class="nx-score">{sc["final"]:.0f}<span class="nx-meta"> /100 - data coverage '
                    f'{sc["coverage"] * 100:.0f}%</span></div>{ui.score_bars(sc)}'
                    f'<p class="nx-meta">S = 0.35 C + 0.25 O + 0.20 R + 0.20 E. Strength of fit and evidence, not '
                    f'probability of commercial success.</p></div>', unsafe_allow_html=True)
        v = bp["verification"]
        st.caption(f"Verification Agent: {v['status'].replace('_', ' ')} - {v['checks']['claims_with_source']} of "
                   f"{v['checks']['claims_used']} capability claims have a public source.")
        md = bg.to_markdown(bp)
        d1, d2 = st.columns(2)
        d1.download_button("Download Markdown", md, file_name="nexus_blueprint.md", mime="text/markdown", width="stretch")
        try:
            d2.download_button("Download PDF", bg.to_pdf(bp), file_name="nexus_blueprint.pdf", mime="application/pdf",
                               width="stretch")
        except Exception as exc:  # PDF library problem must not break the page
            d2.caption(f"PDF export unavailable: {exc}")

    st.divider()
    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("3. Capability areas and 4. companies")
        for area in bp["capability_areas"]:
            st.markdown(f'<div class="nx-card">{ui.badge("FACT")}<span class="nx-meta">{ui.esc(area["slot"])}</span>'
                        f'<h4>{ui.esc(area["capability"])}</h4><p>{ui.esc(area["company"])}</p></div>', unsafe_allow_html=True)
        if bp["missing_capabilities"]:
            st.markdown('<div class="nx-card">' + ui.badge("HYPOTHESIS", "MISSING") + "<h4>Not covered by these companies</h4><p>"
                        + ui.esc(", ".join(bp["missing_capabilities"])) + "</p></div>", unsafe_allow_html=True)
        for c in bp["companies"]:
            st.markdown(f'<p class="nx-meta"><b>{ui.esc(c["name"])}</b> - {ui.link(c["directory_url"], "member directory")} '
                        f'{ui.link(c["website"], "website") if c["website"] else ""}</p>', unsafe_allow_html=True)
    with b:
        st.subheader("5. Why they complement each other")
        for c in bp["complementarity"][:5]:
            ev = "".join(f'<div class="nx-quote">{ui.badge("FACT" if e["basis"] == "SOURCED" else "USER")}'
                         f'{ui.esc(e["company"])} - {ui.esc(e["capability"])}: "{ui.esc(e["excerpt"][:230])}" '
                         + " ".join(ui.link(u) for u in e["urls"][:2]) + "</div>" for e in c["evidence"])
            st.markdown(f'<div class="nx-card">{ui.badge("HYPOTHESIS")}<span class="nx-meta">relationship strength '
                        f'{c["strength"]:.2f} - {ui.esc(c["kind"].replace("_", " "))}</span><p style="color:#e6edf7">{ui.esc(c["text"])}</p>{ev}</div>',
                        unsafe_allow_html=True)

    a, b, c = st.columns(3, gap="large")
    with a:
        st.subheader("6. Relevant research")
        for r in bp["research"]:
            st.markdown(f'<div class="nx-card">{ui.badge("SOURCED", "OPENALEX")}<span class="nx-meta">{r["date"]} - relevance {r["relevance"]:.0f}</span>'
                        f'<p style="color:#e6edf7">{ui.esc(r["title"][:140])}</p><p class="nx-meta">{ui.esc(r["authors"])}</p>'
                        f'<p class="nx-meta">{ui.link(r["url"])}</p></div>', unsafe_allow_html=True)
        if not bp["research"]:
            st.info("No clearly relevant research record was retrieved.")
    with b:
        st.subheader("7. Potential funding")
        for f in bp["funding"]:
            st.markdown(f'<div class="nx-card">{ui.badge(f["status"])}<span class="nx-meta">deadline {f["deadline"]} - relevance {f["relevance"]:.0f}</span>'
                        f'<p style="color:#e6edf7">{ui.esc(f["title"][:140])}</p>'
                        + (f'<p><b>Who can apply (Vinnova):</b> {ui.esc(f["eligibility"][:260])}</p>' if f["eligibility"] else "")
                        + f'<p class="nx-meta">{ui.esc(f["note"])} {ui.link(f["url"])}</p></div>', unsafe_allow_html=True)
        if not bp["funding"]:
            st.info("No currently open or upcoming call was clearly relevant.")
    with c:
        st.subheader("8. Test possibilities")
        for t in bp["testbeds"]:
            st.markdown(f'<div class="nx-card">{ui.badge("SOURCED", t["kind"].upper())}<p style="color:#e6edf7">{ui.esc(t["name"][:120])}</p>'
                        f'<div class="nx-quote">"{ui.esc(t["description"][:240])}"</div>'
                        f'<p class="nx-meta">{ui.esc(t["note"])} {ui.link(t["url"])}</p></div>', unsafe_allow_html=True)
        if not bp["testbeds"]:
            st.info("No test environment matched.")

    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("9. First prototype experiment")
        st.markdown(f'<div class="nx-card">{ui.badge("HYPOTHESIS")}<p style="color:#e6edf7">{ui.esc(bp["first_experiment"]["text"])}</p></div>',
                    unsafe_allow_html=True)
        st.subheader("10. Technical requirements")
        st.markdown("\n".join(f"- {r['text']}" for r in bp["technical_requirements"]))
        st.subheader("13. Suggested next steps")
        st.markdown("\n".join(f"{i}. {x}" for i, x in enumerate(bp["next_steps"], 1)))
    with b:
        st.subheader("11. Risks and unknowns")
        st.markdown("\n".join(f"- {r['text']}" for r in bp["risks"]))
        st.subheader("12. Sources")
        st.markdown("\n".join(f"- [{x['label']}]({x['url']})" + (f" - retrieved {x['retrieved_at']:%Y-%m-%d}" if x.get("retrieved_at") else "")
                              for x in bp["sources"]))

    st.divider()
    st.subheader("Was this useful?")
    acting = st.session_state.get("acting_company")
    if acting is None:
        st.caption("Select the company you are acting as (sidebar) to rate this hypothesis. Ratings are private to your company; "
                   "only the anonymous average is shown on the Evaluation page.")
    else:
        with st.form("fb"):
            rating = st.slider("Relevance for your company (1 = not relevant, 5 = very relevant)", 1, 5, 3)
            comment = st.text_input("Comment (optional, private)")
            if st.form_submit_button("Save rating"):
                privacy.add_feedback(s, acting, hyp.key, rating, comment)
                s.commit()
                st.success("Rating saved.")
