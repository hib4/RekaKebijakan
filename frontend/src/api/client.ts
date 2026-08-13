const API_URL = (import.meta.env.VITE_API_URL || "/backend").replace(/\/$/, "");

export type ApiErrorDetails = Record<string, unknown> | unknown[] | string | null;

type ApiErrorPayload = {
  message?: string;
  error?: string | { code?: string; message?: string; details?: ApiErrorDetails };
  code?: string;
  details?: ApiErrorDetails;
  detail?: ApiErrorDetails;
};

export type ApiStageName = "graph" | "environment" | "simulation" | "report" | "interaction";
export type ApiRunStatus = "locked" | "ready" | "queued" | "processing" | "running" | "paused" | "stale" | "cancelled" | "failed" | "completed";

export type ApiStageDto = {
  status?: ApiRunStatus;
  progress?: number;
  active_task?: string | null;
  started_at?: string;
  completed_at?: string;
  error?: string;
  stale?: boolean;
  stale_reason?: string;
  execution_kind?: "accelerated_fixture" | string;
};

export type ApiCitationDto = {
  id?: string;
  source_type: "document_chunk" | "event" | "graph_node" | "interview_answer" | "report_section";
  source_id: string;
  document_id?: string;
  chunk_id?: string;
  locator?: Record<string, unknown>;
  quote?: string;
  label?: string;
};

export type ApiGraphNodeDto = {
  id?: string;
  uuid?: string;
  label?: string;
  name?: string;
  type?: string;
  entity_type?: string;
  labels?: string[];
  summary?: string;
  description?: string;
  group?: string;
  x?: number;
  y?: number;
  citations?: ApiCitationDto[];
};

export type ApiGraphEdgeDto = {
  id?: string;
  uuid?: string;
  source?: string;
  target?: string;
  source_node_uuid?: string;
  target_node_uuid?: string;
  type?: string;
  relation_type?: string;
  fact_type?: string;
  citations?: ApiCitationDto[];
};

export type ApiGraphKind = "policy" | "runtime";

export type ApiGraphStreamMetadata = {
  graph_kind?: ApiGraphKind;
  graph_id?: string;
  build_id?: string;
  revision?: number;
  milestone?: string;
  milestone_index?: number;
  milestone_count?: number;
  milestone_progress?: number;
  removed_node_ids?: string[];
  removed_edge_ids?: string[];
};

export type ApiRuntimeGraph = ({
  available: false;
} | ({
  available: true;
  graph_id: string;
  source_revision: number;
  mapping_status: string;
  node_count: number;
  edge_count: number;
  nodes: ApiGraphNodeDto[];
  edges: ApiGraphEdgeDto[];
} & ApiGraphStreamMetadata)) & ApiGraphStreamMetadata;

export type ApiEmbeddedRuntimeGraph =
  | ApiRuntimeGraph
  | (Omit<Extract<ApiRuntimeGraph, { available: true }>, "available"> & {
      available?: true;
    });

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
  citations?: ApiCitationDto[];
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
  citations?: ApiCitationDto[];
  platform?: string;
  action_args?: Record<string, unknown>;
  success?: boolean;
};

export type ApiRiskDto = {
  id?: string;
  title: string;
  level?: "Rendah" | "Sedang" | "Tinggi" | "low" | "medium" | "high";
  trend?: "Menurun" | "Stabil" | "Meningkat" | "decreasing" | "stable" | "increasing";
  evidence?: string;
  citations?: ApiCitationDto[];
};

export type ApiReportSectionDto = {
  id?: string;
  title: string;
  content?: string | string[];
  paragraphs?: string[];
  content_markdown?: string;
  completed_at?: string;
  citations?: ApiCitationDto[];
};

export type ApiInteractionMessageDto = {
  id?: string;
  role?: "user" | "agent" | "assistant";
  author?: string;
  tool?: string;
  text?: string;
  content?: string;
  citations?: string[];
  evidence_citations?: ApiCitationDto[];
  created_at?: string;
  persona_group?: string;
  tool_calls?: Record<string, unknown>[];
  sources?: Record<string, unknown>[];
};

