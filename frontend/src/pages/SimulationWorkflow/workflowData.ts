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
      "Respons membaik ketika informasi operasional dikaitkan dengan bukti layanan: jadwal per wilayah, definisi status stok, dan alur pengaduan yang dapat ditelusuri.",
    ],
  },
  {
    id: "response",
    title: "Pergeseran Respons Stakeholder",
    content: [
      "Kelompok petani bergerak dari sikap khawatir menuju netral setelah penyuluh menjelaskan jadwal penyaluran dan mekanisme pengaduan.",
      "Kios resmi dan distributor tetap netral, dengan perhatian pada sinkronisasi data dan kepastian waktu pengiriman.",
      "Penyuluh menjadi aktor penyangga karena mampu menerjemahkan kebijakan menjadi tindakan lapangan, tetapi kapasitas klarifikasi mereka perlu didukung materi resmi yang selalu diperbarui.",
    ],
  },
  {
    id: "narrative",
    title: "Risiko Narasi Utama",
    content: [
      "Narasi bahwa pupuk akan semakin sulit diakses menyebar paling cepat di Forum Publik pada ronde kedua.",
      "Risiko meningkat ketika informasi stok tidak disertai sumber dan jadwal pembaruan yang dapat ditelusuri.",
      "Narasi tandingan perlu menampilkan kondisi per wilayah, alasan keterlambatan, dan langkah koreksi agar tidak terbaca sebagai bantahan umum tanpa bukti.",
    ],
  },
  {
    id: "indirect",
    title: "Dampak Tidak Langsung",
    content: [
      "Ketidakpastian penyaluran mendorong penundaan keputusan tanam dan meningkatkan beban klarifikasi pada penyuluh lapangan.",
      "Kelompok tani berpotensi menjadi penghubung informasi, tetapi juga mempercepat penyebaran narasi risiko jika tidak mendapat pembaruan resmi.",
      "Dampak tidak langsung juga terlihat pada koordinasi kios dan distributor: perbedaan data stok dapat menciptakan persepsi kelangkaan meskipun pasokan sedang dipindahkan antarwilayah.",
    ],
  },
  {
    id: "recommendation",
    title: "Rekomendasi Kebijakan",
    content: [
      "Publikasikan jadwal penyaluran per wilayah, definisi status stok, serta waktu pembaruan data dalam satu kanal resmi.",
      "Tambahkan masa transisi, protokol eskalasi pengaduan, dan materi klarifikasi singkat untuk penyuluh serta kelompok tani.",
      "Gunakan indikator mingguan berupa keluhan akses, waktu respons, ketepatan jadwal, dan jumlah koreksi data untuk menentukan apakah wilayah tertentu membutuhkan intervensi tambahan.",
    ],
  },
  {
    id: "evidence",
    title: "Jejak Bukti Simulasi",
    content: [
      "Temuan mengacu pada 8 event simulasi, 6 kelompok stakeholder, 30 persona sintetis, dan 3 narasi risiko yang ditinjau sepanjang 5 ronde.",
      "Jejak ini merupakan keluaran simulasi berbasis asumsi skenario dan bukan representasi opini masyarakat sebenarnya.",
      "Setiap rekomendasi perlu divalidasi dengan data lapangan, catatan pengaduan, dan wawancara pelaksana sebelum dijadikan keputusan implementasi final.",
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

demoCases["demo-mbg"] = {
  id: "demo-mbg",
  title: "Makan Bergizi Gratis (MBG)",
  question: "Seberapa kuat alasan untuk menunda ekspansi MBG jika risiko salah sasaran, pengadaan, kesiapan wilayah, dan biaya peluang belum terjawab?",
  graphNodes: [
    { id: "issue", label: "Risiko ekspansi MBG", type: "PolicyIssue", x: 385, y: 190, summary: "Isu utama mengenai ekspansi cepat, salah sasaran, pengadaan, kapasitas wilayah, dan biaya peluang." },
    { id: "bgn", label: "Badan Gizi Nasional", type: "Institution", x: 675, y: 115, summary: "Pengampu kebijakan yang perlu membuktikan dampak dan kesiapan ekspansi.", group: "BGN" },
    { id: "regional", label: "Pemerintah daerah", type: "Stakeholder", x: 245, y: 72, summary: "Pelaksana wilayah yang menanggung beban koreksi data dan pengawasan lokal.", group: "Pemerintah daerah" },
    { id: "school", label: "Sekolah", type: "Stakeholder", x: 105, y: 145, summary: "Satuan pendidikan yang berisiko menerima beban administrasi tambahan.", group: "Sekolah" },
    { id: "sppg", label: "SPPG & pemasok lokal", type: "PersonaGroup", x: 205, y: 320, summary: "Pelaksana produksi dan pengadaan yang rentan pada pembayaran terlambat serta konsentrasi pemasok.", group: "SPPG dan pemasok lokal" },
    { id: "health", label: "Tenaga kesehatan/gizi", type: "Stakeholder", x: 640, y: 300, summary: "Pemantau yang menuntut bukti dampak gizi, bukan hanya jumlah porsi tersalur.", group: "Tenaga kesehatan/gizi" },
    { id: "civil", label: "Masyarakat sipil & media", type: "Stakeholder", x: 470, y: 68, summary: "Pemantau konflik kepentingan, biaya peluang, dan transparansi anggaran.", group: "Masyarakat sipil & media" },
    { id: "clause", label: "Prasyarat ekspansi", type: "RegulationClause", x: 745, y: 220, summary: "Ambang validitas data, kapasitas SPPG, audit pengadaan, dan bukti dampak." },
    { id: "concern", label: "Biaya peluang dan salah sasaran", type: "PublicConcern", x: 330, y: 365, summary: "Kekhawatiran bahwa anggaran besar tidak menjangkau sasaran prioritas dan menggeser program lain." },
    { id: "risk", label: "Ekspansi terlalu cepat", type: "RiskNarrative", x: 500, y: 350, summary: "Narasi bahwa MBG berubah menjadi proyek logistik mahal sebelum prasyarat kebijakan terpenuhi." },
    { id: "evidence", label: "Audit dan evaluasi independen", type: "EvidenceSource", x: 60, y: 265, summary: "Bukti yang dibutuhkan: exclusion error, kesiapan wilayah, penerima kontrak, biaya peluang, dan dampak gizi." },
  ],
  graphEdges: [
    { id: "e1", source: "issue", target: "school", type: "AFFECTS" },
    { id: "e2", source: "issue", target: "regional", type: "IMPLEMENTED_BY" },
    { id: "e3", source: "sppg", target: "civil", type: "INFLUENCES" },
    { id: "e4", source: "civil", target: "bgn", type: "REFERENCES" },
    { id: "e5", source: "bgn", target: "clause", type: "IMPLEMENTED_BY" },
    { id: "e6", source: "school", target: "concern", type: "RAISES_CONCERN" },
    { id: "e7", source: "concern", target: "risk", type: "INFLUENCES" },
    { id: "e8", source: "health", target: "risk", type: "MITIGATES" },
    { id: "e9", source: "regional", target: "school", type: "SUPPORTS" },
    { id: "e10", source: "evidence", target: "issue", type: "REFERENCES" },
    { id: "e11", source: "health", target: "school", type: "INFLUENCES" },
  ],
  personas: [
    { id: "p1", name: "Pak Dedi", group: "BGN", role: "Analis tata kelola nasional", stance: "Netral", concern: "Tekanan ekspansi dan pembuktian dampak kebijakan", topics: ["ekspansi", "evaluasi", "akuntabilitas"], count: 5 },
    { id: "p2", name: "Ibu Rina", group: "Pemerintah daerah", role: "Koordinator pelaksanaan daerah", stance: "Kritis", concern: "Mandat pelaksanaan tanpa kapasitas dan anggaran memadai", topics: ["beban daerah", "kesiapan wilayah", "data"], count: 5 },
    { id: "p3", name: "Ibu Lestari", group: "Sekolah", role: "Kepala sekolah", stance: "Kritis", concern: "Beban administrasi dan gangguan pembelajaran", topics: ["administrasi", "pelaporan", "waktu belajar"], count: 5 },
    { id: "p4", name: "Pak Bima", group: "SPPG dan pemasok lokal", role: "Pengelola layanan dan pemasok lokal", stance: "Kritis", concern: "Risiko pengadaan, pembayaran terlambat, dan konsentrasi pemasok", topics: ["pengadaan", "pembayaran", "rantai pasok"], count: 5 },
    { id: "p5", name: "Dr. Maya", group: "Tenaga kesehatan/gizi", role: "Pemantau dampak gizi", stance: "Kritis", concern: "Bukti dampak gizi lemah dan biaya peluang kesehatan", topics: ["bukti dampak", "gizi", "biaya peluang"], count: 5 },
    { id: "p6", name: "Mbak Tara", group: "Masyarakat sipil & media", role: "Pemantau anggaran publik", stance: "Kritis", concern: "Transparansi anggaran, konflik kepentingan, dan biaya peluang", topics: ["anggaran", "konflik kepentingan", "biaya peluang"], count: 5 },
  ],
  events: [
    { id: "ev1", round: 1, time: "00:18", channel: "Forum Publik", persona: "Pak Dedi", group: "BGN", type: "Pernyataan", statement: "Tujuan gizi MBG penting, tetapi desain saat ini terlalu bergantung pada asumsi bahwa skala besar otomatis menghasilkan dampak.", stance: "Netral", concerns: ["Ekspansi", "Bukti dampak"], riskNarrative: "Ekspansi terlalu cepat", influenceSource: "Policy brief MBG" },
    { id: "ev2", round: 1, time: "00:31", channel: "Komunitas Kebijakan", persona: "Ibu Rina", group: "Pemerintah daerah", type: "Kritik desain", statement: "Daerah khawatir mandat pelaksanaan turun lebih cepat daripada dukungan anggaran, data, dan kapasitas pengawasan.", stance: "Kritis", concerns: ["Beban daerah", "Kapasitas"], riskNarrative: "Ekspansi mendahului kapasitas wilayah", influenceSource: "Mandat pelaksanaan" },
    { id: "ev3", round: 2, time: "00:52", channel: "Forum Publik", persona: "Mbak Tara", group: "Masyarakat sipil & media", type: "Penguatan narasi", statement: "Tanpa transparansi kontrak dan penerima manfaat akhir, risiko konflik kepentingan tetap tinggi.", stance: "Kritis", concerns: ["Transparansi", "Konflik kepentingan"], riskNarrative: "Akuntabilitas pengadaan lemah", influenceSource: "Diskusi publik" },
    { id: "ev4", round: 2, time: "01:14", channel: "Komunitas Kebijakan", persona: "Ibu Lestari", group: "Sekolah", type: "Tanggapan kritis", statement: "Pendataan dan pelaporan MBG berisiko mengalihkan waktu sekolah dari fungsi utama pembelajaran.", stance: "Kritis", concerns: ["Administrasi", "Pembelajaran"], riskNarrative: "Beban pelaksana tidak terlihat", influenceSource: "Data sekolah" },
    { id: "ev5", round: 3, time: "01:42", channel: "Forum Publik", persona: "Pak Bima", group: "SPPG dan pemasok lokal", type: "Kritik kapasitas", statement: "Kontrak baru sebaiknya ditunda di wilayah yang belum memiliki kepastian pembayaran dan aturan pengadaan terbuka.", stance: "Kritis", concerns: ["Pengadaan", "Pembayaran"], riskNarrative: "Ekspansi mendahului kapasitas wilayah", influenceSource: "Peta kapasitas wilayah" },
    { id: "ev6", round: 4, time: "02:18", channel: "Komunitas Kebijakan", persona: "Dr. Maya", group: "Tenaga kesehatan/gizi", type: "Pengaruh kritis", statement: "Program harus membuktikan dampak dibanding intervensi alternatif seperti suplementasi, sanitasi, atau edukasi gizi.", stance: "Kritis", concerns: ["Bukti dampak", "Biaya peluang"], riskNarrative: "Bukti dampak gizi lemah", influenceSource: "Evaluasi independen" },
    { id: "ev7", round: 4, time: "02:41", channel: "Forum Publik", persona: "Mbak Tara", group: "Masyarakat sipil & media", type: "Perubahan sikap", statement: "Publikasi agregat saja tidak cukup jika penerima kontrak, audit pemasok, dan wilayah yang ditunda tidak dibuka.", stance: "Kritis", concerns: ["Audit", "Anggaran"], riskNarrative: "Akuntabilitas pengadaan lemah", influenceSource: "Dashboard evaluasi" },
    { id: "ev8", round: 5, time: "03:05", channel: "Komunitas Kebijakan", persona: "Pak Dedi", group: "BGN", type: "Respons kebijakan", statement: "Review merekomendasikan penahanan ekspansi sampai data sasaran, kapasitas wilayah, dan audit pengadaan memenuhi ambang minimum.", stance: "Kritis", concerns: ["Penundaan", "Evaluasi"], riskNarrative: "Ekspansi terlalu cepat", influenceSource: "Jejak event simulasi" },
  ],
  risks: [
    { id: "r1", title: "Program tidak tepat sasaran", level: "Tinggi", trend: "Meningkat", evidence: "Exclusion error, data sasaran yang sulit dikoreksi, dan variasi kondisi wilayah muncul lintas ronde." },
    { id: "r2", title: "Ekspansi mendahului kapasitas wilayah", level: "Tinggi", trend: "Stabil", evidence: "Mandat pusat, beban sekolah, dan kapasitas SPPG tetap tidak seimbang meskipun ada klarifikasi." },
    { id: "r3", title: "Akuntabilitas pengadaan lemah", level: "Tinggi", trend: "Meningkat", evidence: "Transparansi anggaran, konflik kepentingan, audit pemasok, dan biaya peluang tetap menjadi keberatan utama." },
  ],
  reportTitle: "Analisis Risiko Makan Bergizi Gratis Berbasis Simulasi Skenario",
  reportSections: [
    { id: "executive", title: "Ringkasan Eksekutif", content: ["Simulasi menunjukkan argumen kontra yang kuat: MBG berisiko menjadi proyek logistik mahal jika ekspansi didorong sebelum data sasaran, kapasitas wilayah, audit pengadaan, dan bukti dampak memadai.", "Risiko tertinggi muncul pada salah sasaran, ekspansi mendahului kapasitas, akuntabilitas pengadaan, dan biaya peluang terhadap intervensi gizi atau pendidikan lain.", "Klarifikasi teknis belum cukup menurunkan keberatan; sebagian risiko tetap tinggi atau meningkat karena prasyarat belum mengikat keputusan ekspansi."] },
    { id: "response", title: "Pergeseran Respons Stakeholder", content: ["Daerah, sekolah, SPPG, tenaga gizi, dan masyarakat sipil bergerak ke posisi kritis karena beban dan risiko desain lebih jelas sepanjang simulasi.", "BGN tetap mencoba mempertahankan tujuan program, tetapi respons akhir tetap mengarah pada penahanan ekspansi, bukan sekadar perbaikan teknis.", "Tenaga kesehatan/gizi menjadi aktor penyangga kontra karena menuntut bukti dampak dibanding intervensi alternatif."] },
    { id: "narrative", title: "Risiko Narasi Utama", content: ["Narasi bahwa ekspansi terlalu cepat menyebar ketika data sasaran, kesiapan wilayah, penerima kontrak, dan biaya peluang tidak dapat diverifikasi.", "Risiko meningkat ketika informasi resmi hanya menonjolkan skala penyaluran tanpa membuka exclusion error, konflik pengadaan, dan hasil evaluasi independen.", "Narasi tandingan tidak cukup berupa klaim manfaat; perlu prasyarat ekspansi yang dapat membatalkan atau menunda pelaksanaan di wilayah belum siap."] },
    { id: "indirect", title: "Dampak Tidak Langsung", content: ["Ketidakjelasan desain meningkatkan beban administrasi sekolah dan tekanan koordinasi pada pemerintah daerah.", "SPPG berpotensi menjadi titik tekanan jika target ekspansi mendahului kapasitas rantai pasok, kepastian pembayaran, dan audit kontrak.", "Dampak tidak langsung juga terlihat pada biaya peluang anggaran untuk sanitasi, suplementasi, edukasi gizi, dan penguatan sekolah."] },
    { id: "recommendation", title: "Rekomendasi Kebijakan", content: ["Tahan ekspansi di wilayah yang belum memenuhi ambang validitas data, kapasitas SPPG, dukungan sekolah, audit pengadaan, dan bukti dampak.", "Publikasikan dashboard yang membuka cakupan sasaran, exclusion error, realisasi anggaran, penerima kontrak, audit pemasok, wilayah ditunda, dan indikator dampak gizi.", "Uji pilot dampak independen sebelum klaim keberhasilan dipakai untuk membenarkan perluasan anggaran nasional."] },
    { id: "evidence", title: "Jejak Bukti Simulasi", content: ["Temuan mengacu pada 8 event simulasi, 6 kelompok stakeholder, 30 persona sintetis, dan 3 narasi risiko yang ditinjau sepanjang 5 ronde.", "Jejak ini merupakan keluaran simulasi berbasis asumsi skenario dan bukan representasi opini masyarakat sebenarnya.", "Setiap rekomendasi kontra perlu divalidasi dengan data sasaran, kontrak pengadaan, biaya peluang, evaluasi gizi, dan observasi pelaksanaan sebelum dijadikan keputusan final."] },
  ],
};

export const suggestedQuestions = [
  "Mengapa ekspansi MBG berisiko terlalu cepat?",
  "Narasi risiko apa yang paling cepat menyebar?",
  "Seberapa kuat alasan untuk menunda ekspansi MBG?",
  "Risiko anggaran dan pengadaan apa yang paling kritis?",
];

export const mockAnswers: Record<string, string> = {
  "Mengapa ekspansi MBG berisiko terlalu cepat?": "Risiko terlalu cepat muncul karena target cakupan dapat mendahului validitas data sasaran, kesiapan SPPG, dukungan administrasi sekolah, audit pengadaan, dan bukti dampak gizi. Dalam simulasi, mayoritas stakeholder meminta penahanan ekspansi sampai prasyarat minimum terpenuhi.",
  "Narasi risiko apa yang paling cepat menyebar?": "Narasi 'ekspansi terlalu cepat' menyebar paling cepat ketika data sasaran, kesiapan wilayah, penerima kontrak, dan biaya peluang tidak dapat diverifikasi publik.",
  "Seberapa kuat alasan untuk menunda ekspansi MBG?": "Alasan terkuat adalah kombinasi exclusion error, beban sekolah/daerah, kapasitas SPPG yang belum merata, risiko konflik pengadaan, dan belum adanya bukti dampak independen yang membenarkan perluasan anggaran.",
  "Risiko anggaran dan pengadaan apa yang paling kritis?": "Risiko paling kritis adalah transparansi penerima kontrak, konsentrasi pemasok, pembayaran terlambat, audit pemasok yang terlambat, dan biaya peluang terhadap program gizi, sanitasi, kesehatan, atau pendidikan lain.",
};
