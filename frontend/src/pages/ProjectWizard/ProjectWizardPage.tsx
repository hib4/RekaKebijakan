import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../../api/client";
import { AppShell } from "../../components/AppShell/AppShell";
import { saveProjectIntake } from "../SimulationWorkflow/projectIntake";
import { clearQuickPresentationSession } from "../SimulationWorkflow/workflowSession";
import "./ProjectWizard.css";

const workflow = [
  ["01", "Graph Build", "Menyusun ontologi, stakeholder, dan relasi kebijakan."],
  ["02", "Env Setup", "Membentuk persona sintetis dan konfigurasi skenario."],
  ["03", "Simulation", "Menjalankan event pada dua kanal kebijakan."],
  ["04", "Report", "Menghasilkan laporan dengan jejak bukti."],
  ["05", "Interaction", "Meninjau laporan dan mewawancarai persona."],
] as const;

const acceptedExtensions = new Set(["pdf", "md", "txt", "docx"]);
const maxFiles = 20;
const maxFileBytes = 16 * 1024 * 1024;
const quickDemoBundleId = "registrasi-digital-umkm-v1";
const quickDemoMetadata = {
  projectName: "Registrasi Digital UMKM",
  institution: "Dinas Koperasi dan UMKM",
  objective: "Bagaimana respons pelaku UMKM terhadap kewajiban registrasi digital, dan narasi risiko apa yang perlu diklarifikasi?",
};
type WorkflowMode = "full_simulation" | "quick_demo";

type SubmitPhase = "idle" | "preparing" | "uploading" | "processing" | "opening";

const phaseLabels: Record<SubmitPhase, string> = {
  idle: "",
  preparing: "Memvalidasi input...",
  uploading: "Mengunggah dokumen...",
  processing: "Membuat proyek dan menyiapkan graf...",
  opening: "Proyek siap. Membuka Graph Build...",
};

