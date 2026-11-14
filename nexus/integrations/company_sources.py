"""Public company information: Blue Science Park member directory + official company websites.

Only publicly reachable pages are read, robots.txt is respected, and nothing is filled in when a
page cannot be read. Every text block keeps the exact URL and retrieval time it came from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from nexus.integrations.http_cache import HttpClient

BSP_BASE = "https://www.bluesciencepark.se"
DIRECTORY_INDEX_PAGES = [BSP_BASE + "/", BSP_BASE + "/bli-medlem/"]
_SKIP_PATH = re.compile(r"(kontakt|contact|privacy|integritet|cookie|karri|career|lediga|login|wp-|webbshop|"
                        r"ladda-ner|download|\?s=|investerare|crew|vart-team|policy|\.pdf|\.jpg|\.png|/feed)", re.I)
_PRIORITY_PATH = re.compile(r"(om-oss|about|erbjudande|produkt|product|service|tjanst|innovation|"
                            r"kundsegment|undervatten|dyk|vatten|equipment|news|nyheter|ubat)", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ0-9])")


@dataclass
class MemberRecord:
    slug: str
    name: str
    description: str
    industry: str | None
    employees: str | None
    founded: str | None
    location: str | None
    website: str | None
    directory_url: str
    retrieved_at: datetime
    related_slugs: list[str] = field(default_factory=list)  # the profile's "Fler medlemmar" links
    from_cache_after_failure: bool = False  # live fetch failed; parsed from the last cached copy

    def missing_fields(self) -> list[str]:
        """Fields the official profile page does not publish (left empty, never guessed)."""
        return [k for k in PROFILE_FIELDS if not getattr(self, k)]


# The facts copied from an official Blue Science Park profile page, in display order.
PROFILE_FIELDS = ("name", "description", "industry", "employees", "founded", "location", "website")


@dataclass
class DirectoryListing:
    """What the public member directory listed, read page by page like its "Ladda mer" button does."""
    slugs: list[str] = field(default_factory=list)  # unique profile slugs in listing order
    card_count: int = 0  # directory cards loaded across all pages (before de-duplication)
    pages_read: list[str] = field(default_factory=list)
    max_page: int | None = None  # the page count the directory itself announces
    stable_end: bool = False  # True only when the last announced page was read and nothing more loads
    method: str = "paginated_grid"  # paginated_grid | link_scan (fallback when the grid markup is missing)
    errors: list[str] = field(default_factory=list)


@dataclass
class PageText:
    url: str
    title: str
    sentences: list[str]
    retrieved_at: datetime
    lang: str | None = None


@dataclass
class CrawlResult:
    website: str
    pages: list[PageText] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


DIRECTORY_URL = BSP_BASE + "/bli-medlem/"
_SLUG_RE = re.compile(r"bluesciencepark\.se/medlem/([a-z0-9\-]+)/?")


def _slug(href: str) -> str | None:
    m = _SLUG_RE.search(href or "")
    return m.group(1) if m else None


def list_directory(client: HttpClient, ttl_hours: float = 24, max_pages: int = 30) -> DirectoryListing:
    """Read the member directory to its end.

    The directory is an Elementor loop grid: "Ladda mer" loads /bli-medlem/2/, /3/, ... and the grid
    announces its last page in `data-max-page`. Reading those pages over plain HTTP gives exactly what
    clicking the button gives. The listing only counts as complete (`stable_end`) when the announced
    last page was read and the page after it adds no cards.
    """
    out = DirectoryListing()
    for page in range(1, max_pages + 1):
        url = DIRECTORY_URL if page == 1 else f"{DIRECTORY_URL}{page}/"
        res = client.get(url, ttl_hours=ttl_hours, check_robots=True)
        if not res.ok:
            out.errors.append(f"{url}: {res.error}")
            return out  # an unread page means the end was not reached
        out.pages_read.append(url)
        soup = BeautifulSoup(res.text, "html.parser")
        grid = soup.select_one('[data-widget_type="loop-grid.post"]')
        if grid is None and page == 1:  # markup changed: take every profile link on the page, and say so
            out.method = "link_scan"
            for s in (_slug(a["href"]) for a in soup.find_all("a", href=True)):
                if s and s not in out.slugs:
                    out.slugs.append(s)
            out.card_count = len(out.slugs)
            return out
        items = grid.select(".e-loop-item") if grid is not None else []
        if not items:  # the page after the last one: nothing more loads
            out.stable_end = out.max_page is not None and page > out.max_page
            return out
        for item in items:
            a = item.find("a", href=_SLUG_RE)
            s = _slug(a["href"]) if a else None
            if s:
                out.card_count += 1
                if s not in out.slugs:
                    out.slugs.append(s)
        anchor = soup.select_one(".e-load-more-anchor")
        if anchor is not None and anchor.get("data-max-page", "").isdigit():
            out.max_page = int(anchor["data-max-page"])
        if out.max_page is None:  # no pagination announced: a single page, end not confirmed
            return out
    out.errors.append(f"stopped after {max_pages} pages without reaching the end")
    return out


def list_member_slugs(client: HttpClient) -> list[str]:
    """Unique profile slugs, plus profile links on the start page (kept for older call sites)."""
    listing = list_directory(client)
    slugs = list(listing.slugs)
    res = client.get(BSP_BASE + "/", ttl_hours=24, check_robots=True)
    if res.ok:
        slugs += [s for s in _SLUG_RE.findall(res.text) if s not in slugs]
    return slugs


_FIELDS = re.compile(r"^(?P<industry>.*?)\s+(?:(?P<employees>\d+\+|\d+-\d+|\d+)\s+)?(?P<founded>\d{4})\s+"
                     r"(?P<location>.*)\s+(?P<web>\S+)$")


def _list_text(value: str | None) -> str | None:
    """'A , B' (an artefact of reading the page text) -> 'A, B'. Values are otherwise unchanged."""
    return re.sub(r"\s+,", ",", value).strip() if value else value


def parse_member_page(html: str, slug: str, url: str, retrieved_at: datetime) -> MemberRecord | None:
    """Parse one directory page. Returns None when the expected structure is missing (never guesses)."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    h1 = soup.find("h1")
    heading = " ".join(h1.get_text(" ", strip=True).split()) if h1 else ""
    # The page heading is the name exactly as displayed (e.g. "AddSecure – Smartgrids"); <title> is a fallback.
    name = heading or re.sub(r"\s*[-|]\s*Blue Science Park\s*$", "", title).strip()
    related = []
    m_rel = re.search(r"Fler medlemmar", html)
    if m_rel:
        for s in _SLUG_RE.findall(html[m_rel.start():]):
            if s != slug and s not in related:
                related.append(s)
    website = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and not re.search(
                r"bluesciencepark|cookiedatabase|linkedin|facebook|instagram|youtube|mtcos\.se|techconceptlab", href):
            website = href
            break
    for t in soup(["script", "style"]):
        t.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    m = re.search(r"Till medlemmar (.*?) Bransch Antal anställda Grundat Ort Webb (.*?) Fler medlemmar", text)
    if not m or not name:
        return None
    head, tail = m.group(1).strip(), m.group(2).strip()
    # the directory sometimes labels the page slightly differently from <title>
    description = head[len(name):].strip() if head.lower().startswith(name.lower()) else head
    if not description.lower().startswith(name.lower()[:4]) and head != description:
        # "AddSecure – Smartgrids Erbjuder ..." style: drop a leading dash-suffix belonging to the name
        description = re.sub(r"^[–-]\s*\S+\s+", "", description)
    f = _FIELDS.match(tail)
    return MemberRecord(
        slug=slug, name=name, description=description,
        industry=_list_text(f.group("industry")) if f else None,
        employees=f.group("employees") if f else None,
        founded=f.group("founded") if f else None,
        location=_list_text(f.group("location")) if f else None,
        website=website, directory_url=url, retrieved_at=retrieved_at, related_slugs=related)


