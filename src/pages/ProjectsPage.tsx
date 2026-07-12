import { useEffect, useId, useMemo, useRef, useState } from "react";
import { AppShell } from "../components/AppShell";
import {
  pageSizeOptions,
  policyProjects,
  projectInstitutionOptions,
  projectRiskOptions,
  projectSortOptions,
  projectStatusOptions,
  projectSummary,
} from "../data/projects";
import type { PolicyProject, ProjectRisk, ProjectStatus } from "../data/projects";

type Toast = { id: number; message: string };
type MenuState = { id: string; x: number; y: number } | null;

const riskRank: Record<ProjectRisk, number> = {
  Tinggi: 4,
  Sedang: 3,
  Rendah: 2,
  "Belum dihitung": 1,
};

function goTo(path: string, setToast?: (message: string) => void) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
  setToast?.(`Membuka ${path}. Halaman detail masih berupa placeholder prototipe.`);
}

function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const key = status.toLowerCase().replaceAll(" ", "-");
  return <span className={`project-badge project-status project-status-${key}`}><i aria-hidden="true" />{status}</span>;
}

function RiskBadge({ risk }: { risk: ProjectRisk }) {
  const key = risk.toLowerCase().replaceAll(" ", "-");
  return <span className={`project-badge project-risk project-risk-${key}`}><i aria-hidden="true" />{risk}</span>;
}

function ToastRegion({ toast }: { toast: Toast | null }) {
  return <div className="toast-region" aria-live="polite">{toast && <div className="toast">{toast.message}</div>}</div>;
}

function ArchiveProjectModal({ project, onCancel, onConfirm }: { project: PolicyProject; onCancel: () => void; onConfirm: () => void }) {
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
        <p className="eyebrow">ARSIPKAN PROYEK</p>
        <h2 id={titleId}>Arsipkan {project.name}?</h2>
        <p className="dialog-copy">Proyek akan dipindahkan dari daftar aktif pada prototipe lokal ini. Data mock tidak disimpan permanen.</p>
        <div className="actions">
          <button className="button primary" onClick={onConfirm}>Arsipkan proyek</button>
          <button className="button secondary" onClick={onCancel}>Batal</button>
        </div>
      </section>
    </div>
  );
}

function ProjectActionMenu({ project, menu, setMenu, onOpen, onDuplicate, onArchive }: {
  project: PolicyProject;
  menu: MenuState;
  setMenu: (menu: MenuState) => void;
  onOpen: () => void;
  onDuplicate: () => void;
  onArchive: () => void;
}) {
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const open = () => {
    const rect = buttonRef.current?.getBoundingClientRect();
    setMenu({ id: project.id, x: rect?.right ?? 0, y: rect?.bottom ?? 0 });
  };
  const isOpen = menu?.id === project.id;
  return (
    <div className="project-menu-wrap">
      <button ref={buttonRef} className="kebab-button" aria-label={`Buka menu aksi untuk ${project.name}`} aria-expanded={isOpen} onClick={() => isOpen ? setMenu(null) : open()}>⋮</button>
      {isOpen && (
        <div className="project-menu" role="menu" style={{ top: menu.y, left: menu.x }}>
          <button role="menuitem" onClick={onOpen}>Buka proyek</button>
          <button role="menuitem" onClick={onDuplicate}>Duplikat skenario</button>
          <button role="menuitem" onClick={onArchive}>Arsipkan proyek</button>
        </div>
      )}
    </div>
  );
}

