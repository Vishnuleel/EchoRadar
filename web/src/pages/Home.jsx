import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowRight, Bot, Building2, CalendarDays, Banknote, Lightbulb, SendHorizontal, ShieldAlert, ShieldCheck, Sparkles, Trash2, User } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import ItemCard, { KIND } from "../components/ItemCard";
import { Badge, CompanyPicker, Disclosure, Empty, HypothesisCard, Notice, QueryState, SectionTitle, SourceLink, Stat } from "../components/ui";

const SECTIONS = [
  { title: "Funding", key: "funding", need: "funding" },
  { title: "Testing opportunities", key: "testing", need: "testing" },
  { title: "Events", key: "events", need: "events" },
  { title: "Knowledge and trends", key: "knowledge", need: "knowledge" },
];
const ANGLE = { funding: 300, testbed: 30, event: 100, research: 170, news: 235 };

/** The radar graphic plots the real digest items: closer to the centre = more relevant. */
function RadarSweep({ items }) {
  const seen = new Set();
  const blips = items.filter((i) => { const k = `${i.kind}:${i.ref_id}`; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 12);
  const count = {};
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[300px]" role="img"
         aria-label={`Radar with ${blips.length} items; closer to the centre means more relevant`}>
      {[100, 72, 44, 16].map((d) => (
        <div key={d} className="absolute rounded-full border border-cyan/20" style={{ inset: `${(100 - d) / 2}%` }} />
      ))}
      <div className="absolute inset-x-0 top-1/2 h-px bg-cyan/15" />
      <div className="absolute inset-y-0 left-1/2 w-px bg-cyan/15" />
      <div className="absolute inset-0 animate-sweep rounded-full"
           style={{ background: "conic-gradient(from 0deg, rgb(var(--cyan) / 0.32), transparent 22%, transparent)" }} />
      <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan" />
      {blips.map((it) => {
        const n = (count[it.kind] = (count[it.kind] ?? 0) + 1);
        const a = ((ANGLE[it.kind] ?? 0) + (n - 1) * 17 - 90) * (Math.PI / 180);
        const r = 9 + ((100 - Math.min(100, it.relevance)) / 100) * 62;
        const color = KIND[it.kind]?.color;
        return (
          <span key={`${it.kind}:${it.ref_id}`} title={`${KIND[it.kind]?.label}: ${it.title} (relevance ${it.relevance.toFixed(0)})`}
                className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ left: `${50 + (r / 2) * Math.cos(a)}%`, top: `${50 + (r / 2) * Math.sin(a)}%`, background: color, boxShadow: `0 0 10px ${color}` }}>
            <span className="absolute inset-0 animate-ping2 rounded-full" style={{ background: color, animationDelay: `${n * 0.4}s` }} />
          </span>
        );
      })}
    </div>
  );
}

