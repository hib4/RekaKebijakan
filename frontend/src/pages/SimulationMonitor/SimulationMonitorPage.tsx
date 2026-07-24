import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell/AppShell";
import "./SimulationMonitor.css";

// Demo-only prototype. This page intentionally has no application route.

type Status = "running" | "paused" | "completed" | "stopped";
type Level = "Rendah" | "Sedang" | "Tinggi";
type Node = { id: string; label: string; x: number; y: number; r: number; personas: number; stance: string; concern: string; influence: Level };
type Event = { id: string; round: number; time: string; node: string; persona: string; type: string; message: string; risk: Level; edge: string; };
type Log = { id: string; time: string; level: "INFO" | "WARN" | "DONE"; message: string };
type ProjectConfig = { name: string; nodes: Node[]; edges: [string, string][]; events: Event[] };

const configs: Record<string, ProjectConfig> = {
  "registrasi-digital-umkm": {
    name: "Registrasi Digital UMKM",
    nodes: [
      { id: "mikro", label: "Pelaku UMKM mikro", x: 116, y: 190, r: 20, personas: 10, stance: "Khawatir", concern: "Pajak tambahan dan data pribadi", influence: "Sedang" },
      { id: "kecil", label: "Pelaku UMKM kecil", x: 278, y: 92, r: 17, personas: 8, stance: "Netral", concern: "Kesederhanaan prosedur", influence: "Sedang" },
      { id: "dinas", label: "Dinas UMKM", x: 446, y: 172, r: 25, personas: 5, stance: "Mendukung", concern: "Kesiapan kanal layanan", influence: "Tinggi" },
      { id: "platform", label: "Platform digital", x: 628, y: 80, r: 21, personas: 6, stance: "Mendukung", concern: "Standar integrasi data", influence: "Tinggi" },
      { id: "pendamping", label: "Pendamping UMKM", x: 647, y: 274, r: 21, personas: 7, stance: "Mendukung", concern: "Materi dan kanal bantuan", influence: "Tinggi" },
      { id: "konsumen", label: "Konsumen lokal", x: 335, y: 292, r: 14, personas: 6, stance: "Netral", concern: "Harga dan transparansi usaha", influence: "Rendah" },
      { id: "komunitas", label: "Komunitas usaha", x: 773, y: 176, r: 16, personas: 4, stance: "Netral", concern: "Kejelasan masa transisi", influence: "Sedang" },
      { id: "pengaduan", label: "Kanal pengaduan", x: 505, y: 315, r: 13, personas: 3, stance: "Netral", concern: "Akses klarifikasi", influence: "Rendah" },
    ],
    edges: [["mikro", "dinas"], ["mikro", "kecil"], ["kecil", "dinas"], ["dinas", "platform"], ["dinas", "pendamping"], ["dinas", "konsumen"], ["platform", "komunitas"], ["pendamping", "pengaduan"], ["konsumen", "pengaduan"], ["pendamping", "komunitas"]],
    events: [
      { id: "e1", round: 2, time: "10:04:52", node: "mikro", persona: "Ibu Rani", type: "Menguatkan narasi", message: "Kekhawatiran bahwa registrasi digital berkaitan dengan pajak tambahan.", risk: "Tinggi", edge: "mikro-dinas" },
      { id: "e2", round: 2, time: "10:04:58", node: "kecil", persona: "Pak Dedi", type: "Tanggapan", message: "Meminta proses registrasi sederhana dan tidak mengganggu operasional.", risk: "Sedang", edge: "kecil-dinas" },
      { id: "e3", round: 2, time: "10:05:10", node: "pendamping", persona: "Sari", type: "Klarifikasi", message: "Materi sosialisasi dan kanal bantuan perlu tersedia bagi pendamping.", risk: "Rendah", edge: "pendamping-pengaduan" },
      { id: "e4", round: 3, time: "10:05:39", node: "dinas", persona: "Nina", type: "Klarifikasi", message: "Kanal bantuan dan periode transisi disiapkan sebagai asumsi skenario revisi.", risk: "Sedang", edge: "dinas-pendamping" },
      { id: "e5", round: 3, time: "10:05:46", node: "mikro", persona: "Ibu Rani", type: "Perubahan sikap", message: "Pendampingan dan penjelasan data meningkatkan kesiapan mencoba proses.", risk: "Sedang", edge: "mikro-dinas" },
      { id: "e6", round: 4, time: "10:06:01", node: "platform", persona: "Andika", type: "Pernyataan awal", message: "Standar teknis dan batas akses data perlu dijelaskan sebelum integrasi.", risk: "Sedang", edge: "dinas-platform" },
      { id: "e7", round: 5, time: "10:06:28", node: "komunitas", persona: "Rizal", type: "Tanggapan", message: "Komunitas usaha membutuhkan contoh proses dan jadwal sosialisasi yang jelas.", risk: "Rendah", edge: "platform-komunitas" },
    ],
  },
  "penyaluran-pupuk": {
    name: "Penyaluran Pupuk",
    nodes: [
      { id: "petani", label: "Petani", x: 130, y: 185, r: 23, personas: 12, stance: "Khawatir", concern: "Ketersediaan dan harga pupuk", influence: "Tinggi" },
      { id: "kios", label: "Kios Resmi", x: 292, y: 88, r: 18, personas: 6, stance: "Netral", concern: "Validasi distribusi", influence: "Sedang" },
      { id: "distributor", label: "Distributor", x: 455, y: 180, r: 22, personas: 5, stance: "Netral", concern: "Jadwal penyaluran", influence: "Tinggi" },
      { id: "kementerian", label: "Kementerian", x: 625, y: 92, r: 25, personas: 4, stance: "Mendukung", concern: "Ketepatan sasaran", influence: "Tinggi" },
      { id: "penyuluh", label: "Penyuluh", x: 640, y: 276, r: 19, personas: 7, stance: "Mendukung", concern: "Informasi lapangan", influence: "Tinggi" },
      { id: "kelompok", label: "Kelompok Tani", x: 328, y: 290, r: 19, personas: 8, stance: "Netral", concern: "Akses pengaduan", influence: "Sedang" },
    ],
    edges: [["petani", "kios"], ["petani", "kelompok"], ["kios", "distributor"], ["distributor", "kementerian"], ["distributor", "penyuluh"], ["penyuluh", "kelompok"]],
    events: [{ id: "p1", round: 2, time: "10:04:52", node: "petani", persona: "Pak Asep", type: "Tanggapan", message: "Kelompok tani meminta kepastian jadwal penyaluran pupuk.", risk: "Sedang", edge: "petani-kelompok" }],
  },
};

