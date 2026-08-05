import {
  useCallback,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import type { Dispatch, SetStateAction } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  createSimulationInterview,
  getRuntimeGraph,
  getSimulation,
  listSimulationInterviews,
  pauseSimulation,
  resumeSimulation,
  sendInteraction,
  startStage,
  updateEnvironment,
} from "../../api/client";
import type {
  ApiInterviewDto,
  ApiRuntimeGraph,
  ApiSimulationSnapshot,
  SimulationStreamEvent,
} from "../../api/client";
import {
  getWorkspaceProjectBySimulation,
  getWorkspaceReportBySimulation,
  saveWorkspaceReport,
  updateProjectStage,
} from "../../data/localWorkspace";
import {
  demoCases,
  entityTypes as fallbackEntityTypes,
  relationTypes as fallbackRelationTypes,
} from "./workflowData";
import { intakeToDemoCase, loadProjectIntake } from "./projectIntake";
import type {
  ConsoleLog,
  DemoCase,
  ReportSection,
  SimulationEvent,
  ViewMode,
  WorkflowStep,
} from "./workflowTypes";
import {
  PolicyGraph,
  StepCard,
  SystemConsole,
  WorkflowTopBar,
} from "./WorkflowComponents";
import {
  appendSessionLog,
  createWorkflowSession,
  formatTime,
  highestUnlockedStep,
  loadWorkflowSession,
  saveWorkflowSession,
} from "./workflowSession";
import type { InteractionMessage, WorkflowSession } from "./workflowSession";
import { useAutoFollow } from "./useAutoFollow";
import { mapBackendSnapshot, mapInteractionMessage } from "./backendWorkflow";
import { CitationDrawer } from "../../components/CitationDrawer/CitationDrawer";
import { Markdown } from "../../components/Markdown/Markdown";
import {
  mergeRuntimeGraphEvent,
  mergeSimulationStreamEvent,
} from "./simulationStream";
import { useSimulationStream } from "./useSimulationStream";
import "./SimulationWorkflow.css";

const graphTasks = [
  {
    title: "Penyusunan ontologi kebijakan",
    operation: "ONTOLOGY EXTRACTION",
    description:
      "Mengekstrak isu, stakeholder, klausul, kekhawatiran publik, dan narasi risiko.",
  },
  {
    title: "Pembangunan graf stakeholder",
    operation: "GRAPH ASSEMBLY",
    description:
      "Menyusun entity dan relasi menjadi graf kebijakan yang dapat ditinjau.",
  },
  {
    title: "Pembangunan graf selesai",
    operation: "COVERAGE VALIDATION",
    description:
      "Memvalidasi cakupan stakeholder dan jejak bukti sebelum Environment Setup.",
  },
];
const environmentTasks = [
  {
    title: "Buat profil persona",
    operation: "PERSONA GENERATION",
    description:
      "Membentuk persona sintetis berdasarkan kelompok stakeholder yang tersedia.",
  },
  {
    title: "Buat konfigurasi simulasi",
    operation: "CONFIGURATION GENERATION",
    description:
      "Menyiapkan ronde, kanal reaksi, pengaruh, dan respons pemerintah.",
  },
  {
    title: "Lingkungan siap",
    operation: "READINESS VALIDATION",
    description: "Memeriksa cakupan persona dan kesiapan konfigurasi.",
  },
];
const reportTasks = [
  "Perencanaan / kerangka",
  "Pemilihan bukti",
  "Penulisan bagian",
  "Tinjauan risiko",
  "Selesai",
];

function stepQuery(step: WorkflowStep) {
  return ["graph", "environment", "simulation", "report", "interaction"][
    step - 1
  ];
}
function queryStep(value: string | null): WorkflowStep | null {
  const index = [
    "graph",
    "environment",
    "simulation",
    "report",
    "interaction",
  ].indexOf(value ?? "");
  return index >= 0 ? ((index + 1) as WorkflowStep) : null;
}
function queryViewMode(value: string | null): ViewMode | null {
  return value && ["graph", "split", "workbench"].includes(value)
    ? (value as ViewMode)
    : null;
}
function reconcileRoute(session: WorkflowSession, search: string) {
  const params = new URLSearchParams(search);
  const requested = queryStep(params.get("step"));
  const targetStep =
    requested && requested <= highestUnlockedStep(session)
      ? requested
      : session.currentStep;
  const requestedMode = queryViewMode(params.get("mode"));

  return {
    ...session,
    currentStep: targetStep,
    // Report and Interaction always render as Workbench. A generated
    // mode=workbench URL must not overwrite the earlier-stage preference.
    viewMode:
      requestedMode && (targetStep < 4 || requestedMode !== "workbench")
        ? requestedMode
        : session.viewMode,
  };
}
function taskState(progress: number, index: number, running: boolean) {
  const start = index * 33;
  const end = (index + 1) * 33;
  if (progress >= end || (index === 2 && progress === 100))
    return "completed" as const;
  if (running && progress >= start) return "processing" as const;
  return "ready" as const;
}

function hydrateSession(simulationId: string, demo: DemoCase): WorkflowSession {
  const stored = loadWorkflowSession(simulationId);
  const session = stored ?? createWorkflowSession(simulationId, demo.title);
  if (stored) {
    const params = new URLSearchParams(window.location.search);
    const requested = queryStep(params.get("step"));
    const mode = queryViewMode(params.get("mode"));
    if (requested && requested <= highestUnlockedStep(session))
      session.currentStep = requested;
    if (mode && (session.currentStep < 4 || mode !== "workbench"))
      session.viewMode = mode;
    return session;
  }
  const project = getWorkspaceProjectBySimulation(simulationId);
  const report = getWorkspaceReportBySimulation(simulationId);
  const stage = project?.stage ?? 0;
  for (let step = 1; step <= 5; step += 1) {
    const key = step as WorkflowStep;
    if (step <= stage)
      session.steps[key] = {
        status: "completed",
        progress: 100,
        activeTask: null,
        completedAt: project?.updatedAt,
      };
    else if (step === stage + 1)
      session.steps[key] = { status: "ready", progress: 0, activeTask: null };
  }
  if (stage >= 1)
    session.graph = {
      nodeCount: demo.graphNodes.length,
      edgeCount: demo.graphEdges.length,
      selectedNodeId: null,
    };
  if (stage >= 2)
    session.environment.personaCount = demo.personas.reduce(
      (sum, persona) => sum + persona.count,
      0,
    );
  if (stage >= 3)
    session.simulation = {
      ...session.simulation,
      status: "completed",
      eventCount: demo.events.length,
    };
  if (report)
    session.report = {
      progress: 100,
      sections: report.sections,
      timestamps: Array(5).fill(report.completedAt),
      completedAt: report.completedAt,
    };
  session.currentStep = Math.min(5, Math.max(1, stage || 1)) as WorkflowStep;
  const params = new URLSearchParams(window.location.search);
  const requested = queryStep(params.get("step"));
  const mode = queryViewMode(params.get("mode"));
  if (requested && requested <= highestUnlockedStep(session))
    session.currentStep = requested;
  if (mode && (session.currentStep < 4 || mode !== "workbench"))
    session.viewMode = mode;
  return session;
}

