import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ArrowRight, ArrowUpRight, BadgeCheck, Building2, CheckCircle2, CircleDashed, GitCompareArrows, Globe,
         Lightbulb, Lock, MapPin, Pencil, ShieldCheck, Users } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import { Badge, Card, Chip, CompanyPicker, Disclosure, Empty, HypothesisNotice, Notice, PageHeader, QueryState, Ring, ScoreBars,
         SourceLink, Stat, Tabs, Translated, stamp } from "../components/ui";

function ClaimCard({ claim: cl }) {
  const ev = cl.evidence;
  const head = cl.capability && cl.category === "capability" && cl.classification === "FACT" ? cl.capability.name : cl.text;
  return (
    <div className="rounded-xl border border-line bg-bg/40 p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge kind={cl.classification} />
        <span className="meta">
          confidence {cl.confidence.toFixed(2)} · {(ev?.status ?? "unsupported").replace(/_/g, " ")} ·{" "}
          {ev?.retrieved_at ? `retrieved ${stamp(ev.retrieved_at)} UTC` : "no retrieval date"}
        </span>
      </div>
      <h4 className="mt-1.5 text-sm font-semibold leading-snug">{head}</h4>
      {ev && (cl.classification !== "INFERENCE"
        ? <blockquote className="quote">“{ev.text.slice(0, 420)}”</blockquote>
        : <p className="mt-1 text-[13px] leading-relaxed text-ink2">{ev.text.split(" Domain key:")[0]}</p>)}
      {ev && <p className="text-xs"><SourceLink url={ev.url} /></p>}
    </div>
  );
}

/* ---- directory verification ---------------------------------------------------------------------- */
const STATUS = {
  verified: { label: "Verified against the official profile", tone: "border-fact/35 bg-fact/10 text-fact", icon: BadgeCheck },
  check_failed: { label: "Last check failed", tone: "border-pink/40 bg-pink/10 text-pink", icon: AlertTriangle },
  not_listed: { label: "No longer in the directory listing", tone: "border-hyp/40 bg-hyp/10 text-hyp", icon: AlertTriangle },
  outside_listing: { label: "Profile found outside the directory listing", tone: "border-inf/40 bg-inf/10 text-inf", icon: CircleDashed },
  not_verified: { label: "Not yet verified by a directory sync", tone: "border-line bg-surface2 text-ink2", icon: CircleDashed },
};

export function VerificationBadge({ v }) {
  const s = STATUS[v.status] ?? STATUS.not_verified;
  const Icon = s.icon;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11.5px] font-medium", s.tone)}
          title={v.last_verified_at ? `Profile page read ${stamp(v.last_verified_at)} UTC` : undefined}>
      <Icon size={13} />{s.label}{v.status === "verified" && v.last_verified_at && <span className="opacity-80">· {stamp(v.last_verified_at).slice(0, 10)}</span>}
    </span>
  );
}

/** A small link to the exact page a displayed fact was copied from. */
function FactSource({ f }) {
  if (!f?.url) return null;
  return (
    <a href={f.url} target="_blank" rel="noopener noreferrer" className="ml-1 inline-flex align-middle text-muted hover:text-brand"
       title={`Source: ${f.source}, read ${stamp(f.retrieved_at)} UTC`} aria-label={`Source for ${f.label}`}>
      <ArrowUpRight size={12} />
    </a>
  );
}

