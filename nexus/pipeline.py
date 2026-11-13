"""Orchestration of the NEXUS agents.

ingest()    - Company, Research and Opportunity agents retrieve public data (live or cached)
recompute() - Combination -> Ranking -> Verification agents rebuild hypotheses and rankings
answer_request() - boundary-checked free-text entry point ("Ask NEXUS")

A plain sequential orchestrator is used on purpose: the flow is linear and deterministic, so a
graph framework would add dependencies without adding behaviour. Each step records a trace entry
(agent, duration, counts) that the UI shows.
"""
from __future__ import annotations

import time
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.agents import (combination_agent, company_agent, monitoring_agent, opportunity_agent, ranking_agent,
                          research_agent)
from nexus.agents import verification_agent
from nexus.core import matching_engine as me
from nexus.core import taxonomy as tx
from nexus.core.embeddings import get_embedder
from nexus.database import repository as repo
from nexus.core import radar
from nexus.database.models import (CollaborationHypothesis, Company, Event, FundingOpportunity, NewsUpdate, Opportunity,
                                   Recommendation, ResearchPublication, SavedItem, Testbed)
from nexus.integrations import company_sources
from nexus.integrations.http_cache import HttpClient
from nexus.security import boundary_guard, privacy
from nexus.utils.logging import get_logger
from nexus.utils.validators import utcnow

log = get_logger(__name__)

# Members whose official websites are read in addition to the directory (verified reachable).
DEFAULT_DEEP_SLUGS = ["njord-x", "embeddedart", "c-marine-ab", "baltic-offshore", "lassen-construction"]


def _drain(s: Session, client: HttpClient, source: str) -> None:
    for ev in client.events:
        if ev.status != "cached":
            repo.log_retrieval(s, source, ev.url, ev.status, ev.http_status, ev.error)
    client.events.clear()


def refresh_company(s: Session, client: HttpClient, member: company_sources.MemberRecord, deep: bool) -> dict:
    """Generate (or refresh) one baseline profile from public information."""
    crawl = company_sources.crawl_company_site(client, member.website) if deep and member.website else None
    draft = company_agent.build_profile(member, crawl)
    company = company_agent.persist_profile(s, draft)
    _drain(s, client, "company_website" if deep else "member_directory")
    for q in draft.quarantined:
        repo.log_retrieval(s, "boundary", q.split(": ")[0], "quarantined", detail=q)
    return {"company": company, "claims": len(draft.claims), "depth": draft.profile_depth,
            "warnings": draft.warnings, "quarantined": len(draft.quarantined)}


def ingest(s: Session, client: HttpClient | None = None, deep_slugs: list[str] | None = None,
           limit: int | None = None, research: bool = True, funding: bool = True, testbeds: bool = True) -> list[dict]:
    client = client or HttpClient()
    deep_slugs = DEFAULT_DEEP_SLUGS if deep_slugs is None else deep_slugs
    trace = []

    t = time.time()
    members, errors = company_sources.fetch_member_directory(client, limit)
    _drain(s, client, "member_directory")
    n_claims, warnings = 0, list(errors)
    for m in members:
        out = refresh_company(s, client, m, deep=m.slug in deep_slugs)
        n_claims += out["claims"]
        warnings += [f"{m.name}: {w}" for w in out["warnings"]]
    s.commit()
    trace.append({"agent": "Company Intelligence Agent", "seconds": round(time.time() - t, 1),
                  "result": f"{len(members)} profiles, {n_claims} evidence-backed claims", "warnings": warnings})

    if research:
        t = time.time()
        present = sorted({c.capability.key for c in repo.all_claims(s)
                          if c.capability and c.claim_category == "capability"})
        out = research_agent.collect_research(s, client, present)
        _drain(s, client, "openalex")
        s.commit()
        trace.append({"agent": "Research Intelligence Agent", "seconds": round(time.time() - t, 1),
                      "result": f"{out['queries']} OpenAlex queries, {out['new']} new works, "
                                f"{out['duplicates']} duplicates merged", "warnings": out["errors"]})
    if funding:
        t = time.time()
        out = opportunity_agent.collect_funding(s, client)
        _drain(s, client, "vinnova")
        s.commit()
        trace.append({"agent": "Opportunity Intelligence Agent (Vinnova)", "seconds": round(time.time() - t, 1),
                      "result": f"{out['new']} new calls, {out['updated']} updated", "warnings": out["errors"]})
    if testbeds:
        t = time.time()
        out = opportunity_agent.collect_testbeds(s, client)
        _drain(s, client, "testbeds")
        s.commit()
        trace.append({"agent": "Opportunity Intelligence Agent (test environments)",
                      "seconds": round(time.time() - t, 1),
                      "result": f"{out['new']} new, {out['updated']} updated", "warnings": out["errors"]})
    t = time.time()
    ev = monitoring_agent.collect_events(s, client)
    nw = monitoring_agent.collect_news(s, client)
    _drain(s, client, "monitoring")
    s.commit()
    trace.append({"agent": "Monitoring Agent (events and news)", "seconds": round(time.time() - t, 1),
                  "result": f"{ev['new'] + ev['updated']} events, {nw['new'] + nw['updated']} news items, "
                            f"{nw['member_mentions']} member mentions", "warnings": ev["errors"] + nw["errors"]})
    return trace


