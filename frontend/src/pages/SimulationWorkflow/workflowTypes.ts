export type WorkflowStep = 1 | 2 | 3 | 4 | 5;

export type ViewMode = "graph" | "split" | "workbench";

export type SimulationStatus = "ready" | "processing" | "stale" | "cancelled" | "failed" | "completed";

export type Citation = {
  id?: string;
  sourceType: "document_chunk" | "event" | "graph_node" | "interview_answer" | "report_section";
  sourceId: string;
  documentId?: string;
  chunkId?: string;
  locator?: Record<string, unknown>;
  quote?: string;
  label?: string;
};

export type PolicyGraphNode = {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  summary: string;
  group?: string;
  citations?: Citation[];
};

export type PolicyGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  citations?: Citation[];
};

export type Persona = {
  id: string;
  name: string;
  group: string;
  role: string;
  stance: string;
  concern: string;
  topics: string[];
  count: number;
  citations?: Citation[];
};

export type SimulationChannel = {
  id: string;
  name: string;
  round: number;
  elapsed: string;
  eventCount: number;
  status: SimulationStatus;
};

export type SimulationEvent = {
  id: string;
  round: number;
  time: string;
  channel: string;
  persona: string;
  group: string;
  type: string;
  statement: string;
  stance: string;
  concerns: string[];
  riskNarrative: string;
  influenceSource: string;
  citations?: Citation[];
  platform?: string;
  actionArgs?: Record<string, unknown>;
  success?: boolean;
};

export type RiskNarrative = {
  id: string;
  title: string;
  level: "Rendah" | "Sedang" | "Tinggi";
  trend: "Menurun" | "Stabil" | "Meningkat";
  evidence: string;
  citations?: Citation[];
};

export type ReportSection = {
  id: string;
  title: string;
  content: string[];
  citations?: Citation[];
};

export type ConsoleLog = {
  id: string;
  time: string;
  level: "INFO" | "WARN" | "DONE";
  message: string;
};

export type WorkflowTask = {
  title: string;
  operation: string;
  description: string;
};

export type DemoCase = {
  id: string;
  title: string;
  question: string;
  graphNodes: PolicyGraphNode[];
  graphEdges: PolicyGraphEdge[];
  personas: Persona[];
  events: SimulationEvent[];
  risks: RiskNarrative[];
  reportTitle: string;
  reportSections: ReportSection[];
};
