import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { api } from "../api";
import { ORDER, SECTIONS } from "../sections";
import { useSession } from "../store";
import { Badge, CompanyPicker, Notice, PageSkeleton } from "./ui";

// the table of contents, in the order of the paper
const NAV = [{ title: "In this issue", items: ORDER.map((id) => ({ to: SECTIONS[id].path, label: SECTIONS[id].title, page: SECTIONS[id].page })) }];

function Masthead({ onToggle, closeIcon: CloseIcon = PanelLeftClose, closeLabel = "Hide sidebar (Ctrl+B)" }) {
  return (
    <div className="flex items-start justify-between gap-2 border-b-2 border-ink pb-3">
      <div>
        <div className="font-serif text-[28px] font-bold leading-none tracking-tight">EchoRadar</div>
        <div className="kicker mt-1.5">Blue Science Park</div>
      </div>
      <button type="button" onClick={onToggle} title={closeLabel} aria-label={closeLabel}
              className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface2 hover:text-ink">
        <CloseIcon size={18} />
      </button>
    </div>
  );
}

function Sidebar({ onNavigate, onToggle, drawer }) {
  const { companies, acting, setActing, theme, setTheme } = useSession();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30000, retry: false });
  const qc = useQueryClient();
  const ranked = useRef(undefined);
  // new information from the sources: the server re-ranked, so every page fetches its data again
  useEffect(() => {
    const at = health.data?.ranked_at;
    if (at === undefined) return;
    if (ranked.current !== undefined && ranked.current !== at) {
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "health" });
    }
    ranked.current = at;
  }, [health.data?.ranked_at, qc]);
  const auto = health.data?.auto_monitor;
  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-5 py-5">
      <Masthead onToggle={onToggle} closeIcon={drawer ? X : PanelLeftClose} closeLabel={drawer ? "Close menu" : "Hide sidebar (Ctrl+B)"} />

      <nav className="space-y-5" aria-label="Sections">
        <NavLink to="/" end onClick={onNavigate}
                 className={({ isActive }) => clsx("block font-sans text-[14px] font-semibold underline-offset-4 hover:underline",
                                                  isActive ? "text-ink" : "text-brand")}>
          Browse the paper
        </NavLink>
        {NAV.map((group) => (
          <div key={group.title}>
            <div className="kicker mb-1.5">{group.title}</div>
            {group.items.map(({ to, label, page }) => (
              <NavLink key={to} to={to} onClick={onNavigate}
                       className={({ isActive }) => clsx(
                         "flex items-baseline justify-between border-l-2 py-1.5 pl-3 font-serif text-[17px] leading-snug transition-colors",
                         isActive ? "border-ink font-semibold text-ink" : "border-transparent text-ink2 hover:border-line hover:text-ink")}>
                <span>{label}</span>
                <span className="font-sans text-[12px] tabular-nums text-muted">{page}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="mt-auto space-y-4">
        <div>
          <CompanyPicker label="Reading as" companies={companies} value={acting} onChange={setActing} allowNone />
          <p className="meta mt-1.5 leading-snug">Simulated sign-in: a selector, not authentication.</p>
        </div>
        <div className="rule-thin pt-3">
          <div className="kicker mb-2">Labels</div>
          <ul className="grid grid-cols-2 gap-x-2 gap-y-1.5 font-sans text-[12.5px] text-ink2">
            <li><Badge kind="FACT" /> <span className="sr-only">public source</span></li>
            <li><Badge kind="INFERENCE" /></li>
            <li><Badge kind="USER" /></li>
            <li><Badge kind="HYPOTHESIS" /></li>
          </ul>
          <p className="meta mt-1.5 leading-snug">Fact: public source. Inference: derived by EchoRadar. User: entered by the company. Hypothesis: a proposal.</p>
        </div>
        <div className="rule-thin space-y-1.5 pt-3 font-sans text-[12.5px] text-muted">
          <div className="flex items-center gap-2"
               title={health.data ? (health.data.semantic ? `Embeddings: ${health.data.embedding_backend}`
                 : `Fallback embeddings (${health.data.embedding_backend}): ${health.data.fallback_reason ?? "the multilingual model is not loaded"}. Matching quality is lower.`) : undefined}>
            <span className={clsx("h-1.5 w-1.5 shrink-0 rounded-full", health.isError ? "bg-pink" : !health.data ? "bg-muted" : health.data.semantic ? "bg-sea" : "bg-inf")} />
            {health.isError ? "API offline" : health.data ? (health.data.semantic ? "Engine ready" : "Fallback embeddings in use") : "Connecting"}
          </div>
          {health.data && (
            <div title="All findings come from stored copies of public sources; each item shows its own retrieval date.">
              Sources checked {(health.data.sources_checked_at ?? health.data.ranked_at ?? "").slice(0, 16).replace("T", " ") || "unknown"} UTC
              {health.data.offline && " (offline: stored copies only)"}
            </div>
          )}
          {auto?.enabled && (
            <div title="While the site runs, every source is re-checked on its own schedule; new or changed records appear without a restart.">
              Updates automatically{auto.running ? ": checking now" : ` · next check ${String(auto.next_cycle_at ?? "").slice(11, 16)} UTC`}
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pt-1">
            <span className="flex gap-3 whitespace-nowrap">
              <NavLink to="/evaluation" onClick={onNavigate}
                       className={({ isActive }) => clsx("underline-offset-2 hover:underline", isActive ? "text-ink" : "hover:text-ink2")}>
                Method and evaluation
              </NavLink>
              <NavLink to="/study" onClick={onNavigate}
                       className={({ isActive }) => clsx("underline-offset-2 hover:underline", isActive ? "text-ink" : "hover:text-ink2")}>
                Task test
              </NavLink>
            </span>
            <button type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                    className="underline-offset-2 hover:text-ink2 hover:underline">
              {theme === "dark" ? "Day edition" : "Night edition"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Shell() {
  const { loading, metaError, companies, navOpen, setNavOpen } = useSession();
  const [drawer, setDrawer] = useState(false);
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b" && !e.target.closest?.("input, textarea")) {
        e.preventDefault();
        setNavOpen(!navOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen, setNavOpen]);

  return (
    <div className={clsx("min-h-screen transition-[padding] duration-200", navOpen && "lg:pl-[264px]")}>
      <a href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}
         className="fixed left-3 top-3 z-50 -translate-y-20 rounded-md bg-brand px-4 py-2 font-sans text-sm font-semibold text-surface transition focus:translate-y-0">
        Skip to content
      </a>

      {/* wide screens: a sidebar that can be hidden and reopened */}
      <aside className={clsx("fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-line bg-surface transition-transform duration-200 lg:block",
                             navOpen ? "translate-x-0" : "-translate-x-full")}
             aria-hidden={!navOpen} inert={navOpen ? undefined : ""}>
        <Sidebar onToggle={() => setNavOpen(false)} />
      </aside>
      {!navOpen && (
        <button type="button" onClick={() => setNavOpen(true)} title="Show sidebar (Ctrl+B)" aria-label="Show sidebar (Ctrl+B)"
                className="fixed left-3 top-3 z-30 hidden rounded-md border border-line bg-surface p-1.5 text-ink2 transition-colors hover:text-ink lg:block">
          <PanelLeftOpen size={18} />
        </button>
      )}

      {/* small screens: top bar and drawer */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b-2 border-ink bg-bg px-4 py-2.5 lg:hidden">
        <span className="font-serif text-xl font-bold">EchoRadar</span>
        <button type="button" className="rounded-md p-1.5 text-ink2" onClick={() => setDrawer(true)} aria-label="Open menu"><PanelLeftOpen size={20} /></button>
      </div>
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-[290px] max-w-[88vw] border-r border-line bg-surface">
            <Sidebar drawer onToggle={() => setDrawer(false)} onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}

      {/* the desk fills the window; pages scroll inside the reader, never the window */}
      <main id="main" tabIndex={-1} className="relative h-[calc(100dvh-50px)] focus:outline-none lg:h-[100dvh]">
        {loading || metaError || !companies.length ? (
          <div className="mx-auto max-w-[900px] px-6 py-10">
            {loading ? <PageSkeleton />
              : metaError ? (
                <Notice tone="error">
                  <b className="text-ink">The EchoRadar API is not reachable.</b> Start it with <code>python -m api</code> in the
                  project folder, then reload. ({metaError.message})
                </Notice>
              ) : <Notice tone="sim">The database is empty. Run <code>python scripts/ingest.py</code> to retrieve public data first.</Notice>}
          </div>
        ) : <Outlet />}
      </main>
    </div>
  );
}
