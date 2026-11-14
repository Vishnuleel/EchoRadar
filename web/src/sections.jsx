import { Suspense, lazy } from "react";
import { PageSkeleton } from "./components/ui";
import Home from "./pages/Home";
import Radar from "./pages/Radar";
import CompanyDNA from "./pages/CompanyDNA";
import Blueprint from "./pages/Blueprint";
import Ask from "./pages/Ask";
import Staff from "./pages/Staff";
import Overview from "./pages/Overview";
import Evaluation from "./pages/Evaluation";
import TaskTest from "./pages/TaskTest";

const GraphPage = lazy(() => import("./pages/Graph")); // the force-graph library is only loaded when needed
function Graph(props) {
  return <Suspense fallback={<PageSkeleton />}><GraphPage {...props} /></Suspense>;
}

/** The paper, page by page. `page` is the printed page number. */
export const SECTIONS = {
  front: { path: "/front", title: "Latest", kicker: "Front page", page: 1, Comp: Home },
  radar: { path: "/radar", title: "Opportunity Radar", kicker: "Opportunities", page: 2, Comp: Radar },
  dna: { path: "/dna", title: "Company profile", kicker: "Profile", page: 3, Comp: CompanyDNA },
  blueprint: { path: "/blueprint", title: "Innovation Blueprint", kicker: "Briefs", page: 4, Comp: Blueprint },
  ask: { path: "/ask", title: "Ask EchoRadar", kicker: "Inquiries", page: 5, Comp: Ask },
  graph: { path: "/graph", title: "Connections graph", kicker: "Connections", page: 6, Comp: Graph },
  staff: { path: "/staff", title: "Staff desk", kicker: "Blue Science Park", page: 7, Comp: Staff },
  overview: { path: "/overview", title: "Overview", kicker: "Back page", page: 8, Comp: Overview },
  evaluation: { path: "/evaluation", title: "Method and evaluation", kicker: "About this paper", page: null, Comp: Evaluation },
  study: { path: "/study", title: "Task test", kicker: "For testers", page: null, Comp: TaskTest },
};
export const ORDER = ["front", "radar", "dna", "blueprint", "ask", "graph", "staff", "overview"];

/** Four sheets: [front face, back face]. Turning sheet i reveals spread i + 1. */
export const SHEETS = [["front", "radar"], ["dna", "blueprint"], ["ask", "graph"], ["staff", "overview"]];
export const SPREADS = SHEETS.length + 1; // 0 = front page (closed), 1..3 = two-page spreads, 4 = back page (closed)

/** The pages visible at spread k: [left, right] (null where the desk shows). */
export const spreadPages = (k) => [k > 0 ? SHEETS[k - 1][1] : null, k < SHEETS.length ? SHEETS[k][0] : null];

/** The spread on which a section lies. */
export function spreadOf(id) {
  if (id === "evaluation" || id === "study") return SHEETS.length;
  for (let k = 0; k < SPREADS; k++) if (spreadPages(k).includes(id)) return k;
  return 0;
}

export const spreadLabel = (k) => spreadPages(k).filter(Boolean).map((id) => SECTIONS[id].page).join("–");

/** Where the address bar puts us: which spread is on the desk and which section (if any) is open to read. */
export function parseLocation(pathname) {
  const m = pathname.match(/^\/p\/(\d)$/);
  if (m) return { spread: Math.min(SPREADS - 1, Number(m[1])), open: null };
  const id = Object.keys(SECTIONS).find((k) => SECTIONS[k].path === pathname);
  if (id) return { spread: spreadOf(id), open: id };
  return { spread: 0, open: null };
}
export const spreadPath = (k) => (k === 0 ? "/" : `/p/${k}`);
