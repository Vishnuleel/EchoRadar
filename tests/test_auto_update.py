"""The website keeps itself current: the monitor's wake-up re-ranks only when a source changed, the API's
background worker survives a failing cycle, and the health endpoint reports it. No network: the
monitor run is replaced by a fake report."""
from nexus import monitor, pipeline
from tests.test_api import api  # noqa: F401  (fixture)


def _fake_run(changes):
    return lambda s, batch=6, **kw: {"ran": [{"source": "vinnova", "ok": True}], "changes": changes, "failed": 0}


def test_a_wake_up_reranks_only_when_something_changed(session, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "translate_new_texts", lambda s: {"agent": "translate"})
    monkeypatch.setattr(pipeline, "recompute", lambda s, emb: calls.append("recompute") or [])
    monkeypatch.setattr(pipeline, "save_trace", lambda trace, backend: calls.append("save"))
    monkeypatch.setattr(monitor, "run_due", _fake_run(0))
    assert monitor.cycle(session)["reranked"] is False and calls == []
    monkeypatch.setattr(monitor, "run_due", _fake_run(3))
    assert monitor.cycle(session)["reranked"] is True and calls == ["recompute", "save"]  # save rewrites last_run.json


def test_background_worker_records_its_state_and_survives_a_failure(monkeypatch):
    from api.background import AutoMonitor

    w = AutoMonitor(interval=600)
    assert not w.enabled  # NEXUS_AUTO_MONITOR=0 in tests: never started by the test suite
    monkeypatch.setattr(monitor, "cycle", lambda s, batch=6: {"ran": [1, 2], "changes": 1, "failed": 0, "reranked": True})
    w.cycle_once()
    assert w.state["last_report"] == {"ran": 2, "changes": 1, "failed": 0, "reranked": True, "skipped": None}
    assert w.state["next_cycle_at"] > w.state["last_cycle_at"] and not w.state["running"]

    def boom(s, batch=6):
        raise RuntimeError("source down")
    monkeypatch.setattr(monitor, "cycle", boom)
    assert w.cycle_once() is None and "source down" in w.state["last_error"]  # the site keeps working


def test_health_reports_the_update_status(api):  # noqa: F811
    client, _, _ = api
    h = client.get("/api/health").json()
    assert h["auto_monitor"]["enabled"] is False and h["auto_monitor"]["interval_seconds"] > 0
