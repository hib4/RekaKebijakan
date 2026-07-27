import type { ApiInteractionMessageDto, ApiRunStatus, ApiSimulationSnapshot, ApiStageDto } from "../../api/client";
import type { Citation, DemoCase, ReportSection, RiskNarrative, WorkflowStep } from "./workflowTypes";
import { createWorkflowSession, formatTime } from "./workflowSession";
import type { InteractionMessage, StepRunStatus, WorkflowSession } from "./workflowSession";

const stageNames = ["graph", "environment", "simulation", "report", "interaction"] as const;

function status(value?: ApiRunStatus): StepRunStatus {
  if (value === "queued" || value === "running" || value === "processing") return "processing";
  return value ?? "locked";
}

function citations(values: import("../../api/client").ApiCitationDto[] = []): Citation[] {
  return values.map((citation) => ({ id: citation.id, sourceType: citation.source_type, sourceId: citation.source_id, documentId: citation.document_id, chunkId: citation.chunk_id, locator: citation.locator, quote: citation.quote, label: citation.label }));
}

function stage(snapshot: ApiSimulationSnapshot, index: number): ApiStageDto {
  const name = stageNames[index];
  if (name === "interaction") return snapshot.stages?.interaction ?? {};
  return snapshot.stages?.[name] ?? snapshot[name] ?? {};
}

function level(value?: string): RiskNarrative["level"] {
  if (value === "high" || value === "Tinggi") return "Tinggi";
  if (value === "low" || value === "Rendah") return "Rendah";
  return "Sedang";
}

function trend(value?: string): RiskNarrative["trend"] {
  if (value === "increasing" || value === "Meningkat") return "Meningkat";
  if (value === "decreasing" || value === "Menurun") return "Menurun";
  return "Stabil";
}

export function mapInteractionMessage(message: ApiInteractionMessageDto, index = 0): InteractionMessage {
  return {
    id: message.id ?? `backend-message-${index}`,
    role: message.role === "user" ? "user" : "agent",
    author: message.author ?? (message.role === "user" ? "Anda" : "Report Agent"),
    tool: message.tool ?? "report",
    text: message.text ?? message.content ?? "",
    citations: citations(message.evidence_citations ?? (message.citations ?? []).map((label, citationIndex) => ({ source_type: "report_section", source_id: `citation-${citationIndex + 1}`, label }))),
  };
}

