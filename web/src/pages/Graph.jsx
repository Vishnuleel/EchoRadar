import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ForceGraph2D from "react-force-graph-2d";
import { ArrowRight, Maximize2, MousePointerClick } from "lucide-react";
import { api } from "../api";
import { useSession } from "../store";
import { Badge, Chip, CompanyPicker, Empty, HypothesisNotice, PageHeader, QueryState, SourceLink } from "../components/ui";

const DASH = { solid: null, dot: [1.5, 3], dash: [6, 4] };
const SHAPE = { application: "diamond", funding: "square", testbed: "triangle", research: "hexagon" };
const endId = (end) => (typeof end === "object" ? end.id : end);

function drawShape(ctx, shape, x, y, r) {
  ctx.beginPath();
  if (shape === "diamond") { ctx.moveTo(x, y - r * 1.25); ctx.lineTo(x + r * 1.25, y); ctx.lineTo(x, y + r * 1.25); ctx.lineTo(x - r * 1.25, y); }
  else if (shape === "square") ctx.rect(x - r, y - r, r * 2, r * 2);
  else if (shape === "triangle") { ctx.moveTo(x, y - r * 1.2); ctx.lineTo(x + r * 1.15, y + r); ctx.lineTo(x - r * 1.15, y + r); }
  else if (shape === "hexagon") { for (let i = 0; i < 6; i += 1) { const a = (Math.PI / 3) * i; ctx.lineTo(x + r * 1.1 * Math.cos(a), y + r * 1.1 * Math.sin(a)); } }
  else ctx.arc(x, y, r, 0, 2 * Math.PI);
  ctx.closePath();
}

function useSize() {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 800, height: 620 });
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setSize({ width: Math.floor(e.contentRect.width), height: Math.floor(e.contentRect.height) }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, size];
}

