"""OpenAlex connector (https://docs.openalex.org/).

Searches works by keyword, follows page-based pagination, rebuilds abstracts from the inverted
index, de-duplicates by OpenAlex ID / DOI and never invents metadata: missing fields stay None.

Authentication: OpenAlex accepts anonymous calls on a small shared daily budget. Set
OPENALEX_API_KEY (free) for your own budget. In managed environments the key may instead be
injected by a network proxy, in which case no variable is needed.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from nexus.integrations.http_cache import HttpClient
from nexus.utils.config import get_settings
from nexus.utils.validators import parse_date

API = "https://api.openalex.org/works"
FIELDS = ("id,doi,title,publication_date,authorships,cited_by_count,primary_location,"
          "abstract_inverted_index,topics,type")


class OpenAlexError(RuntimeError):
    pass


def rebuild_abstract(inverted: dict | None) -> str | None:
    if not inverted:
        return None
    positions = [(pos, word) for word, plist in inverted.items() for pos in plist]
    return " ".join(w for _, w in sorted(positions)) or None


def parse_work(work: dict, retrieved_at: datetime, query: str | None = None) -> dict | None:
    oid, title = work.get("id"), (work.get("title") or "").strip()
    if not oid or not title:
        return None
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    return {
        "external_id": oid.rsplit("/", 1)[-1],
        "doi": work.get("doi"),
        "title": title,
        "authors": [a["author"]["display_name"] for a in work.get("authorships") or []
                    if a.get("author", {}).get("display_name")][:12],
        "abstract": rebuild_abstract(work.get("abstract_inverted_index")),
        "publication_date": parse_date(work.get("publication_date")),
        "venue": source.get("display_name"),
        "cited_by_count": work.get("cited_by_count"),
        "topics": [t["display_name"] for t in work.get("topics") or [] if t.get("display_name")],
        "source_url": work.get("doi") or loc.get("landing_page_url") or oid,
        "query": query,
        "retrieved_at": retrieved_at,
    }


def search_works(client: HttpClient, query: str, per_page: int = 8, max_pages: int = 1,
                 from_year: int | None = 2019) -> list[dict]:
    """Search works. Raises OpenAlexError with the service's own message on failure."""
    st = get_settings()
    results, seen = [], set()
    for page in range(1, max_pages + 1):
        params = {"search": query, "per-page": per_page, "page": page, "select": FIELDS}
        filters = ["type:article|review|preprint|book-chapter"]
        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")
        params["filter"] = ",".join(filters)
        if st.contact_email:
            params["mailto"] = st.contact_email
        url = f"{API}?{urlencode(params)}"
        headers = {"Authorization": f"Bearer {st.openalex_api_key}"} if st.openalex_api_key else {}
        res = client.get(url, ttl_hours=24 * 7, headers=headers)
        if not res.ok:
            hint = ""
            if res.http_status == 429:
                hint = " (rate limit / daily budget exhausted - configure OPENALEX_API_KEY)"
            elif res.http_status in (401, 403):
                hint = " (authentication rejected - check OPENALEX_API_KEY)"
            raise OpenAlexError(f"OpenAlex request failed: {res.error}{hint}")
        try:
            payload = res.json()
        except ValueError as exc:
            raise OpenAlexError(f"OpenAlex returned non-JSON content: {exc}") from exc
        batch = payload.get("results") or []
        for work in batch:
            parsed = parse_work(work, res.retrieved_at, query)
            if parsed is None:
                continue
            key = parsed["doi"] or parsed["external_id"]
            if key in seen or parsed["external_id"] in seen:
                continue
            seen.update({key, parsed["external_id"]})
            results.append(parsed)
        if len(batch) < per_page:
            break
    return results
