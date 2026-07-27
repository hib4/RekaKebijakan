import { useNavigate, useParams } from "react-router-dom";
import { useProject, useProvenance } from "../../api/queries";
import { AppShell } from "../../components/AppShell/AppShell";
import "../ProjectDetail/ProjectDetail.css";

export default function ProvenancePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const project = useProject(projectId);
  const provenance = useProvenance(projectId);
  return <AppShell title="Jejak Provenance" subtitle="Telusuri keluaran analisis ke sumber, event, dan versi input yang membentuknya." eyebrow="Workspace kebijakan" actions={<button className="button secondary" onClick={() => navigate(`/projects/${projectId}`)}>Kembali ke workspace</button>}>
    <section className="workspace-top"><div className="workspace-breadcrumb">Proyek Kebijakan / {project.data?.name ?? "Memuat proyek"} / Provenance</div><p>Setiap rantai menampilkan sumber yang dikembalikan API. Kutipan tidak dibuat ulang oleh antarmuka.</p></section>
    <section className="dashboard-panel workspace-panel" style={{ marginTop: 24 }}>
      <div className="panel-heading"><div><h2>Rantai bukti</h2><p>{provenance.data?.items.length ?? 0} keluaran memiliki jejak tersimpan.</p></div></div>
      {provenance.isLoading && <div className="state-block"><h3>Memuat jejak bukti...</h3></div>}
      {provenance.isError && <div className="state-block"><h3>Jejak bukti tidak dapat dimuat</h3><button className="button primary" onClick={() => provenance.refetch()}>Muat ulang</button></div>}
      {provenance.data?.items.length === 0 && <div className="state-block"><h3>Belum ada provenance</h3><p>Jejak akan tersedia setelah graf, simulasi, atau laporan menghasilkan keluaran.</p></div>}
      <div className="workspace-row-list">{provenance.data?.items.map((item) => <article key={item.id}><span>{item.subject_type}</span><div><p><b>{item.label}</b></p>{item.inputs?.map((input) => <p key={`${input.type}-${input.id}`}>{input.type}: {input.label ?? input.id}</p>)}{item.citations.map((citation) => <blockquote key={citation.id ?? `${citation.source_type}-${citation.source_id}`}><b>{citation.label ?? citation.source_id}</b>{citation.quote && <p>“{citation.quote}”</p>}</blockquote>)}</div></article>)}</div>
    </section>
  </AppShell>;
}
