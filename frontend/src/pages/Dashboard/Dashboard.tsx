import { useNavigate } from "react-router-dom";
import { AppShell } from "../../components/AppShell/AppShell";
import { useDashboard } from "../../api/queries";
import "./Dashboard.css";

function RiskLabel({ value }: { value: string }) {
  const key = value.toLowerCase().replaceAll(" ", "-");
  return <span className={`dash-risk dash-risk-${key}`}>{value}</span>;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const dashboard = useDashboard();
  const data = dashboard.data;
  const metrics = data
    ? ([
        ["Proyek aktif", data.metrics.active_projects, "Ruang kerja saat ini"],
        ["Simulasi berjalan", data.metrics.running_simulations, "Pekerjaan aktif"],
        ["Perlu ditinjau", data.metrics.review_items, "Risiko tinggi"],
        ["Laporan tersedia", data.metrics.available_reports, "Siap dibuka"],
      ] as const)
    : [];

  return (
    <AppShell
      title="Dashboard"
      subtitle="Pantau proyek kebijakan, simulasi, dan temuan yang memerlukan peninjauan."
      eyebrow="Ringkasan kerja"
      actions={
        <>
          <button className="button primary" onClick={() => navigate("/projects")}>
            Buka Proyek Kebijakan
          </button>
          <button className="button secondary" onClick={() => navigate("/reports")}>
            Lihat Laporan
          </button>
        </>
      }
    >
      {dashboard.isLoading && (
        <div className="state-block">
          <h3>Memuat dashboard...</h3>
          <p>Menyusun ringkasan terbaru dari ruang kerja.</p>
        </div>
      )}
      {dashboard.isError && (
        <div className="state-block">
          <h3>Dashboard tidak dapat dimuat</h3>
          <p>Periksa koneksi lalu coba kembali.</p>
          <button className="button primary" onClick={() => dashboard.refetch()}>
            Muat ulang
          </button>
        </div>
      )}
      {data && (
        <>
          <section className="metrics-grid" aria-label="Ringkasan metrik">
            {metrics.map(([label, value, detail]) => (
              <article className="metric-card" key={label}>
                <p>{label}</p>
                <strong>{value}</strong>
                <span>{detail}</span>
                {/* <small>Diperbarui {new Date(data.generated_at).toLocaleTimeString("id-ID")}</small> */}
              </article>
            ))}
          </section>
          {data.recent_projects.length === 0 ? (
            <div className="state-block">
              <h3>Belum ada proyek kebijakan</h3>
              <p>Buat proyek pertama untuk mulai membangun graph dan simulasi.</p>
              <button className="button primary" onClick={() => navigate("/projects/new")}>
                Buat Proyek
              </button>
            </div>
          ) : (
            <div className="dashboard-grid">
              <section className="dashboard-panel span-2" aria-labelledby="attention-title">
                <div className="panel-heading">
                  <h2 id="attention-title">Perlu Ditinjau</h2>
                  <span>{data.attention.length} prioritas aktif</span>
                </div>
                {data.attention.length === 0 ? (
                  <div className="state-block">
                    <h3>Tidak ada prioritas tinggi</h3>
                    <p>Semua proyek berada dalam batas risiko saat ini.</p>
                  </div>
                ) : (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Prioritas</th>
                          <th>Proyek</th>
                          <th>Institusi</th>
                          {/* <th>Diperbarui</th> */}
                          <th>Aksi</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.attention.map((item) => (
                          <tr key={item.id}>
                            <td>
                              <RiskLabel value={item.highest_risk} />
                            </td>
                            <td>{item.name}</td>
                            <td>{item.institution}</td>
                            {/* <td>{new Date(item.updated_at).toLocaleDateString("id-ID")}</td> */}
                            <td>
                              <button
                                className="text-button inline-action"
                                onClick={() => navigate(`/projects/${item.id}`)}
                              >
                                Tinjau
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
              {data.active_runs[0] && (
                <section className="dashboard-panel active-simulation" aria-labelledby="active-sim-title">
                  <div className="panel-heading">
                    <div>
                      <h2 id="active-sim-title">Simulasi Berjalan</h2>
                      <p>{data.active_runs[0].name}</p>
                    </div>
                    <span className="status-badge">{data.active_runs[0].workflow_status}</span>
                  </div>
                  <div className="simulation-summary">
                    <div>
                      <span>Tahap</span>
                      <b>{data.active_runs[0].current_stage}</b>
                    </div>
                    <div>
                      <span>Risiko</span>
                      <b>{data.active_runs[0].highest_risk}</b>
                    </div>
                  </div>
                  <div className="actions">
                    <button
                      className="button primary"
                      onClick={() => navigate(`/simulation/${data.active_runs[0].simulation_id}`)}
                    >
                      Buka Simulasi
                    </button>
                  </div>
                </section>
              )}
              <section className="dashboard-panel span-2" aria-labelledby="projects-title">
                <div className="panel-heading">
                  <h2 id="projects-title">Proyek Terbaru</h2>
                  <button className="text-button inline-action" onClick={() => navigate("/projects")}>
                    Lihat semua proyek
                  </button>
                </div>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Nama proyek</th>
                        <th>Institusi</th>
                        <th>Status</th>
                        <th>Risiko tertinggi</th>
                        {/* <th>Diperbarui</th> */}
                        <th>Aksi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_projects.map((item) => (
                        <tr key={item.id}>
                          <td>{item.name}</td>
                          <td>{item.institution}</td>
                          <td>{item.workflow_status}</td>
                          <td>
                            <RiskLabel value={item.highest_risk} />
                          </td>
                          {/* <td>{new Date(item.updated_at).toLocaleDateString("id-ID")}</td> */}
                          <td>
                            <button
                              className="text-button inline-action"
                              onClick={() => navigate(`/projects/${item.id}`)}
                            >
                              Buka
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}
