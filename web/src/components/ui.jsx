import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { ArrowUpRight, Check, ChevronDown, ChevronsUpDown, Search } from "lucide-react";

export const day = (iso) => (iso ? String(iso).slice(0, 10) : "");
export const stamp = (iso) => (iso ? String(iso).slice(0, 16).replace("T", " ") : "");

/* ---- labels ---------------------------------------------------------------------------------- */
const TONES = {
  FACT: "border-fact/40 bg-fact/[0.08] text-fact",
  INFERENCE: "border-inf/40 bg-inf/[0.08] text-inf",
  USER: "border-user/40 bg-user/[0.08] text-user",
  HYPOTHESIS: "border-hyp/40 bg-hyp/[0.08] text-hyp",
  SOURCED: "border-brand/30 bg-brand/[0.06] text-brand",
  open: "border-fact/40 bg-fact/[0.08] text-fact",
  upcoming: "border-brand/30 bg-brand/[0.06] text-brand",
  recurring: "border-sea/40 bg-sea/[0.08] text-sea",
  neutral: "border-line bg-surface2/70 text-ink2",
};

export function Badge({ kind = "SOURCED", children, className }) {
  return (
    <span className={clsx("inline-flex items-center whitespace-nowrap rounded-full border px-2 py-px font-sans text-[10.5px] font-semibold uppercase tracking-[0.08em]",
                          TONES[kind] ?? TONES.neutral, className)}>
      {children ?? kind}
    </span>
  );
}

export function SourceLink({ url, children = "source", className }) {
  if (!url || !/^https?:\/\//.test(url)) return <span className="meta">no public source</span>;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={clsx("link", className)}>
      {children}<ArrowUpRight size={13} />
    </a>
  );
}

/**
 * Swedish source text shown in English. `en` comes from the API:
 *   undefined/null  - the text is not Swedish: shown as is
 *   {available}     - stored machine translation: English first, original one click away
 *   {!available}    - Swedish, not translated yet: the original, with an honest note
 * The original stays the evidence; the translation is only a reading aid.
 */
export function Translated({ original, en, className, max }) {
  const [showOriginal, setShowOriginal] = useState(false);
  const cut = (t) => (max && t && t.length > max ? `${t.slice(0, max)}...` : t);
  if (!en) return <span className={className}>{cut(original)}</span>;
  if (!en.available) {
    return (
      <span className={className}>
        {cut(original)}{" "}
        <span className="whitespace-nowrap font-sans text-[11.5px] font-normal not-italic text-muted" title="No English translation is stored for this text yet">(Swedish original; no translation yet)</span>
      </span>
    );
  }
  return (
    <span className={className}>
      {cut(showOriginal ? original : en.text)}{" "}
      <button type="button" onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowOriginal(!showOriginal); }}
              className="whitespace-nowrap align-baseline font-sans text-[11.5px] font-normal not-italic tracking-normal text-muted underline decoration-dotted underline-offset-2 hover:text-brand"
              title={showOriginal ? "Show the English machine translation" : `Machine translation (${en.engine}). Click to read the Swedish original.`}>
        {showOriginal ? "Swedish original · English" : "translated · original"}
      </button>
      {!showOriginal && en.numbers_ok === false && <span className="ml-1 font-sans text-[11.5px] font-normal text-hyp">check numbers in the original</span>}
    </span>
  );
}

/* ---- layout ---------------------------------------------------------------------------------- */
/** A newspaper section head: kicker, serif title, a heavy rule; the dek (subtitle) underneath. */
export function PageHeader({ eyebrow, title, subtitle, children }) {
  return (
    <header className="mb-7">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b-2 border-ink pb-3">
        <div className="min-w-0">
          <div className="kicker">{eyebrow}</div>
          <h1 className="mt-1 text-[34px] font-semibold leading-[1.05] sm:text-[42px]">{title}</h1>
        </div>
        {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
      </div>
      {subtitle && <p className="mt-2.5 max-w-3xl font-serif text-[17px] italic leading-snug text-ink2">{subtitle}</p>}
    </header>
  );
}

export function Card({ className, children, ...rest }) {
  return <div className={clsx("card card-pad", className)} {...rest}>{children}</div>;
}

export function SectionTitle({ children, hint, right }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3 border-b border-ink/70 pb-1.5">
      <div>
        <h2 className="text-[22px] font-semibold leading-tight">{children}</h2>
        {hint && <p className="meta mt-0.5">{hint}</p>}
      </div>
      {right}
    </div>
  );
}

