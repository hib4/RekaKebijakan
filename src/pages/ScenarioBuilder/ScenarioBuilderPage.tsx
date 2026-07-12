import { useId, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell/AppShell";
import "./ScenarioBuilder.css";

type Outreach = "Rendah" | "Sedang" | "Tinggi";
type Response = "Diam" | "Klarifikasi" | "Revisi kebijakan";
type Rounds = "3" | "5" | "8";
type ScenarioConfig = {
  name: string;
  description: string;
  outreach: Outreach;
  response: Response;
  rounds: Rounds;
  channels: string[];
  focus: string[];
  assumptions: string;
};
type Notice = { id: number; message: string } | null;

const channelOptions = ["Forum publik", "Media sosial", "Konsultasi daerah", "Kanal pengaduan", "Komunitas UMKM"];
const focusOptions = ["Dukungan", "Kekhawatiran", "Risiko narasi", "Dampak tidak langsung", "Kebutuhan informasi"];

const baselineDefault: ScenarioConfig = {
  name: "Rancangan awal",
  description: "Kewajiban registrasi digital diberlakukan sesuai rancangan awal tanpa penyesuaian tambahan.",
  outreach: "Rendah",
  response: "Diam",
  rounds: "5",
  channels: ["Media sosial", "Forum publik"],
  focus: ["Kekhawatiran", "Risiko narasi", "Dampak tidak langsung"],
  assumptions: "Registrasi diwajibkan tanpa masa transisi yang panjang.",
};

const revisedDefault: ScenarioConfig = {
  name: "Skenario revisi",
  description: "Rancangan diperbaiki dengan klarifikasi perlindungan data, bantuan pendampingan, dan sosialisasi bertahap.",
  outreach: "Tinggi",
  response: "Klarifikasi",
  rounds: "5",
  channels: ["Forum publik", "Konsultasi daerah", "Komunitas UMKM"],
  focus: ["Dukungan", "Kekhawatiran", "Kebutuhan informasi"],
  assumptions: "Pemerintah menyediakan pendampingan, penjelasan perlindungan data, dan kanal bantuan.",
};

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

function ChipGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const toggle = (item: string) => onChange(value.includes(item) ? value.filter((entry) => entry !== item) : [...value, item]);
  return (
    <fieldset className="scenario-chip-group">
      <legend>{label}</legend>
      <div>
        {options.map((item) => (
          <button type="button" className={value.includes(item) ? "selected" : ""} key={item} onClick={() => toggle(item)}>
            {item}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function ScenarioCard({
  title,
  scenario,
  onChange,
  actions,
}: {
  title: string;
  scenario: ScenarioConfig;
  onChange: (scenario: ScenarioConfig) => void;
  actions?: React.ReactNode;
}) {
  return (
    <article className="scenario-card">
      <div className="scenario-card-heading">
        <div><p className="eyebrow">{title}</p><h2>{scenario.name}</h2></div>
        {actions && <div className="scenario-card-actions">{actions}</div>}
      </div>
      <label>Nama skenario<input value={scenario.name} onChange={(event) => onChange({ ...scenario, name: event.target.value })} /></label>
      <label>Ringkasan perubahan<textarea rows={3} value={scenario.description} onChange={(event) => onChange({ ...scenario, description: event.target.value })} /></label>
      <div className="scenario-form-grid">
        <label>Tingkat sosialisasi<select value={scenario.outreach} onChange={(event) => onChange({ ...scenario, outreach: event.target.value as Outreach })}>{["Rendah", "Sedang", "Tinggi"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Respons pemerintah<select value={scenario.response} onChange={(event) => onChange({ ...scenario, response: event.target.value as Response })}>{["Diam", "Klarifikasi", "Revisi kebijakan"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Jumlah ronde simulasi<select value={scenario.rounds} onChange={(event) => onChange({ ...scenario, rounds: event.target.value as Rounds })}>{["3", "5", "8"].map((item) => <option key={item}>{item}</option>)}</select></label>
      </div>
      <ChipGroup label="Saluran reaksi" options={channelOptions} value={scenario.channels} onChange={(channels) => onChange({ ...scenario, channels })} />
      <ChipGroup label="Fokus analisis" options={focusOptions} value={scenario.focus} onChange={(focus) => onChange({ ...scenario, focus })} />
      <label>Asumsi tambahan<textarea rows={4} value={scenario.assumptions} onChange={(event) => onChange({ ...scenario, assumptions: event.target.value })} /></label>
    </article>
  );
}

function ConfirmModal({ onCancel, onConfirm }: { onCancel: () => void; onConfirm: () => void }) {
  const titleId = useId();
  return (
    <div className="dialog-backdrop" onMouseDown={onCancel}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={(event) => event.stopPropagation()}>
        <button className="dialog-close" onClick={onCancel} aria-label="Tutup dialog">X</button>
        <p className="eyebrow">KONFIRMASI SIMULASI</p>
        <h2 id={titleId}>Jalankan simulasi skenario?</h2>
        <p className="dialog-copy">
          Simulasi akan menggunakan persona sintetis dan asumsi skenario yang telah ditinjau. Hasilnya digunakan sebagai dukungan analisis, bukan prediksi pasti terhadap masyarakat.
        </p>
        <div className="actions">
          <button className="button primary" onClick={onConfirm}>Jalankan simulasi</button>
          <button className="button secondary" onClick={onCancel}>Batal</button>
        </div>
      </section>
    </div>
  );
}

export default function ScenarioBuilderPage() {
  const projectFound = true;
  const activePersonas: number = 30;
  const [baseline, setBaseline] = useState<ScenarioConfig>(baselineDefault);
  const [revised, setRevised] = useState<ScenarioConfig>(revisedDefault);
  const [activeTab, setActiveTab] = useState<"baseline" | "revised">("baseline");
  const [notice, setNotice] = useState<Notice>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const showNotice = (message: string) => {
    setNotice({ id: Date.now(), message });
    window.setTimeout(() => setNotice(null), 2800);
  };
  const readiness = [
    ["Kedua skenario memiliki nama", Boolean(baseline.name.trim() && revised.name.trim())],
    ["Minimal satu saluran reaksi dipilih", baseline.channels.length > 0 && revised.channels.length > 0],
    ["Minimal satu fokus analisis dipilih", baseline.focus.length > 0 && revised.focus.length > 0],
    ["Jumlah ronde dipilih", Boolean(baseline.rounds && revised.rounds)],
    ["Asumsi tambahan ditinjau", Boolean(baseline.assumptions.trim() && revised.assumptions.trim())],
  ] as const;
  const ready = readiness.every(([, value]) => value);
  const combinedFocus = useMemo(() => Array.from(new Set([...baseline.focus, ...revised.focus])).join(", "), [baseline.focus, revised.focus]);
  const maxRounds = Math.max(Number(baseline.rounds), Number(revised.rounds));

  if (!projectFound) {
    return (
      <AppShell title="Data proyek tidak ditemukan" subtitle="Ruang kerja skenario tidak dapat dibuka." eyebrow="Skenario">
        <section className="dashboard-panel state-block"><h2>Data proyek tidak ditemukan.</h2><button className="button primary" onClick={() => navigate("/projects")}>Kembali ke daftar proyek</button></section>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Scenario Builder"
      subtitle="Bandingkan rancangan awal dan skenario revisi sebelum simulasi dijalankan."
      eyebrow="Workspace kebijakan"
      actions={<><button className="button primary" onClick={() => showNotice("Skenario disimpan secara lokal untuk sesi prototipe.")}>Simpan skenario</button><button className="button secondary" onClick={() => navigate("/projects/registrasi-digital-umkm")}>Kembali ke workspace</button></>}
    >
      <section className="scenario-top" aria-label="Ringkasan pembuat skenario">
        <div className="workspace-breadcrumb">Proyek Kebijakan / Registrasi Digital UMKM / Skenario</div>
        <div className="workspace-title-row"><StatusBadge /><span>Transformasi digital layanan publik · Kota Bandung</span></div>
        <p>Bagaimana respons pelaku UMKM terhadap kewajiban registrasi digital?</p>
        <div className="inline-alert scenario-notice"><p>Skenario adalah asumsi kerja untuk membantu analisis kebijakan. Hasil simulasi tidak menggantikan konsultasi publik atau keputusan manusia.</p></div>
      </section>
      <section className="scenario-summary-bar" aria-label="Konfigurasi bersama">
        <article><span>Persona aktif</span><b>{activePersonas}</b></article>
        <article><span>Stakeholder</span><b>6 kelompok</b></article>
        <article><span>Mode simulasi</span><b>Demo deterministik</b></article>
        <article><span>Estimasi ronde</span><b>{maxRounds}</b></article>
        <article><span>Fokus analisis</span><b>{combinedFocus}</b></article>
      </section>
      {activePersonas === 0 && <div className="inline-alert error scenario-warning"><p>Belum ada persona aktif. Tinjau persona sebelum menjalankan simulasi.</p></div>}
      {activePersonas > 0 && activePersonas < 20 && <div className="inline-alert warning scenario-warning"><p>Jumlah persona aktif di bawah rekomendasi minimum untuk simulasi yang lebih representatif.</p></div>}
      <div className="scenario-mobile-tabs" role="tablist" aria-label="Pilih skenario">
        <button className={activeTab === "baseline" ? "active" : ""} onClick={() => setActiveTab("baseline")}>Rancangan awal</button>
        <button className={activeTab === "revised" ? "active" : ""} onClick={() => setActiveTab("revised")}>Skenario revisi</button>
      </div>
      <section className="scenario-builder-grid">
        <div className={activeTab === "baseline" ? "scenario-mobile-visible" : ""}>
          <ScenarioCard title="Rancangan awal" scenario={baseline} onChange={setBaseline} />
        </div>
        <div className={activeTab === "revised" ? "scenario-mobile-visible" : ""}>
          <ScenarioCard
            title="Skenario revisi"
            scenario={revised}
            onChange={setRevised}
            actions={<><button className="text-button inline-action" onClick={() => setRevised(revisedDefault)}>Reset skenario revisi</button><button className="text-button inline-action" onClick={() => setRevised({ ...baseline, name: "Skenario revisi" })}>Salin dari rancangan awal</button></>}
          />
        </div>
      </section>
      <section className="scenario-review-layout">
        <section className="dashboard-panel scenario-comparison" aria-labelledby="comparison-title">
          <div className="panel-heading"><div><h2 id="comparison-title">Ringkasan Perbandingan</h2><p>Perubahan asumsi skenario diperbarui langsung dari konfigurasi.</p></div></div>
          <div className="scenario-table-wrap">
            <table className="data-table">
              <thead><tr><th>Parameter</th><th>Rancangan awal</th><th>Skenario revisi</th></tr></thead>
              <tbody>
                <tr><td>Tingkat sosialisasi</td><td>{baseline.outreach}</td><td>{revised.outreach}</td></tr>
                <tr><td>Respons pemerintah</td><td>{baseline.response}</td><td>{revised.response}</td></tr>
                <tr><td>Jumlah ronde</td><td>{baseline.rounds}</td><td>{revised.rounds}</td></tr>
                <tr><td>Saluran reaksi</td><td>{baseline.channels.join(", ")}</td><td>{revised.channels.join(", ")}</td></tr>
                <tr><td>Fokus analisis</td><td>{baseline.focus.join(", ")}</td><td>{revised.focus.join(", ")}</td></tr>
                <tr><td>Potensi risiko utama</td><td>Kekhawatiran pajak dan data pribadi</td><td>Kesiapan pendampingan lapangan</td></tr>
                <tr><td>Perkiraan kebutuhan klarifikasi</td><td>Tinggi</td><td>Sedang</td></tr>
                <tr><td>Estimasi biaya simulasi</td><td>Rendah</td><td>Rendah</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <aside className="dashboard-panel scenario-readiness" aria-label="Kesiapan skenario">
          <p className="eyebrow">KESIAPAN SKENARIO</p>
          <h2>{ready ? "Siap disimpan" : "Perlu dilengkapi"}</h2>
          <div className="readiness-list">
            {readiness.map(([label, value]) => <label className="checkbox-row" key={label}><input type="checkbox" checked={value} readOnly /><span>{label}</span></label>)}
          </div>
          {!ready && <div className="inline-alert warning"><p>Lengkapi semua asumsi skenario sebelum simulasi terbatas dijalankan.</p></div>}
          <div className="scenario-actions">
            <button className="button primary" onClick={() => showNotice("Skenario disimpan secara lokal untuk sesi prototipe.")}>Simpan skenario</button>
            <button className="button secondary" disabled={!ready || activePersonas === 0} onClick={() => setModalOpen(true)}>Jalankan simulasi</button>
            <button className="button ghost" onClick={() => navigate("/projects/registrasi-digital-umkm")}>Kembali ke workspace</button>
          </div>
        </aside>
      </section>
      {modalOpen && <ConfirmModal onCancel={() => setModalOpen(false)} onConfirm={() => navigate("/projects/registrasi-digital-umkm/simulations/current")} />}
      <NoticeRegion notice={notice} />
    </AppShell>
  );
}