function DirectoryRecord({ v }) {
  const differs = v.fields.filter((f) => f.seed && !f.seed.agrees);
  const seeded = v.fields.some((f) => f.seed);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <VerificationBadge v={v} />
        <span className="meta">
          Fetch status: {v.fetch_status ?? "never fetched"}{v.snapshot_id && ` · snapshot ${v.snapshot_id}`}
        </span>
      </div>
      <p className="meta max-w-3xl leading-relaxed">
        Every fact below was copied from the company's official Blue Science Park profile page; the link next to each
        value opens that exact page. Facts the page does not publish are left empty, never filled in from elsewhere.
        {seeded && " The imported audited seed is shown as a second source and never replaces the official text."}
      </p>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Field</th><th>Value on the official profile</th><th>Source</th>{seeded && <th>Audited seed (2026-11-13)</th>}</tr></thead>
          <tbody>
            {v.fields.map((f) => (
              <tr key={f.field}>
                <td className="whitespace-nowrap font-medium text-ink">{f.label}</td>
                <td className="min-w-[220px]">
                  {f.value ? <span className={f.field === "description" ? "block max-w-xl leading-relaxed" : ""}>{f.field === "website"
                    ? <a className="link" href={f.value} target="_blank" rel="noopener noreferrer">{f.value}</a> : f.value}</span>
                    : <span className="italic text-muted">not published on the profile</span>}
                </td>
                <td className="whitespace-nowrap">
                  {f.url ? <SourceLink url={f.url}>BSP profile</SourceLink> : <span className="text-muted">-</span>}
                  {f.retrieved_at && <div className="meta">{stamp(f.retrieved_at)} UTC</div>}
                </td>
                {seeded && (
                  <td className="min-w-[180px]">
                    {!f.seed ? <span className="text-muted">-</span> : f.seed.agrees
                      ? <span className="inline-flex items-center gap-1 text-fact"><CheckCircle2 size={13} />agrees</span>
                      : <span className="block text-[12.5px] leading-relaxed"><span className="inline-flex items-center gap-1 font-medium text-inf"><GitCompareArrows size={13} />differs:</span> {f.seed.value ?? <i className="text-muted">empty</i>}</span>}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {differs.length > 0 && (
        <Notice tone="sim" icon={GitCompareArrows}>
          The audited seed differs from the live official page on {differs.map((f) => f.label.toLowerCase().split(" (")[0]).join(", ")}.
          NEXUS shows the official page's wording; the seed values are kept for review only.
        </Notice>
      )}
      <dl className="grid gap-x-6 gap-y-2 text-[13px] sm:grid-cols-2">
        <div><dt className="meta">Member or partner</dt><dd className="text-ink2">Not disclosed per organisation by Blue Science Park, so not stated here.</dd></div>
        <div><dt className="meta">Directory listing</dt><dd className="text-ink2">{{ listed: "Listed in the public member directory", related_link_only: "Found through a related-member link only", seed_only: "Found only through the audited seed", not_in_latest_listing: "Not in the latest listing (kept until an admin confirms removal)" }[v.listing_status] ?? "Unknown"}</dd></div>
        {v.aliases.length > 0 && <div className="sm:col-span-2"><dt className="meta">Also known as</dt><dd className="break-all text-ink2">{v.aliases.join(" · ")}</dd></div>}
      </dl>
    </div>
  );
}

function Facts({ facts }) {
  const caps = facts.filter((x) => x.category === "capability");
  const other = facts.filter((x) => x.category !== "capability");
  const groups = useMemo(() => {
    const m = new Map();
    caps.forEach((x) => { const k = x.capability?.key ?? "?"; m.set(k, [...(m.get(k) ?? []), x]); });
    return [...m.values()];
  }, [caps]);
  return (
    <div className="space-y-6">
      <p className="meta">Each fact is a statement found in a public source. The quoted sentence is the evidence.</p>
      {groups.length ? (
        <div>
          <h3 className="mb-2.5 text-sm font-semibold text-ink2">Technology capabilities</h3>
          <div className="grid items-start gap-3 lg:grid-cols-2">
            {groups.map((rows, i) => (
              <Disclosure key={rows[0].id} defaultOpen={i < 2}
                          title={<span className="flex flex-wrap items-center gap-2"><b className="text-ink">{rows[0].capability?.name}</b>
                            <span className="meta">{rows.length} source(s) · confidence {rows[0].confidence.toFixed(2)}</span></span>}>
                {rows[0].capability?.role_label && <p className="meta mb-2">{rows[0].capability.role_label}</p>}
                <div className="space-y-2.5">{rows.map((r) => <ClaimCard key={r.id} claim={r} />)}</div>
              </Disclosure>
            ))}
          </div>
        </div>
      ) : <Empty icon={ShieldCheck}>No capability could be confirmed from public text. NEXUS does not guess from the company name.</Empty>}
      {other.length > 0 && (
        <div>
          <h3 className="mb-2.5 text-sm font-semibold text-ink2">Description, industry, geography, markets, collaborations and development activities</h3>
          <div className="grid items-start gap-3 lg:grid-cols-2">{other.map((x) => <ClaimCard key={x.id} claim={x} />)}</div>
        </div>
      )}
    </div>
  );
}

function Refine({ data }) {
  const { meta } = useSession();
  const qc = useQueryClient();
  const c = data.company;
  const editable = data.claims.filter((k) => ["capability", "interest"].includes(k.category));
  const initial = () => ({ description: c.user_description ?? "", needs: c.needs, domains: c.domains, new_interest: "", new_capability: "",
                           share_refinements: !!c.share_refinements, claims: Object.fromEntries(editable.map((k) => [k.id, k.active])) });
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState(null);
  useEffect(() => { setForm(initial()); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (patch) => { setForm((f) => ({ ...f, ...patch })); if (result?.preview) setResult(null); };
  const flip = (key, v) => set({ [key]: form[key].includes(v) ? form[key].filter((x) => x !== v) : [...form[key], v] });
  const save = useMutation({
    mutationFn: (preview) => api.refine(c.id, { ...form, preview }),
    onSuccess: (res) => { setResult(res); if (res.changes.length && !res.preview) qc.invalidateQueries(); },
  });
  const busy = save.isPending;
  const user = data.claims.filter((x) => x.active && x.classification === "USER");

  if (!data.can_edit) {
    return (
      <Notice tone="info" icon={Lock}>
        Select <b className="text-ink">{c.name}</b> under “Acting as” in the sidebar to refine this profile. Public facts
        stay visible to everyone; refinements are attributed to the company.
      </Notice>
    );
  }
  return (
    <div className="space-y-5">
      <Notice tone="info" icon={Lock}>
        <b className="text-ink">Private by default.</b> What you enter here is visible only to {c.name} and only changes your own
        radar and recommendations. Other members, visitors and staff see it only if you choose to share it below. Public facts are
        never overwritten.
      </Notice>
      <form className="card card-pad space-y-5" onSubmit={(e) => { e.preventDefault(); save.mutate(false); }}>
        <label className="block">
          <span className="label">What would you like help with?</span>
          <input className="input" value={form.new_interest} maxLength={300} placeholder="A short current goal, e.g. machine learning for sonar data"
                 onChange={(e) => set({ new_interest: e.target.value })} />
          <span className="meta mt-1 block">Saved as something you are looking for; it is matched against other members' evidenced capabilities.</span>
        </label>
        <div>
          <span className="label">I'm looking for</span>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={!form.needs.length} onClick={() => set({ needs: [] })}>Anything relevant</Chip>
            {Object.entries(meta.need_areas).map(([k, label]) => <Chip key={k} active={form.needs.includes(k)} onClick={() => flip("needs", k)}>{label}</Chip>)}
          </div>
          <span className="meta mt-1 block">Chosen areas move to the top of your radar. Nothing is hidden.</span>
        </div>
        <div>
          <span className="label">Subject areas - optional</span>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(meta.domains).map(([k, label]) => <Chip key={k} active={form.domains.includes(k)} onClick={() => flip("domains", k)}>{label}</Chip>)}
          </div>
          <span className="meta mt-1 block">Partner suggestions in these subjects are ranked higher for you; other findings stay accessible.</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">Something you can offer - optional</span>
            <input className="input" value={form.new_capability} maxLength={300} placeholder="e.g. ROV inspection"
                   onChange={(e) => set({ new_capability: e.target.value })} />
          </label>
          <label className="block">
            <span className="label">Describe the company in your own words - optional</span>
            <textarea className="input min-h-[42px]" value={form.description} placeholder={c.description ?? ""} maxLength={4000}
                      onChange={(e) => set({ description: e.target.value })} />
          </label>
        </div>
        {editable.length > 0 && (
          <fieldset>
            <legend className="label">Keep or remove existing claims (removed claims are hidden and ignored, not deleted)</legend>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {editable.map((x) => (
                <label key={x.id} className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line bg-bg/40 px-3 py-2 text-[13px] text-ink2 hover:border-brand/40">
                  <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[rgb(var(--brand))]" checked={form.claims[x.id] ?? x.active}
                         onChange={(e) => set({ claims: { ...form.claims, [x.id]: e.target.checked } })} />
                  <span className="min-w-0">
                    <Badge kind={x.classification} className="mr-1.5" />
                    {x.capability && x.classification !== "USER" && <b className="text-ink">{x.capability.name}: </b>}{x.text.slice(0, 70)}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-bg/40 p-3.5">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[rgb(var(--brand))]" checked={form.share_refinements}
                 onChange={(e) => set({ share_refinements: e.target.checked })} />
          <span className="text-[13px] leading-relaxed text-ink2">
            <b className="text-ink">Share my description and additions with other members</b><br />
            When shared, they appear on your public profile labelled USER and are used to suggest partners for other companies.
            Your "I'm looking for" and subject areas always stay private.
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className="btn !px-4 !py-2" disabled={busy} onClick={() => save.mutate(true)}>
            {busy && save.variables === true ? "Calculating..." : "See changes before saving"}
          </button>
          <button className="btn btn-primary !px-4 !py-2" disabled={busy}>
            {busy && save.variables === false ? "Saving..." : "Save and update my results"}
          </button>
          {busy && <span className="meta">The ranking is being recalculated with your changes...</span>}
        </div>
        {save.isError && <Notice tone="error">{save.error.message}</Notice>}
      </form>

      {result && (result.changes.length === 0 ? <Notice tone="info">No changes to {result.preview ? "preview" : "save"}.</Notice> : (
        <Card className={clsx("space-y-3", result.preview && "border-dashed border-brand/50")}>
          {result.preview
            ? <Notice tone="info" icon={GitCompareArrows}><b className="text-ink">Preview - nothing has been saved.</b> {result.changes.join("; ")}. Press "Save and update my results" to keep this.</Notice>
            : <Notice tone="ok" icon={CheckCircle2}><b className="text-ink">Saved:</b> {result.changes.join("; ")}</Notice>}
          <p className="meta">
            Partner suggestions, top 5: {result.new_recommendations} new entr{result.new_recommendations === 1 ? "y" : "ies"}
            {result.recommendations_changed ? "" : " (order and content unchanged)"}.
          </p>
          {JSON.stringify(result.radar_before) !== JSON.stringify(result.radar_after) ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {[["Your radar top 5 now", result.radar_before], [result.preview ? "Your radar top 5 if you save" : "Your radar top 5 after saving", result.radar_after]].map(([title, rows]) => (
                <div key={title}>
                  <h4 className="mb-1.5 text-sm font-semibold">{title}</h4>
                  <ol className="list-decimal space-y-1 pl-5 text-[13px] text-ink2">
                    {rows.map((r, i) => <li key={i}><span className="text-muted">{r.kind}:</span> {r.title}</li>)}
                  </ol>
                </div>
              ))}
            </div>
          ) : <p className="meta">Your radar top 5 is unchanged by this edit.</p>}
        </Card>
      ))}
      {user.length > 0 && (
        <div>
          <h3 className="mb-2.5 text-sm font-semibold text-ink2">
            Current refinements <span className="meta font-normal">({c.share_refinements ? "shared with other members" : "private to your company"})</span>
          </h3>
          <div className="grid items-start gap-3 lg:grid-cols-2">{user.map((x) => <ClaimCard key={x.id} claim={x} />)}</div>
        </div>
      )}
    </div>
  );
}

function Recommendations({ recs }) {
  const { meta } = useSession();
  return (
    <div className="space-y-4">
      <HypothesisNotice />
      {!recs.length && <Empty>No recommendation: this company has no evidence-backed capability with a known complementary relationship.</Empty>}
      {recs.map((r) => (
        <div key={r.key} className="card grid gap-5 p-5 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div>
            <div className="flex flex-wrap items-center gap-2"><Badge kind="HYPOTHESIS" /><span className="meta">#{r.rank} · {r.kind}</span></div>
            <h4 className="mt-1.5 text-base font-semibold leading-snug">{r.title}</h4>
            <p className="mt-0.5 text-sm font-medium text-ink">with {r.partners.join(" + ")}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink2">{r.explanation}</p>
            <Link to={`/blueprint?key=${encodeURIComponent(r.key)}`} className="link mt-2.5 text-[13px]">Open the full brief <ArrowRight size={13} /></Link>
          </div>
          <div>
            <div className="mb-3 flex items-center gap-3">
              <Ring value={r.score} label="Score" />
              <span className="meta">of 100 · data coverage {((r.breakdown.coverage ?? 0) * 100).toFixed(0)}%</span>
            </div>
            <ScoreBars breakdown={r.breakdown} labels={meta.score_labels} />
          </div>
        </div>
      ))}
      <p className="meta">Scores express strength of fit and evidence, not probability of commercial success.</p>
    </div>
  );
}

function History({ data }) {
  const c = data.company;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <h3 className="mb-2.5 text-sm font-semibold text-ink2">Profile revisions (public information vs. company refinements)</h3>
        {data.revisions.length ? (
          <div className="table-wrap max-h-[420px]">
            <table className="table">
              <thead><tr><th>When (UTC)</th><th>By</th><th>Change</th></tr></thead>
              <tbody>{data.revisions.map((r, i) => <tr key={i}><td className="whitespace-nowrap tabular-nums">{stamp(r.when)}</td><td>{r.author}</td><td>{r.summary}</td></tr>)}</tbody>
            </table>
          </div>
        ) : data.can_edit ? <p className="meta">No refinements yet: the profile shows only what public sources state.</p>
          : <p className="meta flex items-center gap-1.5"><Lock size={13} />The revision history is private to {c.name}.</p>}
      </div>
      <div>
        <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-ink2"><Lock size={14} />Private interactions</h3>
        {data.private ? (
          <>
            <p className="meta mb-2">Visible only to {c.name}: {data.private.interaction_count} questions asked, {data.private.feedback_count} feedback entries.</p>
            {data.private.interactions.length > 0 && (
              <div className="table-wrap max-h-[380px]">
                <table className="table">
                  <thead><tr><th>When (UTC)</th><th>Type</th><th>Text</th><th>Boundary result</th></tr></thead>
                  <tbody>{data.private.interactions.map((r, i) => (
                    <tr key={i}><td className="whitespace-nowrap tabular-nums">{stamp(r.when)}</td><td>{r.kind}</td><td>{r.text}</td><td>{r.outcome}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </>
        ) : <Notice tone="error" icon={Lock}>Access denied: private data is only visible to the company that owns it.</Notice>}
      </div>
    </div>
  );
}

export default function CompanyDNA() {
  const { companies, companyId, setViewing, acting } = useSession();
  const [tab, setTab] = useState("facts");
  const query = useQuery({ queryKey: ["dna", companyId, acting], queryFn: () => api.dna(companyId), enabled: companyId !== null });
  return (
    <>
      <PageHeader eyebrow="Profile" title="Company DNA"
                  subtitle="What public sources say about a company, what NEXUS infers, and what the company has added.">
        <CompanyPicker className="w-72" companies={companies} value={companyId} onChange={setViewing} />
      </PageHeader>
      <QueryState query={query}>
        {(data) => {
          const c = data.company;
          const active = data.claims.filter((x) => x.active);
          const facts = active.filter((x) => x.classification === "FACT");
          const inferred = active.filter((x) => x.classification === "INFERENCE");
          const user = active.filter((x) => x.classification === "USER");
          const capCount = new Set(facts.filter((x) => x.category === "capability" && x.capability).map((x) => x.capability.key)).size;
          const vf = Object.fromEntries(data.verification.fields.map((f) => [f.field, f]));
          return (
            <>
              <div className="mb-6 grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                <Card className="relative overflow-hidden">
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand/10 to-transparent" />
                  <div className="relative">
                    <div className="flex items-start gap-3.5">
                      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-brand/15 font-display text-lg font-semibold text-brand">
                        {c.name.slice(0, 2).toUpperCase()}
                      </span>
                      <div className="min-w-0">
                        <h2 className="text-2xl font-semibold leading-tight">{c.name}</h2>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2">
                          <button onClick={() => setTab("directory")} className="rounded-full transition hover:brightness-110"><VerificationBadge v={data.verification} /></button>
                          <SourceLink url={c.directory_url} className="text-xs">official profile</SourceLink>
                        </div>
                      </div>
                    </div>
                    <p className="mt-4 text-[14.5px] leading-relaxed text-ink2">
                      <Badge kind="FACT" className="mr-2 align-middle" />
                      {c.description ? <Translated original={c.description} en={c.description_en} /> : "No public description found."}
                      <FactSource f={vf.description} />
                    </p>
                    {c.user_description && (
                      <div className="mt-4 rounded-xl border border-user/30 bg-user/[0.06] p-3.5">
                        <div className="flex flex-wrap items-center gap-2"><Badge kind="USER" /><span className="meta">company refinement (not independently verified)</span></div>
                        <p className="mt-1.5 text-sm leading-relaxed text-ink2">{c.user_description}</p>
                      </div>
                    )}
                    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px] sm:grid-cols-4">
                      {[[Building2, "Industry", "industry"], [MapPin, "Location", "location"], [Users, "Employees", "employees"], [Pencil, "Founded", "founded"]].map(([Icon, k, f]) => (
                        <div key={k}><dt className="meta flex items-center gap-1"><Icon size={12} />{k}{c[f] && <FactSource f={vf[f]} />}</dt>
                          <dd className="mt-0.5 text-ink">{c[f] ? (f === "industry" ? <Translated original={c[f]} en={c.industry_en} /> : c[f])
                            : <span className="text-muted" title="Not published on the official profile">not published</span>}</dd></div>
                      ))}
                    </dl>
                    {c.website && <p className="mt-3 flex items-center gap-1.5 text-[13px]"><Globe size={13} className="text-muted" /><SourceLink url={c.website}>{c.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}</SourceLink><span className="meta">as linked on the official profile</span></p>}
                  </div>
                </Card>
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <Stat value={capCount} label="Capabilities" sub="with public source" tone="fact" />
                    <Stat value={inferred.length} label="Inferred interests" sub="derived, not stated" tone="inf" />
                    <Stat value={user.length} label="User refinements" sub="unverified" tone="user" />
                  </div>
                  {data.gaps.length > 0 && (
                    <Disclosure title={`Missing or uncertain information (${data.gaps.length})`} defaultOpen>
                      <ul className="ml-4 list-disc space-y-1 text-[13px] leading-relaxed text-ink2">{data.gaps.map((g) => <li key={g}>{g}</li>)}</ul>
                      <p className="meta mt-2">Gaps are stated, not filled in. The company can add what is missing under “Review and refine”.</p>
                    </Disclosure>
                  )}
                  <p className="meta">
                    Profile depth: {c.profile_depth === "website" ? "member directory + official website" : "member directory only"}.
                    Last updated {stamp(c.updated_at)} UTC.
                  </p>
                </div>
              </div>

              <Tabs value={tab} onChange={setTab} tabs={[
                { id: "facts", label: "Verified facts", count: facts.length },
                { id: "inferred", label: "Inferred interests", count: inferred.length },
                { id: "refine", label: "Review and refine", count: user.length },
                { id: "recs", label: "Recommendations", count: data.recommendations.length },
                { id: "directory", label: "Directory record" },
                { id: "history", label: "History and private data" },
              ]} />
              <div className={clsx("animate-rise")} key={tab}>
                {tab === "facts" && <Facts facts={facts} />}
                {tab === "inferred" && (
                  <div className="space-y-3">
                    <p className="meta">Interests are inferred from the evidenced capabilities. They are never presented as facts and are not used as evidence in rankings.</p>
                    {inferred.length
                      ? <div className="grid items-start gap-3 lg:grid-cols-2">{inferred.map((x) => <ClaimCard key={x.id} claim={x} />)}</div>
                      : <Empty icon={Lightbulb}>Nothing inferred: there are too few evidenced capabilities.</Empty>}
                  </div>
                )}
                {tab === "refine" && <Refine data={data} />}
                {tab === "recs" && <Recommendations recs={data.recommendations} />}
                {tab === "directory" && <DirectoryRecord v={data.verification} />}
                {tab === "history" && <History data={data} />}
              </div>
            </>
          );
        }}
      </QueryState>
    </>
  );
}