def fetch_member_profile(client: HttpClient, slug: str, ttl_hours: float = 24 * 3) -> tuple[MemberRecord | None, str]:
    """(record or None, fetch status). Status: ok | ok_cached (live fetch failed) | failed: <reason>."""
    url = f"{BSP_BASE}/medlem/{slug}/"
    res = client.get(url, ttl_hours=ttl_hours, check_robots=True)
    if not res.ok:
        return None, f"failed: {res.error}"
    final = res.final_url or url
    canonical_slug = _slug(final) or slug  # e.g. /medlem/hundtjanst-blekinge/ redirects to .../hundtjanst-blekinge-ab/
    rec = parse_member_page(res.text, canonical_slug, f"{BSP_BASE}/medlem/{canonical_slug}/", res.retrieved_at)
    if rec is None:
        return None, "failed: unexpected page structure"
    rec.from_cache_after_failure = bool(res.error)
    return rec, "ok_cached" if res.error else "ok"


def fetch_member_directory(client: HttpClient, limit: int | None = None) -> tuple[list[MemberRecord], list[str]]:
    records, errors = [], []
    for slug in list_member_slugs(client)[:limit]:
        rec, status = fetch_member_profile(client, slug)
        if rec is None:
            errors.append(f"{BSP_BASE}/medlem/{slug}/: {status.removeprefix('failed: ')}")
        else:
            records.append(rec)
    return records, errors


