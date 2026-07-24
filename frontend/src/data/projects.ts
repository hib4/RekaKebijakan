export type ProjectStatus =
  | "Draft"
  | "Persiapan"
  | "Simulasi berjalan"
  | "Menunggu peninjauan"
  | "Laporan tersedia"
  | "Selesai";

export type ProjectRisk = "Tinggi" | "Sedang" | "Rendah" | "Belum dihitung";

export type PolicyProject = {
  id: string;
  name: string;
  institution: string;
  status: ProjectStatus;
  scenarios: number;
  lastSimulation: string;
  risk: ProjectRisk;
  updated: string;
  updatedRank: number;
  archived?: boolean;
};

export const projectSummary = [
  ["Total proyek", "12", "Seluruh proyek dalam ruang kerja"],
  ["Simulasi berjalan", "2", "Eksperimen aktif saat ini"],
  ["Menunggu peninjauan", "3", "Memerlukan keputusan analis"],
  ["Laporan tersedia", "5", "Siap dibuka atau dibagikan"],
] as const;

export const policyProjects: PolicyProject[] = [
  {
    id: "registrasi-digital-umkm",
    name: "Registrasi Digital UMKM",
    institution: "Dinas Koperasi Kota Arunika",
    status: "Simulasi berjalan",
    scenarios: 3,
    lastSimulation: "Ronde 3 dari 5",
    risk: "Sedang",
    updated: "8 menit lalu",
    updatedRank: 1,
  },
  {
    id: "subsidi-transportasi-pelajar",
    name: "Subsidi Transportasi Pelajar",
    institution: "Dinas Perhubungan Kota Arunika",
    status: "Menunggu peninjauan",
    scenarios: 2,
    lastSimulation: "Persiapan persona",
    risk: "Rendah",
    updated: "1 jam lalu",
    updatedRank: 2,
  },
  {
    id: "retribusi-pasar-berkeadilan",
    name: "Retribusi Pasar Berkeadilan",
    institution: "Bappeda Kota Arunika",
    status: "Laporan tersedia",
    scenarios: 4,
    lastSimulation: "Selesai",
    risk: "Tinggi",
    updated: "Kemarin",
    updatedRank: 3,
  },
  {
    id: "pengurangan-plastik-sekali-pakai",
    name: "Pengurangan Plastik Sekali Pakai",
    institution: "Dinas Lingkungan Hidup Kota Arunika",
    status: "Draft",
    scenarios: 1,
    lastSimulation: "Belum dijalankan",
    risk: "Belum dihitung",
    updated: "3 hari lalu",
    updatedRank: 4,
  },
  {
    id: "bantuan-pangan-berbasis-wilayah",
    name: "Bantuan Pangan Berbasis Wilayah",
    institution: "Dinas Sosial Kota Arunika",
    status: "Persiapan",
    scenarios: 2,
    lastSimulation: "Tinjau stakeholder",
    risk: "Belum dihitung",
    updated: "5 hari lalu",
    updatedRank: 5,
  },
  {
    id: "kawasan-rendah-emisi-pusat-kota",
    name: "Kawasan Rendah Emisi Pusat Kota",
    institution: "Dinas Perhubungan Kota Arunika",
    status: "Selesai",
    scenarios: 5,
    lastSimulation: "Selesai",
    risk: "Sedang",
    updated: "7 hari lalu",
    updatedRank: 6,
  },
  {
    id: "program-literasi-digital-desa",
    name: "Program Literasi Digital Desa",
    institution: "Dinas Komunikasi dan Informatika Kota Arunika",
    status: "Laporan tersedia",
    scenarios: 3,
    lastSimulation: "Selesai",
    risk: "Rendah",
    updated: "10 hari lalu",
    updatedRank: 7,
  },
];

export const projectStatusOptions = [
  "Semua status",
  "Draft",
  "Persiapan",
  "Simulasi berjalan",
  "Menunggu peninjauan",
  "Laporan tersedia",
  "Selesai",
] as const;

export const projectRiskOptions = [
  "Semua risiko",
  "Tinggi",
  "Sedang",
  "Rendah",
  "Belum dihitung",
] as const;

export const projectInstitutionOptions = [
  "Semua institusi",
  "Dinas Koperasi Kota Arunika",
  "Dinas Perhubungan Kota Arunika",
  "Bappeda Kota Arunika",
  "Dinas Lingkungan Hidup Kota Arunika",
] as const;

export const projectSortOptions = [
  "Terakhir diperbarui",
  "Nama proyek",
  "Risiko tertinggi",
  "Status",
] as const;

export const pageSizeOptions = [10, 20, 50] as const;
