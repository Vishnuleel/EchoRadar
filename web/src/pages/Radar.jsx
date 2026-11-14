import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bookmark, Fingerprint, MessageSquare, Radar as RadarIcon, SlidersHorizontal } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import ItemCard, { KIND } from "../components/ItemCard";
import MissedCalls from "../components/MissedCalls";
import { Chip, CompanyPicker, Disclosure, Notice, PageHeader, QueryState, Segmented, SourceLink, day } from "../components/ui";

const VIEWS = [{ value: "all", label: "All items" }, { value: "saved", label: "Saved by us" }, { value: "open", label: "Funding: open only" }];
const DEFAULT_MIN = 25;
const DEFAULT_KINDS = ["funding", "research"]; // the page opens on funding and research; the other areas are one click away

/** The company has no radar at all: explain why, and offer the ways forward. */
function NoRadar({ name, owner }) {
  return (
    <div className="card relative overflow-hidden p-6 sm:p-8">
      <div className="relative max-w-2xl">
        <h2 className="mt-4 text-xl font-semibold">No radar yet for {name}</h2>
        <p className="mt-2 text-[14px] leading-relaxed text-ink2">
          The radar ranks funding, test environments, events and research against a company's confirmed capabilities.
          The public profile of {name} does not name a technology or expertise that EchoRadar can confirm, so nothing is
          ranked rather than guessed.
        </p>
        <ol className="mt-5 space-y-2.5 text-[13.5px] text-ink2">
          <li className="flex gap-3"><span className="font-serif text-[18px] font-semibold text-sea">1.</span>
            {owner ? "Add one capability or interest to your profile; the radar is calculated straight away."
                   : `Sign in as ${name} under “Acting as” and add one capability or interest; the radar is calculated straight away.`}</li>
          <li className="flex gap-3"><span className="font-serif text-[18px] font-semibold text-sea">2.</span>
            Or ask the assistant directly, for example “funding for digital services”.</li>
        </ol>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link to="/dna" className="btn btn-primary !px-4 !py-2"><Fingerprint size={15} />{owner ? "Refine the profile" : "Open the profile"}<ArrowRight size={14} /></Link>
          <Link to="/ask" className="btn !px-4 !py-2"><MessageSquare size={15} />Ask EchoRadar</Link>
        </div>
      </div>
    </div>
  );
}

function EmptyFilter({ icon: Icon, title, text, action, onAction }) {
  return (
    <div className="card flex flex-col items-center px-6 py-10 text-center">
      <h2 className="mt-3 text-base font-semibold">{title}</h2>
      <p className="mt-1 max-w-md text-[13.5px] leading-relaxed text-ink2">{text}</p>
      <button type="button" className="btn mt-4" onClick={onAction}>{action}</button>
    </div>
  );
}

export default function Radar({ preview }) {
  const { companies, companyId, setViewing, acting, meta } = useSession();
  const [kinds, setKinds] = useState(() => DEFAULT_KINDS.filter((k) => k in meta.radar_labels));
  const [minRel, setMinRel] = useState(DEFAULT_MIN);
  const [view, setView] = useState("all");
  const reset = () => { setKinds(Object.keys(meta.radar_labels)); setMinRel(DEFAULT_MIN); setView("all"); };
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
            {view === "saved" && !data.can_mark && all.length > 0 && (
              <Notice tone="info" className="mb-4">Saved items are private. Select this company under “Acting as” to see its saved items.</Notice>
            )}
            {items.length ? (
              <div className="grid items-start gap-4 xl:grid-cols-2">
                {items.map((it) => <ItemCard key={`${it.kind}:${it.ref_id}`} item={it} canMark={data.can_mark} />)}
              </div>
            ) : !all.length ? (
              <NoRadar name={data.company.name} owner={data.can_mark} />
            ) : view === "saved" ? (
              data.can_mark && <EmptyFilter icon={Bookmark} title="Nothing saved yet"
                                            text="Use Save on any radar item to keep it here. Saved items are visible only to your company."
                                            action="Show all items" onAction={() => setView("all")} />
            ) : (
              <EmptyFilter icon={SlidersHorizontal} title="No item matches these filters"
                           text={`${all.length} items are on this company's radar, but none are in the selected areas at relevance ${minRel} or higher.`}
                           action="Reset filters" onAction={reset} />
            )}
            {items.length > 0 && (
              <p className="meta mt-5 max-w-4xl leading-relaxed">
                {items.length} of {all.length} items. Relevance = 70% text similarity (multilingual embeddings) + 30% shared
                capability tags, then adjusted for the company's stated priorities and feedback (shown as a ranking note).
                Closed funding calls and items the company marked “not useful” are never listed.
              </p>
            )}
            {!preview && <MissedCalls companyId={companyId} name={data.company.name} />}
            {data.past_events.length > 0 && kinds.includes("event") && all.length > 0 && (
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
