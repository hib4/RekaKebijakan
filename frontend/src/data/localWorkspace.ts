import type { ProjectIntake } from "../pages/SimulationWorkflow/projectIntake";
import type { ReportSection } from "../pages/SimulationWorkflow/workflowTypes";
import { authStorageKey } from "../auth/storageNamespace";

export type ProjectStage = 0 | 1 | 2 | 3 | 4 | 5;

export type WorkspaceProject = ProjectIntake & {
  projectId: string;
  stage: ProjectStage;
  updatedAt: string;
  reportId?: string;
  highestRisk?: "Rendah" | "Sedang" | "Tinggi";
};

export type WorkspaceReport = {
  id: string;
  simulationId: string;
  projectId: string;
  projectName: string;
  institution: string;
  title: string;
  completedAt: string;
  highestRisk: "Rendah" | "Sedang" | "Tinggi";
  eventCount: number;
  personaCount: number;
  sections: ReportSection[];
};

type WorkspaceData = {
  version: 1;
  projects: WorkspaceProject[];
  reports: WorkspaceReport[];
};

const workspaceKey = () => authStorageKey("rekakebijakan-workspace-v1");

const seedProjects: WorkspaceProject[] = [
  {
    projectId: "makan-bergizi-gratis",
    simulationId: "demo-mbg",
    projectName: "Makan Bergizi Gratis (MBG)",
    institution: "Badan Gizi Nasional",
    domain: "Layanan gizi dan kesehatan publik",
    region: "Indonesia",
    period: "2026",
    purpose: "Mengkritisi desain tata kelola nasional Program MBG.",
    question: "Seberapa kuat alasan untuk menunda ekspansi MBG jika risiko salah sasaran, pengadaan, kesiapan wilayah, dan biaya peluang belum terjawab?",
    policySource: "Policy brief kritis tata kelola Program Makan Bergizi Gratis.pdf",
    framing: {},
    createdAt: "2026-07-20T09:00:00.000Z",
    updatedAt: "2026-07-24T08:04:00.000Z",
    stage: 3,
    highestRisk: "Sedang",
  },
  {
    projectId: "subsidi-transportasi-pelajar",
    simulationId: "demo-subsidi-transportasi",
    projectName: "Subsidi Transportasi Pelajar",
    institution: "Dinas Perhubungan Kota Arunika",
    domain: "Mobilitas dan pendidikan",
    region: "Kota Arunika",
    period: "2026",
    purpose: "Meninjau akses subsidi bagi siswa lintas wilayah.",
    question: "Kelompok siswa mana yang berisiko tidak terjangkau?",
    policySource: "Policy brief subsidi transportasi.pdf",
    framing: {},
    createdAt: "2026-07-18T09:00:00.000Z",
    updatedAt: "2026-07-24T07:00:00.000Z",
    stage: 2,
    highestRisk: "Rendah",
  },
  {
    projectId: "retribusi-pasar-berkeadilan",
    simulationId: "demo-retribusi-pasar",
    projectName: "Retribusi Pasar Berkeadilan",
    institution: "Bappeda Kota Arunika",
    domain: "Ekonomi daerah",
    region: "Kota Arunika",
    period: "2026",
    purpose: "Meninjau risiko masa transisi perubahan retribusi pasar.",
    question: "Bagaimana pedagang merespons perubahan retribusi?",
    policySource: "Rancangan perubahan retribusi pasar.pdf",
    framing: {},
    createdAt: "2026-07-15T09:00:00.000Z",
    updatedAt: "2026-07-23T10:30:00.000Z",
    stage: 5,
    reportId: "report-retribusi-pasar",
    highestRisk: "Tinggi",
  },
  {
    projectId: "pengurangan-plastik-sekali-pakai",
    simulationId: "demo-plastik-sekali-pakai",
    projectName: "Pengurangan Plastik Sekali Pakai",
    institution: "Dinas Lingkungan Hidup Kota Arunika",
    domain: "Lingkungan hidup",
    region: "Kota Arunika",
    period: "2026",
    purpose: "Menyiapkan rancangan pembatasan plastik sekali pakai.",
    question: "Apa kekhawatiran utama pelaku usaha dan konsumen?",
    policySource: "Ringkasan rancangan kebijakan.md",
    framing: {},
    createdAt: "2026-07-21T09:00:00.000Z",
    updatedAt: "2026-07-21T09:00:00.000Z",
    stage: 0,
  },
];

