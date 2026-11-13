import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { FileText, Fingerprint, Home, LayoutDashboard, Menu, Moon, Radar, Share2, Sun, Users, X } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import { Badge, CompanyPicker, Notice, PageSkeleton } from "./ui";

const NAV = [
  { title: "Your company", items: [
    { to: "/", label: "Home", icon: Home, end: true },
    { to: "/radar", label: "Opportunity Radar", icon: Radar },
    { to: "/dna", label: "Company DNA", icon: Fingerprint },
    { to: "/blueprint", label: "Innovation Blueprint", icon: FileText },
  ] },
  { title: "Ecosystem", items: [
    { to: "/overview", label: "Innovation Overview", icon: LayoutDashboard },
    { to: "/graph", label: "Innovation Graph", icon: Share2 },
    { to: "/staff", label: "Staff View", icon: Users },
  ] },
];

function Sidebar({ onNavigate }) {
  const { companies, acting, setActing, theme, setTheme } = useSession();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30000, retry: false });
  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-4 py-5">
      <div className="px-2">
        <div className="font-display text-[22px] font-semibold leading-none tracking-[0.18em]">NEXUS</div>
        <div className="meta mt-1.5 leading-tight">The Innovation Connection Engine</div>
      </div>

      <nav className="space-y-4" aria-label="Pages">
        {NAV.map((group) => (
          <div key={group.title}>
            <div className="mb-1 px-2 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">{group.title}</div>
            {group.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} onClick={onNavigate}
                       className={({ isActive }) => clsx(
                         "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium transition",
                         isActive ? "bg-brand/15 text-ink" : "text-ink2 hover:bg-surface2 hover:text-ink")}>
                {({ isActive }) => (
                  <>
                    {isActive && <span className="absolute -left-4 top-1.5 h-6 w-1 rounded-r bg-brand" />}
                    <Icon size={17} className={isActive ? "text-brand" : "text-muted group-hover:text-ink2"} />
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="mt-auto space-y-3">
        <div className="rounded-xl border border-line bg-bg/40 p-3">
          <CompanyPicker label="Acting as (simulated sign-in)" companies={companies} value={acting} onChange={setActing} allowNone />
          <p className="mt-2 text-[11.5px] leading-snug text-muted">
            <span className="font-semibold text-inf">SIMULATED:</span> sign-in is a selector in this prototype. The
            authorisation checks behind it are real.
          </p>
        </div>
        <div className="px-1">
          <div className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">Labels used everywhere</div>
          <ul className="space-y-1 text-[12px] text-ink2">
            <li><Badge kind="FACT" /> public source</li>
            <li><Badge kind="INFERENCE" /> derived by NEXUS</li>
            <li><Badge kind="USER" /> entered by a user</li>
            <li><Badge kind="HYPOTHESIS" /> generated proposal</li>
          </ul>
        </div>
        <NavLink to="/evaluation" onClick={onNavigate}
                 className={({ isActive }) => clsx("block px-1 text-[12px] underline-offset-2 hover:underline", isActive ? "text-brand" : "text-muted hover:text-ink2")}>
          Method and evaluation
        </NavLink>
        <div className="flex items-center justify-between border-t border-line px-1 pt-3">
          <span className="flex items-center gap-2 text-[11.5px] text-muted" title={health.data?.embedding_backend}>
            <span className={clsx("h-2 w-2 rounded-full", health.isError ? "bg-pink" : health.data ? "bg-fact" : "bg-muted")} />
            {health.isError ? "API offline" : health.data ? (health.data.semantic ? "Engine ready" : "Engine ready (fallback embeddings)") : "Connecting"}
          </span>
          <button className="btn !px-2" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                  aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Shell() {
  const { loading, metaError, companies } = useSession();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);

  return (
    <div className="min-h-screen lg:pl-[272px]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[272px] border-r border-line bg-surface/70 backdrop-blur-xl lg:block">
        <Sidebar />
      </aside>

      {/* small screens: top bar and drawer */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg/85 px-4 py-2.5 backdrop-blur lg:hidden">
        <span className="font-display text-lg font-semibold tracking-[0.18em]">NEXUS</span>
        <button className="btn !px-2" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-[290px] max-w-[88vw] border-r border-line bg-surface">
            <button className="btn absolute right-3 top-4 z-10 !px-2" onClick={() => setOpen(false)} aria-label="Close menu"><X size={16} /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <main className="mx-auto w-full max-w-[1320px] px-4 py-6 sm:px-8 sm:py-9">
        {loading ? <PageSkeleton />
          : metaError ? (
            <Notice tone="error">
              <b className="text-ink">The NEXUS API is not reachable.</b> Start it with <code>python -m api</code> in the
              project folder, then reload. ({metaError.message})
            </Notice>
          ) : !companies.length ? (
            <Notice tone="sim">The database is empty. Run <code>python scripts/ingest.py</code> to retrieve public data first.</Notice>
          ) : <Outlet />}
      </main>
    </div>
  );
}
