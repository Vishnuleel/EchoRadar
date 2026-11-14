import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import ItemCard from "../components/ItemCard";
import { Badge, CompanyPicker, Disclosure, Empty, HypothesisCard, QueryState } from "../components/ui";

const AREAS = [
  { title: "Funding", key: "funding", need: "funding" },
  { title: "Testing", key: "testing", need: "testing" },
  { title: "Events", key: "events", need: "events" },
  { title: "Knowledge and trends", key: "knowledge", need: "knowledge" },
];
const keyOf = (i) => `${i.kind}:${i.ref_id}`;
const longDate = (d = new Date()) => d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

/** The week's top three: closing deadlines first, then the strongest item of each area, never two of one kind first. */
function topThree(digest) {
  const pool = [...digest.urgent, ...digest.funding, ...digest.testing, ...digest.events, ...digest.knowledge];
  const seen = new Set();
  const unique = pool.filter((i) => !seen.has(keyOf(i)) && seen.add(keyOf(i)));
  const lead = unique[0];
  const rest = unique.slice(1);
  const also = [...rest.filter((i) => i.kind !== lead?.kind), ...rest.filter((i) => i.kind === lead?.kind)].slice(0, 2);
  return { lead, also };
}

function Masthead({ data }) {
  const { companies, acting, companyId, setViewing } = useSession();
  const n = data.counts;
  return (
    <header className="mb-8">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-ink pb-2 font-sans text-[13px] text-ink2">
        <span>{longDate()}</span>
        <span className="hidden sm:inline">Blue Science Park · Karlskrona</span>
        {acting === null ? (
          <div className="flex items-center gap-2">
            <span>Edition for</span>
            <CompanyPicker className="w-56" companies={companies} value={companyId} onChange={setViewing} />
          </div>
        ) : <span>Your edition</span>}
      </div>
      <h1 className="border-b-[3px] border-double border-ink py-3 text-center font-serif text-[52px] font-bold leading-none tracking-tight sm:text-[72px]">
        NEXUS Weekly
      </h1>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink py-2 font-sans text-[13px] text-ink2">
        <span className="font-semibold uppercase tracking-[0.12em] text-ink">{data.company.name} edition</span>
        <span className="text-muted">
          {n.companies} members · {n.funding} funding calls · {n.testbeds + n.events} test sites and events · {n.research + n.news} research and news items
        </span>
      </div>
    </header>
  );
}

