"""Run the profiling agent again on one member, in the open, without saving anything.

recheck() reads the member's directory page and website (live, or from the cache when asked to),
builds a profile with the same Company Intelligence Agent that ingest uses, and compares it with
the stored profile: what the agent read, what it found and where, what it set aside, and what
changed since the stored profile was built. It is the "a website becomes a profile" step of the
demo, and it shows how profiles are kept current. Nothing is written to the database.
"""
from __future__ import annotations

import time
from collections import Counter
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from nexus.agents import company_agent
from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import Company
from nexus.integrations import company_sources
from nexus.integrations.http_cache import HttpClient

PROFILE_PARTS = {"description": "What the company does", "capability": "Technologies and expertise",
                 "market": "Markets and customers", "geography": "Geographical focus",
                 "collaboration": "Collaborations", "development_activity": "Stated development activities"}


def _member_from_store(c: Company) -> company_sources.MemberRecord:
    return company_sources.MemberRecord(slug=c.slug, name=c.name, description=c.description, industry=c.industry,
                                        employees=c.employees, founded=c.founded, location=c.location,
                                        website=c.website, directory_url=c.directory_url,
                                        retrieved_at=c.last_verified_at or c.updated_at)


def recheck(s: Session, company_id: int, fresh: bool = False, client: HttpClient | None = None, llm=None) -> dict:
    c = s.get(Company, company_id)
    if c is None:
        raise KeyError(company_id)
    client = client or HttpClient()
    ttl = 0 if fresh else 24 * 3
    t0 = time.perf_counter()
    steps = []

    member, status = company_sources.fetch_member_profile(client, c.slug, ttl_hours=ttl)
    steps.append({"agent": "Directory agent", "did": "Read the member's page in the Blue Science Park directory",
                  "status": status, "url": member.directory_url if member else c.directory_url})
    if member is None:
        member = _member_from_store(c)
        steps[-1]["note"] = "The page could not be read, so the stored directory entry is used."

    website = member.website or c.website
    crawl = company_sources.crawl_company_site(client, website, max_pages=5 if fresh else 8, ttl_hours=ttl) if website else None
    pages = [{"url": p.url, "title": p.title, "sentences": len(p.sentences),
              "retrieved_at": p.retrieved_at} for p in (crawl.pages if crawl else [])]
    host = urlparse(website).netloc if website else None
    fetched = Counter("live" if e.status == "ok" else "cache" if e.status == "cached" else "failed"
                      for e in client.events if host and urlparse(e.url).netloc == host and not e.url.endswith("robots.txt"))
    steps.append({"agent": "Website reader", "did": f"Read {len(pages)} page(s) of {website}" if website
                  else "No website is listed, so only the directory entry can be read",
                  "status": ", ".join(f"{n} {k}" for k, n in sorted(fetched.items())) or "nothing fetched",
                  "url": website, "errors": (crawl.errors if crawl else [])[:5]})

    draft = company_agent.build_profile(member, crawl, llm=llm)
    steps.append({"agent": "Boundary filter", "did": "Set aside sentences that read like instructions to an AI",
                  "status": f"{len(draft.quarantined)} set aside"})

    stored = [cl for cl in repo.claims(s, company_id) if cl.origin == "public"]
    stored_caps = {cl.capability.key for cl in stored
                   if cl.classification == "FACT" and cl.claim_category == "capability" and cl.capability}
    found: dict[str, list] = {}
    for cl in draft.claims:
        if cl.classification == "FACT" and cl.claim_category == "capability" and cl.capability_key:
            found.setdefault(cl.capability_key, []).append({"text": cl.evidence_text[:280], "url": cl.evidence_url,
                                                            "source": cl.source_type})
    capabilities = [{"key": k, "name": tx.CAPABILITIES[k].name, "status": "unchanged" if k in stored_caps else "new",
                     # the company's own words first: that is what this check is about
                     "quotes": sorted(v, key=lambda q: q["source"] != "company_website")[:2]} for k, v in sorted(found.items(), key=lambda kv: tx.CAPABILITIES[kv[0]].name)]
    gone = sorted(tx.CAPABILITIES[k].name if k in tx.CAPABILITIES else k for k in stored_caps - set(found))
    other = [{"part": PROFILE_PARTS.get(cl.claim_category, cl.claim_category), "text": cl.evidence_text[:240],
              "url": cl.evidence_url} for cl in draft.claims
             if cl.classification == "FACT" and cl.claim_category in ("market", "geography", "collaboration",
                                                                      "development_activity")]
    present = {cl.claim_category for cl in draft.claims if cl.classification == "FACT"}
    steps.append({"agent": "Company intelligence agent",
                  "did": "Matched each sentence against the capability taxonomy and kept first-party, current statements",
                  "status": f"{len(capabilities)} capabilities, {len(other)} other facts, {len(draft.rejected)} statements not used"})
    return {
        "company": {"id": c.id, "name": c.name, "website": website},
        "fresh": fresh, "seconds": round(time.perf_counter() - t0, 1),
        "steps": steps, "pages": pages,
        "description": member.description, "description_changed": (member.description or "") != (c.description or ""),
        "capabilities": capabilities, "no_longer_found": gone, "other_facts": other,
        "inferences": [cl.claim_text for cl in draft.claims if cl.classification == "INFERENCE"],
        "missing": [label for key, label in PROFILE_PARTS.items() if key not in present],
        "quarantined": draft.quarantined[:5], "not_used": draft.rejected[:8], "warnings": draft.warnings[:5],
        "stored_profile": {"capabilities": len(stored_caps), "depth": c.profile_depth,
                           "updated_at": c.updated_at},
    }
