# RekaKebijakan Summary

## Executive Summary

RekaKebijakan is a public policy simulation platform that helps policy teams evaluate draft regulations, programs, and implementation plans before they are released. The system transforms uploaded policy sources into a structured policy graph, generates synthetic stakeholder personas, runs bounded scenario simulations, and produces reports with traceable evidence.

The core objective is to support earlier and more responsible policy analysis. Instead of waiting until a policy is implemented to discover stakeholder concerns, narrative risks, or evidence gaps, RekaKebijakan gives analysts a controlled environment to explore possible interpretations and reactions while preserving citations back to the original sources.

RekaKebijakan is not intended to replace public consultation or expert review. It is designed as a decision-support tool that helps teams identify questions, risks, and consultation priorities earlier in the policy lifecycle.

## Problem Background

Public policy teams often face several challenges during early-stage analysis:

- Policy documents are long, technical, and difficult to translate into stakeholder-level implications.
- Affected groups may be incomplete or inconsistently mapped during early planning.
- Risks can emerge from interpretation gaps, unclear obligations, or uneven implementation capacity.
- Public narratives may form before institutions have prepared evidence-based clarification.
- Conventional review processes can be slow, manual, and difficult to reproduce.

RekaKebijakan addresses these challenges by combining document-grounded extraction, graph modeling, synthetic persona generation, simulation, and evidence-aware reporting in one workflow.

## Proposed Solution

The proposed product is a workflow platform for policy-scenario simulation. A user creates a project, uploads policy sources, defines the analysis objective, and runs a five-stage process:

1. Source intake and document processing.
2. Policy graph construction.
3. Environment and persona generation.
4. Scenario simulation.
5. Report generation and follow-up interaction.

Each output remains connected to structured evidence. Graph nodes, persona assumptions, simulation events, report findings, and follow-up answers can expose citations to document chunks, graph elements, simulation events, interview answers, or report sections.

## System Workflow

### 1. Source Intake

Users provide project metadata, the responsible institution or team, an analysis objective, and source files. Supported files include PDF, DOCX, Markdown, and plain text documents.

The system validates file type, size, and project limits, stores the original files, extracts text, and prepares the source material for downstream analysis.

### 2. Graph Build

The system extracts important policy concepts from the source material and turns them into a graph. The graph represents policy objects, affected stakeholders, issues, risks, expected outcomes, and relationships between them.

### 3. Environment Setup

The system converts graph entities into synthetic personas. Each persona includes a stakeholder group, role, stance, concerns, topics, influence score, and evidence references where available.

### 4. Simulation

The system runs a bounded scenario simulation over a configured number of rounds. Personas generate responses through channels such as public forums, social media, or public meetings. In the full runtime, OASIS can run Twitter-like and Reddit-like platform simulations in parallel.

### 5. Report and Interaction

The system aggregates simulation events into report sections, risks, and recommendations. Users can ask follow-up questions about reports, personas, evidence, risks, comparisons, and policy revisions.

## Detailed Algorithm

The RekaKebijakan algorithm is a staged pipeline. Each stage receives structured input from the previous stage and produces durable artifacts that can be inspected, cited, and reused.

### Stage A: Project Initialization and Document Ingestion

Input:

- Project name.
- Institution or team name.
- Policy analysis objective.
- One or more source documents.
- User identity and idempotency key, when authenticated.

Process:

1. Validate that at least one document is provided.
2. Enforce upload limits such as maximum files per project, maximum file size, total storage quota, maximum PDF pages, maximum extracted characters, and maximum chunks per document.
3. Generate durable identifiers for the project, simulation, documents, and queued workflow job.
4. Store each uploaded file in local storage or Firebase Storage, depending on deployment configuration.
5. Persist project state in PostgreSQL with the initial workflow stage set to graph processing.
6. Queue the graph-build job for the worker.

Output:

- Project record.
- Simulation record.
- Stored source files.
- Initial workflow state.
- Queued graph-build job.

### Stage B: Text Extraction and Chunking

Input:

- Stored source documents.

Process:

1. Extract text from PDF, DOCX, Markdown, or text files.
2. Normalize document metadata such as media type, size, language, page count, extraction version, and hash.
3. Split extracted text into overlapping chunks.
4. Assign each chunk stable metadata: document ID, chunk ID, ordinal, character start, character end, and text content.
5. Store chunks in PostgreSQL so every downstream artifact can cite the original source span.

The current backend uses deterministic chunking defaults, including a chunk size and overlap, to preserve repeatability.

Output:

- Extracted document text.
- Document chunks.
- Chunk-level citation metadata.

### Stage C: Evidence Retrieval

Input:

- A query such as policy objective, risk question, report prompt, or user follow-up question.
- Stored document chunks.

Process:

1. Tokenize the query into candidate terms.
2. Remove common stopwords.
3. Score chunks by term occurrence in chunk text.
4. Rank chunks by relevance, then by document ID and chunk order for stable output.
5. Return the best matching chunks, or fallback to the earliest ranked chunks when no term matches.
6. Convert selected chunks into structured citations.