export type ApiInterviewAnswerDto = {
  id: string;
  persona_id: string;
  persona_name: string;
  question: string;
  answer: string;
  citations?: ApiCitationDto[];
  event_ids?: string[];
};

export type ApiInterviewDto = {
  id: string;
  question: string;
  created_at: string;
  status: "completed" | "partial" | "failed";
  summary?: string;
  answers: ApiInterviewAnswerDto[];
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
    workflow?: ApiWorkflowDto;
    bundle?: ApiDemoBundleDto;
  };
  workflow?: ApiWorkflowDto;
  workflow_mode?: "quick_demo" | "full_simulation";
  demo_bundle_id?: string;
  bundle?: ApiDemoBundleDto;
  demo_bundle?: ApiDemoBundleDto;
  stages?: Partial<Record<ApiStageName, ApiStageDto>>;
  graph?: ApiStageDto & ApiGraphStreamMetadata & {
    nodes?: ApiGraphNodeDto[];
    edges?: ApiGraphEdgeDto[];
    node_count?: number;
    edge_count?: number;
  };
  runtime_graph?: ApiEmbeddedRuntimeGraph;
  environment?: ApiStageDto & {
    personas?: ApiPersonaDto[];
    persona_count?: number;
    config?: {
      rounds?: number; socialization?: string; response_mode?: string; channels?: string[];
      platforms?: string[]; total_simulation_hours?: number; minutes_per_round?: number;
      max_rounds?: number; generation_reasoning?: string; raw_config?: Record<string, unknown>;
    };
  };
  simulation?: ApiStageDto & {
    events?: ApiEventDto[]; event_count?: number; speed?: number;
    runtime?: { current_round?: number; twitter_current_round?: number; reddit_current_round?: number; total_rounds?: number };
  };
  report?: ApiStageDto & {
    title?: string;
    sections?: ApiReportSectionDto[];
    risks?: ApiRiskDto[];
    outline?: { title?: string; summary?: string; sections?: { title: string }[] };
    current_section?: string | null;
  };
  interactions?: { messages?: ApiInteractionMessageDto[] } | ApiInteractionMessageDto[];
  logs?: { id?: string; time?: string; level?: string; message: string }[];
  updated_at?: string;
  stale?: boolean;
  stale_reason?: string;
  ontology?: {
    version?: number;
    entity_types?: { name: string; description?: string }[];
    relation_types?: { name: string }[];
    analysis_summary?: string;
    citations?: ApiCitationDto[];
  };
};

export type SimulationStreamEventType =
  | "snapshot"
  | "simulation.event"
  | "graph.snapshot"
  | "graph.delta"
  | "report.progress"
  | "report.section"
  | "stage.updated";

export type SimulationStreamPayload = {
  state?: ApiSimulationSnapshot;
  event?: ApiEventDto;
  event_count?: number;
  graph_kind?: ApiGraphKind;
  graph_id?: string;
  build_id?: string;
  revision?: number;
  milestone?: string;
  milestone_index?: number;
  milestone_count?: number;
  milestone_progress?: number;
  graph?: ApiRuntimeGraph | (ApiGraphStreamMetadata & Partial<Exclude<ApiRuntimeGraph, { available: false }>> & {
    nodes?: ApiGraphNodeDto[];
    edges?: ApiGraphEdgeDto[];
    removed_node_ids?: string[];
    removed_edge_ids?: string[];
  });
  report?: ApiSimulationSnapshot["report"];
  section?: ApiReportSectionDto;
  progress?: number;
  stage?: ApiStageName | (ApiStageDto & { name: ApiStageName });
  status?: ApiRunStatus;
  active_task?: string | null;
  [key: string]: unknown;
};

