import type { ConsoleLog, ReportSection, SimulationStatus, ViewMode, WorkflowStep } from "./workflowTypes";
import { authStorageKey } from "../../auth/storageNamespace";

export type StepRunStatus = "locked" | "ready" | "processing" | "paused" | "stale" | "cancelled" | "failed" | "completed";

export type WorkflowStepState = {
  status: StepRunStatus;
  progress: number;
  activeTask: string | null;
  startedAt?: string;
  completedAt?: string;
  staleReason?: string;
  error?: string;
};

export type InteractionMessage = {
  id: string;
  role: "user" | "agent";
  author: string;
  tool: string;
  text: string;
  citations?: import("./workflowTypes").Citation[];
};

export type WorkflowSession = {
  version: 2;
  simulationId: string;
  currentStep: WorkflowStep;
  viewMode: ViewMode;
  steps: Record<WorkflowStep, WorkflowStepState>;
  graph: { nodeCount: number; edgeCount: number; selectedNodeId: string | null };
  environment: {
    personaCount: number; rounds: number; socialization: string; responseMode: string;
    platforms: string[]; totalSimulationHours?: number; minutesPerRound?: number;
  };
  simulation: { status: "ready" | "running" | "paused" | "stale" | "cancelled" | "failed" | "completed"; eventCount: number; speed: 0.5 | 1 | 2; staleReason?: string; error?: string };
  report: { progress: number; sections: ReportSection[]; timestamps: string[]; completedAt?: string };
  interaction: { messages: InteractionMessage[]; revisionNotes: string[] };
  logs: ConsoleLog[];
  updatedAt: string;
};

const prefix = "rekakebijakan-workflow-v2:";
const sessionKey = (simulationId: string) => authStorageKey(`${prefix}${simulationId}`);

function readyStep(status: StepRunStatus): WorkflowStepState {
  return { status, progress: 0, activeTask: null };
}

export function createWorkflowSession(simulationId: string, projectName: string): WorkflowSession {
  const timestamp = new Date().toISOString();
  return {
    version: 2,
    simulationId,
    currentStep: 1,
    viewMode: "split",
    steps: {
      1: readyStep("ready"),
      2: readyStep("locked"),
      3: readyStep("locked"),
      4: readyStep("locked"),
      5: readyStep("locked"),
    },
    graph: { nodeCount: 0, edgeCount: 0, selectedNodeId: null },
    environment: { personaCount: 0, rounds: 40, socialization: "OASIS activity model", responseMode: "LLMAction", platforms: ["twitter", "reddit"] },
    simulation: { status: "ready", eventCount: 0, speed: 1 },
    report: { progress: 0, sections: [], timestamps: [] },
    interaction: {
      messages: [{ id: "welcome", role: "agent", author: "Report Agent", tool: "report", text: `Report Agent siap meninjau temuan untuk ${projectName}.` }],
      revisionNotes: [],
    },
    logs: [{ id: "initialized", time: formatTime(timestamp), level: "INFO", message: `Workflow ${projectName} initialized` }],
    updatedAt: timestamp,
  };
}

export function loadWorkflowSession(simulationId: string): WorkflowSession | null {
  const stored = localStorage.getItem(sessionKey(simulationId));
  if (!stored) return null;
  try {
    const parsed = JSON.parse(stored) as Partial<WorkflowSession>;
    if (parsed.version !== 2 || parsed.simulationId !== simulationId) return null;
    const fallback = createWorkflowSession(simulationId, "Proyek kebijakan");
    const step = (value: unknown, defaultValue: WorkflowStepState): WorkflowStepState => {
      if (!value || typeof value !== "object") return defaultValue;
      const candidate = value as Partial<WorkflowStepState>;
      const statuses: StepRunStatus[] = ["locked", "ready", "processing", "paused", "stale", "cancelled", "failed", "completed"];
      return {
        ...defaultValue,
        ...candidate,
        status: statuses.includes(candidate.status as StepRunStatus) ? candidate.status as StepRunStatus : defaultValue.status,
        progress: Math.min(100, Math.max(0, Number(candidate.progress) || 0)),
        activeTask: typeof candidate.activeTask === "string" ? candidate.activeTask : null,
      };
    };
    const currentStep = [1, 2, 3, 4, 5].includes(Number(parsed.currentStep)) ? Number(parsed.currentStep) as WorkflowStep : 1;
    const viewMode = ["graph", "split", "workbench"].includes(parsed.viewMode ?? "") ? parsed.viewMode as ViewMode : "split";
    const steps = parsed.steps as Partial<Record<WorkflowStep, WorkflowStepState>> | undefined;
    return {
      ...fallback,
      ...parsed,
      simulationId,
      currentStep,
      viewMode,
      steps: {
        1: step(steps?.[1], fallback.steps[1]),
        2: step(steps?.[2], fallback.steps[2]),
        3: step(steps?.[3], fallback.steps[3]),
        4: step(steps?.[4], fallback.steps[4]),
        5: step(steps?.[5], fallback.steps[5]),
      },
      graph: {
        nodeCount: Math.max(0, Number(parsed.graph?.nodeCount) || 0),
        edgeCount: Math.max(0, Number(parsed.graph?.edgeCount) || 0),
        selectedNodeId: typeof parsed.graph?.selectedNodeId === "string" ? parsed.graph.selectedNodeId : null,
      },
      environment: { ...fallback.environment, ...(parsed.environment ?? {}) },
      simulation: { ...fallback.simulation, ...(parsed.simulation ?? {}) },
      report: {
        ...fallback.report,
        ...(parsed.report ?? {}),
        sections: Array.isArray(parsed.report?.sections) ? parsed.report.sections : [],
        timestamps: Array.isArray(parsed.report?.timestamps) ? parsed.report.timestamps : [],
      },
      interaction: {
        ...fallback.interaction,
        ...(parsed.interaction ?? {}),
        messages: Array.isArray(parsed.interaction?.messages) ? parsed.interaction.messages : fallback.interaction.messages,
        revisionNotes: Array.isArray(parsed.interaction?.revisionNotes) ? parsed.interaction.revisionNotes : [],
      },
      logs: Array.isArray(parsed.logs) ? parsed.logs : fallback.logs,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : fallback.updatedAt,
      version: 2,
    };
  } catch {
    return null;
  }
}

export function clearWorkflowSession(simulationId: string) {
  localStorage.removeItem(sessionKey(simulationId));
}

export function saveWorkflowSession(session: WorkflowSession) {
  localStorage.setItem(sessionKey(session.simulationId), JSON.stringify({ ...session, updatedAt: new Date().toISOString() }));
}

export function formatTime(value = new Date().toISOString()) {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)) {
    return value;
  }
  const date = new Date(value);
  if (isNaN(date.getTime())) {
    return value;
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

export function appendSessionLog(session: WorkflowSession, message: string, level: ConsoleLog["level"] = "INFO"): WorkflowSession {
  return {
    ...session,
    logs: [...session.logs.slice(-199), { id: `${Date.now()}-${session.logs.length}`, time: formatTime(), level, message }],
  };
}

export function workflowStatus(session: WorkflowSession): SimulationStatus {
  const status = session.steps[session.currentStep].status;
  if (status === "processing") return "processing";
  if (status === "stale" || status === "cancelled" || status === "failed") return status;
  if (status === "completed") return "completed";
  return "ready";
}

export function highestUnlockedStep(session: WorkflowSession): WorkflowStep {
  return ([5, 4, 3, 2, 1] as WorkflowStep[]).find((step) => session.steps[step].status !== "locked") ?? 1;
}