export function mapBackendSnapshot(snapshot: ApiSimulationSnapshot, simulationId: string, previous?: WorkflowSession) {
  const projectName = snapshot.project?.name ?? snapshot.project?.project_name ?? `Simulasi ${simulationId}`;
  const graphNodes = (snapshot.graph?.nodes ?? []).map((node, index) => ({
    id: node.id,
    label: node.label ?? node.name ?? node.id,
    type: node.type ?? node.entity_type ?? "Stakeholder",
    summary: node.summary ?? node.description ?? "Entity dari graph kebijakan.",
    group: node.group,
    x: node.x ?? 100 + (index % 4) * 180,
    y: node.y ?? 90 + Math.floor(index / 4) * 130,
    citations: citations(node.citations),
  }));
  const graphEdges = (snapshot.graph?.edges ?? []).map((edge, index) => ({
    id: edge.id ?? `edge-${index}`,
    source: edge.source,
    target: edge.target,
    type: edge.type ?? edge.relation_type ?? "RELATED_TO",
    citations: citations(edge.citations),
  }));
  const personas = (snapshot.environment?.personas ?? []).map((persona) => ({
    id: persona.id,
    name: persona.name ?? persona.id,
    group: persona.group ?? persona.stakeholder_group ?? "Stakeholder",
    role: persona.role ?? "Persona sintetis",
    stance: persona.stance ?? "Netral",
    concern: persona.concern ?? persona.concerns?.join(", ") ?? "Belum ada kekhawatiran tercatat.",
    topics: persona.topics ?? [],
    count: persona.count ?? 1,
    citations: citations(persona.citations),
  }));
  const events = (snapshot.simulation?.events ?? []).map((event) => ({
    id: event.id,
    round: event.round ?? 1,
    time: event.time ?? event.elapsed ?? "00:00",
    channel: event.channel ?? "Simulasi",
    persona: event.persona ?? event.persona_name ?? "Persona",
    group: event.group ?? "Stakeholder",
    type: event.type ?? event.event_type ?? "Event",
    statement: event.statement ?? event.content ?? "",
    stance: event.stance ?? "Netral",
    concerns: event.concerns ?? [],
    riskNarrative: event.risk_narrative ?? "Belum diklasifikasikan",
    influenceSource: event.influence_source ?? "Graph kebijakan",
    citations: citations(event.citations),
    platform: event.platform ?? event.channel,
    actionArgs: event.action_args,
    success: event.success,
  }));
  const reportSections: ReportSection[] = (snapshot.report?.sections ?? []).map((section, index) => ({
    id: section.id ?? `section-${index}`,
    title: section.title,
    content: section.paragraphs ?? (Array.isArray(section.content) ? section.content : section.content ? [section.content] : []),
    citations: citations(section.citations),
  }));
  const risks = (snapshot.report?.risks ?? []).map((risk, index) => ({
    id: risk.id ?? `risk-${index}`,
    title: risk.title,
    level: level(risk.level),
    trend: trend(risk.trend),
    evidence: risk.evidence ?? "Jejak tersedia pada laporan backend.",
    citations: citations(risk.citations),
  }));
  const demo: DemoCase = {
    id: simulationId,
    title: projectName,
    question: snapshot.project?.question ?? snapshot.project?.objective ?? "Tinjau hasil simulasi kebijakan.",
    graphNodes,
    graphEdges,
    personas,
    events,
    risks,
    reportTitle: snapshot.report?.title ?? `Laporan Simulasi ${projectName}`,
    reportSections,
  };

  const session = createWorkflowSession(simulationId, projectName);
  stageNames.forEach((_, index) => {
    const number = (index + 1) as WorkflowStep;
    const dto = stage(snapshot, index);
    let stepStatus = status(dto.status);
    if (!dto.status && index === 0) stepStatus = "ready";
    session.steps[number] = {
      status: stepStatus,
      progress: Math.min(100, Math.max(0, dto.progress ?? (stepStatus === "completed" ? 100 : 0))),
      activeTask: dto.active_task ?? null,
      startedAt: dto.started_at,
      completedAt: dto.completed_at,
      staleReason: dto.stale_reason ?? (dto.stale ? snapshot.stale_reason : undefined),
      error: dto.error,
    };
  });
  const explicitStage = typeof snapshot.current_stage === "number"
    ? snapshot.current_stage
    : stageNames.indexOf(snapshot.current_stage ?? "graph") + 1;
  session.currentStep = Math.min(5, Math.max(1, explicitStage)) as WorkflowStep;
  if (session.steps[4].status === "completed" && session.steps[5].status === "locked") session.steps[5].status = "ready";
  session.viewMode = previous?.viewMode ?? (session.currentStep >= 4 ? "workbench" : "split");
  session.graph = { nodeCount: graphNodes.length, edgeCount: graphEdges.length, selectedNodeId: previous?.graph.selectedNodeId ?? null };
  const rounds = snapshot.environment?.config?.max_rounds ?? snapshot.environment?.config?.rounds;
  session.environment = {
    personaCount: snapshot.environment?.persona_count ?? personas.reduce((sum, persona) => sum + persona.count, 0),
    rounds: Math.max(1, rounds ?? 40),
    socialization: snapshot.environment?.config?.socialization ?? "OASIS activity model",
    responseMode: snapshot.environment?.config?.response_mode ?? "LLMAction",
    platforms: snapshot.environment?.config?.platforms ?? snapshot.environment?.config?.channels ?? ["twitter", "reddit"],
    totalSimulationHours: snapshot.environment?.config?.total_simulation_hours,
    minutesPerRound: snapshot.environment?.config?.minutes_per_round,
  };
  const simulationStatus = snapshot.simulation?.status;
  session.simulation = {
    status: simulationStatus === "running" || simulationStatus === "processing" || simulationStatus === "queued" ? "running" : simulationStatus === "paused" ? "paused" : simulationStatus === "stale" || snapshot.simulation?.stale ? "stale" : simulationStatus === "cancelled" ? "cancelled" : simulationStatus === "failed" ? "failed" : simulationStatus === "completed" ? "completed" : "ready",
    eventCount: snapshot.simulation?.event_count ?? events.length,
    speed: previous?.simulation.speed ?? 1,
    currentRound: snapshot.simulation?.runtime?.current_round,
    platformRounds: {
      twitter: snapshot.simulation?.runtime?.twitter_current_round ?? 0,
      reddit: snapshot.simulation?.runtime?.reddit_current_round ?? 0,
    },
    staleReason: snapshot.simulation?.stale_reason ?? snapshot.stale_reason,
    error: snapshot.simulation?.error,
  };
  session.report = {
    progress: snapshot.report?.progress ?? (snapshot.report?.status === "completed" ? 100 : 0),
    sections: reportSections,
    timestamps: reportSections.map(() => snapshot.report?.completed_at ? formatTime(snapshot.report.completed_at) : "--"),
    completedAt: snapshot.report?.completed_at,
  };
  const rawMessages = Array.isArray(snapshot.interactions) ? snapshot.interactions : snapshot.interactions?.messages;
  session.interaction.messages = rawMessages?.map(mapInteractionMessage) ?? previous?.interaction.messages ?? session.interaction.messages;
  session.logs = snapshot.logs?.map((item, index) => ({
    id: item.id ?? `backend-log-${index}`,
    time: formatTime(item.time ?? undefined),
    level: item.level === "WARN" ? "WARN" : item.level === "DONE" ? "DONE" : "INFO",
    message: item.message,
  })) ?? previous?.logs ?? session.logs;
  session.updatedAt = snapshot.updated_at ?? new Date().toISOString();
  return { demo, session };
}