/** A figure in the margin style: big serif number, small label. No icon tiles. */
export function Stat({ value, label, sub }) {
  return (
    <div className="border-l border-line pl-4 first:border-l-0 first:pl-0">
      <div className="font-serif text-[34px] font-semibold leading-none tabular-nums">{value ?? "n/a"}</div>
      <div className="mt-1.5 font-sans text-[13.5px] font-semibold text-ink2">{label}</div>
      {sub && <div className="meta mt-0.5 leading-snug">{sub}</div>}
    </div>
  );
}

/** A row of figures separated by hairlines. */
export function Stats({ children, className }) {
  return <div className={clsx("grid grid-cols-2 gap-y-5 border-y border-line py-4 sm:flex sm:gap-0 [&>*]:sm:flex-1", className)}>{children}</div>;
}

/** An editor's note: a coloured rule in the margin, no box, no icon. */
export function Notice({ tone = "hyp", children, className }) {
  const rule = { hyp: "border-hyp", sim: "border-inf", info: "border-brand/60", error: "border-pink", ok: "border-sea" }[tone];
  return (
    <div className={clsx("border-l-[3px] bg-surface2/40 py-2 pl-3.5 pr-3 font-sans text-[14px] leading-relaxed text-ink2", rule, className)}>
      {children}
    </div>
  );
}

export const HypothesisNotice = () => (
  <Notice>
    <b className="text-ink">Hypotheses, not agreements.</b> NEXUS generated these from public information; no company has
    been contacted, and funding eligibility has not been checked.
  </Notice>
);

export function Empty({ children }) {
  return (
    <div className="border-y border-line py-8 text-center font-serif text-[16px] italic text-ink2">
      {children}
    </div>
  );
}

