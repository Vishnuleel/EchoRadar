import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useSession } from "../store";
import { BadgeCheck, CircleDashed, GitCompareArrows } from "lucide-react";
import { Bar, Empty, HypothesisCard, HypothesisNotice, Notice, PageHeader, QueryState, SectionTitle, SourceLink, day, stamp } from "../components/ui";

const FIELD_NAMES = { name: "name", description: "description", industry: "industry", employees: "employee band",
                      founded: "founding year", location: "location", website: "website" };

/** Audit summary of the latest member directory crawl (and the reconciled audited seed). */
function DirectoryCoverage() {
  const q = useQuery({ queryKey: ["directory"], queryFn: api.directory });
  const snap = q.data?.snapshot;
  if (!q.data) return null;
  if (!snap) {
    return <Notice tone="info" className="mb-8">No directory audit has run yet. Run <code>python scripts/sync_directory.py</code> to crawl the member directory and record coverage.</Notice>;
  }
  const verified = q.data.status_counts.verified ?? 0;
  const missing = Object.entries(snap.missing_fields_by_column).filter(([, n]) => n > 0);
  const differs = Object.entries(snap.seed_disagreements_by_field ?? {});
  const stat = (value, label) => (
    <div><div className="font-display text-2xl font-semibold tabular-nums">{value}</div><div className="meta mt-0.5">{label}</div></div>
  );
  return (
    <section className="card mb-9 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Member directory coverage</h2>
          <p className="meta mt-0.5">Snapshot {snap.snapshot_id} · {stamp(snap.taken_at)} UTC · <SourceLink url={snap.directory_url}>public directory</SourceLink></p>
        </div>
        <span className={snap.stable_end ? "inline-flex items-center gap-1.5 rounded-full border border-fact/35 bg-fact/10 px-2.5 py-0.5 text-[12px] font-medium text-fact"
                                         : "inline-flex items-center gap-1.5 rounded-full border border-hyp/40 bg-hyp/10 px-2.5 py-0.5 text-[12px] font-medium text-hyp"}>
          {snap.stable_end ? <BadgeCheck size={13} /> : <CircleDashed size={13} />}
          {snap.stable_end ? "End of listing confirmed" : "End of listing not confirmed"}
        </span>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-6">
        {stat(snap.loaded_card_count, `cards loaded on ${snap.announced_pages ?? "?"} pages`)}
        {stat(snap.unique_listed_profiles, "unique listed profiles")}
        {stat(`${verified}/${snap.companies_stored}`, "profiles verified")}
        {stat(snap.new_records.length, "new since last sync")}
        {stat(snap.failed_urls.length, "failed profile URLs")}
        {stat(snap.not_in_latest_listing.length, "no longer listed")}
      </div>
      <div className="mt-5 grid gap-4 border-t border-line/70 pt-4 text-[13px] leading-relaxed text-ink2 lg:grid-cols-2">
        <p>
          {snap.coverage_statement} Coverage refers to the public directory only.
          {snap.seed_scope_note && " The audited seed notes that Blue Science Park states it has over 80 members, so some members may not be listed publicly."}
          {" "}Fields not published on a profile: {missing.length ? missing.map(([f, n]) => `${FIELD_NAMES[f]} (${n})`).join(", ") : "none"}.
          Member versus partner status is not published per organisation and is not stated.
        </p>
        {snap.seed_records !== undefined && (
          <p className="flex gap-2">
            <GitCompareArrows size={15} className="mt-0.5 shrink-0 text-inf" />
            <span>
              Audited seed: {snap.seed_matches} of {snap.seed_records} records matched
              {snap.duplicates.length > 0 && ` (${snap.duplicates.length} via an old profile URL that now redirects)`}
              {snap.seed_unmatched.length > 0 && `; unmatched: ${snap.seed_unmatched.map((u) => u.name).join(", ")}`}.
              {differs.length > 0 && ` Its values differ from the live official pages on ${differs.map(([f, n]) => `${n} ${FIELD_NAMES[f]}${n > 1 ? "s" : ""}`).join(", ")}; the official wording is shown and the seed values are kept for review on each company's Directory record.`}
            </span>
          </p>
        )}
      </div>
    </section>
  );
}

