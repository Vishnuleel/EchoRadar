"""Run the test suite and store a machine-readable summary for the Evaluation page.

    python scripts/run_tests.py            # unit + mocked integration tests
    python scripts/run_tests.py --live     # also run live tests against OpenAlex, Vinnova and the member directory
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
live = "--live" in sys.argv
xml = ROOT / "data" / "test_results.xml"
cmd = [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"] + ([] if live else ["-m", "not live"])
proc = subprocess.run(cmd, cwd=ROOT)
suite = ET.parse(xml).getroot()
suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
cases = []
for tc in suite.iter("testcase"):
    outcome = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
        "skipped" if tc.find("skipped") is not None else "passed"
    cases.append({"file": tc.get("classname", "").split(".")[-1], "name": tc.get("name"), "outcome": outcome,
                  "live": "live" in tc.get("name", ""), "seconds": float(tc.get("time", 0))})
summary = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "live_included": live,
           "total": len(cases), "passed": sum(c["outcome"] == "passed" for c in cases),
           "failed": sum(c["outcome"] == "failed" for c in cases),
           "skipped": sum(c["outcome"] == "skipped" for c in cases),
           "seconds": float(suite.get("time", 0)), "command": " ".join(cmd[1:]), "cases": cases}
(ROOT / "data" / "test_results.json").write_text(json.dumps(summary, indent=1))
xml.unlink(missing_ok=True)
print(f"\n{summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped -> data/test_results.json")
sys.exit(proc.returncode)
