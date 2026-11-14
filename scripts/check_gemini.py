"""Live check of the optional Gemini extraction. Writes nothing to the database.

    1. put GEMINI_API_KEY=... in .env (the file is git-ignored), optionally GEMINI_MODEL=...
    2. python scripts/check_gemini.py [company-slug]        (default: njord-x)

Reads the company's already retrieved public website pages (from data/cache), sends them to Gemini, and prints
every proposed claim with the evidence check's verdict, next to what the rule-based extractor finds. Only public
website text is sent. Results depend on the live model on the day it runs; they are not used by the app until
NEXUS_LLM_EXTRACTION=gemini is set and the directory is synced.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus.agents import company_agent  # noqa: E402
from nexus.integrations import company_sources as cs, gemini  # noqa: E402
from nexus.integrations.http_cache import HttpClient  # noqa: E402

if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "njord-x"
    ext = gemini.GeminiExtractor()
    if not ext.api_key:
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (git-ignored) and run again.")
    client = HttpClient()
    member, status = cs.fetch_member_profile(client, slug)
    if member is None or not member.website:
        sys.exit(f"{slug}: no member profile or website ({status})")
    crawl = cs.crawl_company_site(client, member.website)
    print(f"{member.name}: {len(crawl.pages)} website pages, model {ext.model}")

    rules = company_agent.build_profile(member, crawl)
    try:
        model = company_agent.build_profile(member, crawl, llm=ext)
    except Exception as exc:
        sys.exit(f"Gemini call failed: {type(exc).__name__}: {exc}")
    for w in model.warnings:
        print("  note:", w)
    web = lambda d: [c for c in d.claims if c.source_type == "company_website"]
    print(f"\nAccepted model claims ({len(web(model))}):")
    for c in web(model):
        print(f"  [{c.claim_category}] {c.claim_text[:90]}\n      quote: \"{c.evidence_text[:160]}\"  {c.evidence_url}")
    print(f"\nRejected model proposals ({len([r for r in model.rejected if r.startswith('model claim')])}):")
    for r in model.rejected:
        if r.startswith("model claim"):
            print("  -", r[:220])
    caps = lambda d: sorted({c.capability_key for c in d.claims if c.capability_key})
    print(f"\nCapabilities, rule-based: {caps(rules)}")
    print(f"Capabilities, model-assisted: {caps(model)}")
    print("\nRead the accepted quotes: an exact quote proves the text exists, not that the claim is right.")
