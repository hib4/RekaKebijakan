export type Scenario = {
  id: string;
  name: string;
  support: number;
  concern: number;
  risk: "Tinggi" | "Sedang" | "Rendah";
  insight: string;
  personas: number;
  evidence: number;
  narratives: number;
};

export const scenarios: Scenario[] = [
  {
    id: "awal",
    name: "Rancangan awal",
    support: 46,
    concern: 38,
    risk: "Tinggi",
    insight:
      "Biaya registrasi dan masa transisi belum dipahami secara konsisten.",
    personas: 18,
    evidence: 5,
    narratives: 6,
  },
  {
    id: "transisi",
    name: "Skenario revisi",
    support: 61,
    concern: 25,
    risk: "Sedang",
    insight:
      "Pelaku UMKM menerima perubahan, tetapi masih membutuhkan pendampingan.",
    personas: 14,
    evidence: 7,
    narratives: 4,
  },
  {
    id: "bantuan",
    name: "Respons pemerintah",
    support: 74,
    concern: 16,
    risk: "Rendah",
    insight:
      "Akses bantuan langsung menurunkan kekhawatiran kelompok berliterasi digital rendah.",
    personas: 12,
    evidence: 8,
    narratives: 3,
  },
];