export type SimulationStreamEvent = {
  id?: string;
  type: SimulationStreamEventType;
  data: SimulationStreamPayload;
};

export type SimulationStreamOptions = {
  signal?: AbortSignal;
  lastEventId?: string;
  onOpen?: () => void;
  onEvent: (event: SimulationStreamEvent) => void;
};

export type CreateProjectInput = {
  projectName: string;
  institution: string;
  objective: string;
  files: File[];
  workflowMode?: "quick_demo" | "full_simulation";
  demoBundleId?: string;
};

export type ApiDemoBundleDto = {
  id?: string;
  name?: string;
  title?: string;
  version?: string;
  description?: string;
};

export type ApiWorkflowDto = {
  mode?: "quick_demo" | "full_simulation";
  bundle?: ApiDemoBundleDto;
  bundle_id?: string;
  demo_bundle_id?: string;
};

export type CreateProjectOptions = {
  idempotencyKey?: string;
  signal?: AbortSignal;
  onUploadProgress?: (percentage: number) => void;
  onUploadComplete?: () => void;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly details: ApiErrorDetails;

  constructor(message: string, status: number, code: string | null = null, details: ApiErrorDetails = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function apiErrorFromPayload(payload: ApiErrorPayload | null, status: number) {
  const detailMessage = typeof payload?.detail === "string" ? payload.detail : null;
  const nestedError = typeof payload?.error === "object" ? payload.error : null;
  return new ApiError(
    payload?.message || nestedError?.message || (typeof payload?.error === "string" ? payload.error : null) || detailMessage || `Permintaan gagal (${status})`,
    status,
    payload?.code ?? nestedError?.code ?? null,
    payload?.details ?? nestedError?.details ?? payload?.detail ?? null,
  );
}

function notifyExpiredSession(path: string, status: number) {
  if (status === 401 && path !== "/api/auth/me" && path !== "/api/auth/login") {
    window.dispatchEvent(new Event("auth-session-expired"));
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, credentials: "include" });
  const payload = await response.json().catch(() => null) as ApiErrorPayload | T | null;
  if (!response.ok) {
    notifyExpiredSession(path, response.status);
    throw apiErrorFromPayload(payload as ApiErrorPayload | null, response.status);
  }
  return payload as T;
}

export type AuthUser = {
  id: string;
  email: string;
  name: string;
};

type AuthResponse = AuthUser | { user: AuthUser };

function authUser(response: AuthResponse) {
  return "user" in response ? response.user : response;
}

export const getCurrentUser = () => request<AuthResponse>("/api/auth/me").then(authUser);

export const loginUser = (input: { email: string; password: string }) =>
  request<AuthResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  }).then(authUser);

export const registerUser = (input: { name: string; email: string; password: string }) =>
  request<AuthResponse>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  }).then(authUser);

export const logoutUser = () => request<unknown>("/api/auth/logout", { method: "POST" });

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

export function createProject(input: CreateProjectInput, options: CreateProjectOptions = {}) {
  const body = new FormData();
  body.append("project_name", input.projectName);
  body.append("institution", input.institution);
  body.append("objective", input.objective);
  body.append("workflow_mode", input.workflowMode ?? "full_simulation");
  if (input.demoBundleId) body.append("demo_bundle_id", input.demoBundleId);
  input.files.forEach((file) => body.append("files", file, file.name));
  const path = "/api/projects";

  return new Promise<{ simulation_id: string; id?: string }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    xhr.open("POST", `${API_URL}${path}`);
    xhr.withCredentials = true;
    if (options.idempotencyKey) xhr.setRequestHeader("Idempotency-Key", options.idempotencyKey);
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onUploadProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    });
    xhr.upload.addEventListener("load", () => options.onUploadComplete?.());
    xhr.addEventListener("load", () => {
      options.signal?.removeEventListener("abort", abort);
      const payload: ApiErrorPayload | { simulation_id: string; id?: string } | null = (() => {
        try {
          return xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch {
          return null;
        }
      })();
      if (xhr.status < 200 || xhr.status >= 300) {
        notifyExpiredSession(path, xhr.status);
        reject(apiErrorFromPayload(payload as ApiErrorPayload | null, xhr.status));
        return;
      }
      resolve(payload as { simulation_id: string; id?: string });
    });
    xhr.addEventListener("error", () => {
      options.signal?.removeEventListener("abort", abort);
      reject(new Error("Tidak dapat terhubung ke server. Periksa koneksi lalu coba lagi."));
    });
    xhr.addEventListener("abort", () => {
      options.signal?.removeEventListener("abort", abort);
      reject(new DOMException("Permintaan dibatalkan.", "AbortError"));
    });
    if (options.signal?.aborted) {
      reject(new DOMException("Permintaan dibatalkan.", "AbortError"));
      return;
    }
    options.signal?.addEventListener("abort", abort, { once: true });
    xhr.send(body);
  });
}

