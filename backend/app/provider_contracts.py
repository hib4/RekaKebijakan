from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class InputEntity(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")


class Project(InputEntity):
    id: str
    name: str
    objective: str


class Chunk(InputEntity):
    id: str
    document_id: str
    ordinal: int = Field(ge=0)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_offsets(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class Citation(Contract):
    source_type: str
    source_id: str
    chunk_id: str | None = None
    document_id: str | None = None
    locator: dict[str, Any] = Field(default_factory=dict)
    quote: str | None = None
    label: str | None = None


class EntityType(Contract):
    name: str
    description: str


class RelationType(Contract):
    name: str
    source_types: list[str]
    target_types: list[str]


class Ontology(InputEntity):
    version: int = Field(ge=1)
    entity_types: list[EntityType]
    relation_types: list[RelationType]
    analysis_summary: str
    citations: list[Citation]
    generated_by: str


class GraphNode(InputEntity):
    id: str
    label: str
    type: str
    summary: str = ""
    citations: list[Citation] = Field(default_factory=list)


class GraphEdge(InputEntity):
    id: str
    source: str
    target: str
    type: str
    citations: list[Citation] = Field(default_factory=list)


class Graph(InputEntity):
    revision: int = Field(ge=0)
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Persona(InputEntity):
    id: str
    name: str
    group: str
    concern: str
    concerns: list[str]
    source_node_ids: list[str]
    citations: list[Citation] = Field(default_factory=list)


class Event(InputEntity):
    id: str
    stance: str
    group: str
    citations: list[Citation] = Field(default_factory=list)


class OntologyInput(Contract):
    project: Project
    chunks: list[Chunk]


class GraphInput(OntologyInput):
    ontology: Ontology


class EnvironmentInput(Contract):
    simulation_id: str
    graph: Graph
    config: dict[str, Any]


class SimulateInput(EnvironmentInput):
    personas: list[Persona]


class ReportInput(OntologyInput):
    events: list[Event]


class AnswerInput(Contract):
    payload: "InteractionPayload"
    state: dict[str, Any]
    chunks: list[Chunk]


class InteractionPayload(InputEntity):
    question: str
    persona_group: str | None = None


class InterviewInput(Contract):
    question: str
    personas: list[Persona]
    events: list[Event]


class GraphMemoryInput(Contract):
    graph: Graph
    events: list[Event]


class OntologyOutput(Contract):
    version: int = Field(ge=1)
    entity_types: list[EntityType]
    relation_types: list[RelationType]
    analysis_summary: str
    citations: list[Citation]
    generated_by: str


class GraphNodeOutput(Contract):
    id: str
    label: str
    type: str
    summary: str = ""
    x: int | float | None = None
    y: int | float | None = None
    group: str | None = None
    memory_source: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class GraphEdgeOutput(Contract):
    id: str
    source: str
    target: str
    type: str
    summary: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class GraphOutput(Contract):
    revision: int = Field(ge=0)
    ontology_version: int | None = None
    nodes: list[GraphNodeOutput]
    edges: list[GraphEdgeOutput]
    generated_by: str | None = None
    memory_revision: int | None = None
    memory_event_ids: list[str] | None = None

    @model_validator(mode="after")
    def valid_graph(self):
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("graph node IDs must be unique")
        known = set(node_ids)
        if any(edge.source not in known or edge.target not in known for edge in self.edges):
            raise ValueError("graph edges must reference known nodes")
        return self


class PersonaOutput(Contract):
    id: str
    name: str
    group: str
    stakeholder_group: str
    role: str
    profile: str
    stance: str
    concern: str
    concerns: list[str]
    topics: list[str]
    influence: float
    active: bool
    count: int
    source_node_ids: list[str]
    citations: list[Citation]


class EnvironmentConfig(Contract):
    rounds: int = Field(gt=0)
    socialization: str
    response_mode: str
    channels: list[str] = Field(min_length=1)
    influence_mode: str
    events_per_round: int = Field(gt=0)
    seed: str
    assumptions: list[Any]
    generation_reasoning: str
    generated_by: str
    version: int = Field(ge=1)
    overrides: dict[str, Any]


class EnvironmentOutput(Contract):
    personas: list[PersonaOutput]
    persona_count: int = Field(ge=0)
    config: EnvironmentConfig

    @model_validator(mode="after")
    def valid_count(self):
        if self.persona_count != len(self.personas):
            raise ValueError("persona_count must equal the number of personas")
        return self


class EventOutput(Contract):
    id: str
    sequence: int = Field(gt=0)
    round: int = Field(gt=0)
    time: str
    channel: str
    persona_id: str
    persona: str
    persona_name: str
    group: str
    type: str
    event_type: str
    statement: str
    content: str
    stance: str
    concerns: list[str]
    risk_narrative: str
    influence_source: str
    source_node_ids: list[str]
    citations: list[Citation]
    graph_revision: int
    config_version: int


class SimulationOutput(Contract):
    id: str
    events: list[EventOutput]
    event_count: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_count(self):
        if self.event_count != len(self.events):
            raise ValueError("event_count must equal the number of events")
        return self


class ReportSection(Contract):
    id: str
    title: str
    paragraphs: list[str]
    citations: list[Citation]


class Risk(Contract):
    id: str
    title: str
    level: str
    trend: str
    evidence: str
    citations: list[Citation]


class ReportOutput(Contract):
    id: str
    version: int = Field(ge=1)
    title: str
    generated_by: str
    sections: list[ReportSection]
    risks: list[Risk]
    citations: list[Citation]


class AnswerOutput(Contract):
    text: str
    citations: list[str]
    evidence_citations: list[Citation]


class InterviewAnswer(Contract):
    id: str
    persona_id: str
    question: str
    answer: str
    citations: list[Citation]
    event_ids: list[str]


class InterviewOutput(Contract):
    answers: list[InterviewAnswer]
    summary: str


PROVIDER_INPUTS = {
    "ontology": OntologyInput,
    "graph": GraphInput,
    "environment": EnvironmentInput,
    "simulate": SimulateInput,
    "report": ReportInput,
    "answer": AnswerInput,
    "interview": InterviewInput,
    "graph_memory": GraphMemoryInput,
}

PROVIDER_OUTPUTS = {
    "ontology": OntologyOutput,
    "graph": GraphOutput,
    "environment": EnvironmentOutput,
    "simulate": SimulationOutput,
    "report": ReportOutput,
    "answer": AnswerOutput,
    "interview": InterviewOutput,
    "graph_memory": GraphOutput,
}

FallbackPolicy = Literal["deterministic", "raise"]
