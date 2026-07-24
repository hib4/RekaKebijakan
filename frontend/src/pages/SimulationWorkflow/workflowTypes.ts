export type WorkflowStep = 1 | 2 | 3 | 4 | 5;

export type ViewMode = "graph" | "split" | "workbench";

export type SimulationStatus = "ready" | "processing" | "completed";

export type PolicyGraphNode = {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  summary: string;
  group?: string;
};

export type PolicyGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
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
};

export type RiskNarrative = {
  id: string;
  title: string;
  level: "Rendah" | "Sedang" | "Tinggi";
  trend: "Menurun" | "Stabil" | "Meningkat";
  evidence: string;
};

export type ReportSection = {
  id: string;
  title: string;
  content: string[];
};

export type ConsoleLog = {
  id: string;
  time: string;
  level: "INFO" | "WARN" | "DONE";
  message: string;
};

export type WorkflowTask = {
  title: string;
  endpoint: string;
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
