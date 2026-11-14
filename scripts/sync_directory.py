"""Re-read the Blue Science Park member directory, reconcile the audited seed, and re-rank.

    python scripts/sync_directory.py                    # live directory (cache reused while fresh) + seed
    python scripts/sync_directory.py --seed other.json  # reconcile a different audited seed file
    python scripts/sync_directory.py --no-seed          # live directory only
    python scripts/sync_directory.py --no-recompute     # update profiles, keep the current rankings

Writes the audit summary to data/directory_audit.json and prints it. Coverage is only reported as
complete when the directory pagination reached its last page and the page after it loaded nothing.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus import pipeline  # noqa: E402
from nexus.core.embeddings import get_embedder  # noqa: E402
from nexus.database.database import session_scope  # noqa: E402
from nexus.integrations.http_cache import HttpClient  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=None, help="audited seed JSON (default: data/sources/...)")
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--no-recompute", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore cached directory pages younger than 3 days")
    args = ap.parse_args()
    client = HttpClient()
    if args.fresh:  # read every page live (the cache is still updated with the new copy)
        get = client.get
        client.get = lambda url, **kw: get(url, **{**kw, "force": True})
    with session_scope() as s:
        summary, totals = pipeline.sync_directory(s, client, seed_path="" if args.no_seed else args.seed)
        s.commit()
        trace = [{"agent": "Company Intelligence Agent (directory sync)", "seconds": 0,
                  "result": f"{summary['profiles_opened']} profiles, {totals['claims']} evidence-backed claims",
                  "warnings": totals["warnings"]}]
        trace.append(pipeline.translate_new_texts(s))
        print(f"  translation: {trace[-1]['result']} {trace[-1]['warnings'] or ''}")
        if not args.no_recompute:
            emb = get_embedder()
            trace += pipeline.recompute(s, emb)
            pipeline.save_trace(trace, emb.backend)
        pipeline.save_directory_audit(summary)

    print(f"\nSnapshot {summary['snapshot_id']}")
    print(f"  {summary['coverage_statement']}")
    print(f"  pages read: {len(summary['pages_read'])} (announced: {summary['announced_pages']}), "
          f"cards loaded: {summary['loaded_card_count']}, unique listed profiles: {summary['unique_listed_profiles']}")
    print(f"  profiles opened: {summary['profiles_opened']}, new records: {len(summary['new_records'])}, "
          f"found outside the listing: {len(summary['found_outside_listing'])}, duplicates/aliases: {len(summary['duplicates'])}, "
          f"failed URLs: {len(summary['failed_urls'])}, no longer listed: {len(summary['not_in_latest_listing'])}")
    print(f"  missing fields by column: {summary['missing_fields_by_column']}")
    if "seed_records" in summary:
        print(f"  seed: {summary['seed_matches']} of {summary['seed_records']} matched {summary['seed_matched_by']}; "
              f"unmatched: {summary['seed_unmatched']}")
        print(f"  seed values that differ from the live official page, by field: {summary['seed_disagreements_by_field']}")
    print("  written to data/directory_audit.json")
