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
  getRuntimeGraph,
  getSimulation,
  pauseSimulation,
  resumeSimulation,
  sendInteraction,
  startStage,
  updateEnvironment,
} from "../../api/client";
import {
  getWorkspaceProjectBySimulation,
  getWorkspaceReportBySimulation,
  saveWorkspaceReport,
  updateProjectStage,
} from "../../data/localWorkspace";
import {
  demoCases,
  entityTypes,
  relationTypes,
  suggestedQuestions,
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
  highestUnlockedStep,
  loadWorkflowSession,
  saveWorkflowSession,
} from "./workflowSession";
import type { InteractionMessage, WorkflowSession } from "./workflowSession";
import { useAutoFollow } from "./useAutoFollow";
import { mapBackendSnapshot, mapInteractionMessage } from "./backendWorkflow";
import { CitationDrawer } from "../../components/CitationDrawer/CitationDrawer";
import "./SimulationWorkflow.css";

const graphTasks = [
  {
    title: "Policy Ontology Generation",
    operation: "ONTOLOGY EXTRACTION",
    description:
      "Mengekstrak isu, stakeholder, klausul, kekhawatiran publik, dan narasi risiko.",
  },
  {
    title: "Stakeholder Graph Build",
    operation: "GRAPH ASSEMBLY",
    description:
      "Menyusun entity dan relasi menjadi graf kebijakan yang dapat ditinjau.",
  },
  {
    title: "Graph Build Complete",
    operation: "COVERAGE VALIDATION",
    description:
      "Memvalidasi cakupan stakeholder dan jejak bukti sebelum Environment Setup.",
  },
];
const environmentTasks = [
  {
    title: "Generate Persona Profiles",
    operation: "PERSONA GENERATION",
    description:
      "Membentuk persona sintetis berdasarkan kelompok stakeholder yang tersedia.",
  },
  {
    title: "Generate Simulation Config",
    operation: "CONFIGURATION GENERATION",
    description:
      "Menyiapkan ronde, kanal reaksi, pengaruh, dan respons pemerintah.",
  },
  {
    title: "Environment Ready",
    operation: "READINESS VALIDATION",
    description: "Memeriksa cakupan persona dan kesiapan konfigurasi.",
  },
];
const reportTasks = [
  "Planning / Outline",
  "Evidence Selection",
  "Section Writing",
  "Risk Review",
  "Complete",
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
  if (stage >= 2) session.environment.personaCount = demo.personas.reduce((sum, persona) => sum + persona.count, 0);
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
  start,
  next,
}: {
  demo: DemoCase;
  session: WorkflowSession;
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
        <span>STEP 1/5</span>
        <h1 tabIndex={-1}>Bangun graf kebijakan</h1>
        <p>
          Entity dan relasi muncul bertahap sesuai proses ekstraksi dan
          validasi.
        </p>
      </div>
      {graphTasks.map((task, index) => (
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
          Start Graph Build →
        </button>
      )}
      {step.status === "completed" && (
        <button className="button primary start-action" onClick={next}>
          Continue to Env Setup →
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
  useLlmForProfiles,
  onMaxProfileCountChange,
  onUseLlmForProfilesChange,
  next,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  start: () => void;
  maxProfileCount: number;
  useLlmForProfiles: boolean;
  onMaxProfileCountChange: (value: number) => void;
  onUseLlmForProfilesChange: (value: boolean) => void;
  next: () => void;
}) {
  const step = session.steps[2];
  const personaTotal = demo.personas.reduce((sum, persona) => sum + persona.count, 0);
  const visibleGroups = personaTotal
    ? Math.ceil((session.environment.personaCount / personaTotal) * demo.personas.length)
    : 0;
  const scrollRef = useAutoFollow<HTMLDivElement>(
    `${step.status}-${step.progress}-${session.environment.personaCount}`,
  );
  return (
    <div className="step-scroll" ref={scrollRef}>
      <div className="step-intro">
        <span>STEP 2/5</span>
        <h1 tabIndex={-1}>Siapkan lingkungan simulasi</h1>
        <p>
          Graf kebijakan tetap menjadi sumber tinjauan. OASIS membentuk graf runtime Zep terpisah untuk persona, relasi hasil ekstraksi, dan memori simulasi.
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
                  <b>{Math.min(demo.personas.length, visibleGroups)}/{demo.personas.length}</b>Cakupan stakeholder
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
                    <CitationDrawer citations={persona.citations} label="Lihat sumber persona" />
                  </article>
                ))}
              </div>
            </>
          )}
          {index === 1 && step.progress >= 50 && (
            <>
              <div className="config-controls">
                <span><small>Generated rounds</small><b>{session.environment.rounds}</b></span>
                <span><small>Simulated time</small><b>{session.environment.totalSimulationHours ?? "–"} jam</b></span>
                <span><small>Time step</small><b>{session.environment.minutesPerRound ?? "–"} menit/round</b></span>
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
            <span>Jumlah maksimum profil</span>
            <input
              type="number"
              min="1"
              max="500"
              value={maxProfileCount}
              onChange={(event) => onMaxProfileCountChange(Math.max(1, Math.min(500, Number(event.target.value) || 1)))}
            />
          </label>
          <label className="profile-llm-toggle">
            <input
              type="checkbox"
              checked={useLlmForProfiles}
              onChange={(event) => onUseLlmForProfilesChange(event.target.checked)}
            />
            <span>Perkaya setiap profil dengan LLM (lebih lambat)</span>
          </label>
          <button className="button primary start-action" onClick={start}>
            Prepare OASIS Environment →
          </button>
        </div>
      )}
      {step.status === "completed" && (
        <button className="button primary start-action" onClick={next}>
          Start Simulation →
        </button>
      )}
    </div>
  );
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
    >
      <header>
        <div>
          <b>{event.persona}</b>
          <span>
            {event.group} · {event.channel}
          </span>
        </div>
        <time>
          Ronde {event.round} · {event.time}
        </time>
      </header>
      <p>{event.statement}</p>
      <div className="event-tags">
        <span>{event.type}</span>
        <span>Sikap: {event.stance}</span>
        {event.concerns.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <button
        onClick={(click) => {
          click.stopPropagation();
          setOpen(!open);
        }}
      >
        {open ? "Tutup detail" : "Lihat detail"}
      </button>{" "}
      <CitationDrawer
        citations={event.citations}
        label="Lihat kutipan dan jejak"
      />
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

function SimulationStep({
  demo,
  session,
  update,
  start,
  report,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  update: (session: WorkflowSession) => void;
  start: () => void;
  report: () => void;
}) {
  const run = session.simulation;
  const events = demo.events.slice(0, run.eventCount);
  const round =
    run.status === "completed"
      ? session.environment.rounds
      : Math.max(1, run.currentRound ?? events.at(-1)?.round ?? 1);
  const activeNode = session.graph.selectedNodeId;
  const scrollRef = useAutoFollow<HTMLDivElement>(
    `${run.status}-${events.length}`,
  );
  return (
    <div className="step-scroll simulation-step" ref={scrollRef}>
      <div className="step-intro">
        <span>STEP 3/5</span>
        <h1 tabIndex={-1}>Jalankan simulasi OASIS</h1>
        <p>{demo.question}</p>
      </div>
      <div className="channel-grid">
        {session.environment.platforms.map((channel) => {
          const count = events.filter(
            (event) => event.channel === channel,
          ).length;
          const lastRound = run.platformRounds?.[channel] ??
            events.filter((event) => event.channel === channel).at(-1)?.round ?? 0;
          return (
            <article key={channel}>
              <header>
                <h3>{channel}</h3>
                <span className={run.status}>
                  {run.status === "completed"
                    ? "Completed"
                    : run.status === "running"
                      ? "Running"
                      : run.status === "paused"
                        ? "Paused"
                        : "Ready"}
                </span>
              </header>
              <dl>
                <div>
                  <dt>Round</dt>
                  <dd>
                    {lastRound}/{session.environment.rounds}
                  </dd>
                </div>
                <div>
                  <dt>Elapsed</dt>
                  <dd>{events.at(-1)?.time ?? "00:00"}</dd>
                </div>
                <div>
                  <dt>Acts/events</dt>
                  <dd>{count}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </div>
      <div className="workflow-simulation-summary">
        <span>
          <b>{events.length}</b>Total events
        </span>
        <span>
          <b>
            {round}/{session.environment.rounds}
          </b>
          Round progress
        </span>
        <label>
          Speed
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
        {run.status === "ready" && (
          <button className="button primary" onClick={start}>
            Start Simulation →
          </button>
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
            Pause
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
              Resume
            </button>
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
              Next event
            </button>
          </>
        )}
      </div>
      <div className="event-feed">
        {events.length ? (
          events.map((event) => (
            <div className="event-feed-item" key={event.id}>
              <EventCard
                event={event}
                selected={
                  activeNode === event.group.toLowerCase().replaceAll(" ", "-")
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
          ))
        ) : (
          <div className="workflow-empty">
            <h3>Simulasi siap dijalankan</h3>
            <p>
              Event persona, pengaruh, dan perubahan risiko akan muncul secara
              bertahap.
            </p>
          </div>
        )}
      </div>
      {run.status === "completed" && (
        <div className="simulation-complete-action">
          <button className="button primary" onClick={report}>
            Buka Report →
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
        <span>POLICY SIMULATION REPORT</span>
        <h1>{demo.reportTitle}</h1>
        <p>
          Disusun dari simulasi skenario · {demo.events.length} event · {demo.personas.reduce((sum, persona) => sum + persona.count, 0)} persona sintetis
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
                  {stored.content.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
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
          <span>STEP 4/5</span>
          <h1 tabIndex={-1}>Generate policy report</h1>
          <p>Dokumen dan jejak proses diperbarui dari artifact yang sama.</p>
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
            <b>{session.report.progress}%</b>Progress
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
            Generate Report →
          </button>
        )}
        {step.status === "completed" && (
          <>
            <span className="report-complete-badge">
              ✓ Report completed and saved
            </span>
            <button className="button primary" onClick={next}>
              Go to Interaction →
            </button>
          </>
        )}
      </aside>
    </div>
  );
}

const tools = [
  ["report", "Report Agent", "Ajukan pertanyaan dengan kutipan laporan."],
  [
    "persona",
    "Persona Group Interview",
    "Wawancarai kelompok stakeholder sintetis.",
  ],
  ["evidence", "Evidence Trace", "Telusuri insight ke event dan graph."],
  ["compare", "Scenario Compare", "Bandingkan baseline dan asumsi revisi."],
  ["revision", "Revision Notes", "Susun catatan revisi kebijakan."],
] as const;

function InteractionStep({
  demo,
  session,
  update,
  sendBackend,
}: {
  demo: DemoCase;
  session: WorkflowSession;
  update: Dispatch<SetStateAction<WorkflowSession>>;
  sendBackend?: (
    tool: string,
    question: string,
    group: string,
  ) => Promise<InteractionMessage>;
}) {
  const [tool, setTool] = useState("report");
  const [group, setGroup] = useState(demo.personas[0]?.group ?? "Stakeholder");
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [sendError, setSendError] = useState("");
  const timer = useRef<number | null>(null);
  const scrollRef = useAutoFollow<HTMLElement>(
    `${tool}-${typing}-${session.interaction.messages.length}`,
  );
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );
  const answer = (question: string) => {
    if (tool === "persona") {
      const persona =
        demo.personas.find((item) => item.group === group) ?? demo.personas[0];
      return `${group} menekankan ${persona?.concern.toLowerCase()}. Sikap awalnya ${persona?.stance.toLowerCase()} dan berubah ketika asumsi skenario menyediakan klarifikasi yang dapat ditelusuri.`;
    }
    if (tool === "evidence")
      return `Jejak bukti menghubungkan temuan ke event "${demo.events[0]?.statement}", node ${demo.graphNodes[0]?.label}, dan bagian Ringkasan Eksekutif.`;
    if (tool === "compare")
      return `Baseline menunjukkan risiko komunikasi lebih tinggi. Pada asumsi revisi, intensitas sosialisasi ${session.environment.socialization.toLowerCase()} dan respons ${session.environment.responseMode.toLowerCase()} menurunkan ketidakpastian stakeholder.`;
    if (tool === "revision")
      return `Prioritas revisi: perjelas ketentuan utama, tetapkan kanal klarifikasi, dan lampirkan indikator evaluasi. Catatan ini didukung event simulasi serta Risiko Narasi Utama.`;
    return `Laporan menunjukkan bahwa ${demo.risks[0]?.title.toLowerCase()} merupakan indikasi risiko utama. Temuan ini didukung Bagian 3 dan event pada ronde ${demo.events[0]?.round ?? 1}. Pertanyaan: ${question}`;
  };
  const send = async (question = input) => {
    if (!question.trim() || typing) return;
    const user: InteractionMessage = {
      id: `u-${tool}-${session.interaction.messages.length}`,
      role: "user",
      author: "Anda",
      tool,
      text: question,
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
    if (sendBackend) {
      try {
        const agent = await sendBackend(tool, question, group);
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
      } catch (cause) {
        setSendError(
          cause instanceof Error ? cause.message : "Interaksi gagal dikirim.",
        );
      } finally {
        setTyping(false);
      }
      return;
    }
    timer.current = window.setTimeout(() => {
      const agent: InteractionMessage = {
        id: `a-${tool}-${session.interaction.messages.length + 1}`,
        role: "agent",
        author:
          tool === "persona"
            ? group
            : (tools.find((item) => item[0] === tool)?.[1] ?? "Report Agent"),
        tool,
        text: answer(question),
        citations:
          tool === "persona"
            ? [
                {
                  sourceType: "interview_answer",
                  sourceId: group,
                  label: `Kelompok ${group}`,
                  quote: demo.personas.find((item) => item.group === group)
                    ?.concern,
                },
              ]
            : [
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
    }, 1200);
  };
  const exportNotes = () => {
    const content = session.interaction.messages
      .map((message) => `## ${message.author}\n${message.text}`)
      .join("\n\n");
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/markdown" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${demo.id}-interaction.md`;
    link.click();
    URL.revokeObjectURL(url);
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
      <aside className="interaction-tools" ref={scrollRef}>
        <div className="step-intro">
          <span>STEP 5/5</span>
          <h1 tabIndex={-1}>Interaksi dengan hasil</h1>
          <p>Setiap alat memiliki konteks dan keluaran yang berbeda.</p>
        </div>
        <div className="tool-list">
          {tools.map(([id, title, description]) => (
            <button
              key={id}
              aria-pressed={tool === id}
              className={tool === id ? "active" : ""}
              onClick={() => setTool(id)}
            >
              <b>{title}</b>
              <span>{description}</span>
            </button>
          ))}
        </div>
        {tool === "persona" && (
          <label className="persona-select">
            Persona group
            <select
              value={group}
              onChange={(event) => setGroup(event.target.value)}
            >
              {demo.personas.map((persona) => (
                <option key={persona.group}>{persona.group}</option>
              ))}
            </select>
            <small>
              Persona bersifat sintetis dan bukan profil warga nyata.
            </small>
          </label>
        )}
        {tool === "evidence" && (
          <div className="tool-artifact">
            <b>Evidence chain</b>
            <span>
              Report §3 → Event {demo.events[0]?.id} →{" "}
              {demo.graphNodes[0]?.label}
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
            <b>Revision workspace</b>
            <span>
              Catatan dapat diedit melalui percakapan dan diekspor sebagai
              Markdown.
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
            <div className="chat-messages" aria-live="polite">
              {session.interaction.messages
                .filter(
                  (message) => message.tool === tool || message.id === "welcome",
                )
                .map((message) => (
                  <p key={message.id} className={message.role}>
                    <b>{message.author}</b>
                    {message.text}
                    <CitationDrawer citations={message.citations} label="Lihat sumber jawaban" />
                  </p>
                ))}
              {typing && (
                <p className="agent typing">
                  <b>{tools.find((item) => item[0] === tool)?.[1]}</b>
                  <span>
                    <i />
                    <i />
                    <i />
                  </span>
                </p>
              )}
            </div>
            <div className="suggested-questions">
              {suggestedQuestions.map((question) => (
                <button key={question} type="button" onClick={() => send(question)}>
                  {question}
                </button>
              ))}
            </div>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ajukan pertanyaan berbasis laporan..."
              rows={3}
            />
            {sendError && (
              <p className="interaction-send-error" role="alert">
                {sendError}
              </p>
            )}
          </div>
          <div className="chat-actions">
            <button
              className="button primary"
              type="submit"
              disabled={!input.trim() || typing}
            >
              Send →
            </button>
            <button
              className="button secondary"
              type="button"
              onClick={exportNotes}
            >
              Export .md
            </button>
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
  const project = localMode ? getWorkspaceProjectBySimulation(simulationId) : undefined;
  const demo = intake ? intakeToDemoCase(intake) : knownDemo;
  const exists = localMode
    ? Boolean(simulationId && (demo || project))
    : Boolean(simulationId);
  const [resolvedDemo, setResolvedDemo] = useState<DemoCase>(() => {
    if (demo) return demo;
    if (project) return intakeToDemoCase(project);
    return { id: simulationId, title: "Simulasi kebijakan", question: "", graphNodes: [], graphEdges: [], personas: [], events: [], risks: [], reportTitle: "Laporan simulasi", reportSections: [] };
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
  const [graphSource, setGraphSource] = useState<"policy" | "runtime">("policy");
  const [maxProfileCount, setMaxProfileCount] = useState(10);
  const [useLlmForProfiles, setUseLlmForProfiles] = useState(false);
  const latest = useEffectEvent((next: WorkflowSession) => {
    if (localMode) saveWorkflowSession(next);
  });
  useEffect(() => {
    latest(session);
  }, [session]);

  const applyBackendSnapshot = useCallback(
    (snapshot: Awaited<ReturnType<typeof getSimulation>>) => {
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
  const loadRuntimeGraph = useCallback(async () => {
    if (localMode) return;
    try {
      const graph = await getRuntimeGraph(simulationId);
      if (!graph.available) return;
      setRuntimeDemo((current) => ({
        ...(current ?? resolvedDemo),
        id: `${simulationId}-runtime`,
        title: `${resolvedDemo.title} · Memori runtime`,
        graphNodes: graph.nodes.map((node, index) => ({
          id: node.id,
          label: node.label ?? node.name ?? node.id,
          type: node.type ?? node.entity_type ?? "Entity",
          summary: node.summary ?? node.description ?? "Entitas hasil ekstraksi runtime.",
          x: 100 + (index % 5) * 150,
          y: 80 + Math.floor(index / 5) * 100,
          citations: [],
        })),
        graphEdges: graph.edges.map((edge, index) => ({
          id: edge.id ?? `runtime-edge-${index}`,
          source: edge.source,
          target: edge.target,
          type: edge.type ?? edge.relation_type ?? "RELATED_TO",
          citations: [],
        })),
      }));
      if (session.currentStep >= 2) setGraphSource("runtime");
    } catch (cause) {
      // Runtime topology is supplemental; the policy workflow remains usable
      // while Zep is unavailable or before Stage 02 creates the graph.
      if (cause instanceof ApiError && cause.status === 401) setBackendError(cause.message);
    }
  }, [localMode, resolvedDemo, session.currentStep, simulationId]);
  useEffect(() => {
    if (localMode) return;
    const timer = window.setTimeout(loadBackend, 0);
    return () => window.clearTimeout(timer);
  }, [loadBackend, localMode]);
  const backendPolling =
    (!localMode &&
      Object.values(session.steps).some(
        (item) => item.status === "processing",
      )) ||
    (!localMode && session.simulation.status === "running");
  useEffect(() => {
    if (!backendPolling) return;
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
  }, [backendPolling, loadBackend]);
  const runtimeGraphPolling = !localMode && session.steps[2].status !== "locked";
  useEffect(() => {
    if (!runtimeGraphPolling) return;
    const active = session.simulation.status === "running" || session.steps[2].status === "processing";
    const initialTimer = window.setTimeout(loadRuntimeGraph, 0);
    const pollTimer = active ? window.setInterval(loadRuntimeGraph, 5000) : undefined;
    return () => {
      window.clearTimeout(initialTimer);
      if (pollTimer) window.clearInterval(pollTimer);
    };
  }, [loadRuntimeGraph, runtimeGraphPolling, session.simulation.status, session.steps]);

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
                resolvedDemo.personas.reduce((sum, persona) => sum + persona.count, 0),
                Math.floor((progress / 50) * resolvedDemo.personas.reduce((sum, persona) => sum + persona.count, 0)),
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
                personaCount: resolvedDemo.personas.reduce((sum, persona) => sum + persona.count, 0),
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
      const config = step === 2
        ? { max_rounds: 40, max_profile_count: maxProfileCount, use_llm_for_profiles: useLlmForProfiles, parallel_profile_count: 5 }
        : step === 3
          ? { max_rounds: session.environment.rounds, enable_graph_memory_update: true }
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
  const displayedDemo = graphSource === "runtime" && runtimeDemo ? runtimeDemo : resolvedDemo;
  const displayedNodeCount = graphSource === "runtime" && runtimeDemo ? runtimeDemo.graphNodes.length : session.graph.nodeCount;
  const displayedEdgeCount = graphSource === "runtime" && runtimeDemo ? runtimeDemo.graphEdges.length : session.graph.edgeCount;
  return (
    <div className="simulation-workflow">
      <WorkflowTopBar session={session} onStep={goStep} onViewMode={setMode} />
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
                <button className={graphSource === "policy" ? "active" : ""} onClick={() => setGraphSource("policy")}>Graf kebijakan</button>
                <button className={graphSource === "runtime" ? "active" : ""} disabled={!runtimeDemo} onClick={() => setGraphSource("runtime")}>Graf runtime {runtimeDemo ? `${runtimeDemo.graphNodes.length}/${runtimeDemo.graphEdges.length}` : "memuat"}</button>
              </div>
            )}
            <PolicyGraph
              demo={displayedDemo}
              nodeCount={displayedNodeCount}
              edgeCount={displayedEdgeCount}
              graphLabel={graphSource === "runtime" ? "OASIS / ZEP RUNTIME GRAPH" : "POLICY KNOWLEDGE GRAPH"}
              activeNodeId={graphActiveNode}
              selectedNodeId={session.graph.selectedNodeId}
              onSelect={(id) =>
                setSession((current) => ({
                  ...current,
                  graph: { ...current.graph, selectedNodeId: id },
                }))
              }
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
                useLlmForProfiles={useLlmForProfiles}
                onMaxProfileCountChange={setMaxProfileCount}
                onUseLlmForProfilesChange={setUseLlmForProfiles}
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
                sendBackend={
                  localMode
                    ? undefined
                    : async (tool, question, group) => {
                        const response = await sendInteraction(simulationId, {
                          tool,
                          question,
                          personaGroup:
                            tool === "persona" ? group : undefined,
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
