import { demoCases } from "./workflowData";
import { getWorkspaceProjectBySimulation, saveWorkspaceProject } from "../../data/localWorkspace";
import type { DemoCase, PolicyGraphEdge, PolicyGraphNode } from "./workflowTypes";

export type ProjectIntake = {
  simulationId: string;
  projectName: string;
  institution: string;
  domain: string;
  region: string;
  period: string;
  purpose: string;
  question: string;
  policySource: string;
  framing: Record<string, string[]>;
  createdAt: string;
};

const storagePrefix = "rekakebijakan-project-intake:";

export function saveProjectIntake(intake: ProjectIntake) {
  saveWorkspaceProject({ ...intake, projectId: intake.simulationId.replace(/-\d{6}$/, ""), stage: 0, updatedAt: intake.createdAt });
}

export function loadProjectIntake(simulationId: string): ProjectIntake | null {
  const project = getWorkspaceProjectBySimulation(simulationId);
  if (project) return project;
  const stored = sessionStorage.getItem(`${storagePrefix}${simulationId}`);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as ProjectIntake;
  } catch {
    return null;
  }
}

function first(framing: Record<string, string[]>, key: string, fallback: string) {
  return framing[key]?.find((item) => item.trim()) ?? fallback;
}

export function intakeToDemoCase(intake: ProjectIntake): DemoCase {
  const base = demoCases["demo-registrasi-umkm"];
  const stakeholderNames = intake.framing["Kelompok terdampak"]?.filter((item) => item.trim()).slice(0, 3) ?? [];
  const groups = [...stakeholderNames, "Pelaksana layanan", "Organisasi masyarakat", intake.institution].slice(0, 6);
  while (groups.length < 6) groups.push(`Kelompok stakeholder ${groups.length + 1}`);
  const primaryConcern = first(intake.framing, "Potensi keberatan", "Kejelasan proses implementasi dan akses layanan.");
  const primaryRisk = first(intake.framing, "Risiko narasi", `Kebijakan ${intake.projectName} dipersepsikan menambah beban tanpa dukungan yang memadai.`);
  const nodes: PolicyGraphNode[] = [
    { id: "issue", label: intake.projectName, type: "PolicyIssue", x: 385, y: 190, summary: intake.purpose },
    { id: "institution", label: intake.institution, type: "Institution", x: 650, y: 100, summary: `Institusi pengampu di ${intake.region}.`, group: intake.institution },
    { id: "clause", label: "Ketentuan utama", type: "RegulationClause", x: 720, y: 250, summary: first(intake.framing, "Pasal/ketentuan penting", "Ketentuan kebijakan yang perlu ditinjau.") },
    { id: "stakeholder-primary", label: first(intake.framing, "Kelompok terdampak", "Kelompok terdampak utama"), type: "Stakeholder", x: 130, y: 120, summary: "Kelompok yang menerima dampak langsung dari rancangan kebijakan." },
    { id: "stakeholder-secondary", label: intake.domain, type: "Stakeholder", x: 205, y: 315, summary: "Ekosistem pelaksana dan penerima manfaat kebijakan." },
    { id: "concern", label: "Keberatan utama", type: "PublicConcern", x: 365, y: 365, summary: first(intake.framing, "Potensi keberatan", "Kekhawatiran implementasi dan akses layanan.") },
    { id: "risk", label: "Risiko narasi", type: "RiskNarrative", x: 540, y: 350, summary: first(intake.framing, "Risiko narasi", "Narasi risiko yang perlu diuji melalui simulasi.") },
    { id: "persona", label: "Kelompok persona", type: "PersonaGroup", x: 75, y: 255, summary: "Persona sintetis akan dibentuk pada tahap Environment Setup." },
    { id: "evidence", label: "Sumber kebijakan", type: "EvidenceSource", x: 310, y: 75, summary: intake.policySource },
  ];
  const edges: PolicyGraphEdge[] = [
    { id: "custom-e1", source: "issue", target: "stakeholder-primary", type: "AFFECTS" },
    { id: "custom-e2", source: "issue", target: "stakeholder-secondary", type: "AFFECTS" },
    { id: "custom-e3", source: "institution", target: "issue", type: "IMPLEMENTED_BY" },
    { id: "custom-e4", source: "clause", target: "issue", type: "REFERENCES" },
    { id: "custom-e5", source: "stakeholder-primary", target: "concern", type: "RAISES_CONCERN" },
    { id: "custom-e6", source: "concern", target: "risk", type: "INFLUENCES" },
    { id: "custom-e7", source: "persona", target: "stakeholder-primary", type: "REFERENCES" },
    { id: "custom-e8", source: "evidence", target: "issue", type: "REFERENCES" },
  ];
  return {
    ...base,
    id: intake.simulationId,
    title: intake.projectName,
    question: intake.question,
    graphNodes: nodes,
    graphEdges: edges,
    personas: groups.map((group, index) => ({
      id: `custom-persona-${index + 1}`,
      name: [`Ibu Sari`, `Pak Bima`, `Ibu Ratna`, `Pak Dedi`, `Ibu Maya`, `Pak Arif`][index],
      group,
      role: index === 5 ? "Perwakilan institusi pengampu" : `Perwakilan ${group.toLowerCase()}`,
      stance: index < 2 ? "Khawatir" : index > 3 ? "Mendukung" : "Netral",
      concern: index < 2 ? primaryConcern : index === 5 ? "Kesiapan implementasi dan akuntabilitas" : "Kejelasan informasi dan masa transisi",
      topics: index < 2 ? ["akses", "implementasi", "klarifikasi"] : ["sosialisasi", "layanan", "evaluasi"],
      count: 5,
    })),
    events: [
      { id: "custom-event-1", round: 1, time: "00:18", channel: "Forum Publik", persona: "Ibu Sari", group: groups[0], type: "Pernyataan", statement: `${groups[0]} meminta penjelasan mengenai tahapan implementasi ${intake.projectName}.`, stance: "Khawatir", concerns: ["Implementasi", "Akses"], riskNarrative: primaryRisk, influenceSource: intake.policySource },
      { id: "custom-event-2", round: 1, time: "00:36", channel: "Komunitas Kebijakan", persona: "Pak Arif", group: intake.institution, type: "Klarifikasi", statement: `${intake.institution} menjelaskan tujuan kebijakan dan asumsi masa transisi.`, stance: "Mendukung", concerns: ["Klarifikasi"], riskNarrative: primaryRisk, influenceSource: "Ketentuan utama" },
      { id: "custom-event-3", round: 2, time: "00:58", channel: "Forum Publik", persona: "Pak Bima", group: groups[1], type: "Penguatan narasi", statement: primaryRisk, stance: "Khawatir", concerns: ["Kepercayaan", "Dampak"], riskNarrative: primaryRisk, influenceSource: `Percakapan ${groups[1]}` },
      { id: "custom-event-4", round: 2, time: "01:16", channel: "Komunitas Kebijakan", persona: "Ibu Ratna", group: groups[2], type: "Tanggapan", statement: "Stakeholder meminta indikator keberhasilan dan kanal pengaduan yang dapat ditelusuri.", stance: "Netral", concerns: ["Evaluasi", "Pengaduan"], riskNarrative: primaryRisk, influenceSource: "Bingkai kebijakan" },
      { id: "custom-event-5", round: 3, time: "01:44", channel: "Forum Publik", persona: "Pak Dedi", group: groups[3], type: "Klarifikasi", statement: "Pelaksana layanan membagikan tahapan implementasi dan mekanisme pendampingan.", stance: "Mendukung", concerns: ["Pendampingan"], riskNarrative: primaryRisk, influenceSource: intake.institution },
      { id: "custom-event-6", round: 4, time: "02:12", channel: "Komunitas Kebijakan", persona: "Ibu Maya", group: groups[4], type: "Pengaruh", statement: "Kejelasan masa transisi mengurangi ketidakpastian pada kelompok terdampak.", stance: "Netral", concerns: ["Transisi"], riskNarrative: primaryRisk, influenceSource: "Jejak klarifikasi" },
      { id: "custom-event-7", round: 4, time: "02:38", channel: "Forum Publik", persona: "Ibu Sari", group: groups[0], type: "Perubahan sikap", statement: "Informasi yang lebih operasional membuat kebijakan lebih mudah dipahami.", stance: "Netral", concerns: ["Informasi"], riskNarrative: primaryRisk, influenceSource: "Pelaksana layanan" },
      { id: "custom-event-8", round: 5, time: "03:04", channel: "Komunitas Kebijakan", persona: "Pak Arif", group: intake.institution, type: "Respons kebijakan", statement: "Catatan revisi memasukkan klarifikasi, masa transisi, dan indikator evaluasi.", stance: "Mendukung", concerns: ["Revisi", "Evaluasi"], riskNarrative: primaryRisk, influenceSource: "Jejak simulasi" },
    ],
    risks: [
      { id: "custom-risk-1", title: primaryRisk, level: "Tinggi", trend: "Meningkat", evidence: "Menguat sebelum informasi implementasi dan masa transisi tersedia." },
      { id: "custom-risk-2", title: "Informasi pelaksanaan tidak konsisten", level: "Sedang", trend: "Menurun", evidence: "Menurun setelah institusi menggunakan satu rujukan klarifikasi." },
      { id: "custom-risk-3", title: "Kelompok terdampak tidak memiliki kanal pengaduan", level: "Sedang", trend: "Stabil", evidence: "Tetap memerlukan ketentuan operasional dan batas waktu respons." },
    ],
    reportTitle: `Analisis Risiko ${intake.projectName} Berbasis Simulasi Skenario`,
    reportSections: [
      { id: "executive", title: "Ringkasan Eksekutif", content: [`Simulasi ${intake.projectName} menunjukkan bahwa kejelasan implementasi, masa transisi, dan kanal klarifikasi menjadi penentu respons stakeholder.`] },
      { id: "response", title: "Pergeseran Respons Stakeholder", content: [`${groups[0]} dan ${groups[1]} bergerak dari khawatir menuju netral setelah informasi operasional tersedia.`] },
      { id: "narrative", title: "Risiko Narasi Utama", content: [primaryRisk, "Risiko meningkat ketika informasi pelaksanaan berbeda antarkanal."] },
      { id: "indirect", title: "Dampak Tidak Langsung", content: ["Ketidakpastian dapat meningkatkan beban klarifikasi pelaksana dan menunda kesiapan kelompok terdampak."] },
      { id: "recommendation", title: "Rekomendasi Kebijakan", content: ["Perjelas tahapan implementasi, masa transisi, kanal pengaduan, serta indikator evaluasi dalam satu rujukan resmi."] },
      { id: "evidence", title: "Jejak Bukti Simulasi", content: [`Temuan mengacu pada 8 event, 6 kelompok stakeholder, 30 persona sintetis, dan sumber ${intake.policySource}.`] },
    ],
  };
}
