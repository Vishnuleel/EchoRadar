"""Directory Agent: paginated listing, per-field provenance, seed reconciliation, nothing guessed or deleted."""
from sqlalchemy import select

from nexus.agents import directory_agent as da
from nexus.database.models import Company, DirectorySnapshot
from nexus.integrations import company_sources as cs
from nexus.integrations.http_cache import FetchResult
from nexus.utils.validators import utcnow
from tests.conftest import FakeClient

BSP = "https://www.bluesciencepark.se"


def grid(slugs, page=None, max_page=None):
    cards = "".join(f'<div class="e-loop-item"><a href="{BSP}/medlem/{s}/">{s}</a></div>' for s in slugs)
    anchor = (f'<div class="e-load-more-anchor" data-page="{page}" data-max-page="{max_page}" '
              f'data-next-page="{BSP}/bli-medlem/{page + 1}/"></div>') if max_page else ""
    return f'<html><body><div data-widget_type="loop-grid.post">{cards}{anchor}</div></body></html>'


def profile(name, desc, fields="Marinteknik 1-10 2010 Karlskrona x.se", related=(), website="https://x.se/"):
    rel = "".join(f'<a href="{BSP}/medlem/{r}/">{r}</a>' for r in related)
    return (f"<html><head><title>{name} - Blue Science Park</title></head><body><h1>{name}</h1>"
            f"<div>Till medlemmar {name} {desc} Bransch Antal anställda Grundat Ort Webb {fields} Fler medlemmar {rel}</div>"
            f'<a href="{website}">site</a></body></html>')


class RedirectingClient(FakeClient):
    """FakeClient that also follows the redirects given in `redirects` (old slug -> current URL)."""

    def __init__(self, responses, redirects=None):
        super().__init__(responses)
        self.redirects = redirects or {}

    def get(self, url, **kw):
        target = self.redirects.get(url)
        res = super().get(target or url, **kw)
        return FetchResult(url, res.ok, res.status, res.http_status, res.text, res.retrieved_at, target or res.final_url,
                           res.error)


def directory_client(extra=None, redirects=None):
    # longer URL prefixes first: FakeClient matches by prefix
    responses = {
        f"{BSP}/bli-medlem/3/": grid([]),
        f"{BSP}/bli-medlem/2/": grid(["beta", "alpha"], 2, 2),  # "alpha" listed twice: one card, no new profile
        f"{BSP}/bli-medlem/": grid(["alpha"], 1, 2),
        f"{BSP}/medlem/alpha/": profile("Alpha", "Erbjuder sonar och hydroakustiska system.", related=["gamma"]),
        f"{BSP}/medlem/beta/": profile("Beta AB", "Installation av sjökabel.", fields="Sjökabelinstallation 2012 Karlskrona , Malmö y.se",
                                       website="https://y.se/kabel/"),
        f"{BSP}/medlem/gamma/": profile("Gamma", "Konsulter inom AI och maskininlärning."),
        f"{BSP}/robots.txt": "User-agent: *\nDisallow:",
        **(extra or {}),
    }
    return RedirectingClient(responses, redirects)


def test_listing_reads_every_page_and_confirms_the_end():
    listing = cs.list_directory(directory_client())
    assert listing.slugs == ["alpha", "beta"] and listing.card_count == 3 and listing.max_page == 2
    assert listing.stable_end and listing.method == "paginated_grid" and len(listing.pages_read) == 3


def test_listing_without_a_readable_last_page_is_not_complete():
    client = FakeClient({f"{BSP}/bli-medlem/2/": (503, "down"), f"{BSP}/bli-medlem/": grid(["alpha"], 1, 2)})
    listing = cs.list_directory(client)
    assert listing.slugs == ["alpha"] and not listing.stable_end and listing.errors


def test_profile_heading_is_the_name_and_list_fields_are_clean():
    rec = cs.parse_member_page(
        "<html><head><title>AddSecure - Smartgrids - Blue Science Park</title></head><body><h1>AddSecure – Smartgrids</h1>"
        "<div>Till medlemmar AddSecure – Smartgrids Erbjuder kommunikationsplattformar för elnät. Bransch Antal anställda "
        "Grundat Ort Webb IoT 200+ 2000 Karlskrona , Stockholm addsecure.se Fler medlemmar</div></body></html>",
        "addsecure", f"{BSP}/medlem/addsecure/", utcnow())
    assert rec.name == "AddSecure – Smartgrids" and rec.description.startswith("Erbjuder")
    assert rec.location == "Karlskrona, Stockholm" and rec.employees == "200+"


