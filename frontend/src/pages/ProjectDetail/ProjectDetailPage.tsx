import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell/AppShell";
import {
  useArchiveProject,
  useArchiveScenario,
  useCreateScenario,
  useDeleteProject,
  useDeleteScenario,
  useDuplicateScenario,
  useGraphFeedback,
  useProject,
  useRestoreProject,
  useScenarios,
} from "../../api/queries";
import type { ApiProject, ApiScenario } from "../../api/client";
import "./ProjectDetail.css";

type ReadinessItem = { id: string; label: string; checked: boolean };

const stageLabels = {
  graph: "Graf kebijakan",
  environment: "Lingkungan simulasi",
  simulation: "Simulasi",
  report: "Laporan",
  interaction: "Interaksi",
} as const;

function projectStatus(project: ApiProject) {
  if (project.status === "archived") return "Diarsipkan";
  if (project.report_available) return "Laporan tersedia";
  if (["processing", "running", "paused", "queued"].includes(project.workflow_status)) return "Simulasi berjalan";
  return project.current_stage === "graph" ? "Persiapan" : stageLabels[project.current_stage];
}

function StatusBadge({ project }: { project: ApiProject }) {
  const label = projectStatus(project);
  const key = label.toLowerCase().replaceAll(" ", "-");
  return <span className={`project-badge project-status project-status-${key}`}><i aria-hidden="true" />{label}</span>;
}

function ReadinessPanel({ items, rounds, onLaunch, mobile = false }: {
  items: ReadinessItem[];
  rounds: number;
  onLaunch: () => void;
  mobile?: boolean;
}) {
  const missing = items.filter((item) => !item.checked);
  const score = Math.round(((items.length - missing.length) / items.length) * 100);
  return (
    <aside className={`workspace-side-panel ${mobile ? "mobile" : ""}`} aria-label="Kesiapan simulasi">
      <p className="eyebrow">KESIAPAN SIMULASI</p>
      <div className="readiness-score"><strong>{score}%</strong><span>Kesiapan berdasarkan data tersimpan</span></div>
      <div className="progress-bar" aria-label={`Kesiapan ${score} persen`}><span style={{ width: `${score}%` }} /></div>
      <div className="readiness-list">
        {items.map((item) => <label className="checkbox-row" key={item.id}><input type="checkbox" checked={item.checked} disabled /><span>{item.label}</span></label>)}
      </div>
      <div className="workspace-side-meta">
        <div><span>Item belum lengkap</span><b>{missing.length ? missing.map((item) => item.label).join(", ") : "Tidak ada"}</b></div>
        <div><span>Konfigurasi aktif</span><b>{rounds} ronde</b></div>
        <div><span>Mode biaya</span><b>Ditentukan oleh penyedia backend</b></div>
      </div>
      <div className="output-list"><span>Output</span><p>event simulasi</p><p>analisis risiko narasi</p><p>laporan berbasis bukti</p></div>
      <button className="button primary run" onClick={onLaunch}>Buka workflow</button>
    </aside>
  );
}

function LaunchDialog({ projectName, missing, onCancel, onConfirm }: {
  projectName: string;
  missing: ReadinessItem[];
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && onCancel();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onCancel]);
  return (
    <div className="dialog-backdrop" onMouseDown={onCancel}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={(event) => event.stopPropagation()}>
        <button className="dialog-close" onClick={onCancel} aria-label="Tutup dialog">X</button>
        <p className="eyebrow">BUKA WORKFLOW</p>
        <h2 id={titleId}>Lanjutkan {projectName}?</h2>
        {missing.length > 0 && <div className="inline-alert warning"><p>Workflow masih perlu melengkapi: {missing.map((item) => item.label).join(", ")}.</p></div>}
        <p className="dialog-copy">Hasil simulasi adalah alat bantu analisis skenario dan tidak menggantikan konsultasi publik.</p>
        <div className="actions"><button className="button primary" onClick={onConfirm}>Buka workflow</button><button className="button secondary" onClick={onCancel}>Batal</button></div>
      </section>
    </div>
  );
}

