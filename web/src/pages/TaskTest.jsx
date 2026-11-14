import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api";
import { Notice, PageHeader, QueryState } from "../components/ui";

/* A timed task test: the brief's own example task, done once without EchoRadar and once with it.
 * The order alternates between sessions so that learning the task does not favour one side.
 * Only a role is stored, never a name. */
const TASK = "You run a company that develops sensors. Find one test environment and one funding call that would be worth looking at for it.";
const ROLES = [["bsp_staff", "Blue Science Park staff"], ["member", "Member company"], ["mentor_or_judge", "Mentor or judge"], ["other", "Other"]];
const SIDE = {
  without: { title: "Without EchoRadar", how: "Use any other tab: a search engine, vinnova.se, bluesciencepark.se, mtcos.se. Do not use EchoRadar." },
  with: { title: "With EchoRadar", how: "Use EchoRadar only: the paper, the radar, Ask EchoRadar." },
};
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function Round({ side, value, onChange, active, onStart }) {
  const [now, setNow] = useState(Date.now());
  const running = value.startedAt && !value.result;
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [running]);
  const seconds = value.seconds ?? (value.startedAt ? (now - value.startedAt) / 1000 : 0);
  const stop = (result) => onChange({ ...value, result, seconds: (Date.now() - value.startedAt) / 1000 });
  return (
    <section className={clsx("border-t-2 pt-3", active ? "border-ink" : "border-line opacity-60")}>
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="kicker">{value.n === 1 ? "First round" : "Second round"}</div>
          <h3 className="font-serif text-[24px] font-semibold">{SIDE[side].title}</h3>
        </div>
        <div className="font-serif text-[44px] font-semibold tabular-nums leading-none" aria-live="off">{mmss(seconds)}</div>
      </div>
      <p className="mt-1 font-sans text-[14px] text-ink2">{SIDE[side].how}</p>
      {!value.startedAt && (
        <button type="button" className="btn btn-primary mt-3" disabled={!active} onClick={onStart}>Start the clock</button>
      )}
      {running && (
        <div className="mt-3 flex gap-2">
          <button type="button" className="btn btn-primary" onClick={() => stop("found")}>Found both</button>
          <button type="button" className="btn" onClick={() => stop("gave_up")}>Give up</button>
        </div>
      )}
      {value.result && (
        <div className="mt-3 space-y-2">
          <p className="font-sans text-[14px] text-ink2">{value.result === "found" ? "Found" : "Gave up"} after {mmss(seconds)}.</p>
          {value.result === "found" && (
            <>
              <label className="block">
                <span className="label">What did you find? (titles or links; no personal names)</span>
                <input className="input" maxLength={300} value={value.found ?? ""} onChange={(e) => onChange({ ...value, found: e.target.value })} />
              </label>
              <fieldset>
                <legend className="label">Is it a real fit for a sensor company, in your own view?</legend>
                <div className="flex gap-2">
                  {["yes", "partly", "no"].map((f) => (
                    <button key={f} type="button" aria-pressed={value.fit === f} onClick={() => onChange({ ...value, fit: f })}
                            className={clsx("btn", value.fit === f && "btn-on")}>{f}</button>
                  ))}
                </div>
              </fieldset>
            </>
          )}
        </div>
      )}
    </section>
  );
}

