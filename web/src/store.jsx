import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, setActingHeader } from "./api";

const read = (key, fallback) => {
  try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
};
const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } };

const Ctx = createContext(null);

// Set before the first request so the very first fetch already carries the header.
setActingHeader(read("nexus.acting", null));

export function SessionProvider({ children }) {
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const [acting, setActingState] = useState(() => read("nexus.acting", null));
  const [viewing, setViewingState] = useState(() => read("nexus.viewing", null));
  const [theme, setThemeState] = useState(() => document.documentElement.dataset.theme || "dark");

  const companies = meta.data?.companies ?? [];
  const names = useMemo(() => Object.fromEntries(companies.map((c) => [c.id, c.name])), [companies]);
  const known = (id) => id !== null && names[id] !== undefined;

  // A stored id can outlive the database it came from.
  useEffect(() => {
    if (!meta.data) return;
    if (acting !== null && !known(acting)) setActing(null);
    if (viewing !== null && !known(viewing)) setViewing(null);
  }, [meta.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const setActing = useCallback((id) => {
    setActingHeader(id);
    setActingState(id);
    write("nexus.acting", id);
    if (id !== null) { setViewingState(id); write("nexus.viewing", id); }
    qc.invalidateQueries(); // private fields depend on who is acting
  }, [qc]);
  const setViewing = useCallback((id) => { setViewingState(id); write("nexus.viewing", id); }, []);
  const setTheme = useCallback((t) => {
    document.documentElement.dataset.theme = t;
    setThemeState(t);
    try { localStorage.setItem("nexus.theme", t); } catch { /* ignore */ }
  }, []);

  // The company whose radar and profile are shown by default.
  const companyId = acting ?? (known(viewing) ? viewing : meta.data?.default_company ?? null);

  const value = { meta: meta.data, metaError: meta.error, loading: meta.isLoading, companies, names, acting, setActing,
                  companyId, setViewing, theme, setTheme };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);
