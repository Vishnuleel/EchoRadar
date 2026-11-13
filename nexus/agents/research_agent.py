"""Research Intelligence Agent: retrieves real publications from OpenAlex and stores them once."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.core import taxonomy as tx
from nexus.database import repository as repo
from nexus.database.models import ResearchPublication
from nexus.integrations import openalex
from nexus.integrations.http_cache import HttpClient


def upsert_publication(s: Session, rec: dict, capability_key: str | None = None) -> tuple[ResearchPublication, bool]:
    """Insert unless the OpenAlex ID or DOI is already stored (duplicate detection)."""
    row = s.scalar(select(ResearchPublication).where(ResearchPublication.external_id == rec["external_id"]))
    if row is None and rec.get("doi"):
        row = s.scalar(select(ResearchPublication).where(ResearchPublication.doi == rec["doi"]))
    created = row is None
    tags = {c for c, _ in tx.detect_capabilities(f"{rec['title']} {rec.get('abstract') or ''}")}
    if capability_key:
        tags.add(capability_key)
    if created:
        row = ResearchPublication(**{k: v for k, v in rec.items()}, capability_keys=sorted(tags))
        s.add(row)
    else:
        row.capability_keys = sorted(set(row.capability_keys or []) | tags)
        row.cited_by_count = rec.get("cited_by_count", row.cited_by_count)
    s.flush()
    return row, created


def collect_research(s: Session, client: HttpClient, capability_keys: list[str], per_query: int = 8) -> dict:
    """Query OpenAlex once per capability that has a search phrase. Failures are reported, not hidden."""
    summary = {"queries": 0, "new": 0, "duplicates": 0, "errors": []}
    for key in capability_keys:
        cap = tx.CAPABILITIES.get(key)
        if not cap or not cap.openalex_query:
            continue
        summary["queries"] += 1
        try:
            works = openalex.search_works(client, cap.openalex_query, per_page=per_query)
        except openalex.OpenAlexError as exc:
            summary["errors"].append(f"{cap.openalex_query}: {exc}")
            repo.log_retrieval(s, "openalex", openalex.API, "error", detail=str(exc))
            if "429" in str(exc) or "401" in str(exc) or "403" in str(exc):
                break  # quota/auth problems will not fix themselves on the next query
            continue
        for rec in works:
            _, created = upsert_publication(s, rec, key)
            summary["new" if created else "duplicates"] += 1
        repo.log_retrieval(s, "openalex", f"search: {cap.openalex_query}", "ok", 200, records=len(works))
    return summary


def explain_relevance(pub: ResearchPublication, shared_caps: list[str], cosine: float) -> str:
    if shared_caps:
        names = ", ".join(tx.CAPABILITIES[c].name for c in shared_caps[:3])
        return f"Addresses {names}, which appear in the evidenced profile (text similarity {cosine:.2f})."
    return f"Topically close to the profile text (similarity {cosine:.2f}); no direct capability tag in common."