export const getSimulation = (simulationId: string) =>
  request<ApiSimulationSnapshot>(`/api/simulations/${encodeURIComponent(simulationId)}`);

export const getPublicQuickDemo = () =>
  request<ApiSimulationSnapshot>("/api/public/quick-demo");

export async function connectSimulationStream(simulationId: string, options: SimulationStreamOptions) {
  const path = `/api/simulations/${encodeURIComponent(simulationId)}/stream`;
  const headers = new Headers({ Accept: "text/event-stream" });
  if (options.lastEventId) headers.set("Last-Event-ID", options.lastEventId);
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    headers,
    signal: options.signal,
  });
  if (!response.ok) {
    notifyExpiredSession(path, response.status);
    const payload = await response.json().catch(() => null) as ApiErrorPayload | null;
    throw apiErrorFromPayload(payload, response.status);
  }
  if (!response.body) throw new Error("Server tidak menyediakan aliran pembaruan.");

  options.onOpen?.();
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let eventName = "message";
  let eventId: string | undefined;
  let dataLines: string[] = [];
  const dispatch = () => {
    if (!dataLines.length) return;
    try {
      const parsed = JSON.parse(dataLines.join("\n")) as SimulationStreamPayload & {
        type?: SimulationStreamEventType;
        data?: SimulationStreamPayload;
        payload?: SimulationStreamPayload;
      };
      const type = (eventName === "message" ? parsed.type : eventName) as SimulationStreamEventType;
      const supported: SimulationStreamEventType[] = ["snapshot", "simulation.event", "graph.snapshot", "graph.delta", "report.progress", "report.section", "stage.updated"];
      if (supported.includes(type)) {
        options.onEvent({ id: eventId, type, data: parsed.data ?? parsed.payload ?? parsed });
      }
    } catch {
      // A malformed event is isolated to its SSE frame; later frames remain usable.
    } finally {
      eventName = "message";
      eventId = undefined;
      dataLines = [];
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line) {
        dispatch();
      } else if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("id:")) {
        eventId = line.slice(3).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
  }
  if (buffer) dataLines.push(buffer.startsWith("data:") ? buffer.slice(5).trimStart() : buffer);
  dispatch();
}

export const getRuntimeGraph = (simulationId: string) =>
  request<ApiRuntimeGraph>(`/api/simulations/${encodeURIComponent(simulationId)}/runtime-graph`);

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

export const cancelSimulation = (simulationId: string) =>
  request<ApiSimulationSnapshot>(`/api/simulations/${encodeURIComponent(simulationId)}/cancel`, { method: "POST" });