# ------------------------------------------------------------------------------------------------
def _item_text(row) -> str:
    if isinstance(row, ResearchPublication):
        return f"{row.title}. {(row.abstract or '')[:900]}"
    if isinstance(row, FundingOpportunity):
        return f"{row.title}. {row.description or ''}"
    if isinstance(row, Event):
        return f"{row.title}. {row.description or ''}"
    if isinstance(row, NewsUpdate):
        return f"{row.title}. {row.summary or ''}"
    return f"{row.name}. {row.description}"


def _item_set(s: Session, rows: list, embedder) -> ranking_agent.ItemSet:
    if not rows:
        return ranking_agent.ItemSet()
    vecs = embedder.encode([_item_text(r) for r in rows], s)
    return ranking_agent.ItemSet(rows=rows, vectors=vecs, caps=[set(r.capability_keys or []) for r in rows])


def build_context(s: Session, embedder, now: datetime | None = None) -> ranking_agent.RankingContext:
    now = now or utcnow()
    research = list(s.scalars(select(ResearchPublication)))
    all_funding = list(s.scalars(select(FundingOpportunity)))
    live = [f for f in all_funding if opportunity_agent.current_status(f, now) in ("open", "upcoming")]
    testbeds = list(s.scalars(select(Testbed)))
    caps = list(tx.CAPABILITIES.values())
    cap_vecs = embedder.encode([f"{c.name}. {c.description} {c.openalex_query}" for c in caps], s)
    con_vecs = embedder.encode([f"{c.title}. {c.problem} {c.outcome}" for c in tx.CONCEPTS], s)
    return ranking_agent.RankingContext(
        research=_item_set(s, research, embedder), funding=_item_set(s, live, embedder),
        testbeds=_item_set(s, testbeds, embedder),
        cap_vectors={c.id: v for c, v in zip(caps, cap_vecs)},
        concept_vectors={c.id: v for c, v in zip(tx.CONCEPTS, con_vecs)},
        semantic=embedder.is_semantic, now=now)


def hypothesis_title(cand: me.Candidate, profiles: dict) -> tuple[str, str]:
    """(title, proposed application). Both are generated hypotheses, never facts."""
    if cand.concept_id:
        c = tx.CONCEPTS_BY_ID[cand.concept_id]
        return c.title, c.outcome
    l = cand.links[0]
    a, b = tx.CAPABILITIES[l.cap_a].name, tx.CAPABILITIES[l.cap_b].name
    domain = tx.DOMAINS.get(cand.domain or "", "a shared application")
    if l.kind == "stated_interest":
        return (f"{a}: matching a stated interest with an evidenced capability",
                f"Explore how {profiles[l.company_b].name}'s capability could meet the interest stated by "
                f"{profiles[l.company_a].name}.")
    return (f"{a} + {b} for {domain.lower()}",
            f"Explore a joint offer in {domain.lower()} where {l.rationale}.")


