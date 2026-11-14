"""Keeps the website current while it runs: the source monitor, in a background thread of the API.

Every NEXUS_MONITOR_INTERVAL seconds (default 900) the worker runs the monitoring checks that are due
(each source has its own schedule, see nexus/monitor.py) and, if any source changed, re-ranks. The
re-ranking rewrites data/last_run.json, which drops the API's cached pages; the browser notices the
new ranking time through /api/health and refetches. Nothing has to be restarted.

Off when NEXUS_AUTO_MONITOR=0 or NEXUS_OFFLINE=1. The monitor's lease lock means an external
`python -m nexus.monitor --loop` and this worker never scan at the same time.
"""
from __future__ import annotations

import os
import threading
from datetime import timedelta

from nexus.utils.config import get_settings
from nexus.utils.logging import get_logger
from nexus.utils.validators import utcnow

log = get_logger(__name__)


class AutoMonitor:
    def __init__(self, interval: float | None = None, first_delay: float = 60.0):
        self.interval = interval or float(os.getenv("NEXUS_MONITOR_INTERVAL", "900"))
        self.first_delay = first_delay  # let the language model load and the first pages render first
        self.enabled = os.getenv("NEXUS_AUTO_MONITOR", "1") != "0" and not get_settings().offline
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = {"enabled": self.enabled, "interval_seconds": self.interval, "running": False,
                      "last_cycle_at": None, "next_cycle_at": None, "last_report": None, "last_error": None}

    def start(self) -> None:
        if not self.enabled or self._thread:
            return
        self.state["next_cycle_at"] = utcnow() + timedelta(seconds=self.first_delay)
        self._thread = threading.Thread(target=self._run, name="nexus-auto-monitor", daemon=True)
        self._thread.start()
        log.info("Auto-monitor started: every %.0f s", self.interval)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        delay = self.first_delay
        while not self._stop.wait(delay):
            self.cycle_once()
            delay = self.interval

    def cycle_once(self) -> dict | None:
        from nexus import monitor
        from nexus.database.database import get_sessionmaker

        self.state["running"] = True
        s = get_sessionmaker()()
        try:
            report = monitor.cycle(s)
            self.state["last_report"] = {"ran": len(report["ran"]), "changes": report["changes"],
                                         "failed": report.get("failed", 0), "reranked": report["reranked"],
                                         "skipped": report.get("skipped")}
            self.state["last_error"] = None
            if report["ran"]:
                log.info("Auto-monitor: %d checks, %d changes%s", len(report["ran"]), report["changes"],
                         ", re-ranked" if report["reranked"] else "")
            return report
        except Exception as exc:  # the website must keep working whatever a source does
            log.warning("Auto-monitor cycle failed: %s", exc)
            self.state["last_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            return None
        finally:
            s.close()
            now = utcnow()
            self.state.update(running=False, last_cycle_at=now, next_cycle_at=now + timedelta(seconds=self.interval))


auto_monitor = AutoMonitor()