Citation structure includes:

- `source_type`.
- `source_id`.
- `document_id`.
- `chunk_id`.
- `locator` with ordinal and character range.
- `quote`.
- `label`.

Output:

- Ranked evidence chunks.
- Validated citation objects.

### Stage D: Ontology Generation

Input:

- Project metadata.
- Document chunks.

Process:

1. Extract frequent and policy-relevant terms from the source text.
2. Define entity types that represent the policy domain.
3. Define relation types that describe how entities can connect.
4. Attach citations to support the ontology summary.

The deterministic provider defines core entity types:

- `Policy`: the policy or program being analyzed.
- `Stakeholder`: groups that influence or are affected by the policy.
- `Issue`: concerns or topics found in the source material.
- `Risk`: implementation or impact-distribution risks.
- `Outcome`: expected results or policy goals.

The deterministic provider defines core relation types:

- `RESPONDS_TO`: a stakeholder responds to a policy or issue.
- `RAISES`: a stakeholder raises an issue or risk.
- `AFFECTS`: a policy or issue affects a stakeholder or outcome.

Output:

- Ontology version.
- Entity type definitions.
- Relation type definitions.
- Analysis summary.
- Supporting citations.

### Stage E: Policy Graph Construction

Input:

- Project metadata.
- Generated ontology.
- Document chunks.

Process:

1. Create a central policy node from the project name and objective.
2. Create stakeholder nodes from predefined or extracted stakeholder groups.
3. Create issue nodes from high-frequency policy terms and source concepts.
4. Attach citations from relevant chunks to each node where possible.
5. Create edges between stakeholders, the policy node, and issue nodes using ontology relation types.
6. Persist graph revision, ontology version, nodes, edges, and generator metadata.

In the OASIS/Zep path, graph construction can also use Zep as a graph memory layer:

1. Create a Zep graph with a durable graph ID.
2. Set the generated ontology.
3. Split text into ingestion batches.
4. Submit batches to Zep.
5. Wait for graph ingestion to complete.
6. Fetch graph nodes, edges, and entity type summaries.

Output:

- Policy graph nodes.
- Policy graph edges.
- Graph revision.
- Entity and relation provenance.

### Stage F: Environment and Persona Generation

Input:

- Policy graph.
- Simulation configuration.
- Simulation ID.

Process:

1. Select stakeholder and issue nodes from the graph.
2. Generate personas by pairing stakeholder groups with policy issues.
3. Assign each persona an ID, name, group, role, profile, stance, concern, topics, and activity status.
4. Generate a deterministic influence score where deterministic mode is used.
5. Link each persona to source graph nodes and citations.
6. Resolve simulation configuration such as rounds, socialization level, response mode, channels, events per round, and seed.

In the full OASIS runtime, this stage is expanded:

1. Read and filter graph entities from Zep.
2. Optionally limit the number of generated profiles.
3. Generate OASIS agent profiles from entities, optionally with an LLM.
4. Generate profiles in parallel for faster preparation.
5. Save Reddit profiles as JSON and Twitter profiles as CSV.
6. Generate simulation parameters such as timing, activity, and posting frequency.
7. Save `simulation_config.json` and mark the environment as ready.

Output:

- Persona list.
- Persona count.
- Resolved simulation configuration.
- Runtime profile files when OASIS is enabled.

### Stage G: Scenario Simulation

Input:

- Simulation ID.
- Policy graph.
- Persona list.
- Simulation configuration.

Process in deterministic mode:

1. Read the configured number of rounds.
2. For each round, iterate through stakeholder groups.
3. Select a persona from the matching stakeholder group.
4. Generate a deterministic stance using a hash of simulation ID, round number, and group index.
5. Produce a persona statement focused on the persona concern.
6. Assign the event to a channel.
7. Add risk narrative, influence source, source graph nodes, citations, graph revision, and config version.
8. Append the event to the run output.

Each simulation event contains fields such as:

- Event ID and sequence.
- Round and time.
- Channel.
- Persona ID and persona name.
- Stakeholder group.
- Event type.
- Statement and content.
- Stance.
- Concerns.
- Risk narrative.
- Influence source.
- Source node IDs.
- Citations.
- Graph revision.
- Configuration version.

Process in OASIS mode:

1. Load generated platform profiles and simulation configuration.
2. Run enabled platform worlds, such as Twitter and Reddit, in parallel.
3. Stream actions from platform simulations.
4. Normalize raw actions into the backend event schema.
5. Persist actions incrementally to PostgreSQL.
6. Wait for graph-memory ingestion when enabled.
7. Mark the run as completed, failed, paused, cancelled, or stopped according to runtime status.

Output:

- Run ID.
- Ordered simulation events.
- Event count.
- Runtime status.
- Persisted raw or normalized actions.

### Stage H: Graph Memory Update

Input:

