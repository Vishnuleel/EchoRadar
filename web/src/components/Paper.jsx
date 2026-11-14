import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { SECTIONS, SHEETS, SPREADS, parseLocation, spreadLabel, spreadOf, spreadPages, spreadPath } from "../sections";
import { useSession } from "../store";
import DownloadPaper from "./DownloadPaper";

/* Motion (see the motion-design guidance):
 *   page turn      - an on-screen object changing position: ease-in-out-cubic, illustrative length (rare action)
 *   lift to reader - entering: ease-out-quart; leaving is faster than entering
 *   hover focus    - subtle state: ease 150ms, applied to the OTHER page so the hovered one never moves under the cursor */
const FLIP_MS = 800;
const STAGGER_MS = 90;
const LIFT_MS = 420;
const DROP_MS = 180;
const EASE_IN_OUT = "cubic-bezier(.645,.045,.355,1)";
const EASE_OUT = "cubic-bezier(.165,.84,.44,1)";
const VIRTUAL_W = 1100; // pages are laid out at this width and scaled down onto the sheet
const RATIO = 1.414; // A-series paper: height / width

const longDate = () => new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

function useSize(ref) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

// an element under the pointer that scrolls sideways keeps horizontal wheel movement for itself
function scrollsSideways(el) {
  for (let n = el; n && n !== document.body; n = n.parentElement) {
    if (n.scrollWidth > n.clientWidth + 1 && ["auto", "scroll"].includes(getComputedStyle(n).overflowX)) return true;
  }
  return false;
}

/** A two-finger trackpad swipe: horizontal wheel movement, one action per gesture (inertia keeps sending events). */
function useWheelSwipe(onSwipe, threshold = 110) {
  const acc = useRef({ x: 0, t: 0, fired: false, firedAt: 0, low: Infinity });
  return useCallback((e) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY) || scrollsSideways(e.target)) return;
    const a = acc.current, now = Date.now(), mag = Math.abs(e.deltaX);
    // A new swipe starts after a pause, on a change of direction, or when the fingers push again while the
    // last swipe is still coasting (inertia only ever decays, so a sharp rise is a new push).
    const fresh = now - a.t > 160
      || (a.x !== 0 && Math.sign(e.deltaX) !== Math.sign(a.x))
      || (a.fired && now - a.firedAt > 220 && mag > Math.max(8, a.low * 2.5));
    if (fresh) { a.x = 0; a.fired = false; a.low = Infinity; }
    a.t = now;
    if (a.fired) { a.low = Math.min(a.low, mag); return; }
    a.x += e.deltaX;
    if (Math.abs(a.x) > threshold) { a.fired = true; a.firedAt = now; a.low = mag; onSwipe(a.x > 0 ? 1 : -1); }
  }, [onSwipe, threshold]);
}

function useMedia(query) {
  const [match, setMatch] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setMatch(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [query]);
  return match;
}

const interactive = (el) => !!el.closest?.("input, textarea, select, button, a, canvas, [role=slider], [role=listbox], [contenteditable]");

/** The running head printed at the top of every page. */
function RunningHead({ id }) {
  const s = SECTIONS[id];
  return (
    <div className="flex items-end justify-between border-b border-ink pb-1.5 font-sans text-[13px] text-ink2">
      <span className="font-serif text-[17px] font-bold text-ink">EchoRadar</span>
      <span className="uppercase tracking-[0.14em]">{s.kicker}</span>
      <span>{longDate()}{s.page ? ` · Page ${s.page}` : ""}</span>
    </div>
  );
}

