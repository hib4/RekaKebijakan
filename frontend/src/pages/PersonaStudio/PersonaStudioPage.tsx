import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../../components/AppShell/AppShell";
import "./PersonaStudio.css";

// Demo-only prototype. This page intentionally has no application route.

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

const requiredExamples: Persona[] = [
  {
    id: "p-001",
    name: "Ibu Rani",
    group: "Pelaku UMKM mikro",
    profile: "Pemilik usaha makanan rumahan, terbiasa menjual lewat pesan instan.",
    motivation: "Menjaga pesanan tetap berjalan tanpa administrasi rumit.",
    concern: "Khawatir registrasi digital berkaitan dengan pajak tambahan.",
    needs: "Penjelasan biaya, manfaat, dan bantuan tatap muka.",
    stance: "Khawatir",
    influence: "Sedang",
    risk: "Tinggi",
    active: true,
    notes: "Asumsi skenario untuk pelaku mikro berliterasi digital sedang.",
  },
  {
    id: "p-002",
    name: "Pak Dedi",
    group: "Pelaku UMKM kecil",
    profile: "Pemilik toko kelontong yang mulai menggunakan pembayaran digital.",
    motivation: "Memastikan proses registrasi tidak mengganggu operasional.",
    concern: "Ingin proses registrasi sederhana dan tidak mengganggu operasional.",
    needs: "Panduan langkah dan batas waktu yang jelas.",
    stance: "Netral",
    influence: "Sedang",
    risk: "Sedang",
    active: true,
    notes: "Asumsi untuk usaha kecil yang sudah mengenal kanal digital.",
  },
  {
    id: "p-003",
    name: "Sari",
    group: "Pendamping UMKM",
    profile: "Pendamping lapangan yang membantu pelaku usaha mengakses program pemerintah.",
    motivation: "Membantu kelompok terdampak memahami kewajiban baru.",
    concern: "Membutuhkan materi sosialisasi dan kanal bantuan yang jelas.",
    needs: "Materi resmi, FAQ, dan eskalasi pertanyaan.",
    stance: "Mendukung",
    influence: "Tinggi",
    risk: "Rendah",
    active: true,
    notes: "Asumsi untuk penghubung lapangan dengan pengaruh tinggi.",
  },
  {
    id: "p-004",
    name: "Andika",
    group: "Penyedia platform digital",
    profile: "Perwakilan platform katalog UMKM lokal.",
    motivation: "Menjaga integrasi layanan tetap aman dan jelas.",
    concern: "Membutuhkan integrasi data yang aman dan standar teknis yang jelas.",
    needs: "Dokumentasi teknis dan batas penggunaan data.",
    stance: "Mendukung",
    influence: "Tinggi",
    risk: "Sedang",
    active: true,
    notes: "Asumsi untuk mitra teknologi dalam skenario revisi.",
  },
  {
    id: "p-005",
    name: "Bu Lina",
    group: "Konsumen lokal",
    profile: "Konsumen yang sering membeli dari UMKM sekitar.",
    motivation: "Mendapatkan produk lokal yang jelas dan terjangkau.",
    concern: "Ingin transparansi usaha tanpa membuat harga naik.",
    needs: "Informasi sederhana tentang manfaat registrasi.",
    stance: "Netral",
    influence: "Rendah",
    risk: "Rendah",
    active: false,
    notes: "Asumsi dampak tidak langsung pada konsumen lokal.",
  },
];

const names = ["Nina", "Hendra", "Wati", "Rizal", "Mira", "Arif", "Dewi", "Teguh", "Yuni", "Fajar", "Nanda", "Rika"];
const groupNames = groups.map(([name]) => name);
const stances: Stance[] = ["Mendukung", "Netral", "Khawatir", "Menolak"];
const levels: Level[] = ["Rendah", "Sedang", "Tinggi"];