function navigate(path: string) { window.history.pushState(null, "", path); window.dispatchEvent(new PopStateEvent("popstate")); }
function edgeId(a: string, b: string) { return [a, b].sort().join("-"); }
function riskClass(level: Level) { return level.toLowerCase(); }

export default function SimulationMonitorPage() {
  const projectId = window.location.pathname.split("/")[2] || "registrasi-digital-umkm";
  const config = configs[projectId] ?? configs["registrasi-digital-umkm"];
  const [simulationStatus, setSimulationStatus] = useState<Status>("running");
  const [events, setEvents] = useState<Event[]>([]);
  const [activeNodeId, setActiveNodeId] = useState("dinas");
  const [activeEdgeIds, setActiveEdgeIds] = useState<string[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRound, setSelectedRound] = useState<number | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [activeTab, setActiveTab] = useState("events");
  const [logFilter, setLogFilter] = useState("Semua");
  const [autoScrollLog, setAutoScrollLog] = useState(true);
  const [logs, setLogs] = useState<Log[]>([{ id: "l1", time: "10:04:21", level: "INFO", message: `Simulasi ${config.name} diinisialisasi` }, { id: "l2", time: "10:04:40", level: "INFO", message: "Ronde 2 dimulai" }]);
  const logRef = useRef<HTMLDivElement>(null);
  const currentRound = simulationStatus === "completed" ? 5 : events.length < 3 ? 2 : Math.min(5, events[events.length - 1]?.round ?? 2);
  const supportPercent = Math.min(62, 46 + events.filter((event) => event.risk === "Rendah").length * 4);
  const concernPercent = Math.max(24, 38 - events.filter((event) => event.risk === "Rendah").length * 2 + events.filter((event) => event.risk === "Tinggi").length * 4);
  const narrativeRisk: Level = events.some((event) => event.risk === "Tinggi") ? "Tinggi" : "Sedang";
  const appendEvent = useCallback(() => {
    const next = config.events[events.length];
    if (!next) { setSimulationStatus("completed"); setLogs((items) => [...items, { id: "done", time: "10:06:40", level: "DONE", message: "Ronde simulasi selesai ditinjau" }]); return; }
    setEvents((items) => [...items, next]); setActiveNodeId(next.node); setActiveEdgeIds([next.edge]);
    setLogs((items) => [...items, { id: `log-${next.id}`, time: next.time, level: next.risk === "Tinggi" ? "WARN" : "INFO", message: `${next.type}: ${next.persona}` }]);
  }, [config.events, events.length]);
  useEffect(() => { if (simulationStatus !== "running") return undefined; const timer = window.setInterval(appendEvent, Math.round(2600 / playbackSpeed)); return () => window.clearInterval(timer); }, [appendEvent, playbackSpeed, simulationStatus]);
  useEffect(() => { if (autoScrollLog) logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" }); }, [autoScrollLog, logs]);
  const reset = () => { setSimulationStatus("running"); setEvents([]); setActiveNodeId("dinas"); setActiveEdgeIds([]); setSelectedNodeId(null); setSelectedRound(null); setLogs([{ id: "l1", time: "10:04:21", level: "INFO", message: `Simulasi ${config.name} diinisialisasi` }]); };
  const selectNode = (id: string) => { setSelectedNodeId((current) => current === id ? null : id); setActiveNodeId(id); };
  const visibleEvents = events.filter((event) => (!selectedNodeId || event.node === selectedNodeId) && (!selectedRound || event.round === selectedRound));
  const roundState = (round: number) => simulationStatus === "completed" || round < currentRound ? "Selesai" : round === currentRound ? "Berjalan" : "Menunggu";
  const selectedNode = config.nodes.find((node) => node.id === selectedNodeId);
  const visibleLogs = logs.filter((log) => logFilter === "Semua" || log.level === logFilter);
  const copyLog = () => navigator.clipboard?.writeText(logs.map((log) => `[${log.time}] ${log.level} ${log.message}`).join("\n"));
  const badge = simulationStatus === "running" ? "Berjalan" : simulationStatus === "paused" ? "Dijeda" : simulationStatus === "completed" ? "Selesai" : "Dihentikan";

  return <AppShell title="Simulation Monitor" subtitle="Pantau event simulasi dan jejak bukti dari asumsi skenario yang ditinjau." eyebrow="Workspace kebijakan" actions={<><button className="button primary" onClick={() => simulationStatus === "completed" ? undefined : setSimulationStatus(simulationStatus === "running" ? "paused" : "running")} disabled={simulationStatus === "stopped"}>{simulationStatus === "running" ? "Jeda simulasi" : simulationStatus === "completed" ? "Buat laporan" : "Lanjutkan simulasi"}</button><button className="button secondary" onClick={() => navigate(`/projects/${projectId}`)}>Kembali ke workspace</button></>}>
    <section className="experiment-controls" aria-label="Kontrol simulasi"><span className={`project-badge monitor-status ${simulationStatus}`}><i />{badge}</span><label>Kecepatan<select value={playbackSpeed} onChange={(event) => setPlaybackSpeed(Number(event.target.value))}><option value={0.5}>0.5x</option><option value={1}>1x</option><option value={2}>2x</option></select></label><button className="text-button" onClick={appendEvent} disabled={simulationStatus === "completed" || simulationStatus === "stopped"}>Event berikutnya</button><button className="text-button" onClick={reset}>Reset demo</button><button className="text-button danger-text" onClick={() => { setSimulationStatus("stopped"); setLogs((items) => [...items, { id: "stop", time: "10:06:41", level: "WARN", message: "Simulasi dihentikan; event tersimpan sebagai draft" }]); }} disabled={simulationStatus === "completed" || simulationStatus === "stopped"}>Hentikan simulasi</button></section>
    <section className="experiment-canvas" aria-labelledby="experiment-title"><header><div><p className="eyebrow">EKSPERIMEN AKTIF</p><h2 id="experiment-title">{config.name}</h2></div><span className="round-badge">Ronde {currentRound} dari 5</span></header><div className="stakeholder-graph-wrap"><svg className="stakeholder-graph" viewBox="0 0 880 370" role="group" aria-label="Graf stakeholder simulasi">{config.edges.map(([from, to]) => { const a = config.nodes.find((node) => node.id === from)!; const b = config.nodes.find((node) => node.id === to)!; const id = edgeId(from, to); return <line className={activeEdgeIds.includes(id) ? "active-edge" : ""} key={id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />; })}{config.nodes.map((node) => <g className={`${activeNodeId === node.id ? "graph-node active" : "graph-node"} ${selectedNodeId === node.id ? "selected" : ""}`} key={node.id}><circle cx={node.x} cy={node.y} r={node.r} /><foreignObject x={node.x - 24} y={node.y - 24} width="48" height="48"><button aria-label={`${node.label}. ${node.personas} persona aktif. Sikap ${node.stance}. Kekhawatiran ${node.concern}. Pengaruh ${node.influence}.`} onClick={() => selectNode(node.id)} /></foreignObject><foreignObject className="graph-label" x={node.x + node.r + 8} y={node.y - 13} width="145" height="32"><span>{node.label}</span></foreignObject><title>{node.label} · {node.personas} persona aktif · {node.stance} · {node.concern} · Pengaruh {node.influence}</title></g>)}</svg></div>{selectedNode && <div className="node-detail"><b>{selectedNode.label}</b><span>{selectedNode.personas} persona sintetis · {selectedNode.stance} · {selectedNode.concern} · Pengaruh {selectedNode.influence}</span><button className="text-button" onClick={() => setSelectedNodeId(null)}>Clear filter</button></div>}<div className="round-progress" aria-label="Progres ronde">{[1, 2, 3, 4, 5].map((round) => <button className={round < currentRound || simulationStatus === "completed" ? "done" : round === currentRound ? "current" : ""} key={round} onClick={() => setSelectedRound(selectedRound === round ? null : round)} title={`Ronde ${round} ${roundState(round).toLowerCase()}`}><span>Ronde {round}</span></button>)}</div><div className="canvas-metrics"><div><span>Dukungan</span><b>{supportPercent}%</b><i><em style={{ width: `${supportPercent}%` }} /></i></div><div><span>Kekhawatiran</span><b>{concernPercent}%</b><i className="warning"><em style={{ width: `${concernPercent}%` }} /></i></div><div><span>Risiko narasi</span><b>{narrativeRisk}</b><small><i />Ditinjau</small></div></div><footer><i />{simulationStatus === "completed" ? "Aktivitas ronde selesai ditinjau" : "Aktivitas ronde sedang berjalan"}</footer></section>
    <section className="experiment-details" aria-label="Detail simulasi"><div className="monitor-tabs" role="tablist"><button aria-selected={activeTab === "events"} onClick={() => setActiveTab("events")}>Event simulasi</button><button aria-selected={activeTab === "personas"} onClick={() => setActiveTab("personas")}>Reaksi persona</button><button aria-selected={activeTab === "risks"} onClick={() => setActiveTab("risks")}>Risiko narasi</button><button aria-selected={activeTab === "logs"} onClick={() => setActiveTab("logs")}>Sistem log</button></div>{activeTab === "events" && <div className="detail-panel"><div className="detail-heading"><h2>Event simulasi</h2><span>{visibleEvents.length} event terlihat</span></div>{visibleEvents.length ? visibleEvents.slice().reverse().map((event) => <button className="event-row" key={event.id} onClick={() => { setActiveNodeId(event.node); setActiveEdgeIds([event.edge]); setSelectedNodeId(event.node); }}><span>Ronde {event.round} · {event.time}</span><b>{event.persona} · {event.type}</b><p>{event.message}</p><i className={`risk-tag ${riskClass(event.risk)}`}>Risiko {event.risk}</i></button>) : <p className="empty-copy">Event simulasi akan muncul saat asumsi skenario diproses.</p>}</div>}{activeTab === "personas" && <div className="detail-panel persona-table"><div className="detail-heading"><h2>Reaksi persona</h2><span>30 persona aktif</span></div>{config.nodes.map((node) => <button key={node.id} onClick={() => selectNode(node.id)}><b>{node.label}</b><span>{node.stance}</span><p>{node.concern}</p><small>Pengaruh {node.influence} · Risiko {node.id === "mikro" ? "Tinggi" : "Sedang"}</small></button>)}</div>}{activeTab === "risks" && <div className="detail-panel risk-list"><div className="detail-heading"><h2>Risiko narasi</h2><span>Indikasi risiko</span></div>{[["Registrasi digital berarti pajak tambahan", "Tinggi", "Meningkat", "Pelaku UMKM mikro, Pelaku UMKM kecil"], ["Data usaha tidak aman", "Sedang", "Stabil", "Pelaku UMKM mikro, Konsumen lokal"], ["Proses digital menyulitkan usaha kecil", "Sedang", "Meningkat", "Pelaku UMKM mikro, Pendamping UMKM"]].map(([title, level, trend, affected]) => <article key={title}><b>{title}</b><span className={`risk-tag ${level.toLowerCase()}`}>{level} · {trend}</span><p>{affected}</p></article>)}</div>}{activeTab === "logs" && <div className="detail-panel log-panel"><div className="detail-heading"><h2>Sistem log</h2><div><label><input type="checkbox" checked={autoScrollLog} onChange={(event) => setAutoScrollLog(event.target.checked)} /> Auto-scroll</label><select value={logFilter} onChange={(event) => setLogFilter(event.target.value)}><option>Semua</option><option>INFO</option><option>WARN</option><option>DONE</option></select><button className="text-button" onClick={copyLog}>Salin</button></div></div><div ref={logRef}>{visibleLogs.map((log) => <p className={log.level.toLowerCase()} key={log.id}>[{log.time}] <b>{log.level}</b> {log.message}</p>)}</div></div>}</section>
    <p className="responsible-note">Event simulasi berasal dari persona sintetis dan asumsi skenario. Hasilnya digunakan sebagai dukungan keputusan dan indikasi risiko, bukan untuk menyimpulkan opini masyarakat secara pasti.</p>
  </AppShell>;
}
