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


def list_member_slugs(client: HttpClient) -> list[str]:
    slugs: set[str] = set()
    for url in DIRECTORY_INDEX_PAGES:
        res = client.get(url, ttl_hours=24, check_robots=True)
        if res.ok:
            slugs.update(re.findall(r"bluesciencepark\.se/medlem/([a-z0-9\-]+)/", res.text))
    return sorted(slugs)


_FIELDS = re.compile(r"^(?P<industry>.*?)\s+(?:(?P<employees>\d+\+|\d+-\d+|\d+)\s+)?(?P<founded>\d{4})\s+"
                     r"(?P<location>.*)\s+(?P<web>\S+)$")


def parse_member_page(html: str, slug: str, url: str, retrieved_at: datetime) -> MemberRecord | None:
    """Parse one directory page. Returns None when the expected structure is missing (never guesses)."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    name = re.sub(r"\s*[-|]\s*Blue Science Park\s*$", "", title).strip()
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
        industry=f.group("industry").strip() if f else None,
        employees=f.group("employees") if f else None,
        founded=f.group("founded") if f else None,
        location=re.sub(r"\s+,", ",", f.group("location")).strip() if f else None,
        website=website, directory_url=url, retrieved_at=retrieved_at)


def fetch_member_directory(client: HttpClient, limit: int | None = None) -> tuple[list[MemberRecord], list[str]]:
    records, errors = [], []
    for slug in list_member_slugs(client)[:limit]:
        url = f"{BSP_BASE}/medlem/{slug}/"
        res = client.get(url, ttl_hours=24 * 3, check_robots=True)
        if not res.ok:
            errors.append(f"{url}: {res.error}")
            continue
        rec = parse_member_page(res.text, slug, url, res.retrieved_at)
        if rec is None:
            errors.append(f"{url}: unexpected page structure, skipped")
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


def crawl_company_site(client: HttpClient, website: str, max_pages: int = 8) -> CrawlResult:
    """Read the start page plus a few informative same-host pages."""
    result = CrawlResult(website=website)
    start = client.get(website, ttl_hours=24 * 3, check_robots=True)
    if not start.ok:
        result.errors.append(f"{website}: {start.error}")
        return result
    host = urlparse(start.final_url or website).netloc
    soup = BeautifulSoup(start.text, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        u = urljoin(start.final_url or website, a["href"]).split("#")[0]
        if urlparse(u).netloc == host and u.rstrip("/") != (start.final_url or website).rstrip("/") \
                and not _SKIP_PATH.search(u) and u not in links and "/en/" not in u:
            links.append(u)
    links.sort(key=lambda u: (0 if _PRIORITY_PATH.search(urlparse(u).path) else 1, urlparse(u).path.count("/"), len(u)))
    seen_sentences: set[str] = set()
    for url, res in [(website, start)] + [(u, None) for u in links[: max_pages - 1]]:
        res = res or client.get(url, ttl_hours=24 * 3, check_robots=True)
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
