import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import { AppShell } from "../../components/AppShell/AppShell";
import { saveProjectIntake } from "../SimulationWorkflow/projectIntake";
import "./ProjectWizard.css";

const workflow = [
  ["01", "Graph Build", "Menyusun ontologi, stakeholder, dan relasi kebijakan."],
  ["02", "Env Setup", "Membentuk persona sintetis dan konfigurasi skenario."],
  ["03", "Simulation", "Menjalankan event pada dua kanal kebijakan."],
  ["04", "Report", "Menghasilkan laporan dengan jejak bukti."],
  ["05", "Interaction", "Meninjau laporan dan mewawancarai persona."],
] as const;

function navigate(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function ProjectWizardPage() {
  const [projectName, setProjectName] = useState("Registrasi Digital UMKM");
  const [institution, setInstitution] = useState("Dinas Koperasi dan UMKM");
  const [objective, setObjective] = useState("Bagaimana respons pelaku UMKM terhadap kewajiban registrasi digital, dan narasi risiko apa yang perlu diklarifikasi?");
  const [files, setFiles] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const valid = Array.from(list).filter((file) => ["pdf", "md", "txt", "docx"].includes(file.name.split(".").pop()?.toLowerCase() ?? ""));
    setFiles((current) => [...new Set([...current, ...valid.map((file) => file.name)])]);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!projectName.trim() || !institution.trim() || !objective.trim() || files.length === 0) return;
    const slug = projectName.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "proyek-kebijakan";
    const simulationId = `${slug}-${Date.now().toString().slice(-6)}`;
    saveProjectIntake({
      simulationId,
      projectName: projectName.trim(),
      institution: institution.trim(),
      domain: "Kebijakan publik",
      region: "Indonesia",
      period: "2026",
      purpose: objective.trim(),
      question: objective.trim(),
      policySource: files.join(", "),
      framing: {},
      createdAt: new Date().toISOString(),
    });
    navigate(`/simulation/${simulationId}`);
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
      <form className="create-project-console" onSubmit={submit}>
        <div className="create-console-header"><span>PROJECT INPUT</span><span>LOCAL MOCK ENGINE</span></div>
        <div className="create-fields">
          <label className="field"><span>Nama proyek</span><input value={projectName} onChange={(event) => setProjectName(event.target.value)} required /></label>
          <label className="field"><span>Instansi/tim</span><input value={institution} onChange={(event) => setInstitution(event.target.value)} required /></label>
        </div>
        <section className="create-console-section">
          <header><b>SUMBER KEBIJAKAN</b><span>PDF, DOCX, MD, TXT</span></header>
          <button className={`project-upload-zone ${dragging ? "dragging" : ""} ${files.length ? "has-files" : ""}`} type="button" onClick={() => inputRef.current?.click()} onDragOver={(event: DragEvent) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}>
            <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.md,.txt" onChange={(event: ChangeEvent<HTMLInputElement>) => addFiles(event.target.files)} />
            {files.length === 0 ? <><strong>↑</strong><b>Tarik dokumen ke sini atau pilih berkas</b><span>Minimal satu sumber diperlukan untuk membangun graf.</span></> : <div className="project-file-list">{files.map((file) => <span key={file}>{file}<i onClick={(event) => { event.stopPropagation(); setFiles((current) => current.filter((item) => item !== file)); }}>×</i></span>)}</div>}
          </button>
        </section>
        <section className="create-console-section">
          <header><b>TUJUAN SIMULASI</b><span>PERTANYAAN ANALISIS</span></header>
          <textarea value={objective} onChange={(event) => setObjective(event.target.value)} rows={7} required placeholder="Jelaskan hal yang ingin diuji melalui simulasi skenario..." />
        </section>
        <button className="button primary create-project-submit" type="submit" disabled={!projectName.trim() || !institution.trim() || !objective.trim() || files.length === 0}>Buat Proyek & Bangun Graf →</button>
      </form>
    </section>
  </AppShell>;
}
