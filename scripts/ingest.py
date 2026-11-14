"""Retrieve public data and (re)build all recommendations.

    python scripts/ingest.py              # live retrieval (uses cache where fresh), then recompute
    python scripts/ingest.py --recompute  # only rebuild hypotheses from what is stored
    NEXUS_OFFLINE=1 python scripts/ingest.py   # rebuild the database from the cached snapshot only

To refresh only the member directory (faster), use scripts/sync_directory.py.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus import pipeline  # noqa: E402
from nexus.agents import directory_agent  # noqa: E402
from nexus.core.embeddings import get_embedder  # noqa: E402
from nexus.database.database import session_scope  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true", help="skip retrieval")
    args = ap.parse_args()
    with session_scope() as s:
        trace = [] if args.recompute else pipeline.ingest(s)
        if not args.recompute:
            trace.append(pipeline.translate_new_texts(s))
        emb = get_embedder()
        print(f"Embedding backend: {emb.backend}" + (f" (fallback: {emb.fallback_reason})" if emb.fallback_reason else ""))
        trace += pipeline.recompute(s, emb)
        pipeline.save_trace(trace, emb.backend)
        snap = directory_agent.latest_snapshot(s)
        if snap is not None and not args.recompute:
            pipeline.save_directory_audit(snap.summary)
    for step in trace:
        print(f"[{step['seconds']:>6}s] {step['agent']}: {step['result']}")
        for w in step["warnings"][:8]:
            print(f"          ! {w}")