/** One face of a sheet: a live, scaled-down copy of the real page. Click (or Enter) opens it to read. */
function Face({ id, back, pageW, pageH, live, visible, dim, lifted, shading, onOpen, onHover }) {
  const s = SECTIONS[id];
  const Comp = s.Comp;
  const scale = pageW / VIRTUAL_W;
  const touch = useMedia("(pointer: coarse)");
  return (
    <div className={clsx("page group paper-grain absolute inset-0 overflow-hidden transition-shadow duration-150 focus-visible:outline-none",
                         lifted ? "page-lifted" : "page-resting")}
         style={{ backfaceVisibility: "hidden", WebkitBackfaceVisibility: "hidden", transform: back ? "rotateY(180deg)" : undefined }}
         role="button" tabIndex={visible ? 0 : -1} aria-label={`Read page ${s.page}: ${s.title}`}
         onClick={(e) => onOpen(id, e.currentTarget.getBoundingClientRect())}
         onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(id, e.currentTarget.getBoundingClientRect()); } }}
         onMouseEnter={() => onHover(id)} onMouseLeave={() => onHover(null)}>
      <div inert="" aria-hidden="true" style={{ width: VIRTUAL_W, transform: `scale(${scale})`, transformOrigin: "top left", pointerEvents: "none" }}>
        <div className="px-14 pt-8">
          <RunningHead id={id} />
          <div className="pt-6">
            {live ? <Comp preview /> : (
              <div className="pt-24 text-center">
                <div className="kicker">{s.kicker}</div>
                <div className="mt-3 font-serif text-[64px] font-semibold leading-none">{s.title}</div>
              </div>
            )}
          </div>
        </div>
      </div>
      {/* the fold of the page: where the preview ends, the invitation to read on */}
      <div className="paper-grain absolute inset-x-0 bottom-0 flex items-center justify-between border-t border-ink/60 px-4 font-sans text-ink2"
           style={{ height: Math.max(26, pageH * 0.055), fontSize: Math.max(10.5, pageW * 0.022) }}>
        <span className="italic decoration-ink2/60 underline-offset-2 group-focus-visible:underline">Continued inside: {touch ? "tap" : "click"} to read</span>
        <span className="tabular-nums">{s.page}</span>
      </div>
      <div className={clsx("pointer-events-none absolute inset-0 bg-bg transition-opacity duration-150", dim ? "opacity-45" : "opacity-0")} />
      {shading && <div className="page-shade pointer-events-none absolute inset-0" style={{ animationDuration: `${FLIP_MS}ms` }} />}
    </div>
  );
}

