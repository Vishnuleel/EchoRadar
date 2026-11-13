import clsx from "clsx";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookOpen, CalendarDays, Banknote, FlaskConical, HelpCircle, Lightbulb, Newspaper, ShieldCheck,
         ArrowRightCircle, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../api";
import { Badge, Ring, SourceLink, day } from "./ui";

export const KIND = {
  funding: { icon: Banknote, color: "rgb(var(--inf))", label: "Funding" },
  testbed: { icon: FlaskConical, color: "rgb(var(--pink))", label: "Testing" },
  event: { icon: CalendarDays, color: "rgb(var(--user))", label: "Events" },
  research: { icon: BookOpen, color: "rgb(var(--brand))", label: "Research" },
  news: { icon: Newspaper, color: "rgb(var(--cyan))", label: "News" },
};

const same = (a, b) => a.kind === b.kind && a.ref_id === b.ref_id;

/** Apply a mark to cached radar / home data right away, before the server answers. */
function applyMark(data, m) {
  if (!data) return data;
  const touch = (items) => items
    .filter((i) => !(m.action === "not_useful" && m.on && same(i, m)))
    .map((i) => {
      if (!same(i, m)) return i;
      let marks = (i.marks ?? []).filter((x) => x !== m.action && !(m.on && m.action === "useful" && x === "not_useful"));
      if (m.on) marks = [...marks, m.action];
      return { ...i, marks };
    });
  if (Array.isArray(data.items)) return { ...data, items: touch(data.items) };
  if (data.digest) {
    const digest = Object.fromEntries(Object.entries(data.digest).map(([k, v]) =>
      [k, Array.isArray(v) && v.length && typeof v[0] === "object" ? touch(v) : v]));
    return { ...data, digest };
  }
  return data;
}

/** Save / useful / not useful. The click shows instantly; the server then re-ranks this company only. */
export function useMark() {
  const qc = useQueryClient();
  const mine = { predicate: (q) => ["radar", "home"].includes(q.queryKey[0]) };
  return useMutation({
    mutationFn: api.mark,
    onMutate: async (m) => {
      await qc.cancelQueries(mine);
      const before = qc.getQueriesData(mine);
      qc.setQueriesData(mine, (data) => applyMark(data, m));
      return { before };
    },
    onError: (_e, _m, ctx) => ctx?.before?.forEach(([key, data]) => qc.setQueryData(key, data)),
    onSettled: () => qc.invalidateQueries({ predicate: (q) => ["radar", "home", "graph", "dna"].includes(q.queryKey[0]) }),
  });
}

function Row({ icon: Icon, label, children, tone = "text-brand" }) {
  return (
    <div className="flex gap-2.5 text-[13px] leading-relaxed">
      <Icon size={15} className={clsx("mt-[3px] shrink-0", tone)} />
      <div className="min-w-0 text-ink2"><span className="font-semibold text-ink">{label}</span> {children}</div>
    </div>
  );
}

/** One radar item: why it fits / what supports it / what to do next, with its uncertainty. */
export default function ItemCard({ item: it, canMark, compact }) {
  const mark = useMark();
  const kind = KIND[it.kind] ?? KIND.news;
  const Icon = kind.icon;
  const marks = new Set(it.marks ?? []);
  const toggle = (action) => mark.mutate({ kind: it.kind, ref_id: it.ref_id, action, on: !marks.has(action) });

  return (
    <article className={clsx("card group animate-rise transition hover:border-brand/40", compact ? "p-3.5" : "p-5")}>
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl" style={{ background: `color-mix(in srgb, ${kind.color} 14%, transparent)`, color: kind.color }}>
          <Icon size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge kind="neutral">{it.area}</Badge>
            {it.status && <Badge kind={["open", "upcoming", "recurring"].includes(it.status) ? it.status : "neutral"}>{it.status}</Badge>}
            {(it.flags ?? []).map((f) => <Badge key={f} kind="HYPOTHESIS">{f}</Badge>)}
            {it.priority_area && <Badge kind="USER">your priority</Badge>}
          </div>
          <h3 className={clsx("mt-1.5 font-semibold leading-snug", compact ? "text-sm" : "text-base")}>{it.title?.slice(0, 150)}</h3>
          <div className="meta mt-1">{it.source} · {it.date_label}</div>
        </div>
        <Ring value={it.relevance} size={compact ? 42 : 52} stroke={compact ? 4 : 5} label="Relevance" />
      </div>

      <div className="mt-3.5 space-y-2">
        <Row icon={Lightbulb} label="Why it fits:" tone="text-inf">
          {it.why}{" "}
          {(it.matched ?? []).map((c) => <Badge key={c} kind="SOURCED" className="ml-1 normal-case tracking-normal">{c}</Badge>)}
        </Row>
        <Row icon={ShieldCheck} label="What supports it:" tone="text-fact">
          <SourceLink url={it.url}>source record</SourceLink>
          {it.apply_url && <> · <SourceLink url={it.apply_url}>application page</SourceLink></>}
          <span className="text-muted"> · retrieved {day(it.retrieved_at)}</span>
        </Row>
        {!compact && it.excerpt && <blockquote className="quote ml-[26px]">“{it.excerpt}”</blockquote>}
        {!compact && (it.terms ?? []).map(([k, v]) => (
          <p key={k} className="ml-[26px] text-[13px] leading-relaxed text-ink2"><span className="font-semibold text-ink">{k}:</span> {v}</p>
        ))}
        {!compact && (
          <div className="flex gap-2.5 rounded-xl bg-brand/[0.07] px-3 py-2 text-[13px] leading-relaxed">
            <ArrowRightCircle size={15} className="mt-[3px] shrink-0 text-brand" />
            <div className="text-ink2"><span className="font-semibold text-ink">What to do next:</span> {it.next_action || "Open the source and check the details."}</div>
          </div>
        )}
        {it.uncertainty && (
          <Row icon={HelpCircle} label="Uncertain:" tone="text-muted"><span className="text-muted">{it.uncertainty}</span></Row>
        )}
        {(it.adjustments ?? []).map((a) => <p key={a} className="meta ml-[26px]">Ranking note: {a}</p>)}
      </div>

      {canMark !== undefined && !compact && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line/70 pt-3.5">
          {canMark ? (
            <>
              <button className={clsx("btn", marks.has("saved") && "btn-on")} onClick={() => toggle("saved")} aria-pressed={marks.has("saved")}>
                <Bookmark size={14} fill={marks.has("saved") ? "currentColor" : "none"} />{marks.has("saved") ? "Saved" : "Save"}
              </button>
              <button className={clsx("btn", marks.has("useful") && "btn-on")} onClick={() => toggle("useful")} aria-pressed={marks.has("useful")}>
                <ThumbsUp size={14} />{marks.has("useful") ? "Marked useful" : "Useful"}
              </button>
              <button className="btn" onClick={() => toggle("not_useful")} title="Hide this item and stop offering it">
                <ThumbsDown size={14} />Not useful
              </button>
            </>
          ) : (
            <span className="meta">Choose this company under “Acting as” to save or rate items.</span>
          )}
        </div>
      )}
    </article>
  );
}