const seedSections: ReportSection[] = [
  { id: "executive", title: "Ringkasan Eksekutif", content: ["Simulasi menunjukkan bahwa masa transisi dan kejelasan penggunaan retribusi menjadi penentu penerimaan stakeholder."] },
  { id: "response", title: "Pergeseran Respons Stakeholder", content: ["Pedagang bergerak dari menolak menuju netral setelah mekanisme keberatan dan masa transisi dijelaskan."] },
  { id: "narrative", title: "Risiko Narasi Utama", content: ["Narasi kenaikan biaya tanpa perbaikan layanan menjadi indikasi risiko utama."] },
  { id: "indirect", title: "Dampak Tidak Langsung", content: ["Ketidakjelasan jadwal berpotensi menunda penyesuaian harga dan pencatatan pedagang."] },
  { id: "recommendation", title: "Rekomendasi Kebijakan", content: ["Publikasikan masa transisi, penggunaan penerimaan, dan kanal keberatan secara bersamaan."] },
  { id: "evidence", title: "Jejak Bukti Simulasi", content: ["Temuan dirangkum dari event persona sintetis dan asumsi skenario yang tersimpan."] },
];

const seedReports: WorkspaceReport[] = [
  {
    id: "report-retribusi-pasar",
    simulationId: "demo-retribusi-pasar",
    projectId: "retribusi-pasar-berkeadilan",
    projectName: "Retribusi Pasar Berkeadilan",
    institution: "Bappeda Kota Arunika",
    title: "Analisis Risiko Retribusi Pasar Berkeadilan Berbasis Simulasi Skenario",
    completedAt: "2026-07-23T10:30:00.000Z",
    highestRisk: "Tinggi",
    eventCount: 8,
    personaCount: 30,
    sections: seedSections,
  },
];

function initialData(): WorkspaceData {
  return { version: 1, projects: seedProjects, reports: seedReports };
}

function read(): WorkspaceData {
  const key = workspaceKey();
  const stored = localStorage.getItem(key);
  if (!stored) {
    const data = initialData();
    localStorage.setItem(key, JSON.stringify(data));
    return data;
  }
  try {
    return JSON.parse(stored) as WorkspaceData;
  } catch {
    const data = initialData();
    localStorage.setItem(key, JSON.stringify(data));
    return data;
  }
}

function write(data: WorkspaceData) {
  localStorage.setItem(workspaceKey(), JSON.stringify(data));
  window.dispatchEvent(new Event("workspace-updated"));
}

export function listWorkspaceProjects() {
  return read().projects.toSorted((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getWorkspaceProjectBySimulation(simulationId: string) {
  return read().projects.find((project) => project.simulationId === simulationId) ?? null;
}

export function getWorkspaceProject(projectId: string) {
  return read().projects.find((project) => project.projectId === projectId) ?? null;
}

export function saveWorkspaceProject(project: WorkspaceProject) {
  const data = read();
  const index = data.projects.findIndex((item) => item.projectId === project.projectId);
  if (index >= 0) data.projects[index] = project;
  else data.projects.unshift(project);
  write(data);
}

export function updateProjectStage(simulationId: string, stage: ProjectStage, reportId?: string) {
  const data = read();
  const project = data.projects.find((item) => item.simulationId === simulationId);
  if (!project) return;
  project.stage = Math.max(project.stage, stage) as ProjectStage;
  project.updatedAt = new Date().toISOString();
  if (reportId) project.reportId = reportId;
  write(data);
}

export function listWorkspaceReports() {
  return read().reports.toSorted((a, b) => b.completedAt.localeCompare(a.completedAt));
}

export function getWorkspaceReportBySimulation(simulationId: string) {
  return read().reports.find((report) => report.simulationId === simulationId) ?? null;
}

export function saveWorkspaceReport(report: WorkspaceReport) {
  const data = read();
  const index = data.reports.findIndex((item) => item.simulationId === report.simulationId);
  if (index >= 0) data.reports[index] = report;
  else data.reports.unshift(report);
  const project = data.projects.find((item) => item.simulationId === report.simulationId);
  if (project) {
    project.stage = Math.max(project.stage, 4) as ProjectStage;
    project.reportId = report.id;
    project.highestRisk = report.highestRisk;
    project.updatedAt = report.completedAt;
  }
  write(data);
}
