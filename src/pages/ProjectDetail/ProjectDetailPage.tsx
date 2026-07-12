import { useId, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell/AppShell";
import "./ProjectDetail.css";

const project = {
  name: "Registrasi Digital UMKM",
  status: "Persiapan",
  domain: "Transformasi digital layanan publik",
  region: "Kota Bandung",
  institution: "Dinas Koperasi dan UMKM",
  period: "2026",
  question: "Bagaimana respons pelaku UMKM terhadap kewajiban registrasi digital?",
  mode: "Demo deterministik",
  personas: 30,
  rounds: 5,
  focus: ["Dukungan", "kekhawatiran", "risiko narasi", "dampak tidak langsung"],
};

const initialReadiness = [
  ["info", "Informasi proyek lengkap", true],
  ["docs", "Dokumen kebijakan tersedia", true],
  ["framing", "Bingkai isu ditinjau", true],
  ["stakeholders", "Stakeholder diverifikasi", true],
  ["personas", "Persona sintetis dipilih", true],
  ["scenario", "Skenario dikonfigurasi", false],
] as const;

const documents: Array<[string, string, string, string]> = [
  ["Draft Peraturan Registrasi Digital UMKM.pdf", "PDF", "Hari ini", "Selesai diproses"],
  ["Data UMKM Kota Bandung.csv", "CSV", "Hari ini", "Terverifikasi"],
  ["Ringkasan Program Digitalisasi UMKM.docx", "DOCX", "Kemarin", "Selesai diproses"],
];

const framing = [
  ["Tujuan kebijakan", "Meningkatkan akurasi data UMKM dan mempercepat layanan publik berbasis digital."],
  ["Kewajiban baru", "Pelaku UMKM melakukan registrasi digital melalui kanal resmi selama periode transisi."],
  ["Kelompok terdampak", "Pelaku UMKM mikro, UMKM kecil, pendamping UMKM, dinas pengampu, dan platform digital."],
  ["Potensi manfaat", "Data bantuan lebih rapi, layanan lebih cepat, dan proses pembinaan lebih terarah."],
  ["Potensi keberatan", "Keterbatasan perangkat, literasi digital, waktu administrasi, dan kekhawatiran biaya."],
  ["Risiko narasi awal", "Registrasi dapat dipersepsikan sebagai izin baru yang membebani pelaku usaha kecil."],
  ["Indikator keberhasilan", "Tingkat registrasi, kebutuhan pendampingan, waktu layanan, dan indikasi risiko narasi."],
] as const;

const stakeholders = [
  "Pelaku UMKM mikro",
  "Pelaku UMKM kecil",
  "Dinas koperasi dan UMKM",
  "Penyedia platform digital",
  "Pendamping UMKM",
  "Konsumen lokal",
];

const scenarioRows = [
  ["Skenario utama", "Rancangan awal"],
  ["Skenario pembanding", "Skenario revisi"],
  ["Tingkat sosialisasi", "Sedang"],
  ["Respons pemerintah", "Klarifikasi"],
  ["Saluran reaksi", "Forum publik, media sosial, konsultasi daerah"],
  ["Jumlah ronde", "5"],
  ["Fokus analisis", "Dukungan, kekhawatiran, risiko narasi, dampak tidak langsung"],
] as const;


type ReadinessItem = {
  id: string;
  label: string;
  checked: boolean;
};

type Notice = {
  id: number;
  message: string;
} | null;

function navigate(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function StatusBadge() {
  return <span className="project-badge project-status project-status-persiapan"><i aria-hidden="true" />Persiapan</span>;
}

function NoticeRegion({ notice }: { notice: Notice }) {
  return <div className="toast-region" aria-live="polite">{notice && <div className="toast">{notice.message}</div>}</div>;
}

function ReadinessPanel({
  items,
  score,
  missing,
  onToggle,
  onLaunch,
  mobile = false,
}: {
  items: ReadinessItem[];
  score: number;
  missing: ReadinessItem[];
  onToggle: (id: string) => void;
  onLaunch: () => void;
  mobile?: boolean;
}) {
  return (
    <aside className={`workspace-side-panel ${mobile ? "mobile" : ""}`} aria-label="Kesiapan simulasi">
      <p className="eyebrow">KESIAPAN SIMULASI</p>
      <div className="readiness-score">
        <strong>{score}%</strong>
        <span>Kesiapan simulasi</span>
      </div>
      <div className="progress-bar" aria-hidden="true"><span style={{ width: `${score}%` }} /></div>
      <div className="readiness-list">
        {items.map((item) => (
          <label className="checkbox-row" key={item.id}>
            <input type="checkbox" checked={item.checked} onChange={() => onToggle(item.id)} />
            <span>{item.label}</span>
          </label>
        ))}
      </div>
      <div className="workspace-side-meta">
        <div><span>Item belum lengkap</span><b>{missing.length ? missing.map((item) => item.label).join(", ") : "Tidak ada"}</b></div>
        <div><span>Estimasi runtime</span><b>5 ronde · sekitar 2 menit</b></div>
        <div><span>Mode biaya</span><b>Rendah · demo deterministik</b></div>
      </div>
      <div className="output-list">
        <span>Output</span>
        <p>event simulasi</p>
        <p>analisis risiko narasi</p>
        <p>laporan berbasis bukti</p>
      </div>
      <button className="button primary run" onClick={onLaunch}>Jalankan simulasi</button>
    </aside>
  );
}

function LaunchModal({
  readinessComplete,
  missing,
  onCancel,
  onConfirm,
}: {
  readinessComplete: boolean;
  missing: ReadinessItem[];
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  return (
    <div className="dialog-backdrop" onMouseDown={onCancel}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={(event) => event.stopPropagation()}>
        <button className="dialog-close" onClick={onCancel} aria-label="Tutup dialog">X</button>
        <p className="eyebrow">KONFIRMASI SIMULASI</p>
        <h2 id={titleId}>Jalankan simulasi skenario?</h2>
        {!readinessComplete && (
          <div className="inline-alert warning">
            <p>Masih ada item kesiapan yang belum lengkap: {missing.map((item) => item.label).join(", ")}.</p>
          </div>
        )}
        <p className="dialog-copy">
          Hasil simulasi adalah alat bantu analisis skenario dan tidak menggantikan konsultasi publik.
        </p>
        <div className="actions">
          <button className="button primary" onClick={onConfirm}>Jalankan simulasi</button>
          <button className="button secondary" onClick={onCancel}>Batal</button>
        </div>
      </section>
    </div>
  );
}

export default function ProjectDetailPage() {
  const [readiness, setReadiness] = useState<ReadinessItem[]>(
    initialReadiness.map(([id, label, checked]) => ({ id, label, checked })),
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const checkedCount = readiness.filter((item) => item.checked).length;
  const score = Math.round((checkedCount / readiness.length) * 100);
  const missing = readiness.filter((item) => !item.checked);
  const readinessComplete = missing.length === 0;
  const metadata = useMemo(
    () => [
      ["Domain", project.domain],
      ["Wilayah", project.region],
      ["Instansi", project.institution],
      ["Periode", project.period],
      ["Mode simulasi", project.mode],
      ["Persona aktif", `${project.personas} persona sintetis`],
      ["Jumlah ronde", `${project.rounds} ronde`],
      ["Fokus analisis", project.focus.join(", ")],
    ],
    [],
  );
  const showNotice = (message: string) => {
    setNotice({ id: Date.now(), message });
    window.setTimeout(() => setNotice(null), 2800);
  };
  const toggleReadiness = (id: string) => {
    setReadiness((items) => items.map((item) => item.id === id ? { ...item, checked: !item.checked } : item));
  };

  return (
    <AppShell
      title={project.name}
      subtitle="Ruang kerja untuk meninjau asumsi, dokumen, persona sintetis, dan skenario sebelum simulasi dijalankan."
      eyebrow="Workspace kebijakan"
      actions={
        <>
          <button className="button primary" onClick={() => setModalOpen(true)}>Jalankan simulasi</button>
          <button className="button secondary" onClick={() => navigate("/projects/registrasi-digital-umkm/scenarios")}>Ubah skenario</button>
          <button className="button ghost" onClick={() => showNotice("Draft proyek disimpan secara lokal dalam sesi prototipe.")}>Simpan draft</button>
          <button className="button ghost" onClick={() => showNotice("Duplikasi proyek tersedia sebagai aksi mock.")}>Duplikasi proyek</button>
          <button className="button ghost" onClick={() => showNotice("Arsip proyek tersedia sebagai aksi mock.")}>Arsipkan</button>
        </>
      }
    >
      <section className="workspace-top" aria-label="Ringkasan workspace">
        <div>
          <div className="workspace-breadcrumb">Proyek Kebijakan / Registrasi Digital UMKM</div>
          <div className="workspace-title-row">
            <StatusBadge />
            <span>Mode simulasi: {project.mode}</span>
          </div>
          <p>{project.question}</p>
        </div>
        <ReadinessPanel items={readiness} score={score} missing={missing} onToggle={toggleReadiness} onLaunch={() => setModalOpen(true)} mobile />
      </section>
      <section className="workspace-layout">
        <div className="workspace-main">
          <section className="dashboard-panel workspace-panel" aria-labelledby="summary-title">
            <div className="panel-heading"><div><h2 id="summary-title">Ringkasan Proyek</h2><p>Metadata utama untuk dukungan keputusan skenario.</p></div></div>
            <div className="workspace-card-grid">
              {metadata.map(([label, value]) => <article key={label}><span>{label}</span><b>{value}</b></article>)}
            </div>
          </section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="docs-title">
            <div className="panel-heading"><div><h2 id="docs-title">Dokumen Kebijakan</h2><p>Berkas mock yang menjadi dasar jejak bukti.</p></div></div>
            {documents.length === 0 ? (
              <div className="state-block"><h3>Belum ada dokumen</h3><p>Unggah draft regulasi, policy brief, atau dataset pendukung.</p></div>
            ) : (
              <div className="workspace-table-wrap">
                <table className="data-table workspace-table">
                  <thead><tr><th>Dokumen</th><th>Tipe</th><th>Diunggah</th><th>Status</th><th>Aksi</th></tr></thead>
                  <tbody>
                    {documents.map(([name, type, date, status]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>{type}</td>
                        <td>{date}</td>
                        <td><span className="project-badge project-risk-rendah"><i aria-hidden="true" />{status}</span></td>
                        <td><div className="row-actions"><button onClick={() => showNotice(`Membuka ${name}.`)}>Lihat</button><button onClick={() => showNotice(`Mengganti ${name}.`)}>Ganti</button><button onClick={() => showNotice(`Menghapus ${name}.`)}>Hapus</button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="framing-title">
            <div className="panel-heading"><div><h2 id="framing-title">Bingkai Isu Kebijakan</h2><p>Asumsi ditinjau manusia sebelum simulasi skenario.</p></div><button className="text-button inline-action" onClick={() => showNotice("Edit bingkai isu tersedia sebagai aksi mock.")}>Edit bingkai isu</button></div>
            <div className="workspace-row-list">
              {framing.map(([label, value]) => <article key={label}><span>{label}</span><p>{value}</p></article>)}
            </div>
          </section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="persona-title">
            <div className="panel-heading"><div><h2 id="persona-title">Stakeholder & Persona</h2><p>Kelompok terdampak dan persona sintetis untuk simulasi terbatas.</p></div><button className="text-button inline-action" onClick={() => navigate("/projects/registrasi-digital-umkm/personas")}>Tinjau persona</button></div>
            <div className="stakeholder-grid">{stakeholders.map((item) => <span key={item}>{item}</span>)}</div>
            <div className="workspace-card-grid persona-summary">
              <article><span>Persona aktif</span><b>30 persona aktif</b></article>
              <article><span>Kelompok stakeholder</span><b>6 kelompok stakeholder</b></article>
              <article><span>Distribusi pengaruh</span><b>Rendah 8 · Sedang 14 · Tinggi 8</b></article>
              <article><span>Kecenderungan sikap</span><b>Dukung 12 · Netral 9 · Khawatir 9</b></article>
            </div>
            <p className="demo-note">Persona bersifat sintetis dan digunakan untuk simulasi skenario, bukan profil warga nyata.</p>
          </section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="scenario-title">
            <div className="panel-heading"><div><h2 id="scenario-title">Skenario Simulasi</h2><p>Konfigurasi skenario untuk melihat indikasi risiko dan perubahan respons.</p></div><button className="text-button inline-action" onClick={() => navigate("/projects/registrasi-digital-umkm/scenarios")}>Ubah skenario</button></div>
            <div className="workspace-row-list two-column">
              {scenarioRows.map(([label, value]) => <article key={label}><span>{label}</span><p>{value}</p></article>)}
            </div>
          </section>

        </div>
        <ReadinessPanel items={readiness} score={score} missing={missing} onToggle={toggleReadiness} onLaunch={() => setModalOpen(true)} />
      </section>
      {modalOpen && <LaunchModal readinessComplete={readinessComplete} missing={missing} onCancel={() => setModalOpen(false)} onConfirm={() => navigate("/simulations/registrasi-digital-umkm")} />}
      <NoticeRegion notice={notice} />
    </AppShell>
  );
}
