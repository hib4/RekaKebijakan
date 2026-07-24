import type { DemoCase, PolicyGraphEdge, ReportSection } from "./workflowTypes";

export const entityTypes = [
  "PolicyIssue",
  "Stakeholder",
  "Institution",
  "RegulationClause",
  "PublicConcern",
  "RiskNarrative",
  "PersonaGroup",
  "EvidenceSource",
];

export const relationTypes = [
  "AFFECTS",
  "SUPPORTS",
  "OPPOSES",
  "INFLUENCES",
  "RAISES_CONCERN",
  "MITIGATES",
  "REFERENCES",
  "IMPLEMENTED_BY",
];

export const graphColors: Record<string, string> = {
  PolicyIssue: "#0f62fe",
  Stakeholder: "#198038",
  Institution: "#6929c4",
  RegulationClause: "#005d5d",
  PublicConcern: "#b28600",
  RiskNarrative: "#da1e28",
  PersonaGroup: "#8a3ffc",
  EvidenceSource: "#525252",
};

const fertilizerEdges: PolicyGraphEdge[] = [
  { id: "e1", source: "issue", target: "petani", type: "AFFECTS" },
  { id: "e2", source: "issue", target: "kios", type: "IMPLEMENTED_BY" },
  { id: "e3", source: "kios", target: "distributor", type: "INFLUENCES" },
  { id: "e4", source: "distributor", target: "ministry", type: "REFERENCES" },
  { id: "e5", source: "ministry", target: "clause", type: "IMPLEMENTED_BY" },
  { id: "e6", source: "petani", target: "concern", type: "RAISES_CONCERN" },
  { id: "e7", source: "concern", target: "risk", type: "INFLUENCES" },
  { id: "e8", source: "extension", target: "risk", type: "MITIGATES" },
  { id: "e9", source: "farmer-group", target: "petani", type: "SUPPORTS" },
  { id: "e10", source: "evidence", target: "issue", type: "REFERENCES" },
  { id: "e11", source: "extension", target: "farmer-group", type: "INFLUENCES" },
];

const reportSections: ReportSection[] = [
  {
    id: "executive",
    title: "Ringkasan Eksekutif",
    content: [
      "Simulasi menunjukkan bahwa kepastian jadwal, transparansi stok, dan akses klarifikasi menjadi penentu utama respons stakeholder.",
      "Indikasi risiko tertinggi muncul ketika perubahan mekanisme penyaluran dipahami sebagai pembatasan akses tanpa masa transisi yang jelas.",
    ],
  },
  {
    id: "response",
    title: "Pergeseran Respons Stakeholder",
    content: [
      "Kelompok petani bergerak dari sikap khawatir menuju netral setelah penyuluh menjelaskan jadwal penyaluran dan mekanisme pengaduan.",
      "Kios resmi dan distributor tetap netral, dengan perhatian pada sinkronisasi data dan kepastian waktu pengiriman.",
    ],
  },
  {
    id: "narrative",
    title: "Risiko Narasi Utama",
    content: [
      "Narasi bahwa pupuk akan semakin sulit diakses menyebar paling cepat di Forum Publik pada ronde kedua.",
      "Risiko meningkat ketika informasi stok tidak disertai sumber dan jadwal pembaruan yang dapat ditelusuri.",
    ],
  },
  {
    id: "indirect",
    title: "Dampak Tidak Langsung",
    content: [
      "Ketidakpastian penyaluran mendorong penundaan keputusan tanam dan meningkatkan beban klarifikasi pada penyuluh lapangan.",
      "Kelompok tani berpotensi menjadi penghubung informasi, tetapi juga mempercepat penyebaran narasi risiko jika tidak mendapat pembaruan resmi.",
    ],
  },
  {
    id: "recommendation",
    title: "Rekomendasi Kebijakan",
    content: [
      "Publikasikan jadwal penyaluran per wilayah, definisi status stok, serta waktu pembaruan data dalam satu kanal resmi.",
      "Tambahkan masa transisi, protokol eskalasi pengaduan, dan materi klarifikasi singkat untuk penyuluh serta kelompok tani.",
    ],
  },
  {
    id: "evidence",
    title: "Jejak Bukti Simulasi",
    content: [
      "Temuan mengacu pada 8 event simulasi, 6 kelompok stakeholder, 30 persona sintetis, dan 3 narasi risiko yang ditinjau sepanjang 5 ronde.",
      "Jejak ini merupakan keluaran simulasi berbasis asumsi skenario dan bukan representasi opini masyarakat sebenarnya.",
    ],
  },
];

