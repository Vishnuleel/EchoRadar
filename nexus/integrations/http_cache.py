"""Polite HTTP client with on-disk cache, robots.txt checks and retrieval timestamps.

Every response is cached under data/cache/<sha1>.json together with the time it was retrieved, so
* repeated runs do not hit the public sources again (incremental updates),
* the demo can run offline from the last snapshot (NEXUS_OFFLINE=1), and
* each fact can carry the exact retrieval timestamp of the page it came from.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from nexus.utils.config import get_settings
from nexus.utils.logging import get_logger
from nexus.utils.validators import utcnow

log = get_logger(__name__)
USER_AGENT = "EchoRadar-innovation-prototype/0.1 (BUILD Hackathon research prototype)"


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: str  # ok | cached | error | blocked_robots | offline
    http_status: int | None
    text: str
    retrieved_at: datetime | None
    final_url: str | None = None
    error: str | None = None

    def json(self):
        return json.loads(self.text)


class HttpClient:
    def __init__(self, cache_dir=None, offline: bool | None = None, min_interval: float = 0.4, session=None):
        st = get_settings()
        self.cache_dir = cache_dir or st.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline = st.offline if offline is None else offline
        self.min_interval = min_interval
        self.session = session or requests.Session()
        self._last_call: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self.events: list[FetchResult] = []  # drained into RetrievalLog by the pipeline

    def _path(self, url: str):
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")

    def _read_cache(self, url: str):
        p = self._path(url)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        return None

    def allowed_by_robots(self, url: str) -> bool:
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            res = self.get(base + "/robots.txt", ttl_hours=24 * 7, check_robots=False, timeout=15)
            if res.ok and res.http_status == 200 and "<html" not in res.text[:300].lower():
                rp = RobotFileParser()
                rp.parse(res.text.splitlines())
                self._robots[base] = rp
            else:
                self._robots[base] = None  # no robots.txt => no stated restriction
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, ttl_hours: float = 24, headers: dict | None = None, timeout: float = 40,
            check_robots: bool = False, force: bool = False) -> FetchResult:
        cached = self._read_cache(url)
        if cached and not force:
            ts = datetime.fromisoformat(cached["retrieved_at"])
            if self.offline or utcnow() - ts < timedelta(hours=ttl_hours):
                res = FetchResult(url, True, "cached", cached.get("http_status"), cached["text"], ts,
                                  cached.get("final_url"))
                self.events.append(res)
                return res
        if self.offline:
            res = FetchResult(url, False, "offline", None, "", None, error="offline mode and no cached copy")
            self.events.append(res)
            return res
        if check_robots and not self.allowed_by_robots(url):
            res = FetchResult(url, False, "blocked_robots", None, "", None, error="disallowed by robots.txt")
            self.events.append(res)
            return res
        host = urlparse(url).netloc
        wait = self.min_interval - (time.time() - self._last_call.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.session.get(url, headers={"User-Agent": USER_AGENT, **(headers or {})}, timeout=timeout)
            self._last_call[host] = time.time()
            if r.status_code != 200:
                res = FetchResult(url, False, "error", r.status_code, r.text[:2000], None, r.url,
                                  error=f"HTTP {r.status_code}")
            else:
                if not r.encoding or r.encoding.lower() == "iso-8859-1":
                    r.encoding = r.apparent_encoding or "utf-8"
                now = utcnow()
                self._path(url).write_text(json.dumps({"url": url, "final_url": r.url, "http_status": 200,
                                                       "retrieved_at": now.isoformat(), "text": r.text},
                                                      ensure_ascii=False), encoding="utf-8")
                res = FetchResult(url, True, "ok", 200, r.text, now, r.url)
        except requests.RequestException as exc:
            res = FetchResult(url, False, "error", None, "", None, error=f"{type(exc).__name__}: {exc}"[:500])
        if not res.ok and cached:  # stale cache is better than nothing, but say so
            ts = datetime.fromisoformat(cached["retrieved_at"])
            log.warning("Live fetch failed for %s (%s); using cached copy from %s", url, res.error, ts)
            res = FetchResult(url, True, "cached", cached.get("http_status"), cached["text"], ts,
                              cached.get("final_url"), error=f"live fetch failed: {res.error}")
        self.events.append(res)
        return res
