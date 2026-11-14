"""Shared Streamlit helpers: styling, sidebar, cards and cached resources.

All external text is HTML-escaped before it is placed in markup: retrieved web content is
untrusted data and must never be able to inject markup or script into the interface.
"""
from __future__ import annotations

import html
from contextlib import contextmanager

import streamlit as st

from nexus.core.scoring import LABELS
from nexus.database import repository as repo
from nexus.database.database import get_sessionmaker

CSS = """
<style>
:root { --bg:#0b1220; --panel:#111b2e; --panel2:#16233a; --line:#22324d; --ink:#e6edf7; --ink2:#a9b6cb;
        --muted:#7f8ea8; --blue:#3987e5; --cyan:#35c3e0; --good:#199e70; --warn:#c98500; --hyp:#d95926; }
.block-container { padding-top: 3.6rem; max-width: 1280px; }
h1, h2, h3 { letter-spacing: -0.01em; }
[data-testid="stSidebar"] { background: #0d1626; border-right: 1px solid var(--line); }
.nx-hero { padding: 26px 30px; border: 1px solid var(--line); border-radius: 14px;
           background: linear-gradient(135deg, #10203b 0%, #0d1626 70%); margin-bottom: 18px; }
.nx-hero h1 { margin: 0 0 6px 0; font-size: 2.0rem; }
.nx-hero p { margin: 0; color: var(--ink2); font-size: 1.02rem; }
.nx-eyebrow { color: var(--cyan); font-size: .74rem; letter-spacing: .14em; text-transform: uppercase; font-weight: 600; }
.nx-card { border: 1px solid var(--line); background: var(--panel); border-radius: 12px; padding: 16px 18px; margin-bottom: 12px; }
.nx-card h4 { margin: 0 0 6px 0; font-size: 1.02rem; line-height: 1.35; }
.nx-card p { margin: 4px 0; color: var(--ink2); font-size: .9rem; line-height: 1.5; }
.nx-card a { color: #6fb0ff; text-decoration: none; } .nx-card a:hover { text-decoration: underline; }
.nx-meta { color: var(--muted); font-size: .8rem; }
.nx-tile { border: 1px solid var(--line); background: var(--panel); border-radius: 12px; padding: 14px 16px; height: 100%; }
.nx-tile .v { font-size: 1.9rem; font-weight: 650; line-height: 1.1; font-variant-numeric: tabular-nums; }
.nx-tile .l { color: var(--ink2); font-size: .82rem; margin-top: 4px; }
.nx-tile .s { color: var(--muted); font-size: .74rem; margin-top: 2px; }
.nx-badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .7rem; font-weight: 650;
            letter-spacing: .04em; border: 1px solid; margin-right: 6px; vertical-align: middle; white-space: nowrap; }
.b-fact { color: #5fd0a4; border-color: #1f6f55; background: #0f2a24; }
.b-inf { color: #f0b54a; border-color: #7a5a14; background: #2b2210; }
.b-user { color: #b9b0ff; border-color: #4c4590; background: #1d1b3a; }
.b-hyp { color: #ff9b72; border-color: #8a3d1c; background: #2e1a12; }
.b-src { color: #8fc1ff; border-color: #27508a; background: #10223c; }
.b-open { color: #5fd0a4; border-color: #1f6f55; background: #0f2a24; }
.b-upcoming { color: #8fc1ff; border-color: #27508a; background: #10223c; }
.b-closed, .b-unknown { color: #a9b6cb; border-color: #3a4a66; background: #152033; }
.nx-quote { border-left: 3px solid #2a4f86; padding: 4px 0 4px 12px; margin: 8px 0; color: #c9d5e8; font-size: .88rem; font-style: italic; }
.nx-bar { display: grid; grid-template-columns: 190px 1fr 46px; gap: 10px; align-items: center; margin: 5px 0; font-size: .84rem; }
.nx-bar .t { color: var(--ink2); } .nx-bar .n { text-align: right; font-variant-numeric: tabular-nums; color: var(--ink); }
.nx-track { background: #1a2740; border-radius: 4px; height: 8px; overflow: hidden; }
.nx-fill { background: var(--blue); height: 8px; border-radius: 4px; }
.nx-notice { border: 1px solid #8a3d1c; background: #24160f; color: #ffc2a6; border-radius: 10px; padding: 10px 14px; font-size: .88rem; margin: 8px 0 14px 0; }
.nx-sim { border: 1px dashed #7a5a14; background: #221b0c; color: #f0c779; border-radius: 10px; padding: 8px 12px; font-size: .82rem; margin: 6px 0; }
.nx-score { font-size: 1.7rem; font-weight: 650; font-variant-numeric: tabular-nums; }
.nx-step { display:flex; gap:10px; align-items:flex-start; margin: 6px 0; font-size:.9rem; color: var(--ink2); }
.nx-step b { color: var(--ink); } .nx-step .i { color: var(--cyan); font-weight: 700; min-width: 20px; }
</style>
"""


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


