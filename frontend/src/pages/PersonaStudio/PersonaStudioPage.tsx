import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell/AppShell";
import { useBulkUpdatePersonas, useCreateCustomPersona, useEffectivePersonas, usePersonaOverride, useProject, useResetPersona, useScenario } from "../../api/queries";
import type { ApiEffectivePersona } from "../../api/client";
import "./PersonaStudio.css";

type Stance = "Mendukung" | "Netral" | "Khawatir" | "Menolak";
type Level = "Rendah" | "Sedang" | "Tinggi";
type Persona = {
  id: string;
  name: string;
  group: string;
  profile: string;
  motivation: string;
  concern: string;
  needs: string;
  stance: Stance;
  influence: Level;
  risk: Level;
  active: boolean;
  notes: string;
};

const groups = [
  ["Pelaku UMKM mikro", 10],
  ["Pelaku UMKM kecil", 8],
  ["Dinas koperasi dan UMKM", 5],
  ["Penyedia platform digital", 6],
  ["Pendamping UMKM", 7],
  ["Konsumen lokal", 6],
] as const;

const groupSummaries: Record<string, { description: string; concerns: string; friction: string; stance: Stance }> = {
  "Pelaku UMKM mikro": {
    description: "Pelaku usaha skala rumah tangga dengan kapasitas administrasi terbatas.",
    concerns: "Kewajiban digital, biaya tidak langsung, dan kebutuhan pendampingan.",
    friction: "Tinggi pada tahap awal sosialisasi.",
    stance: "Khawatir",
  },
  "Pelaku UMKM kecil": {
    description: "Usaha kecil yang mulai memakai pembayaran dan katalog digital.",
    concerns: "Kesederhanaan proses, waktu operasional, dan kepastian manfaat.",
    friction: "Sedang karena sebagian kanal digital sudah dikenal.",
    stance: "Netral",
  },
  "Dinas koperasi dan UMKM": {
    description: "Unit pelaksana yang mengelola sosialisasi dan layanan registrasi.",
    concerns: "Kesiapan kanal, dukungan teknis, dan validasi data.",
    friction: "Sedang pada koordinasi lintas unit.",
    stance: "Mendukung",
  },
  "Penyedia platform digital": {
    description: "Mitra teknologi yang berpotensi membantu kanal registrasi dan katalog.",
    concerns: "Standar integrasi, keamanan data, dan kepastian peran.",
    friction: "Sedang pada spesifikasi teknis.",
    stance: "Mendukung",
  },
  "Pendamping UMKM": {
    description: "Pendamping lapangan yang membantu pelaku usaha memahami program.",
    concerns: "Materi sosialisasi, kanal bantuan, dan beban pendampingan.",
    friction: "Sedang karena perlu materi yang konsisten.",
    stance: "Mendukung",
  },
  "Konsumen lokal": {
    description: "Pembeli lokal yang terdampak oleh perubahan kepercayaan dan harga.",
    concerns: "Transparansi usaha dan potensi kenaikan harga.",
    friction: "Rendah karena dampak tidak langsung.",
    stance: "Netral",
  },
};

const groupNames = groups.map(([name]) => name);
const stances: Stance[] = ["Mendukung", "Netral", "Khawatir", "Menolak"];
const levels: Level[] = ["Rendah", "Sedang", "Tinggi"];

type Notice = { id: number; message: string } | null;
type StatusFilter = "Semua" | "Aktif" | "Nonaktif";
type SortKey = "Pengaruh" | "Risiko narasi" | "Nama" | "Stakeholder";

function NoticeRegion({ notice }: { notice: Notice }) {
  return <div className="toast-region" aria-live="polite">{notice && <div className="toast">{notice.message}</div>}</div>;
}

function StatusBadge() {
  return <span className="project-badge project-status project-status-persiapan"><i aria-hidden="true" />Persiapan</span>;
}

const rank: Record<string, number> = { Rendah: 1, Sedang: 2, Tinggi: 3 };