export const sendInteraction = (simulationId: string, input: { tool: string; question: string; personaGroup?: string }) =>
  request<ApiInteractionMessageDto>(`/api/simulations/${encodeURIComponent(simulationId)}/interactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: input.tool, question: input.question, persona_group: input.personaGroup }),
  });

export const sendPublicQuickDemoInteraction = (input: { tool: string; question: string; personaGroup?: string }) =>
  request<ApiInteractionMessageDto>("/api/public/quick-demo/interactions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: input.tool, question: input.question, persona_group: input.personaGroup }),
  });

export const createSimulationInterview = (simulationId: string, input: { question: string; personaIds: string[] }) =>
  request<ApiInterviewDto>(`/api/simulations/${encodeURIComponent(simulationId)}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: input.question, persona_ids: input.personaIds }),
  });

export const listSimulationInterviews = (simulationId: string) =>
  request<{ items: ApiInterviewDto[] }>(`/api/simulations/${encodeURIComponent(simulationId)}/interviews`);

export type ProjectLifecycleStatus = "draft" | "active" | "archived" | "pending_delete" | "deleted";

export type ApiProject = {
  id: string;
  name: string;
  project_name: string;
  institution: string;
  objective: string;
  status: ProjectLifecycleStatus;
  version: number;
  simulation_id: string;
  current_stage: ApiStageName;
  workflow_status: ApiRunStatus;
  highest_risk: "Rendah" | "Sedang" | "Tinggi";
  report_available: boolean;
  scenario_count: number;
  updated_at: string;
  created_at: string;
  archived_at: string | null;
  workflow_mode?: "quick_demo" | "full_simulation";
  demo_bundle_id?: string;
  workflow?: ApiWorkflowDto;
  bundle?: ApiDemoBundleDto;
};

export type ApiDocument = {
  id: string;
  name: string;
  media_type?: string | null;
  size_bytes?: number;
  page_count?: number | null;
  status?: string;
  created_at?: string;
};

export type ApiProjectDetail = ApiProject & {
  documents: ApiDocument[];
  snapshot: ApiSimulationSnapshot;
};

export type ApiProjectList = {
  items: ApiProject[];
  total: number;
  limit: number;
  offset: number;
};

export type ApiDashboard = {
  generated_at: string;
  metrics: {
    active_projects: number;
    running_simulations: number;
    review_items: number;
    available_reports: number;
  };
  recent_projects: ApiProject[];
  active_runs: ApiProject[];
  attention: ApiProject[];
};

export type ApiScenario = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  kind: "baseline" | "revision" | "custom";
  config: Record<string, unknown>;
  persona_overrides: Record<string, Partial<ApiPersonaDto>>;
  base_environment_revision: number;
  version: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type ProjectListParams = {
  q?: string;
  status?: ProjectLifecycleStatus | "all";
  limit?: number;
  offset?: number;
};

export type UpdateProjectInput = {
  name?: string;
  institution?: string;
  objective?: string;
  expected_version: number;
};

export type CreateScenarioInput = {
  name: string;
  description?: string;
  kind?: ApiScenario["kind"];
  config?: Record<string, unknown>;
};

export type UpdateScenarioInput = Partial<Omit<CreateScenarioInput, "config">> & {
  config?: Record<string, unknown>;
  expected_version: number;
};

const jsonRequest = <T>(path: string, method: string, body?: unknown) => request<T>(path, {
  method,
  headers: body === undefined ? undefined : { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export function listProjects(params: ProjectListParams = {}) {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.status) search.set("status", params.status);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const query = search.toString();
  return request<ApiProjectList>(`/api/v1/projects${query ? `?${query}` : ""}`);
}

export const getProject = (projectId: string) =>
  request<ApiProjectDetail>(`/api/v1/projects/${encodeURIComponent(projectId)}`);

export const getDashboard = () => request<ApiDashboard>("/api/v1/dashboard");

export const updateProject = (projectId: string, input: UpdateProjectInput) =>
  jsonRequest<ApiProject>(`/api/v1/projects/${encodeURIComponent(projectId)}`, "PATCH", input);

export const archiveProject = (projectId: string) =>
  jsonRequest<ApiProject>(`/api/v1/projects/${encodeURIComponent(projectId)}/archive`, "POST");

export const restoreProject = (projectId: string) =>
  jsonRequest<ApiProject>(`/api/v1/projects/${encodeURIComponent(projectId)}/restore`, "POST");

export const deleteProject = (projectId: string) =>
  jsonRequest<ApiProject>(`/api/v1/projects/${encodeURIComponent(projectId)}`, "DELETE");

export const listScenarios = (projectId: string) =>
  request<{ items: ApiScenario[] }>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios`);

export const createScenario = (projectId: string, input: CreateScenarioInput) =>
  jsonRequest<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios`, "POST", input);

export const getScenario = (projectId: string, scenarioId: string) =>
  request<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}`);

export const updateScenario = (projectId: string, scenarioId: string, input: UpdateScenarioInput) =>
  jsonRequest<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}`, "PATCH", input);