export const demoCases: Record<string, DemoCase> = {
  "demo-penyaluran-pupuk": {
    id: "demo-penyaluran-pupuk",
    title: "Penyaluran Pupuk",
    question: "Bagaimana perubahan mekanisme penyaluran memengaruhi akses, kepercayaan, dan risiko narasi di tingkat petani?",
    graphNodes: [
      { id: "issue", label: "Akses penyaluran pupuk", type: "PolicyIssue", x: 385, y: 190, summary: "Isu utama mengenai ketepatan sasaran, stok, dan jadwal penyaluran." },
      { id: "petani", label: "Petani", type: "Stakeholder", x: 105, y: 145, summary: "Penerima manfaat yang memperhatikan ketersediaan dan harga pupuk.", group: "Petani" },
      { id: "kios", label: "Kios Resmi", type: "Stakeholder", x: 245, y: 72, summary: "Pelaksana penyaluran tingkat lokal dan titik validasi transaksi.", group: "Kios Resmi" },
      { id: "distributor", label: "Distributor", type: "Institution", x: 470, y: 68, summary: "Mengelola jadwal pasok dan distribusi antarwilayah.", group: "Distributor" },
      { id: "ministry", label: "Kementerian", type: "Institution", x: 675, y: 115, summary: "Pemilik kebijakan dan pengawasan ketepatan sasaran.", group: "Kementerian" },
      { id: "extension", label: "Penyuluh", type: "Stakeholder", x: 640, y: 300, summary: "Menjembatani informasi kebijakan dan kondisi lapangan.", group: "Penyuluh" },
      { id: "farmer-group", label: "Kelompok Tani", type: "PersonaGroup", x: 205, y: 320, summary: "Forum koordinasi petani dan penyebaran informasi lokal.", group: "Kelompok Tani" },
      { id: "clause", label: "Klausul verifikasi", type: "RegulationClause", x: 745, y: 220, summary: "Ketentuan verifikasi penerima dan pencatatan penyaluran." },
      { id: "concern", label: "Ketidakpastian stok", type: "PublicConcern", x: 330, y: 365, summary: "Kekhawatiran mengenai ketersediaan pada awal musim tanam." },
      { id: "risk", label: "Akses semakin sulit", type: "RiskNarrative", x: 500, y: 350, summary: "Narasi bahwa mekanisme baru akan membatasi akses pupuk." },
      { id: "evidence", label: "Rekap penyaluran", type: "EvidenceSource", x: 60, y: 265, summary: "Ringkasan data penyaluran dan pengaduan pada skenario demo." },
    ],
    graphEdges: fertilizerEdges,
    personas: [
      { id: "p1", name: "Pak Asep", group: "Petani", role: "Petani padi skala kecil", stance: "Khawatir", concern: "Kepastian stok sebelum masa tanam", topics: ["stok", "harga", "jadwal"], count: 8 },
      { id: "p2", name: "Ibu Nia", group: "Kios Resmi", role: "Pengelola kios kecamatan", stance: "Netral", concern: "Validasi penerima dan pembaruan stok", topics: ["verifikasi", "data", "layanan"], count: 4 },
      { id: "p3", name: "Bapak Arman", group: "Distributor", role: "Koordinator distribusi wilayah", stance: "Netral", concern: "Sinkronisasi jadwal pengiriman", topics: ["logistik", "jadwal", "stok"], count: 4 },
      { id: "p4", name: "Ibu Ratih", group: "Kementerian", role: "Analis kebijakan", stance: "Mendukung", concern: "Ketepatan sasaran dan audit", topics: ["regulasi", "sasaran", "audit"], count: 4 },
      { id: "p5", name: "Mas Dimas", group: "Penyuluh", role: "Penyuluh lapangan", stance: "Mendukung", concern: "Kejelasan materi sosialisasi", topics: ["klarifikasi", "pendampingan", "pengaduan"], count: 5 },
      { id: "p6", name: "Ibu Yani", group: "Kelompok Tani", role: "Ketua kelompok tani", stance: "Khawatir", concern: "Akses pengaduan dan pemerataan", topics: ["pengaduan", "pemerataan", "informasi"], count: 5 },
    ],
    events: [
      { id: "ev1", round: 1, time: "00:18", channel: "Forum Publik", persona: "Pak Asep", group: "Petani", type: "Pernyataan", statement: "Jadwal penyaluran perlu diumumkan sebelum keputusan tanam dibuat.", stance: "Khawatir", concerns: ["Jadwal", "Stok"], riskNarrative: "Akses semakin sulit", influenceSource: "Kelompok Tani" },
      { id: "ev2", round: 1, time: "00:31", channel: "Komunitas Kebijakan", persona: "Ibu Ratih", group: "Kementerian", type: "Klarifikasi", statement: "Verifikasi ditujukan untuk ketepatan sasaran dan tidak mengurangi alokasi wilayah.", stance: "Mendukung", concerns: ["Verifikasi"], riskNarrative: "Pembatasan penerima", influenceSource: "Klausul verifikasi" },
      { id: "ev3", round: 2, time: "00:52", channel: "Forum Publik", persona: "Ibu Yani", group: "Kelompok Tani", type: "Penguatan narasi", statement: "Informasi stok yang berbeda antarkanal memicu dugaan bahwa pupuk akan semakin sulit diperoleh.", stance: "Khawatir", concerns: ["Stok", "Transparansi"], riskNarrative: "Akses semakin sulit", influenceSource: "Percakapan petani" },
      { id: "ev4", round: 2, time: "01:14", channel: "Komunitas Kebijakan", persona: "Ibu Nia", group: "Kios Resmi", type: "Tanggapan", statement: "Kios memerlukan satu definisi status stok dan waktu pembaruan yang konsisten.", stance: "Netral", concerns: ["Data", "Layanan"], riskNarrative: "Data stok tidak akurat", influenceSource: "Rekap penyaluran" },
      { id: "ev5", round: 3, time: "01:42", channel: "Forum Publik", persona: "Mas Dimas", group: "Penyuluh", type: "Klarifikasi", statement: "Jadwal wilayah dan kanal pengaduan akan dibagikan melalui kelompok tani.", stance: "Mendukung", concerns: ["Klarifikasi"], riskNarrative: "Akses semakin sulit", influenceSource: "Kementerian" },
      { id: "ev6", round: 4, time: "02:18", channel: "Komunitas Kebijakan", persona: "Bapak Arman", group: "Distributor", type: "Pengaruh", statement: "Pembaruan jadwal mingguan mengurangi selisih informasi antara distributor dan kios.", stance: "Netral", concerns: ["Logistik"], riskNarrative: "Data stok tidak akurat", influenceSource: "Jadwal distribusi" },
      { id: "ev7", round: 4, time: "02:41", channel: "Forum Publik", persona: "Pak Asep", group: "Petani", type: "Perubahan sikap", statement: "Kepastian tanggal dan nomor pengaduan membuat mekanisme baru lebih dapat dipahami.", stance: "Netral", concerns: ["Jadwal", "Pengaduan"], riskNarrative: "Akses semakin sulit", influenceSource: "Penyuluh" },
      { id: "ev8", round: 5, time: "03:05", channel: "Komunitas Kebijakan", persona: "Ibu Ratih", group: "Kementerian", type: "Respons kebijakan", statement: "Masa transisi dan protokol eskalasi pengaduan dimasukkan ke dalam catatan revisi.", stance: "Mendukung", concerns: ["Transisi", "Pengaduan"], riskNarrative: "Pembatasan penerima", influenceSource: "Jejak event simulasi" },
    ],
    risks: [
      { id: "r1", title: "Pupuk akan semakin sulit diakses", level: "Tinggi", trend: "Meningkat", evidence: "Menguat pada ronde 2 sebelum klarifikasi jadwal tersedia." },
      { id: "r2", title: "Data stok tidak akurat", level: "Sedang", trend: "Menurun", evidence: "Menurun setelah definisi status dan pembaruan mingguan diperkenalkan." },
      { id: "r3", title: "Verifikasi membatasi penerima", level: "Sedang", trend: "Stabil", evidence: "Tetap muncul pada kelompok dengan akses informasi terbatas." },
    ],
    reportTitle: "Analisis Risiko Kebijakan Penyaluran Pupuk Berbasis Simulasi Skenario",
    reportSections,
  },
};

