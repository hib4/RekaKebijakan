import { useEffect, useRef, useState } from "react";
import { drag } from "d3-drag";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";
import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import { select } from "d3-selection";
import { zoom, zoomIdentity } from "d3-zoom";
import { graphColors } from "./workflowData";
import type { ConsoleLog, DemoCase, PolicyGraphNode, ViewMode, WorkflowStep, WorkflowTask } from "./workflowTypes";
import type { StepRunStatus, WorkflowSession } from "./workflowSession";
import { workflowStatus } from "./workflowSession";

const stepNames: Record<WorkflowStep, string> = { 1: "Graph Build", 2: "Env Setup", 3: "Simulation", 4: "Report", 5: "Interaction" };

function navigate(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function WorkflowTopBar({ session, onStep, onViewMode }: { session: WorkflowSession; onStep: (step: WorkflowStep) => void; onViewMode: (mode: ViewMode) => void }) {
  const status = workflowStatus(session);
  return <>
    <header className="workflow-topbar">
      <div className="workflow-brand"><button className="workflow-back" onClick={() => navigate("/projects")} aria-label="Kembali ke proyek kebijakan">←</button><button className="workflow-wordmark" onClick={() => navigate("/projects")}>RekaKebijakan</button></div>
      <div className="view-modes" aria-label="Mode tampilan">{(["graph", "split", "workbench"] as ViewMode[]).map((mode) => <button key={mode} aria-pressed={session.viewMode === mode} onClick={() => onViewMode(mode)}>{mode === "graph" ? "Graph" : mode === "split" ? "Split" : "Workbench"}</button>)}</div>
      <div className="workflow-meta"><span className="workflow-step-label"><b>Step {session.currentStep}/5</b><small>{stepNames[session.currentStep]}</small></span><span className={`workflow-status ${status}`} role="status" aria-live="polite"><i />{status === "processing" ? "Processing" : status === "completed" ? "Completed" : "Ready"}</span></div>
    </header>
    <nav className="workflow-stepper" aria-label="Tahap workflow">{([1, 2, 3, 4, 5] as WorkflowStep[]).map((step) => { const state = session.steps[step]; return <button key={step} className={`${state.status} ${session.currentStep === step ? "active" : ""}`} disabled={state.status === "locked"} onClick={() => onStep(step)} aria-current={session.currentStep === step ? "step" : undefined}><span>{String(step).padStart(2, "0")}</span><b>{stepNames[step]}</b><small>{state.status === "processing" ? `${state.progress}%` : state.status}</small></button>; })}</nav>
  </>;
}

type GraphNode = PolicyGraphNode & SimulationNodeDatum;
type GraphLink = SimulationLinkDatum<GraphNode> & { id: string; type: string };

export function PolicyGraph({ demo, nodeCount, edgeCount, activeNodeId, selectedNodeId, onSelect, onLog }: { demo: DemoCase; nodeCount: number; edgeCount: number; activeNodeId: string | null; selectedNodeId: string | null; onSelect: (id: string | null) => void; onLog: (message: string) => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const viewportRef = useRef<SVGGElement>(null);
  const [showLabels, setShowLabels] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Semua");
  const [layoutKey, setLayoutKey] = useState(0);
  const initialZoomApplied = useRef(false);
  const visibleNodes = demo.graphNodes.slice(0, nodeCount).filter((node) => filter === "Semua" || node.type === filter);
  const ids = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = demo.graphEdges.slice(0, edgeCount).filter((edge) => ids.has(edge.source) && ids.has(edge.target));
  const selected = demo.graphNodes.find((node) => node.id === selectedNodeId) ?? null;

  useEffect(() => {
    const effectNodes = demo.graphNodes.slice(0, nodeCount).filter((node) => filter === "Semua" || node.type === filter);
    const effectIds = new Set(effectNodes.map((node) => node.id));
    const effectEdges = demo.graphEdges.slice(0, edgeCount).filter((edge) => effectIds.has(edge.source) && effectIds.has(edge.target));
    if (!svgRef.current || !viewportRef.current || effectNodes.length === 0) return;
    const svg = select(svgRef.current);
    const viewport = select(viewportRef.current);
    const nodes: GraphNode[] = effectNodes.map((node, index) => ({ ...node, x: node.x || 100 + index * 30, y: node.y || 100 + index * 20 }));
    const links: GraphLink[] = effectEdges.map((edge) => ({ ...edge, source: edge.source, target: edge.target }));
    const simulation = forceSimulation(nodes).force("link", forceLink<GraphNode, GraphLink>(links).id((node) => node.id).distance(105)).force("charge", forceManyBody().strength(-280)).force("center", forceCenter(410, 220)).force("collision", forceCollide(34));
    const edgeGroup = viewport.select<SVGGElement>(".graph-edges").selectAll<SVGGElement, GraphLink>("g").data(links);
    const line = edgeGroup.select<SVGLineElement>("line");
    const edgeLabel = edgeGroup.select<SVGTextElement>("text");
    const group = viewport.select<SVGGElement>(".graph-nodes").selectAll<SVGGElement, GraphNode>("g").data(nodes);
    const zoomBehavior = zoom<SVGSVGElement, unknown>().scaleExtent([0.35, 3]).on("zoom", (event) => viewport.attr("transform", event.transform));
    svg.call(zoomBehavior);
    if (!initialZoomApplied.current) {
      const width = svgRef.current.clientWidth || 820;
      const height = svgRef.current.clientHeight || 440;
      const scale = 0.82;
      svg.call(zoomBehavior.transform, zoomIdentity.translate(width * (1 - scale) / 2, height * (1 - scale) / 2).scale(scale));
      initialZoomApplied.current = true;
    }
    group.call(drag<SVGGElement, GraphNode>().on("start", (event, node) => { if (!event.active) simulation.alphaTarget(.25).restart(); node.fx = node.x; node.fy = node.y; }).on("drag", (event, node) => { node.fx = event.x; node.fy = event.y; }).on("end", (event, node) => { if (!event.active) simulation.alphaTarget(0); node.fx = null; node.fy = null; }));
    simulation.on("tick", () => {
      line.attr("x1", (item) => (item.source as GraphNode).x ?? 0).attr("y1", (item) => (item.source as GraphNode).y ?? 0).attr("x2", (item) => (item.target as GraphNode).x ?? 0).attr("y2", (item) => (item.target as GraphNode).y ?? 0);
      edgeLabel.attr("x", (item) => (((item.source as GraphNode).x ?? 0) + ((item.target as GraphNode).x ?? 0)) / 2).attr("y", (item) => (((item.source as GraphNode).y ?? 0) + ((item.target as GraphNode).y ?? 0)) / 2 - 6);
      group.attr("transform", (node) => `translate(${node.x ?? 0},${node.y ?? 0})`);
    });
    return () => { simulation.stop(); svg.on(".zoom", null); };
  }, [demo, edgeCount, filter, layoutKey, nodeCount]);

  const fit = () => {
    if (!svgRef.current || !viewportRef.current) return;
    const bounds = viewportRef.current.getBBox();
    if (!bounds.width || !bounds.height) return;
    const width = svgRef.current.clientWidth || 820;
    const height = svgRef.current.clientHeight || 440;
    const scale = Math.min(2, .88 / Math.max(bounds.width / width, bounds.height / height));
    const transform = zoomIdentity.translate(width / 2 - scale * (bounds.x + bounds.width / 2), height / 2 - scale * (bounds.y + bounds.height / 2)).scale(scale);
    select(svgRef.current).call(zoom<SVGSVGElement, unknown>().transform, transform);
    onLog("Graph fitted to viewport");
  };
  const focusNode = visibleNodes.find((node) => node.label.toLowerCase().includes(query.toLowerCase()));
  useEffect(() => { if (query && focusNode && focusNode.id !== selectedNodeId) onSelect(focusNode.id); }, [focusNode, onSelect, query, selectedNodeId]);

  return <section className="policy-graph-panel" aria-labelledby="graph-title"><header className="graph-toolbar"><div><p>POLICY KNOWLEDGE GRAPH</p><h2 id="graph-title">{demo.title}</h2></div><div className="graph-actions"><button onClick={() => { setLayoutKey((value) => value + 1); onLog("Graph layout refreshed"); }}>↻ <span>Refresh</span></button><button onClick={fit}>⊙ <span>Fit</span></button></div></header><div className="graph-filters"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari entity..." aria-label="Cari entity graph" /><select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter tipe entity"><option>Semua</option>{Object.keys(graphColors).map((type) => <option key={type}>{type}</option>)}</select><label><input type="checkbox" checked={showLabels} onChange={(event) => setShowLabels(event.target.checked)} /> Label relasi</label></div><div className="graph-stage">
    {visibleNodes.length === 0 ? <div className="graph-waiting"><i /><h3>Graph menunggu proses build</h3><p>Entity dan relasi akan muncul secara bertahap.</p></div> : <svg ref={svgRef} role="group" aria-label={`Graf stakeholder dan kebijakan ${demo.title}`} onClick={(event) => { if (event.target === event.currentTarget) onSelect(null); }}><g ref={viewportRef}><g className="graph-edges">{visibleEdges.map((edge) => { const connected = selectedNodeId && (edge.source === selectedNodeId || edge.target === selectedNodeId); return <g key={edge.id}><line className={connected ? "selected" : ""} />{showLabels && <text>{edge.type}</text>}</g>; })}</g><g className="graph-nodes">{visibleNodes.map((node) => <g key={node.id} className={`${activeNodeId === node.id ? "active" : ""} ${selectedNodeId === node.id ? "selected" : ""}`} onClick={(event) => { event.stopPropagation(); onSelect(node.id); }} tabIndex={0} role="button" aria-label={`${node.label}, ${node.type}. ${node.summary}`} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(node.id); }}><circle r={node.type === "PolicyIssue" ? 15 : 11} fill={graphColors[node.type]} /><text x="18" y="4">{node.label}</text></g>)}</g></g></svg>}
    {selected && <aside className="graph-inspector" aria-label="Detail entity"><div><span style={{ background: graphColors[selected.type] }} />{selected.type}</div><h3>{selected.label}</h3><p>{selected.summary}</p>{selected.group && <dl><dt>Kelompok</dt><dd>{selected.group}</dd></dl>}<button onClick={() => onSelect(null)}>Tutup detail</button></aside>}
    <div className="graph-legend" aria-label="Legenda entity">{Object.entries(graphColors).map(([type, color]) => <button key={type} className={filter === type ? "active" : ""} onClick={() => setFilter(filter === type ? "Semua" : type)}><i style={{ background: color }} />{type}</button>)}</div>
  </div></section>;
}