export default function ProjectWizardPage() {
  const navigate = useNavigate();
  const demoMode = import.meta.env.VITE_DEMO_MODE === "true";
  const [projectName, setProjectName] = useState(quickDemoMetadata.projectName);
  const [institution, setInstitution] = useState(quickDemoMetadata.institution);
  const [objective, setObjective] = useState(quickDemoMetadata.objective);
  const [workflowMode, setWorkflowMode] = useState<WorkflowMode>("quick_demo");
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitPhase, setSubmitPhase] = useState<SubmitPhase>("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [fileError, setFileError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const submitLockRef = useRef(false);
  const idempotencyKeyRef = useRef<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => () => {
    submitLockRef.current = false;
    requestRef.current?.abort();
  }, []);

  const markFormChanged = () => {
    idempotencyKeyRef.current = null;
    setError("");
  };
  const selectWorkflowMode = (mode: WorkflowMode) => {
    if (submitting) return;
    setWorkflowMode(mode);
    if (mode === "quick_demo") {
      setProjectName(quickDemoMetadata.projectName);
      setInstitution(quickDemoMetadata.institution);
      setObjective(quickDemoMetadata.objective);
      setFiles([]);
      setFileError("");
    } else if (
      projectName === quickDemoMetadata.projectName &&
      institution === quickDemoMetadata.institution &&
      objective === quickDemoMetadata.objective
    ) {
      setProjectName("");
      setInstitution("");
      setObjective("");
    }
    markFormChanged();
  };

  const addFiles = (list: FileList | null) => {
    if (!list || submitting) return;
    const rejected: string[] = [];
    const candidates = Array.from(list).filter((file) => {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!acceptedExtensions.has(extension)) {
        rejected.push(`${file.name}: tipe berkas tidak didukung`);
        return false;
      }
      if (file.size > maxFileBytes) {
        rejected.push(`${file.name}: ukuran melebihi 16 MB`);
        return false;
      }
      return true;
    });
    const unique = candidates.filter((file) => !files.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified));
    const available = Math.max(0, maxFiles - files.length);
    if (unique.length > available) rejected.push(`Maksimal ${maxFiles} berkas per proyek; ${unique.length - available} berkas tidak ditambahkan`);
    setFiles([...files, ...unique.slice(0, available)]);
    setFileError(rejected.join(". "));
    idempotencyKeyRef.current = null;
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitLockRef.current || !projectName.trim() || !institution.trim() || !objective.trim() || (workflowMode === "full_simulation" && files.length === 0)) return;
    submitLockRef.current = true;
    setSubmitting(true);
    setSubmitPhase("preparing");
    setUploadProgress(0);
    setError("");
    const controller = new AbortController();
    requestRef.current = controller;
    idempotencyKeyRef.current ??= globalThis.crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
    try {
      const result = await createProject(
        { projectName: projectName.trim(), institution: institution.trim(), objective: objective.trim(), files, workflowMode, demoBundleId: workflowMode === "quick_demo" ? quickDemoBundleId : undefined },
        {
          idempotencyKey: idempotencyKeyRef.current,
          signal: controller.signal,
          onUploadProgress: (progress) => {
            setSubmitPhase("uploading");
            setUploadProgress(progress);
          },
          onUploadComplete: () => {
            setUploadProgress(100);
            setSubmitPhase("processing");
          },
        },
      );
      const simulationId = result.simulation_id || result.id;
      if (!simulationId) throw new Error("Backend tidak mengembalikan simulation_id.");
      if (workflowMode === "quick_demo")
        clearQuickPresentationSession(simulationId);
      if (demoMode) {
        saveProjectIntake({ simulationId, projectName: projectName.trim(), institution: institution.trim(), domain: "Kebijakan publik", region: "Indonesia", period: "2026", purpose: objective.trim(), question: objective.trim(), policySource: files.map((file) => file.name).join(", "), framing: {}, createdAt: new Date().toISOString() });
      }
      setSubmitPhase("opening");
      navigate(`/simulation/${encodeURIComponent(simulationId)}?step=graph&mode=split`);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setError(cause instanceof Error ? cause.message : "Proyek gagal dibuat. Coba lagi.");
      setSubmitting(false);
      setSubmitPhase("idle");
      submitLockRef.current = false;
      requestRef.current = null;
    }
  };

  return <AppShell title="Buat Proyek Kebijakan" subtitle="Masukkan sumber kebijakan dan tujuan simulasi untuk memulai Graph Build." eyebrow="Proyek kebijakan" actions={<button className="button secondary" onClick={() => navigate("/projects")}>Kembali ke daftar proyek</button>}>
    <section className="create-project-layout">
      <aside className="create-project-guide">
        <p className="eyebrow">ALUR PROYEK</p>
        <h2>Satu input, lima tahap peninjauan.</h2>
        <p>Sumber kebijakan menjadi dasar graf, persona sintetis, simulasi skenario, laporan, dan interaksi lanjutan.</p>
        <div className="create-workflow-list">{workflow.map(([number, title, description]) => <article key={number}><span>{number}</span><div><b>{title}</b><p>{description}</p></div></article>)}</div>
        <p className="responsible-note">Keluaran merupakan simulasi berbasis asumsi skenario untuk dukungan keputusan, bukan pengganti konsultasi publik.</p>
      </aside>
      <form className="create-project-console" onSubmit={submit} aria-busy={submitting}>
        <div className="create-console-header"><span>PROJECT INPUT</span><span>FLASK API</span></div>
        <fieldset className="workflow-mode-selector">
          <legend>Pilih cara memulai</legend>
          <div className="workflow-mode-options">
            <label className={workflowMode === "quick_demo" ? "selected" : ""}>
              <input type="radio" name="workflow-mode" value="quick_demo" checked={workflowMode === "quick_demo"} onChange={() => selectWorkflowMode("quick_demo")} disabled={submitting} />
              <span><b>Simulasi Cepat <em>Direkomendasikan</em></b><small>Jelajahi skenario Registrasi Digital UMKM.</small></span>
            </label>
            <label className={workflowMode === "full_simulation" ? "selected" : ""}>
              <input type="radio" name="workflow-mode" value="full_simulation" checked={workflowMode === "full_simulation"} onChange={() => selectWorkflowMode("full_simulation")} disabled={submitting} />
              <span><b>Simulasi lengkap</b><small>Unggah sumber sendiri dan jalankan seluruh tahap dari awal.</small></span>
            </label>
          </div>
        </fieldset>
        <div className="create-fields">
          <label className="field"><span>Nama proyek</span><input value={projectName} onChange={(event) => { setProjectName(event.target.value); markFormChanged(); }} required disabled={submitting || workflowMode === "quick_demo"} /></label>
          <label className="field"><span>Instansi/tim</span><input value={institution} onChange={(event) => { setInstitution(event.target.value); markFormChanged(); }} required disabled={submitting || workflowMode === "quick_demo"} /></label>
        </div>
        {workflowMode === "full_simulation" ? <section className="create-console-section">
          <header><b>SUMBER KEBIJAKAN</b><span>PDF, DOCX, MD, TXT</span></header>
          <div className={`project-upload-zone ${dragging ? "dragging" : ""} ${files.length ? "has-files" : ""}`} onDragOver={(event: DragEvent) => { event.preventDefault(); if (!submitting) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}>
            <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.md,.txt" onChange={(event: ChangeEvent<HTMLInputElement>) => addFiles(event.target.files)} disabled={submitting} aria-describedby="project-file-help project-file-error" />
            {files.length === 0 ? <><strong aria-hidden="true">↑</strong><button className="project-upload-picker" type="button" onClick={() => inputRef.current?.click()} disabled={submitting}>Tarik dokumen ke sini atau pilih berkas</button><span id="project-file-help">Maksimal 20 berkas PDF, DOCX, MD, atau TXT; masing-masing hingga 16 MB.</span></> : <><div className="project-file-list">{files.map((file) => <span key={`${file.name}-${file.size}-${file.lastModified}`}>{file.name}<button type="button" disabled={submitting} aria-label={`Hapus ${file.name}`} onClick={() => { setFiles((current) => current.filter((item) => item !== file)); setFileError(""); markFormChanged(); }}>×</button></span>)}</div><button className="project-upload-picker add-more" type="button" onClick={() => inputRef.current?.click()} disabled={submitting || files.length >= maxFiles}>Tambah berkas</button></>}
          </div>
          <p id="project-file-error" className="file-rejection" role="alert">{fileError}</p>
        </section> : <section className="quick-demo-source" aria-label="Sumber Simulasi Cepat"><b>Registrasi Digital UMKM</b><p>Telusuri graf kebijakan, persona sintetis, dinamika respons, laporan, dan interaksi dalam satu alur.</p></section>}
        <section className="create-console-section">
          <header><b>TUJUAN SIMULASI</b><span>PERTANYAAN ANALISIS</span></header>
          <textarea value={objective} onChange={(event) => { setObjective(event.target.value); markFormChanged(); }} rows={7} required disabled={submitting || workflowMode === "quick_demo"} placeholder="Jelaskan hal yang ingin diuji melalui simulasi skenario..." />
        </section>
        {error && <p className="inline-alert error" role="alert">{error}</p>}
        {submitting && <div className="create-submit-status"><div className="create-submit-status-heading" aria-live="polite" aria-atomic="true"><b>{phaseLabels[submitPhase]}</b><span>{submitPhase === "uploading" ? `${uploadProgress}%` : submitPhase === "processing" ? "Memproses" : ""}</span></div><div className={`create-upload-progress ${submitPhase !== "uploading" ? "indeterminate" : ""}`} role="progressbar" aria-label="Progres pembuatan proyek" aria-valuemin={0} aria-valuemax={100} aria-valuenow={submitPhase === "uploading" ? uploadProgress : undefined}><span style={{ width: `${submitPhase === "uploading" ? uploadProgress : 100}%` }} /></div></div>}
        <button className={`button primary create-project-submit ${submitting ? "loading" : ""}`} type="submit" disabled={submitting || !projectName.trim() || !institution.trim() || !objective.trim() || (workflowMode === "full_simulation" && files.length === 0)}><span>{workflowMode === "quick_demo" ? "Mulai Simulasi Cepat →" : "Buat Proyek & Bangun Graf →"}</span>{submitting && <small>{phaseLabels[submitPhase]}</small>}</button>
      </form>
    </section>
  </AppShell>;
}
