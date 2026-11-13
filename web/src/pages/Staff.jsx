import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useSession } from "../store";
import { Bar, Empty, HypothesisCard, HypothesisNotice, Notice, PageHeader, QueryState, SectionTitle, SourceLink, day } from "../components/ui";

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