export const archiveScenario = (projectId: string, scenarioId: string) =>
  jsonRequest<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/archive`, "POST");

export const restoreScenario = (projectId: string, scenarioId: string) =>
  jsonRequest<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/restore`, "POST");

export const deleteScenario = (projectId: string, scenarioId: string) =>
  jsonRequest<{ ok: true }>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}`, "DELETE");

export const listEffectivePersonas = (projectId: string, scenarioId: string) =>
  request<{ items: ApiPersonaDto[] }>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/personas`);

export const putPersonaOverride = (
  projectId: string,
  scenarioId: string,
  personaId: string,
  input: { expected_version: number; base_environment_revision: number; patch: Partial<ApiPersonaDto> },
) => jsonRequest<ApiScenario>(
  `/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/persona-overrides/${encodeURIComponent(personaId)}`,
  "PUT",
  input,
);

// Production workspace API v1. Mutating resources carry expected_version so
// clients never silently overwrite a newer project, scenario, or run state.
export type ApiRun = {
  id: string;
  project_id: string;
  scenario_id: string;
  status: "queued" | "running" | "paused" | "cancelled" | "failed" | "completed";
  version: number;
  progress: number;
  current_round: number;
  total_rounds: number;
  event_count: number;
  created_at: string;
  updated_at: string;
  engine?: "deterministic" | "oasis";
};

export type ApiOasisAction = {
  sequence: number;
  platform: string;
  external_sequence: number;
  round?: number | null;
  event: ApiEventDto;
  raw_action?: Record<string, unknown> | null;
};

export type ApiOasisArtifacts = {
  posts: Record<string, unknown>[];
  comments: Record<string, unknown>[];
  timeline: Record<string, unknown>[];
  stats: Record<string, unknown>[];
};

export type ApiRunEventPage = {
  items: ApiEventDto[];
  next_cursor: string | null;
  run: ApiRun;
};

export type ApiEffectivePersona = ApiPersonaDto & {
  active: boolean;
  source: "environment" | "override" | "custom";
  profile?: string;
  motivation?: string;
  needs?: string;
  influence?: "Rendah" | "Sedang" | "Tinggi";
  risk?: "Rendah" | "Sedang" | "Tinggi";
  notes?: string;
};

export type ApiProvenance = {
  id: string;
  subject_type: string;
  subject_id: string;
  label: string;
  created_at?: string;
  citations: ApiCitationDto[];
  inputs?: { type: string; id: string; label?: string }[];
};

export const duplicateProject = (projectId: string, input: { name?: string } = {}) =>
  jsonRequest<ApiProject>(`/api/v1/projects/${encodeURIComponent(projectId)}/duplicate`, "POST", input);

export const bulkProjectAction = (input: { project_ids: string[]; action: "archive" | "restore" | "delete" }) =>
  jsonRequest<{ items: ApiProject[]; failed: { id: string; message: string }[] }>("/api/v1/projects/bulk-actions", "POST", input);

export const duplicateScenario = (projectId: string, scenarioId: string, input: { name?: string } = {}) =>
  jsonRequest<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/duplicate`, "POST", input);

export const compareScenarios = (projectId: string, scenarioIds: string[]) =>
  jsonRequest<{ scenarios: ApiScenario[]; differences: { field: string; values: Record<string, unknown> }[] }>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/compare`, "POST", { scenario_ids: scenarioIds },
  );

