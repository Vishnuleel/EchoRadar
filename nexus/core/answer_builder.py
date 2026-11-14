"""Ask NEXUS answers, one builder per kind of question (see nexus.core.question_router).

Everything shown comes from stored records or from the fixed sentences in this file. Records keep
their source links; counts are counted, not estimated; what NEXUS does not store is said plainly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.agents.opportunity_agent import current_status
from nexus.core import matching_engine as me
from nexus.core import radar
from nexus.core import taxonomy as tx
from nexus.core.question_router import KNOWN_ALIASES, CompanyIndex, Route, parse_window
from nexus.database import repository as repo
from nexus.database.models import (OWNER, PUBLIC, CollaborationHypothesis, Company, Event, FundingOpportunity, NewsUpdate,
                                   ResearchPublication, Testbed)
from nexus.integrations.bsp_sources import BSP, CONTACT_EMAIL_PUBLIC, CONTACT_URL

FLOOR = 25.0  # minimum relevance for a record to be offered as a match
KIND_LABEL = {"funding": "funding calls", "event": "events", "testbed": "test environments", "research": "research records",
              "news": "news articles"}
SUGGESTIONS = ["Which funding calls close in the next 30 days?", "Events next month", "Which members work with cybersecurity?",
               "What does Njord X do?", "We develop sensors and need somewhere to test them", "How can I contact Blue Science Park?"]

HELP = {
    "general": ("What you can ask", None,
                "Ask about funding, test environments, events, research and news, about a member company, or about who could "
                "work on something. You can name a period, such as next month, and compare two members. Answers are put "
                "together from stored, sourced records."),
    "front": ("This week", "/", "The front page: the findings of the week that fit the company you read as best, and the "
                                "strongest partner proposals."),
    "radar": ("Opportunity Radar", "/radar", "Funding, test environments, events, research and regional news, ranked for one "
                                             "company. Each item says why it fits, where it comes from and what to do next."),
    "dna": ("Company profile", "/dna", "What public sources say about a company, what NEXUS infers from that, and what the "
                                       "company has added itself. Every fact links to the page it was copied from."),
    "blueprint": ("Innovation Blueprint", "/blueprint", "A proposed collaboration between two or three members: what each one "
                                                        "brings, the evidence, the score and what is still missing. A proposal, "
                                                        "not an agreement."),
    "graph": ("Connections graph", "/graph", "Members, their capabilities and the proposed connections between them, drawn as "
                                             "a network."),
    "staff": ("Staff desk", "/staff", "For Blue Science Park staff: shared interests across members, connections worth "
                                      "facilitating, and where profiles need attention."),
    "overview": ("Overview", "/overview", "Counts for the whole ecosystem, from stored records: capabilities, funding calls, "
                                          "research and the strongest proposals."),
    "ask": ("Ask NEXUS", "/ask", "Questions in, sourced records out. A boundary check comes first, and no language model writes "
                                 "the answers."),
    "FACT": ("The FACT label", None, "A statement found in a public source. The quoted sentence is the evidence."),
    "INFERENCE": ("The INFERENCE label", None, "Derived by NEXUS from evidenced facts, for example a likely interest. Never "
                                               "presented as a fact and never used as evidence in rankings."),
    "USER": ("The USER label", None, "Added by the company itself. Not independently verified."),
    "HYPOTHESIS": ("The HYPOTHESIS label", None, "A collaboration NEXUS proposes from public information. No company has been "
                                                 "contacted and nothing has been agreed."),
}


def card(kind: str, title: str, text: str | None = None, **extra) -> dict:
    return {"kind": kind, "title": title, "text": text, "rows": [], "quotes": [], "links": [], "note": None, **extra}


def company_index(s: Session) -> CompanyIndex:
    return CompanyIndex.build([(c.id, c.name, list(c.aliases or []) + KNOWN_ALIASES.get(c.slug, []))
                               for c in repo.companies(s)])


def _contact_rows() -> list[dict]:
    return [{"label": "Contact page", "value": CONTACT_URL.replace("https://", ""), "url": CONTACT_URL},
            {"label": "Email", "value": CONTACT_EMAIL_PUBLIC, "url": f"mailto:{CONTACT_EMAIL_PUBLIC}"}]


_CONTACT_NOTE = ("The email address was copied from the contact page when NEXUS was set up. NEXUS does not re-check it "
                 "automatically, so the contact page is the place to confirm it.")


# ---- Blue Science Park itself -------------------------------------------------------------------
def park(s: Session, route: Route) -> dict:
    topic = route.park
    if topic == "contact":
        return card("park", "Contacting Blue Science Park", "Blue Science Park staff can be reached through the park's "
                    "contact page.", rows=_contact_rows(), note=_CONTACT_NOTE)
    if topic == "about":
        n = len(repo.companies(s))
        return card("park", "Blue Science Park", f"Blue Science Park is the science park whose public member directory NEXUS "
                    f"reads. NEXUS tracks {n} organisations listed there, with their public capabilities, and the funding, "
                    "test environments, events and research around them.",
                    rows=[{"label": "Website", "value": BSP.replace("https://", ""), "url": BSP + "/"}] + _contact_rows()[:1])
    if topic == "membership":
        return card("park", "Membership", "Membership is decided by Blue Science Park, not by NEXUS. The park's staff can tell "
                    "you how it works.", rows=_contact_rows(), note=_CONTACT_NOTE)
    what = {"location": "address", "hours": "opening hours", "staff": "staff list"}.get(topic, "details")
    return card("park", f"Blue Science Park's {what}", f"NEXUS does not store Blue Science Park's {what}, so it will not "
                "guess. The park's contact page is the place to ask.", rows=_contact_rows()[:1])


# ---- help with NEXUS ----------------------------------------------------------------------------
def help_card(route: Route) -> dict:
    title, href, text = HELP.get(route.help or "general", HELP["general"])
    c = card("help", title, text)
    if href:
        c["links"].append({"label": f"Open {title}", "href": href})
    return c


# ---- members ------------------------------------------------------------------------------------
def _fact_caps(s: Session, company_id: int) -> list:
    """The company's capability facts with evidence, one per capability, strongest first."""
    seen, out = set(), []
    for cl in sorted(repo.claims(s, company_id), key=lambda c: -c.confidence):
        if (cl.classification == "FACT" and cl.claim_category == "capability" and cl.capability and cl.evidence
                and cl.capability.key not in seen):
            seen.add(cl.capability.key)
            out.append(cl)
    return out


