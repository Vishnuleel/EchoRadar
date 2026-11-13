"""Shared plumbing: JSON encoding, database session, the simulated sign-in header and the result cache."""
from __future__ import annotations

import json
import math
import threading
from dataclasses import asdict, is_dataclass
from datetime import date, datetime

import numpy as np
from fastapi import Header
from starlette.responses import Response

from nexus.database.database import get_sessionmaker
from nexus.utils.config import DATA_DIR


def clean(o):
    """Make engine output JSON-safe: datetimes, numpy scalars, sets, tuples, dataclasses, NaN."""
    if o is None or isinstance(o, (str, bool, int)):
        return o
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, np.generic):
        return clean(o.item())
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [clean(v) for v in o]
    if is_dataclass(o):
        return clean(asdict(o))
    return str(o)


class NexusJSON(Response):
    media_type = "application/json"

    def render(self, content) -> bytes:
        return json.dumps(clean(content), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def get_db():
    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


def acting_company(x_acting_company: str | None = Header(default=None)) -> int | None:
    """SIMULATED sign-in: the frontend sends the company chosen under 'Acting as'.

    The authorisation checks that use this value (nexus.security.privacy) are real.
    """
    try:
        return int(x_acting_company) if x_acting_company not in (None, "", "null") else None
    except ValueError:
        return None


class Cache:
    """In-memory results, computed once. Dropped when data changes (feedback, refinement, ingest).

    `data/last_run.json` is rewritten by every recompute / ingest run, so its modification time is
    used to notice changes made outside this process (e.g. `python scripts/ingest.py`).
    """

    def __init__(self):
        self._data: dict[str, object] = {}
        self._lock = threading.RLock()
        self._stamp = None

    def _check(self):
        p = DATA_DIR / "last_run.json"
        stamp = p.stat().st_mtime if p.exists() else None
        if stamp != self._stamp:
            self._data.clear()
            self._stamp = stamp

    def get(self, key: str, build):
        with self._lock:
            self._check()
            if key not in self._data:
                self._data[key] = build()
            return self._data[key]

    def drop_company(self, company_id: int):
        """Forget what depends on one company's radar marks."""
        with self._lock:
            for key in [k for k in self._data if k.endswith(f"@{company_id}")]:
                del self._data[key]

    def clear(self):
        with self._lock:
            self._data.clear()


cache = Cache()
write_lock = threading.Lock()  # one recompute at a time
