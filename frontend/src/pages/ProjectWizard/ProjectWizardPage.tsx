import { useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell/AppShell";
import "./ProjectWizard.css";

const steps = [
  "Informasi Proyek",
  "Masukkan Kebijakan",
  "Bingkai Isu Kebijakan",
  "Tinjau Stakeholder & Persona",
  "Konfigurasi Skenario",
  "Tinjau & Jalankan",
] as const;

const stakeholderGroups = [
  "Pelaku UMKM mikro",
  "Pelaku UMKM kecil",
  "Dinas koperasi dan UMKM",
  "Penyedia platform digital",
  "Pendamping UMKM",
  "Konsumen lokal",
];

const initialExtracted = [
  ["Tujuan kebijakan", "Meningkatkan akurasi data UMKM dan mempercepat layanan perizinan digital."],
  ["Kewajiban baru", "Pelaku UMKM mendaftarkan usaha melalui kanal digital dalam masa transisi."],
  ["Kelompok terdampak awal", "Pelaku mikro, pelaku kecil, pendamping UMKM, dinas pengampu, dan platform digital."],
  ["Risiko awal", "Kesenjangan literasi digital, kekhawatiran biaya, dan narasi kewajiban administratif baru."],
  ["Indikator keberhasilan", "Tingkat registrasi, kebutuhan pendampingan, waktu layanan, dan indikasi risiko narasi."],
] as const;

const initialFraming: Record<string, string[]> = {
  "Tujuan kebijakan": ["Menyatukan data UMKM untuk layanan publik yang lebih terukur."],
  "Pasal/ketentuan penting": ["Kewajiban registrasi digital selama masa transisi.", "Pendaftaran tidak dikenakan biaya."],
  "Kelompok terdampak": ["Pelaku UMKM mikro", "Pelaku UMKM kecil", "Pendamping UMKM"],
  "Potensi manfaat": ["Akses layanan lebih cepat.", "Data bantuan dan pembinaan lebih rapi."],
  "Potensi keberatan": ["Keterbatasan perangkat dan literasi digital.", "Kekhawatiran biaya tambahan."],
  "Risiko narasi": ["Kebijakan dipersepsikan sebagai izin baru yang memberatkan."],
  "Indikator evaluasi": ["Jumlah pendaftar", "Jumlah permintaan pendampingan", "Kejelasan pemahaman kewajiban"],
};

type WizardPersona = {
  id: string;
  name: string;
  segment: string;
  concern: string;
  influence: "Rendah" | "Sedang" | "Tinggi";
  stance: string;
  active: boolean;
};

const initialPersonas: WizardPersona[] = [
  { id: "siti", name: "Siti Rahma", segment: "Pelaku UMKM mikro", concern: "Akses pendampingan tatap muka", influence: "Sedang", stance: "Cenderung mendukung jika dibantu", active: true },
  { id: "budi", name: "Budi Santoso", segment: "Pelaku UMKM kecil", concern: "Waktu administrasi dan kepastian biaya", influence: "Tinggi", stance: "Menunggu klarifikasi", active: true },
  { id: "ratna", name: "Ratna Lestari", segment: "Pendamping UMKM", concern: "Beban edukasi dan materi sosialisasi", influence: "Tinggi", stance: "Mendukung dengan syarat", active: true },
  { id: "agus", name: "Agus Wirawan", segment: "Dinas koperasi dan UMKM", concern: "Kesiapan kanal layanan", influence: "Tinggi", stance: "Mendukung", active: true },
  { id: "maya", name: "Maya Putri", segment: "Penyedia platform digital", concern: "Integrasi data dan dukungan teknis", influence: "Sedang", stance: "Mendukung terbatas", active: true },
  { id: "tono", name: "Tono Hidayat", segment: "Konsumen lokal", concern: "Kepercayaan pada usaha terdaftar", influence: "Rendah", stance: "Netral", active: true },
];

type WizardState = {
  projectName: string;
  institution: string;
  domain: string;
  region: string;
  period: string;
  purpose: string;
  question: string;
  processed: boolean;
  manualPolicy: string;
  framing: Record<string, string[]>;
  personaCount: "20" | "30" | "50";
  personas: WizardPersona[];
  scenario: "Rancangan awal" | "Skenario revisi";
  rounds: "3" | "5" | "8";
  mode: "Demo deterministik" | "Cached LLM" | "Live LLM";
  outreach: "Rendah" | "Sedang" | "Tinggi";
  response: "Diam" | "Klarifikasi" | "Revisi kebijakan";
  channels: string[];
  focus: string[];
  acknowledged: boolean;
};

const initialState: WizardState = {
  projectName: "Registrasi Digital UMKM",
  institution: "Dinas Koperasi dan UMKM",
  domain: "Transformasi digital layanan publik",
  region: "Kota Bandung",
  period: "2026-2027",
  purpose: "Menguji asumsi implementasi registrasi digital UMKM sebelum konsultasi publik.",
  question: "Bagaimana respons pelaku UMKM terhadap kewajiban registrasi digital?",
  processed: false,
  manualPolicy: "",
  framing: initialFraming,
  personaCount: "20",
  personas: initialPersonas,
  scenario: "Rancangan awal",
  rounds: "5",
  mode: "Demo deterministik",
  outreach: "Sedang",
  response: "Klarifikasi",
  channels: ["Forum publik"],
  focus: ["Dukungan", "kekhawatiran", "risiko narasi"],
  acknowledged: false,
};

function navigate(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function TextField({
  label,
  value,
  onChange,
  textarea = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  textarea?: boolean;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {textarea ? (
        <textarea rows={4} value={value} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function OptionGroup({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string;
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="wizard-option-group">
      <legend>{legend}</legend>
      {options.map((option) => (
        <label className="radio-row" key={option}>
          <input type="radio" checked={value === option} onChange={() => onChange(option)} />
          <span>{option}</span>
        </label>
      ))}
    </fieldset>
  );
}

function MultiCheck({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string;
  options: string[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const toggle = (option: string) =>
    onChange(value.includes(option) ? value.filter((item) => item !== option) : [...value, option]);
  return (
    <fieldset className="wizard-option-group">
      <legend>{legend}</legend>
      {options.map((option) => (
        <label className="checkbox-row" key={option}>
          <input type="checkbox" checked={value.includes(option)} onChange={() => toggle(option)} />
          <span>{option}</span>
        </label>
      ))}
    </fieldset>
  );
}

function SummaryPanel({
  state,
  complete,
  mobile = false,
}: {
  state: WizardState;
  complete: number;
  mobile?: boolean;
}) {
  return (
    <aside className={`wizard-summary ${mobile ? "mobile" : ""}`} aria-label="Ringkasan proyek">
      <p className="eyebrow">RINGKASAN</p>
      <dl>
        <div><dt>Nama proyek</dt><dd>{state.projectName || "Belum diisi"}</dd></div>
        <div><dt>Domain</dt><dd>{state.domain || "Belum diisi"}</dd></div>
        <div><dt>Wilayah</dt><dd>{state.region || "Belum diisi"}</dd></div>
        <div><dt>Jumlah persona</dt><dd>{state.personaCount} persona sintetis</dd></div>
        <div><dt>Jumlah ronde</dt><dd>{state.rounds} ronde</dd></div>
        <div><dt>Mode simulasi</dt><dd>{state.mode}</dd></div>
        <div><dt>Status kelengkapan</dt><dd>{complete} dari {steps.length} langkah</dd></div>
      </dl>
      <div className="summary-tags">
        {state.focus.map((tag) => <span key={tag}>{tag}</span>)}
      </div>
    </aside>
  );
}

export default function ProjectWizardPage() {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(initialState);
  const [launched, setLaunched] = useState(false);
  const [notice, setNotice] = useState("");
  const [editingPersona, setEditingPersona] = useState<WizardPersona | null>(null);
  const dirty = !launched;
  const setField = <K extends keyof WizardState>(key: K, value: WizardState[K]) =>
    setState((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const valid = [
    [state.projectName, state.institution, state.domain, state.region, state.period, state.purpose, state.question].every((item) => item.trim()),
    state.processed || state.manualPolicy.trim().length > 0,
    Object.values(state.framing).every((items) => items.some((item) => item.trim())),
    Number(state.personaCount) >= 20 && state.personas.length > 0,
    Boolean(state.scenario && state.rounds && state.mode && state.outreach && state.response && state.channels.length && state.focus.length),
    state.acknowledged,
  ];
  const complete = valid.filter(Boolean).length;

  const confirmExit = (path: string) => {
    if (!dirty || window.confirm("Perubahan belum disimpan. Tinggalkan wizard?")) {
      navigate(path);
    }
  };

  const addFramingItem = (category: string) => {
    setState((current) => ({
      ...current,
      framing: { ...current.framing, [category]: [...current.framing[category], ""] },
    }));
  };
  const updateFramingItem = (category: string, index: number, value: string) => {
    setState((current) => ({
      ...current,
      framing: {
        ...current.framing,
        [category]: current.framing[category].map((item, itemIndex) => itemIndex === index ? value : item),
      },
    }));
  };
  const removeFramingItem = (category: string, index: number) => {
    setState((current) => ({
      ...current,
      framing: {
        ...current.framing,
        [category]: current.framing[category].filter((_, itemIndex) => itemIndex !== index),
      },
    }));
  };
  const activeManagedPersonas = state.personas.filter((persona) => persona.active).length;
  const savePersona = () => {
    if (!editingPersona) return;
    setState((current) => ({
      ...current,
      personas: current.personas.map((persona) => persona.id === editingPersona.id ? editingPersona : persona),
    }));
    setEditingPersona(null);
  };
  const addPersona = () => {
    const persona: WizardPersona = {
      id: `persona-${Date.now()}`,
      name: "Persona sintetis baru",
      segment: "Pelaku UMKM mikro",
      concern: "Membutuhkan kejelasan informasi kebijakan.",
      influence: "Sedang",
      stance: "Netral",
      active: true,
    };
    setState((current) => ({ ...current, personas: [persona, ...current.personas] }));
    setEditingPersona(persona);
  };
  const deletePersona = (id: string) => {
    setState((current) => ({ ...current, personas: current.personas.filter((persona) => persona.id !== id) }));
    if (editingPersona?.id === id) setEditingPersona(null);
  };
  const togglePersona = (id: string) => {
    setState((current) => ({
      ...current,
      personas: current.personas.map((persona) => persona.id === id ? { ...persona, active: !persona.active } : persona),
    }));
  };

  const estimate = useMemo(() => {
    if (state.mode === "Live LLM") return `${state.rounds} ronde · biaya tinggi · latensi sedang`;
    if (state.mode === "Cached LLM") return `${state.rounds} ronde · biaya terkendali · latensi rendah`;
    return `${state.rounds} ronde · tanpa biaya model · latensi rendah`;
  }, [state.mode, state.rounds]);

  if (launched) {
    return (
      <AppShell
        title="Simulasi mock disiapkan"
        subtitle="Konfigurasi lokal telah disusun. Belum ada integrasi backend pada prototipe ini."
        eyebrow="Proyek baru"
        actions={<button className="button secondary" onClick={() => navigate("/projects")}>Kembali ke daftar proyek</button>}
      >
        <section className="dashboard-panel wizard-success" aria-live="polite">
          <p className="eyebrow">DUKUNGAN KEPUTUSAN</p>
          <h2>{state.projectName}</h2>
          <p>
            Simulasi skenario siap dijalankan sebagai ruang kerja mock. Hasil akan diperlakukan sebagai
            indikasi risiko dan bahan peninjauan, bukan pengganti konsultasi publik.
          </p>
          <div className="wizard-review-grid">
            {["simulation events", "risk narrative analysis", "evidence-linked report"].map((item) => (
              <article key={item}><span>Output</span><b>{item}</b></article>
            ))}
          </div>
          <div className="actions">
            <button className="button primary" onClick={() => navigate("/projects/registrasi-digital-umkm")}>Buka detail simulasi</button>
            <button className="button secondary" onClick={() => navigate("/projects")}>Kembali ke daftar proyek</button>
          </div>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Buat Proyek Kebijakan"
      subtitle="Susun asumsi, skenario, persona sintetis, dan jejak bukti sebelum simulasi dijalankan."
      eyebrow="Wizard proyek"
      actions={<button className="button secondary" onClick={() => confirmExit("/projects")}>Kembali ke daftar proyek</button>}
    >
      <section className="wizard-shell">
        <nav className="wizard-steps" aria-label="Langkah pembuatan proyek">
          {steps.map((label, index) => (
            <button
              key={label}
              className={step === index ? "active" : ""}
              aria-current={step === index ? "step" : undefined}
              onClick={() => {
                if (index <= step || valid[step]) setStep(index);
              }}
              disabled={index > step && !valid[step]}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              {label}
            </button>
          ))}
        </nav>
        <div className="wizard-progress" aria-hidden="true"><span style={{ width: `${((step + 1) / steps.length) * 100}%` }} /></div>
        <div className="wizard-layout">
          <div className="wizard-main">
            <section className="dashboard-panel wizard-panel" aria-labelledby="wizard-step-title">
              <p className="eyebrow">LANGKAH {step + 1} DARI {steps.length}</p>
              <h2 id="wizard-step-title">{steps[step]}</h2>
              {step === 0 && (
                <div className="wizard-form-grid">
                  <TextField label="Nama proyek" value={state.projectName} onChange={(value) => setField("projectName", value)} />
                  <TextField label="Instansi/tim" value={state.institution} onChange={(value) => setField("institution", value)} />
                  <TextField label="Domain kebijakan" value={state.domain} onChange={(value) => setField("domain", value)} />
                  <TextField label="Wilayah implementasi" value={state.region} onChange={(value) => setField("region", value)} />
                  <TextField label="Periode kebijakan" value={state.period} onChange={(value) => setField("period", value)} />
                  <TextField label="Pertanyaan analisis utama" value={state.question} onChange={(value) => setField("question", value)} />
                  <div className="span-2"><TextField textarea label="Ringkasan tujuan kebijakan" value={state.purpose} onChange={(value) => setField("purpose", value)} /></div>
                </div>
              )}
              {step === 1 && (
                <div className="wizard-stack">
                  <div className="mock-upload">
                    <p className="eyebrow">UNGGAH MOCK</p>
                    <h3>Draft regulasi, policy brief, atau dataset pendukung</h3>
                    <p>Jenis berkas diterima: PDF, DOCX, CSV, XLSX.</p>
                    <button className="button primary" onClick={() => setField("processed", true)}>Proses dokumen mock</button>
                  </div>
                  <TextField textarea label="Input manual kebijakan" value={state.manualPolicy} onChange={(value) => setField("manualPolicy", value)} />
                  {state.processed && (
                    <div className="extracted-grid">
                      {initialExtracted.map(([label, value]) => <article key={label}><span>{label}</span><p>{value}</p></article>)}
                    </div>
                  )}
                </div>
              )}
              {step === 2 && (
                <div className="wizard-stack">
                  <div className="inline-alert"><p>Asumsi kebijakan ditinjau manusia sebelum simulasi. Ubah, tambah, atau hapus item yang belum tepat.</p></div>
                  <div className="framing-list">
                    {Object.entries(state.framing).map(([category, items]) => (
                      <article className="framing-card" key={category}>
                        <div className="framing-heading"><h3>{category}</h3><button className="text-button" onClick={() => addFramingItem(category)}>Tambah</button></div>
                        {items.map((item, index) => (
                          <div className="framing-row" key={`${category}-${index}`}>
                            <input value={item} onChange={(event) => updateFramingItem(category, index, event.target.value)} aria-label={`${category} ${index + 1}`} />
                            <button className="kebab-button" onClick={() => removeFramingItem(category, index)} aria-label={`Hapus ${category} ${index + 1}`}>×</button>
                          </div>
                        ))}
                      </article>
                    ))}
                  </div>
                </div>
              )}
              {step === 3 && (
                <div className="wizard-stack">
                  <div className="stakeholder-grid">{stakeholderGroups.map((group) => <span key={group}>{group}</span>)}</div>
                  <OptionGroup legend="Jumlah persona sintetis" options={["20", "30", "50"]} value={state.personaCount} onChange={(value) => setField("personaCount", value as WizardState["personaCount"])} />
                  <p className="demo-note">Minimum direkomendasikan: 20 persona. Persona bersifat sintetis dan digunakan untuk simulasi skenario, bukan profil warga nyata.</p>
                  {activeManagedPersonas === 0 && <div className="inline-alert warning"><p>Setidaknya satu contoh persona perlu aktif untuk meninjau asumsi skenario.</p></div>}
                  <div className="persona-manager-toolbar">
                    <div>
                      <b>{activeManagedPersonas} dari {state.personas.length}</b>
                      <span>contoh persona aktif</span>
                    </div>
                    <button className="button primary" onClick={addPersona}>Tambah persona sintetis</button>
                  </div>
                  <div className="persona-review-grid">
                    {state.personas.map((persona) => (
                      <article className={!persona.active ? "persona-card disabled" : "persona-card"} key={persona.id}>
                        <label className="switch-row">
                          <input
                            type="checkbox"
                            checked={persona.active}
                            onChange={() => togglePersona(persona.id)}
                          />
                          <span>{persona.name}</span>
                        </label>
                        <dl>
                          <div><dt>Segmen</dt><dd>{persona.segment}</dd></div>
                          <div><dt>Kekhawatiran</dt><dd>{persona.concern}</dd></div>
                          <div><dt>Pengaruh</dt><dd>{persona.influence}</dd></div>
                          <div><dt>Kecenderungan</dt><dd>{persona.stance}</dd></div>
                        </dl>
                        <div className="persona-card-actions">
                          <button className="text-button inline-action" onClick={() => setEditingPersona({ ...persona })}>Edit</button>
                          <button className="text-button inline-action" onClick={() => deletePersona(persona.id)}>Hapus</button>
                        </div>
                      </article>
                    ))}
                  </div>
                  {editingPersona && (
                    <div className="persona-editor" aria-label="Editor persona sintetis">
                      <div className="framing-heading"><h3>Edit persona</h3><button className="text-button" onClick={() => setEditingPersona(null)}>Tutup</button></div>
                      <div className="wizard-form-grid">
                        <TextField label="Nama persona" value={editingPersona.name} onChange={(value) => setEditingPersona({ ...editingPersona, name: value })} />
                        <label className="field"><span>Kelompok stakeholder</span><select value={editingPersona.segment} onChange={(event) => setEditingPersona({ ...editingPersona, segment: event.target.value })}>{stakeholderGroups.map((group) => <option key={group}>{group}</option>)}</select></label>
                        <TextField label="Kekhawatiran" value={editingPersona.concern} onChange={(value) => setEditingPersona({ ...editingPersona, concern: value })} />
                        <label className="field"><span>Tingkat pengaruh</span><select value={editingPersona.influence} onChange={(event) => setEditingPersona({ ...editingPersona, influence: event.target.value as WizardPersona["influence"] })}>{["Rendah", "Sedang", "Tinggi"].map((item) => <option key={item}>{item}</option>)}</select></label>
                        <TextField label="Kecenderungan sikap" value={editingPersona.stance} onChange={(value) => setEditingPersona({ ...editingPersona, stance: value })} />
                        <label className="switch-row persona-editor-switch"><input type="checkbox" checked={editingPersona.active} onChange={(event) => setEditingPersona({ ...editingPersona, active: event.target.checked })} /><span>Status aktif</span></label>
                      </div>
                      <div className="wizard-actions compact">
                        <button className="button primary" onClick={savePersona}>Simpan perubahan</button>
                        <button className="button secondary" onClick={() => setEditingPersona(null)}>Batalkan</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {step === 4 && (
                <div className="wizard-stack">
                  <div className="wizard-config-grid">
                    <OptionGroup legend="Skenario" options={["Rancangan awal", "Skenario revisi"]} value={state.scenario} onChange={(value) => setField("scenario", value as WizardState["scenario"])} />
                    <OptionGroup legend="Jumlah ronde" options={["3", "5", "8"]} value={state.rounds} onChange={(value) => setField("rounds", value as WizardState["rounds"])} />
                    <OptionGroup legend="Mode simulasi" options={["Demo deterministik", "Cached LLM", "Live LLM"]} value={state.mode} onChange={(value) => setField("mode", value as WizardState["mode"])} />
                    <OptionGroup legend="Tingkat sosialisasi" options={["Rendah", "Sedang", "Tinggi"]} value={state.outreach} onChange={(value) => setField("outreach", value as WizardState["outreach"])} />
                    <OptionGroup legend="Respons pemerintah" options={["Diam", "Klarifikasi", "Revisi kebijakan"]} value={state.response} onChange={(value) => setField("response", value as WizardState["response"])} />
                    <MultiCheck legend="Saluran reaksi" options={["Forum publik", "media sosial", "konsultasi daerah"]} value={state.channels} onChange={(value) => setField("channels", value)} />
                    <MultiCheck legend="Fokus analisis" options={["Dukungan", "kekhawatiran", "risiko narasi", "dampak tidak langsung"]} value={state.focus} onChange={(value) => setField("focus", value)} />
                  </div>
                  <div className="scenario-preview">
                    <article><span>Baseline</span><b>Rancangan awal</b><p>Sosialisasi rendah, respons lambat, indikasi risiko narasi lebih tinggi.</p></article>
                    <article><span>Revisi</span><b>{state.scenario}</b><p>Sosialisasi {state.outreach.toLowerCase()}, respons {state.response.toLowerCase()}, fokus pada {state.focus.join(", ")}.</p></article>
                  </div>
                </div>
              )}
              {step === 5 && (
                <div className="wizard-stack">
                  <div className="wizard-review-grid">
                    <article><span>Informasi proyek</span><b>{state.projectName}</b><p>{state.domain} · {state.region}</p></article>
                    <article><span>Kelengkapan framing</span><b>{Object.keys(state.framing).length} kategori</b><p>Asumsi dan indikator siap ditinjau.</p></article>
                    <article><span>Stakeholder/persona</span><b>{state.personaCount} persona sintetis</b><p>{activeManagedPersonas} contoh aktif · {stakeholderGroups.length} kelompok stakeholder.</p></article>
                    <article><span>Pengaturan skenario</span><b>{state.scenario}</b><p>{state.rounds} ronde · {state.mode}</p></article>
                    <article><span>Estimasi biaya/latensi</span><b>{estimate}</b><p>Indikator lokal untuk prototipe.</p></article>
                    <article><span>Output</span><b>Event, analisis risiko, laporan</b><p>Jejak bukti disiapkan untuk dukungan keputusan.</p></article>
                  </div>
                  <label className="checkbox-row acknowledgement">
                    <input type="checkbox" checked={state.acknowledged} onChange={(event) => setField("acknowledged", event.target.checked)} />
                    <span>Saya memahami bahwa hasil simulasi adalah alat bantu analisis skenario dan tidak menggantikan konsultasi publik.</span>
                  </label>
                </div>
              )}
              {notice && <div className="inline-alert wizard-notice"><p>{notice}</p></div>}
              <SummaryPanel state={state} complete={complete} mobile />
              <div className="wizard-actions">
                <button className="button secondary" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Kembali</button>
                <button className="button secondary" onClick={() => setNotice("Draft disimpan secara lokal untuk sesi prototipe ini.")}>Simpan sebagai draft</button>
                {step < steps.length - 1 ? (
                  <button className="button primary" disabled={!valid[step]} onClick={() => setStep(step + 1)}>Berikutnya</button>
                ) : (
                  <button className="button primary" disabled={!valid[step]} onClick={() => setLaunched(true)}>Jalankan simulasi</button>
                )}
              </div>
              <p className="sr-only" aria-live="polite">{notice || (valid[step] ? "Langkah siap dilanjutkan." : "Lengkapi bidang wajib pada langkah ini.")}</p>
            </section>
          </div>
          <SummaryPanel state={state} complete={complete} />
        </div>
      </section>
    </AppShell>
  );
}