def _uncertainty(scored: dict, verification: dict) -> list[str]:
    cand = scored["candidate"]
    out = ["Capability claims come from public web text; depth, capacity and availability are not verified.",
           "No contact has been made with any company; interest in collaborating is unknown.",
           "This is a generated hypothesis, not an existing or agreed collaboration."]
    if cand.missing_slots:
        out.append("Missing capabilities would have to be sourced elsewhere: " + ", ".join(cand.missing_slots) + ".")
    if scored["funding"]:
        out.append("Funding eligibility has not been checked against the call criteria.")
    else:
        out.append("No currently open funding call was found that is clearly relevant.")
    if not scored["research"]:
        out.append("No clearly relevant research record was retrieved.")
    return out + verification["warnings"]


def recompute(s: Session, embedder=None, now: datetime | None = None) -> list[dict]:
    """Rebuild all hypotheses, personalised recommendations and radar items from stored data."""
    embedder = embedder or get_embedder()
    now = now or utcnow()
    trace = []

    t = time.time()
    profiles = combination_agent.load_profiles(s, embedder)
    by_id = {p.id: p for p in profiles}
    pairs, triads, _sim = combination_agent.generate_candidates(profiles)
    trace.append({"agent": "Innovation Combination Agent", "seconds": round(time.time() - t, 2),
                  "result": f"{len(pairs)} complementary pairs and {len(triads)} three-company combinations "
                            f"from {len(profiles)} profiles", "warnings": []})

    t = time.time()
    ctx = build_context(s, embedder, now)
    scored = [ranking_agent.score_candidate(c, by_id, ctx) for c in pairs + triads]
    missing = sorted({m for sc in scored for m in sc["breakdown"].missing})
    trace.append({"agent": "Ranking Agent", "seconds": round(time.time() - t, 2),
                  "result": f"{len(scored)} candidates scored against {len(ctx.research)} research records and "
                            f"{len(ctx.funding)} open/upcoming calls",
                  "warnings": [f"No data for component(s): {', '.join(missing)} (scored as 0)"] if missing else []})

    t = time.time()
    funding_rows = {f.id: f for f in ctx.funding.rows}
    accepted, rejected = [], 0
    for sc in scored:
        title, application = hypothesis_title(sc["candidate"], by_id)
        ver = verification_agent.verify(sc, by_id, title, funding_rows, now)
        if ver["status"] == "rejected":
            rejected += 1
            continue
        sc.update(title=title, application=application, verification=ver)
        accepted.append(sc)
    trace.append({"agent": "Verification Agent", "seconds": round(time.time() - t, 2),
                  "result": f"{len(accepted)} hypotheses passed, {rejected} rejected for unsupported claims",
                  "warnings": []})

    # keep what is needed for personalised lists (bounded storage)
    keep: dict[str, dict] = {}
    per_company: dict[int, list[dict]] = {}
    for p in profiles:
        mine = ranking_agent.rank_for_company(p.id, accepted, profile=p)
        per_company[p.id] = mine
        for sc in mine:
            keep[sc["candidate"].key] = sc
    for sc in sorted((a for a in accepted if a["candidate"].kind == "triad"),
                     key=lambda a: -a["breakdown"].final)[:40]:
        keep[sc["candidate"].key] = sc

    repo.clear_derived(s)
    s.flush()
    rows: dict[str, CollaborationHypothesis] = {}
    for key, sc in keep.items():
        cand = sc["candidate"]
        links = []
        for l in cand.links:
            d = l.to_dict()
            for side, cid, cap in (("a", l.company_a, l.cap_a), ("b", l.company_b, l.cap_b)):
                claim = by_id[cid].capabilities.get(cap)
                d[f"evidence_{side}"] = ({"excerpt": claim.excerpt[:400], "urls": sorted(set(claim.source_urls))[:3],
                                          "classification": claim.classification} if claim else None)
            links.append(d)
        row = CollaborationHypothesis(
            key=key, kind=cand.kind, title=sc["title"], participating_companies=list(cand.company_ids),
            required_capabilities=[{"slot": slot, **v} for slot, v in cand.slot_assignment.items()],
            missing_capabilities=cand.missing_slots, proposed_application=sc["application"],
            concept_id=cand.concept_id, evidence=links, uncertainty=_uncertainty(sc, sc["verification"]),
            score=sc["breakdown"].final,
            score_breakdown={**sc["breakdown"].to_dict(), "evidence_detail": sc["evidence"],
                             "similarity": cand.similarity, "concept_coverage": cand.coverage,
                             "domain": cand.domain},
            research_ids=sc["research"], funding_ids=sc["funding"], testbed_ids=sc["testbeds"],
            verification=sc["verification"], validation_status="hypothesis")
        s.add(row)
        rows[key] = row
    s.flush()
    for cid, mine in per_company.items():
        for rank, sc in enumerate(mine, 1):
            s.add(Recommendation(company_id=cid, target_id=rows[sc["candidate"].key].id, rank=rank,
                                 score=sc["personal_score"],
                                 score_breakdown={**sc["breakdown"].to_dict(), "personal_note": sc["personal_note"]},
                                 explanation=ranking_agent.explain(sc, by_id, cid)
                                 + (" " + sc["personal_note"] if sc["personal_note"] else "")))

    # Radar: company-specific relevance for every monitoring area, adjusted by stated needs and feedback
    t = time.time()
    sets = _radar_sets(s, embedder, now, ctx.research, ctx.testbeds)
    companies_by_id = {c.id: c for c in s.scalars(select(Company))}
    marks = _radar_marks(s)
    n_radar = 0
    for p in profiles:
        n_radar += _radar_for_profile(s, p, companies_by_id[p.id], sets, marks.get(p.id, {}), ctx.semantic, now)
    s.commit()
    trace.append({"agent": "Opportunity bridge (radar)", "seconds": round(time.time() - t, 2),
                  "result": f"{n_radar} company-specific radar items; {len(rows)} hypotheses stored",
                  "warnings": []})
    return trace