function ScenarioForm({ projectId, onCreated }: { projectId: string; onCreated: (name: string) => void }) {
  const mutation = useCreateScenario(projectId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const created = await mutation.mutateAsync({ name, description, kind: "custom" }) as ApiScenario;
    setName("");
    setDescription("");
    onCreated(created.name);
  };
  return (
    <form className="scenario-create-form" onSubmit={submit}>
      <label>Nama skenario<input required minLength={2} maxLength={160} value={name} onChange={(event) => setName(event.target.value)} placeholder="Contoh: Sosialisasi intensif" /></label>
      <label>Deskripsi<textarea maxLength={2000} rows={2} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Asumsi yang ingin dibandingkan" /></label>
      {mutation.isError && <p className="form-error" role="alert">Skenario tidak dapat disimpan. Coba kembali.</p>}
      <button className="button secondary" disabled={mutation.isPending}>{mutation.isPending ? "Menyimpan..." : "Tambah skenario"}</button>
    </form>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const projectQuery = useProject(projectId);
  const scenariosQuery = useScenarios(projectId);
  const archiveMutation = useArchiveProject();
  const restoreMutation = useRestoreProject();
  const deleteProjectMutation = useDeleteProject();
  const duplicateScenarioMutation = useDuplicateScenario(projectId ?? "");
  const archiveScenarioMutation = useArchiveScenario(projectId ?? "");
  const deleteScenarioMutation = useDeleteScenario(projectId ?? "");
  const graphFeedback = useGraphFeedback(projectId ?? "");
  const [launchOpen, setLaunchOpen] = useState(false);
  const [notice, setNotice] = useState("");

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2800);
  };

  if (projectQuery.isLoading) {
    return <AppShell title="Memuat proyek" subtitle="Mengambil workspace kebijakan dari server." eyebrow="Workspace kebijakan"><div className="project-detail-skeleton" aria-label="Memuat detail proyek"><span /><span /><span /></div></AppShell>;
  }
  if (projectQuery.isError || !projectQuery.data) {
    return <AppShell title="Proyek tidak dapat dimuat" subtitle="Workspace mungkin tidak tersedia atau Anda tidak memiliki akses." eyebrow="Workspace kebijakan"><div className="state-block"><h3>Detail proyek tidak tersedia</h3><p>Periksa koneksi atau kembali ke daftar proyek.</p><div className="actions"><button className="button primary" onClick={() => projectQuery.refetch()}>Muat ulang</button><button className="button secondary" onClick={() => navigate("/projects")}>Kembali</button></div></div></AppShell>;
  }

  const project = projectQuery.data;
  const snapshot = project.snapshot;
  const scenarios = scenariosQuery.data?.items ?? [];
  const graphNodes = snapshot.graph?.nodes ?? [];
  const personas = snapshot.environment?.personas ?? [];
  const personaCount = snapshot.environment?.persona_count ?? personas.length;
  const rounds = snapshot.environment?.config?.rounds ?? 5;
  const stakeholders = [...new Set(personas.map((item) => item.group ?? item.stakeholder_group).filter((item): item is string => Boolean(item)))];
  if (stakeholders.length === 0) {
    stakeholders.push(...new Set(graphNodes.map((item) => item.group ?? item.type ?? item.entity_type).filter((item): item is string => Boolean(item))));
  }
  const readiness: ReadinessItem[] = [
    { id: "info", label: "Informasi proyek lengkap", checked: Boolean(project.name && project.institution && project.objective) },
    { id: "docs", label: "Dokumen kebijakan tersedia", checked: project.documents.length > 0 },
    { id: "framing", label: "Bingkai isu dihasilkan", checked: Boolean(snapshot.ontology?.analysis_summary || graphNodes.length) },
    { id: "stakeholders", label: "Stakeholder terpetakan", checked: stakeholders.length > 0 },
    { id: "personas", label: "Persona sintetis tersedia", checked: personaCount > 0 },
    { id: "scenario", label: "Skenario dikonfigurasi", checked: scenarios.length > 0 || Boolean(snapshot.environment?.config) },
  ];
  const missing = readiness.filter((item) => !item.checked);
  const workflowPath = `/simulation/${project.simulation_id}?step=${project.current_stage}&mode=${project.current_stage === "report" || project.current_stage === "interaction" ? "workbench" : "split"}`;
  const metadata = [
    ["Instansi", project.institution],
    ["Status proyek", projectStatus(project)],
    ["Tahap saat ini", stageLabels[project.current_stage]],
    ["Risiko tertinggi", project.highest_risk],
    ["Persona tersedia", `${personaCount} persona sintetis`],
    ["Jumlah ronde", `${rounds} ronde`],
    ["Skenario tersimpan", `${scenarios.length} skenario`],
    ["Terakhir diperbarui", new Date(project.updated_at).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })],
  ];
  const framing = [
    ["Tujuan kebijakan", project.objective],
    ["Pertanyaan analisis", snapshot.project?.question ?? project.objective],
    ["Ringkasan analisis", snapshot.ontology?.analysis_summary ?? "Bingkai isu akan tersedia setelah tahap graf kebijakan selesai."],
  ];
  const lifecyclePending = archiveMutation.isPending || restoreMutation.isPending;
  const changeLifecycle = async () => {
    if (project.status === "archived") {
      await restoreMutation.mutateAsync(project.id);
      showNotice(`${project.name} dipulihkan ke daftar aktif.`);
      return;
    }
    await archiveMutation.mutateAsync(project.id);
    navigate("/projects");
  };
  const removeProject = async () => {
    if (!window.confirm(`Jadwalkan penghapusan ${project.name}? Proyek dapat dipulihkan selama masa retensi.`)) return;
    await deleteProjectMutation.mutateAsync(project.id);
    navigate("/projects");
  };
  const scenarioAction = async (action: "duplicate" | "archive" | "delete", scenario: ApiScenario) => {
    try {
      if (action === "duplicate") await duplicateScenarioMutation.mutateAsync({ scenarioId: scenario.id, name: `${scenario.name} (salinan)` });
      if (action === "archive") await archiveScenarioMutation.mutateAsync(scenario.id);
      if (action === "delete" && window.confirm(`Hapus skenario ${scenario.name}?`)) await deleteScenarioMutation.mutateAsync(scenario.id);
      showNotice(`Skenario ${action === "duplicate" ? "diduplikasi" : action === "archive" ? "diarsipkan" : "dihapus"}.`);
    } catch { showNotice("Aksi skenario tidak dapat diselesaikan."); }
  };
  const sendGraphFeedback = async (action: "accept" | "reject") => {
    try { await graphFeedback.mutateAsync({ target_type: "graph", action, expected_version: project.version }); showNotice(action === "accept" ? "Graf diterima untuk tahap berikutnya." : "Graf ditandai untuk ditinjau ulang."); }
    catch { showNotice("Umpan balik graf tidak dapat disimpan."); }
  };

  return (
    <AppShell
      title={project.name}
      subtitle="Tinjau dokumen, asumsi, persona sintetis, dan skenario sebelum melanjutkan workflow simulasi."
      eyebrow="Workspace kebijakan"
      actions={<><button className="button primary" onClick={() => setLaunchOpen(true)}>Buka workflow</button><button className="button secondary" onClick={() => navigate(`/projects/${project.id}/scenarios`)}>Kelola skenario</button><button className="button ghost" onClick={() => navigate(`/projects/${project.id}/provenance`)}>Provenance</button><button className="button ghost" disabled={lifecyclePending} onClick={changeLifecycle}>{lifecyclePending ? "Memproses..." : project.status === "archived" ? "Pulihkan proyek" : "Arsipkan proyek"}</button><button className="button danger" disabled={deleteProjectMutation.isPending} onClick={removeProject}>Hapus</button></>}
    >
      <section className="workspace-top" aria-label="Ringkasan workspace">
        <div><div className="workspace-breadcrumb">Proyek Kebijakan / {project.name}</div><div className="workspace-title-row"><StatusBadge project={project} /><span>{stageLabels[project.current_stage]}</span></div><p>{snapshot.project?.question ?? project.objective}</p></div>
        <ReadinessPanel items={readiness} rounds={rounds} onLaunch={() => setLaunchOpen(true)} mobile />
      </section>
      <section className="workspace-layout">
        <div className="workspace-main">
          <section className="dashboard-panel workspace-panel" aria-labelledby="summary-title"><div className="panel-heading"><div><h2 id="summary-title">Ringkasan Proyek</h2><p>Metadata utama dari resource proyek dan snapshot workflow.</p></div></div><div className="workspace-card-grid">{metadata.map(([label, value]) => <article key={label}><span>{label}</span><b>{value}</b></article>)}</div></section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="docs-title"><div className="panel-heading"><div><h2 id="docs-title">Dokumen Kebijakan</h2><p>Berkas yang menjadi dasar ekstraksi dan jejak bukti.</p></div></div>{project.documents.length === 0 ? <div className="state-block"><h3>Belum ada dokumen</h3><p>Buat proyek baru dengan draft regulasi atau policy brief untuk membangun jejak bukti.</p></div> : <div className="workspace-table-wrap"><table className="data-table workspace-table"><thead><tr><th>Dokumen</th><th>Tipe</th><th>Diunggah</th><th>Status</th></tr></thead><tbody>{project.documents.map((document) => <tr key={document.id}><td>{document.name}</td><td>{document.media_type ?? document.name.split(".").at(-1)?.toUpperCase() ?? "Berkas"}</td><td>{document.created_at ? new Date(document.created_at).toLocaleDateString("id-ID") : "Tersimpan"}</td><td><span className="project-badge project-risk-rendah"><i aria-hidden="true" />{document.status ?? "Tersedia"}</span></td></tr>)}</tbody></table></div>}</section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="framing-title"><div className="panel-heading"><div><h2 id="framing-title">Bingkai Isu Kebijakan</h2><p>Asumsi yang dapat ditinjau sebelum simulasi skenario.</p></div></div><div className="workspace-row-list">{framing.map(([label, value]) => <article key={label}><span>{label}</span><p>{value}</p></article>)}</div></section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="graph-feedback-title"><div className="panel-heading"><div><h2 id="graph-feedback-title">Tinjauan Graf</h2><p>Rekam keputusan analis terhadap graf berversi sebelum persona digunakan.</p></div><div className="row-actions"><button disabled={graphFeedback.isPending} onClick={() => sendGraphFeedback("accept")}>Terima graf</button><button disabled={graphFeedback.isPending} onClick={() => sendGraphFeedback("reject")}>Minta revisi</button></div></div></section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="persona-title"><div className="panel-heading"><div><h2 id="persona-title">Stakeholder & Persona</h2><p>Kelompok sintetis yang dibentuk dari graf kebijakan.</p></div>{scenarios[0] && <button className="text-button inline-action" onClick={() => navigate(`/projects/${project.id}/scenarios/${scenarios[0].id}/personas`)}>Kelola persona</button>}</div>{stakeholders.length ? <div className="stakeholder-grid">{stakeholders.map((item) => <span key={item}>{item}</span>)}</div> : <div className="state-block"><h3>Stakeholder belum dipetakan</h3><p>Jalankan tahap graf kebijakan untuk menghasilkan kelompok stakeholder.</p></div>}<div className="workspace-card-grid"><article><span>Persona tersedia</span><b>{personaCount} persona</b></article><article><span>Kelompok stakeholder</span><b>{stakeholders.length} kelompok</b></article><article><span>Node graf</span><b>{graphNodes.length} node</b></article><article><span>Relasi graf</span><b>{snapshot.graph?.edges?.length ?? 0} relasi</b></article></div><p className="demo-note">Persona bersifat sintetis dan digunakan untuk simulasi skenario, bukan profil warga nyata.</p></section>

          <section className="dashboard-panel workspace-panel" aria-labelledby="scenario-title"><div className="panel-heading"><div><h2 id="scenario-title">Skenario Simulasi</h2><p>Asumsi pembanding yang disimpan sebagai resource berversi.</p></div></div>{scenariosQuery.isLoading && <div className="state-block"><h3>Memuat skenario...</h3></div>}{scenariosQuery.isError && <div className="state-block"><h3>Skenario tidak dapat dimuat</h3><button className="button secondary" onClick={() => scenariosQuery.refetch()}>Muat ulang</button></div>}{!scenariosQuery.isLoading && !scenariosQuery.isError && scenarios.length === 0 && <div className="state-block"><h3>Belum ada skenario pembanding</h3><p>Tambahkan asumsi alternatif untuk dibandingkan dengan konfigurasi workflow saat ini.</p></div>}{scenarios.length > 0 && <div className="workspace-row-list">{scenarios.map((scenario) => <article key={scenario.id}><span>{scenario.kind === "baseline" ? "Baseline" : scenario.kind === "revision" ? "Revisi" : "Kustom"}</span><div><p><b>{scenario.name}</b>{scenario.description ? ` · ${scenario.description}` : ""}</p><div className="row-actions"><button onClick={() => navigate(`/projects/${project.id}/scenarios/${scenario.id}`)}>Edit</button><button onClick={() => scenarioAction("duplicate", scenario)}>Duplikat</button><button onClick={() => scenarioAction("archive", scenario)}>Arsipkan</button><button onClick={() => scenarioAction("delete", scenario)}>Hapus</button></div></div></article>)}</div>}{project.status !== "archived" && <ScenarioForm projectId={project.id} onCreated={(name) => showNotice(`Skenario ${name} tersimpan.`)} />}</section>
        </div>
        <ReadinessPanel items={readiness} rounds={rounds} onLaunch={() => setLaunchOpen(true)} />
      </section>
      {launchOpen && <LaunchDialog projectName={project.name} missing={missing} onCancel={() => setLaunchOpen(false)} onConfirm={() => navigate(workflowPath)} />}
      <div className="toast-region" aria-live="polite">{notice && <div className="toast">{notice}</div>}</div>
    </AppShell>
  );
}
