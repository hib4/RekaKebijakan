import { useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell/AppShell";
import { listWorkspaceReports } from "../../data/localWorkspace";
import "./ReportsPage.css";

function navigate(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function ReportsPage() {
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("Semua risiko");
  const [sort, setSort] = useState("Terbaru");
  const reports = listWorkspaceReports();
  const visible = useMemo(() => reports.filter((report) => {
    const matchesQuery = `${report.projectName} ${report.institution} ${report.title}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (risk === "Semua risiko" || report.highestRisk === risk);
  }).toSorted((a, b) => sort === "Nama proyek" ? a.projectName.localeCompare(b.projectName) : b.completedAt.localeCompare(a.completedAt)), [query, reports, risk, sort]);

  return <AppShell title="Laporan" subtitle="Laporan dari simulasi kebijakan yang telah menyelesaikan proses generasi dan peninjauan risiko." eyebrow="Keluaran simulasi">
    <section className="report-index-summary" aria-label="Ringkasan laporan"><article><span>Laporan selesai</span><b>{reports.length}</b></article><article><span>Risiko tinggi</span><b>{reports.filter((report) => report.highestRisk === "Tinggi").length}</b></article><article><span>Total jejak event</span><b>{reports.reduce((total, report) => total + report.eventCount, 0)}</b></article></section>
    <section className="dashboard-panel reports-index" aria-labelledby="reports-list-title">
      <div className="panel-heading"><div><h2 id="reports-list-title">Laporan Simulasi Kebijakan</h2><p>Hanya simulasi dengan laporan selesai yang ditampilkan.</p></div></div>
      <div className="reports-toolbar"><label>Cari laporan<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari proyek atau institusi" /></label><label>Risiko<select value={risk} onChange={(event) => setRisk(event.target.value)}><option>Semua risiko</option><option>Tinggi</option><option>Sedang</option><option>Rendah</option></select></label><label>Urutkan<select value={sort} onChange={(event) => setSort(event.target.value)}><option>Terbaru</option><option>Nama proyek</option></select></label></div>
      {visible.length === 0 ? <div className="state-block"><h3>Belum ada laporan yang sesuai</h3><p>Laporan akan muncul setelah Step 4 pada workflow proyek selesai.</p><button className="button primary" onClick={() => navigate("/projects")}>Buka Proyek Kebijakan</button></div> : <div className="reports-table-wrap"><table className="data-table reports-table"><thead><tr><th>Laporan</th><th>Institusi</th><th>Selesai</th><th>Risiko tertinggi</th><th>Jejak simulasi</th><th>Aksi</th></tr></thead><tbody>{visible.map((report) => <tr key={report.id}><td><b>{report.title}</b><span>{report.projectName}</span></td><td>{report.institution}</td><td>{new Date(report.completedAt).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}</td><td><span className={`report-risk ${report.highestRisk.toLowerCase()}`}>{report.highestRisk}</span></td><td>{report.eventCount} event · {report.personaCount} persona</td><td><div className="report-actions"><button onClick={() => navigate(`/simulation/${report.simulationId}?step=report&mode=workbench`)}>Buka laporan</button><button onClick={() => navigate(`/simulation/${report.simulationId}?step=interaction&mode=workbench`)}>Interaction</button></div></td></tr>)}</tbody></table></div>}
    </section>
  </AppShell>;
}