# ------------------------------------------------------------------------------------------------
# Radar: (items kept per kind, relevance floor)
RADAR_LIMITS = {"research": (10, 25.0), "funding": (10, 25.0), "testbed": (4, 10.0), "event": (6, 10.0), "news": (6, 22.0)}


def _radar_sets(s: Session, embedder, now: datetime, research: ranking_agent.ItemSet | None = None,
                testbeds: ranking_agent.ItemSet | None = None) -> dict[str, ranking_agent.ItemSet]:
    """The records every company's radar is ranked against, one ItemSet per monitoring area."""
    if research is None:
        research = _item_set(s, list(s.scalars(select(ResearchPublication))), embedder)
    testbed_rows = testbeds.rows if testbeds is not None else list(s.scalars(select(Testbed)))
    all_funding = list(s.scalars(select(FundingOpportunity)))
    return {
        "research": research,
        "funding": _item_set(s, [f for f in all_funding if opportunity_agent.current_status(f, now) != "closed"], embedder),
        "testbed": _item_set(s, [x for x in testbed_rows if x.kind != "event"], embedder),
        "event": _item_set(s, [e for e in s.scalars(select(Event)) if e.starts_at is None or e.starts_at >= now], embedder),
        "news": _item_set(s, [n for n in s.scalars(select(NewsUpdate))
                              if n.published_at and (now - n.published_at).days <= 180], embedder),
    }


def _radar_marks(s: Session, company_id: int | None = None) -> dict[int, dict]:
    """{company_id: {action: {(kind, ref_id), ...}}} from the saved / useful / not useful marks."""
    q = select(SavedItem) if company_id is None else select(SavedItem).where(SavedItem.company_id == company_id)
    marks: dict[int, dict] = {}
    for m in s.scalars(q):
        marks.setdefault(m.company_id, {}).setdefault(m.action, set()).add((m.kind, m.ref_id))
    return marks