@st.cache_resource(show_spinner="Loading embedding model...")
def embedder():
    from nexus.core.embeddings import get_embedder

    return get_embedder()


@contextmanager
def db():
    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


def setup(title: str):
    try:
        st.set_page_config(page_title=f"EchoRadar - {title}", page_icon=":material/hub:", layout="wide")
    except Exception:  # already configured by the router
        pass
    st.markdown(CSS, unsafe_allow_html=True)
    with db() as s:
        comps = repo.companies(s)
    names = {c.id: c.name for c in comps}
    with st.sidebar:
        st.markdown("### EchoRadar")
        st.caption("The Innovation Connection Engine - Blue Science Park prototype")
        options = [None] + [c.id for c in comps]
        current = st.session_state.get("acting_company")
        choice = st.selectbox("Acting as (simulated sign-in)", options,
                              index=options.index(current) if current in options else 0,
                              format_func=lambda i: "Visitor (public view)" if i is None else names[i],
                              help="Private notes, questions and feedback are scoped to this company.")
        st.session_state["acting_company"] = choice
        st.markdown('<div class="nx-sim">SIMULATED: sign-in is a selector in this prototype. '
                    'The authorisation checks behind it are real.</div>', unsafe_allow_html=True)
        st.divider()
        st.caption("Labels used everywhere")
        st.markdown(badge("FACT") + " public source<br>" + badge("INFERENCE") + " derived by EchoRadar<br>"
                    + badge("USER") + " entered by a user<br>" + badge("HYPOTHESIS") + " generated proposal",
                    unsafe_allow_html=True)
    if not comps:
        st.warning("The database is empty. Run `python scripts/ingest.py` to retrieve public data first.")
        st.stop()
    st.session_state.setdefault("dna_company", next((c.id for c in comps if c.slug == "njord-x"), comps[0].id))
    return names


def badge(kind: str, text: str | None = None) -> str:
    cls = {"FACT": "b-fact", "INFERENCE": "b-inf", "USER": "b-user", "HYPOTHESIS": "b-hyp", "SOURCED": "b-src",
           "open": "b-open", "upcoming": "b-upcoming", "closed": "b-closed", "unknown": "b-unknown"}.get(kind, "b-src")
    return f'<span class="nx-badge {cls}">{esc(text or kind)}</span>'


def tile(value, label, sub: str = "") -> str:
    return (f'<div class="nx-tile"><div class="v">{esc(value)}</div><div class="l">{esc(label)}</div>'
            f'<div class="s">{esc(sub)}</div></div>')


def tiles(items: list[tuple]):
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        col.markdown(tile(*item), unsafe_allow_html=True)


