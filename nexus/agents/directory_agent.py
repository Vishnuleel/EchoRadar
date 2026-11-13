"""Directory Agent: keeps every member profile tied to the official Blue Science Park directory.

sync_directory()
  1. reads the public member directory to its end (all "Ladda mer" pages) and records the card count,
  2. opens every listed profile and copies name, Swedish description, industry, employee band,
     founding year, locations and website, each with its own source URL and retrieval time,
  3. follows related-member links ("Fler medlemmar") to catch profiles missing from the listing,
  4. optionally reconciles an imported audited seed: seed values are kept next to the live values as a
     second source, never on top of them, and every disagreement is recorded,
  5. stores a DirectorySnapshot with the audit summary.

Nothing is deleted: a company that disappears from the listing is marked `not_in_latest_listing`.
Nothing is guessed: a field the profile does not publish stays empty and is listed in `missing_fields`.
Member versus partner status is not published per organisation, so it is never set.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.integrations import company_sources as cs
from nexus.integrations.http_cache import HttpClient
from nexus.database.models import Company, DirectorySnapshot
from nexus.utils.validators import utcnow

BSP_PROFILE = "Blue Science Park member profile"
NOT_DISCLOSED = "member_or_partner_not_individually_disclosed"
# seed column -> NEXUS field
SEED_FIELDS = {"organisation_name": "name", "description_original_sv": "description", "industry_original_sv": "industry",
               "employee_range": "employees", "founded_year": "founded", "locations": "location",
               "official_website": "website"}


# ---- normalisation -------------------------------------------------------------------------------
def canonical_profile_url(url: str | None) -> str | None:
    """https://bluesciencepark.se/medlem/x -> https://www.bluesciencepark.se/medlem/x/ (the dedupe key)."""
    m = re.search(r"bluesciencepark\.se/medlem/([a-z0-9\-]+)", (url or "").lower())
    return f"{cs.BSP_BASE}/medlem/{m.group(1)}/" if m else None