def _radar_for_profile(s: Session, p, company: Company, sets: dict, mine: dict, semantic: bool, now: datetime) -> int:
    """Add the Opportunity rows (radar items) of one company. Returns the number of rows added."""
    if p.vector is None or not p.capabilities:
        return 0
    caps = set(p.capabilities) | set(p.interests)
    needs = list(company.need_priorities or [])
    boosted = {k for n in needs for k in radar.NEED_TO_KINDS.get(n, [])}
    liked_kinds = {k for k, _ in mine.get("useful", set())}
    n_radar = 0
    for kind, items in sets.items():
        if not len(items):
            continue
        k, floor = RADAR_LIMITS[kind]
        scored_items = me.bridge(p.vector, caps, items.vectors, items.caps, semantic)
        for d in scored_items:
            row = items.rows[d["index"]]
            d["adjust"], d["final"] = [], d["relevance"]
            if kind == "news" and p.id in (row.mentioned_company_ids or []):
                d["final"] = max(d["final"], 90.0)
                d["adjust"].append("names your company")
            if kind in boosted:
                d["final"] = min(100.0, d["final"] + radar.PRIORITY_BOOST)
                d["adjust"].append(f"+{radar.PRIORITY_BOOST:.0f} because you marked this area as a current priority")
            if kind in liked_kinds:
                d["final"] = min(100.0, d["final"] + radar.FEEDBACK_BOOST)
                d["adjust"].append(f"+{radar.FEEDBACK_BOOST:.0f} because you rated similar items as useful")
        scored_items.sort(key=lambda d: -d["final"])
        for d in scored_items[:k]:
            row = items.rows[d["index"]]
            if d["final"] < floor or (kind, row.id) in mine.get("not_useful", set()):
                continue  # items the company marked as not useful are not offered again
            names = ", ".join(tx.CAPABILITIES[c].name for c in d["shared_capabilities"][:3])
            if kind == "research":
                why = research_agent.explain_relevance(row, d["shared_capabilities"], d["cosine"])
                action = "Read the publication and note which methods or data could apply to your products."
            elif kind == "funding":
                why = (f"The call text relates to {names} in your profile (text similarity {d['cosine']:.2f})." if names else
                       f"The call text is close to your profile (text similarity {d['cosine']:.2f}).")
                action = opportunity_agent.funding_next_action(row, now)
            elif kind == "testbed":
                why = (f"A published environment for testing and collaboration close to your profile"
                       + (f" ({names})" if names else "") + f" (text similarity {d['cosine']:.2f}).")
                action = f"Check the requirements with {row.source_name} and ask what access is possible for your case."
            elif kind == "event":
                why = (f"The topic relates to {names} in your profile." if names else
                       f"A networking format in the Blue Science Park ecosystem (text similarity {d['cosine']:.2f}).")
                action = ("Register through the source page; places are limited." if row.starts_at else
                          f"Ask {row.organiser} when the next occasion takes place.")
            else:
                why = ("The article names your company." if p.id in (row.mentioned_company_ids or []) else
                       (f"A regional development touching {names}." if names else
                        f"A regional development close to your profile (text similarity {d['cosine']:.2f})."))
                action = "Read the article and consider whether the project or actor behind it is relevant to contact."
            s.add(Opportunity(company_id=p.id, kind=kind, ref_id=row.id, relevance=round(d["final"], 1),
                              base_relevance=d["relevance"], adjustments=d["adjust"], semantic=d["cosine"],
                              matched_capabilities=d["shared_capabilities"], why=why, next_action=action))
            n_radar += 1
    return n_radar


def recompute_radar(s: Session, company_id: int, embedder=None, now: datetime | None = None) -> int:
    """Rebuild the radar items of ONE company from stored data (after useful / not useful feedback).

    Marks only influence the owning company's radar, so this gives the same rows as a full
    recompute() for that company without touching hypotheses or any other company.
    """
    from sqlalchemy import delete

    embedder = embedder or get_embedder()
    now = now or utcnow()
    company = s.get(Company, company_id)
    profile = next((p for p in combination_agent.load_profiles(s, embedder) if p.id == company_id), None)
    s.execute(delete(Opportunity).where(Opportunity.company_id == company_id))
    n = 0
    if company is not None and profile is not None:
        sets = _radar_sets(s, embedder, now)
        n = _radar_for_profile(s, profile, company, sets, _radar_marks(s, company_id).get(company_id, {}),
                               embedder.is_semantic, now)
    s.commit()
    return n