function GraphBuildStep({
  demo,
  session,
  entityTypes,
  relationTypes,
  start,
  next,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  entityTypes: string[];
  relationTypes: string[];
  start: () => void;
  next: () => void;
}) {
  const step = session.steps[1];
  const scrollRef = useAutoFollow<HTMLDivElement>(
    `${step.status}-${step.progress}-${session.graph.nodeCount}-${session.graph.edgeCount}`,
  );
  return (
    <div className="step-scroll" ref={scrollRef}>
      <div className="step-intro">
        <span>TAHAP 1/5</span>
        <h1 tabIndex={-1}>Bangun graf kebijakan</h1>
        <p aria-live="polite">
          {step.status === "processing" && step.activeTask
            ? step.activeTask
            : "Entity dan relasi muncul bertahap sesuai proses ekstraksi dan validasi."}
        </p>
      </div>
      {graphTasks.map((task, index) => (
        <StepCard
          key={task.title}
          number={index + 1}
          task={task}
          state={taskState(step.progress, index, step.status === "processing")}
          className={
            task.title === "Pembangunan graf selesai"
              ? "graph-complete-task"
              : undefined
          }
          progress={Math.min(
            100,
            Math.max(0, (step.progress - index * 33) * 3),
          )}
        >
          {index === 0 && step.progress >= 24 && (
            <>
              <h4>Generated entity types</h4>
              <div className="type-tags">
                {entityTypes
                  .slice(0, Math.max(2, Math.ceil(step.progress / 12)))
                  .map((type) => (
                    <span key={type}>{type}</span>
                  ))}
              </div>
              {step.progress >= 33 && (
                <>
                  <h4>Generated relation types</h4>
                  <div className="type-tags relations">
                    {relationTypes.map((type) => (
                      <span key={type}>{type}</span>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
          {index === 1 && step.progress >= 48 && (
            <div className="inline-stats">
              <span>
                <b>{session.graph.nodeCount}</b>Entity nodes
              </span>
              <span>
                <b>{session.graph.edgeCount}</b>Relation edges
              </span>
              <span>
                <b>{entityTypes.length}</b>Schema types
              </span>
            </div>
          )}
          {index === 2 && step.status === "completed" && (
            <div className="completion-review">
              <span>
                <b>100%</b>Stakeholder coverage
              </span>
              <span>
                <b>{demo.risks.length}</b>Narasi risiko
              </span>
              <span>
                <b>0</b>Node terputus
              </span>
            </div>
          )}
        </StepCard>
      ))}
      {step.status === "ready" && (
        <button className="button primary start-action" onClick={start}>
          Mulai membangun graf →
        </button>
      )}
      {step.status === "completed" && (
        <button className="button primary start-action" onClick={next}>
          Lanjut ke penyiapan lingkungan →
        </button>
      )}
    </div>
  );
}

function EnvironmentStep({
  demo,
  session,
  start,
  maxProfileCount,
  rounds,
  useLlmForProfiles,
  useLlmForConfig,
  onMaxProfileCountChange,
  onRoundsChange,
  onUseLlmForProfilesChange,
  onUseLlmForConfigChange,
  next,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  start: () => void;
  maxProfileCount: number;
  rounds: number;
  useLlmForProfiles: boolean;
  useLlmForConfig: boolean;
  onMaxProfileCountChange: (value: number) => void;
  onRoundsChange: (value: number) => void;
  onUseLlmForProfilesChange: (value: boolean) => void;
  onUseLlmForConfigChange: (value: boolean) => void;
  next: () => void;
}) {
  const step = session.steps[2];
  const personaTotal = demo.personas.reduce(
    (sum, persona) => sum + persona.count,
    0,
  );
  const visibleGroups = personaTotal
    ? Math.ceil(
        (session.environment.personaCount / personaTotal) *
          demo.personas.length,
      )
    : 0;
  const scrollRef = useAutoFollow<HTMLDivElement>(
    `${step.status}-${step.progress}-${session.environment.personaCount}`,
  );
  return (
    <div className="step-scroll" ref={scrollRef}>
      <div className="step-intro">
        <span>TAHAP 2/5</span>
        <h1 tabIndex={-1}>Siapkan lingkungan simulasi</h1>
        <p aria-live="polite">
          {step.status === "processing" && step.activeTask
            ? step.activeTask
            : "Graf kebijakan tetap menjadi sumber tinjauan. OASIS membentuk graf runtime Zep terpisah untuk persona, relasi hasil ekstraksi, dan memori simulasi."}
        </p>
      </div>
      {environmentTasks.map((task, index) => (
        <StepCard
          key={task.title}
          number={index + 1}
          task={task}
          state={taskState(step.progress, index, step.status === "processing")}
          progress={Math.min(
            100,
            Math.max(0, (step.progress - index * 33) * 3),
          )}
        >
          {index === 0 && step.progress > 0 && (
            <>
              <div className="persona-summary">
                <span>
                  <b>{session.environment.personaCount}</b>Persona saat ini
                </span>
                <span>
                  <b>{session.environment.personaCount}</b>Profil runtime aktif
                </span>
                <span>
                  <b>
                    {
                      demo.personas
                        .slice(0, visibleGroups)
                        .flatMap((persona) => persona.topics).length
                    }
                  </b>
                  Topik terkait
                </span>
                <span>
                  <b>
                    {Math.min(demo.personas.length, visibleGroups)}/
                    {demo.personas.length}
                  </b>
                  Cakupan stakeholder
                </span>
              </div>
              <div className="persona-list">
                {demo.personas.slice(0, visibleGroups).map((persona) => (
                  <article key={persona.id}>
                    <div>
                      <b>{persona.name}</b>
                      <span>
                        {persona.group} · {persona.role}
                      </span>
                    </div>
                    <strong>{persona.count} persona</strong>
                    <p>{persona.concern}</p>
                    <div>
                      {persona.topics.map((topic) => (
                        <i key={topic}>{topic}</i>
                      ))}
                    </div>
                    <CitationDrawer
                      citations={persona.citations}
                      label="Lihat sumber persona"
                    />
                  </article>
                ))}
              </div>
            </>
          )}
          {index === 1 && step.progress >= 50 && (
            <>
              <div className="config-controls">
                <span>
                  <small>Generated rounds</small>
                  <b>{session.environment.rounds}</b>
                </span>
                <span>
                  <small>Simulated time</small>
                  <b>{session.environment.totalSimulationHours ?? "–"} jam</b>
                </span>
                <span>
                  <small>Time step</small>
                  <b>
                    {session.environment.minutesPerRound ?? "–"} menit/round
                  </b>
                </span>
              </div>
              <div className="config-grid">
                <span>
                  <small>Reaction channels</small>
                  <b>{session.environment.platforms.join(" · ")}</b>
                </span>
                <span>
                  <small>Influence mode</small>
                  <b>OASIS agent config</b>
                </span>
                <span>
                  <small>Output mode</small>
                  <b>Jejak bukti</b>
                </span>
                <span>
                  <small>Scenario</small>
                  <b>{demo.title}</b>
                </span>
              </div>
            </>
          )}
        </StepCard>
      ))}
      <p className="responsible-note">
        Persona bersifat sintetis dan digunakan untuk simulasi skenario, bukan
        profil warga nyata.
      </p>
      {step.status === "ready" && (
        <div className="environment-start-controls">
          <label>
            <span>Jumlah ronde simulasi</span>
            <input
              type="number"
              min="1"
              max="1000"
              value={rounds}
              onChange={(event) =>
                onRoundsChange(
                  Math.max(1, Math.min(1000, Number(event.target.value) || 1)),
                )
              }
            />
          </label>
          <label>
            <span>Jumlah maksimum profil</span>
            <input
              type="number"
              min="1"
              max="500"
              value={maxProfileCount}
              onChange={(event) =>
                onMaxProfileCountChange(
                  Math.max(1, Math.min(500, Number(event.target.value) || 1)),
                )
              }
            />
          </label>
          <label className="profile-llm-toggle">
            <input
              type="checkbox"
              checked={useLlmForProfiles}
              onChange={(event) =>
                onUseLlmForProfilesChange(event.target.checked)
              }
            />
            <span>Perkaya setiap profil dengan LLM (lebih lambat)</span>
          </label>
          <label className="profile-llm-toggle">
            <input
              type="checkbox"
              checked={useLlmForConfig}
              onChange={(event) =>
                onUseLlmForConfigChange(event.target.checked)
              }
            />
            <span>Perkaya konfigurasi simulasi dengan LLM (lebih lambat)</span>
          </label>
          <button className="button primary start-action" onClick={start}>
            Siapkan lingkungan OASIS →
          </button>
        </div>
      )}
      {step.status === "completed" && (
        <button className="button primary start-action" onClick={next}>
          Mulai simulasi →
        </button>
      )}
    </div>
  );
}

const actionLabels: Record<string, string> = {
  CREATE_POST: "Publikasi",
  QUOTE_POST: "Kutipan",
  REPOST: "Bagikan ulang",
  LIKE_POST: "Reaksi",
  LIKE_COMMENT: "Reaksi",
  CREATE_COMMENT: "Komentar",
  SEARCH_POSTS: "Pencarian",
  FOLLOW: "Mengikuti",
  UPVOTE_POST: "Dukung",
  DOWNVOTE_POST: "Tolak",
  DO_NOTHING: "Tanpa aksi",
};

function actionValue(event: SimulationEvent, key: string) {
  const value = event.actionArgs?.[key];
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : "";
}

function ActionContent({ event }: { event: SimulationEvent }) {
  const type = event.type.toUpperCase();
  const content = actionValue(event, "content") || event.statement;
  const originalContent = actionValue(event, "original_content");
  const postContent = actionValue(event, "post_content");
  const originalAuthor = actionValue(event, "original_author_name");
  if (type === "QUOTE_POST") {
    return (
      <>
        <p>{actionValue(event, "quote_content") || content}</p>
        {originalContent && (
          <blockquote>
            <b>{originalAuthor || "Persona lain"}</b>
            {originalContent}
          </blockquote>
        )}
      </>
    );
  }
  if (type === "REPOST") {
    return (
      <div className="event-action-context">
        <b>
          Membagikan ulang{" "}
          {originalAuthor ? `dari ${originalAuthor}` : "publikasi lain"}
        </b>
        {originalContent && <p>{originalContent}</p>}
      </div>
    );
  }
  if (type === "LIKE_POST" || type === "LIKE_COMMENT") {
    return (
      <div className="event-action-context">
        <b>Memberi reaksi pada publikasi</b>
        {postContent && <p>{postContent}</p>}
      </div>
    );
  }
  if (type === "SEARCH_POSTS") {
    return (
      <div className="event-action-context">
        <b>Menelusuri percakapan</b>
        <p>“{actionValue(event, "query") || "Kueri tidak tersedia"}”</p>
      </div>
    );
  }
  if (type === "FOLLOW") {
    return (
      <div className="event-action-context">
        <b>
          Mengikuti{" "}
          {actionValue(event, "target_user") ||
            actionValue(event, "user_id") ||
            "persona lain"}
        </b>
      </div>
    );
  }
  if (type === "UPVOTE_POST" || type === "DOWNVOTE_POST") {
    return (
      <div className="event-action-context">
        <b>
          {type === "UPVOTE_POST" ? "Mendukung" : "Menolak"} sebuah publikasi
        </b>
        {postContent && <p>{postContent}</p>}
      </div>
    );
  }
  if (type === "DO_NOTHING") {
    return (
      <div className="event-action-context muted">
        <b>Persona tidak mengambil aksi pada ronde ini.</b>
      </div>
    );
  }
  return <p>{content}</p>;
}

function EventCard({
  event,
  selected,
  onSelect,
}: {
  event: SimulationEvent;
  selected: boolean;
  onSelect: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article
      className={`simulation-event ${selected ? "selected" : ""}`}
      onClick={onSelect}
      aria-label={`${event.persona}, ${actionLabels[event.type.toUpperCase()] ?? event.type}, ronde ${event.round}`}
    >
      <header>
        <div className="event-persona">
          <span className="event-avatar" aria-hidden="true">
            {event.persona.charAt(0).toUpperCase()}
          </span>
          <span>
            <b>{event.persona}</b>
            <small>{event.group}</small>
          </span>
        </div>
        <span className="event-action-label">
          {actionLabels[event.type.toUpperCase()] ?? event.type}
        </span>
      </header>
      <div className="event-content">
        <ActionContent event={event} />
      </div>
      <div className="event-tags">
        <span>Sikap: {event.stance}</span>
        {event.concerns.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <footer className="event-footer">
        <div className="event-footer-meta">
          <span>{event.channel}</span>
          <time>Ronde {event.round}</time>
          <time>{formatCompactTimestamp(event.time)}</time>
        </div>
        <div
          className="event-footer-actions"
          onClick={(click) => click.stopPropagation()}
        >
          <button
            aria-expanded={open}
            onClick={(click) => {
              click.stopPropagation();
              setOpen(!open);
            }}
          >
            {open ? "Tutup detail" : "Detail risiko"}
          </button>
          <CitationDrawer citations={event.citations} label="Bukti" />
        </div>
      </footer>
      {open && (
        <dl>
          <dt>Narasi risiko</dt>
          <dd>{event.riskNarrative}</dd>
          <dt>Sumber pengaruh</dt>
          <dd>{event.influenceSource}</dd>
        </dl>
      )}
    </article>
  );
}

function formatSimulatedTime(round: number, minutesPerRound?: number) {
  const minutes = round * (minutesPerRound ?? 30);
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function formatCompactTimestamp(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return value;
  const [, year, month, day, hour, minute] = match;
  return `${day}/${month}/${year.slice(2)} ${hour}:${minute}`;
}

function runStatusLabel(status: WorkflowSession["simulation"]["status"]) {
  return {
    ready: "Siap dimulai",
    running: "Berjalan",
    paused: "Dijeda",
    completed: "Selesai",
    stale: "Perlu diperbarui",
    cancelled: "Dibatalkan",
    failed: "Gagal",
  }[status];
}

const chatScrollAnimations = new WeakMap<HTMLDivElement, number>();

function scrollChatToBottom(container: HTMLDivElement | null) {
  if (!container) return;
  const target = Math.max(0, container.scrollHeight - container.clientHeight);
  const start = container.scrollTop;
  const distance = target - start;
  if (Math.abs(distance) < 1) return;

  const activeAnimation = chatScrollAnimations.get(container);
  if (activeAnimation !== undefined) window.cancelAnimationFrame(activeAnimation);

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    container.scrollTop = target;
    return;
  }

  const duration = 800;
  const startedAt = window.performance.now();
  const animate = (now: number) => {
    const progress = Math.min(1, (now - startedAt) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    container.scrollTop = start + distance * eased;
    if (progress < 1) {
      chatScrollAnimations.set(container, window.requestAnimationFrame(animate));
    } else {
      container.scrollTop = target;
      chatScrollAnimations.delete(container);
    }
  };

  chatScrollAnimations.set(container, window.requestAnimationFrame(animate));
}

function SimulationStep({
  demo,
  session,
  update,
  start,
  report,
  localMode,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  update: (session: WorkflowSession) => void;
  start: () => void;
  report: () => void;
  localMode: boolean;
}) {
  const run = session.simulation;
  const step = session.steps[3];
  const events = demo.events.slice(0, run.eventCount);
  const round =
    run.status === "completed"
      ? session.environment.rounds
      : Math.max(1, run.currentRound ?? events.at(-1)?.round ?? 1);
  const activeNode = session.graph.selectedNodeId;
  const terminalIssue =
    run.status === "failed" ||
    run.status === "cancelled" ||
    run.status === "stale";
  const feedRef = useAutoFollow<HTMLDivElement>(
    `${run.status}-${events.length}`,
  );
  return (
    <div className="step-scroll simulation-step">
      <header className="simulation-run-header">
        <div className="step-intro">
          <span>TAHAP 3/5 · SIMULASI PERSONA SINTETIS</span>
          <h1 tabIndex={-1}>Pantau dinamika skenario</h1>
          <p>{demo.question}</p>
        </div>
        <div className={`run-state ${run.status}`} aria-live="polite">
          <i aria-hidden="true" />
          <span>Status run</span>
          <b>{runStatusLabel(run.status)}</b>
        </div>
      </header>

      {run.status === "ready" && (
        <section
          className="simulation-start-review"
          aria-labelledby="start-review-title"
        >
          <div>
            <h2 id="start-review-title">
              Periksa konfigurasi sebelum menjalankan
            </h2>
            <p>
              {session.environment.personaCount} persona sintetis akan
              berinteraksi selama {session.environment.rounds} ronde di{" "}
              {session.environment.platforms.length} kanal. Aktivitas ini adalah
              eksplorasi skenario, bukan prediksi opini publik.
            </p>
          </div>
          <button className="button primary" onClick={start}>
            Mulai simulasi →
          </button>
        </section>
      )}

      {terminalIssue && (
        <section className={`simulation-run-notice ${run.status}`} role="alert">
          <div>
            <h2>{runStatusLabel(run.status)}</h2>
            <p>
              {run.error ||
                run.staleReason ||
                step.error ||
                step.staleReason ||
                "Run berhenti sebelum seluruh ronde selesai. Periksa konsol sistem sebelum menjalankan ulang."}
            </p>
          </div>
        </section>
      )}

      <section className="channel-grid" aria-label="Status kanal simulasi">
        {session.environment.platforms.map((channel) => {
          const count = events.filter(
            (event) => event.channel === channel,
          ).length;
          const lastRound =
            run.platformRounds?.[channel] ??
            events.filter((event) => event.channel === channel).at(-1)?.round ??
            0;
          return (
            <article
              key={channel}
              className={run.status === "running" ? "active" : ""}
            >
              <header>
                <div>
                  <span>Kanal simulasi</span>
                  <h3>{channel}</h3>
                </div>
                <span className={run.status}>
                  <i aria-hidden="true" />
                  {runStatusLabel(run.status)}
                </span>
              </header>
              <dl>
                <div>
                  <dt>Ronde</dt>
                  <dd>
                    {lastRound}/{session.environment.rounds}
                  </dd>
                </div>
                <div>
                  <dt>Waktu simulasi</dt>
                  <dd>
                    {formatSimulatedTime(
                      lastRound,
                      session.environment.minutesPerRound,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Aksi/event</dt>
                  <dd>{count}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </section>
      <section
        className="workflow-simulation-summary"
        aria-label="Kontrol dan progres run"
      >
        <span>
          <b>{events.length}</b>Total event
        </span>
        <span>
          <b>
            {round}/{session.environment.rounds}
          </b>
          Progres ronde
        </span>
        <span>
          <b>
            {formatSimulatedTime(round, session.environment.minutesPerRound)}
          </b>
          Waktu simulasi
        </span>
        {localMode && (
          <label>
            Kecepatan demo
            <select
              value={run.speed}
              onChange={(event) =>
                update({
                  ...session,
                  simulation: {
                    ...run,
                    speed: Number(event.target.value) as 0.5 | 1 | 2,
                  },
                })
              }
            >
              <option value="0.5">0.5x</option>
              <option value="1">1x</option>
              <option value="2">2x</option>
            </select>
          </label>
        )}
        {run.status === "running" && (
          <button
            className="button secondary"
            onClick={() =>
              update(
                appendSessionLog(
                  {
                    ...session,
                    simulation: { ...run, status: "paused" },
                    steps: {
                      ...session.steps,
                      3: { ...session.steps[3], status: "paused" },
                    },
                  },
                  "Simulation paused",
                ),
              )
            }
          >
            Jeda
          </button>
        )}
        {run.status === "paused" && (
          <>
            <button
              className="button primary"
              onClick={() =>
                update(
                  appendSessionLog(
                    {
                      ...session,
                      simulation: { ...run, status: "running" },
                      steps: {
                        ...session.steps,
                        3: { ...session.steps[3], status: "processing" },
                      },
                    },
                    "Simulation resumed",
                  ),
                )
              }
            >
              Lanjutkan
            </button>
            {localMode && (
              <button
                className="button secondary"
                onClick={() =>
                  update({
                    ...session,
                    simulation: {
                      ...run,
                      eventCount: Math.min(
                        demo.events.length,
                        run.eventCount + 1,
                      ),
                    },
                  })
                }
              >
                Event berikutnya
              </button>
            )}
          </>
        )}
      </section>
      <div className="simulation-timeline-heading">
        <div>
          <h2>Linimasa aktivitas sintetis</h2>
          <p>
            Event diurutkan secara kronologis dan dipisahkan berdasarkan kanal.
          </p>
        </div>
        <span>{events.length} event diterima</span>
      </div>
      <div
        className="event-feed"
        ref={feedRef}
        aria-live="polite"
        aria-label="Linimasa event simulasi"
      >
        {events.length ? (
          events.map((event, index) => {
            const channelIndex = Math.max(
              0,
              session.environment.platforms.indexOf(event.channel),
            );
            return (
              <div
                className={`event-feed-item lane-${channelIndex % 2 === 0 ? "left" : "right"}`}
                key={event.id}
              >
                <span className="timeline-marker" aria-hidden="true">
                  {index + 1}
                </span>
                <EventCard
                  event={event}
                  selected={
                    activeNode ===
                    event.group.toLowerCase().replaceAll(" ", "-")
                  }
                  onSelect={() =>
                    update({
                      ...session,
                      graph: {
                        ...session.graph,
                        selectedNodeId:
                          demo.graphNodes.find(
                            (node) => node.group === event.group,
                          )?.id ?? null,
                      },
                    })
                  }
                />
              </div>
            );
          })
        ) : (
          <div className="workflow-empty">
            <i aria-hidden="true" />
            <h3>
              {run.status === "ready"
                ? "Simulasi menunggu konfirmasi"
                : "Menunggu aktivitas persona"}
            </h3>
            <p>
              {run.status === "ready"
                ? "Tinjau konfigurasi di atas, lalu mulai simulasi saat siap."
                : "Event, pengaruh, dan perubahan risiko akan muncul di linimasa ini."}
            </p>
          </div>
        )}
      </div>
      {run.status === "completed" && (
        <div className="simulation-complete-action">
          <button className="button primary" onClick={report}>
            Buka laporan →
          </button>
        </div>
      )}
    </div>
  );
}

function ReportPreview({
  demo,
  sections,
  pendingCount = 0,
}: {
  demo: DemoCase;
  sections: ReportSection[];
  pendingCount?: number;
}) {
  return (
    <article className="report-preview">
      <header>
        <span>LAPORAN SIMULASI KEBIJAKAN</span>
        <h1>{demo.reportTitle}</h1>
        <p>
          Disusun dari simulasi skenario · {demo.events.length} event ·{" "}
          {demo.personas.reduce((sum, persona) => sum + persona.count, 0)}{" "}
          persona sintetis
        </p>
      </header>
      {demo.reportSections.map((section, index) => {
        const stored = sections.find((item) => item.id === section.id);
        return (
          <section key={section.id} className={stored ? "visible" : "pending"}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h2>{section.title}</h2>
              {stored ? (
                <>
                  <Markdown>{stored.content.join("\n\n")}</Markdown>
                  <CitationDrawer
                    citations={stored.citations}
                    label="Lihat sumber bagian"
                  />
                </>
              ) : (
                <p>
                  {index === pendingCount
                    ? "Sedang menyusun bagian dan menghubungkan jejak bukti..."
                    : "Menunggu penulisan bagian..."}
                </p>
              )}
            </div>
          </section>
        );
      })}
    </article>
  );
}

function ReportStep({
  demo,
  session,
  start,
  next,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  start: () => void;
  next: () => void;
}) {
  const step = session.steps[4];
  const scrollRef = useAutoFollow<HTMLElement>(
    `${step.status}-${session.report.progress}-${session.report.sections.length}`,
  );
  return (
    <div className="report-workbench">
      <ReportPreview
        demo={demo}
        sections={session.report.sections}
        pendingCount={session.report.sections.length}
      />
      <aside className="report-progress" ref={scrollRef}>
        <div className="step-intro">
          <span>TAHAP 4/5</span>
          <h1 tabIndex={-1}>Susun laporan kebijakan</h1>
          <p aria-live="polite">
            {step.status === "processing" && step.activeTask
              ? step.activeTask
              : "Dokumen dan jejak proses diperbarui dari artefak yang sama."}
          </p>
        </div>
        <div className="report-metrics">
          <span>
            <b>
              {session.report.sections.length}/{demo.reportSections.length}
            </b>
            Bagian selesai
          </span>
          <span>
            <b>{demo.events.length}</b>Event dipilih
          </span>
          <span>
            <b>{session.report.progress}%</b>Progres
          </span>
        </div>
        <div className="progress-timeline">
          {reportTasks.map((task, index) => {
            const threshold = (index + 1) * 20;
            const complete = session.report.progress >= threshold;
            const active =
              step.status === "processing" &&
              session.report.progress >= index * 20 &&
              !complete;
            return (
              <article
                key={task}
                className={
                  complete ? "complete" : active ? "processing" : "ready"
                }
              >
                <i>{complete ? "✓" : index + 1}</i>
                <div>
                  <b>{task}</b>
                  <span>
                    {complete
                      ? `${session.report.timestamps[index] ?? "--"} · selesai`
                      : active
                        ? "Sedang diproses"
                        : "Menunggu"}
                  </span>
                </div>
              </article>
            );
          })}
        </div>
        {step.status === "ready" && (
          <button className="button primary" onClick={start}>
            Susun laporan →
          </button>
        )}
        {step.status === "completed" && (
          <>
            <span className="report-complete-badge">
              ✓ Laporan selesai dan tersimpan
            </span>
            <button className="button primary" onClick={next}>
              Buka interaksi →
            </button>
          </>
        )}
      </aside>
    </div>
  );
}

const tools = [
  ["report", "Tanya laporan"],
  ["persona", "Wawancara persona"],
  ["multi", "Beberapa persona"],
  ["evidence", "Telusuri bukti"],
  ["risk", "Analisis risiko"],
  ["compare", "Bandingkan"],
  ["revision", "Susun revisi"],
] as const;

type InteractionTool = (typeof tools)[number][0];

function interactionSuggestions(
  tool: InteractionTool,
  demo: DemoCase,
  personaName?: string,
) {
  if (tool === "persona")
    return [
      `Apa kekhawatiran utama ${personaName ?? "persona ini"}?`,
      "Asumsi apa yang paling memengaruhi respons Anda?",
      "Klarifikasi apa yang dapat mengubah sikap Anda?",
    ];
  if (tool === "multi")
    return [
      "Bagian kebijakan mana yang paling membutuhkan klarifikasi?",
      "Apa dampak tidak langsung yang mungkin terlewat?",
      "Perubahan apa yang paling membantu kelompok Anda?",
    ];
  if (tool === "risk")
    return demo.risks
      .slice(0, 3)
      .map((risk) => `Bagaimana memitigasi risiko “${risk.title}”?`);
  if (tool === "evidence")
    return [
      "Bukti apa yang mendukung temuan utama?",
      "Temuan mana yang hanya berasal dari simulasi?",
      "Di mana terdapat kesenjangan bukti?",
    ];
  if (tool === "compare")
    return [
      "Apa perbedaan utama baseline dan revisi?",
      "Asumsi mana yang paling mengubah hasil?",
      "Apa trade-off dari skenario revisi?",
    ];
  if (tool === "revision")
    return [
      "Susun tiga prioritas revisi.",
      "Bahasa kebijakan mana yang perlu diperjelas?",
      "Indikator evaluasi apa yang perlu ditambahkan?",
    ];
  return [
    `Apa temuan utama dari ${demo.reportTitle}?`,
    demo.risks[0]
      ? `Mengapa risiko “${demo.risks[0].title}” muncul?`
      : "Apa risiko utama dalam laporan?",
    "Apa yang perlu divalidasi melalui konsultasi publik?",
  ];
}

function InteractionStep({
  demo,
  session,
  update,
  sendBackend,
  simulationId,
  localMode,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  update: Dispatch<SetStateAction<WorkflowSession>>;
  sendBackend?: (
    tool: string,
    question: string,
    group: string,
  ) => Promise<InteractionMessage>;
  simulationId: string;
  localMode: boolean;
}) {
  const [tool, setTool] = useState<InteractionTool>("report");
  const [personaId, setPersonaId] = useState(demo.personas[0]?.id ?? "");
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<string[]>(
    demo.personas[0] ? [demo.personas[0].id] : [],
  );
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [sendError, setSendError] = useState("");
  const [interviews, setInterviews] = useState<ApiInterviewDto[]>([]);
  const [interviewsLoading, setInterviewsLoading] = useState(false);
  const timer = useRef<number | null>(null);
  const selectedPersona =
    demo.personas.find((persona) => persona.id === personaId) ??
    demo.personas[0];
  const suggestions = interactionSuggestions(tool, demo, selectedPersona?.name);
  const threadMessages = session.interaction.messages.filter(
    (message) =>
      (message.tool === tool ||
        (tool === "persona" && message.tool === "persona")) &&
      (tool !== "persona" ||
        !message.personaGroup ||
        message.personaGroup === selectedPersona?.group),
  );
  const visibleInterviews = interviews.filter(
    (interview) =>
      tool === "multi" ||
      interview.answers.some((answer) => answer.persona_id === personaId),
  );
  const scrollRef = useAutoFollow<HTMLDivElement>(
    `${tool}-${personaId}-${typing}-${session.interaction.messages.length}-${interviews.length}`,
    { force: true },
  );
  useEffect(() => {
    scrollChatToBottom(scrollRef.current);
  }, [scrollRef, tool, personaId, typing, threadMessages.length, visibleInterviews.length]);
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );
  useEffect(() => {
    if (localMode || (tool !== "persona" && tool !== "multi")) return;
    let active = true;
    listSimulationInterviews(simulationId)
      .then((response) => {
        if (active) setInterviews(response.items);
      })
      .catch(() => {
        if (active) setSendError("Riwayat wawancara belum dapat dimuat.");
      })
      .finally(() => {
        if (active) setInterviewsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [localMode, simulationId, tool]);
  const answer = (question: string) => {
    if (tool === "persona")
      return `${selectedPersona?.name} menekankan ${selectedPersona?.concern.toLowerCase()}. Sikap awalnya ${selectedPersona?.stance.toLowerCase()} dan dapat berubah ketika skenario menyediakan klarifikasi yang dapat ditelusuri.`;
    if (tool === "evidence")
      return `Jejak bukti menghubungkan temuan ke event "${demo.events[0]?.statement}", node ${demo.graphNodes[0]?.label}, dan bagian Ringkasan Eksekif.`;
    if (tool === "compare")
      return `Baseline menunjukkan risiko komunikasi lebih tinggi. Pada asumsi revisi, intensitas sosialisasi ${session.environment.socialization.toLowerCase()} dan respons ${session.environment.responseMode.toLowerCase()} menurunkan ketidakpastian stakeholder.`;
    if (tool === "revision")
      return "Prioritas revisi: perjelas ketentuan utama, tetapkan kanal klarifikasi, dan lampirkan indikator evaluasi. Catatan ini didukung event simulasi serta Risiko Narasi Utama.";
    if (tool === "risk")
      return `Mitigasi perlu memprioritaskan ${demo.risks[0]?.title.toLowerCase() ?? "risiko utama"}, memperjelas asumsi implementasi, dan menguji temuan melalui konsultasi dengan kelompok terdampak.`;
    return `Laporan menunjukkan bahwa ${demo.risks[0]?.title.toLowerCase()} merupakan indikasi risiko utama. Temuan ini didukung Bagian 3 dan event pada ronde ${demo.events[0]?.round ?? 1}. Pertanyaan: ${question}`;
  };
  const send = async (question = input) => {
    if (!question.trim() || typing) return;
    if (
      (tool === "persona" && !selectedPersona) ||
      (tool === "multi" && selectedPersonaIds.length === 0)
    )
      return;
    if (tool === "persona" || tool === "multi") {
      setInput("");
      setTyping(true);
      setSendError("");
      scrollChatToBottom(scrollRef.current);
      const ids = tool === "multi" ? selectedPersonaIds : [selectedPersona!.id];
      try {
        const result = localMode
          ? {
              id: `interview-${Date.now()}`,
              question,
              created_at: new Date().toISOString(),
              status: "completed" as const,
              summary: `${ids.length} jawaban persona sintetis`,
              answers: ids.map((id) => {
                const persona = demo.personas.find((item) => item.id === id)!;
                return {
                  id: `answer-${id}-${Date.now()}`,
                  persona_id: id,
                  persona_name: persona.name,
                  question,
                  answer: `${persona.name} menekankan ${persona.concern.toLowerCase()}. Sikapnya ${persona.stance.toLowerCase()} berdasarkan asumsi persona dan event simulasi yang tersedia.`,
                  citations: [],
                };
              }),
            }
          : await createSimulationInterview(simulationId, {
              question,
              personaIds: ids,
            });
        setInterviews((current) => [...current, result]);
        scrollChatToBottom(scrollRef.current);
      } catch (cause) {
        setSendError(
          cause instanceof Error
            ? cause.message
            : "Wawancara persona gagal dikirim.",
        );
      } finally {
        setTyping(false);
        scrollChatToBottom(scrollRef.current);
      }
      return;
    }
    const user: InteractionMessage = {
      id: `u-${tool}-${session.interaction.messages.length}`,
      role: "user",
      author: "Anda",
      tool,
      text: question,
      createdAt: new Date().toISOString(),
    };
    update((current) => ({
      ...current,
      interaction: {
        ...current.interaction,
        messages: [...current.interaction.messages, user],
      },
    }));
    setInput("");
    setTyping(true);
    setSendError("");
    scrollChatToBottom(scrollRef.current);
    if (sendBackend) {
      try {
        const agent = await sendBackend(
          tool,
          question,
          selectedPersona?.group ?? "",
        );
        update((current) => {
          const messages = current.interaction.messages.some(
            (message) => message.id === agent.id,
          )
            ? current.interaction.messages
            : [...current.interaction.messages, agent];
          return appendSessionLog(
            {
              ...current,
              interaction: { ...current.interaction, messages },
            },
            `${agent.author} response generated`,
          );
        });
        scrollChatToBottom(scrollRef.current);
      } catch (cause) {
        setSendError(
          cause instanceof Error ? cause.message : "Interaksi gagal dikirim.",
        );
      } finally {
        setTyping(false);
        scrollChatToBottom(scrollRef.current);
      }
      return;
    }
    timer.current = window.setTimeout(() => {
      const agent: InteractionMessage = {
        id: `a-${tool}-${session.interaction.messages.length + 1}`,
        role: "agent",
        author: tools.find((item) => item[0] === tool)?.[1] ?? "Agen Laporan",
        tool,
        text: answer(question),
        createdAt: new Date().toISOString(),
        citations: [
          {
            sourceType: "report_section",
            sourceId: demo.reportSections[2]?.id ?? "section-3",
            label: "Bagian 3",
          },
          {
            sourceType: "event",
            sourceId: demo.events[0]?.id ?? "01",
            label: `Event ${demo.events[0]?.id ?? "01"}`,
            quote: demo.events[0]?.statement,
          },
        ],
      };
      update((current) =>
        appendSessionLog(
          {
            ...current,
            interaction: {
              ...current.interaction,
              messages: [...current.interaction.messages, agent],
            },
          },
          `${agent.author} response generated`,
        ),
      );
      setTyping(false);
      scrollChatToBottom(scrollRef.current);
    }, 1200);
  };
  return (
    <div className="interaction-workbench">
      <ReportPreview
        demo={demo}
        sections={
          session.report.sections.length
            ? session.report.sections
            : demo.reportSections
        }
      />
      <aside className="interaction-tools">
        <header className="interaction-header">
          <div>
            <span>TAHAP 5/5 · RUANG ANALISIS</span>
            <h1 tabIndex={-1}>Interaksi dengan hasil</h1>
            <p>
              Selidiki laporan, bukti, dan respons persona sintetis tanpa
              kehilangan konteks sumber.
            </p>
          </div>
        </header>
        <nav className="tool-list" aria-label="Mode interaksi">
          {tools
            .filter(([id]) => id !== "persona" && id !== "multi")
            .map(([id, title]) => (
              <button
                key={id}
                aria-current={tool === id ? "page" : undefined}
                className={tool === id ? "active" : ""}
                onClick={() => setTool(id)}
              >
                {title}
              </button>
            ))}
        </nav>
        {tool === "evidence" && (
          <div className="tool-artifact">
            <b>Rantai bukti</b>
            <span>
              Report → Event {demo.events[0]?.id} → {demo.graphNodes[0]?.label}
            </span>
          </div>
        )}
        {tool === "compare" && (
          <div className="scenario-comparison">
            <span>
              <b>Baseline</b>Sosialisasi rendah · risiko meningkat
            </span>
            <span>
              <b>Revisi</b>
              {session.environment.socialization} · respons{" "}
              {session.environment.responseMode}
            </span>
          </div>
        )}
        {tool === "revision" && (
          <div className="tool-artifact">
            <b>Ruang kerja revisi</b>
            <span>
              Catatan dapat diedit melalui percakapan dan diekspor sebagai
              Markdown.
            </span>
          </div>
        )}
        {tool === "risk" && (
          <div className="tool-artifact">
            <b>Risiko yang dianalisis</b>
            <span>
              {demo.risks
                .map((risk) => `${risk.title} (${risk.level})`)
                .join(" · ") || "Belum ada risiko terstruktur."}
            </span>
          </div>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            send();
          }}
        >
          <div className="chat-panel">
            <header className="thread-header">
              <div>
                <span>
                  {tool === "persona"
                    ? "WAWANCARA PERSONA"
                    : tool === "multi"
                      ? "EKSPLORASI MULTI-PERSONA"
                      : "AGEN ANALISIS"}
                </span>
                <h2>
                  {tool === "persona"
                    ? selectedPersona?.name
                    : tools.find(([id]) => id === tool)?.[1]}
                </h2>
              </div>
              <span>
                {tool === "persona" || tool === "multi"
                  ? `${visibleInterviews.length} sesi`
                  : `${threadMessages.length} pesan`}
              </span>
            </header>
            {tool === "persona" && (
              <section
                className="persona-context"
                aria-label="Persona terpilih"
              >
                <label>
                  Persona sintetis
                  <select
                    value={personaId}
                    onChange={(event) => setPersonaId(event.target.value)}
                  >
                    {demo.personas.map((persona) => (
                      <option key={persona.id} value={persona.id}>
                        {persona.name} · {persona.group}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedPersona && (
                  <div className="persona-profile">
                    <span className="persona-profile-avatar" aria-hidden="true">
                      {selectedPersona.name.charAt(0)}
                    </span>
                    <div>
                      <h2>{selectedPersona.name}</h2>
                      <p>
                        {selectedPersona.group} · {selectedPersona.role}
                      </p>
                    </div>
                    <dl>
                      <div>
                        <dt>Sikap</dt>
                        <dd>{selectedPersona.stance}</dd>
                      </div>
                      <div>
                        <dt>Perhatian utama</dt>
                        <dd>{selectedPersona.concern}</dd>
                      </div>
                    </dl>
                    <div className="event-tags">
                      {selectedPersona.topics.map((topic) => (
                        <span key={topic}>{topic}</span>
                      ))}
                    </div>
                    <CitationDrawer
                      citations={selectedPersona.citations}
                      label="Lihat dasar persona"
                    />
                  </div>
                )}
                <p className="responsible-note">
                  Persona ini sintetis dan merupakan alat eksplorasi skenario,
                  bukan profil atau pendapat warga nyata.
                </p>
              </section>
            )}
            {tool === "multi" && (
              <section className="multi-persona-panel">
                <header>
                  <div>
                    <h2>Eksplorasi beberapa persona</h2>
                    <p>
                      Pilih maksimal 10 persona sintetis untuk menjawab
                      pertanyaan yang sama.
                    </p>
                  </div>
                  <span>{selectedPersonaIds.length}/10 dipilih</span>
                </header>
                <div className="multi-persona-actions">
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedPersonaIds(
                        demo.personas.slice(0, 10).map((persona) => persona.id),
                      )
                    }
                  >
                    Pilih semua
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedPersonaIds([])}
                  >
                    Hapus pilihan
                  </button>
                </div>
                <div className="multi-persona-list">
                  {demo.personas.map((persona) => (
                    <label key={persona.id}>
                      <input
                        type="checkbox"
                        checked={selectedPersonaIds.includes(persona.id)}
                        disabled={
                          !selectedPersonaIds.includes(persona.id) &&
                          selectedPersonaIds.length >= 10
                        }
                        onChange={(event) =>
                          setSelectedPersonaIds((current) =>
                            event.target.checked
                              ? [...current, persona.id]
                              : current.filter((id) => id !== persona.id),
                          )
                        }
                      />
                      <span>
                        <b>{persona.name}</b>
                        <small>
                          {persona.group} · {persona.stance}
                        </small>
                      </span>
                    </label>
                  ))}
                </div>
                <p className="responsible-note">
                  Hasil menggambarkan respons persona terpilih dan tidak
                  mewakili survei publik.
                </p>
              </section>
            )}
            <div
              className="chat-messages"
              ref={scrollRef}
              role="log"
              aria-live="polite"
              aria-label="Riwayat interaksi"
            >
              {tool !== "persona" &&
                tool !== "multi" &&
                threadMessages.map((message) => (
                  <div
                    key={message.id}
                    className={`chat-message ${message.role}`}
                  >
                    <span className="message-avatar" aria-hidden="true">
                      {message.role === "user" ? "A" : message.author.charAt(0)}
                    </span>
                    <div>
                      <header>
                        <b>{message.author}</b>
                        <time>
                          {message.createdAt
                            ? formatTime(message.createdAt).slice(11, 16)
                            : ""}
                        </time>
                      </header>
                      <Markdown>{message.text}</Markdown>
                      <CitationDrawer
                        citations={message.citations}
                        label="Lihat sumber jawaban"
                      />
                      {Boolean(
                        (message.toolCalls?.length ?? 0) +
                        (message.sources?.length ?? 0),
                      ) && (
                        <details className="answer-provenance">
                          <summary>Cara jawaban disusun</summary>
                          <p>
                            {message.toolCalls?.length ?? 0} alat digunakan ·{" "}
                            {message.sources?.length ?? 0} sumber runtime
                            ditemukan
                          </p>
                        </details>
                      )}
                    </div>
                  </div>
                ))}
              {(tool === "persona" || tool === "multi") &&
                visibleInterviews.flatMap((interview) =>
                  interview.answers
                    .filter(
                      (item) =>
                        tool === "multi" || item.persona_id === personaId,
                    )
                    .map((item) => (
                      <article className="interview-result" key={item.id}>
                        <header>
                          <span className="message-avatar" aria-hidden="true">
                            {item.persona_name.charAt(0)}
                          </span>
                          <div>
                            <b>{item.persona_name}</b>
                            <time>
                              {formatTime(interview.created_at).slice(0, 16)}
                            </time>
                          </div>
                        </header>
                        <p className="interview-question">
                          {interview.question}
                        </p>
                        <Markdown>{item.answer}</Markdown>
                        {item.citations?.length ? (
                          <CitationDrawer
                            citations={item.citations.map((citation) => ({
                              sourceType: citation.source_type,
                              sourceId: citation.source_id,
                              label: citation.label,
                              quote: citation.quote,
                              locator: citation.locator,
                            }))}
                            label="Lihat dasar jawaban"
                          />
                        ) : null}
                      </article>
                    )),
                )}
              {!typing &&
                !interviewsLoading &&
                (tool === "persona" || tool === "multi"
                  ? visibleInterviews.length === 0
                  : threadMessages.length === 0) && (
                  <div className="chat-empty">
                    <b>Mulai penyelidikan</b>
                    <p>
                      Pilih pertanyaan yang disarankan atau tulis pertanyaan
                      berbasis konteks yang tersedia.
                    </p>
                  </div>
                )}
              {typing && (
                <div className="agent typing" role="status">
                  <b>
                    {tool === "persona"
                      ? selectedPersona?.name
                      : tools.find((item) => item[0] === tool)?.[1]}
                  </b>
                  <span>
                    <i />
                    <i />
                    <i />
                  </span>
                </div>
              )}
            </div>
            <div className="chat-composer">
              {suggestions.length > 0 && (
                <div
                  className="suggested-questions"
                  aria-label="Pertanyaan yang disarankan"
                >
                  {suggestions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => setInput(question)}
                    >
                      <span>{question}</span>
                    </button>
                  ))}
                </div>
              )}
              <div className="chat-input-field">
                <label
                  className="chat-input-label"
                  htmlFor="interaction-question"
                >
                  Pertanyaan
                </label>
                <textarea
                  id="interaction-question"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  placeholder="Ajukan pertanyaan berbasis laporan..."
                  rows={3}
                  maxLength={2000}
                />
              </div>
              {sendError && (
                <p className="interaction-send-error" role="alert">
                  {sendError}
                </p>
              )}
              <div className="chat-composer-footer">
                <span>Enter untuk mengirim · Shift+Enter untuk baris baru</span>
                <span>{input.length}/2000</span>
                <button
                  className="button primary"
                  type="submit"
                  disabled={
                    !input.trim() ||
                    typing ||
                    (tool === "multi" && selectedPersonaIds.length === 0)
                  }
                >
                  {typing ? "Menunggu jawaban..." : "Kirim →"}
                </button>
              </div>
            </div>
          </div>
        </form>
      </aside>
    </div>
  );
}

export default function SimulationWorkflowPage() {
  const { simulationId = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const localMode =
    import.meta.env.VITE_DEMO_MODE === "true" ||
    simulationId.startsWith("demo-");
  const intake = localMode ? loadProjectIntake(simulationId) : null;
  const knownDemo = localMode ? demoCases[simulationId] : undefined;
  const project = localMode
    ? getWorkspaceProjectBySimulation(simulationId)
    : undefined;
  const demo = intake ? intakeToDemoCase(intake) : knownDemo;
  const exists = localMode
    ? Boolean(simulationId && (demo || project))
    : Boolean(simulationId);
  const [resolvedDemo, setResolvedDemo] = useState<DemoCase>(() => {
    if (demo) return demo;
    if (project) return intakeToDemoCase(project);
    return {
      id: simulationId,
      title: "Simulasi kebijakan",
      question: "",
      graphNodes: [],
      graphEdges: [],
      personas: [],
      events: [],
      risks: [],
      reportTitle: "Laporan simulasi",
      reportSections: [],
    };
  });
  const [session, setSession] = useState(() =>
    localMode
      ? hydrateSession(simulationId, resolvedDemo)
      : createWorkflowSession(simulationId, "Simulasi kebijakan"),
  );
  const [backendLoading, setBackendLoading] = useState(!localMode);
  const [backendLoaded, setBackendLoaded] = useState(localMode);
  const [backendError, setBackendError] = useState("");
  const [runtimeDemo, setRuntimeDemo] = useState<DemoCase | null>(null);
  const [runtimeMappingStatus, setRuntimeMappingStatus] = useState("");
  const [policyOntology, setPolicyOntology] = useState<{
    entityTypes: string[];
    relationTypes: string[];
  }>({ entityTypes: [], relationTypes: [] });
  const [graphSource, setGraphSource] = useState<"policy" | "runtime">(
    "policy",
  );
  const backendSnapshotRef = useRef<ApiSimulationSnapshot | null>(null);
  const runtimeGraphRef = useRef<Extract<
    ApiRuntimeGraph,
    { available: true }
  > | null>(null);
  const graphSourceChosen = useRef(false);
  const autoSelectedRuntime = useRef(false);
  const graphSelections = useRef<{
    policy: string | null;
    runtime: string | null;
  }>({ policy: null, runtime: null });
  const [maxProfileCount, setMaxProfileCount] = useState(10);
  const [requestedRounds, setRequestedRounds] = useState<number | null>(null);
  const effectiveRequestedRounds =
    requestedRounds ?? session.environment.rounds;
  const [useLlmForProfiles, setUseLlmForProfiles] = useState(false);
  const [useLlmForConfig, setUseLlmForConfig] = useState(false);
  const latest = useEffectEvent((next: WorkflowSession) => {
    if (localMode) saveWorkflowSession(next);
  });
  useEffect(() => {
    latest(session);
  }, [session]);

  const applyBackendSnapshot = useCallback(
    (snapshot: Awaited<ReturnType<typeof getSimulation>>) => {
      backendSnapshotRef.current = snapshot;
      setPolicyOntology({
        entityTypes:
          snapshot.ontology?.entity_types?.map((type) => type.name) ?? [],
        relationTypes:
          snapshot.ontology?.relation_types?.map((type) => type.name) ?? [],
      });
      setSession((current) => {
        const mapped = mapBackendSnapshot(snapshot, simulationId, current);
        setResolvedDemo(mapped.demo);
        return reconcileRoute(mapped.session, location.search);
      });
      setBackendError("");
      setBackendLoading(false);
      setBackendLoaded(true);
    },
    [location.search, simulationId],
  );
  const loadBackend = useCallback(async () => {
    try {
      applyBackendSnapshot(await getSimulation(simulationId));
    } catch (cause) {
      setBackendError(
        cause instanceof Error ? cause.message : "Simulasi gagal dimuat.",
      );
      setBackendLoading(false);
    }
  }, [applyBackendSnapshot, simulationId]);
  const applyRuntimeGraph = useCallback(
    (graph: Extract<ApiRuntimeGraph, { available: true }>) => {
      runtimeGraphRef.current = graph;
      setRuntimeMappingStatus(graph.mapping_status);
      const graphNodes = graph.nodes.flatMap((node, index) => {
        const id = node.id ?? node.uuid;
        if (!id) return [];
        return [
          {
            id,
            label: node.label ?? node.name ?? id,
            type: node.type ?? node.entity_type ?? node.labels?.[0] ?? "Entity",
            summary:
              node.summary ??
              node.description ??
              "Entitas hasil ekstraksi runtime.",
            x: 100 + (index % 5) * 150,
            y: 80 + Math.floor(index / 5) * 100,
            citations: [],
          },
        ];
      });
      const nodeIds = new Set(graphNodes.map((node) => node.id));
      const graphEdges = graph.edges.flatMap((edge, index) => {
        const source = edge.source ?? edge.source_node_uuid;
        const target = edge.target ?? edge.target_node_uuid;
        if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target))
          return [];
        return [
          {
            id: edge.id ?? edge.uuid ?? `runtime-edge-${index}`,
            source,
            target,
            type:
              edge.type ?? edge.relation_type ?? edge.fact_type ?? "RELATED_TO",
            citations: [],
          },
        ];
      });
      setRuntimeDemo((current) => ({
        ...(current ?? resolvedDemo),
        id: `${simulationId}-runtime`,
        title: `${resolvedDemo.title} · Memori runtime`,
        graphNodes,
        graphEdges,
      }));
      if (
        !graphSourceChosen.current &&
        !autoSelectedRuntime.current &&
        session.currentStep >= 2
      ) {
        autoSelectedRuntime.current = true;
        setGraphSource("runtime");
      }
    },
    [resolvedDemo, session.currentStep, simulationId],
  );
  const loadRuntimeGraph = useCallback(async () => {
    if (localMode) return;
    try {
      const graph = await getRuntimeGraph(simulationId);
      if (!graph.available) return;
      applyRuntimeGraph(graph);
    } catch (cause) {
      // Runtime topology is supplemental; the policy workflow remains usable
      // while Zep is unavailable or before Stage 02 creates the graph.
      if (cause instanceof ApiError && cause.status === 401)
        setBackendError(cause.message);
    }
  }, [applyRuntimeGraph, localMode, simulationId]);
  useEffect(() => {
    if (localMode) return;
    const timer = window.setTimeout(loadBackend, 0);
    return () => window.clearTimeout(timer);
  }, [loadBackend, localMode]);
  const handleStreamEvent = useCallback(
    (message: SimulationStreamEvent) => {
      if (message.type === "graph.snapshot" || message.type === "graph.delta") {
        const current = backendSnapshotRef.current;
        if (current) {
          const policy = mergeSimulationStreamEvent(current, message);
          if (policy !== current) {
            applyBackendSnapshot(policy);
            return;
          }
        }
        const graph = mergeRuntimeGraphEvent(runtimeGraphRef.current, message);
        if (graph) applyRuntimeGraph(graph);
        return;
      }
      const current = backendSnapshotRef.current;
      if (!current) return;
      const merged = mergeSimulationStreamEvent(current, message);
      if (merged !== current) applyBackendSnapshot(merged);
    },
    [applyBackendSnapshot, applyRuntimeGraph],
  );
  const stream = useSimulationStream({
    simulationId,
    enabled: !localMode && backendLoaded,
    onEvent: handleStreamEvent,
  });
  const backendPolling =
    (!localMode &&
      Object.values(session.steps).some(
        (item) => item.status === "processing",
      )) ||
    (!localMode && session.simulation.status === "running");
  useEffect(() => {
    if (!backendPolling || stream.healthy) return;
    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      await loadBackend();
      if (!cancelled) timer = window.setTimeout(poll, 1500);
    };
    timer = window.setTimeout(poll, 1500);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [backendPolling, loadBackend, stream.healthy]);
  const runtimeGraphPolling =
    !localMode && session.steps[2].status !== "locked";
  useEffect(() => {
    if (!runtimeGraphPolling) return;
    const active =
      session.simulation.status === "running" ||
      session.steps[2].status === "processing";
    const initialTimer = window.setTimeout(loadRuntimeGraph, 0);
    const pollTimer =
      active && !stream.healthy
        ? window.setInterval(loadRuntimeGraph, 5000)
        : undefined;
    return () => {
      window.clearTimeout(initialTimer);
      if (pollTimer) window.clearInterval(pollTimer);
    };
  }, [
    loadRuntimeGraph,
    runtimeGraphPolling,
    session.simulation.status,
    session.steps,
    stream.healthy,
  ]);

  const updateWorkflow = (next: WorkflowSession) => {
    if (!localMode && session.simulation.status !== next.simulation.status) {
      const action =
        next.simulation.status === "paused"
          ? pauseSimulation(simulationId)
          : next.simulation.status === "running"
            ? resumeSimulation(simulationId)
            : null;
      if (action)
        action
          .then(applyBackendSnapshot)
          .catch((cause) =>
            setBackendError(
              cause instanceof Error
                ? cause.message
                : "Status simulasi gagal diperbarui.",
            ),
          );
      return;
    }
    setSession(next);
    if (!localMode && next.environment !== session.environment) {
      updateEnvironment(simulationId, {
        rounds: next.environment.rounds,
        socialization: next.environment.socialization,
        response_mode: next.environment.responseMode,
      })
        .then(applyBackendSnapshot)
        .catch((cause) => {
          if (
            !(cause instanceof ApiError) ||
            (cause.status !== 404 && cause.status !== 405)
          )
            setBackendError(
              cause instanceof Error
                ? cause.message
                : "Konfigurasi gagal disimpan.",
            );
        });
    }
  };
  const log = (message: string, level: ConsoleLog["level"] = "INFO") =>
    setSession((current) => appendSessionLog(current, message, level));
  const goStep = (step: WorkflowStep) => {
    if (session.steps[step].status === "locked") return;
    const mode: ViewMode = step >= 4 ? "workbench" : session.viewMode;
    const next = { ...session, currentStep: step };
    setSession(next);
    document.title = `${resolvedDemo.title} · ${stepQuery(step)} · RekaKebijakan`;
    navigate(
      `/simulation/${simulationId}?step=${stepQuery(step)}&mode=${mode}`,
    );
  };
  const setMode = (mode: ViewMode) => {
    if (session.currentStep >= 4) return;
    setSession((current) => ({ ...current, viewMode: mode }));
    navigate(
      `/simulation/${simulationId}?step=${stepQuery(session.currentStep)}&mode=${mode}`,
      { replace: true },
    );
  };
  const syncRoute = useEffectEvent(() => {
    setSession((current) => reconcileRoute(current, location.search));
  });
  useEffect(() => {
    const timer = window.setTimeout(syncRoute, 0);
    return () => window.clearTimeout(timer);
  }, [location.search]);

  useEffect(() => {
    if (!localMode) return;
    const step = session.currentStep;
    const state = session.steps[step];
    if (state.status !== "processing" || step === 3) return;
    const delay = step === 1 ? 360 : step === 2 ? 380 : 330;
    const timer = window.setTimeout(
      () =>
        setSession((current) => {
          const currentState = current.steps[step];
          if (currentState.status !== "processing") return current;
          const progress = Math.min(
            100,
            currentState.progress + (step === 4 ? 4 : 5),
          );
          let next: WorkflowSession = {
            ...current,
            steps: {
              ...current.steps,
              [step]: {
                ...currentState,
                progress,
                activeTask:
                  step === 1
                    ? progress < 33
                      ? "ontology"
                      : progress < 66
                        ? "graph"
                        : "validation"
                    : step === 2
                      ? progress < 50
                        ? "personas"
                        : "config"
                      : progress < 20
                        ? "outline"
                        : progress < 40
                          ? "evidence"
                          : progress < 80
                            ? "writing"
                            : "review",
              },
            },
          };
          if (step === 1)
            next.graph = {
              ...next.graph,
              nodeCount: Math.min(
                resolvedDemo.graphNodes.length,
                Math.floor((progress / 100) * resolvedDemo.graphNodes.length),
              ),
              edgeCount: Math.min(
                resolvedDemo.graphEdges.length,
                Math.floor(
                  (Math.max(0, progress - 28) / 72) *
                    resolvedDemo.graphEdges.length,
                ),
              ),
            };
          if (step === 2)
            next.environment = {
              ...next.environment,
              personaCount: Math.min(
                resolvedDemo.personas.reduce(
                  (sum, persona) => sum + persona.count,
                  0,
                ),
                Math.floor(
                  (progress / 50) *
                    resolvedDemo.personas.reduce(
                      (sum, persona) => sum + persona.count,
                      0,
                    ),
                ),
              ),
            };
          if (step === 4) {
            const sectionCount = Math.min(
              resolvedDemo.reportSections.length,
              Math.floor(
                (Math.max(0, progress - 35) / 65) *
                  (resolvedDemo.reportSections.length + 1),
              ),
            );
            next.report = {
              ...next.report,
              progress,
              sections: resolvedDemo.reportSections.slice(0, sectionCount),
              timestamps:
                progress % 20 < 4
                  ? [
                      ...next.report.timestamps,
                      new Date().toLocaleTimeString("id-ID", { hour12: false }),
                    ]
                  : next.report.timestamps,
            };
          }
          if (progress % 20 === 0)
            next = appendSessionLog(
              next,
              `${stepQuery(step)} progress ${progress}%`,
            );
          if (progress === 100) {
            const completedAt = new Date().toISOString();
            next.steps[step] = {
              ...next.steps[step],
              status: "completed",
              completedAt,
              activeTask: null,
            };
            if (step < 5)
              next.steps[(step + 1) as WorkflowStep] = {
                ...next.steps[(step + 1) as WorkflowStep],
                status: "ready",
              };
            next = appendSessionLog(
              next,
              `${stepQuery(step)} completed`,
              "DONE",
            );
            if (localMode) updateProjectStage(simulationId, step);
            if (step === 4) {
              next.report.completedAt = completedAt;
              saveWorkspaceReport({
                id: `report-${simulationId}`,
                simulationId,
                projectId: project?.projectId ?? simulationId,
                projectName: resolvedDemo.title,
                institution: project?.institution ?? "Institusi kebijakan",
                title: resolvedDemo.reportTitle,
                completedAt,
                highestRisk: resolvedDemo.risks.some(
                  (risk) => risk.level === "Tinggi",
                )
                  ? "Tinggi"
                  : "Sedang",
                eventCount: resolvedDemo.events.length,
                personaCount: resolvedDemo.personas.reduce(
                  (sum, persona) => sum + persona.count,
                  0,
                ),
                sections: resolvedDemo.reportSections,
              });
            }
          }
          return next;
        }),
      delay,
    );
    return () => window.clearTimeout(timer);
  }, [
    localMode,
    project?.institution,
    project?.projectId,
    resolvedDemo,
    session.currentStep,
    session.steps,
    simulationId,
  ]);

  useEffect(() => {
    if (!localMode) return;
    if (session.simulation.status !== "running") return;
    const timer = window.setTimeout(
      () =>
        setSession((current) => {
          const count = Math.min(
            resolvedDemo.events.length,
            current.simulation.eventCount + 1,
          );
          const event = resolvedDemo.events[count - 1];
          let next: WorkflowSession = {
            ...current,
            simulation: { ...current.simulation, eventCount: count },
            graph: {
              ...current.graph,
              selectedNodeId:
                resolvedDemo.graphNodes.find(
                  (node) => node.group === event?.group,
                )?.id ?? current.graph.selectedNodeId,
            },
            steps: {
              ...current.steps,
              3: {
                ...current.steps[3],
                progress: Math.round(
                  (count / resolvedDemo.events.length) * 100,
                ),
                activeTask: `round-${event?.round ?? 1}`,
              },
            },
          };
          next = appendSessionLog(
            next,
            `Ronde ${event?.round}: ${event?.persona} · ${event?.type}`,
            event?.success === false ? "WARN" : "INFO",
          );
          if (count === resolvedDemo.events.length) {
            next.simulation.status = "completed";
            next.steps[3] = {
              ...next.steps[3],
              status: "completed",
              progress: 100,
              activeTask: null,
              completedAt: new Date().toISOString(),
            };
            next.steps[4] = { ...next.steps[4], status: "ready" };
            next = appendSessionLog(next, "Simulation completed", "DONE");
            if (localMode) updateProjectStage(simulationId, 3);
          }
          return next;
        }),
      1100 / session.simulation.speed,
    );
    return () => window.clearTimeout(timer);
  }, [
    localMode,
    resolvedDemo.events,
    resolvedDemo.graphNodes,
    session.simulation.speed,
    session.simulation.status,
    simulationId,
  ]);

  const startStep = (step: WorkflowStep) => {
    if (!localMode) {
      const config =
        step === 2
          ? {
              rounds: effectiveRequestedRounds,
              max_rounds: effectiveRequestedRounds,
              max_profile_count: maxProfileCount,
              use_llm_for_profiles: useLlmForProfiles,
              use_llm_for_config: useLlmForConfig,
              parallel_profile_count: 5,
            }
          : step === 3
            ? {
                rounds: session.environment.rounds,
                max_rounds: session.environment.rounds,
                enable_graph_memory_update: true,
              }
            : undefined;
      setSession((current) => ({
        ...current,
        steps: {
          ...current.steps,
          [step]: {
            ...current.steps[step],
            status: "processing",
            progress: 0,
            activeTask: stepQuery(step),
          },
        },
        ...(step === 3
          ? {
              simulation: { ...current.simulation, status: "running" as const },
            }
          : {}),
      }));
      startStage(
        simulationId,
        stepQuery(step) as "graph" | "environment" | "simulation" | "report",
        config,
      )
        .then(applyBackendSnapshot)
        .catch((cause) =>
          setBackendError(
            cause instanceof Error ? cause.message : "Tahap gagal dimulai.",
          ),
        );
      return;
    }
    setSession((current) =>
      appendSessionLog(
        {
          ...current,
          steps: {
            ...current.steps,
            [step]: {
              ...current.steps[step],
              status: "processing",
              startedAt: new Date().toISOString(),
              progress: 0,
            },
          },
          ...(step === 3
            ? {
                simulation: {
                  ...current.simulation,
                  status: "running" as const,
                  eventCount: 0,
                },
              }
            : {}),
        },
        `${stepQuery(step)} started`,
      ),
    );
  };
  const graphActiveNode =
    session.currentStep === 3
      ? session.graph.selectedNodeId
      : session.steps[1].status === "processing"
        ? (resolvedDemo.graphNodes[Math.max(0, session.graph.nodeCount - 1)]
            ?.id ?? null)
        : null;
  if (backendLoading)
    return (
      <div className="workflow-not-found">
        <p className="eyebrow">MEMUAT WORKFLOW</p>
        <h1>Mengambil snapshot simulasi...</h1>
      </div>
    );
  if (backendError && !localMode && !backendLoaded)
    return (
      <div className="workflow-not-found">
        <h1>Workflow gagal dimuat</h1>
        <p>{backendError}</p>
        <button
          className="button primary"
          onClick={() => {
            setBackendLoading(true);
            setBackendError("");
            loadBackend();
          }}
        >
          Coba lagi
        </button>
      </div>
    );
  if (!exists)
    return (
      <div className="workflow-not-found">
        <h1>Workflow tidak ditemukan</h1>
        <p>ID simulasi tidak tersedia atau data lokal telah dihapus.</p>
        <button
          className="button primary"
          onClick={() => navigate("/projects")}
        >
          Kembali ke Proyek Kebijakan
        </button>
      </div>
    );
  const effectiveViewMode: ViewMode =
    session.currentStep >= 4 ? "workbench" : session.viewMode;
  const displayedDemo =
    graphSource === "runtime" && runtimeDemo ? runtimeDemo : resolvedDemo;
  const displayedNodeCount =
    graphSource === "runtime" && runtimeDemo
      ? runtimeDemo.graphNodes.length
      : session.graph.nodeCount;
  const displayedEdgeCount =
    graphSource === "runtime" && runtimeDemo
      ? runtimeDemo.graphEdges.length
      : session.graph.edgeCount;
  const policyEntityTypes = policyOntology.entityTypes.length
    ? policyOntology.entityTypes
    : [...new Set(resolvedDemo.graphNodes.map((node) => node.type))];
  const policyRelationTypes = policyOntology.relationTypes.length
    ? policyOntology.relationTypes
    : [...new Set(resolvedDemo.graphEdges.map((edge) => edge.type))];
  const displayedGraphBusy =
    graphSource === "policy"
      ? session.steps[1].status === "processing"
      : runtimeMappingStatus === "running";
  const chooseGraphSource = (source: "policy" | "runtime") => {
    if (source === "runtime" && !runtimeDemo) return;
    graphSourceChosen.current = true;
    graphSelections.current[graphSource] = session.graph.selectedNodeId;
    setGraphSource(source);
    setSession((current) => ({
      ...current,
      graph: {
        ...current.graph,
        selectedNodeId: graphSelections.current[source],
      },
    }));
  };
  const connectionLabel = localMode
    ? "Mode demo lokal"
    : stream.status === "connected"
      ? "Pembaruan langsung tersambung"
      : stream.status === "connecting"
        ? "Menghubungkan pembaruan langsung"
        : stream.status === "reconnecting"
          ? "Menyambungkan ulang · polling aktif"
          : stream.status === "error"
            ? "Pembaruan langsung gagal · polling aktif"
            : "Pembaruan langsung berhenti";
  return (
    <div className="simulation-workflow">
      <WorkflowTopBar
        session={session}
        onStep={goStep}
        onViewMode={setMode}
        connectionStatus={stream.status}
        connectionLabel={connectionLabel}
      />
      {backendError && (
        <p className="inline-alert error workflow-api-error" role="alert">
          {backendError} <button onClick={loadBackend}>Coba lagi</button>
        </p>
      )}
      <main className={`workflow-content mode-${effectiveViewMode}`}>
        {effectiveViewMode !== "workbench" && (
          <div className="graph-column">
            {session.currentStep >= 2 && (
              <div className="graph-source-toggle" aria-label="Sumber graf">
                <button
                  className={graphSource === "policy" ? "active" : ""}
                  aria-pressed={graphSource === "policy"}
                  onClick={() => chooseGraphSource("policy")}
                >
                  Graf kebijakan
                </button>
                <button
                  className={graphSource === "runtime" ? "active" : ""}
                  aria-pressed={graphSource === "runtime"}
                  disabled={!runtimeDemo}
                  onClick={() => chooseGraphSource("runtime")}
                >
                  Graf runtime{" "}
                  {runtimeDemo
                    ? `${runtimeDemo.graphNodes.length}/${runtimeDemo.graphEdges.length}`
                    : "memuat"}
                </button>
              </div>
            )}
            <PolicyGraph
              demo={displayedDemo}
              nodeCount={displayedNodeCount}
              edgeCount={displayedEdgeCount}
              graphLabel={
                graphSource === "runtime"
                  ? "GRAF RUNTIME OASIS / ZEP"
                  : "GRAF PENGETAHUAN KEBIJAKAN"
              }
              isBusy={displayedGraphBusy}
              activeNodeId={graphActiveNode}
              selectedNodeId={session.graph.selectedNodeId}
              onSelect={(id) => {
                graphSelections.current[graphSource] = id;
                setSession((current) => ({
                  ...current,
                  graph: { ...current.graph, selectedNodeId: id },
                }));
              }}
              onLog={log}
            />
          </div>
        )}
        {effectiveViewMode !== "graph" && (
          <div className="workbench-column">
            {session.currentStep === 1 && (
              <GraphBuildStep
                demo={resolvedDemo}
                session={session}
                entityTypes={
                  policyEntityTypes.length
                    ? policyEntityTypes
                    : fallbackEntityTypes
                }
                relationTypes={
                  policyRelationTypes.length
                    ? policyRelationTypes
                    : fallbackRelationTypes
                }
                start={() => startStep(1)}
                next={() => goStep(2)}
              />
            )}
            {session.currentStep === 2 && (
              <EnvironmentStep
                demo={resolvedDemo}
                session={session}
                start={() => startStep(2)}
                maxProfileCount={maxProfileCount}
                rounds={effectiveRequestedRounds}
                useLlmForProfiles={useLlmForProfiles}
                useLlmForConfig={useLlmForConfig}
                onMaxProfileCountChange={setMaxProfileCount}
                onRoundsChange={setRequestedRounds}
                onUseLlmForProfilesChange={setUseLlmForProfiles}
                onUseLlmForConfigChange={setUseLlmForConfig}
                next={() => goStep(3)}
              />
            )}
            {session.currentStep === 3 && (
              <SimulationStep
                demo={resolvedDemo}
                session={session}
                update={updateWorkflow}
                start={() => startStep(3)}
                report={() => goStep(4)}
                localMode={localMode}
              />
            )}
            {session.currentStep === 4 && (
              <ReportStep
                demo={resolvedDemo}
                session={session}
                start={() => startStep(4)}
                next={() => goStep(5)}
              />
            )}
            {session.currentStep === 5 && (
              <InteractionStep
                demo={resolvedDemo}
                session={session}
                update={setSession}
                simulationId={simulationId}
                localMode={localMode}
                sendBackend={
                  localMode
                    ? undefined
                    : async (tool, question, group) => {
                        const response = await sendInteraction(simulationId, {
                          tool,
                          question,
                          personaGroup: group || undefined,
                        });
                        await loadBackend();
                        return mapInteractionMessage(response);
                      }
                }
              />
            )}
          </div>
        )}
      </main>
      {session.currentStep < 4 && <SystemConsole logs={session.logs} />}
    </div>
  );
}
