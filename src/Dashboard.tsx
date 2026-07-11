import { useEffect, useId, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  attentionRows,
  overviewMetrics,
  projectStatuses,
  recentActivity,
  recentProjects,
} from "./data/dashboard";

type Toast = { id: number; message: string };

function navigatePlaceholder(target: string, setToast: (message: string) => void) {
  window.history.pushState({}, "", target);
  setToast(`Membuka ${target}. Halaman ini masih berupa placeholder prototipe.`);
}

function RiskLabel({ value }: { value: string }) {
  const key = value.toLowerCase().replaceAll(" ", "-");
  return <span className={`dash-risk dash-risk-${key}`}>{value}</span>;
}

function MetricCard({ metric }: { metric: (typeof overviewMetrics)[number] }) {
  return (
    <article className="metric-card">
      <p>{metric[0]}</p>
      <strong>{metric[1]}</strong>
      <span>{metric[2]}</span>
      <small>{metric[3]}</small>
    </article>
  );
}

function CreateProjectDialog({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={(event) => event.stopPropagation()}>
        <button className="dialog-close" onClick={onClose} aria-label="Tutup dialog">X</button>
        {submitted ? (
          <div className="form-success">
            <p className="eyebrow">PROYEK DIBUAT</p>
            <h2 id={titleId}>Proyek tersimpan sebagai prototipe.</h2>
            <p>Data tidak dikirim ke server. Interaksi ini hanya menunjukkan alur dashboard.</p>
            <button className="button primary" onClick={onClose}>Tutup</button>
          </div>
        ) : (
          <>
            <p className="eyebrow">PROYEK BARU</p>
            <h2 id={titleId}>Buat proyek kebijakan.</h2>
            <form onSubmit={submit}>
              <label>Nama proyek<input name="project" required autoFocus /></label>
              <label>Institusi<input name="institution" required /></label>
              <label>Tujuan pengujian<textarea name="purpose" required rows={3} /></label>
              <button className="button primary" type="submit">Buat Proyek</button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}

function AttentionList({ onAction }: { onAction: (label: string) => void }) {
  return (
    <section className="dashboard-panel span-2" aria-labelledby="attention-title">
      <div className="panel-heading">
        <h2 id="attention-title">Perlu Ditinjau</h2>
        <span>3 prioritas aktif</span>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr><th>Prioritas</th><th>Proyek</th><th>Temuan</th><th>Sumber</th><th>Diperbarui</th><th>Aksi</th></tr>
          </thead>
          <tbody>
            {attentionRows.map((row) => (
              <tr key={`${row.project}-${row.action}`}>
                <td><RiskLabel value={row.severity} /></td>
                <td>{row.project}</td>
                <td>{row.finding}</td>
                <td>{row.source}</td>
                <td>{row.updated}</td>
                <td><button className="text-button inline-action" onClick={() => onAction(row.action)}>{row.action}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ActiveSimulationPanel({ onOpen }: { onOpen: () => void }) {
  const [paused, setPaused] = useState(false);
  return (
    <section className="dashboard-panel active-simulation" aria-labelledby="active-sim-title">
      <div className="panel-heading">
        <div>
          <h2 id="active-sim-title">Simulasi Berjalan</h2>
          <p>Registrasi Digital UMKM</p>
        </div>
        <span className="status-badge">{paused ? "Dijeda" : "Berjalan"}</span>
      </div>
      <div className="simulation-summary">
        <div><span>Ronde</span><b>3 dari 5</b></div>
        <div><span>Persona selesai</span><b>16 dari 20 persona</b></div>
        <div><span>Risiko narasi</span><b>Sedang</b></div>
        <div><span>Estimasi selesai</span><b>± 2 menit</b></div>
      </div>
      <div className="dashboard-progress"><span style={{ width: paused ? "60%" : "60%" }} /></div>
      <div className="simulation-visual">
        <svg viewBox="0 0 320 140" aria-hidden="true">
          <path d="M42 72 L115 38 L168 78 L252 42 M115 38 L128 112 L168 78 L258 110 M168 78 L292 74" />
          <circle cx="42" cy="72" r="8" /><circle cx="115" cy="38" r="10" /><circle cx="128" cy="112" r="8" /><circle cx="168" cy="78" r="13" /><circle cx="252" cy="42" r="9" /><circle cx="258" cy="110" r="9" /><circle cx="292" cy="74" r="8" />
        </svg>
        <ol>
          <li>Rina mengajukan pertanyaan mengenai biaya pendaftaran.</li>
          <li>Budi membagikan klarifikasi dari Dinas Koperasi.</li>
          <li>Narasi 'registrasi akan berbayar' meningkat.</li>
        </ol>
      </div>
      <div className="actions">
        <button className="button primary" onClick={onOpen}>Buka Simulasi</button>
        <button className="button secondary" onClick={() => setPaused(!paused)}>{paused ? "Lanjutkan" : "Jeda"}</button>
      </div>
    </section>
  );
}

function ProjectsTable({ onAction }: { onAction: (label: string) => void }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Semua status");
  const filtered = useMemo(() => recentProjects.filter((project) => {
    const matchesQuery = `${project[0]} ${project[1]}`.toLowerCase().includes(query.toLowerCase());
    const matchesStatus = status === "Semua status" || project[2] === status;
    return matchesQuery && matchesStatus;
  }), [query, status]);

  return (
    <section className="dashboard-panel span-2" aria-labelledby="projects-title">
      <div className="panel-heading">
        <h2 id="projects-title">Proyek Terbaru</h2>
        <button className="text-button inline-action" onClick={() => onAction("Lihat semua proyek")}>Lihat semua proyek</button>
      </div>
      <div className="project-tools">
        <label>Cari proyek<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari nama atau institusi" /></label>
        <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}>{projectStatuses.map((item) => <option key={item}>{item}</option>)}</select></label>
      </div>
      {filtered.length === 0 ? (
        <div className="state-block"><h3>Tidak ada proyek yang sesuai.</h3><p>Ubah kata kunci atau filter status untuk melihat proyek lain.</p></div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Nama proyek</th><th>Institusi</th><th>Status</th><th>Skenario</th><th>Risiko tertinggi</th><th>Terakhir diperbarui</th><th>Aksi</th></tr></thead>
            <tbody>
              {filtered.map((project) => (
                <tr key={project[0]}>
                  <td>{project[0]}</td><td>{project[1]}</td><td>{project[2]}</td><td>{project[3]}</td><td><RiskLabel value={project[4]} /></td><td>{project[5]}</td>
                  <td><button className="text-button inline-action" onClick={() => onAction(project[6])}>{project[6]}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ActivityTimeline() {
  return (
    <section className="dashboard-panel" aria-labelledby="activity-title">
      <div className="panel-heading"><h2 id="activity-title">Aktivitas Terbaru</h2></div>
      <ol className="activity-timeline">
        {recentActivity.map(([actor, text, time]) => (
          <li key={text}><span>{actor}</span><p>{text}</p><small>{time}</small></li>
        ))}
      </ol>
    </section>
  );
}

function ToastRegion({ toast }: { toast: Toast | null }) {
  return <div className="toast-region" aria-live="polite">{toast && <div className="toast">{toast.message}</div>}</div>;
}

export default function Dashboard() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const showToast = (message: string) => {
    setToast({ id: Date.now(), message });
    window.setTimeout(() => setToast(null), 3200);
  };
  const action = (label: string) => navigatePlaceholder(`/dashboard/${label.toLowerCase().replaceAll(" ", "-")}`, showToast);

  return (
    <div id="dashboard" className="dashboard-page">
      <header className="header">
        <div className="shell nav-wrap">
          <a
            className="brand"
            href="/"
            aria-label="RekaKebijakan, kembali ke beranda"
            onClick={(e) => {
              e.preventDefault();
              window.history.pushState(null, "", "/");
              window.dispatchEvent(new PopStateEvent('popstate'));
            }}
          >
            <span aria-hidden="true">RK</span>
            <b>RekaKebijakan</b>
          </a>
          <nav className="desktop-nav dashboard-nav" aria-label="Navigasi dashboard">
            <a className="active" href="/dashboard" onClick={(e) => e.preventDefault()}>Dashboard</a>
            <a
              href="/"
              onClick={(e) => {
                e.preventDefault();
                window.history.pushState(null, "", "/");
                window.dispatchEvent(new PopStateEvent('popstate'));
              }}
            >
              Beranda
            </a>
          </nav>
        </div>
      </header>
      <main className="dashboard-main shell">
        <section className="dashboard-hero" aria-labelledby="dashboard-title">
          <div><p className="eyebrow">RINGKASAN KERJA</p><h1 id="dashboard-title">Dashboard</h1><p>Pantau proyek kebijakan, simulasi, dan temuan yang memerlukan peninjauan.</p></div>
          <div className="actions"><button className="button primary" onClick={() => setDialogOpen(true)}>Buat Proyek</button><button className="button secondary" onClick={() => action("Lihat Semua Proyek")}>Lihat Semua Proyek</button></div>
        </section>
        <section className="metrics-grid" aria-label="Ringkasan metrik">{overviewMetrics.map((metric) => <MetricCard metric={metric} key={metric[0]} />)}</section>
        <div className="dashboard-grid">
          <AttentionList onAction={action} />
          <ActiveSimulationPanel onOpen={() => action("Buka Simulasi")} />
          <ProjectsTable onAction={action} />
          <ActivityTimeline />
        </div>
      </main>
      {dialogOpen && <CreateProjectDialog onClose={() => setDialogOpen(false)} />}
      <ToastRegion toast={toast} />
    </div>
  );
}
