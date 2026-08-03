import type {
  ApiGraphEdgeDto,
  ApiGraphKind,
  ApiGraphNodeDto,
  ApiReportSectionDto,
  ApiRuntimeGraph,
  ApiSimulationSnapshot,
  ApiStageDto,
  SimulationStreamEvent,
} from "../../api/client";

function mergeById<T extends { id?: string }>(current: T[] = [], incoming: T[] = []) {
  const merged = new Map(current.map((item, index) => [item.id ?? `current-${index}`, item]));
  incoming.forEach((item, index) => {
    const key = item.id ?? `incoming-${index}`;
    merged.set(key, { ...merged.get(key), ...item });
  });
  return [...merged.values()];
}

function mergeSection(current: ApiReportSectionDto[] = [], section: ApiReportSectionDto) {
  const key = section.id ?? section.title;
  const index = current.findIndex((item) => (item.id ?? item.title) === key);
  if (index < 0) return [...current, section];
  return current.map((item, itemIndex) => itemIndex === index ? { ...item, ...section } : item);
}

export function mergeSimulationStreamEvent(
  current: ApiSimulationSnapshot,
  message: SimulationStreamEvent,
): ApiSimulationSnapshot {
  const data = message.data;
  if (message.type === "snapshot" && data.state) return data.state;
  if (message.type === "graph.snapshot" || message.type === "graph.delta") {
    return mergePolicyGraphEvent(current, message);
  }

  if (message.type === "simulation.event" && data.event) {
    const events = mergeById(current.simulation?.events, [data.event]);
    return {
      ...current,
      simulation: {
        ...current.simulation,
        events,
        event_count: Math.max(current.simulation?.event_count ?? 0, data.event_count ?? 0, events.length),
      },
    };
  }

  if (message.type === "report.progress") {
    const report = data.report ?? {};
    return {
      ...current,
      report: {
        ...current.report,
        ...report,
        progress: data.progress ?? report.progress ?? current.report?.progress,
        sections: report.sections
          ? report.sections.reduce((sections, section) => mergeSection(sections, section), current.report?.sections ?? [])
          : current.report?.sections,
      },
    };
  }

  if (message.type === "report.section") {
    const granularSection = typeof data.title === "string"
      ? data as unknown as ApiReportSectionDto
      : undefined;
    const section = data.section ?? (data.report?.sections?.[0]) ?? granularSection;
    if (!section) return current;
    return {
      ...current,
      report: {
        ...current.report,
        ...data.report,
        progress: data.progress ?? data.report?.progress ?? current.report?.progress,
        sections: mergeSection(current.report?.sections, section),
      },
    };
  }

  if (message.type === "stage.updated" && data.stage) {
    const stageName = typeof data.stage === "string" ? data.stage : data.stage.name;
    const stageData: ApiStageDto = typeof data.stage === "string" ? {} : data.stage;
    const previous = current.stages?.[stageName] ?? (stageName === "interaction" ? undefined : current[stageName]);
    const nextStage = {
      ...previous,
      ...stageData,
      status: data.status ?? stageData.status ?? previous?.status,
      progress: data.progress ?? stageData.progress ?? previous?.progress,
      active_task: data.active_task === undefined ? stageData.active_task ?? previous?.active_task : data.active_task,
    };
    return { ...current, current_stage: stageName, stages: { ...current.stages, [stageName]: nextStage } };
  }

  return current;
}

type RuntimeGraphData = Extract<ApiRuntimeGraph, { available: true }>;

function graphId(item: ApiGraphNodeDto | ApiGraphEdgeDto, index: number) {
  return item.id ?? item.uuid ?? `stream-graph-${index}`;
}

type GraphStreamData = Exclude<NonNullable<SimulationStreamEvent["data"]["graph"]>, { available: false }>;

function graphMetadata(message: SimulationStreamEvent, graph: GraphStreamData) {
  return {
    kind: graph.graph_kind ?? message.data.graph_kind,
    graphId: graph.graph_id ?? message.data.graph_id,
    buildId: graph.build_id ?? message.data.build_id,
    revision: graph.revision ?? message.data.revision ?? graph.source_revision,
  };
}

function acceptsGraphEvent(
  current: { graph_id?: string; build_id?: string; revision?: number; source_revision?: number } | null,
  message: SimulationStreamEvent,
  graph: GraphStreamData,
) {
  if (!current) return message.type === "graph.snapshot" || Boolean(graph.graph_id || graph.build_id);
  const incoming = graphMetadata(message, graph);
  const currentRevision = current.revision ?? current.source_revision;
  if (message.type === "graph.snapshot" && (
    (current.graph_id && incoming.graphId && current.graph_id !== incoming.graphId)
    || (current.build_id && incoming.buildId && current.build_id !== incoming.buildId)
  )) return true;
  if (message.type === "graph.delta") {
    if (current.graph_id && incoming.graphId && current.graph_id !== incoming.graphId) return false;
    if (current.build_id && incoming.buildId && current.build_id !== incoming.buildId) return false;
  }
  return incoming.revision === undefined || currentRevision === undefined || incoming.revision >= currentRevision;
}