function Hero({ data }) {
  const { companies, acting, companyId, setViewing } = useSession();
  const d = data.digest;
  const all = [...d.urgent, ...d.funding, ...d.testing, ...d.events, ...d.knowledge];
  return (
    <section className="card relative mb-5 overflow-hidden">
      <div className="pointer-events-none absolute inset-0"
           style={{ background: "radial-gradient(700px 300px at 85% 40%, rgb(var(--cyan) / 0.10), transparent 70%), linear-gradient(135deg, rgb(var(--brand) / 0.12), transparent 55%)" }} />
      <div className="relative grid items-center gap-6 p-6 sm:p-8 lg:grid-cols-[1fr_300px]">
        <div>
          <div className="eyebrow">Blue Science Park · Virtual Science Park</div>
          <h1 className="mt-2 text-[30px] font-semibold leading-[1.12] sm:text-[40px]">
            What should <span className="bg-gradient-to-r from-brand to-cyan bg-clip-text text-transparent">{data.company.name}</span> know this week?
          </h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink2">
            NEXUS builds a profile from public sources, watches funding, test environments, events and research, finds
            members whose capabilities <b className="text-ink">complement</b> yours, and shows the evidence and a next
            step for every finding.
          </p>
          <div className="mt-5 flex flex-wrap items-end gap-3">
            {acting === null && (
              <CompanyPicker className="w-64" label="Showing the radar for" companies={companies} value={companyId} onChange={setViewing} />
            )}
            <Link to="/radar" className="btn btn-primary !px-4 !py-2">Open the full radar <ArrowRight size={15} /></Link>
            <Link to="/dna" className="btn !px-4 !py-2">View company profile</Link>
          </div>
          {acting === null && (
            <p className="meta mt-3">Public view. Choose a company under “Acting as” to save items, rate them and refine the profile.</p>
          )}
        </div>
        <div className="hidden lg:block">
          <RadarSweep items={all} />
          <div className="mt-3 flex flex-wrap justify-center gap-x-3 gap-y-1">
            {Object.entries(KIND).map(([k, v]) => (
              <span key={k} className="flex items-center gap-1.5 text-[11px] text-muted">
                <span className="h-2 w-2 rounded-full" style={{ background: v.color }} />{v.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Digest({ data }) {
  const { acting, names } = useSession();
  const { digest, company, recommendations } = data;
  const canMark = acting === company.id;
  const urgent = digest.urgent.slice(0, 2);
  const shown = new Set(urgent.map((i) => `${i.kind}:${i.ref_id}`));
  const sections = [...SECTIONS].sort((a, b) => company.needs.includes(b.need) - company.needs.includes(a.need));
  return (
    <div className="min-w-0 space-y-6">
      <SectionTitle hint={company.needs.length ? `Current priorities set by the company: ${company.needs.join(", ")}.` : undefined}>
        This week for {names[company.id]}
      </SectionTitle>
      {!digest.total && (
        <Empty icon={Lightbulb}>
          No radar items: no technology or expertise could be confirmed for this company from public text. Add a
          capability or interest on the <Link className="link" to="/dna">Company DNA</Link> page to get a personalised radar.
        </Empty>
      )}
      {urgent.length > 0 && (
        <div>
          <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-hyp"><CalendarDays size={15} />Closing soon</h3>
          <div className="space-y-3">{urgent.map((it) => <ItemCard key={`u${it.kind}${it.ref_id}`} item={it} canMark={canMark} />)}</div>
        </div>
      )}
      {sections.map(({ title, key, need }) => {
        const items = digest[key].filter((i) => !shown.has(`${i.kind}:${i.ref_id}`)).slice(0, 2);
        if (!items.length) return null;
        return (
          <div key={key}>
            <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-ink2">
              {title}{company.needs.includes(need) && <Badge kind="USER">your current priority</Badge>}
            </h3>
            <div className="space-y-3">{items.map((it) => <ItemCard key={`${it.kind}${it.ref_id}`} item={it} canMark={canMark} />)}</div>
          </div>
        );
      })}
      {recommendations.length > 0 && (
        <div>
          <h3 className="mb-2.5 text-sm font-semibold text-ink2">Potential connections with other members</h3>
          <div className="space-y-3">
            {recommendations.map((r) => (
              <HypothesisCard key={r.key} h={r}>
                <p className="meta mt-2 leading-relaxed">{r.explanation.slice(0, 260)}</p>
                <p className="meta mt-1"><b>Uncertain:</b> neither company has expressed an interest; this is a generated hypothesis.</p>
                <Link to={`/blueprint?key=${encodeURIComponent(r.key)}`} className="link mt-2 text-[13px]">Open as Innovation Blueprint <ArrowRight size={13} /></Link>
              </HypothesisCard>
            ))}
          </div>
        </div>
      )}
      {digest.total > 0 && (
        <p className="meta">{digest.total} radar items in total - see <Link to="/radar" className="link">Opportunity Radar</Link>.</p>
      )}
    </div>
  );
}

/* ---- assistant ---------------------------------------------------------------------------------- */
let chatMemory = []; // survives page changes within the session; never stored

function Answer({ turn, disclaimer }) {
  const cat = turn.category;
  const blocked = ["prompt_injection", "privacy_violation"].includes(cat);
  const declined = ["out_of_scope", "needs_clarification", "empty"].includes(cat);
  const nothing = !blocked && !declined && !(turn.items.length || turn.companies.length);
  return (
    <div className="space-y-2.5">
      <span className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                            blocked ? "border-pink/40 bg-pink/10 text-pink" : declined ? "border-line bg-surface2 text-ink2" : "border-fact/35 bg-fact/10 text-fact")}>
        {blocked ? <ShieldAlert size={12} /> : <ShieldCheck size={12} />}Boundary check: {cat.replace(/_/g, " ")}
      </span>
      {(blocked || declined || cat === "escalation") && turn.message && (
        <Notice tone={blocked ? "error" : cat === "escalation" ? "sim" : "info"} icon={blocked ? ShieldAlert : Lightbulb}>{turn.message}</Notice>
      )}
      {nothing && (
        <Notice tone="info" icon={Lightbulb}>
          No stored record matches this well enough. Nothing has been made up. Blue Science Park staff may know
          more: <SourceLink url="https://www.bluesciencepark.se/kontakt/">contact</SourceLink>
        </Notice>
      )}
      {!blocked && !declined && turn.items.map((it) => <ItemCard key={`${it.kind}${it.ref_id}`} item={it} compact />)}
      {!blocked && !declined && turn.companies.map((c) => (
        <div key={c.company_id} className="card p-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2"><Building2 size={15} className="text-fact" /><b className="text-sm">{c.name}</b><Badge kind="FACT">member</Badge></div>
            <span className="meta">relevance {c.relevance.toFixed(0)}</span>
          </div>
          {c.evidence.map((e, i) => (
            <blockquote key={i} className="quote">{e.capability_name}: “{e.excerpt.slice(0, 200)}” <SourceLink url={e.url} /></blockquote>
          ))}
        </div>
      ))}
      {!blocked && !declined && turn.hypotheses.map((h) => <HypothesisCard key={h.key} h={h} compact />)}
      {!blocked && !declined && <p className="meta">{disclaimer}</p>}
    </div>
  );
}

function Assistant() {
  const { meta } = useSession();
  const [chat, setChat] = useState(chatMemory);
  const [text, setText] = useState("");
  const scroller = useRef(null);
  useEffect(() => { chatMemory = chat; }, [chat]);
  const ask = useMutation({
    mutationFn: (question) => {
      const prev = [...chat].reverse().find((t) => ["in_scope", "escalation"].includes(t.category))?.query ?? null;
      return api.ask(question, prev);
    },
    onSuccess: (turn) => setChat((c) => [...c, turn].slice(-12)),
  });
  // scroll the conversation box only, never the page
  useEffect(() => { const el = scroller.current; if (el && (chat.length || ask.isPending)) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }, [chat.length, ask.isPending]);
  const send = (q) => { const question = (q ?? text).trim(); if (!question || ask.isPending) return; setText(""); ask.mutate(question); };

  return (
    <aside className="min-w-0 lg:sticky lg:top-6 lg:self-start">
      <div className="card flex max-h-[calc(100vh-3rem)] flex-col overflow-hidden">
        <div className="border-b border-line p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-lg font-semibold"><Sparkles size={17} className="text-cyan" />Ask the assistant</h2>
            {chat.length > 0 && <button type="button" className="btn !px-2" onClick={() => setChat([])} title="Clear conversation"><Trash2 size={14} /></button>}
          </div>
          <p className="meta mt-1 leading-relaxed">{meta.scope}</p>
        </div>
        <div ref={scroller} className="min-h-[260px] flex-1 space-y-4 overflow-y-auto p-4">
          {!chat.length && !ask.isPending && (
            <div className="space-y-3">
              <Notice tone="sim" icon={Bot}>
                Rule-based assistant: answers are assembled from stored, source-linked records. No language model writes
                the text, so it cannot be talked into another role.
              </Notice>
              <p className="meta">Try a relevant request, an unrelated one, and an override attempt:</p>
              <div className="flex flex-col gap-2">
                {meta.examples.map((ex) => (
                  <button type="button" key={ex} onClick={() => send(ex)}
                          className="rounded-xl border border-line bg-surface2/60 px-3 py-2 text-left text-[13px] text-ink2 transition hover:border-brand/50 hover:text-ink">
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}
          {chat.map((turn, i) => (
            <div key={i} className="animate-rise space-y-3">
              <div className="flex justify-end gap-2">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-3.5 py-2 text-sm text-white">{turn.question}</div>
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface2 text-ink2"><User size={14} /></span>
              </div>
              <div className="flex gap-2">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-cyan/15 text-cyan"><Bot size={14} /></span>
                <div className="min-w-0 flex-1"><Answer turn={turn} disclaimer={meta.disclaimer} /></div>
              </div>
            </div>
          ))}
          {ask.isPending && <div className="meta flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-cyan" />Checking boundaries and searching stored records...</div>}
          {ask.isError && <Notice tone="error">{ask.error.message}</Notice>}
        </div>
        <form className="flex gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000}
                 placeholder="Ask about funding, testing, events, research or partners" aria-label="Your question" />
          <button type="submit" className="btn btn-primary !px-3" disabled={!text.trim() || ask.isPending} aria-label="Send"><SendHorizontal size={16} /></button>
        </form>
      </div>
    </aside>
  );
}

export default function Home() {
  const { companyId, acting, meta } = useSession();
  const query = useQuery({ queryKey: ["home", companyId, acting], queryFn: () => api.home(companyId), enabled: companyId !== null });
  return (
    <QueryState query={query}>
      {(data) => {
        const n = data.counts;
        return (
          <>
            <Hero data={data} />
            <div className="mb-7 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
              <Stat value={n.companies} label="Member profiles" sub={`${n.companies_website} enriched from own website`} icon={Building2} />
              <Stat value={n.funding} label="Funding calls" sub="Vinnova open data" icon={Banknote} tone="inf" />
              <Stat value={n.testbeds + n.events} label="Test environments and events" sub="Blue Science Park, MTC" icon={CalendarDays} tone="user" />
              <Stat value={n.research + n.news} label="Research and news items" sub="OpenAlex, regional news" icon={KIND.research.icon} tone="cyan" />
              <Stat value={n.hypotheses} label="Collaboration hypotheses" sub="not confirmed collaborations" icon={Sparkles} tone="hyp" />
            </div>
            <div className="grid gap-7 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <Digest data={data} />
              <div className="space-y-4">
                <Assistant />
                {data.trace && (
                  <Disclosure title={`What the agents did in the last run (${data.trace.finished_at} UTC)`}>
                    <p className="meta mb-2">Embedding backend: {data.trace.embedding_backend}</p>
                    <ol className="space-y-2.5">
                      {data.trace.trace.map((step) => (
                        <li key={step.agent} className="text-[13px] leading-relaxed text-ink2">
                          <b className="text-ink">{step.agent}</b> <span className="text-muted">({step.seconds} s)</span><br />{step.result}
                          {step.warnings.slice(0, 3).map((w) => <span key={w} className="meta block">Warning: {w}</span>)}
                        </li>
                      ))}
                    </ol>
                  </Disclosure>
                )}
              </div>
            </div>
            <p className="meta mt-8 max-w-3xl">{meta.disclaimer}</p>
          </>
        );
      }}
    </QueryState>
  );
}