def html_to_sentences(html: str) -> tuple[str, list[str], str | None]:
    """Return (title, sentences, lang). Navigation, forms and scripts are removed first."""
    soup = BeautifulSoup(html, "html.parser")
    lang = soup.html.get("lang") if soup.html else None
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    for t in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "svg", "iframe"]):
        t.decompose()
    sentences, seen = [], set()
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "span", "div"]):
        if el.find(["p", "li", "div", "h1", "h2", "h3", "h4"]):
            continue  # only leaf blocks
        block = " ".join(el.get_text(" ", strip=True).split())
        for sent in _SENT_SPLIT.split(block):
            sent = sent.strip()
            if 35 <= len(sent) <= 600 and sent not in seen and not re.search(r"cookie|samtyck", sent, re.I):
                seen.add(sent)
                sentences.append(sent)
    return title, sentences, lang


# country and language copies of the same site ("/en/", "/br/", "/de-at/") repeat the start page
_LOCALE_PATH = re.compile(r"^/[a-z]{2}(?:[-_][a-z]{2})?(?:/|$)", re.I)


def crawl_company_site(client: HttpClient, website: str, max_pages: int = 8, ttl_hours: float = 24 * 3) -> CrawlResult:
    """Read the start page plus a few informative same-host pages. `ttl_hours=0` reads them live."""
    result = CrawlResult(website=website)
    start = client.get(website, ttl_hours=ttl_hours, check_robots=True)
    if not start.ok:
        result.errors.append(f"{website}: {start.error}")
        return result
    host = urlparse(start.final_url or website).netloc
    soup = BeautifulSoup(start.text, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        u = urljoin(start.final_url or website, a["href"]).split("#")[0]
        if urlparse(u).netloc == host and u.rstrip("/") != (start.final_url or website).rstrip("/") \
                and not _SKIP_PATH.search(u) and u not in links and not _LOCALE_PATH.match(urlparse(u).path):
            links.append(u)
    links.sort(key=lambda u: (0 if _PRIORITY_PATH.search(urlparse(u).path) else 1, urlparse(u).path.count("/"), len(u)))
    seen_sentences: set[str] = set()
    for url, res in [(website, start)] + [(u, None) for u in links[: max_pages - 1]]:
        res = res or client.get(url, ttl_hours=ttl_hours, check_robots=True)
        if not res.ok:
            result.errors.append(f"{url}: {res.error}")
            continue
        title, sentences, lang = html_to_sentences(res.text)
        fresh = [s for s in sentences if s not in seen_sentences]
        seen_sentences.update(fresh)
        if fresh:
            result.pages.append(PageText(url=res.final_url or url, title=title, sentences=fresh,
                                         retrieved_at=res.retrieved_at, lang=lang))
    return result