def company_card(s: Session, c: Company, asks_contact: bool = False) -> dict:
    caps = _fact_caps(s, c.id)
    out = card("company", c.name, c.description or "No public description was found.", company_id=c.id,
               kicker="Member profile")
    for label, value, url in (("Industry", c.industry, None), ("Location", c.location, None), ("Employees", c.employees, None),
                              ("Founded", c.founded, None), ("Website", c.website, c.website),
                              ("Directory profile", c.directory_url and "bluesciencepark.se", c.directory_url)):
        if value:
            out["rows"].append({"label": label, "value": value.replace("https://", "").replace("http://", "").rstrip("/")
                                if label == "Website" else value, "url": url})
    out["quotes"] = [{"label": cl.capability.name, "text": cl.evidence.evidence_text[:260], "url": cl.evidence.source_url}
                     for cl in caps[:4]]
    out["note"] = (f"Checked against the official directory profile on {c.last_verified_at:%Y-%m-%d}."
                   if c.last_verified_at else "Not yet checked against the official directory profile.")
    if asks_contact:
        out["notice"] = ("NEXUS stores no personal contact details. The company's website and its directory profile, linked "
                         "here, are the way to reach it.")
    if not caps:
        out["notice"] = (out.get("notice", "") + " " if out.get("notice") else "") + \
            "No capability could be confirmed from public text, so none is listed."
    out["links"] = [{"label": "Open the full profile", "href": "/dna", "company_id": c.id},
                    {"label": "Proposed partners", "href": "/blueprint", "company_id": c.id}]
    return out


def compare_card(s: Session, companies: list[Company]) -> dict:
    caps = {c.id: [cl.capability.name for cl in _fact_caps(s, c.id)] for c in companies}
    shared = sorted(set.intersection(*(set(v) for v in caps.values()))) if caps else []
    names = " and ".join(c.name for c in companies) if len(companies) == 2 else \
        ", ".join(c.name for c in companies[:-1]) + f" and {companies[-1].name}"
    text = (f"All of them have public evidence of {', '.join(shared)}." if shared and len(companies) > 2 else
            f"Both have public evidence of {', '.join(shared)}." if shared else
            "They have no capability in common in public sources. Different strengths can still complement each other.")
    return card("compare", names, text, kicker="Comparison",
                columns=[{"company_id": c.id, "name": c.name, "capabilities": caps[c.id],
                          "only": [x for x in caps[c.id] if x not in shared]} for c in companies],
                shared=shared, note="Only capabilities with a quoted public source are compared.")