export const resetPersonaOverride = (projectId: string, scenarioId: string, personaId: string, expectedVersion: number) =>
  jsonRequest<ApiScenario>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/persona-overrides/${encodeURIComponent(personaId)}`, "DELETE", { expected_version: expectedVersion });

export const createCustomPersona = (projectId: string, scenarioId: string, input: Omit<ApiEffectivePersona, "id" | "source"> & { expected_version: number }) =>
  jsonRequest<ApiEffectivePersona>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/personas`, "POST", input);

export const bulkUpdatePersonas = (projectId: string, scenarioId: string, input: { persona_ids: string[]; patch: Partial<ApiEffectivePersona>; expected_version: number }) =>
  jsonRequest<{ items: ApiEffectivePersona[]; scenario: ApiScenario }>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/personas/bulk`, "PATCH", input);

export const submitGraphFeedback = (projectId: string, input: { target_type: "node" | "edge" | "graph"; target_id?: string; action: "accept" | "reject" | "comment"; comment?: string; expected_version: number }) =>
  jsonRequest<{ accepted: true; project_version: number }>(`/api/v1/projects/${encodeURIComponent(projectId)}/graph/feedback`, "POST", input);

export const createRun = (projectId: string, scenarioId: string, input: { expected_scenario_version: number; engine?: "deterministic" | "oasis" }) =>
  jsonRequest<ApiRun>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenarios/${encodeURIComponent(scenarioId)}/runs`, "POST", input);

export const getRun = (runId: string) => request<ApiRun>(`/api/v1/runs/${encodeURIComponent(runId)}`);

export const getRunEvents = (runId: string, cursor?: string) => {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return request<ApiRunEventPage>(`/api/v1/runs/${encodeURIComponent(runId)}/events${query}`);
};

export const getRunActions = (runId: string, cursor?: string) => {
  const query = cursor ? `?after=${encodeURIComponent(cursor)}` : "";
  return request<{ items: ApiOasisAction[]; next_cursor: string | null }>(`/api/v1/runs/${encodeURIComponent(runId)}/actions${query}`);
};

export const getRunArtifacts = (runId: string) =>
  request<ApiOasisArtifacts>(`/api/v1/runs/${encodeURIComponent(runId)}/artifacts`);

export const controlRun = (runId: string, action: "pause" | "resume" | "cancel", expectedVersion: number) =>
  jsonRequest<ApiRun>(`/api/v1/runs/${encodeURIComponent(runId)}/${action}`, "POST", { expected_version: expectedVersion });

export const createInterview = (runId: string, input: { persona_ids?: string[]; group?: string; question: string; platform?: "twitter" | "reddit" }) =>
  jsonRequest<{ id: string; answers: ApiInteractionMessageDto[] }>(`/api/v1/runs/${encodeURIComponent(runId)}/interviews`, "POST", input);

export const sendRunInteraction = (runId: string, input: { tool: "report" | "evidence" | "compare" | "revision"; question: string }) =>
  jsonRequest<ApiInteractionMessageDto>(`/api/v1/runs/${encodeURIComponent(runId)}/interactions`, "POST", input);

export const getProvenance = (projectId: string, subjectType?: string, subjectId?: string) => {
  const search = new URLSearchParams();
  if (subjectType) search.set("subject_type", subjectType);
  if (subjectId) search.set("subject_id", subjectId);
  return request<{ items: ApiProvenance[] }>(`/api/v1/projects/${encodeURIComponent(projectId)}/provenance${search.size ? `?${search}` : ""}`);
};

export const submitContact = (input: { name: string; organization: string; email: string; use_case: string }) =>
  jsonRequest<{ id: string; received_at: string }>("/api/v1/contact-requests", "POST", input);
