# Codex task — import and finish the verified Blue Science Park directory

Use `blue_science_park_audited_directory.json` as the corrected seed and read `VERIFICATION_REPORT.md` first.

Critical facts:
- The seed currently contains 55 source-linked organisations.
- This is NOT the full Blue Science Park directory. Blue Science Park states it has 80+ members and the public directory has a dynamic Load More control.
- Do not state that the directory is complete based on these 55 records.
- Blue Science Park distinguishes member and partner application types, but individual profiles don't consistently disclose which class each listed organisation belongs to. Do not guess.

Required:
1. Import all 55 seed records without overwriting source provenance.
2. Run and improve `crawl_blue_science_park.py` against the live directory. Keep clicking Load More until the page reaches a stable end state.
3. Capture every unique official `/medlem/<slug>/` link from all loaded cards and related member links where appropriate.
4. Visit each profile and parse: name, original Swedish description, industry, employee band, founding year, locations and website.
5. Add `field_sources` / provenance per field, `last_verified_at`, `profile_fetch_status`, `missing_fields`, and `directory_snapshot_id`.
6. Deduplicate by canonical Blue Science Park profile URL first, then normalized name; preserve aliases.
7. Add newly found organisations without deleting old records unless an admin confirms they are no longer listed.
8. Keep the official Swedish text. If you translate it, store translation separately and identify it as machine-generated.
9. Do not fill unpublished details from general web search or guesswork. If you use a company's own website to enrich the profile, mark its source separately from the Blue Science Park directory.
10. Produce an audit summary: loaded directory card count, unique profiles, seed matches, new records, duplicates, failed URLs, and missing fields by column.
11. Test that all displayed profile facts link to the exact evidence source.

Acceptance:
- Never claim full coverage unless the live crawl reaches a stable end and the number of profile cards/links is recorded.
- Never invent member-versus-partner status.
- Never invent employee counts, years, city, website or contact information.
- Keep a visible verification state on every NEXUS profile.
