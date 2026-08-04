import { useEffect, useId, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell/AppShell";
import { useCompareScenarios, useCreateRun, useCreateScenario, useProject, useScenarios, useUpdateScenario } from "../../api/queries";
import type { ApiScenario } from "../../api/client";
import "./ScenarioBuilder.css";

type Outreach = "Rendah" | "Sedang" | "Tinggi";
type Response = "Diam" | "Klarifikasi" | "Revisi kebijakan";
type ScenarioConfig = {
  name: string;
  description: string;
  outreach: Outreach;
  response: Response;
  rounds: number;
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
  rounds: 10,
  channels: ["Media sosial", "Forum publik"],
  focus: ["Kekhawatiran", "Risiko narasi", "Dampak tidak langsung"],
  assumptions: "Registrasi diwajibkan tanpa masa transisi yang panjang.",
};

const revisedDefault: ScenarioConfig = {
  name: "Skenario revisi",
  description: "Rancangan diperbaiki dengan klarifikasi perlindungan data, bantuan pendampingan, dan sosialisasi bertahap.",
  outreach: "Tinggi",
  response: "Klarifikasi",
  rounds: 10,
  channels: ["Forum publik", "Konsultasi daerah", "Komunitas UMKM"],
  focus: ["Dukungan", "Kekhawatiran", "Kebutuhan informasi"],
  assumptions: "Pemerintah menyediakan pendampingan, penjelasan perlindungan data, dan kanal bantuan.",
};

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
        <label>Jumlah ronde simulasi<input type="number" min={1} max={1000} value={scenario.rounds} onChange={(event) => onChange({ ...scenario, rounds: Number(event.target.value) })} /></label>
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
  const navigate = useNavigate();
  const { projectId = "", scenarioId } = useParams<{ projectId: string; scenarioId?: string }>();
  const projectQuery = useProject(projectId);
  const scenariosQuery = useScenarios(projectId);
  const createMutation = useCreateScenario(projectId);
  const updateBaseline = useUpdateScenario(projectId, scenarioId ?? scenariosQuery.data?.items[0]?.id ?? "");
  const updateRevised = useUpdateScenario(projectId, scenariosQuery.data?.items.find((item) => item.id !== (scenarioId ?? scenariosQuery.data?.items[0]?.id))?.id ?? "");
  const compareMutation = useCompareScenarios(projectId);
  const [baseline, setBaseline] = useState<ScenarioConfig>(baselineDefault);
  const [revised, setRevised] = useState<ScenarioConfig>(revisedDefault);
  const [activeTab, setActiveTab] = useState<"baseline" | "revised">("baseline");
  const [notice, setNotice] = useState<Notice>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [loadedIds, setLoadedIds] = useState<string[]>([]);
  const selectedScenarios = scenariosQuery.data?.items ?? [];
  const firstScenario = selectedScenarios.find((item) => item.id === scenarioId) ?? selectedScenarios[0];
  const secondScenario = selectedScenarios.find((item) => item.id !== firstScenario?.id);
  const activePersonas = projectQuery.data?.snapshot.environment?.persona_count ?? projectQuery.data?.snapshot.environment?.personas?.length ?? 0;
  const runMutation = useCreateRun(projectId, secondScenario?.id ?? firstScenario?.id ?? "");
  const fromApi = (scenario: ApiScenario, fallback: ScenarioConfig): ScenarioConfig => ({
    ...fallback, name: scenario.name, description: scenario.description,
    outreach: (scenario.config.socialization as Outreach) ?? fallback.outreach,
    response: (scenario.config.response_mode as Response) ?? fallback.response,
    rounds: Number(scenario.config.rounds ?? fallback.rounds),
    channels: (scenario.config.channels as string[]) ?? fallback.channels,
    focus: (scenario.config.focus as string[]) ?? fallback.focus,
    assumptions: (scenario.config.assumptions as string) ?? fallback.assumptions,
  });
  useEffect(() => {
    const ids = [firstScenario?.id, secondScenario?.id].filter(Boolean) as string[];
    if (!firstScenario || ids.join() === loadedIds.join()) return;
    const timer = window.setTimeout(() => {
      setBaseline(fromApi(firstScenario, baselineDefault));
      if (secondScenario) setRevised(fromApi(secondScenario, revisedDefault));
      setLoadedIds(ids);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [firstScenario, loadedIds, secondScenario]);
  const showNotice = (message: string) => {
    setNotice({ id: Date.now(), message });
    window.setTimeout(() => setNotice(null), 2800);
  };
  const readiness = [
    ["Kedua skenario memiliki nama", Boolean(baseline.name.trim() && revised.name.trim())],
    ["Minimal satu saluran reaksi dipilih", baseline.channels.length > 0 && revised.channels.length > 0],
    ["Minimal satu fokus analisis dipilih", baseline.focus.length > 0 && revised.focus.length > 0],
    ["Jumlah ronde valid", [baseline.rounds, revised.rounds].every((rounds) => Number.isInteger(rounds) && rounds >= 1 && rounds <= 1000)],
    ["Asumsi tambahan ditinjau", Boolean(baseline.assumptions.trim() && revised.assumptions.trim())],
  ] as const;
  const ready = readiness.every(([, value]) => value);
  const combinedFocus = useMemo(() => Array.from(new Set([...baseline.focus, ...revised.focus])).join(", "), [baseline.focus, revised.focus]);
  const maxRounds = Math.max(Number(baseline.rounds), Number(revised.rounds));
  const payload = (value: ScenarioConfig) => ({ name: value.name, description: value.description, config: { socialization: value.outreach, response_mode: value.response, rounds: Number(value.rounds), channels: value.channels, focus: value.focus, assumptions: value.assumptions } });
  const save = async () => {
    try {
      const baselineResult = firstScenario
        ? updateBaseline.mutateAsync({ ...payload(baseline), expected_version: firstScenario.version })
        : createMutation.mutateAsync({ ...payload(baseline), kind: "baseline" });
      const revisedResult = secondScenario
        ? updateRevised.mutateAsync({ ...payload(revised), expected_version: secondScenario.version })
        : createMutation.mutateAsync({ ...payload(revised), kind: "revision" });
      await Promise.all([baselineResult, revisedResult]);
      showNotice("Skenario tersimpan di workspace.");
    } catch { showNotice("Skenario tidak dapat disimpan. Muat ulang jika versi telah berubah."); }
  };
  const run = async () => {
    const scenario = secondScenario ?? firstScenario;
    if (!scenario) return;
    try { const created = await runMutation.mutateAsync(scenario.version); navigate(`/runs/${created.id}`); }
    catch { showNotice("Simulasi tidak dapat dimulai."); setModalOpen(false); }
  };

  if (projectQuery.isError) {
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
      actions={<><button className="button primary" disabled={createMutation.isPending || updateBaseline.isPending || updateRevised.isPending} onClick={save}>Simpan skenario</button><button className="button secondary" onClick={() => navigate(`/projects/${projectId}`)}>Kembali ke workspace</button></>}
    >
      <section className="scenario-top" aria-label="Ringkasan pembuat skenario">
        <div className="workspace-breadcrumb">Proyek Kebijakan / {projectQuery.data?.name ?? "Memuat proyek"} / Skenario</div>
        <div className="workspace-title-row"><StatusBadge /><span>{projectQuery.data?.institution}</span></div>
        <p>{projectQuery.data?.snapshot.project?.question ?? projectQuery.data?.objective}</p>
        <div className="inline-alert scenario-notice"><p>Skenario adalah asumsi kerja untuk membantu analisis kebijakan. Hasil simulasi tidak menggantikan konsultasi publik atau keputusan manusia.</p></div>
      </section>
      <section className="scenario-summary-bar" aria-label="Konfigurasi bersama">
        <article><span>Persona aktif</span><b>{activePersonas}</b></article>
        <article><span>Stakeholder</span><b>{new Set(projectQuery.data?.snapshot.environment?.personas?.map((persona) => persona.group) ?? []).size} kelompok</b></article>
        <article><span>Mode simulasi</span><b>Run API v1</b></article>
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
             <button className="button primary" onClick={save}>Simpan skenario</button>
             <button className="button ghost" disabled={!firstScenario || !secondScenario || compareMutation.isPending} onClick={async () => { try { const result = await compareMutation.mutateAsync([firstScenario!.id, secondScenario!.id]); showNotice(`${result.differences.length} perbedaan skenario ditemukan.`); } catch { showNotice("Perbandingan tidak dapat dimuat."); } }}>Bandingkan dari server</button>
            <button className="button secondary" disabled={!ready || activePersonas === 0} onClick={() => setModalOpen(true)}>Jalankan simulasi</button>
             <button className="button ghost" onClick={() => navigate(`/projects/${projectId}`)}>Kembali ke workspace</button>
          </div>
        </aside>
      </section>
      {modalOpen && <ConfirmModal onCancel={() => setModalOpen(false)} onConfirm={run} />}
      <NoticeRegion notice={notice} />
    </AppShell>
  );
}