def hypotheses_with(s: Session, ids: set[int], limit: int = 2) -> list[CollaborationHypothesis]:
    need = 2 if len(ids) >= 2 else 1
    out = []
    for h in s.scalars(repo.public_hypotheses(s).order_by(CollaborationHypothesis.score.desc()).limit(400)):
        if len(ids & set(h.participating_companies)) >= need:
            out.append(h)
            if len(out) == limit:
                break
    return out


# ---- records ------------------------------------------------------------------------------------
def _candidates(s: Session, kind: str, route: Route, now: datetime) -> list:
    w = route.window
    if kind == "funding":
        rows = [f for f in s.scalars(select(FundingOpportunity)) if current_status(f, now) in ("open", "upcoming")]
        if w and w.closing:
            rows = [f for f in rows if f.deadline and w.start <= f.deadline < w.end]
        elif w:
            rows = [f for f in rows if (f.opens_at is None or f.opens_at < w.end) and (f.deadline is None or f.deadline >= w.start)]
        return rows
    if kind == "event":
        rows = [e for e in s.scalars(select(Event)) if e.starts_at is None or e.starts_at >= now]
        return [e for e in rows if e.starts_at and w.start <= e.starts_at < w.end] if w else rows
    if kind == "testbed":
        return [t for t in s.scalars(select(Testbed)) if t.kind != "event"]
    model, col = (ResearchPublication, "publication_date") if kind == "research" else (NewsUpdate, "published_at")
    rows = list(s.scalars(select(model)))
    if w:
        rows = [r for r in rows if getattr(r, col) and w.period_start <= getattr(r, col) < min(w.end, now)]
    return rows


def _date_key(kind: str, d: dict, newest: bool):
    far = datetime.max
    when = d.get("sort_date")
    if kind in ("research", "news") or newest:
        return -(when.timestamp() if when else 0)
    if kind == "testbed":
        return d["title"].lower()
    return when or far


