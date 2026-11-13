"""Blue Science Park and Marine Technology Center of Sweden: events and dated news.

Events come from the published Onsdagslunch programme and the event overview page. The pages
contain template placeholder blocks ("Lorem ipsum"); those are detected and dropped. The page
states weekday, day and month but not the year, so the parsed date carries an explicit note.
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from nexus.integrations.company_sources import html_to_sentences
from nexus.integrations.http_cache import HttpClient

BSP = "https://www.bluesciencepark.se"
EVENT_PROGRAMME_URL = BSP + "/onsdagslunch-med-blue-science-park/"
EVENT_OVERVIEW_URL = BSP + "/event/"
BSP_NEWS_URL = BSP + "/aktuellt/"
MTC_NEWS_URL = "https://www.mtcos.se/nyheter-event/"
CONTACT_URL = BSP + "/kontakt/"
CONTACT_EMAIL_PUBLIC = "info@bluesciencepark.se"  # published on the contact page

_SV_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10,
              "nov": 11, "dec": 12}
_EN_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
              "september": 9, "october": 10, "november": 11, "december": 12, "januari": 1, "februari": 2, "mars": 3,
              "maj": 5, "juni": 6, "juli": 7, "augusti": 8, "oktober": 10}
_OCCASION = re.compile(
    r"(?:När: )?(?P<date>(?:Måndagen|Tisdagen|Onsdagen|Torsdagen|Fredagen) den (?P<day>\d{1,2}) (?P<month>[a-zåäö]+)) "
    r"Tid: (?P<time>\d{1,2}[:.]\d{2} ?[-–] ?\d{1,2}[:.]\d{2})(?: \([^)]*\))?(?: Plats: (?P<place>.+?)(?= Föreläsningen| Under | Hur | Vad | Många |$))?")


def _flat_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "form"]):
        t.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    cut = text.find("Hantera samtycke")
    return text[:cut] if cut > 0 else text


def parse_event_programme(html: str, url: str, retrieved_at: datetime) -> list[dict]:
    """Dated occasions from the Onsdagslunch programme page."""
    text = _flat_text(html)
    soup = BeautifulSoup(html, "html.parser")
    headings = [" ".join(h.get_text(" ", strip=True).split()) for h in soup.find_all(["h2", "h3", "h4", "h5"])]
    headings = [h for h in headings if 6 <= len(h) <= 140 and not re.search(r"tillfällen|Talare|^När", h)]
    events, seen = [], set()
    matches = list(_OCCASION.finditer(text))
    for i, m in enumerate(matches):
        after = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else m.end() + 500]
        if "lorem ipsum" in after[:200].lower():
            continue  # template placeholder block left on the page, not a real event
        # the title is the page heading that appears last before the date
        title, best = "", -1
        for h in headings:
            pos = text.rfind(h, max(0, m.start() - 260), m.start())
            if pos > best:
                title, best = h, pos
        month = _SV_MONTHS.get(m.group("month")[:3].lower())
        if not title or len(title) < 6 or month is None:
            continue
        key = (title.lower(), m.group("date"))
        if key in seen:
            continue
        seen.add(key)
        h, mi = re.split(r"[:.]", m.group("time").split("-")[0].split("–")[0].strip())[:2]
        starts = datetime(retrieved_at.year, month, int(m.group("day")), int(h), int(mi))
        desc = re.split(r" Till anmälan| Talare ", after.strip())[0].strip()
        events.append({
            "key": f"bsp-onsdagslunch:{starts:%m-%d}:{title[:60].lower()}", "title": f"Onsdagslunch: {title}",
            "description": desc[:600] or None, "date_text": f"{m.group('date')}, {m.group('time')}", "starts_at": starts,
            "date_note": f"The page gives no year; {retrieved_at.year} is assumed from the retrieval date.",
            "time_text": m.group("time"), "location": (m.group("place") or "").strip(" .") or None,
            "format": "in_person" if m.group("place") else "unknown",
            "audience": "Companies, public sector, academia and other actors in the Blue Science Park ecosystem "
                        "(as described on the programme page)",
            "organiser": "Blue Science Park", "source_url": url, "retrieved_at": retrieved_at})
    return events


def parse_event_overview(html: str, url: str, retrieved_at: datetime) -> list[dict]:
    """Recurring event formats listed on the overview page. No dates are published there."""
    _, sentences, _ = html_to_sentences(html)
    text = _flat_text(html)
    formats = [("Marine Innovation Day", "Marine Technology Center of Sweden", r"Marine Innovation Day\s+(Är en dag[^.]+\.)"),
               ("TCL & Friends", "Tech Concept Lab", r"TCL & Friends\s+(En serie träffar[^.]+\.)")]
    out = []
    for name, organiser, pattern in formats:
        m = re.search(pattern, text)
        if m:
            out.append({"key": f"bsp-format:{name.lower()}", "title": name, "description": m.group(1), "date_text": None,
                        "starts_at": None, "date_note": "Recurring format. No date is published on the source page.",
                        "time_text": None, "location": None, "format": "unknown", "audience": None,
                        "organiser": organiser, "source_url": url, "retrieved_at": retrieved_at})
    return out


def fetch_events(client: HttpClient) -> tuple[list[dict], list[str]]:
    events, errors = [], []
    for url, parser in ((EVENT_PROGRAMME_URL, parse_event_programme), (EVENT_OVERVIEW_URL, parse_event_overview)):
        res = client.get(url, ttl_hours=24, check_robots=True)
        if not res.ok:
            errors.append(f"{url}: {res.error}")
            continue
        events += parser(res.text, url, res.retrieved_at)
    return events, errors


def _parse_news_date(text: str) -> datetime | None:
    m = re.search(r"(\d{1,2}) ([a-zåäö]{3})[a-zåäö]* (\d{4})", text, re.I)  # 13 nov 2026
    if m and m.group(2).lower() in _SV_MONTHS:
        return datetime(int(m.group(3)), _SV_MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"([a-zåäö]+) (\d{1,2}), (\d{4})", text, re.I)  # september 29, 2026
    if m and m.group(1).lower() in _EN_MONTHS:
        return datetime(int(m.group(3)), _EN_MONTHS[m.group(1).lower()], int(m.group(2)))
    return None


def parse_news_listing(html: str, link_pattern: str) -> list[dict]:
    """Titles, URLs and dates from a news listing. The date is read from the text next to the link."""
    soup = BeautifulSoup(html, "html.parser")
    text = _flat_text(html)
    items, seen = [], set()
    for a in soup.find_all("a", href=re.compile(link_pattern)):
        title = " ".join(a.get_text(" ", strip=True).split())
        url = a["href"].split("#")[0]
        if len(title) < 12 or url in seen:
            continue
        lead = re.match(r"(\d{1,2} [a-zåäö]{3,9} \d{4}) (.+)", title, re.I)
        if lead:  # the link text itself starts with the date
            published, title = _parse_news_date(lead.group(1)), lead.group(2)
        else:
            pos = text.find(title)
            published = _parse_news_date(text[pos + len(title): pos + len(title) + 24]) if pos >= 0 else None
        seen.add(url)
        items.append({"title": title, "source_url": url, "published_at": published})
    return items


def fetch_news(client: HttpClient, max_items: int = 14) -> tuple[list[dict], list[str]]:
    out, errors = [], []
    for listing, pattern, source in ((BSP_NEWS_URL, r"bluesciencepark\.se/aktuellt/[^/]+/?$", "Blue Science Park news"),
                                     (MTC_NEWS_URL, r"mtcos\.se/news/[^/]+/?$", "Marine Technology Center of Sweden news")):
        res = client.get(listing, ttl_hours=12, check_robots=True)
        if not res.ok:
            errors.append(f"{listing}: {res.error}")
            continue
        items = parse_news_listing(res.text, pattern)
        items.sort(key=lambda i: i["published_at"] or datetime(1900, 1, 1), reverse=True)
        for item in items[:max_items]:
            art = client.get(item["source_url"], ttl_hours=24 * 14, check_robots=True)
            sentences = []
            if art.ok:
                _, sentences, _ = html_to_sentences(art.text)
                sentences = [x for x in sentences if not x.startswith(item["title"][:40]) and len(x) > 50]
            item.update(summary=" ".join(sentences[:2])[:600] or None, body=" ".join(sentences[:12]),
                        source_name=source, retrieved_at=(art.retrieved_at if art.ok else res.retrieved_at))
            out.append(item)
    return out, errors
