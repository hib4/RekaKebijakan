import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../../components/AppShell/AppShell";
import { useReports } from "../../api/queries";
import "./ReportsPage.css";

export default function ReportsPage() {
  const navigate = useNavigate();
  const reportsQuery = useReports();
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("Semua risiko");
  const [sort, setSort] = useState("Terbaru");
  const reports = reportsQuery.data ?? [];
  const visible = reports.filter((item) => {
    const report = item.snapshot.report;
    const matchesQuery = `${item.name} ${item.institution} ${report?.title ?? ""}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (risk === "Semua risiko" || item.highest_risk === risk);
  }).toSorted((a, b) => sort === "Nama proyek" ? a.name.localeCompare(b.name) : b.updated_at.localeCompare(a.updated_at));

  const eventCount = reports.reduce((total, item) => total + (item.snapshot.simulation?.event_count ?? 0), 0);
  return <AppShell title="Laporan" subtitle="Laporan dari simulasi kebijakan yang telah menyelesaikan proses generasi dan peninjauan risiko." eyebrow="Keluaran simulasi">
    <section className="report-index-summary" aria-label="Ringkasan laporan"><article><span>Laporan selesai</span><b>{reports.length}</b></article><article><span>Risiko tinggi</span><b>{reports.filter((item) => item.highest_risk === "Tinggi").length}</b></article><article><span>Total jejak event</span><b>{eventCount}</b></article></section>
    <section className="dashboard-panel reports-index" aria-labelledby="reports-list-title">
      <div className="panel-heading"><div><h2 id="reports-list-title">Laporan Simulasi Kebijakan</h2><p>Hanya simulasi dengan laporan selesai yang ditampilkan.</p></div></div>
      <div className="reports-toolbar"><label>Cari laporan<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari proyek atau institusi" /></label><label>Risiko<select value={risk} onChange={(event) => setRisk(event.target.value)}><option>Semua risiko</option><option>Tinggi</option><option>Sedang</option><option>Rendah</option></select></label><label>Urutkan<select value={sort} onChange={(event) => setSort(event.target.value)}><option>Terbaru</option><option>Nama proyek</option></select></label></div>
      {reportsQuery.isLoading && <div className="state-block"><h3>Memuat laporan...</h3><p>Mengambil laporan terbaru dari server.</p></div>}
      {reportsQuery.isError && <div className="state-block"><h3>Laporan tidak dapat dimuat</h3><p>Periksa koneksi lalu coba kembali.</p><button className="button primary" onClick={() => reportsQuery.refetch()}>Muat ulang</button></div>}
      {!reportsQuery.isLoading && !reportsQuery.isError && visible.length === 0 ? <div className="state-block"><h3>Belum ada laporan yang sesuai</h3><p>Laporan akan muncul setelah Step 4 pada workflow proyek selesai.</p><button className="button primary" onClick={() => navigate("/projects")}>Buka Proyek Kebijakan</button></div> : null}
      {visible.length > 0 && <div className="reports-table-wrap"><table className="data-table reports-table"><thead><tr><th>Laporan</th><th>Institusi</th><th>Diperbarui</th><th>Risiko tertinggi</th><th>Jejak simulasi</th><th>Aksi</th></tr></thead><tbody>{visible.map((item) => <tr key={item.id}><td><b>{item.snapshot.report?.title ?? `Laporan ${item.name}`}</b><span>{item.name}</span></td><td>{item.institution}</td><td>{new Date(item.updated_at).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}</td><td><span className={`report-risk ${item.highest_risk.toLowerCase()}`}>{item.highest_risk}</span></td><td>{item.snapshot.simulation?.event_count ?? 0} event · {item.snapshot.environment?.persona_count ?? 0} persona</td><td><div className="report-actions"><button onClick={() => navigate(`/simulation/${item.simulation_id}?step=report&mode=workbench`)}>Buka laporan</button><button onClick={() => navigate(`/simulation/${item.simulation_id}?step=interaction&mode=workbench`)}>Interaction</button></div></td></tr>)}</tbody></table></div>}
    </section>
  </AppShell>;
}
