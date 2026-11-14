import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, Download, FileDown, FlaskConical, Star } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import { Badge, Card, CompanyPicker, Empty, Notice, PageHeader, QueryState, Ring, ScoreBars, Segmented, SourceLink, Translated, day } from "../components/ui";

function Section({ n, title, badge, children, className }) {
  return (
    <section className={className}>
      <h2 className="mb-3 flex items-center gap-2.5 text-lg font-semibold">
        <span className="grid h-7 min-w-7 place-items-center rounded-lg bg-brand/15 px-1.5 font-display text-[13px] text-brand">{n}</span>
        {title}{badge && <Badge kind={badge} />}
      </h2>
      {children}
    </section>
  );
}

function RateForm({ hypothesisKey }) {
  const { acting } = useSession();
  const [rating, setRating] = useState(3);
  const [comment, setComment] = useState("");
  const save = useMutation({ mutationFn: () => api.rate({ key: hypothesisKey, rating, comment }) });
  useEffect(() => { save.reset(); }, [hypothesisKey]); // eslint-disable-line react-hooks/exhaustive-deps
  if (acting === null) {
    return <p className="meta">Select the company you are acting as (sidebar) to rate this hypothesis. Ratings are private to your company; only the anonymous average is shown on the Evaluation page.</p>;
  }
  return (
    <form className="flex flex-wrap items-end gap-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <div>
        <span className="label">Relevance for your company (1 = not relevant, 5 = very relevant)</span>
        <div className="flex gap-1" role="radiogroup" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((v) => (
            <button key={v} type="button" role="radio" aria-checked={rating === v} aria-label={`${v} of 5`} onClick={() => setRating(v)}
                    className={clsx("rounded-lg p-1.5 transition", v <= rating ? "text-inf" : "text-line hover:text-muted")}>
              <Star size={24} fill={v <= rating ? "currentColor" : "none"} />
            </button>
          ))}
        </div>
      </div>
      <label className="min-w-[220px] flex-1">
        <span className="label">Comment (optional, private)</span>
        <input className="input" value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)} />
      </label>
      <button type="submit" className="btn btn-primary !py-2" disabled={save.isPending}>Save rating</button>
      {save.isSuccess && <span className="flex items-center gap-1.5 text-[13px] text-fact"><CheckCircle2 size={15} />Rating saved.</span>}
      {save.isError && <span className="text-[13px] text-pink">{save.error.message}</span>}
    </form>
  );
}