- Current policy graph.
- Simulation events.

Process:

1. Select critical events, especially events with a critical stance.
2. Convert recurring concerns into memory risk nodes.
3. Link memory risk nodes back to source graph nodes.
4. Attach citations from the triggering simulation events.
5. Increment the graph memory revision.
6. Store event IDs used for graph-memory updates.

Output:

- Updated graph nodes.
- Updated graph edges.
- Memory revision.
- Memory event references.

### Stage I: Report Generation

Input:

- Project metadata.
- Document chunks.
- Simulation events.

Process:

1. Count and analyze simulation events by stance, group, concern, and risk narrative.
2. Identify critical events and recurring issues.
3. Retrieve evidence chunks relevant to the project objective, risk, access, impact, and implementation concerns.
4. Generate report sections such as executive summary, findings, evidence, and recommendations.
5. Generate risk entries with level, trend, evidence, and citations.
6. Attach structured citations to report sections and risks.
7. Validate provider outputs against expected response contracts.

In the richer report-agent path, report generation can use a ReACT-style loop:

1. Plan the report outline.
2. Fetch simulation and graph context.
3. Call tools such as search, insight extraction, panorama, or interview utilities.
4. Generate sections iteratively.
5. Log thoughts, tool calls, tool results, and section output for auditability.

Output:

- Report ID.
- Report version.
- Report title.
- Report sections.
- Risk narratives.
- Structured citations.

### Stage J: Follow-Up Interaction and Interviews

Input:

- User question.
- Selected tool type: report, persona, evidence, risk, compare, or revision.
- Optional persona group.
- Current simulation state.
- Document chunks.

Process:

1. Select simulation events relevant to the requested persona group or tool context.
2. Retrieve document chunks relevant to the user question.
3. Choose an answer strategy based on tool type.
4. Generate an answer that references relevant events, report sections, or evidence chunks.
5. Return citation IDs and structured evidence citations.

For persona interviews:

1. Select target personas.
2. Retrieve events associated with each persona.
3. Generate an answer from each persona perspective.
4. Attach persona citations and related event IDs.
5. Summarize the interview across personas.

Output:

- Follow-up answer.
- Event citations.
- Evidence citations.
- Persona interview answers when requested.

### Stage K: Evaluation

Input:

- Deterministic fixtures.
- Source set.
- Required concepts.
- Report claims.

Process:

1. Compare report claim text against required concepts.
2. Validate whether citation references identify known fixture sources.
3. Measure whether evidence-requiring claims contain at least one valid citation.
4. Emit JSON evaluation results.
5. Fail the evaluation when any aggregate metric falls below the configured threshold.

Evaluation metrics:

- `concept_recall`: required concepts present in report claim text.
- `citation_validity`: citation references that identify a fixture source.
- `citation_coverage`: evidence-requiring claims with at least one valid citation.

Output:

- Evaluation JSON.
- Pass/fail result based on threshold.

## Architecture Overview

RekaKebijakan uses a React frontend and a FastAPI backend. PostgreSQL stores durable workflow state, documents, chunks, jobs, projects, scenarios, runs, reports, and provenance. Uploaded files can be stored locally or in Firebase Storage. Background workers execute workflow jobs with leases, retries, heartbeats, and stale-revision checks.

The backend supports two provider families:

- Deterministic provider for offline, reproducible generation and evaluation.
- OpenAI-compatible or OASIS-enabled path for richer ontology, profile, simulation, and reporting workflows.

The full runtime can integrate with Zep for graph memory and OASIS for social simulation. This enables graph entities to become agents, platform actions to stream into storage, and completed events to update temporal graph memory.

## Evidence and Provenance

Evidence traceability is a central product principle. Every important artifact should be inspectable and connected to its source where possible.

The provenance model supports citations to:

- Document chunks.
- Simulation events.
- Graph nodes.
- Interview answers.
- Report sections.

This design prevents generated findings from becoming disconnected from their evidence base. It also allows reviewers to distinguish between statements grounded in uploaded documents and statements derived from synthetic simulation behavior.

## Responsible Use

RekaKebijakan should be used as an early-warning and exploration system, not as an automated policy decision-maker.

Responsible-use principles:

- Treat synthetic personas as scenario approximations, not real citizens.
- Treat simulation outputs as exploratory signals, not predictions.
- Use findings to improve consultation design and policy review.
- Validate high-impact recommendations with affected communities and experts.
- Preserve uncertainty, citation gaps, and assumption boundaries.

## Expected Impact

RekaKebijakan can help policy teams improve early-stage analysis by making stakeholder concerns, implementation risks, and evidence gaps visible sooner. The expected impact includes faster policy review cycles, more transparent reasoning, better-prepared public communication, and more targeted consultation with affected groups.

For proposal purposes, the most important contribution is the combination of simulation and provenance. RekaKebijakan does not only generate outputs; it preserves the chain from source documents to graph entities, personas, simulation events, reports, and follow-up answers.