def records(s: Session, route: Route, kinds: list[str], query: str, embedder, acting: int | None, now: datetime,
            limit: int = 4) -> tuple[list[dict], str]:
    """Records of the asked kinds and period, and one sentence saying how they were chosen and ordered."""
    from nexus import pipeline  # shared item embedding helpers (imported late: pipeline imports this module)

    found: list[dict] = []
    ranked = route.has_subject
    q = embedder.encode([query], s)[0] if ranked else None
    owner = {}
    if not ranked and acting is not None:  # the company's own radar ranking, visible only to that company
        owner = {(i["kind"], i["ref_id"]): i for i in radar.company_items(s, acting, kinds, audience=OWNER, now=now)}
    per_kind: dict[str, list[dict]] = {}
    for kind in kinds:
        rows = _candidates(s, kind, route, now)
        out = []
        if ranked and rows:
            items = pipeline._item_set(s, rows, embedder)
            for d in sorted(me.bridge(q, set(route.caps), items.vectors, items.caps, embedder.is_semantic),
                            key=lambda d: -d["relevance"]):
                if d["relevance"] < FLOOR or len(out) >= limit:
                    continue
                item = radar.describe(kind, items.rows[d["index"]], now)
                if item is None:
                    continue
                names = ", ".join(tx.CAPABILITIES[c].name for c in d["shared_capabilities"][:3] if c in tx.CAPABILITIES)
                item.update(relevance=d["relevance"], matched=[], why=(f"Matches your question on {names}." if names else
                            f"Close to the wording of your question (text similarity {d['cosine']:.2f})."))
                out.append(item)
        else:
            for row in rows:
                item = owner.get((kind, row.id)) or radar.describe(kind, row, now)
                if item is None or (kind == "event" and item.get("status") == "past"):
                    continue
                if (kind, row.id) not in owner:
                    item.update(relevance=None, matched=[], why=None)
                out.append(item)
            if owner:
                out.sort(key=lambda i: (i.get("relevance") is None, -(i.get("relevance") or 0)))
            else:
                out.sort(key=lambda i: _date_key(kind, i, route.newest))
        per_kind[kind] = out
    if ranked or owner:
        found = sorted((i for v in per_kind.values() for i in v), key=lambda i: -(i.get("relevance") or 0))[:limit]
    else:  # date order: a few of each kind
        each = max(1, limit // max(1, len([k for k in kinds if per_kind.get(k)])))
        found = [i for k in kinds for i in per_kind.get(k, [])[:each]][:max(limit, each)]
    return found, _explain(route, kinds, found, ranked, bool(owner), s, now)


def _period_phrase(route: Route) -> str:
    w = route.window
    if not w:
        return ""
    plain = w.label in ("today", "tomorrow", "this week", "next week", "this month") or w.label.startswith("the rest")
    return (" closing" if w.closing else "") + (f" {w.label}" if plain else f" in {w.label}")


def _explain(route: Route, kinds: list[str], found: list[dict], ranked: bool, owner: bool, s: Session, now: datetime) -> str:
    what = " and ".join(KIND_LABEL[k] for k in kinds)
    period = _period_phrase(route)
    if not found:
        msg = f"No stored {what}{period}" + (" match the subject of your question." if ranked else ".")
        nxt = _next_after(s, kinds, route, now)
        msg += f" The next one stored is {nxt}." if nxt else ""
        undated = len([e for e in s.scalars(select(Event)) if e.starts_at is None]) if "event" in kinds and route.window else 0
        if undated:
            msg += (f" {undated} stored event{'s have' if undated != 1 else ' has'} no published date and cannot be placed in "
                    "a period; ask for upcoming events to see them.")
        return msg
    if ranked:
        return f"Stored {what}{period}, ranked by how well they fit your question."
    if owner:
        return f"Stored {what}{period}, ranked for the company you read as, by its radar."
    order = {"funding": "soonest deadline first", "event": "soonest first", "testbed": "by name",
             "research": "newest first", "news": "newest first"}
    return f"Stored {what}{period}, " + ("; ".join(order[k] for k in kinds if k in order) if not route.newest
                                         else "newest first") + "."


def _next_after(s: Session, kinds: list[str], route: Route, now: datetime) -> str | None:
    """For an empty period: the first stored event or deadline after it, so the answer is still useful."""
    w = route.window
    if not w:
        return None
    best = None
    if "event" in kinds:
        for e in s.scalars(select(Event)):
            if e.starts_at and e.starts_at >= max(w.end, now) and (best is None or e.starts_at < best[0]):
                best = (e.starts_at, f'"{e.title}" on {e.starts_at:%Y-%m-%d}')
    if "funding" in kinds:
        for f in s.scalars(select(FundingOpportunity)):
            if (current_status(f, now) in ("open", "upcoming") and f.deadline and f.deadline >= w.end
                    and (best is None or f.deadline < best[0])):
                best = (f.deadline, f'"{f.title[:80]}" with deadline {f.deadline:%Y-%m-%d}')
    return best[1] if best else None


def partners(s: Session, query: str, route: Route, embedder, limit: int = 4) -> tuple[list[dict], list]:
    """Members whose evidenced capabilities fit the question, with the quoted evidence."""
    import numpy as np

    from nexus.agents import combination_agent

    q = embedder.encode([query], s)[0]
    profiles = combination_agent.load_profiles(s, embedder)
    comp = [(p, set(p.capabilities)) for p in profiles if p.vector is not None and p.capabilities]
    out = []
    if comp:
        scored = me.bridge(q, set(route.caps), np.vstack([p.vector for p, _ in comp]), [c for _, c in comp], embedder.is_semantic)
        for d in sorted(scored, key=lambda d: -d["relevance"])[:limit]:
            if d["relevance"] >= FLOOR:
                p = comp[d["index"]][0]
                claims = [p.capabilities[c] for c in (d["shared_capabilities"] or list(p.capabilities)[:2])]
                out.append({"company_id": p.id, "name": p.name, "relevance": d["relevance"],
                            "evidence": [{"capability": c.capability, "excerpt": c.excerpt[:300],
                                          "url": c.source_urls[0] if c.source_urls else None} for c in claims[:2]]})
    hyps = []
    ids = {c["company_id"] for c in out[:3]}
    if ids and route.caps:
        q_caps = set(route.caps)
        for h in s.scalars(repo.public_hypotheses(s).order_by(CollaborationHypothesis.score.desc())):
            if ids & set(h.participating_companies) and q_caps & ({l["cap_a"] for l in h.evidence} | {l["cap_b"] for l in h.evidence}):
                hyps.append(h)
                if len(hyps) == 3:
                    break
    return out, hyps


def count_answer(s: Session, route: Route, query: str, embedder, acting: int | None, now: datetime) -> tuple[dict, list, list]:
    """(card, companies, items) for a "how many" question. Numbers are counted from stored records."""
    caps = [c for c in route.caps if c in tx.CAPABILITIES]
    if caps:
        by_company: dict[int, list] = {}
        for cl in repo.all_claims(s):
            if (cl.classification == "FACT" and cl.claim_category == "capability" and cl.capability
                    and cl.capability.key in caps and cl.evidence):
                by_company.setdefault(cl.company_id, []).append(cl)
        names = {c.id: c.name for c in repo.companies(s)}
        n = len(by_company)
        what = ", ".join(tx.CAPABILITIES[c].name for c in caps)
        rows = [{"company_id": cid, "name": names.get(cid, "?"), "relevance": None,
                 "evidence": [{"capability": cl.capability.key, "excerpt": cl.evidence.evidence_text[:300],
                               "url": cl.evidence.source_url} for cl in cls[:2]]}
                for cid, cls in sorted(by_company.items(), key=lambda kv: names.get(kv[0], ""))]
        return (card("count", f"{n} member{'s' if n != 1 else ''} {'have' if n != 1 else 'has'} public evidence of {what}",
                     "Counted from capability statements quoted from public sources. A member without such a statement is "
                     "not counted, so the real number may be higher.", number=n), rows, [])
    if route.kinds:
        allowed = [k for k in route.kinds]
        total = {k: len([r for r in _candidates(s, k, route, now)
                         if (k != "funding" or current_status(r, now) in ("open", "upcoming"))]) for k in allowed}
        n = sum(total.values())
        what = " and ".join(KIND_LABEL[k] for k in allowed)
        label = ("open or upcoming " if "funding" in allowed else "") + what
        items, _ = records(s, route, allowed, query, embedder, acting, now)
        undated = len([e for e in s.scalars(select(Event)) if e.starts_at is None]) if "event" in allowed and route.window else 0
        return (card("count", f"{n} {label}{_period_phrase(route)}",
                     "Counted from the records NEXUS has stored: " + ", ".join(f"{v} {KIND_LABEL[k]}" for k, v in total.items())
                     + "." + (f" {undated} more event{'s have' if undated != 1 else ' has'} no published date and cannot be "
                              "placed in a period." if undated else ""), number=n), [], items)
    n = len(repo.companies(s))
    return (card("count", f"NEXUS tracks {n} organisations from the Blue Science Park member directory",
                 "Name a technology to count the members with public evidence of it, for example: how many members work "
                 "with sonar?", number=n), [], [])


def apply_card() -> dict:
    return card("apply", "Applying for funding", "Each funding call has its own application page with the criteria and the "
                "deadline. NEXUS links to them but cannot check eligibility or apply for you. Blue Science Park staff can "
                "help you prepare an application.", rows=_contact_rows()[:1])


def route_from_model(sorted_reply: dict, index: CompanyIndex, now: datetime) -> Route:
    """Turn the model's fixed-list choices into a Route. Company names are mapped back to ids."""
    by_name = {v: k for k, v in index.names.items()}
    kw = sorted_reply.get("keywords") or ""
    window = parse_window(sorted_reply["period"], now) if sorted_reply.get("period") else None
    from nexus.core.question_router import content_words

    kind = sorted_reply["type"]
    r = Route(kind=kind, topics=sorted_reply.get("topics") or [], park=sorted_reply.get("park_topic"),
              companies=[by_name[n] for n in sorted_reply.get("companies") or [] if n in by_name], window=window,
              count=bool(sorted_reply.get("count")), caps=[c for c, _ in tx.detect_capabilities(kw)],
              content=content_words(kw), help=sorted_reply.get("help_topic"), source="gemini")
    # a choice whose required details are missing falls back to the closest kind that can be answered
    if r.kind == "company" and not r.companies:
        r.kind = "search" if r.has_subject else "unknown"
    if r.kind == "park" and not r.park:
        r.park = "contact"
    if r.kind == "help" and not r.help:
        r.help = "general"
    if r.kind == "opportunities" and not r.kinds:
        r.kind = "search" if r.has_subject else "unknown"
    if r.kind in ("partners", "search") and not r.has_subject:
        r.kind = "unknown"
    return r