function mergeGraphItems(
  currentNodes: ApiGraphNodeDto[],
  currentEdges: ApiGraphEdgeDto[],
  graph: GraphStreamData,
  replace: boolean,
) {
  const removedNodes = new Set(graph.removed_node_ids ?? []);
  const removedEdges = new Set(graph.removed_edge_ids ?? []);
  const nodes = mergeById(
    (replace ? [] : currentNodes).map((node, index) => ({ ...node, id: graphId(node, index) })),
    (graph.nodes ?? []).map((node, index) => ({ ...node, id: graphId(node, index) })),
  ).filter((node) => !removedNodes.has(node.id ?? ""));
  const edges = mergeById(
    (replace ? [] : currentEdges).map((edge, index) => ({ ...edge, id: graphId(edge, index) })),
    (graph.edges ?? []).map((edge, index) => ({ ...edge, id: graphId(edge, index) })),
  ).filter((edge) => {
    if (removedEdges.has(edge.id ?? "")) return false;
    const source = edge.source ?? edge.source_node_uuid;
    const target = edge.target ?? edge.target_node_uuid;
    return !removedNodes.has(source ?? "") && !removedNodes.has(target ?? "");
  });
  return { nodes, edges };
}

function streamGraphKind(message: SimulationStreamEvent, graph: GraphStreamData): ApiGraphKind | undefined {
  return graph.graph_kind ?? message.data.graph_kind;
}

function mergePolicyGraphEvent(current: ApiSimulationSnapshot, message: SimulationStreamEvent) {
  if (message.type !== "graph.snapshot" && message.type !== "graph.delta") return current;
  const graph = message.data.graph;
  if (!graph || graph.available === false || streamGraphKind(message, graph) !== "policy") return current;
  if (!acceptsGraphEvent(current.graph ?? null, message, graph)) return current;
  const { nodes, edges } = mergeGraphItems(current.graph?.nodes ?? [], current.graph?.edges ?? [], graph, message.type === "graph.snapshot");
  return {
    ...current,
    graph: {
      ...current.graph,
      graph_kind: "policy" as const,
      graph_id: graph.graph_id ?? message.data.graph_id ?? current.graph?.graph_id,
      build_id: graph.build_id ?? message.data.build_id ?? current.graph?.build_id,
      revision: graph.revision ?? message.data.revision ?? current.graph?.revision,
      milestone: graph.milestone ?? message.data.milestone ?? current.graph?.milestone,
      milestone_index: graph.milestone_index ?? message.data.milestone_index ?? current.graph?.milestone_index,
      milestone_count: graph.milestone_count ?? message.data.milestone_count ?? current.graph?.milestone_count,
      milestone_progress: graph.milestone_progress ?? message.data.milestone_progress ?? current.graph?.milestone_progress,
      nodes,
      edges,
      node_count: nodes.length,
      edge_count: edges.length,
    },
  };
}

export function mergeRuntimeGraphEvent(
  current: RuntimeGraphData | null,
  message: SimulationStreamEvent,
): RuntimeGraphData | null {
  if (message.type !== "graph.snapshot" && message.type !== "graph.delta") return current;
  const graph = message.data.graph;
  if (!graph || graph.available === false) return current;
  const kind = streamGraphKind(message, graph);
  if (kind && kind !== "runtime") return current;
  if (!acceptsGraphEvent(current, message, graph)) return current;
  const { nodes, edges } = mergeGraphItems(current?.nodes ?? [], current?.edges ?? [], graph, message.type === "graph.snapshot");
  return {
    ...current,
    available: true,
    graph_id: graph.graph_id ?? message.data.graph_id ?? current?.graph_id ?? "runtime",
    graph_kind: "runtime",
    build_id: graph.build_id ?? message.data.build_id ?? current?.build_id,
    revision: graph.revision ?? message.data.revision ?? current?.revision,
    milestone: graph.milestone ?? message.data.milestone ?? current?.milestone,
    milestone_index: graph.milestone_index ?? message.data.milestone_index ?? current?.milestone_index,
    milestone_count: graph.milestone_count ?? message.data.milestone_count ?? current?.milestone_count,
    milestone_progress: graph.milestone_progress ?? message.data.milestone_progress ?? current?.milestone_progress,
    source_revision: graph.source_revision ?? graph.revision ?? message.data.revision ?? current?.source_revision ?? 0,
    mapping_status: graph.mapping_status ?? current?.mapping_status ?? "running",
    node_count: nodes.length,
    edge_count: edges.length,
    nodes,
    edges,
  };
}