export default function TaskTest({ preview }) {
  const qc = useQueryClient();
  const summary = useQuery({ queryKey: ["study"], queryFn: api.study });
  const [role, setRole] = useState("");
  const [practice, setPractice] = useState(false);
  const [rounds, setRounds] = useState({ without: {}, with: {} });
  const [prefer, setPrefer] = useState("");
  const [comment, setComment] = useState("");
  const [saved, setSaved] = useState(null);
  const orderRef = useRef(null);
  const order = orderRef.current ?? summary.data?.next_order ?? "without_first";
  const first = order === "without_first" ? "without" : "with";
  const second = first === "without" ? "with" : "without";
  const save = useMutation({
    mutationFn: () => api.saveStudy({
      role, order, practice, prefer: prefer || null, comment: comment.trim() || null,
      ...Object.fromEntries(["without", "with"].flatMap((k) => [
        [`${k}_seconds`, rounds[k].seconds ?? null], [`${k}_result`, rounds[k].result ?? null],
        [`${k}_found`, rounds[k].found?.trim() || null], [`${k}_fit`, rounds[k].fit ?? null]])),
    }),
    onSuccess: (r) => { setSaved(r); qc.invalidateQueries({ queryKey: ["study"] }); qc.invalidateQueries({ queryKey: ["evaluation"] }); },
  });
  const reset = () => { orderRef.current = null; setRounds({ without: {}, with: {} }); setPrefer(""); setComment(""); setSaved(null); setRole(""); setPractice(false); };
  const start = (k) => { if (!orderRef.current) orderRef.current = order; setRounds((r) => ({ ...r, [k]: { ...r[k], startedAt: Date.now() } })); };
  const done = rounds[first].result && rounds[second].result;

  return (
    <>
      <PageHeader eyebrow="For testers" title="Task test"
                  subtitle="The challenge's own example task, timed once without EchoRadar and once with it. Results appear on the Evaluation page." />
      {preview ? null : (
        <div className="grid gap-10 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="space-y-6">
            <blockquote className="border-l-[3px] border-ink pl-4 font-serif text-[21px] leading-snug">{TASK}</blockquote>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="label">Who is taking part? (a role, never a name)</span>
                <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="">Choose a role</option>
                  {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="flex items-end gap-2 pb-2 font-sans text-[14px] text-ink2">
                <input type="checkbox" checked={practice} onChange={(e) => setPractice(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--brand))]" />
                Practice run (saved, but not counted)
              </label>
            </div>
            <p className="meta">This session starts {first === "without" ? "without EchoRadar" : "with EchoRadar"}; the next session starts the other way round.</p>
            {[first, second].map((k, i) => (
              <Round key={k} side={k} value={{ ...rounds[k], n: i + 1 }} active={!!role && (i === 0 || !!rounds[first].result)}
                     onStart={() => start(k)} onChange={(v) => setRounds((r) => ({ ...r, [k]: v }))} />
            ))}
            {done && !saved && (
              <section className="space-y-3 border-t-2 border-ink pt-3">
                <fieldset>
                  <legend className="label">Next time, which way would you use?</legend>
                  <div className="flex flex-wrap gap-2">
                    {[["nexus", "EchoRadar"], ["without", "My usual way"], ["either", "Either"]].map(([v, l]) => (
                      <button key={v} type="button" aria-pressed={prefer === v} onClick={() => setPrefer(v)} className={clsx("btn", prefer === v && "btn-on")}>{l}</button>
                    ))}
                  </div>
                </fieldset>
                <label className="block">
                  <span className="label">Anything else? What was missing, wrong or useful (optional; no personal names)</span>
                  <textarea className="input min-h-[70px]" maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} />
                </label>
                <button type="button" className="btn btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>
                  {save.isPending ? "Saving..." : "Save this session"}
                </button>
                {save.isError && <Notice tone="error">{save.error.message}</Notice>}
              </section>
            )}
            {saved && (
              <Notice tone="ok">
                Saved{practice ? " as a practice run (not counted)" : ""}. <button type="button" className="link" onClick={reset}>Start the next session</button>
              </Notice>
            )}
          </div>
          <aside className="space-y-4 lg:border-l lg:border-line lg:pl-8">
            <div className="kicker">How to run it fairly</div>
            <ul className="ml-4 list-disc space-y-1.5 font-serif text-[16px] leading-relaxed text-ink2">
              <li>Read the task aloud; do not show where to look.</li>
              <li>Alternate the order between people (the page does it), so being faster the second time does not count for EchoRadar.</li>
              <li>Let the participant judge the fit; do not correct them.</li>
              <li>Three to five people is a small sample. Report it as that.</li>
            </ul>
            <QueryState query={summary}>
              {(d) => (
                <p className="meta">Sessions so far: {d.n} counted, {d.practice_runs} practice.{d.n > 0 && d.without.median_seconds != null && d.with.median_seconds != null
                  && ` Median time without EchoRadar ${mmss(d.without.median_seconds)}, with ${mmss(d.with.median_seconds)}.`}</p>
              )}
            </QueryState>
          </aside>
        </div>
      )}
    </>
  );
}