# ------------------------------------------------------------------------------------------------
def answer_request(s: Session, text: str, acting_company_id: int | None = None, embedder=None, limit: int = 4,
                   previous_in_scope: str | None = None) -> dict:
    """One assistant turn: boundary check first, then retrieval from stored, source-linked records.

    The reply is assembled from records; no text is generated by a language model. `previous_in_scope`
    lets a short follow-up reuse the topic of the last in-scope request, and nothing else.
    """
    decision = boundary_guard.classify_request(text, previous_in_scope)
    privacy.record_interaction(s, acting_company_id, "query", text, decision.category)
    out = {"decision": decision, "companies": [], "hypotheses": [], "items": [], "query": text}
    if not decision.allowed:
        s.commit()
        return out
    embedder = embedder or get_embedder()
    query = f"{previous_in_scope} {text}" if decision.follow_up and previous_in_scope else text
    out["query"] = query
    q = embedder.encode([query], s)[0]
    q_caps = {c for c, _ in tx.detect_capabilities(query)}
    intents = decision.intents or (boundary_guard.detect_intents(query) if decision.follow_up else [])
    want_kinds = {k for i in intents for k in {"funding": ["funding"], "events": ["event"], "testing": ["testbed"],
                                               "knowledge": ["research", "news"]}.get(i, [])}
    want_partners = "partners" in intents or not intents
    now = utcnow()
    for kind in (want_kinds or {"funding", "testbed", "event", "research"}):
        rows = [r for r in s.scalars(select(radar.MODEL[kind])) if radar.describe(kind, r, now) is not None]
        if kind == "event":
            rows = [r for r in rows if r.starts_at is None or r.starts_at >= now]
        items = _item_set(s, rows, embedder)
        if not len(items):
            continue
        floor = 0.0 if kind in ("testbed", "event") and kind in want_kinds else 25.0  # few records: list them all
        for d in sorted(me.bridge(q, q_caps, items.vectors, items.caps, embedder.is_semantic),
                        key=lambda d: -d["relevance"])[:limit if kind in want_kinds else 2]:
            if d["relevance"] >= floor:
                card = radar.describe(kind, items.rows[d["index"]], now)
                names = ", ".join(tx.CAPABILITIES[c].name for c in d["shared_capabilities"][:3])
                card.update(relevance=d["relevance"], matched=[],
                            why=(f"Matches your request on {names}." if names else
                                 f"Close to the wording of your request (text similarity {d['cosine']:.2f})."))
                out["items"].append(card)
    out["items"].sort(key=lambda c: -c["relevance"])
    if want_partners:
        profiles = combination_agent.load_profiles(s, embedder)
        comp = [(p, set(p.capabilities)) for p in profiles if p.vector is not None and p.capabilities]
        if comp:
            scored = me.bridge(q, q_caps, np.vstack([p.vector for p, _ in comp]), [c for _, c in comp], embedder.is_semantic)
            for d in sorted(scored, key=lambda d: -d["relevance"])[:limit]:
                if d["relevance"] >= 25:
                    p = comp[d["index"]][0]
                    claims = [p.capabilities[c] for c in (d["shared_capabilities"] or list(p.capabilities)[:2])]
                    out["companies"].append({"company_id": p.id, "name": p.name, "relevance": d["relevance"],
                                             "evidence": [{"capability": c.capability, "excerpt": c.excerpt[:300],
                                                           "url": c.source_urls[0] if c.source_urls else None}
                                                          for c in claims[:2]]})
        ids = {c["company_id"] for c in out["companies"][:3]}
        if ids and q_caps:
            hyps = s.scalars(select(CollaborationHypothesis).order_by(CollaborationHypothesis.score.desc()))
            out["hypotheses"] = [h for h in hyps if ids & set(h.participating_companies)
                                 and q_caps & ({l["cap_a"] for l in h.evidence} | {l["cap_b"] for l in h.evidence})][:3]
    s.commit()
    return out


def company_names(s: Session) -> dict[int, str]:
    return {c.id: c.name for c in s.scalars(select(Company))}


# ------------------------------------------------------------------------------------------------
LAST_RUN_PATH = None


def save_trace(trace: list[dict], backend: str) -> None:
    """Persist the last agent trace so the UI can show what actually ran."""
    import json

    from nexus.utils.config import DATA_DIR

    (DATA_DIR / "last_run.json").write_text(json.dumps(
        {"finished_at": utcnow().isoformat(timespec="seconds"), "embedding_backend": backend, "trace": trace}, indent=1))


def load_trace() -> dict | None:
    import json

    from nexus.utils.config import DATA_DIR

    p = DATA_DIR / "last_run.json"
    return json.loads(p.read_text()) if p.exists() else None