export function Skeleton({ className }) {
  return <div className={clsx("skeleton", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Skeleton className="h-10 w-72" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div>
      <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-72" /><Skeleton className="h-72" /></div>
    </div>
  );
}

export function QueryState({ query, children }) {
  if (query.isPending) return <PageSkeleton />;
  if (query.isError) {
    return (
      <Notice tone="error">
        <b className="text-ink">Could not load this view.</b> {query.error.message}. Check that the API is running
        (<code>python -m api</code>) and try again.
        <button type="button" className="btn ml-2" onClick={() => query.refetch()}>Retry</button>
      </Notice>
    );
  }
  return children(query.data);
}

/* ---- controls -------------------------------------------------------------------------------- */
export function Tabs({ tabs, value, onChange }) {
  // one Tab stop for the whole tab list; arrow keys move between tabs (WAI-ARIA tabs pattern)
  const onKey = (e) => {
    const i = tabs.findIndex((t) => t.id === value);
    const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    const t = tabs[(next + tabs.length) % tabs.length];
    e.currentTarget.querySelector(`[data-tab="${t.id}"]`)?.focus(); // every tab button is already rendered
    onChange(t.id);
  };
  return (
    <div className="mb-5 flex gap-1 overflow-x-auto border-b border-line" role="tablist" onKeyDown={onKey}>
      {tabs.map((t) => (
        <button type="button" key={t.id} role="tab" data-tab={t.id} tabIndex={value === t.id ? 0 : -1}
                aria-selected={value === t.id} onClick={() => onChange(t.id)}
                className={clsx("-mb-px whitespace-nowrap border-b-2 px-3.5 py-2.5 font-sans text-[14.5px] font-semibold transition-colors",
                                value === t.id ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink2")}>
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 tabular-nums text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Segmented({ options, value, onChange }) {
  return (
    <div className="inline-flex rounded-md border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button type="button" key={o.value} onClick={() => onChange(o.value)} aria-pressed={value === o.value}
                className={clsx("rounded px-3 py-1.5 font-sans text-[14px] font-medium transition-colors",
                                value === o.value ? "bg-brand text-surface" : "text-ink2 hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Chip({ active, onClick, children, color }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
            className={clsx("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-sans text-[14px] font-medium transition-colors",
                            active ? "border-ink/60 bg-surface2 text-ink" : "border-line bg-transparent text-muted hover:border-ink/40 hover:text-ink2")}>
      {color && <span className="h-2 w-2 rounded-full" style={{ background: color, opacity: active ? 1 : 0.4 }} />}
      {children}
    </button>
  );
}

export function Disclosure({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-y border-line">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              className="flex w-full items-center justify-between gap-3 py-2.5 text-left font-sans text-[14.5px] font-semibold text-ink2 hover:text-ink">
        <span>{title}</span>
        <ChevronDown size={16} className={clsx("shrink-0 transition", open && "rotate-180")} />
      </button>
      {open && <div className="pb-4 pt-1">{children}</div>}
    </div>
  );
}

/** Searchable company selector. `allowNone` adds the public "Visitor" option. */
export function CompanyPicker({ companies, value, onChange, allowNone, noneLabel = "Visitor (public view)", label, max, className }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const box = useRef(null);
  const input = useRef(null);
  const trigger = useRef(null);
  const listRef = useRef(null);
  const [active, setActive] = useState(0);
  const uid = useId();
  const multi = Array.isArray(value);
  const selected = multi ? value : [value];

  const panel = useRef(null);
  const [pos, setPos] = useState(null);

  const close = (refocus = true) => { setOpen(false); setQ(""); if (refocus) trigger.current?.focus(); };
  useEffect(() => {
    if (!open) return undefined;
    const outside = (e) => { if (!box.current?.contains(e.target) && !panel.current?.contains(e.target)) close(false); };
    document.addEventListener("mousedown", outside);
    input.current?.focus();
    return () => document.removeEventListener("mousedown", outside);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // The list is drawn in a layer above the page (a portal), so a card that clips its content cannot cut it off.
  // It sits under the field, or above it when there is not enough room below.
  useLayoutEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const r = trigger.current?.getBoundingClientRect();
      if (!r) return;
      const below = window.innerHeight - r.bottom - 12, above = r.top - 12;
      const up = below < 260 && above > below;
      setPos({ left: Math.min(r.left, window.innerWidth - Math.max(r.width, 240) - 8), width: Math.max(r.width, 240),
               top: up ? undefined : r.bottom + 6, bottom: up ? window.innerHeight - r.top + 6 : undefined,
               maxList: Math.max(140, Math.min(320, (up ? above : below) - 90)) });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [open]);

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return companies.filter((c) => !needle || c.name.toLowerCase().includes(needle));
  }, [companies, q]);
  // the keyboard moves through exactly what is shown: the optional "none" entry, then the matches
  const ids = useMemo(() => [...(allowNone && !q ? [null] : []), ...list.map((c) => c.id)], [allowNone, q, list]);
  useEffect(() => { setActive(0); }, [q, open]);
  useEffect(() => { listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" }); }, [active]);

  const pick = (id) => {
    if (multi) {
      const next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
      if (!max || next.length <= max) onChange(next);
      setQ("");
    } else { onChange(id); close(); }
  };
  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(ids.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Home") { e.preventDefault(); setActive(0); }
    else if (e.key === "End") { e.preventDefault(); setActive(ids.length - 1); }
    else if (e.key === "Enter") { e.preventDefault(); if (ids.length) pick(ids[active]); }
    else if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Tab") close(false);
  };
  const nameOf = (id) => companies.find((c) => c.id === id)?.name;
  const text = multi ? (selected.length ? selected.map(nameOf).join(" + ") : "Choose companies")
                     : (value === null || value === undefined ? (allowNone ? noneLabel : "Choose a company") : nameOf(value) ?? "Choose a company");

  return (
    <div ref={box} className={clsx("relative", className)}>
      {label && <span className="label">{label}</span>}
      <button ref={trigger} type="button" onClick={() => (open ? close() : setOpen(true))} aria-haspopup="listbox" aria-expanded={open}
              aria-label={label ? `${label}: ${text}` : text}
              onKeyDown={(e) => { if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) { e.preventDefault(); setOpen(true); } }}
              className="input flex items-center justify-between gap-2 text-left">
        <span className="truncate">{text}</span>
        <ChevronsUpDown size={15} className="shrink-0 text-muted" />
      </button>
      {open && pos && createPortal(
        <div ref={panel} style={{ position: "fixed", left: pos.left, width: pos.width, top: pos.top, bottom: pos.bottom }}
             className="z-[60] animate-rise overflow-hidden rounded-xl border border-line bg-surface shadow-2xl">
          <div className="flex items-center gap-2 border-b border-line px-3">
            <Search size={14} className="text-muted" />
            <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type to search" onKeyDown={onKey}
                   role="combobox" aria-expanded="true" aria-controls={`${uid}-list`} aria-autocomplete="list"
                   aria-activedescendant={ids.length ? `${uid}-opt-${active}` : undefined} aria-label="Search companies"
                   className="w-full bg-transparent py-2.5 text-sm text-ink placeholder:text-muted focus:outline-none" />
          </div>
          <ul ref={listRef} id={`${uid}-list`} role="listbox" aria-multiselectable={multi || undefined}
              style={{ maxHeight: pos.maxList }} className="overflow-y-auto p-1">
            {ids.map((id, i) => (
              <Option key={id ?? "none"} id={`${uid}-opt-${i}`} index={i} highlighted={i === active}
                      active={id === null ? value === null : selected.includes(id)}
                      onHover={() => setActive(i)} onClick={() => pick(id)}>
                {id === null ? noneLabel : nameOf(id)}
              </Option>
            ))}
            {!ids.length && <li className="px-3 py-3 text-sm text-muted">No company matches.</li>}
          </ul>
          <p className="border-t border-line px-3 py-1.5 text-[11px] text-muted">↑ ↓ to move · Enter to choose · Esc to close</p>
        </div>,
        document.body,
      )}
    </div>
  );
}

function Option({ id, index, active, highlighted, onClick, onHover, children }) {
  return (
    <li id={id} role="option" aria-selected={active} data-index={index} onMouseMove={onHover}>
      <button type="button" tabIndex={-1} onClick={onClick}
              className={clsx("flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition",
                              active ? "bg-brand/15 text-ink" : "text-ink2",
                              highlighted && "outline outline-2 outline-brand/60 bg-surface2 text-ink")}>
        <span className="truncate">{children}</span>
        {active && <Check size={14} className="shrink-0 text-brand" />}
      </button>
    </li>
  );
}

/* ---- scores ---------------------------------------------------------------------------------- */
/** A 0-100 score as a plain figure with a small label (no gauge). The name is kept for existing call sites. */
export function Ring({ value, size = 52, label = "fit" }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const big = size >= 60;
  return (
    <div className="shrink-0 text-right" title={`${label} ${v.toFixed(0)} of 100`}>
      <div className={clsx("font-serif font-semibold leading-none tabular-nums", big ? "text-[40px]" : "text-[26px]",
                           v >= 70 ? "text-sea" : "text-ink")}>{v.toFixed(0)}</div>
      <div className="mt-0.5 font-sans text-[10.5px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</div>
    </div>
  );
}

export function Bar({ value, color = "rgb(var(--brand))", className }) {
  return (
    <div className={clsx("h-1.5 overflow-hidden bg-line/70", className)}>
      <div className="h-full" style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%`, background: color }} />
    </div>
  );
}

/** The four score components (S = 0.35 C + 0.25 O + 0.20 R + 0.20 E). */
export function ScoreBars({ breakdown, labels }) {
  return (
    <div className="space-y-2">
      {Object.entries(labels ?? {}).map(([key, label]) => {
        const v = breakdown?.[key];
        const w = breakdown?.weights?.[key] ?? 0;
        return (
          <div key={key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 font-sans text-[13.5px]">
            <span className="text-ink2">{label} <span className="text-muted">x{w.toFixed(2)}</span></span>
            <span className="tabular-nums text-ink">{v === null || v === undefined ? "n/a" : v.toFixed(0)}</span>
            <Bar value={v} className="col-span-2" />
          </div>
        );
      })}
    </div>
  );
}

/** A proposed connection, set like a short news item: label, serif headline, who, score in the margin. */
export function HypothesisCard({ h, children, compact }) {
  return (
    <article className={clsx("border-b border-line", compact ? "py-3" : "py-4")}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge kind="HYPOTHESIS" />
            <span className="meta">{h.kind === "triad" ? "three companies" : "two companies"}</span>
          </div>
          <h4 className={clsx("mt-1.5 font-semibold leading-snug", compact ? "text-[18px]" : "text-[20px]")}>{h.title}</h4>
          <p className="mt-0.5 font-sans text-[14px] text-ink2">
            {h.partners?.length && h.partners.length < h.companies.length ? `with ${h.partners.join(" and ")}` : h.companies.join(", ")}
          </p>
        </div>
        <Ring value={h.score} label="score" />
      </div>
      {children}
    </article>
  );
}

/** Minimal Markdown (headings, lists, bold, code) for the project's own docs. */
export function Markdown({ text }) {
  const inline = (s, k) => s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
    part.startsWith("**") ? <b key={`${k}-${i}`} className="text-ink">{part.slice(2, -2)}</b>
      : part.startsWith("`") ? <code key={`${k}-${i}`} className="rounded bg-surface2 px-1 text-[12px]">{part.slice(1, -1)}</code> : part);
  const blocks = [];
  let list = null;
  (text ?? "").split(/\r?\n/).forEach((line, i) => {
    const li = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    if (li) { (list ??= []).push(<li key={i}>{inline(li[1], i)}</li>); return; }
    if (list && /^\s{2,}\S/.test(line)) { list.push(<span key={i}> {inline(line.trim(), i)}</span>); return; }
    if (list) { blocks.push(<ul key={`l${i}`} className="ml-5 list-disc space-y-1">{list}</ul>); list = null; }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) blocks.push(<h4 key={i} className={clsx("font-semibold", h[1].length <= 2 ? "mt-4 text-base" : "mt-3 text-sm")}>{h[2]}</h4>);
    else if (line.trim()) blocks.push(<p key={i}>{inline(line, i)}</p>);
  });
  if (list) blocks.push(<ul key="l-end" className="ml-5 list-disc space-y-1">{list}</ul>);
  return <div className="space-y-2 font-serif text-[16px] leading-relaxed text-ink2">{blocks}</div>;
}
