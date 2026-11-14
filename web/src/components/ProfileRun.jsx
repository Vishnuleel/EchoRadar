import { useMutation } from "@tanstack/react-query";
import { api } from "../api";
import { Badge, Disclosure, Notice, SourceLink, Translated, stamp } from "./ui";

/* The profiling agent, run again in the open: what it read, what it found and what changed since the
 * stored profile. Steps appear one after another (a short stagger) so the order of the agents is visible;
 * nothing is saved. */
const STAGGER = 110;

function Step({ i, step }) {
  return (
    <li className="grid animate-rise grid-cols-[28px_1fr] gap-3 border-b border-line py-2.5"
        style={{ animationDelay: `${i * STAGGER}ms`, animationFillMode: "both" }}>
      <span className="font-serif text-[20px] font-semibold leading-none text-muted">{i + 1}</span>
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="font-sans text-[14px] font-semibold text-ink">{step.agent}</span>
          <span className="meta">{step.status}</span>
        </div>
        <p className="font-sans text-[14px] text-ink2">{step.did}{step.url && <> · <SourceLink url={step.url} /></>}</p>
        {step.note && <p className="meta mt-0.5">{step.note}</p>}
        {step.errors?.length > 0 && <p className="meta mt-0.5">Could not read: {step.errors.join("; ")}</p>}
      </div>
    </li>
  );
}

export default function ProfileRun({ companyId, name }) {
  const run = useMutation({ mutationFn: (fresh) => api.recheck(companyId, fresh) });
  const r = run.data;
  const fresh = run.variables;
  const busy = run.isPending;
  const steps = r?.steps ?? [];
  const delay = (steps.length + 1) * STAGGER;

  return (
    <section className="border-t-2 border-ink pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className="kicker">How this profile is made</div>
          <h3 className="font-serif text-[22px] font-semibold leading-tight">Watch the agent read {name}'s public sources</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => run.mutate(true)}>
            {busy && fresh ? "Reading the websites..." : "Read the sources live"}
          </button>
          <button type="button" className="btn" disabled={busy} onClick={() => run.mutate(false)}>
            {busy && !fresh ? "Reading stored copies..." : "Use stored copies"}
          </button>
        </div>
      </div>
      <p className="meta mt-1">
        Runs the same agents that built this profile, then compares the result with the stored profile. Nothing is
        saved. A live read can take up to half a minute; stored copies work offline.
      </p>

      {busy && <p className="mt-3 font-serif text-[16px] italic text-ink2">The directory page and the company website are being read...</p>}
      {run.isError && <Notice tone="error" className="mt-3">{run.error.message}</Notice>}

      {r && !busy && (
        <div className="mt-3 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div>
            <ol>{steps.map((st, i) => <Step key={st.agent} i={i} step={st} />)}</ol>
            <p className="meta mt-2">
              {r.fresh ? "Read live" : "Read from stored copies"} in {r.seconds} s. {r.note}
            </p>
            {r.pages.length > 0 && (
              <div className="mt-2"><Disclosure title={`Pages read (${r.pages.length})`}>
                <ul className="space-y-1 text-[13px] text-ink2">
                  {r.pages.map((p) => (
                    <li key={p.url}><SourceLink url={p.url}>{p.url.replace(/^https?:\/\//, "")}</SourceLink>
                      <span className="text-muted"> · {p.sentences} sentences · {stamp(p.retrieved_at)} UTC</span></li>
                  ))}
                </ul>
              </Disclosure></div>
            )}
          </div>

          <div className="animate-rise space-y-4" style={{ animationDelay: `${delay}ms`, animationFillMode: "both" }}>
            <div>
              <div className="kicker mb-1.5">Technologies and expertise found</div>
              {r.capabilities.length ? (
                <ul className="space-y-2.5">
                  {r.capabilities.map((c) => (
                    <li key={c.key}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge kind="FACT" />
                        <span className="font-serif text-[17px] font-semibold">{c.name}</span>
                        <span className={c.status === "new" ? "font-sans text-[12.5px] font-semibold text-sea" : "meta"}>
                          {c.status === "new" ? "new since the stored profile" : "already in the profile"}
                        </span>
                      </div>
                      <blockquote className="quote !my-1">
                        <Translated original={c.quotes[0].text} en={c.quotes[0].text_en} /> <SourceLink url={c.quotes[0].url} className="not-italic" />
                      </blockquote>
                    </li>
                  ))}
                </ul>
              ) : <p className="meta">No capability is stated clearly enough in the public text. Nothing is guessed.</p>}
              {r.no_longer_found.length > 0 && (
                <p className="mt-2 font-sans text-[14px] text-ink2">
                  <span className="font-semibold text-ink">No longer found:</span> {r.no_longer_found.join(", ")}.
                  The stored profile keeps them until the profile is rebuilt.
                </p>
              )}
            </div>
            {r.inferences.length > 0 && (
              <div>
                <div className="kicker mb-1.5">Inferred, not stated</div>
                <ul className="space-y-1 font-sans text-[14px] text-ink2">
                  {r.inferences.map((x) => <li key={x}><Badge kind="INFERENCE" /> {x}</li>)}
                </ul>
              </div>
            )}
            {r.missing.length > 0 && (
              <p className="font-sans text-[14px] text-ink2"><span className="font-semibold text-ink">Not stated in public sources:</span> {r.missing.join(", ").toLowerCase()}.</p>
            )}
            {(r.quarantined.length > 0 || r.not_used.length > 0) && (
              <Disclosure title={`Set aside: ${r.quarantined.length} instruction-like, ${r.not_used.length} negated, historical or about others`}>
                <ul className="space-y-1 text-[13px] text-ink2">
                  {[...r.quarantined, ...r.not_used].map((x) => <li key={x}>{x}</li>)}
                </ul>
              </Disclosure>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