demoCases["demo-registrasi-umkm"] = {
  ...demoCases["demo-penyaluran-pupuk"],
  id: "demo-registrasi-umkm",
  title: "Registrasi Digital UMKM",
  question: "Bagaimana sosialisasi registrasi digital memengaruhi kekhawatiran tentang biaya, pajak, dan penggunaan data usaha?",
  reportTitle: "Analisis Risiko Registrasi Digital UMKM Berbasis Simulasi Skenario",
};

export const suggestedQuestions = [
  "Mengapa petani menunjukkan kekhawatiran tinggi?",
  "Narasi risiko apa yang paling cepat menyebar?",
  "Bagian kebijakan mana yang perlu diklarifikasi?",
  "Apa rekomendasi revisi paling penting?",
];

export const mockAnswers: Record<string, string> = {
  "Mengapa petani menunjukkan kekhawatiran tinggi?": "Kekhawatiran meningkat karena jadwal penyaluran dan definisi status stok belum konsisten pada ronde awal. Setelah penyuluh menyampaikan jadwal wilayah dan kanal pengaduan, sikap kelompok petani bergerak dari khawatir menuju netral.",
  "Narasi risiko apa yang paling cepat menyebar?": "Narasi 'pupuk akan semakin sulit diakses' menyebar paling cepat melalui Forum Publik pada ronde kedua. Pemicu utamanya adalah perbedaan informasi stok antarkanal.",
  "Bagian kebijakan mana yang perlu diklarifikasi?": "Klausul verifikasi penerima, waktu pembaruan stok, masa transisi, dan protokol eskalasi pengaduan memerlukan bahasa yang lebih operasional.",
  "Apa rekomendasi revisi paling penting?": "Tambahkan jadwal penyaluran per wilayah, definisi status stok, masa transisi, serta satu kanal pengaduan dengan batas waktu respons yang jelas.",
};