export function SystemConsole({ logs }: { logs: ConsoleLog[] }) {
  const [collapsed, setCollapsed] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const [autoScroll, setAutoScroll] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const visible = logs.filter((log) => filter === "ALL" || log.level === filter);
  useEffect(() => { if (autoScroll) ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }, [autoScroll, logs]);
  const copy = () => navigator.clipboard?.writeText(logs.map((log) => `[${log.time}] ${log.level} ${log.message}`).join("\n"));
  return <section className={`system-console ${collapsed ? "collapsed" : ""}`} aria-label="System console"><div className="console-header"><button onClick={() => setCollapsed(!collapsed)} aria-expanded={!collapsed}>SYSTEM CONSOLE</button><div>{!collapsed && <><select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter console"><option>ALL</option><option>INFO</option><option>WARN</option><option>DONE</option></select><button onClick={() => setAutoScroll(!autoScroll)}>{autoScroll ? "AUTO" : "PAUSED"}</button><button onClick={copy}>COPY</button></>}<button onClick={() => setCollapsed(!collapsed)}>{logs.length} EVENTS {collapsed ? "⌃" : "⌄"}</button></div></div>{!collapsed && <div className="console-lines" ref={ref}>{visible.map((log) => <div key={log.id} className={log.level.toLowerCase()}><time>{log.time}</time><b>{log.level}</b><span>{log.message}</span></div>)}</div>}<span className="sr-only" aria-live="polite">{logs.at(-1)?.message}</span></section>;
}

export function StepCard({ number, task, state, progress = 0, children }: { number: number; task: WorkflowTask; state: StepRunStatus; progress?: number; children?: React.ReactNode }) {
  const label = state === "processing" ? `${progress}%` : state === "completed" ? "Complete" : state === "failed" ? "Failed" : state === "locked" ? "Locked" : "Ready";
  return <article className={`workflow-task ${state}`}><header><span className="task-number">{String(number).padStart(2, "0")}</span><h3>{task.title}</h3><span className={`task-badge ${state}`}>{label}</span></header><code>{task.endpoint}</code><p>{task.description}</p>{state === "processing" && <div className="task-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${progress}%` }} /></div>}{children}</article>;
}
