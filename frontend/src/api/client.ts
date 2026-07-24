const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:5001").replace(/\/$/, "");

export type ApiStageName = "graph" | "environment" | "simulation" | "report" | "interaction";
export type ApiRunStatus = "locked" | "ready" | "queued" | "processing" | "running" | "paused" | "failed" | "completed";

export type ApiStageDto = {
  status?: ApiRunStatus;
  progress?: number;
  active_task?: string | null;
  started_at?: string;
  completed_at?: string;
  error?: string;
};

export type ApiGraphNodeDto = {
  id: string;
  label?: string;
  name?: string;
  type?: string;
  entity_type?: string;
  summary?: string;
  description?: string;
  group?: string;
  x?: number;
  y?: number;
};

export type ApiGraphEdgeDto = {
  id?: string;
  source: string;
  target: string;
  type?: string;
  relation_type?: string;
};

export type ApiPersonaDto = {
  id: string;
  name?: string;
  group?: string;
  stakeholder_group?: string;
  role?: string;
  stance?: string;
  concern?: string;
  concerns?: string[];
  topics?: string[];
  count?: number;
};

export type ApiEventDto = {
  id: string;
  round?: number;
  time?: string;
  elapsed?: string;
  channel?: string;
  persona?: string;
  persona_name?: string;
  group?: string;
  type?: string;
  event_type?: string;
  statement?: string;
  content?: string;
  stance?: string;
  concerns?: string[];
  risk_narrative?: string;
  influence_source?: string;
};

export type ApiRiskDto = {
  id?: string;
  title: string;
  level?: "Rendah" | "Sedang" | "Tinggi" | "low" | "medium" | "high";
  trend?: "Menurun" | "Stabil" | "Meningkat" | "decreasing" | "stable" | "increasing";
  evidence?: string;
};

export type ApiReportSectionDto = {
  id?: string;
  title: string;
  content?: string | string[];
  paragraphs?: string[];
};

export type ApiInteractionMessageDto = {
  id?: string;
  role?: "user" | "agent" | "assistant";
  author?: string;
  tool?: string;
  text?: string;
  content?: string;
  citations?: string[];
};

export type ApiSimulationSnapshot = {
  id?: string;
  simulation_id?: string;
  status?: ApiRunStatus;
  current_stage?: ApiStageName | number;
  project?: {
    id?: string;
    name?: string;
    project_name?: string;
    institution?: string;
    objective?: string;
    question?: string;
  };
  stages?: Partial<Record<ApiStageName, ApiStageDto>>;
  graph?: ApiStageDto & { nodes?: ApiGraphNodeDto[]; edges?: ApiGraphEdgeDto[] };
  environment?: ApiStageDto & {
    personas?: ApiPersonaDto[];
    persona_count?: number;
    config?: { rounds?: number; socialization?: string; response_mode?: string };
  };
  simulation?: ApiStageDto & { events?: ApiEventDto[]; event_count?: number; speed?: number };
  report?: ApiStageDto & { title?: string; sections?: ApiReportSectionDto[]; risks?: ApiRiskDto[] };
  interactions?: { messages?: ApiInteractionMessageDto[] } | ApiInteractionMessageDto[];
  logs?: { id?: string; time?: string; level?: string; message: string }[];
  updated_at?: string;
};

export type CreateProjectInput = {
  projectName: string;
  institution: string;
  objective: string;
  files: File[];
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  const payload = await response.json().catch(() => null) as { message?: string; error?: string } | null;
  if (!response.ok) throw new ApiError(payload?.message || payload?.error || `Permintaan gagal (${response.status})`, response.status);
  return payload as T;
}

async function requestFirst<T>(paths: string[], init?: RequestInit): Promise<T> {
  let lastError: unknown;
  for (const path of paths) {
    try {
      return await request<T>(path, init);
    } catch (error) {
      lastError = error;
      if (!(error instanceof ApiError) || (error.status !== 404 && error.status !== 405)) throw error;
    }
  }
  throw lastError;
}

export async function createProject(input: CreateProjectInput) {
  const body = new FormData();
  body.append("project_name", input.projectName);
  body.append("institution", input.institution);
  body.append("objective", input.objective);
  input.files.forEach((file) => body.append("files", file, file.name));
  return request<{ simulation_id: string; id?: string }>("/api/projects", { method: "POST", body });
}

export const getSimulation = (simulationId: string) =>
  request<ApiSimulationSnapshot>(`/api/simulations/${encodeURIComponent(simulationId)}`);

export const startStage = (simulationId: string, stage: ApiStageName, config?: Record<string, unknown>) =>
  requestFirst<ApiSimulationSnapshot>([
    `/api/simulations/${encodeURIComponent(simulationId)}/stages/${stage}/start`,
    `/api/simulations/${encodeURIComponent(simulationId)}/${stage}/start`,
    `/api/simulations/${encodeURIComponent(simulationId)}/start/${stage}`,
  ], {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config ?? {}),
  });

export const updateEnvironment = (simulationId: string, config: Record<string, unknown>) =>
  request<ApiSimulationSnapshot>(`/api/simulations/${encodeURIComponent(simulationId)}/environment`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

export const pauseSimulation = (simulationId: string) =>
  request<ApiSimulationSnapshot>(`/api/simulations/${encodeURIComponent(simulationId)}/pause`, { method: "POST" });

export const resumeSimulation = (simulationId: string) =>
  request<ApiSimulationSnapshot>(`/api/simulations/${encodeURIComponent(simulationId)}/resume`, { method: "POST" });

export const sendInteraction = (simulationId: string, input: { tool: string; question: string; personaGroup?: string }) =>
  request<ApiInteractionMessageDto>(`/api/simulations/${encodeURIComponent(simulationId)}/interactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: input.tool, question: input.question, persona_group: input.personaGroup }),
  });
