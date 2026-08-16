export const overviewMetrics = [
  ["Proyek aktif", "3", "Tiga rancangan sedang dipantau", "Aktif"],
  ["Simulasi berjalan", "1", "Satu eksperimen masih dalam ronde aktif", "Berjalan"],
  ["Temuan perlu ditinjau", "7", "Tiga temuan berisiko sedang atau tinggi", "Prioritas"],
  ["Laporan tersedia", "4", "Laporan dapat dibuka atau diekspor", "Siap"],
] as const;

export const attentionRows = [
  {
    severity: "High risk",
    project: "Makan Bergizi Gratis (MBG)",
    finding: "Ekspansi cepat dinilai berisiko sebelum audit pengadaan, validitas data, dan bukti dampak tersedia",
    source: "Skenario awal",
    updated: "8 menit lalu",
    action: "Tinjau",
  },
  {
    severity: "Medium risk",
    project: "Subsidi Transportasi Pelajar",
    finding: "Kelompok siswa perdesaan belum memiliki persona representatif",
    source: "Persiapan persona",
    updated: "1 jam lalu",
    action: "Lengkapi",
  },
  {
    severity: "Medium risk",
    project: "Retribusi Pasar",
    finding: "Ketentuan masa transisi memicu kekhawatiran pedagang",
    source: "Ronde 3",
    updated: "Kemarin",
    action: "Buka simulasi",
  },
] as const;

export const recentProjects = [
  ["Makan Bergizi Gratis (MBG)", "Badan Gizi Nasional", "Simulasi berjalan", "3", "Sedang", "8 menit lalu", "Buka"],
  ["Subsidi Transportasi Pelajar", "Dinas Perhubungan Kota Arunika", "Persiapan persona", "2", "Rendah", "1 jam lalu", "Lanjutkan"],
  ["Retribusi Pasar Berkeadilan", "Bappeda Kota Arunika", "Laporan tersedia", "4", "Tinggi", "Kemarin", "Lihat laporan"],
  ["Pengurangan Plastik Sekali Pakai", "Dinas Lingkungan Hidup Kota Arunika", "Draft", "1", "Belum dihitung", "3 hari lalu", "Buka"],
] as const;

export const recentActivity = [
  ["Sistem", "Laporan 'Retribusi Pasar Berkeadilan' berhasil dibuat.", "12 menit lalu"],
  ["Anda", "Skenario 'Argumen Penundaan Ekspansi' ditambahkan ke Makan Bergizi Gratis (MBG).", "38 menit lalu"],
  ["Anda", "12 persona diperbarui pada proyek Subsidi Transportasi Pelajar.", "1 jam lalu"],
  ["Sistem", "Stakeholder 'Pedagang Pasar Tradisional' disetujui.", "Kemarin"],
] as const;

export const projectStatuses = [
  "Semua status",
  "Simulasi berjalan",
  "Persiapan persona",
  "Laporan tersedia",
  "Draft",
] as const;
