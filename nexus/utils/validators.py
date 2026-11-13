"""Small, dependency-free validation helpers used by agents, the UI and tests."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite stores naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_valid_url(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        p = urlparse(url.strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and "." in p.netloc and " " not in url.strip()


def parse_date(value) -> datetime | None:
    """Parse ISO-like dates from APIs. Returns None instead of guessing."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26] if "." in s else s[:19] if "T" in s else s[:10], fmt)
        except ValueError:
            continue
    return None


def age_days(ts: datetime | None, now: datetime | None = None) -> float | None:
    if ts is None:
        return None
    return ((now or utcnow()) - ts).total_seconds() / 86400.0


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(x)))
