import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Building2, Banknote, FlaskConical, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../api";
import { Badge, Card, HypothesisCard, HypothesisNotice, Notice, PageHeader, QueryState, SectionTitle, SourceLink, Stat, Translated, day, stamp } from "../components/ui";

function CapabilityBars({ rows }) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, 16);
  const max = Math.max(1, ...rows.map((r) => r.companies));
  return (
    <>
      <ul className="space-y-1.5">
        {shown.map((r) => (
          <li key={r.key} className="group grid grid-cols-[minmax(120px,38%)_1fr_28px] items-center gap-3 text-[13px]" title={r.role_label}>
            <span className="truncate text-right text-ink2 group-hover:text-ink">{r.name}</span>
            <span className="h-5 overflow-hidden rounded-md bg-line/40">
              <span className="block h-full rounded-md bg-gradient-to-r from-brand/70 to-brand transition-all group-hover:from-cyan/70 group-hover:to-cyan"
                    style={{ width: `${(r.companies / max) * 100}%` }} />
            </span>
            <span className="font-display font-semibold tabular-nums">{r.companies}</span>
          </li>
        ))}
      </ul>
      {rows.length > 16 && (
        <button type="button" className="btn mt-3" onClick={() => setAll(!all)}>{all ? "Show top 16" : `Show all ${rows.length} capabilities`}</button>
      )}
    </>
  );
}

export default function Overview() {
  const query = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  return (
    <>
      <PageHeader eyebrow="Ecosystem" title="Innovation Overview" subtitle="Every number on this page is counted from stored records." />
      <QueryState query={query}>
        {(d) => {
          const n = d.counts, st = d.funding_status;
          return (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                <Stat value={n.companies} label="Profiled companies" sub={`${n.companies_website} with website evidence`} icon={Building2} />
                <Stat value={n.verified_capabilities} label="Verified capability claims" sub={`${n.inferences} inferred interests kept separate`} icon={ShieldCheck} tone="fact" />
                <Stat value={n.research} label="Research records discovered" sub="OpenAlex" icon={BookOpen} tone="cyan" />
                <Stat value={(st.open ?? 0) + (st.upcoming ?? 0)} label="Open or upcoming funding calls"
                      sub={`${st.closed ?? 0} closed, ${st.unknown ?? 0} unknown of ${n.funding}`} icon={Banknote} tone="inf" />
                <Stat value={n.testbeds + n.events + n.news} label="Test environments, events, news" sub={`${n.testbeds} / ${n.events} / ${n.news}`} icon={FlaskConical} tone="pink" />
                <Stat value={n.hypotheses} label="Collaboration hypotheses" sub="generated, not confirmed" icon={Sparkles} tone="hyp" />
              </div>
              {n.demo_records
                ? <Notice tone="sim" className="mb-6">{n.demo_records} stored records are DEMO data and are labelled as such.</Notice>
                : <p className="meta mb-6">No demo or simulated records are stored: all companies, research, calls and test environments were retrieved from public sources.</p>}

              <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                <Card>
                  <SectionTitle hint="Number of member companies with at least one public source for each capability. Hover a row for its role.">
                    Capabilities in the ecosystem
                  </SectionTitle>
                  <CapabilityBars rows={d.capabilities} />
                </Card>
                <div>
                  <SectionTitle>Strongest hypotheses</SectionTitle>
                  <HypothesisNotice />
                  <div className="mt-3 space-y-3">{d.hypotheses.map((h) => <HypothesisCard key={h.key} h={h} compact />)}</div>
                </div>
              </div>

              <h2 className="mb-3 mt-9 text-lg font-semibold">Recent intelligence updates</h2>
              <div className="grid gap-5 lg:grid-cols-3">
                <div>
                  <h3 className="mb-2.5 text-sm font-semibold text-ink2">Latest funding calls opened</h3>
                  <div className="space-y-2.5">
                    {d.recent_funding.map((f) => (
                      <div key={f.url} className="card p-3.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge kind={["open", "upcoming"].includes(f.status) ? f.status : "neutral"}>{f.status}</Badge>
                          <span className="meta">opened {day(f.opens_at)}{f.deadline && ` · deadline ${day(f.deadline)}`}</span>
                        </div>
                        <p className="mt-1.5 text-[13px] leading-snug text-ink"><Translated original={f.title} en={f.title_en} max={110} /></p>
                        <p className="mt-1 text-xs"><SourceLink url={f.url}>Vinnova open data</SourceLink></p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="mb-2.5 text-sm font-semibold text-ink2">Most recent research retrieved</h3>
                  <div className="space-y-2.5">
                    {d.recent_research.map((r) => (
                      <div key={r.url} className="card p-3.5">
                        <span className="meta">published {day(r.date)}</span>
                        <p className="mt-1 text-[13px] leading-snug text-ink">{r.title.slice(0, 120)}</p>
                        <p className="mt-1 text-xs"><SourceLink url={r.url}>OpenAlex record source</SourceLink></p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="mb-2.5 text-sm font-semibold text-ink2">Retrieval log</h3>
                  <div className="table-wrap max-h-[420px]">
                    <table className="table">
                      <thead><tr><th>When (UTC)</th><th>Source</th><th>Status</th><th className="text-right">Records</th></tr></thead>
                      <tbody>
                        {d.logs.map((l, i) => (
                          <tr key={i}>
                            <td className="whitespace-nowrap tabular-nums">{stamp(l.when).slice(5)}</td><td>{l.source}</td>
                            <td><span className={l.status === "ok" ? "text-fact" : l.status === "error" ? "text-pink" : ""}>{l.status}</span></td>
                            <td className="text-right tabular-nums">{l.records ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="meta mt-2">Every external retrieval is logged with its status, including failures.</p>
                </div>
              </div>
            </>
          );
        }}
      </QueryState>
    </>
  );
}