function Brief({ bp, note, params }) {
  const { meta } = useSession();
  const sc = bp.score, v = bp.verification ?? {};
  return (
    <div className="animate-rise space-y-8">
      <Notice><b className="text-ink">{bp.disclaimer}</b></Notice>
      {note && <p className="meta -mt-4">{note}</p>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-hyp/10 to-transparent" />
          <div className="relative">
            <div className="flex items-center gap-2"><Badge kind="HYPOTHESIS" /><span className="meta">1. Proposed innovation</span></div>
            <h2 className="mt-2 text-[26px] font-semibold leading-tight">{bp.title}</h2>
            <p className="mt-3 text-[15px] leading-relaxed text-ink2">{bp.proposed_application.text}</p>
            <div className="mt-5 flex items-center gap-2"><Badge kind="HYPOTHESIS" /><span className="meta">2. Problem being addressed</span></div>
            <p className="mt-2 text-[15px] leading-relaxed text-ink2">{bp.problem.text}</p>
          </div>
        </Card>
        <Card>
          <div className="mb-4 flex items-center gap-4">
            <Ring value={sc.final} size={76} stroke={7} label="Score" />
            <div>
              <div className="font-display text-sm font-semibold">Overall score of 100</div>
              <div className="meta">data coverage {((sc.coverage ?? 0) * 100).toFixed(0)}%</div>
            </div>
          </div>
          <ScoreBars breakdown={sc} labels={meta.score_labels} />
          <p className="meta mt-3 leading-relaxed">S = 0.35 C + 0.25 O + 0.20 R + 0.20 E. Strength of fit and evidence, not probability of commercial success.</p>
          {v.checks && (
            <p className="meta mt-2">Verification Agent: {String(v.status).replace(/_/g, " ")} - {v.checks.claims_with_source} of {v.checks.claims_used} capability claims have a public source.</p>
          )}
          <div className="mt-4 grid grid-cols-2 gap-2">
            <a className="btn" href={api.blueprintUrl({ ...params, format: "md" })} download><FileDown size={14} />Markdown</a>
            <a className="btn" href={api.blueprintUrl({ ...params, format: "pdf" })} download><Download size={14} />PDF</a>
          </div>
        </Card>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section n="3-4" title="Capability areas and companies">
          <div className="space-y-2.5">
            {bp.capability_areas.map((a, i) => (
              <div key={i} className="card flex items-start gap-3 p-3.5">
                <Badge kind="FACT" className="mt-0.5" />
                <div className="min-w-0"><div className="meta">{a.slot}</div><div className="text-sm font-semibold text-ink">{a.capability}</div><div className="text-[13px] text-ink2">{a.company}</div></div>
              </div>
            ))}
            {bp.missing_capabilities.length > 0 && (
              <div className="card border-dashed border-hyp/40 p-3.5">
                <Badge kind="HYPOTHESIS">missing</Badge>
                <div className="mt-1.5 text-sm font-semibold text-ink">Not covered by these companies</div>
                <div className="text-[13px] text-ink2">{bp.missing_capabilities.join(", ")}</div>
              </div>
            )}
            <ul className="space-y-1 pt-1 text-[13px]">
              {bp.companies.map((c) => (
                <li key={c.name} className="text-ink2"><b className="text-ink">{c.name}</b> · <SourceLink url={c.directory_url}>member directory</SourceLink>{c.website && <> · <SourceLink url={c.website}>website</SourceLink></>}</li>
              ))}
            </ul>
          </div>
        </Section>
        <Section n="5" title="Why they complement each other">
          <div className="space-y-2.5">
            {bp.complementarity.slice(0, 5).map((c, i) => (
              <div key={i} className="card p-3.5">
                <div className="flex flex-wrap items-center gap-2"><Badge kind="HYPOTHESIS" /><span className="meta">relationship strength {c.strength.toFixed(2)} · {c.kind.replace(/_/g, " ")}</span></div>
                <p className="mt-1.5 text-sm leading-relaxed text-ink">{c.text}</p>
                {c.evidence.map((e, j) => (
                  <blockquote key={j} className="quote">
                    <Badge kind={e.basis === "SOURCED" ? "FACT" : "USER"} className="mr-1.5 not-italic" />
                    {e.company} - {e.capability}: “{e.excerpt.slice(0, 230)}” {e.urls.slice(0, 2).map((u) => <SourceLink key={u} url={u} className="not-italic" />)}
                  </blockquote>
                ))}
              </div>
            ))}
          </div>
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Section n="6" title="Relevant research">
          <div className="space-y-2.5">
            {bp.research.map((r) => (
              <div key={r.url} className="card p-3.5">
                <div className="flex flex-wrap items-center gap-2"><Badge>OpenAlex</Badge><span className="meta">{r.date} · relevance {r.relevance.toFixed(0)}</span></div>
                <p className="mt-1.5 text-[13px] leading-snug text-ink">{r.title.slice(0, 140)}</p>
                <p className="meta mt-1">{r.authors}</p><p className="mt-1 text-xs"><SourceLink url={r.url} /></p>
              </div>
            ))}
            {!bp.research.length && <Empty>No clearly relevant research record was retrieved.</Empty>}
          </div>
        </Section>
        <Section n="7" title="Potential funding">
          <div className="space-y-2.5">
            {bp.funding.map((f) => (
              <div key={f.url} className="card p-3.5">
                <div className="flex flex-wrap items-center gap-2"><Badge kind={["open", "upcoming"].includes(f.status) ? f.status : "neutral"}>{f.status}</Badge><span className="meta">deadline {f.deadline} · relevance {f.relevance.toFixed(0)}</span></div>
                <p className="mt-1.5 text-[13px] leading-snug text-ink"><Translated original={f.title} en={f.title_en} max={140} /></p>
                {f.eligibility && <p className="mt-1 text-[12.5px] leading-relaxed text-ink2"><b className="text-ink">Who can apply (Vinnova):</b> {f.eligibility.slice(0, 260)}</p>}
                <p className="meta mt-1">{f.note} <SourceLink url={f.url} /></p>
              </div>
            ))}
            {!bp.funding.length && <Empty>No currently open or upcoming call was clearly relevant.</Empty>}
          </div>
        </Section>
        <Section n="8" title="Test possibilities">
          <div className="space-y-2.5">
            {bp.testbeds.map((t) => (
              <div key={t.url + t.name} className="card p-3.5">
                <Badge>{t.kind}</Badge>
                <p className="mt-1.5 text-[13px] leading-snug text-ink"><Translated original={t.name} en={t.name_en} max={120} /></p>
                <blockquote className="quote">“{t.description.slice(0, 240)}”</blockquote>
                <p className="meta">{t.note} <SourceLink url={t.url} /></p>
              </div>
            ))}
            {!bp.testbeds.length && <Empty icon={FlaskConical}>No test environment matched.</Empty>}
          </div>
        </Section>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-7">
          <Section n="9" title="First prototype experiment" badge="HYPOTHESIS">
            <Card className="border-brand/30 bg-brand/[0.05]"><p className="text-[15px] leading-relaxed text-ink">{bp.first_experiment.text}</p></Card>
          </Section>
          <Section n="10" title="Technical requirements">
            <ul className="ml-5 list-disc space-y-1.5 text-sm leading-relaxed text-ink2">{bp.technical_requirements.map((r, i) => <li key={i}>{r.text}</li>)}</ul>
          </Section>
          <Section n="13" title="Suggested next steps">
            <ol className="space-y-2">
              {bp.next_steps.map((x, i) => (
                <li key={i} className="flex gap-3 text-sm leading-relaxed text-ink2">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cyan/15 font-display text-xs font-semibold text-cyan">{i + 1}</span>{x}
                </li>
              ))}
            </ol>
          </Section>
        </div>
        <div className="space-y-7">
          <Section n="11" title="Risks and unknowns">
            <ul className="ml-5 list-disc space-y-1.5 text-sm leading-relaxed text-ink2">{bp.risks.map((r, i) => <li key={i}>{r.text}</li>)}</ul>
          </Section>
          <Section n="12" title="Sources">
            <ul className="space-y-1.5 text-[13px]">
              {bp.sources.map((x) => (
                <li key={x.url}><SourceLink url={x.url}>{x.label}</SourceLink>{x.retrieved_at && <span className="meta"> · retrieved {day(x.retrieved_at)}</span>}</li>
              ))}
            </ul>
          </Section>
        </div>
      </div>

      <Card>
        <h2 className="mb-3 text-lg font-semibold">Was this useful?</h2>
        <RateForm hypothesisKey={bp.key} />
      </Card>
    </div>
  );
}

export default function Blueprint() {
  const { companies, companyId, setViewing } = useSession();
  const [search, setSearch] = useSearchParams();
  const urlKey = search.get("key");
  const [mode, setMode] = useState("recs");
  const [chosen, setChosen] = useState([]);
  const recs = useQuery({ queryKey: ["blueprint-recs", companyId], queryFn: () => api.blueprintRecs(companyId), enabled: mode === "recs" && companyId !== null });

  // A key from the graph or the home page wins; otherwise the company's top recommendation.
  const key = mode === "recs" ? (urlKey ?? recs.data?.[0]?.key ?? null) : null;
  const params = mode === "recs" ? (key ? { key } : null) : (chosen.length >= 2 ? { companies: chosen.join(",") } : null);
  const brief = useQuery({ queryKey: ["blueprint", params], queryFn: () => api.blueprint(params), enabled: params !== null, placeholderData: (p) => p });
  const pick = (k) => setSearch(k ? { key: k } : {}, { replace: true });
  const options = recs.data ?? [];
  const extra = urlKey && !options.some((r) => r.key === urlKey);

  return (
    <>
      <PageHeader eyebrow="Brief" title="Innovation Opportunity Blueprint"
                  subtitle="Select a recommendation, or test your own combination of two or three companies.">
        <Segmented value={mode} onChange={setMode} options={[{ value: "recs", label: "A company's recommendations" }, { value: "own", label: "My own combination" }]} />
      </PageHeader>

      <div className="card mb-6 p-4">
        {mode === "recs" ? (
          <div className="grid gap-4 md:grid-cols-[minmax(200px,280px)_1fr]">
            <CompanyPicker label="Company" companies={companies} value={companyId} onChange={(id) => { setViewing(id); pick(null); }} />
            <label className="block min-w-0">
              <span className="label">Recommendation</span>
              <select className="input" value={key ?? ""} onChange={(e) => pick(e.target.value)} disabled={!options.length && !extra}>
                {extra && <option value={urlKey}>Selected hypothesis</option>}
                {options.map((r) => <option key={r.key} value={r.key}>{r.score.toFixed(0)} - {r.title} - with {r.partners.join(" + ")}</option>)}
              </select>
            </label>
          </div>
        ) : (
          <CompanyPicker className="max-w-xl" label="Companies (two or three)" companies={companies} value={chosen} onChange={setChosen} max={3} />
        )}
      </div>

      {mode === "recs" && recs.isSuccess && !options.length && !urlKey && (
        <Empty>No recommendation exists for this company: it has no evidence-backed capability with a known complementary relationship. Add a capability or interest on the Company DNA page.</Empty>
      )}
      {mode === "own" && chosen.length < 2 && <Empty>Choose two or three companies to run the matching engine, ranking and verification for that combination.</Empty>}
      {params !== null && (
        <QueryState query={brief}>
          {(d) => (d.blueprint ? <Brief bp={d.blueprint} note={d.note} params={params} /> : (
            <div className="space-y-2">
              <Notice tone="sim">{d.note}</Notice>
              <p className="meta">NEXUS does not write a blueprint when it cannot support the combination with evidence.</p>
            </div>
          ))}
        </QueryState>
      )}
    </>
  );
}