export default function PersonaStudioPage() {
  const navigate = useNavigate();
  const { projectId = "", scenarioId = "" } = useParams<{ projectId: string; scenarioId: string }>();
  const projectQuery = useProject(projectId);
  const scenarioQuery = useScenario(projectId, scenarioId);
  const personasQuery = useEffectivePersonas(projectId, scenarioId);
  const overrideMutation = usePersonaOverride(projectId, scenarioId);
  const resetMutation = useResetPersona(projectId, scenarioId);
  const customMutation = useCreateCustomPersona(projectId, scenarioId);
  const bulkMutation = useBulkUpdatePersonas(projectId, scenarioId);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedGroup, setSelectedGroup] = useState("Semua kelompok");
  const [status, setStatus] = useState<StatusFilter>("Semua");
  const [stance, setStance] = useState("Semua");
  const [influence, setInfluence] = useState("Semua");
  const [risk, setRisk] = useState("Semua");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("Pengaruh");
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState<Persona | null>(null);
  const [draft, setDraft] = useState<Persona | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  useEffect(() => {
    if (!personasQuery.data) return;
    const mapped = personasQuery.data.items.map((item) => ({
      id: item.id, name: item.name ?? item.id, group: item.group ?? item.stakeholder_group ?? "Stakeholder",
      profile: item.profile ?? item.role ?? "Persona sintetis", motivation: item.motivation ?? "Memahami dampak kebijakan.",
      concern: item.concern ?? item.concerns?.join(", ") ?? "Belum ada kekhawatiran", needs: item.needs ?? "Informasi kebijakan",
      stance: (item.stance as Stance) ?? "Netral", influence: item.influence ?? "Sedang", risk: item.risk ?? "Sedang",
      active: item.active, notes: item.notes ?? "",
    }));
    const timer = window.setTimeout(() => setPersonas(mapped), 0);
    return () => window.clearTimeout(timer);
  }, [personasQuery.data]);

  const activeCount = personas.filter((persona) => persona.active).length;
  const showNotice = (message: string) => {
    setNotice({ id: Date.now(), message });
    window.setTimeout(() => setNotice(null), 2800);
  };
  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    const rows = personas.filter((persona) => {
      const matchesGroup = selectedGroup === "Semua kelompok" || persona.group === selectedGroup;
      const matchesStatus = status === "Semua" || (status === "Aktif" ? persona.active : !persona.active);
      const matchesStance = stance === "Semua" || persona.stance === stance;
      const matchesInfluence = influence === "Semua" || persona.influence === influence;
      const matchesRisk = risk === "Semua" || persona.risk === risk;
      const haystack = `${persona.name} ${persona.group} ${persona.profile} ${persona.concern}`.toLowerCase();
      return matchesGroup && matchesStatus && matchesStance && matchesInfluence && matchesRisk && (!text || haystack.includes(text));
    });
    return [...rows].sort((a, b) => {
      if (sort === "Nama") return a.name.localeCompare(b.name);
      if (sort === "Stakeholder") return a.group.localeCompare(b.group);
      if (sort === "Risiko narasi") return rank[b.risk] - rank[a.risk];
      return rank[b.influence] - rank[a.influence];
    });
  }, [influence, personas, query, risk, selectedGroup, sort, stance, status]);
  const selectedGroupSummary = selectedGroup === "Semua kelompok" ? null : groupSummaries[selectedGroup];
  const selectedGroupActive = personas.filter((persona) => persona.group === selectedGroup && persona.active).length;

  const openDrawer = (persona: Persona) => {
    setEditing(persona);
    setDraft({ ...persona });
  };
  const saveDraft = async () => {
    if (!draft) return;
    try {
      await overrideMutation.mutateAsync({ personaId: draft.id, expected_version: scenarioQuery.data?.version ?? 0, base_environment_revision: scenarioQuery.data?.base_environment_revision ?? 0, patch: { name: draft.name, group: draft.group, role: draft.profile, concern: draft.concern, stance: draft.stance } });
      setEditing(null); setDraft(null); showNotice("Perubahan persona disimpan.");
    } catch { showNotice("Persona tidak dapat disimpan. Versi skenario mungkin berubah."); }
  };
  const toggleActive = async (id: string) => {
    const persona = personas.find((item) => item.id === id);
    if (!persona) return;
    try { await bulkMutation.mutateAsync({ persona_ids: [id], patch: { active: !persona.active }, expected_version: scenarioQuery.data?.version ?? 0 }); }
    catch { showNotice("Status persona tidak dapat diperbarui."); }
  };
  const applyBulk = async (active: boolean) => {
    try { await bulkMutation.mutateAsync({ persona_ids: selected, patch: { active }, expected_version: scenarioQuery.data?.version ?? 0 }); setSelected([]); showNotice(active ? "Persona terpilih diaktifkan." : "Persona terpilih dinonaktifkan."); }
    catch { showNotice("Aksi massal tidak dapat diselesaikan."); }
  };
  const addPersona = async () => {
    const item: Persona = {
      id: `p-${Date.now()}`,
      name: "Persona sintetis baru",
      group: "Pelaku UMKM mikro",
      profile: "Persona sintetis tambahan untuk asumsi skenario registrasi digital.",
      motivation: "Memahami manfaat kebijakan.",
      concern: "Membutuhkan informasi implementasi yang jelas.",
      needs: "Panduan dan kanal bantuan.",
      stance: "Netral",
      influence: "Rendah",
      risk: "Sedang",
      active: false,
      notes: "Catatan asumsi belum ditinjau.",
    };
    try {
      const created = await customMutation.mutateAsync({ ...(item as Omit<ApiEffectivePersona, "id" | "source">), expected_version: scenarioQuery.data?.version ?? 0 });
      openDrawer({ ...item, id: created.id });
    } catch { showNotice("Persona kustom tidak dapat dibuat."); }
  };
  const resetPersona = async () => {
    if (!draft) return;
    try { await resetMutation.mutateAsync({ personaId: draft.id, expectedVersion: scenarioQuery.data?.version ?? 0 }); setEditing(null); setDraft(null); showNotice("Persona dikembalikan ke nilai lingkungan."); }
    catch { showNotice("Override persona tidak dapat direset."); }
  };

  return (
    <AppShell
      title="Stakeholder & Persona"
      subtitle="Tinjau kelompok terdampak dan persona sintetis sebelum simulasi dijalankan."
      eyebrow="Workspace kebijakan"
      actions={
        <>
          <button className="button primary" onClick={() => showNotice("Semua perubahan telah disimpan saat diedit.")}>Simpan perubahan</button>
          <button className="button secondary" onClick={() => navigate(`/projects/${projectId}`)}>Kembali ke workspace</button>
        </>
      }
    >
      <section className="persona-top" aria-label="Ringkasan stakeholder dan persona">
         <div className="workspace-breadcrumb">Proyek Kebijakan / {projectQuery.data?.name ?? "Memuat proyek"} / Stakeholder & Persona</div>
         <div className="workspace-title-row"><StatusBadge /><span>{projectQuery.data?.institution}</span></div>
        <div className="inline-alert persona-notice">
          <p>Persona bersifat sintetis dan digunakan untuk menguji skenario kebijakan. Persona bukan profil warga nyata dan tidak boleh digunakan untuk mengambil keputusan terhadap individu.</p>
        </div>
      </section>

      <section className="metrics-grid persona-metrics" aria-label="Ringkasan persona">
        <article className="metric-card"><p>Persona total</p><strong>{personas.length}</strong><span>Asumsi skenario tersedia</span></article>
        <article className="metric-card"><p>Persona aktif</p><strong>{activeCount}</strong><span>Dipakai dalam simulasi</span></article>
        <article className="metric-card"><p>Kelompok stakeholder</p><strong>{new Set(personas.map((persona) => persona.group)).size}</strong><span>Kelompok terdampak</span></article>
        <article className="metric-card"><p>Tingkat pengaruh</p><strong>3</strong><span>Rendah, sedang, tinggi</span></article>
      </section>
      {activeCount < 20 && (
        <div className="inline-alert warning persona-warning">
          <p>Jumlah persona aktif di bawah rekomendasi minimum untuk simulasi yang lebih representatif.</p>
        </div>
      )}
      {activeCount < 12 && (
        <div className="inline-alert error persona-warning">
          <p>Simulasi tidak dapat dijalankan dari studio ini karena persona aktif di bawah batas minimum operasional.</p>
        </div>
      )}

      <section className="persona-studio-layout">
        <aside className="persona-sidebar" aria-label="Filter persona">
          <section>
            <h2>Kelompok stakeholder</h2>
             <button className={selectedGroup === "Semua kelompok" ? "active" : ""} onClick={() => setSelectedGroup("Semua kelompok")}>Semua kelompok <span>{personas.length}</span></button>
             {[...new Set(personas.map((persona) => persona.group))].map((group) => (
               <button className={selectedGroup === group ? "active" : ""} key={group} onClick={() => setSelectedGroup(group)}>{group} <span>{personas.filter((persona) => persona.group === group).length}</span></button>
            ))}
          </section>
          <section className="persona-filter-stack">
            <h2>Filter</h2>
            <label>Status<select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}>{["Semua", "Aktif", "Nonaktif"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Kecenderungan sikap<select value={stance} onChange={(event) => setStance(event.target.value)}>{["Semua", "Mendukung", "Netral", "Khawatir", "Menolak"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Tingkat pengaruh<select value={influence} onChange={(event) => setInfluence(event.target.value)}>{["Semua", "Rendah", "Sedang", "Tinggi"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Risiko narasi<select value={risk} onChange={(event) => setRisk(event.target.value)}>{["Semua", "Rendah", "Sedang", "Tinggi"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Cari persona, segmen, atau kekhawatiran<input value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          </section>
        </aside>

        <main className="persona-main">
          {selectedGroupSummary && (
            <section className="dashboard-panel group-summary" aria-label={`Ringkasan ${selectedGroup}`}>
              <div><span>Deskripsi</span><p>{selectedGroupSummary.description}</p></div>
              <div><span>Kekhawatiran utama</span><p>{selectedGroupSummary.concerns}</p></div>
              <div><span>Gesekan kebijakan</span><p>{selectedGroupSummary.friction}</p></div>
              <div><span>Persona aktif</span><p>{selectedGroupActive}</p></div>
              <div><span>Kecenderungan dominan</span><p>{selectedGroupSummary.stance}</p></div>
            </section>
          )}

          <section className="dashboard-panel persona-list-panel" aria-labelledby="persona-table-title">
            <div className="panel-heading">
              <div>
                <h2 id="persona-table-title">Daftar Persona Sintetis</h2>
                <p>{filtered.length} persona sesuai filter</p>
              </div>
              <button className="button primary" onClick={addPersona}>Tambah persona sintetis</button>
            </div>
            <div className="persona-toolbar">
              <label className="persona-search">
                Cari
                <input placeholder="Cari nama, segmen, atau kekhawatiran..." value={query} onChange={(event) => setQuery(event.target.value)} />
              </label>
              <label>
                Urutkan
                <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
                  {["Pengaruh", "Risiko narasi", "Nama", "Stakeholder"].map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
              <div className="bulk-actions">
                <span>Pilihan:</span>
                <button className="button secondary" disabled={!selected.length} onClick={() => applyBulk(true)}>Aktifkan</button>
                <button className="button secondary" disabled={!selected.length} onClick={() => applyBulk(false)}>Nonaktifkan</button>
              </div>
            </div>
            {personas.length === 0 ? (
              <div className="state-block"><h3>Belum ada persona sintetis</h3><p>Tambahkan persona sintetis untuk menyusun asumsi skenario.</p><button className="button primary" onClick={addPersona}>Tambah persona sintetis</button></div>
            ) : filtered.length === 0 ? (
              <div className="state-block"><h3>Tidak ada persona yang sesuai dengan filter.</h3><p>Ubah filter atau kata kunci untuk melihat persona lain.</p></div>
            ) : (
              <div className="persona-table-wrap">
                <table className="data-table persona-table">
                  <thead>
                    <tr><th><span className="sr-only">Pilih</span></th><th>Nama</th><th>Kelompok</th><th>Profil</th><th>Kekhawatiran</th><th>Sikap</th><th>Pengaruh</th><th>Risiko</th><th>Status</th><th>Aksi</th></tr>
                  </thead>
                  <tbody>
                    {filtered.map((persona) => (
                      <tr key={persona.id}>
                        <td><input type="checkbox" checked={selected.includes(persona.id)} onChange={() => setSelected(selected.includes(persona.id) ? selected.filter((id) => id !== persona.id) : [...selected, persona.id])} aria-label={`Pilih ${persona.name}`} /></td>
                        <td><button className="project-name-button" onClick={() => openDrawer(persona)}>{persona.name}</button></td>
                        <td>{persona.group}</td>
                        <td>{persona.profile}</td>
                        <td>{persona.concern}</td>
                        <td>{persona.stance}</td>
                        <td>{persona.influence}</td>
                        <td>{persona.risk}</td>
                        <td><label className="switch-row compact"><input type="checkbox" checked={persona.active} onChange={() => toggleActive(persona.id)} /><span>{persona.active ? "Aktif" : "Nonaktif"}</span></label></td>
                        <td><button className="text-button inline-action" onClick={() => openDrawer(persona)}>Detail/Edit</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </main>
      </section>

      {editing && draft && (
        <div className="persona-drawer-backdrop" onMouseDown={() => { setEditing(null); setDraft(null); }}>
          <aside className="persona-drawer" aria-label={`Edit ${editing.name}`} onMouseDown={(event) => event.stopPropagation()}>
            <div className="drawer-heading">
              <div><p className="eyebrow">DETAIL PERSONA</p><h2>{editing.name}</h2></div>
              <button className="dialog-close" onClick={() => { setEditing(null); setDraft(null); }} aria-label="Tutup panel">X</button>
            </div>
            <div className="drawer-form">
              <label>Nama persona<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
              <label>Kelompok stakeholder<select value={draft.group} onChange={(event) => setDraft({ ...draft, group: event.target.value })}>{groupNames.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Profil singkat<textarea rows={3} value={draft.profile} onChange={(event) => setDraft({ ...draft, profile: event.target.value })} /></label>
              <label>Motivasi utama<textarea rows={2} value={draft.motivation} onChange={(event) => setDraft({ ...draft, motivation: event.target.value })} /></label>
              <label>Kekhawatiran utama<textarea rows={2} value={draft.concern} onChange={(event) => setDraft({ ...draft, concern: event.target.value })} /></label>
              <label>Kebutuhan informasi<textarea rows={2} value={draft.needs} onChange={(event) => setDraft({ ...draft, needs: event.target.value })} /></label>
              <label>Kecenderungan sikap<select value={draft.stance} onChange={(event) => setDraft({ ...draft, stance: event.target.value as Stance })}>{stances.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Tingkat pengaruh<select value={draft.influence} onChange={(event) => setDraft({ ...draft, influence: event.target.value as Level })}>{levels.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Risiko narasi<select value={draft.risk} onChange={(event) => setDraft({ ...draft, risk: event.target.value as Level })}>{levels.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label className="switch-row"><input type="checkbox" checked={draft.active} onChange={(event) => setDraft({ ...draft, active: event.target.checked })} /><span>Status aktif</span></label>
              <label>Catatan asumsi<textarea rows={3} value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} /></label>
            </div>
            <div className="drawer-actions">
              <button className="button primary" onClick={saveDraft}>Simpan perubahan</button>
              <button className="button ghost" disabled={resetMutation.isPending} onClick={resetPersona}>Reset ke persona efektif</button>
              <button className="button secondary" onClick={() => { setEditing(null); setDraft(null); }}>Batalkan</button>
            </div>
          </aside>
        </div>
      )}
      <NoticeRegion notice={notice} />
    </AppShell>
  );
}