def adhoc_hypothesis(s: Session, company_ids: list[int], embedder=None, now: datetime | None = None):
    """Evaluate a user-chosen combination of two or three companies.

    Returns (hypothesis or None, message). A stored hypothesis is reused when one exists; otherwise
    the same engine, ranking and verification steps run for this combination only. When the engine
    finds no supported relationship, None is returned with the reason - nothing is made up.
    """
    ids = sorted(set(company_ids))
    if len(ids) not in (2, 3):
        return None, "Select two or three different companies."
    stored = [h for h in s.scalars(select(CollaborationHypothesis).order_by(CollaborationHypothesis.score.desc()))
              if sorted(h.participating_companies) == ids]
    if stored:
        return stored[0], "Stored hypothesis from the last ranking run."
    embedder = embedder or get_embedder()
    now = now or utcnow()
    profiles = {p.id: p for p in combination_agent.load_profiles(s, embedder) if p.id in ids}
    if any(not profiles[i].capabilities for i in ids):
        names = ", ".join(profiles[i].name for i in ids if not profiles[i].capabilities)
        return None, f"No evidence-backed capabilities are stored for: {names}. NEXUS cannot assess this combination."
    if len(ids) == 2:
        cand = me.score_pair(profiles[ids[0]], profiles[ids[1]])
    else:
        best = None
        trio = [profiles[i] for i in ids]
        links = []
        import itertools
        n_pairs = 0
        for x, y in itertools.combinations(trio, 2):
            ls = [l for l in me.pair_links(x, y) if l.strength >= me.MIN_LINK_STRENGTH]
            n_pairs += bool(ls)
            links += ls[:3]
        links.sort(key=lambda l: -l.strength)
        for concept in tx.CONCEPTS:
            assign, missing = me.assign_slots(concept, trio)
            if len({v["company"] for v in assign.values()}) == 3 and (best is None or len(assign) > len(best[1])):
                best = (concept, assign, missing)
        if n_pairs < 2 or best is None:
            return None, ("NEXUS found no application concept in which all three companies contribute a distinct, "
                          "evidence-backed capability with at least two complementary relationships.")
        concept, assign, missing = best
        cov = len(assign) / len(concept.slots)
        comp = 100.0 * (0.45 * cov * float(np.mean([v["confidence"] for v in assign.values()]))
                        + 0.35 * sum(sorted((l.strength for l in links), reverse=True)[:3]) / 3.0)
        cand = me.Candidate("triad", tuple(ids), round(comp, 1), links[:8], concept.id, assign, missing,
                            round(cov, 2), concept.domain)
    if not cand.links:
        return None, "NEXUS found no supported complementary relationship between these companies."
    ctx = build_context(s, embedder, now)
    sc = ranking_agent.score_candidate(cand, profiles, ctx)
    title, application = hypothesis_title(cand, profiles)
    ver = verification_agent.verify(sc, profiles, title, {f.id: f for f in ctx.funding.rows}, now)
    if ver["status"] == "rejected":
        return None, "Rejected by the Verification Agent: " + "; ".join(ver["issues"])
    links = []
    for l in cand.links:
        d = l.to_dict()
        for side, cid, cap in (("a", l.company_a, l.cap_a), ("b", l.company_b, l.cap_b)):
            claim = profiles[cid].capabilities.get(cap)
            d[f"evidence_{side}"] = ({"excerpt": claim.excerpt[:400], "urls": sorted(set(claim.source_urls))[:3],
                                      "classification": claim.classification} if claim else None)
        links.append(d)
    hyp = CollaborationHypothesis(
        key=cand.key + ":adhoc", kind=cand.kind, title=title, participating_companies=list(cand.company_ids),
        required_capabilities=[{"slot": k, **v} for k, v in cand.slot_assignment.items()],
        missing_capabilities=cand.missing_slots, proposed_application=application, concept_id=cand.concept_id,
        evidence=links, uncertainty=_uncertainty(sc, ver), score=sc["breakdown"].final,
        score_breakdown={**sc["breakdown"].to_dict(), "evidence_detail": sc["evidence"], "domain": cand.domain},
        research_ids=sc["research"], funding_ids=sc["funding"], testbed_ids=sc["testbeds"], verification=ver,
        validation_status="hypothesis")
    return hyp, "Computed on request for this combination (not stored)."