def normalised_name(name: str | None) -> str:
    """Second dedupe key: case, accents, punctuation and company-form suffixes removed."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(ab|aktiebolag|ltd|inc|as|oy)\b", " ", s)
    return " ".join(s.split())


def _seed_value(field: str, value):
    """Seed values as display strings comparable with the live parse."""
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _same(field: str, a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a is b
    if field == "website":
        return a.rstrip("/").lower() == b.rstrip("/").lower()
    norm = lambda x: " ".join(x.replace(" ,", ",").split()).casefold()
    return norm(a) == norm(b)


# ---- provenance ----------------------------------------------------------------------------------
def provenance(rec: cs.MemberRecord) -> dict:
    """{field: source} for one parsed profile. All facts come from the profile page itself."""
    when = rec.retrieved_at.isoformat(timespec="seconds") if rec.retrieved_at else None
    out = {}
    for f in cs.PROFILE_FIELDS:
        value = getattr(rec, f)
        if value:
            out[f] = {"value": value, "source": BSP_PROFILE, "url": rec.directory_url, "retrieved_at": when,
                      **({"link_target": value} if f == "website" else {})}
    return out


def apply_profile(company: Company, rec: cs.MemberRecord, status: str, snapshot_id: str, listed: bool) -> None:
    """Record where each directory fact on this company came from. Seed notes already stored are kept."""
    old = company.field_sources or {}
    fresh = provenance(rec)
    for f, src in fresh.items():
        if "seed" in old.get(f, {}):
            src["seed"] = old[f]["seed"]
    company.field_sources = fresh
    company.missing_fields = rec.missing_fields()
    company.last_verified_at = rec.retrieved_at
    company.profile_fetch_status = status
    company.directory_snapshot_id = snapshot_id
    company.listing_status = "listed" if listed else "related_link_only"
    company.membership_classification = NOT_DISCLOSED  # not published per organisation: never inferred


def _add_alias(company: Company, alias: str | None) -> None:
    if alias and alias not in (company.aliases or []) and alias not in (company.name, company.directory_url):
        company.aliases = [*(company.aliases or []), alias]


# ---- seed import ---------------------------------------------------------------------------------
def load_seed(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "records" not in data:
        raise ValueError("seed file has no 'records' list")
    return data


def reconcile_seed(s: Session, seed: dict, client: HttpClient | None = None) -> dict:
    """Attach each audited seed record to its company as a second source and report the result.

    Matching: canonical Blue Science Park profile URL first (following redirects when a client is
    given), then normalised name. Live profile values stay primary; seed values are stored beside them
    with `agrees` true/false. A seed record that matches nothing is reported, not invented into a profile.
    """
    dataset = f"{seed.get('dataset_name', 'audited seed')} v{seed.get('version', '?')} ({seed.get('audit_date', '?')})"
    companies = list(s.scalars(select(Company)))
    by_url = {canonical_profile_url(c.directory_url): c for c in companies if c.directory_url}
    for c in companies:
        for a in c.aliases or []:
            if canonical_profile_url(a):
                by_url.setdefault(canonical_profile_url(a), c)
    by_name = {normalised_name(c.name): c for c in companies}
    for c in companies:
        for a in c.aliases or []:
            by_name.setdefault(normalised_name(a), c)

    stats = Counter()
    unmatched, disagreements = [], Counter()
    for r in seed["records"]:
        url = canonical_profile_url(r.get("blue_science_park_profile_url") or r.get("evidence_url"))
        company, how = by_url.get(url), "profile_url"
        if company is None and url and client is not None:  # an old slug may redirect to the current profile
            res = client.get(url, ttl_hours=24 * 3, check_robots=True)
            company = by_url.get(canonical_profile_url(res.final_url)) if res.ok else None
            how = "profile_url_redirect"
        if company is None:
            company, how = by_name.get(normalised_name(r.get("organisation_name"))), "name"
        if company is None:
            unmatched.append({"name": r.get("organisation_name"), "profile_url": url})
            continue
        stats[f"matched_by_{how}"] += 1
        if url and url != canonical_profile_url(company.directory_url):
            _add_alias(company, url)
        if r.get("organisation_name") and r["organisation_name"] != company.name:
            _add_alias(company, r["organisation_name"])
        sources = dict(company.field_sources or {})
        for col, f in SEED_FIELDS.items():
            seed_v = _seed_value(f, r.get(col))
            live = sources.get(f, {}).get("value")
            if seed_v is None and live is None:
                continue
            agrees = _same(f, live, seed_v)
            if not agrees:
                disagreements[f] += 1
            entry = dict(sources.get(f) or {"value": None, "source": None, "url": None, "retrieved_at": None})
            entry["seed"] = {"value": seed_v, "agrees": agrees, "dataset": dataset,
                             "url": r.get("evidence_url") or r.get("blue_science_park_profile_url"),
                             "verified": r.get("last_verified_date")}
            sources[f] = entry
        company.field_sources = sources
        # an explicit statement in the seed would be the only way to set the class; the seed does not make one
        if r.get("membership_classification") not in (None, NOT_DISCLOSED):
            stats["seed_states_membership_class_ignored_without_source"] += 1
    s.flush()
    return {"seed_dataset": dataset, "seed_records": len(seed["records"]),
            "seed_matches": sum(v for k, v in stats.items() if k.startswith("matched_by_")),
            "seed_matched_by": {k.removeprefix("matched_by_"): v for k, v in stats.items() if k.startswith("matched_by_")},
            "seed_unmatched": unmatched, "seed_disagreements_by_field": dict(disagreements),
            "seed_scope_note": seed.get("scope_note")}


# ---- live crawl ----------------------------------------------------------------------------------
def sync_directory(s: Session, client: HttpClient | None = None, refresh=None, seed: dict | None = None,
                   profile_ttl_hours: float = 24 * 3, follow_related: bool = True) -> dict:
    """Crawl the directory, refresh every profile, reconcile the seed, store the snapshot.

    `refresh(member) -> Company` builds and stores the profile (claims, evidence); the pipeline passes
    its own function so this agent stays independent of how profiles are enriched.
    """
    client = client or HttpClient()
    now = utcnow()
    snapshot_id = f"bsp-live-{now:%Y%m%dT%H%M%SZ}"
    listing = cs.list_directory(client)
    known_before = set(s.scalars(select(Company.slug)))
    # (slug, how it was found): the listing first, then related-member links and seed profile URLs
    queue: list[tuple[str, str]] = [(sl, "listed") for sl in listing.slugs]
    queued = set(listing.slugs)
    for r in (seed or {}).get("records", []):
        url = canonical_profile_url(r.get("blue_science_park_profile_url"))
        sl = url.rstrip("/").rsplit("/", 1)[-1] if url else None
        if sl and sl not in queued:  # e.g. an old slug: opened so a redirect can be resolved, never assumed
            queued.add(sl)
            queue.append((sl, "seed_only"))
    seen_profiles: dict[str, Company] = {}
    failed, found_outside_listing, duplicates, new_records = [], [], [], []

    i = 0
    while i < len(queue):
        slug, how = queue[i]
        i += 1
        rec, status = cs.fetch_member_profile(client, slug, ttl_hours=profile_ttl_hours)
        if rec is None:
            failed.append({"url": f"{cs.BSP_BASE}/medlem/{slug}/", "found_via": how, "status": status})
            existing = s.scalar(select(Company).where(Company.slug == slug))
            if existing is not None:  # keep the record and its last verified facts; say the check failed
                existing.profile_fetch_status = status
            continue
        if rec.slug in seen_profiles:  # an alias slug (e.g. an old URL) that redirects to a profile already read
            if slug != rec.slug:
                duplicates.append({"url": f"{cs.BSP_BASE}/medlem/{slug}/", "canonical": rec.directory_url})
                _add_alias(seen_profiles[rec.slug], f"{cs.BSP_BASE}/medlem/{slug}/")
            continue
        company = refresh(rec) if refresh else _store_minimal(s, rec)
        in_listing = rec.slug in listing.slugs or slug in listing.slugs
        apply_profile(company, rec, status, snapshot_id, listed=in_listing)
        if not in_listing:
            company.listing_status = "related_link_only" if how == "related" else "seed_only"
            found_outside_listing.append({"url": rec.directory_url, "found_via": how})
        if slug != rec.slug:
            duplicates.append({"url": f"{cs.BSP_BASE}/medlem/{slug}/", "canonical": rec.directory_url})
            _add_alias(company, f"{cs.BSP_BASE}/medlem/{slug}/")
        if rec.slug not in known_before:
            new_records.append(rec.directory_url)
        seen_profiles[rec.slug] = company
        if follow_related:
            for r in rec.related_slugs:
                if r not in queued:
                    queued.add(r)
                    queue.append((r, "related"))

    # companies stored earlier but not found now: kept, flagged for an admin to confirm (never deleted)
    failed_slugs = {f["url"].rstrip("/").rsplit("/", 1)[-1] for f in failed}
    gone = []
    if listing.stable_end:
        for c in s.scalars(select(Company)):
            if c.slug not in seen_profiles and c.slug not in failed_slugs:
                c.listing_status = "not_in_latest_listing"
                gone.append(c.name)
    s.flush()

    companies = list(s.scalars(select(Company)))
    missing_by_column = Counter(f for c in companies for f in (c.missing_fields or []))
    summary = {
        "snapshot_id": snapshot_id, "taken_at": now.isoformat(timespec="seconds"),
        "directory_url": cs.DIRECTORY_URL, "method": listing.method, "pages_read": listing.pages_read,
        "announced_pages": listing.max_page, "loaded_card_count": listing.card_count,
        "unique_listed_profiles": len(listing.slugs), "stable_end": listing.stable_end,
        "profiles_opened": len(seen_profiles), "found_outside_listing": found_outside_listing,
        "new_records": new_records, "duplicates": duplicates, "failed_urls": failed,
        "listing_errors": listing.errors, "not_in_latest_listing": gone, "companies_stored": len(companies),
        "missing_fields_by_column": {f: missing_by_column.get(f, 0) for f in cs.PROFILE_FIELDS},
        "membership_classification": "not published per organisation; left as " + NOT_DISCLOSED,
        "coverage_statement": (
            f"The public directory listed {len(listing.slugs)} unique profiles on {listing.max_page} pages; "
            f"the page after the last one loaded no further cards."
            if listing.stable_end else
            "The directory crawl did not reach a confirmed end, so complete coverage is not claimed."),
    }
    if seed is not None:
        summary.update(reconcile_seed(s, seed, client))
    s.merge(DirectorySnapshot(id=snapshot_id, kind="live_crawl", source=cs.DIRECTORY_URL, taken_at=now,
                              stable_end=listing.stable_end, card_count=listing.card_count,
                              unique_profiles=len(listing.slugs), summary=summary))
    s.flush()
    return summary


def _store_minimal(s: Session, rec: cs.MemberRecord) -> Company:
    """Used when no profile builder is passed (tests, dry runs): directory fields only."""
    c = s.scalar(select(Company).where(Company.slug == rec.slug))
    if c is None:
        c = Company(slug=rec.slug, name=rec.name, priority_domains=[])
        s.add(c)
    for f in ("name", "website", "directory_url", "description", "industry", "location", "employees", "founded"):
        setattr(c, f, getattr(rec, f))
    s.flush()
    return c


def latest_snapshot(s: Session) -> DirectorySnapshot | None:
    return s.scalar(select(DirectorySnapshot).where(DirectorySnapshot.kind == "live_crawl")
                    .order_by(DirectorySnapshot.taken_at.desc()))