const generatedPersonas: Persona[] = Array.from({ length: 37 }, (_, index) => {
  const group = groupNames[index % groupNames.length];
  const stance = stances[index % stances.length];
  const influence = levels[(index + 1) % levels.length];
  const risk = levels[(index + 2) % levels.length];
  return {
    id: `p-${String(index + 6).padStart(3, "0")}`,
    name: `${names[index % names.length]} ${index + 1}`,
    group,
    profile: `Persona sintetis dari ${group.toLowerCase()} untuk menguji asumsi skenario registrasi digital.`,
    motivation: "Memahami manfaat kebijakan tanpa menambah beban administrasi.",
    concern: "Membutuhkan kejelasan kewajiban, bantuan, dan konsekuensi implementasi.",
    needs: "Informasi resmi, kanal bantuan, dan contoh proses registrasi.",
    stance,
    influence,
    risk,
    active: index < 26,
    notes: "Catatan asumsi disusun untuk simulasi skenario, bukan identifikasi individu.",
  };
});

const initialPersonas = [...requiredExamples, ...generatedPersonas];

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
  const [personas, setPersonas] = useState<Persona[]>(initialPersonas);
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
  const saveDraft = () => {
    if (!draft) return;
    setPersonas((items) => items.map((item) => item.id === draft.id ? draft : item));
    setEditing(null);
    setDraft(null);
    showNotice("Perubahan persona disimpan.");
  };
  const toggleActive = (id: string) => {
    setPersonas((items) => items.map((item) => item.id === id ? { ...item, active: !item.active } : item));
  };
  const applyBulk = (active: boolean) => {
    setPersonas((items) => items.map((item) => selected.includes(item.id) ? { ...item, active } : item));
    setSelected([]);
    showNotice(active ? "Persona terpilih diaktifkan." : "Persona terpilih dinonaktifkan.");
  };
  const addPersona = () => {
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
    setPersonas((items) => [item, ...items]);
    openDrawer(item);
  };

  return (
    <AppShell
      title="Stakeholder & Persona"
      subtitle="Tinjau kelompok terdampak dan persona sintetis sebelum simulasi dijalankan."
      eyebrow="Workspace kebijakan"
      actions={
        <>
          <button className="button primary" onClick={() => showNotice("Perubahan stakeholder dan persona disimpan.")}>Simpan perubahan</button>
          <button className="button secondary" onClick={() => navigate("/projects/registrasi-digital-umkm")}>Kembali ke workspace</button>
        </>
      }
    >
      <section className="persona-top" aria-label="Ringkasan stakeholder dan persona">
        <div className="workspace-breadcrumb">Proyek Kebijakan / Registrasi Digital UMKM / Stakeholder & Persona</div>
        <div className="workspace-title-row"><StatusBadge /><span>Transformasi digital layanan publik · Kota Bandung</span></div>
        <div className="inline-alert persona-notice">
          <p>Persona bersifat sintetis dan digunakan untuk menguji skenario kebijakan. Persona bukan profil warga nyata dan tidak boleh digunakan untuk mengambil keputusan terhadap individu.</p>
        </div>
      </section>

      <section className="metrics-grid persona-metrics" aria-label="Ringkasan persona">
        <article className="metric-card"><p>Persona total</p><strong>42</strong><span>Asumsi skenario tersedia</span></article>
        <article className="metric-card"><p>Persona aktif</p><strong>{activeCount}</strong><span>Dipakai dalam simulasi</span></article>
        <article className="metric-card"><p>Kelompok stakeholder</p><strong>6</strong><span>Kelompok terdampak</span></article>
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
            <button className={selectedGroup === "Semua kelompok" ? "active" : ""} onClick={() => setSelectedGroup("Semua kelompok")}>Semua kelompok <span>42</span></button>
            {groups.map(([group, count]) => (
              <button className={selectedGroup === group ? "active" : ""} key={group} onClick={() => setSelectedGroup(group)}>{group} <span>{count}</span></button>
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
              <button className="button secondary" onClick={() => { setEditing(null); setDraft(null); }}>Batalkan</button>
            </div>
          </aside>
        </div>
      )}
      <NoticeRegion notice={notice} />
    </AppShell>
  );
}
