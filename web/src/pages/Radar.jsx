import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { SearchX } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import ItemCard, { KIND } from "../components/ItemCard";
import { Chip, CompanyPicker, Disclosure, Empty, Notice, PageHeader, QueryState, Segmented, SourceLink, day } from "../components/ui";

const VIEWS = [{ value: "all", label: "All items" }, { value: "saved", label: "Saved by us" }, { value: "open", label: "Funding: open only" }];

export default function Radar() {
  const { companies, companyId, setViewing, acting, meta } = useSession();
  const [kinds, setKinds] = useState(() => Object.keys(meta.radar_labels));
  const [minRel, setMinRel] = useState(25);
  const [view, setView] = useState("all");
  const query = useQuery({ queryKey: ["radar", companyId, acting], queryFn: () => api.radar(companyId), enabled: companyId !== null });
  const toggleKind = (k) => setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  // All filtering happens in the browser on data that is already loaded, so every control responds instantly.
  const all = query.data?.items ?? [];
  const counts = useMemo(() => all.reduce((acc, i) => { if (i.relevance >= minRel) acc[i.kind] = (acc[i.kind] ?? 0) + 1; return acc; }, {}), [all, minRel]);
  const items = useMemo(() => all.filter((i) =>
    kinds.includes(i.kind) && i.relevance >= minRel
    && (view !== "saved" || i.marks.includes("saved"))
    && (view !== "open" || i.kind !== "funding" || i.status === "open")), [all, kinds, minRel, view]);

  return (
    <>
      <PageHeader eyebrow="Discovery" title="Opportunity Radar"
                  subtitle="Funding, test environments, events, research and regional news from public sources, ranked for one company." />
      <div className="card mb-5 space-y-4 p-4">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
          <CompanyPicker className="w-full sm:w-72" label="Company" companies={companies} value={companyId} onChange={setViewing} />
          <label className="block w-52">
            <span className="label flex justify-between">Minimum relevance <b className="tabular-nums text-ink">{minRel}</b></span>
            <input type="range" min="0" max="100" step="5" value={minRel} onChange={(e) => setMinRel(Number(e.target.value))}
                   className="h-[38px] w-full accent-[rgb(var(--brand))]" />
          </label>
          <div className="ml-auto"><span className="label">Show</span><Segmented options={VIEWS} value={view} onChange={setView} /></div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 border-t border-line/70 pt-3.5">
          <span className="mr-1.5 text-xs font-medium text-ink2">Monitoring area</span>
          {Object.entries(meta.radar_labels).map(([k, label]) => (
            <Chip key={k} active={kinds.includes(k)} onClick={() => toggleKind(k)} color={KIND[k]?.color}>
              {label}<span className="tabular-nums text-muted">{counts[k] ?? 0}</span>
            </Chip>
          ))}
        </div>
      </div>

      <QueryState query={query}>
        {(data) => (
          <>
            {data.company.needs.length > 0 && (
              <p className="meta mb-3">
                Company priorities applied to the ranking: {data.company.needs.join(", ")}. Change them on
                the <Link className="link" to="/dna">Company DNA</Link> page.
              </p>
            )}
            {view === "saved" && !data.can_mark && (
              <Notice tone="info" className="mb-4">Saved items are private. Select this company under “Acting as” to see its saved items.</Notice>
            )}
            {items.length ? (
              <div className="grid items-start gap-4 xl:grid-cols-2">
                {items.map((it) => <ItemCard key={`${it.kind}:${it.ref_id}`} item={it} canMark={data.can_mark} />)}
              </div>
            ) : (
              <Empty icon={SearchX}>No stored item matches these filters. Companies without evidence-backed capabilities have no radar items.</Empty>
            )}
            <p className="meta mt-5 max-w-4xl leading-relaxed">
              {items.length} items. Relevance = 70% text similarity (multilingual embeddings) + 30% shared capability
              tags, then adjusted for the company's stated priorities and feedback (shown as a ranking note). Closed
              funding calls and items the company marked “not useful” are never listed.
            </p>
            {data.past_events.length > 0 && kinds.includes("event") && (
              <div className="mt-4">
                <Disclosure title={`Past events found on the source pages (${data.past_events.length}) - not offered as opportunities`}>
                  <ul className="space-y-1.5 text-[13px] text-ink2">
                    {data.past_events.map((e) => (
                      <li key={e.url + e.title}>
                        <span className="tabular-nums text-muted">{day(e.date)}</span> · {e.title} · {e.location || "location not stated"} ·{" "}
                        <SourceLink url={e.url} /> {e.note}
                      </li>
                    ))}
                  </ul>
                </Disclosure>
              </div>
            )}
          </>
        )}
      </QueryState>
    </>
  );
}