def test_sync_records_provenance_and_never_guesses(session):
    session.add(Company(slug="delisted", name="Delisted Co", directory_url=f"{BSP}/medlem/delisted/", priority_domains=[]))
    session.flush()
    summary = da.sync_directory(session, directory_client())
    by_slug = {c.slug: c for c in session.scalars(select(Company))}

    assert summary["stable_end"] and summary["loaded_card_count"] == 3 and summary["unique_listed_profiles"] == 2
    assert by_slug["gamma"].listing_status == "related_link_only"  # found through "Fler medlemmar", kept apart
    assert by_slug["delisted"].listing_status == "not_in_latest_listing"  # flagged, not deleted
    beta = by_slug["beta"]
    assert beta.missing_fields == ["employees"] and beta.employees is None  # not published: left empty
    for f, src in beta.field_sources.items():  # every stored fact points at the exact profile page
        assert src["url"] == f"{BSP}/medlem/beta/" and src["value"] == getattr(beta, f) and src["retrieved_at"]
    assert beta.field_sources["website"]["value"] == "https://y.se/kabel/"
    assert all(c.membership_classification == da.NOT_DISCLOSED for c in by_slug.values())
    snap = session.get(DirectorySnapshot, summary["snapshot_id"])
    assert snap.stable_end and snap.unique_profiles == 2 and snap.summary["missing_fields_by_column"]["employees"] == 1


def test_seed_is_a_second_source_and_never_overwrites_the_live_page(session):
    seed = {"dataset_name": "audited seed", "version": "3", "audit_date": "2026-11-13", "records": [
        {"organisation_name": "Alpha", "description_original_sv": "Alpha gör sonar (omskriven text).",
         "industry_original_sv": ["Marinteknik"], "employee_range": "1-10", "founded_year": 2010, "locations": ["Karlskrona"],
         "official_website": "https://x.se/", "blue_science_park_profile_url": f"{BSP}/medlem/alpha/",
         "membership_classification": "member"},
        {"organisation_name": "Beta", "description_original_sv": "Installation av sjökabel.", "industry_original_sv": [],
         "employee_range": "11-50", "founded_year": None, "locations": [], "official_website": "",
         "blue_science_park_profile_url": f"{BSP}/medlem/old-beta/"},  # old slug, redirects to /beta/
        {"organisation_name": "Nowhere AB", "description_original_sv": "x", "industry_original_sv": [], "employee_range": "",
         "founded_year": None, "locations": [], "official_website": "", "blue_science_park_profile_url": f"{BSP}/medlem/nowhere/"},
    ]}
    client = directory_client(redirects={f"{BSP}/medlem/old-beta/": f"{BSP}/medlem/beta/"})
    summary = da.sync_directory(session, client, seed=seed)
    alpha = session.scalar(select(Company).where(Company.slug == "alpha"))
    beta = session.scalar(select(Company).where(Company.slug == "beta"))

    assert alpha.description == "Erbjuder sonar och hydroakustiska system."  # official text kept
    d = alpha.field_sources["description"]
    assert d["url"] == f"{BSP}/medlem/alpha/" and d["seed"]["agrees"] is False and "omskriven" in d["seed"]["value"]
    assert alpha.field_sources["website"]["seed"]["agrees"] is True
    assert alpha.membership_classification == da.NOT_DISCLOSED  # a bare claim in the seed is not a source
    assert f"{BSP}/medlem/old-beta/" in beta.aliases and beta.employees is None  # seed's "11-50" is not copied in
    assert beta.field_sources["employees"]["seed"]["value"] == "11-50" and beta.field_sources["employees"]["value"] is None
    assert summary["seed_matches"] == 2 and summary["seed_unmatched"] == [{"name": "Nowhere AB", "profile_url": f"{BSP}/medlem/nowhere/"}]
    assert any(f["url"].endswith("/nowhere/") for f in summary["failed_urls"])
    assert summary["seed_disagreements_by_field"]["description"] == 1