def score_bars(breakdown: dict) -> str:
    rows = []
    for key, label in LABELS.items():
        v = breakdown.get(key)
        w = breakdown.get("weights", {}).get(key, 0)
        width = 0 if v is None else max(0, min(100, v))
        num = "n/a" if v is None else f"{v:.0f}"
        rows.append(f'<div class="nx-bar"><div class="t">{esc(label)} <span class="nx-meta">x{w:.2f}</span></div>'
                    f'<div class="nx-track"><div class="nx-fill" style="width:{width}%"></div></div>'
                    f'<div class="n">{num}</div></div>')
    return "".join(rows)


def link(url: str | None, text: str = "source") -> str:
    if not url or not url.startswith(("http://", "https://")):
        return '<span class="nx-meta">no public source</span>'
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(text)} &#8599;</a>'


def hypothesis_notice():
    st.markdown('<div class="nx-notice"><b>Hypotheses, not confirmed collaborations.</b> Combinations are '
                'generated by EchoRadar from public information. No company has been contacted. Funding programmes '
                'are potentially relevant only: eligibility has not been checked.</div>', unsafe_allow_html=True)


def header(eyebrow: str, title: str, subtitle: str):
    st.markdown(f'<div class="nx-eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(subtitle)


def item_card(it: dict, key: str = "", acting: int | None = None, session=None, actions: bool = False):
    """One radar item: why it fits / what supports it / what to do next, with its uncertainty."""
    status = badge(it["status"]) if it.get("status") in ("open", "upcoming", "closed", "unknown") else \
        (badge("SOURCED", it["status"].upper()) if it.get("status") else "")
    flags = "".join(f'<span class="nx-badge b-hyp">{esc(f)}</span>' for f in it.get("flags", []))
    caps = "".join(badge("SOURCED", c) for c in it.get("matched", []))
    terms = "".join(f"<p><b>{esc(k)}:</b> {esc(v)}</p>" for k, v in it.get("terms", []))
    adj = "".join(f'<p class="nx-meta">Ranking note: {esc(a)}</p>' for a in it.get("adjustments", []))
    rel = it.get("relevance", 0)
    st.markdown(
        f'<div class="nx-card">{badge("SOURCED", it["area"].upper())}{status}{flags}'
        f'<span class="nx-meta">{esc(it["source"])} - {esc(it["date_label"])}</span>'
        f'<h4>{esc(it["title"][:150])}</h4>'
        f'<div class="nx-bar" style="grid-template-columns:90px 1fr 40px"><div class="t">Relevance</div>'
        f'<div class="nx-track"><div class="nx-fill" style="width:{rel}%"></div></div><div class="n">{rel:.0f}</div></div>'
        f'<p><b>Why it fits:</b> {esc(it.get("why", ""))} {caps}</p>'
        f'<p><b>What supports it:</b> {link(it["url"], "source record")}'
        f'{" - " + link(it["apply_url"], "application page") if it.get("apply_url") else ""}'
        f' - retrieved {it["retrieved_at"]:%Y-%m-%d}</p>'
        f'<div class="nx-quote">"{esc(it["excerpt"])}"</div>{terms}'
        f'<p><b>What to do next:</b> {esc(it.get("next_action") or "Open the source and check the details.")}</p>'
        f'<p class="nx-meta"><b>Uncertain:</b> {esc(it.get("uncertainty") or "-")}</p>{adj}</div>',
        unsafe_allow_html=True)
    if actions and session is not None:
        from nexus.core import radar

        marks = set(it.get("marks", []))
        c1, c2, c3, _ = st.columns([1, 1, 1.2, 3])
        if acting is None:
            c1.caption("Sign in (sidebar) to save or rate.")
            return
        for col, action, label in ((c1, "saved", "Saved" if "saved" in marks else "Save"),
                                   (c2, "useful", "Useful (marked)" if "useful" in marks else "Useful"),
                                   (c3, "not_useful", "Not useful")):
            if col.button(label, key=f"{key}_{action}_{it['kind']}_{it['ref_id']}", width="stretch",
                          type="primary" if action in marks else "secondary"):
                radar.mark(session, acting, it["kind"], it["ref_id"], action, on=action not in marks)
                session.commit()
                st.session_state["radar_dirty"] = True
                st.rerun()
