import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleSlash, Clock, Gauge, Layers, ShieldCheck, Star, XCircle } from "lucide-react";
import { api } from "../api";
import { Card, Empty, Markdown, Notice, PageHeader, QueryState, SectionTitle, Stat, Tabs } from "../components/ui";

const pct = (x) => (x === null || x === undefined ? "n/a" : `${(x * 100).toFixed(0)}%`);
const METRICS = ["precision@5", "precision@10", "recall@10", "ndcg@10", "spearman"];
const SERIES = [{ key: "nexus", name: "NEXUS complementarity", color: "rgb(var(--brand))" }, { key: "baseline", name: "Similarity baseline", color: "rgb(var(--hyp))" }];

/** Grouped bars on a shared -min..1 scale with a zero line (Spearman can be negative). */
function MetricChart({ cmp }) {
  const min = Math.min(0, ...SERIES.map((s) => cmp[s.key].spearman ?? 0));
  const H = 220, span = 1 - min, y = (v) => ((1 - v) / span) * H;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4">
        {SERIES.map((s) => <span key={s.key} className="flex items-center gap-2 text-[13px] text-ink2"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />{s.name}</span>)}
      </div>
      <div className="relative" style={{ height: H + 34 }}>
        {[1, 0.75, 0.5, 0.25, 0].map((g) => (
          <div key={g} className="absolute inset-x-0 flex items-center gap-2" style={{ top: y(g) + 8 }}>
            <span className="w-7 text-right text-[10.5px] tabular-nums text-muted">{g.toFixed(2).replace(/0$/, "")}</span>
            <span className={g === 0 ? "h-px flex-1 bg-muted/60" : "h-px flex-1 bg-line/60"} />
          </div>
        ))}
        <div className="absolute inset-y-0 left-9 right-0 grid" style={{ gridTemplateColumns: `repeat(${METRICS.length}, 1fr)` }}>
          {METRICS.map((m) => (
            <div key={m} className="relative">
              <div className="absolute inset-x-0 flex justify-center gap-1.5" style={{ top: 8, height: H }}>
                {SERIES.map((s) => {
                  const v = cmp[s.key][m] ?? 0;
                  const top = y(Math.max(v, 0)), h = Math.abs(y(v) - y(0));
                  return (
                    <div key={s.key} className="relative w-[30%] max-w-[46px]" title={`${s.name} ${m}: ${v.toFixed(2)}`}>
                      <div className="absolute inset-x-0 rounded-md transition-all" style={{ top, height: Math.max(h, 2), background: s.color }} />
                      <span className="absolute inset-x-0 text-center text-[11px] font-semibold tabular-nums text-ink" style={{ top: v >= 0 ? top - 16 : top + h + 2 }}>{v.toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
              <div className="absolute inset-x-0 bottom-0 text-center text-[11.5px] text-ink2">{m}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Baseline({ cmp }) {
  const rows = [...cmp.rows].sort((a, b) => b.nexus_complementarity - a.nexus_complementarity);
  const wrong = rows.filter((r) => r.label === 0 && r.nexus_complementarity >= 30).length;
  const missed = rows.filter((r) => r.label >= 1 && r.nexus_complementarity === 0).length;
  return (
    <div className="space-y-5">
      <SectionTitle>Complementarity engine vs similarity-only baseline</SectionTitle>
      <Notice><b className="text-ink">Read with care.</b> {cmp.caveat}<br />Labelled by: {cmp.labelled_by}</Notice>
      <p className="meta">{cmp.n_pairs} labelled pairs ({cmp.n_relevant} labelled complementary). Both methods rank the same pairs; metrics show how well each ranking puts complementary pairs first.</p>
      {!rows.length ? <Empty>None of the labelled company pairs exist in this database, so the comparison cannot be computed.</Empty> : (
        <>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <Card><MetricChart cmp={cmp} /></Card>
            <div className="grid content-start gap-3">
              <Stat value={cmp.nexus.mean_label_top5} label="Mean label of top-5 (0-2), NEXUS" tone="brand" />
              <Stat value={cmp.baseline.mean_label_top5} label="Mean label of top-5 (0-2), baseline" tone="hyp" />
            </div>
          </div>
          <div className="table-wrap max-h-[440px]">
            <table className="table">
              <thead><tr><th>Company A</th><th>Company B</th><th>Label (0-2)</th><th>Labelling rationale</th><th className="text-right">NEXUS complementarity</th><th className="text-right">Baseline cosine</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td className="whitespace-nowrap text-ink">{r.a}</td><td className="whitespace-nowrap text-ink">{r.b}</td>
                    <td><span className={r.label >= 1 ? "font-semibold text-fact" : "text-muted"}>{r.label}</span></td><td className="min-w-[260px]">{r.rationale}</td>
                    <td className="text-right tabular-nums">{r.nexus_complementarity.toFixed(1)}</td><td className="text-right tabular-nums">{r.baseline_similarity.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="meta">
            Visible errors on this set: {wrong} pair(s) labelled 'not complementary' still score 30 or more, and {missed} pair(s)
            labelled complementary score 0 (no relation defined or capability not detected).
          </p>
        </>
      )}
    </div>
  );
}

function KeyValues({ rows }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <tbody>{rows.map(([k, v]) => <tr key={k}><td>{k}</td><td className="text-right font-semibold tabular-nums text-ink">{v ?? "n/a"}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function Coverage({ d }) {
  const cov = d.coverage, diff = d.differentiation, fb = d.feedback;
  return (
    <div className="grid gap-7 lg:grid-cols-2">
      <div className="space-y-5">
        <SectionTitle>Evidence coverage</SectionTitle>
        <KeyValues rows={[
          ["Fact claims", cov.fact_claims], ["Fact claims with valid URL and excerpt", cov.fact_claims_with_url_and_excerpt],
          ["Inferred interests (kept separate)", cov.inferences], ["User-supplied claims (unverified)", cov.user_claims],
          ["Stored hypotheses", cov.hypotheses], ["Hypotheses whose capability claims all have a source", cov.hypotheses_fully_sourced],
          ["Hypotheses with at least one research record", cov.hypotheses_with_research], ["Hypotheses with at least one open/upcoming call", cov.hypotheses_with_open_funding]]} />
        <SectionTitle>Ranking differentiation</SectionTitle>
        <p className="text-sm leading-relaxed text-ink2">
          {diff.companies_with_recommendations} of {diff.companies_total} companies have recommendations. Across {diff.pairs_compared} company
          pairs, {diff.identical_list_pairs} have identical top-{diff.top_k} lists; {diff.distinct_top1} distinct hypotheses appear as someone's number one.
        </p>
        <p className="meta">Companies without recommendations have no evidence-backed capability that the taxonomy recognises.</p>
      </div>
      <div className="space-y-5">
        <SectionTitle>Source freshness</SectionTitle>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Source</th><th className="text-right">Records</th><th className="text-right">Newest (days)</th><th className="text-right">Oldest (days)</th><th className="text-right">Stale</th></tr></thead>
            <tbody>
              {Object.entries(d.freshness).map(([k, v]) => (
                <tr key={k}><td className="text-ink">{k}</td><td className="text-right tabular-nums">{v.records}</td><td className="text-right tabular-nums">{v.newest_days ?? "-"}</td>
                  <td className="text-right tabular-nums">{v.oldest_days ?? "-"}</td><td className="text-right tabular-nums"><span className={v.stale ? "font-semibold text-hyp" : ""}>{v.stale}</span> <span className="text-muted">&gt; {v.stale_limit_days} d</span></td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="meta">Stale sources lower the evidence-quality score and are flagged by the Verification Agent.</p>
        <SectionTitle>Human feedback</SectionTitle>
        {fb.n ? <p className="text-sm text-ink2">{fb.n} ratings, mean {fb.mean} of 5 (anonymous aggregate).</p>
          : <Notice tone="info">No human ratings have been collected yet. Ratings entered on the Blueprint page appear here. No rating has been invented to fill this space.</Notice>}
      </div>
    </div>
  );
}

function Tests({ r }) {
  if (!r) return <Empty>No test run recorded yet. Run <code>python scripts/run_tests.py</code> to execute the suite and record the results.</Empty>;
  const icon = { passed: <CheckCircle2 size={14} className="text-fact" />, failed: <XCircle size={14} className="text-pink" />, skipped: <CircleSlash size={14} className="text-muted" /> };
  return (
    <div className="space-y-4">
      <SectionTitle>Automated test results</SectionTitle>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat value={r.passed} label="Passed" icon={CheckCircle2} tone="fact" /><Stat value={r.failed} label="Failed" icon={XCircle} tone="pink" />
        <Stat value={r.skipped} label="Skipped" icon={CircleSlash} tone="cyan" /><Stat value={`${r.seconds.toFixed(0)} s`} label="Duration" sub={r.run_at} icon={Clock} tone="inf" />
      </div>
      <p className="meta">Command: python -m {r.command}. Live integration tests included: {r.live_included ? "yes" : "no"}.</p>
      <div className="table-wrap max-h-[480px]">
        <table className="table">
          <thead><tr><th>File</th><th>Test</th><th>Outcome</th><th>Type</th></tr></thead>
          <tbody>{r.cases.map((c) => (
            <tr key={c.file + c.name}><td>{c.file}</td><td className="text-ink">{c.name}</td><td><span className="flex items-center gap-1.5">{icon[c.outcome]}{c.outcome}</span></td>
              <td>{c.live ? "LIVE external call" : "deterministic / mocked"}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

const METHOD = `**S = 0.35 C + 0.25 O + 0.20 R + 0.20 E** (each 0-100; weights are initial hypotheses, not tuned on outcomes)

- **C - Capability complementarity.** Explicit relations between *different* capabilities (77 hand-written capability relations and 18 generic value-chain relations), gated by a shared application area and scaled by evidence confidence. The same capability on both sides counts as similarity, not complementarity.
- **O - Opportunity relevance.** Best three currently open or upcoming Vinnova calls: 70% multilingual text similarity + 30% shared capability tags.
- **R - Research relevance.** Same method against OpenAlex works.
- **E - Evidence quality.** Share and strength of the capability claims used: two independent sources > one source > user-supplied; stale sources are discounted.

A component without data counts as 0 and lowers the displayed *data coverage*; it is never filled in.`;

export default function Evaluation() {
  const [tab, setTab] = useState("baseline");
  const query = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation });
  return (
    <>
      <PageHeader eyebrow="Quality" title="Evaluation and Quality" subtitle="Measured on the stored data. Nothing on this page is typed in by hand." />
      <QueryState query={query}>
        {(d) => {
          const cov = d.coverage, fb = d.feedback;
          return (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Stat value={pct(cov.profile_coverage)} label="Profile evidence coverage" sub={`${cov.fact_claims_with_url_and_excerpt} of ${cov.fact_claims} facts have URL + excerpt`} icon={ShieldCheck} tone="fact" />
                <Stat value={pct(cov.recommendation_coverage)} label="Recommendation evidence coverage" sub={`${cov.hypotheses_fully_sourced} of ${cov.hypotheses} hypotheses fully sourced`} icon={Layers} />
                <Stat value={d.differentiation.mean_jaccard_overlap_top_k} label="Top-5 list overlap between companies" sub="Jaccard; 0 = fully different, 1 = identical" icon={Gauge} tone="cyan" />
                <Stat value={fb.n ? fb.mean : "n/a"} label="Mean human relevance rating" sub={`${fb.n} ratings collected in the app`} icon={Star} tone="inf" />
              </div>
              {!d.embedding.semantic && <Notice tone="sim" className="mb-4">Embedding FALLBACK active ({d.embedding.backend}): {d.embedding.fallback_reason}</Notice>}
              <Tabs value={tab} onChange={setTab} tabs={[{ id: "baseline", label: "Baseline comparison" }, { id: "coverage", label: "Coverage and freshness" },
                                                         { id: "tests", label: "Automated tests", count: d.tests?.total }, { id: "method", label: "Method and limitations" }]} />
              <div className="animate-rise" key={tab}>
                {tab === "baseline" && <Baseline cmp={d.comparison} />}
                {tab === "coverage" && <Coverage d={d} />}
                {tab === "tests" && <Tests r={d.tests} />}
                {tab === "method" && (
                  <div className="grid gap-6 lg:grid-cols-2">
                    <Card><h2 className="mb-3 text-lg font-semibold">How the score is built</h2><Markdown text={METHOD} /></Card>
                    <Card><h2 className="mb-3 text-lg font-semibold">Known limitations</h2><Markdown text={d.limitations ?? "See docs/known_limitations.md"} /></Card>
                  </div>
                )}
              </div>
            </>
          );
        }}
      </QueryState>
    </>
  );
}