function ProjectFilters({
  query,
  setQuery,
  status,
  setStatus,
  risk,
  setRisk,
  institution,
  setInstitution,
  sort,
  setSort,
  hasFilters,
  reset,
}: {
  query: string;
  setQuery: (value: string) => void;
  status: string;
  setStatus: (value: string) => void;
  risk: string;
  setRisk: (value: string) => void;
  institution: string;
  setInstitution: (value: string) => void;
  sort: string;
  setSort: (value: string) => void;
  hasFilters: boolean;
  reset: () => void;
}) {
  return (
    <section className="project-list-toolbar" aria-label="Filter proyek">
      <label className="project-search">Cari proyek<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari nama proyek atau institusi" /></label>
      <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}>{projectStatusOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Risiko<select value={risk} onChange={(event) => setRisk(event.target.value)}>{projectRiskOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Institusi<select value={institution} onChange={(event) => setInstitution(event.target.value)}>{projectInstitutionOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Urutkan<select value={sort} onChange={(event) => setSort(event.target.value)}>{projectSortOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
      {hasFilters && <button className="text-button inline-action" onClick={reset}>Reset filter</button>}
    </section>
  );
}

function ProjectTable({ projects, selected, setSelected, menu, setMenu, onOpen, onDuplicate, onArchive }: {
  projects: PolicyProject[];
  selected: string[];
  setSelected: (ids: string[]) => void;
  menu: MenuState;
  setMenu: (menu: MenuState) => void;
  onOpen: (project: PolicyProject) => void;
  onDuplicate: (project: PolicyProject) => void;
  onArchive: (project: PolicyProject) => void;
}) {
  const toggle = (id: string) => setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);
  return (
    <div className="project-table-wrap">
      <table className="data-table project-table">
        <thead><tr><th><span className="sr-only">Pilih</span></th><th>Nama proyek</th><th>Institusi</th><th>Status</th><th>Skenario</th><th>Simulasi terakhir</th><th>Risiko tertinggi</th><th>Terakhir diperbarui</th><th>Aksi</th></tr></thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td><input type="checkbox" checked={selected.includes(project.id)} onChange={() => toggle(project.id)} aria-label={`Pilih ${project.name}`} /></td>
              <td><button className="project-name-button" onClick={() => onOpen(project)}>{project.name}</button></td>
              <td>{project.institution}</td>
              <td><ProjectStatusBadge status={project.status} /></td>
              <td>{project.scenarios}</td>
              <td>{project.lastSimulation}</td>
              <td><RiskBadge risk={project.risk} /></td>
              <td>{project.updated}</td>
              <td><ProjectActionMenu project={project} menu={menu} setMenu={setMenu} onOpen={() => onOpen(project)} onDuplicate={() => onDuplicate(project)} onArchive={() => onArchive(project)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProjectCards({ projects, menu, setMenu, onOpen, onDuplicate, onArchive }: {
  projects: PolicyProject[];
  menu: MenuState;
  setMenu: (menu: MenuState) => void;
  onOpen: (project: PolicyProject) => void;
  onDuplicate: (project: PolicyProject) => void;
  onArchive: (project: PolicyProject) => void;
}) {
  return (
    <div className="project-card-list">
      {projects.map((project) => (
        <article className="project-card" key={project.id}>
          <div className="project-card-top"><div><button className="project-name-button" onClick={() => onOpen(project)}>{project.name}</button><p>{project.institution}</p></div><ProjectActionMenu project={project} menu={menu} setMenu={setMenu} onOpen={() => onOpen(project)} onDuplicate={() => onDuplicate(project)} onArchive={() => onArchive(project)} /></div>
          <div className="project-card-meta"><ProjectStatusBadge status={project.status} /><RiskBadge risk={project.risk} /></div>
          <div className="project-card-grid"><span>Skenario<b>{project.scenarios}</b></span><span>Terakhir diperbarui<b>{project.updated}</b></span></div>
          <button className="button primary" onClick={() => onOpen(project)}>Buka proyek</button>
        </article>
      ))}
    </div>
  );
}

function ProjectListState({ type, onReset, onCreate, onReload }: { type: "empty" | "loading" | "error"; onReset?: () => void; onCreate?: () => void; onReload?: () => void }) {
  if (type === "loading") {
    return <div className="project-skeleton" aria-label="Memuat daftar proyek"><span /><span /><span /><span /></div>;
  }
  if (type === "error") {
    return <div className="state-block"><h3>Daftar proyek tidak dapat dimuat</h3><p>Coba muat ulang halaman atau periksa kembali koneksi Anda.</p><button className="button primary" onClick={onReload}>Muat ulang</button></div>;
  }
  return <div className="state-block"><h3>Tidak ada proyek yang sesuai</h3><p>Ubah kata kunci atau filter untuk menemukan proyek yang Anda cari.</p><div className="actions"><button className="button secondary" onClick={onReset}>Reset filter</button><button className="button primary" onClick={onCreate}>Buat Proyek</button></div></div>;
}

function Pagination({ pageSize, setPageSize, total }: { pageSize: number; setPageSize: (value: number) => void; total: number }) {
  return (
    <div className="pagination-bar">
      <span>Halaman 1 dari 1 · {total} proyek</span>
      <div>
        <label>Baris per halaman<select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>{pageSizeOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
        <button className="button secondary" disabled>Sebelumnya</button>
        <button className="button secondary" disabled>Berikutnya</button>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState(policyProjects);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Semua status");
  const [risk, setRisk] = useState("Semua risiko");
  const [institution, setInstitution] = useState("Semua institusi");
  const [sort, setSort] = useState("Terakhir diperbarui");
  const [pageSize, setPageSize] = useState(10);
  const [selected, setSelected] = useState<string[]>([]);
  const [menu, setMenu] = useState<MenuState>(null);
  const [archiveProject, setArchiveProject] = useState<PolicyProject | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && setMenu(null);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  const showToast = (message: string) => {
    setToast({ id: Date.now(), message });
    window.setTimeout(() => setToast(null), 3200);
  };
  const reset = () => {
    setQuery("");
    setStatus("Semua status");
    setRisk("Semua risiko");
    setInstitution("Semua institusi");
    setSort("Terakhir diperbarui");
  };
  const hasFilters = query !== "" || status !== "Semua status" || risk !== "Semua risiko" || institution !== "Semua institusi" || sort !== "Terakhir diperbarui";
  const filtered = useMemo(() => {
    const visible = projects.filter((project) => !project.archived).filter((project) => {
      const matchesQuery = `${project.name} ${project.institution}`.toLowerCase().includes(query.toLowerCase());
      const matchesStatus = status === "Semua status" || project.status === status;
      const matchesRisk = risk === "Semua risiko" || project.risk === risk;
      const matchesInstitution = institution === "Semua institusi" || project.institution === institution;
      return matchesQuery && matchesStatus && matchesRisk && matchesInstitution;
    });
    return [...visible].sort((a, b) => {
      if (sort === "Nama proyek") return a.name.localeCompare(b.name);
      if (sort === "Risiko tertinggi") return riskRank[b.risk] - riskRank[a.risk];
      if (sort === "Status") return a.status.localeCompare(b.status);
      return a.updatedRank - b.updatedRank;
    });
  }, [institution, projects, query, risk, sort, status]);
  const paged = filtered.slice(0, pageSize);
  const openProject = (project: PolicyProject) => {
    setMenu(null);
    goTo(`/projects/${project.id}`, showToast);
  };
  const duplicate = (project: PolicyProject) => {
    setMenu(null);
    showToast(`Skenario pada ${project.name} siap diduplikasi dalam prototipe.`);
  };
  const confirmArchive = () => {
    if (!archiveProject) return;
    setProjects(projects.map((project) => project.id === archiveProject.id ? { ...project, archived: true } : project));
    setArchiveProject(null);
    setMenu(null);
    showToast(`${archiveProject.name} telah diarsipkan.`);
  };

  return (
    <AppShell
      title="Proyek Kebijakan"
      subtitle="Kelola rancangan kebijakan, skenario, dan hasil simulasi dalam satu ruang kerja."
      eyebrow="Ruang kerja kebijakan"
      actions={<><button className="button primary" onClick={() => goTo("/projects/new")}>Buat Proyek</button><button className="button secondary import-button" disabled>Impor Proyek <span>Prototipe</span></button></>}
    >
        <section className="metrics-grid" aria-label="Ringkasan proyek">{projectSummary.map((metric) => <article className="metric-card" key={metric[0]}><p>{metric[0]}</p><strong>{metric[1]}</strong><span>{metric[2]}</span></article>)}</section>
        <section className="dashboard-panel project-list-panel" aria-labelledby="project-table-title">
          <div className="panel-heading"><div><h2 id="project-table-title">Daftar Proyek</h2><p>Tampilan tersimpan: Semua proyek aktif</p></div>{selected.length > 0 && <span className="bulk-note">{selected.length} proyek dipilih · Aksi massal belum aktif</span>}</div>
          <ProjectFilters query={query} setQuery={setQuery} status={status} setStatus={setStatus} risk={risk} setRisk={setRisk} institution={institution} setInstitution={setInstitution} sort={sort} setSort={setSort} hasFilters={hasFilters} reset={reset} />
          {loading && <ProjectListState type="loading" />}
          {error && <ProjectListState type="error" onReload={() => { setError(false); setLoading(true); window.setTimeout(() => setLoading(false), 500); }} />}
          {!loading && !error && paged.length === 0 && <ProjectListState type="empty" onReset={reset} onCreate={() => goTo("/projects/new")} />}
          {!loading && !error && paged.length > 0 && (
            <>
              <ProjectTable projects={paged} selected={selected} setSelected={setSelected} menu={menu} setMenu={setMenu} onOpen={openProject} onDuplicate={duplicate} onArchive={(project) => { setMenu(null); setArchiveProject(project); }} />
              <ProjectCards projects={paged} menu={menu} setMenu={setMenu} onOpen={openProject} onDuplicate={duplicate} onArchive={(project) => { setMenu(null); setArchiveProject(project); }} />
              <Pagination pageSize={pageSize} setPageSize={setPageSize} total={filtered.length} />
            </>
          )}
        </section>
      {archiveProject && <ArchiveProjectModal project={archiveProject} onCancel={() => setArchiveProject(null)} onConfirm={confirmArchive} />}
      <ToastRegion toast={toast} />
    </AppShell>
  );
}