export default function Staff() {
  const { setViewing } = useSession();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["staff"], queryFn: api.staff });
  const open = (id) => { setViewing(id); navigate("/dna"); };
  return (
    <>
      <PageHeader eyebrow="Blue Science Park staff" title="Ecosystem View"
                  subtitle="Shared interests across members, connections worth facilitating, and where profiles need attention." />
      <Notice tone="sim" className="mb-6">
        <b className="text-inf">SIMULATED:</b> this page has no staff login in the prototype. It only shows public profile data
        and anonymous aggregates; no company's private questions, saved items or ratings are exposed.
      </Notice>
      <DirectoryCoverage />
      <QueryState query={query}>
        {(d) => {
          const max = Math.max(1, ...d.shared_interests.map((r) => r.members));
          const none = d.profiles.filter((r) => r.capabilities === 0).length;
          return (
            <div className="space-y-9">
              <div className="grid gap-7 lg:grid-cols-2">
                <div>
                  <SectionTitle hint="Application areas where several members have evidenced capabilities: candidates for a theme meeting.">Shared interest areas</SectionTitle>
                  <div className="space-y-2.5">
                    {d.shared_interests.map((r) => (
                      <div key={r.area} className="card p-3.5">
                        <div className="flex items-baseline justify-between gap-3">
                          <h3 className="text-sm font-semibold">{r.area}</h3>
                          <span className="font-display text-lg font-semibold tabular-nums">{r.members}<span className="meta ml-1 font-sans font-normal">members</span></span>
                        </div>
                        <Bar value={(r.members / max) * 100} className="my-2" color="rgb(var(--cyan))" />
                        <p className="text-[12.5px] leading-relaxed text-ink2">{r.who.join(", ")}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <SectionTitle>Connections worth facilitating</SectionTitle>
                  <HypothesisNotice />
                  <div className="mt-3 space-y-3">
                    {d.connections.map((h) => (
                      <HypothesisCard key={h.key} h={h} compact>
                        {h.missing.length > 0 && <p className="meta mt-1.5">Missing: {h.missing.join(", ")}</p>}
                      </HypothesisCard>
                    ))}
                  </div>
                  <p className="meta mt-3">Suggested staff action: check interest with each company separately before any introduction.</p>
                </div>
              </div>

              <div className="grid gap-7 lg:grid-cols-2">
                <div>
                  <SectionTitle hint="Fewest confirmed capabilities first. Click a row to open the profile.">Profiles that need attention</SectionTitle>
                  <div className="table-wrap max-h-[440px]">
                    <table className="table">
                      <thead><tr><th>Company</th><th className="text-right">Capabilities</th><th>Depth</th><th className="text-right">Open gaps</th><th>Refined</th><th>Last updated</th></tr></thead>
                      <tbody>
                        {d.profiles.map((r) => (
                          <tr key={r.id} className="cursor-pointer" onClick={() => open(r.id)}>
                            <td className="font-medium text-ink">{r.company}</td>
                            <td className="text-right tabular-nums"><span className={r.capabilities === 0 ? "font-semibold text-hyp" : ""}>{r.capabilities}</span></td>
                            <td>{r.depth}</td><td className="text-right tabular-nums">{r.gaps}</td><td>{r.refined ? "yes" : "no"}</td>
                            <td className="whitespace-nowrap tabular-nums">{day(r.updated_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="meta mt-2 leading-relaxed">
                    {none} of {d.profiles.length} members have no confirmed capability: their public text is too general for the taxonomy,
                    so a short conversation or the member's own refinement is needed.
                  </p>
                </div>
                <div>
                  <SectionTitle>Member developments in the news</SectionTitle>
                  <div className="space-y-2.5">
                    {d.news.map((n) => (
                      <div key={n.url} className="card p-3.5">
                        <span className="meta">{day(n.date)} · {n.source} · names {n.names.join(", ")}</span>
                        <p className="mt-1 text-sm font-medium leading-snug text-ink">{n.title}</p>
                        <p className="mt-1 text-[13px] leading-relaxed text-ink2">{n.summary}</p>
                        <p className="mt-1 text-xs"><SourceLink url={n.url} /></p>
                      </div>
                    ))}
                    {!d.news.length && <Empty>No retrieved news item names a member company.</Empty>}
                  </div>
                  <p className="meta mt-3">
                    Feedback collected in the app: {d.feedback.n} hypothesis ratings{d.feedback.n ? `, mean ${d.feedback.mean} of 5` : ""} (anonymous aggregate).
                  </p>
                </div>
              </div>
            </div>
          );
        }}
      </QueryState>
    </>
  );
}