function Canvas({ data, selected, picked, onSelect, styles }) {
  const { theme } = useSession();
  const fg = useRef(null);
  const [box, size] = useSize();
  const [hover, setHover] = useState(null);
  const graph = useMemo(() => ({ nodes: data.nodes.map((n) => ({ ...n })), links: data.links.map((l) => ({ ...l })) }), [data]);
  const neighbours = useMemo(() => {
    const m = new Map();
    data.links.forEach((l) => {
      m.set(l.source, (m.get(l.source) ?? new Set()).add(l.target));
      m.set(l.target, (m.get(l.target) ?? new Set()).add(l.source));
    });
    return m;
  }, [data]);
  const ink = useMemo(() => {
    const css = getComputedStyle(document.documentElement);
    const v = (n) => `rgb(${css.getPropertyValue(n).trim().split(" ").join(",")})`;
    return { text: v("--ink"), soft: v("--ink2"), bg: v("--bg") };
  }, [theme]);

  useEffect(() => {
    const g = fg.current;
    if (!g) return;
    g.d3Force("charge").strength(-420).distanceMax(520);
    g.d3Force("link").distance((l) => (l.type === "HAS_CAPABILITY" ? 58 : 120));
    g.d3ReheatSimulation();
  }, [graph]);

  const active = hover ?? picked; // dim the rest only for a node the user pointed at or clicked
  const lit = useCallback((id) => !active || id === active || neighbours.get(active)?.has(id), [active, neighbours]);
  const showCaps = data.nodes.length <= 45;

  const paint = useCallback((node, ctx, scale) => {
    const st = styles.node[node.type] ?? { color: "#888", size: 12 };
    const r = st.size / 2.6 + (node.focus ? 3 : 0);
    const on = lit(node.id);
    ctx.globalAlpha = on ? 1 : 0.28;
    if (node.id === selected) {
      ctx.beginPath(); ctx.arc(node.x, node.y, r + 5, 0, 2 * Math.PI);
      ctx.fillStyle = `${st.color}33`; ctx.fill();
      ctx.lineWidth = 1.2; ctx.strokeStyle = st.color; ctx.stroke();
    }
    drawShape(ctx, SHAPE[node.type], node.x, node.y, r);
    ctx.fillStyle = st.color; ctx.fill();
    ctx.lineWidth = 1.4; ctx.strokeStyle = ink.bg; ctx.stroke();
    const labelled = ["company", "application"].includes(node.type) || (node.type === "capability" && (showCaps || scale > 1.6)) || node.id === active;
    if (labelled) {
      const big = node.type !== "capability";
      const px = Math.max(big ? 11 : 9, (big ? 11.5 : 9.5) / Math.sqrt(scale)) / scale * Math.min(scale, 1.6);
      const cut = node.type === "company" ? 30 : 24;
      const label = node.label.length > cut ? `${node.label.slice(0, cut)}...` : node.label;
      ctx.font = `${big ? 600 : 500} ${px}px "Inter Variable", system-ui, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.lineWidth = 3 / scale; ctx.strokeStyle = ink.bg; ctx.strokeText(label, node.x, node.y + r + 3);
      ctx.fillStyle = big ? ink.text : ink.soft; ctx.fillText(label, node.x, node.y + r + 3);
    }
    ctx.globalAlpha = 1;
  }, [styles, selected, active, lit, ink, showCaps]);

  const linkOn = (l) => !active || endId(l.source) === active || endId(l.target) === active;

  return (
    <div ref={box} className="relative h-[620px] w-full overflow-hidden rounded-2xl">
      <ForceGraph2D
        ref={fg} graphData={graph} width={size.width} height={size.height} backgroundColor="rgba(0,0,0,0)"
        nodeRelSize={6} nodeCanvasObject={paint}
        nodePointerAreaPaint={(node, color, ctx) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(node.x, node.y, 11, 0, 2 * Math.PI); ctx.fill(); }}
        nodeLabel={(n) => `${n.type}: ${n.label}`}
        linkColor={(l) => (styles.edge[l.type]?.color ?? "#888") + (linkOn(l) ? "cc" : "30")}
        linkWidth={(l) => (styles.edge[l.type]?.status === "hypothesis" ? 1.8 : 1.1) + (active && linkOn(l) ? 0.8 : 0)}
        linkLineDash={(l) => DASH[styles.edge[l.type]?.dash] ?? null}
        linkLabel={(l) => `${l.type} (${l.status})`}
        onNodeClick={(n) => onSelect(n.id)} onNodeHover={(n) => setHover(n?.id ?? null)} onBackgroundClick={() => { setHover(null); onSelect(null); }}
        cooldownTicks={160} onEngineStop={() => fg.current?.zoomToFit(500, 56)}
      />
      <button type="button" className="btn absolute right-3 top-3 !px-2" onClick={() => fg.current?.zoomToFit(500, 56)} title="Fit to view"><Maximize2 size={14} /></button>
      <div className="meta pointer-events-none absolute bottom-3 left-3 flex items-center gap-1.5"><MousePointerClick size={13} />Click a node to inspect it · scroll to zoom · drag to move</div>
    </div>
  );
}


// Newsprint palette (the server's colours were chosen for the old dark theme). Shape and line style still carry the meaning.
const NODE_COLOURS = { company: "#152B4E", application: "#A4482D", capability: "#267365", funding: "#966616",
                       testbed: "#A03442", research: "#5C5496" };
const EDGE_COLOURS = { HAS_CAPABILITY: "#267365", SIMILAR_TO: "#8A8F98", COMPLEMENTS: "#152B4E", RELEVANT_TO: "#966616",
                       SUPPORTED_BY: "#5C5496", POTENTIAL_COLLABORATION: "#A4482D" };

/* The legend: every point in its real shape and colour, every line in its real style, in plain words. */
const POINTS = [
  ["company", "Member company", "a larger point is the company in focus"],
  ["capability", "Capability", "something a member can do"],
  ["application", "Proposed joint product", "what three members could build together"],
  ["funding", "Funding call", "Vinnova"],
  ["research", "Research", "OpenAlex"],
  ["testbed", "Test environment", "a place to test or pilot"],
];
const LINES = [
  ["HAS_CAPABILITY", "Has this capability", "quoted from a public source"],
  ["COMPLEMENTS", "Proposed partners", "different capabilities that fit together"],
  ["POTENTIAL_COLLABORATION", "Would take part in", "one role in the proposed product"],
  ["SUPPORTED_BY", "Backed by", "the research or call that fits the proposal best"],
  ["RELEVANT_TO", "Fits the focus company", "a top finding from its radar"],
  ["SIMILAR_TO", "Similar profiles", "alike, not necessarily complementary"],
];
const BASIS = { evidence: "fact", computed: "calculated", hypothesis: "proposal" };
const SVG_DASH = { solid: undefined, dot: "1.5 3", dash: "6 4" };

function LegendShape({ type, color }) {
  const c = 7, r = type === "capability" ? 3.6 : 4.6;
  const shape = SHAPE[type];
  let el;
  if (shape === "diamond") el = <polygon points={`${c},${c - r * 1.25} ${c + r * 1.25},${c} ${c},${c + r * 1.25} ${c - r * 1.25},${c}`} />;
  else if (shape === "square") el = <rect x={c - r} y={c - r} width={r * 2} height={r * 2} />;
  else if (shape === "triangle") el = <polygon points={`${c},${c - r * 1.2} ${c + r * 1.15},${c + r} ${c - r * 1.15},${c + r}`} />;
  else if (shape === "hexagon") el = <polygon points={Array.from({ length: 6 }, (_, i) => `${c + r * 1.1 * Math.cos((Math.PI / 3) * i)},${c + r * 1.1 * Math.sin((Math.PI / 3) * i)}`).join(" ")} />;
  else el = <circle cx={c} cy={c} r={r} />;
  return <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" className="shrink-0" style={{ fill: color }}>{el}</svg>;
}

function LegendLine({ style }) {
  const hyp = style.status === "hypothesis";
  return (
    <svg width="30" height="10" viewBox="0 0 30 10" aria-hidden="true" className="shrink-0">
      <line x1="1" y1="5" x2="29" y2="5" stroke={style.color} strokeWidth={hyp ? 2.2 : 1.6} strokeDasharray={SVG_DASH[style.dash]} strokeLinecap="round" />
    </svg>
  );
}

function Legend({ nodeStyles, edgeStyles, shown }) {
  return (
    <div className="grid gap-x-8 gap-y-4 border-t border-line px-4 py-3.5 md:grid-cols-2" aria-label="Legend">
      <div>
        <div className="kicker mb-2">Points</div>
        <ul className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
          {POINTS.map(([k, label, note]) => (
            <li key={k} className="flex items-start gap-2 text-[13px] leading-snug">
              <span className="mt-0.5"><LegendShape type={k} color={nodeStyles[k]?.color} /></span>
              <span><span className="text-ink">{label}</span><span className="block text-[11.5px] text-muted">{note}</span></span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="kicker mb-2">Lines <span className="normal-case tracking-normal text-muted">(solid: fact or calculated · dashed: proposal, nobody contacted)</span></div>
        <ul className="space-y-1.5">
          {LINES.map(([k, label, note]) => edgeStyles[k] && (
            <li key={k} className={`flex items-start gap-2 text-[13px] leading-snug ${shown.includes(k) ? "" : "opacity-40"}`}>
              <span className="mt-1"><LegendLine style={edgeStyles[k]} /></span>
              <span>
                <span className="text-ink">{label}</span>
                <span className="ml-1.5 rounded-sm border border-line px-1 text-[10.5px] uppercase tracking-wide text-muted">{BASIS[edgeStyles[k].status] ?? edgeStyles[k].status}</span>
                <span className="block text-[11.5px] text-muted">{note}{shown.includes(k) ? "" : " (hidden by the filter)"}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** On the desk the graph page shows a still figure; the live, draggable graph runs only when the page is open. */
function GraphPreview() {
  const nodes = [[150, 120, "Njord X"], [420, 90, "EmbeddedArt"], [650, 170, "Knowit"], [280, 300, "Lassen"], [560, 330, "Nexer"],
                 [860, 120, "C Marine"], [800, 330, "Baltic Offshore"]];
  const edges = [[0, 1, 0], [1, 2, 1], [0, 3, 0], [1, 3, 1], [2, 4, 1], [5, 0, 0], [6, 3, 1], [4, 6, 0]];
  return (
    <>
      <PageHeader eyebrow="Knowledge graph" title="Innovation Connection Graph"
                  subtitle="Solid lines are backed by a source or calculated from text. Dashed lines are generated hypotheses." />
      <figure>
        <svg viewBox="0 0 1000 420" className="w-full border-y border-line">
          {edges.map(([a, b, dashed], i) => (
            <line key={i} x1={nodes[a][0]} y1={nodes[a][1]} x2={nodes[b][0]} y2={nodes[b][1]} stroke={dashed ? "#A4482D" : "#267365"}
                  strokeWidth="2" strokeDasharray={dashed ? "8 6" : undefined} />
          ))}
          {nodes.map(([x, y, label]) => (
            <g key={label}>
              <circle cx={x} cy={y} r="13" fill="#152B4E" />
              <text x={x} y={y + 36} textAnchor="middle" fontFamily="Newsreader, Georgia, serif" fontSize="22" fill="#101F37">{label}</text>
            </g>
          ))}
        </svg>
        <figcaption className="meta mt-2 italic">Illustration. Open the page to explore the live graph built from the stored records.</figcaption>
      </figure>
    </>
  );
}

export default function Graph({ preview }) {
  return preview ? <GraphPreview /> : <GraphFull />;
}

function GraphFull() {
  const { companies, companyId, meta } = useSession();
  const nodeStyles = useMemo(() => Object.fromEntries(Object.entries(meta.node_styles).map(([k, v]) => [k, { ...v, color: NODE_COLOURS[k] ?? v.color }])), [meta]);
  const edgeStyles = useMemo(() => Object.fromEntries(Object.entries(meta.edge_styles).map(([k, v]) => [k, { ...v, color: EDGE_COLOURS[k] ?? v.color }])), [meta]);
  const allTypes = Object.keys(edgeStyles);
  const [focus, setFocus] = useState(companyId);
  const [types, setTypes] = useState(["HAS_CAPABILITY"]); // opens on the evidenced capabilities; the other lines are one click away
  const [selected, setSelected] = useState(null);
  const query = useQuery({ queryKey: ["graph", focus, [...types].sort().join(",")], queryFn: () => api.graph(focus, types), placeholderData: (prev) => prev });
  const styles = useMemo(() => ({ node: nodeStyles, edge: edgeStyles }), [meta]);
  const toggle = (t) => setTypes((ts) => (ts.includes(t) ? ts.filter((x) => x !== t) : [...ts, t]));

  const data = query.data;
  const nodeMap = useMemo(() => new Map((data?.nodes ?? []).map((n) => [n.id, n])), [data]);
  const current = nodeMap.get(selected) ?? nodeMap.get(`company:${focus}`) ?? data?.nodes[0];
  const relations = useMemo(() => {
    if (!data || !current) return [];
    return data.links.filter((l) => l.source === current.id || l.target === current.id)
      .map((l) => ({ ...l, other: nodeMap.get(l.source === current.id ? l.target : l.source) }))
      .sort((a, b) => (a.status !== "evidence") - (b.status !== "evidence") || a.type.localeCompare(b.type));
  }, [data, current, nodeMap]);
  const sorted = useMemo(() => [...(data?.nodes ?? [])].sort((a, b) => a.type.localeCompare(b.type) || a.label.localeCompare(b.label)), [data]);

  return (
    <>
      <PageHeader eyebrow="Knowledge graph" title="Innovation Connection Graph"
                  subtitle="Solid edges are backed by a source or calculated from text. Dashed edges are generated hypotheses." />
      <div className="card mb-4 grid gap-4 p-4 lg:grid-cols-[minmax(220px,300px)_1fr] lg:items-end">
        <CompanyPicker label="Focus company" companies={companies} value={focus} allowNone noneLabel="Whole ecosystem (strongest hypotheses)"
                       onChange={(id) => { setFocus(id); setSelected(null); }} />
        <div>
          <span className="label">Relationship types</span>
          <div className="flex flex-wrap gap-1.5">
            {allTypes.map((t) => (
              <Chip key={t} active={types.includes(t)} onClick={() => toggle(t)} color={edgeStyles[t].color}>
                {t.replace(/_/g, " ").toLowerCase()} <span className="text-muted">({edgeStyles[t].status})</span>
              </Chip>
            ))}
          </div>
        </div>
      </div>

      <QueryState query={query}>
        {(d) => (!d.nodes.length ? <Empty>Nothing to show for this selection.</Empty> : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
            <div className="card overflow-hidden">
              <Canvas data={d} selected={current?.id} picked={nodeMap.has(selected) ? selected : null} onSelect={setSelected} styles={styles} />
              <div className="border-t border-line px-4 py-2">
                <span className="meta tabular-nums">{d.nodes.length} points · {d.links.length} lines. Click a point to see its lines and why each one is there.</span>
              </div>
              <Legend nodeStyles={nodeStyles} edgeStyles={edgeStyles} shown={types} />
            </div>

            <div className="space-y-3">
              {current && (
                <div className="card p-4">
                  <label className="block">
                    <span className="label">Inspect node</span>
                    <select className="input" value={current.id} onChange={(e) => setSelected(e.target.value)}>
                      {sorted.map((n) => <option key={n.id} value={n.id}>{n.type}: {n.label}</option>)}
                    </select>
                  </label>
                  <div className="mt-3.5 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: nodeStyles[current.type]?.color }} />
                    <span className="eyebrow !text-muted">{current.type}</span>
                  </div>
                  <h3 className="mt-1 text-base font-semibold leading-snug">{current.label}</h3>
                  {current.detail && <p className="mt-1.5 text-[13px] leading-relaxed text-ink2">{current.detail}</p>}
                  <p className="mt-2 text-xs"><SourceLink url={current.url}>open source</SourceLink></p>
                  {current.type === "application" && current.key && (
                    <Link to={`/blueprint?key=${encodeURIComponent(current.key)}`} className="btn btn-primary mt-3">Open as Innovation Blueprint <ArrowRight size={14} /></Link>
                  )}
                </div>
              )}
              <div className="card p-4">
                <h3 className="mb-2.5 text-sm font-semibold">Connected relationships and their explanations</h3>
                {!relations.length && <p className="meta">No relationships with the current filter.</p>}
                <ul className="max-h-[420px] space-y-2.5 overflow-y-auto pr-1">
                  {relations.map((r, i) => (
                    <li key={i} className="rounded-xl border border-line bg-bg/40 p-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="h-0.5 w-5 rounded" style={{ background: edgeStyles[r.type]?.color }} />
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink2">{r.type.replace(/_/g, " ")}</span>
                        <Badge kind={r.status === "evidence" ? "FACT" : r.status === "hypothesis" ? "HYPOTHESIS" : r.status === "user" ? "USER" : "neutral"}>{r.status}</Badge>
                      </div>
                      <button type="button" className="mt-1.5 text-left text-sm font-medium text-ink hover:text-brand" onClick={() => setSelected(r.other?.id)}>{r.other?.label}</button>
                      {r.explanation && <p className="mt-1 text-[12.5px] leading-relaxed text-ink2">{r.explanation}</p>}
                      {r.url && <p className="mt-1 text-xs"><SourceLink url={r.url}>open</SourceLink></p>}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </QueryState>
      <div className="mt-5"><HypothesisNotice /></div>
    </>
  );
}
