import clsx from "clsx";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Bookmark, ChevronDown, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../api";
import { Badge, Ring, SourceLink, Translated, day } from "./ui";

export const KIND = {
  funding: { color: "rgb(var(--inf))", label: "Funding" },
  testbed: { color: "rgb(var(--hyp))", label: "Testing" },
  event: { color: "rgb(var(--user))", label: "Event" },
  research: { color: "rgb(var(--brand))", label: "Research" },
  news: { color: "rgb(var(--sea))", label: "News" },
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

/** One finding, set as a short brief. Headline, one line of reason and the source line are always shown;
 * "Read more" opens the evidence, the terms, the next step, what is uncertain and the actions. */
export default function ItemCard({ item: it, canMark, compact, lead }) {
  const [open, setOpen] = useState(false);
  const mark = useMark();
  const marks = new Set(it.marks ?? []);
  const toggle = (action) => mark.mutate({ kind: it.kind, ref_id: it.ref_id, action, on: !marks.has(action) });
  const flag = (it.flags ?? [])[0];

  return (
    <article className={clsx("border-b border-line", lead ? "pb-5" : compact ? "py-3" : "py-4")}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge kind="neutral">{KIND[it.kind]?.label ?? it.area}</Badge>
            {it.status && ["open", "upcoming", "recurring"].includes(it.status) && <Badge kind={it.status}>{it.status}</Badge>}
            {flag && <Badge kind="HYPOTHESIS">{flag}</Badge>}
            {it.priority_area && <Badge kind="USER">your priority</Badge>}
            {marks.has("saved") && <Badge kind="SOURCED">saved</Badge>}
          </div>
          <h3 className={clsx("mt-1.5 font-semibold leading-[1.15]",
                              lead ? "text-[30px] sm:text-[34px]" : compact ? "text-[17px]" : "text-[21px]")}>
            <Translated original={it.title} en={it.title_en} max={lead ? 180 : 140} />
          </h3>
          {it.why && (
            <p className={clsx("mt-1.5 font-serif leading-snug text-ink2", lead ? "text-[18px]" : "text-[15.5px]",
                               !open && !lead && "line-clamp-2")}>
              {it.why}
            </p>
          )}
          <p className="meta mt-1.5">{it.source} · {it.date_label}</p>
          {lead && !open && (
            <>
              {it.excerpt && (
                <p className="mt-4 font-serif text-[17px] leading-relaxed text-ink first-letter:float-left first-letter:mr-2 first-letter:font-serif first-letter:text-[52px] first-letter:font-semibold first-letter:leading-[0.85]">
                  <Translated original={it.excerpt} en={it.excerpt_en} />
                </p>
              )}
              <p className="mt-3 font-sans text-[15px] text-ink2">
                <span className="font-semibold text-ink">Next step:</span> {it.next_action || "Open the source and check the details."}
              </p>
            </>
          )}
        </div>
        {it.relevance != null && <Ring value={it.relevance} size={lead ? 64 : 52} />}
      </div>

      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              className="mt-2 inline-flex items-center gap-1 font-sans text-[13.5px] font-semibold text-brand hover:underline">
        {open ? "Less" : "Read more"} <ChevronDown size={14} className={clsx("transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="mt-3 space-y-3 border-l-2 border-line pl-4">
          {it.excerpt && (
            <blockquote className="quote !my-0"><Translated original={it.excerpt} en={it.excerpt_en} /></blockquote>
          )}
          {(it.terms ?? []).map(([k, v], i) => (
            <p key={k} className="font-sans text-[14px] leading-relaxed text-ink2">
              <span className="font-semibold text-ink">{k}:</span> <Translated original={v} en={it.terms_en?.[i]} />
            </p>
          ))}
          {(it.matched ?? []).length > 0 && (
            <p className="font-sans text-[14px] text-ink2"><span className="font-semibold text-ink">Matches your profile on:</span> {it.matched.join(", ")}</p>
          )}
          <p className="font-sans text-[14px] text-ink2">
            <span className="font-semibold text-ink">Source:</span> <SourceLink url={it.url}>source record</SourceLink>
            {it.apply_url && <> · <SourceLink url={it.apply_url}>application page</SourceLink></>}
            <span className="text-muted"> · retrieved {day(it.retrieved_at)}</span>
          </p>
          {!compact && (
            <p className="font-sans text-[14px] text-ink2">
              <span className="font-semibold text-ink">Next step:</span> {it.next_action || "Open the source and check the details."}
            </p>
          )}
          {it.uncertainty && <p className="font-sans text-[14px] text-muted"><span className="font-semibold">Uncertain:</span> {it.uncertainty}</p>}
          {(it.adjustments ?? []).map((a) => <p key={a} className="meta">Ranking note: {a}</p>)}
          {canMark !== undefined && !compact && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {canMark ? (
                <>
                  <button type="button" className={clsx("btn", marks.has("saved") && "btn-on")} onClick={() => toggle("saved")} aria-pressed={marks.has("saved")}>
                    <Bookmark size={14} fill={marks.has("saved") ? "currentColor" : "none"} />{marks.has("saved") ? "Saved" : "Save"}
                  </button>
                  <button type="button" className={clsx("btn", marks.has("useful") && "btn-on")} onClick={() => toggle("useful")} aria-pressed={marks.has("useful")}>
                    <ThumbsUp size={14} />{marks.has("useful") ? "Marked useful" : "Useful"}
                  </button>
                  <button type="button" className="btn" onClick={() => toggle("not_useful")} title="Hide this item and stop offering it">
                    <ThumbsDown size={14} />Not useful
                  </button>
                </>
              ) : (
                <span className="meta">Choose this company under "Reading as" to save or rate items.</span>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
