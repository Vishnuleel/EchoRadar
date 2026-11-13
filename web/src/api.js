// Thin fetch wrapper. The "acting as" company (simulated sign-in) travels in a header;
// the server decides what that company may see or change.
let acting = null;
export const setActingHeader = (id) => { acting = id; };

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(acting ? { "X-Acting-Company": String(acting) } : {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const body = await res.json(); detail = typeof body.detail === "string" ? body.detail : detail; } catch { /* not JSON */ }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== "") p.set(k, v); });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request("/health"),
  meta: () => request("/meta"),
  home: (companyId) => request(`/home${qs({ company_id: companyId })}`),
  ask: (text, previous) => request("/assistant", { method: "POST", body: JSON.stringify({ text, previous_in_scope: previous }) }),
  overview: () => request("/overview"),
  dna: (companyId) => request(`/companies/${companyId}/dna`),
  refine: (companyId, body) => request(`/companies/${companyId}/refine`, { method: "POST", body: JSON.stringify(body) }),
  graph: (focus, edgeTypes) => request(`/graph${qs({ focus, edge_types: edgeTypes.join(",") })}`),
  radar: (companyId) => request(`/radar${qs({ company_id: companyId })}`),
  mark: (body) => request("/radar/mark", { method: "POST", body: JSON.stringify(body) }),
  blueprintRecs: (companyId) => request(`/blueprint/recommendations${qs({ company_id: companyId })}`),
  blueprint: (params) => request(`/blueprint${qs(params)}`),
  blueprintUrl: (params) => `/api/blueprint${qs(params)}`,
  rate: (body) => request("/blueprint/feedback", { method: "POST", body: JSON.stringify(body) }),
  evaluation: () => request("/evaluation"),
  staff: () => request("/staff"),
  directory: () => request("/directory"),
};