/** The paper itself: sheets that turn around the spine. */
function Book({ spread, pageW, pageH, onOpen, bookRef }) {
  const prev = useRef(spread);
  const [turning, setTurning] = useState({ ids: [], forward: true });
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (prev.current === spread) return undefined;
    const forward = spread > prev.current;
    const lo = Math.min(prev.current, spread), hi = Math.max(prev.current, spread);
    const ids = Array.from({ length: hi - lo }, (_, j) => lo + j);
    prev.current = spread;
    // a turn started while another is still moving keeps both sheets on top until both have landed
    setTurning((t) => ({ ids: [...new Set([...t.ids, ...ids])].sort((a, b) => a - b), forward }));
    const t = setTimeout(() => setTurning({ ids: [], forward }), FLIP_MS + STAGGER_MS * ids.length + 60);
    return () => clearTimeout(t);
  }, [spread]);

  const [left, right] = spreadPages(spread);
  const near = (id) => Math.abs(spreadOf(id) - spread) <= 1 || turning.ids.length > 0;
  // closed paper (front or back page) lies centred; an open spread is centred on its spine
  const shift = spread === 0 ? -pageW / 2 : spread === SPREADS - 1 ? pageW / 2 : 0;
  const spreadOpen = left && right;

  return (
    <div ref={bookRef} className="relative" style={{ width: pageW * 2, height: pageH, perspective: 2800,
         transform: `translateX(${shift}px)`, transition: `transform ${FLIP_MS}ms ${EASE_IN_OUT}` }}>
      {spreadOpen && <div className="pointer-events-none absolute inset-y-0 left-1/2 z-[60] w-10 -translate-x-1/2 spine-shadow" />}
      {SHEETS.map(([front, back], i) => {
        const turned = i < spread;
        const isTurning = turning.ids.includes(i);
        const step = turning.forward ? i - turning.ids[0] : turning.ids[turning.ids.length - 1] - i;
        const z = isTurning ? 100 + step : turned ? 10 + i : 10 + (SHEETS.length - i);
        return (
          <div key={i} className="absolute top-0" style={{ left: pageW, width: pageW, height: pageH, zIndex: z,
               transformStyle: "preserve-3d", transformOrigin: "left center",
               transform: `rotateY(${turned ? -180 : 0}deg)`,
               transition: `transform ${FLIP_MS}ms ${EASE_IN_OUT} ${isTurning ? step * STAGGER_MS : 0}ms` }}>
            {[[front, false], [back, true]].map(([id, isBack]) => {
              const visible = id === left || id === right;
              return (
                <Face key={id} id={id} back={isBack} pageW={pageW} pageH={pageH} live={near(id)} visible={visible}
                      dim={spreadOpen && hover !== null && hover !== id && visible} lifted={hover === id}
                      shading={isTurning} onOpen={onOpen} onHover={setHover} />
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/** Reading a page: it lifts from where it lay into a full sheet. Esc, a sideways swipe or a click outside puts it back. */
function Reader({ id, origin, onClose }) {
  const { navOpen } = useSession();
  const sheet = useRef(null);
  const overlay = useRef(null);
  const closing = useRef(false);
  const s = SECTIONS[id];
  const Comp = s.Comp;

  useLayoutEffect(() => {
    const el = sheet.current;
    if (!el) return undefined;
    overlay.current.scrollTop = 0;
    const r = el.getBoundingClientRect();
    if (origin) { // start exactly where the page lay on the desk
      el.style.transformOrigin = "top left";
      el.style.transform = `translate(${origin.left - r.left}px, ${origin.top - r.top}px) scale(${origin.width / r.width})`;
    } else {
      el.style.transform = "translateY(14px) scale(0.97)";
      el.style.opacity = "0";
    }
    overlay.current.style.opacity = "0";
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      el.style.transition = `transform ${LIFT_MS}ms ${EASE_OUT}, opacity ${LIFT_MS * 0.6}ms ${EASE_OUT}`;
      el.style.transform = "none";
      el.style.opacity = "1";
      overlay.current.style.transition = `opacity ${LIFT_MS * 0.6}ms ease`;
      overlay.current.style.opacity = "1";
    };
    const raf = requestAnimationFrame(() => requestAnimationFrame(go));
    const t = setTimeout(go, 60); // background tabs pause animation frames
    return () => { cancelAnimationFrame(raf); clearTimeout(t); };
  }, [id, origin]);

  const close = useCallback(() => {
    if (closing.current) return;
    closing.current = true;
    const el = sheet.current;
    el.style.transition = `transform ${DROP_MS}ms ${EASE_OUT}, opacity ${DROP_MS}ms ${EASE_OUT}`;
    el.style.transformOrigin = "center top";
    el.style.transform = "translateY(10px) scale(0.97)";
    el.style.opacity = "0";
    overlay.current.style.transition = `opacity ${DROP_MS}ms ease`;
    overlay.current.style.opacity = "0";
    setTimeout(onClose, DROP_MS);
  }, [onClose]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && !e.target.closest?.("[role=listbox], [role=combobox]")) close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  // swipe left or right anywhere (except on controls) to put the page back
  const drag = useRef(null);
  const onPointerDown = (e) => { if (!interactive(e.target)) drag.current = { x: e.clientX, y: e.clientY, t: Date.now() }; };
  const onPointerUp = (e) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (Math.abs(dx) > 110 && Math.abs(dx) > Math.abs(dy) * 2 && Date.now() - d.t < 700 && !window.getSelection()?.toString()) close();
  };
  const onWheel = useWheelSwipe(close);

  return (
    <div ref={overlay} className={clsx("fixed inset-0 z-40 overflow-y-auto overflow-x-hidden bg-ink/30", navOpen && "lg:left-[264px]")}
         onClick={(e) => { if (e.target === overlay.current) close(); }}
         onPointerDown={onPointerDown} onPointerUp={onPointerUp} onWheel={onWheel}
         role="dialog" aria-modal="true" aria-label={`Page ${s.page ?? ""} ${s.title}`}>
      <article ref={sheet} className="paper-grain relative mx-auto my-6 w-[min(1180px,calc(100%-32px))] border border-line px-5 pb-12 pt-6 shadow-[0_30px_80px_-30px_rgb(16_31_55_/_0.55)] sm:my-10 sm:px-12">
        <button type="button" onClick={close} title="Back to the paper (Esc)" aria-label="Back to the paper"
                className="absolute right-3 top-3 rounded-md p-1.5 text-muted transition-colors hover:bg-surface2 hover:text-ink">
          <X size={18} />
        </button>
        <RunningHead id={id} />
        <div className="pt-7"><Comp /></div>
        <div className="mt-12 flex items-center justify-between border-t border-ink pt-2 font-sans text-[13px] text-muted">
          <button type="button" onClick={close} className="hover:text-ink hover:underline">Back to the paper</button>
          <span>{s.page ? `Page ${s.page}` : "About this paper"}</span>
        </div>
      </article>
    </div>
  );
}

/** The page index along the bottom of the desk. */
function Contents({ spread, go }) {
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center justify-center gap-x-1 gap-y-1 font-sans text-[13px]">
      {Array.from({ length: SPREADS }, (_, k) => {
        const titles = spreadPages(k).filter(Boolean).map((id) => SECTIONS[id].title).join(" · ");
        return (
          <button type="button" key={k} onClick={() => go(k)} title={titles} aria-current={k === spread ? "page" : undefined}
                  className={clsx("rounded px-2.5 py-1 transition-colors",
                                  k === spread ? "bg-ink text-surface" : "text-ink2 hover:bg-surface hover:text-ink")}>
            <span className="tabular-nums">{spreadLabel(k)}</span>
            <span className="ml-1.5 hidden xl:inline">{titles}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default function Paper() {
  const loc = useLocation();
  const nav = useNavigate();
  const { spread, open } = parseLocation(loc.pathname);
  const narrow = useMedia("(max-width: 1023px)");
  const desk = useRef(null);
  const bookRef = useRef(null);
  const size = useSize(desk);
  const origin = useRef(null);
  const [zone, setZone] = useState(null);
  const suppressClick = useRef(false);

  const go = useCallback((k) => { if (k >= 0 && k < SPREADS && k !== spread) nav(spreadPath(k)); }, [nav, spread]);
  const openPage = useCallback((id, rect) => {
    if (suppressClick.current) return;
    origin.current = rect;
    nav(SECTIONS[id].path + (id === "blueprint" ? loc.search : ""));
  }, [nav, loc.search]);
  const closeReader = useCallback(() => { origin.current = null; nav(spreadPath(spread)); }, [nav, spread]);

  // keys: arrows / page keys turn pages while no page is open
  useEffect(() => {
    if (open) return undefined;
    const onKey = (e) => {
      if (interactive(e.target) && e.target.tagName !== "BUTTON" && e.target.tagName !== "A") return;
      if (["ArrowRight", "PageDown"].includes(e.key)) { e.preventDefault(); go(spread + 1); }
      if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); go(spread - 1); }
      if (e.key === "Home") go(0);
      if (e.key === "End") go(SPREADS - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, spread, go]);

  // page size: two A-format pages side by side, leaving room for the turning margins and the contents strip
  const availH = Math.max(320, size.h - 120);
  const availW = Math.max(480, size.w - 190);
  const pageH = Math.min(availH, (availW / 2) * RATIO);
  const pageW = pageH / RATIO;

  // which part of the desk the pointer is over: the paper, or a margin that turns the page
  const zoneAt = (x) => {
    const r = bookRef.current?.getBoundingClientRect();
    if (!r) return null;
    const [l, rt] = spreadPages(spread);
    const left = l ? r.left : r.left + r.width / 2;
    const right = rt ? r.right : r.left + r.width / 2;
    if (x > right) return spread < SPREADS - 1 ? "next" : null;
    if (x < left) return spread > 0 ? "prev" : null;
    return "paper";
  };
  const drag = useRef(null);
  const onPointerDown = (e) => { drag.current = interactive(e.target) ? null : { x: e.clientX, y: e.clientY }; suppressClick.current = false; };
  const onPointerUp = (e) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5) { // swipe or drag the paper sideways to turn
      suppressClick.current = true;
      go(dx < 0 ? spread + 1 : spread - 1);
    }
  };
  const onWheel = useWheelSwipe(useCallback((dir) => go(spread + dir), [go, spread]));
  const onDeskClick = (e) => {
    if (suppressClick.current || interactive(e.target)) return;
    const z = zoneAt(e.clientX);
    if (z === "next") go(spread + 1);
    if (z === "prev") go(spread - 1);
  };

  const [left, right] = spreadPages(spread);

  return (
    <>
    <div className="desk relative flex h-full flex-col overflow-hidden" onPointerDown={onPointerDown} onPointerUp={onPointerUp} onWheel={onWheel}>
      <div ref={desk} className={clsx("relative min-h-0 flex-1 select-none", zone === "next" || zone === "prev" ? "cursor-pointer" : "")}
           onClick={onDeskClick} onMouseMove={(e) => setZone(narrow ? null : zoneAt(e.clientX))} onMouseLeave={() => setZone(null)}>
        {narrow ? (
          <div className="h-full overflow-y-auto px-4 py-5">
            <div className="mx-auto max-w-[520px] space-y-5">
              {[left, right].filter(Boolean).map((id) => {
                const w = Math.min(520, size.w - 32);
                return (
                  <div key={id} className="relative" style={{ width: w, height: w * RATIO * 0.62 }}>
                    <Face id={id} pageW={w} pageH={w * RATIO * 0.62} live visible onOpen={openPage} onHover={() => {}} />
                  </div>
                );
              })}
            </div>
          </div>
        ) : size.w > 0 && (
          <div className="absolute inset-0 flex items-center justify-center pb-4">
            <Book spread={spread} pageW={pageW} pageH={pageH} onOpen={openPage} bookRef={bookRef} />
          </div>
        )}

        {/* turning margins: a quiet hint on hover, and buttons for keyboard and touch users */}
        {!narrow && (
          <>
            <div className={clsx("pointer-events-none absolute right-6 top-1/2 -translate-y-1/2 font-serif text-[15px] italic text-ink2 transition-opacity duration-150",
                                 zone === "next" ? "opacity-100" : "opacity-0")}>Turn the page</div>
            <div className={clsx("pointer-events-none absolute left-6 top-1/2 -translate-y-1/2 font-serif text-[15px] italic text-ink2 transition-opacity duration-150",
                                 zone === "prev" ? "opacity-100" : "opacity-0")}>Turn back</div>
          </>
        )}
      </div>

      <div className="relative flex items-center justify-between gap-3 border-t border-line/70 px-4 py-2.5">
        <button type="button" onClick={() => go(spread - 1)} disabled={spread === 0} aria-label="Previous page"
                className="btn !px-2 disabled:opacity-30"><ChevronLeft size={16} /></button>
        <Contents spread={spread} go={go} />
        <span className="flex items-center gap-2">
          <DownloadPaper compact />
          <button type="button" onClick={() => go(spread + 1)} disabled={spread === SPREADS - 1} aria-label="Next page"
                className="btn !px-2 disabled:opacity-30"><ChevronRight size={16} /></button>
        </span>
      </div>
    </div>
    {/* outside the desk, so gestures while reading never turn the pages underneath */}
    {open && <Reader key={open} id={open} origin={origin.current} onClose={closeReader} />}
    </>
  );
}