function FrontPage({ data }) {
  const { acting, names } = useSession();
  const { digest, company } = data;
  const canMark = acting === company.id;
  const { lead, also } = useMemo(() => topThree(digest), [digest]);
  const shown = new Set([lead, ...also].filter(Boolean).map(keyOf));
  const areas = [...AREAS].sort((a, b) => company.needs.includes(b.need) - company.needs.includes(a.need));

  if (!lead) {
    return (
      <Empty>
        No findings this week: the public profile of {names[company.id]} names no technology or expertise NEXUS can
        confirm. <Link className="link not-italic" to="/dna">Add a capability or interest</Link> to get a personal edition.
      </Empty>
    );
  }
  return (
    <>
      <section className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          <div className="kicker mb-2">Lead story</div>
          <ItemCard item={lead} canMark={canMark} lead />
        </div>
        <div className="lg:border-l lg:border-line lg:pl-8">
          <div className="kicker mb-1">Also this week</div>
          {also.map((it) => <ItemCard key={keyOf(it)} item={it} canMark={canMark} compact />)}
          <Link to="/radar" className="mt-4 inline-flex items-center gap-1 font-sans text-[14px] font-semibold text-brand hover:underline">
            All {digest.total} findings in the Radar <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className="mt-12">
        <div className="mb-1 flex items-end justify-between border-b-2 border-ink pb-1.5">
          <h2 className="text-[26px] font-semibold">Briefs</h2>
          {company.needs.length > 0 && <span className="meta">Your priorities first: {company.needs.join(", ")}</span>}
        </div>
        <div className="grid gap-x-8 md:grid-cols-2">
          {areas.map(({ title, key, need }) => {
            const items = digest[key].filter((i) => !shown.has(keyOf(i))).slice(0, 2);
            if (!items.length) return null;
            return (
              <div key={key} className="mt-5">
                <h3 className="flex items-center gap-2 border-b border-line pb-1 font-sans text-[13px] font-semibold uppercase tracking-[0.12em] text-ink2">
                  {title}{company.needs.includes(need) && <Badge kind="USER">priority</Badge>}
                </h3>
                {items.map((it) => <ItemCard key={keyOf(it)} item={it} canMark={canMark} />)}
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

/** Fig. 1: this week's findings per area, drawn from the radar itself. */
function AreaFigure({ areas, total }) {
  const LABEL = { funding: "Funding", testbed: "Testing", event: "Events", research: "Research", news: "Regional news" };
  const max = Math.max(1, ...areas.map((a) => a.count));
  return (
    <figure>
      <div className="mb-1 flex items-end justify-between border-b-2 border-ink pb-1.5">
        <h2 className="text-[26px] font-semibold">The week in figures</h2>
      </div>
      <div className="mt-4 space-y-3">
        {areas.map((a) => (
          <div key={a.kind} className="grid grid-cols-[110px_1fr_auto] items-center gap-3 font-sans text-[14px]">
            <span className="text-ink2">{LABEL[a.kind] ?? a.kind}</span>
            <span className="h-4 bg-line/40"><span className="block h-full bg-brand" style={{ width: `${(a.count / max) * 100}%` }} /></span>
            <span className="w-24 text-right tabular-nums text-ink"><b>{a.count}</b> <span className="text-muted">best {a.best.toFixed(0)}</span></span>
          </div>
        ))}
      </div>
      <figcaption className="meta mt-3 border-t border-line pt-2 italic">
        Fig. 1. The {total} findings on this company's radar by area, with the highest fit score in each.
        Source: NEXUS ranking of public records.
      </figcaption>
    </figure>
  );
}

export default function Home({ preview }) {
  const { companyId, acting, meta } = useSession();
  const query = useQuery({ queryKey: ["home", companyId, acting], queryFn: () => api.home(companyId), enabled: companyId !== null });
  return (
    <QueryState query={query}>
      {(data) => (
        <>
          <Masthead data={data} />
          {acting === null && (
            <p className="meta -mt-4 mb-6">Public edition. Choose a company under "Reading as" to save items, rate them and refine the profile.</p>
          )}
          <FrontPage data={data} />

          <div className="mt-12 grid gap-10 lg:grid-cols-2">
            <section>
              <div className="mb-1 flex items-end justify-between border-b-2 border-ink pb-1.5">
                <h2 className="text-[26px] font-semibold">Possible partners</h2>
                <Link to="/dna" className="meta hover:text-ink hover:underline">All suggestions</Link>
              </div>
              {data.recommendations.length ? data.recommendations.map((r) => (
                <HypothesisCard key={r.key} h={r}>
                  <p className="mt-1.5 font-serif text-[15.5px] leading-snug text-ink2">{r.explanation.slice(0, 220)}{r.explanation.length > 220 ? "..." : ""}</p>
                  <Link to={`/blueprint?key=${encodeURIComponent(r.key)}`} className="mt-2 inline-flex items-center gap-1 font-sans text-[13.5px] font-semibold text-brand hover:underline">
                    Read the brief <ArrowRight size={13} />
                  </Link>
                </HypothesisCard>
              )) : <p className="meta mt-3">No connection with evidence on both sides yet.</p>}
              <p className="meta mt-3 italic">Generated proposals. No company has been asked or has agreed.</p>
            </section>
            <AreaFigure areas={data.areas ?? []} total={data.digest.total} />
          </div>

          {data.trace && (
            <div className="mt-12">
              <Disclosure title={`How this edition was made (${data.trace.finished_at.slice(0, 16).replace("T", " ")} UTC)`}>
                <p className="meta mb-2">Embeddings: {data.trace.embedding_backend}</p>
                <ol className="space-y-2">
                  {data.trace.trace.map((step) => (
                    <li key={step.agent} className="font-sans text-[14px] leading-relaxed text-ink2">
                      <b className="text-ink">{step.agent}</b> <span className="text-muted">({step.seconds} s)</span> {step.result}
                      {step.warnings.slice(0, 3).map((w) => <span key={w} className="meta block">Warning: {w}</span>)}
                    </li>
                  ))}
                </ol>
              </Disclosure>
            </div>
          )}
          <p className="meta mt-6 max-w-3xl italic">{meta.disclaimer}</p>
        </>
      )}
    </QueryState>
  );
}
