# RekaKebijakan Product Brief

## Overview

RekaKebijakan is an early-stage public policy simulation platform for exploring how policy drafts, programs, or regulatory changes may be interpreted by affected groups before implementation.

The product helps policy teams turn source documents into a structured policy graph, generate synthetic stakeholder personas, run bounded scenario simulations, and produce evidence-aware reports that preserve citations back to the original sources and simulation events.

RekaKebijakan is designed as decision-support infrastructure. It is not a replacement for public consultation, legal review, or domain-expert judgment.

## Product Problem

Policy teams often need to reason about social impact before a policy is deployed, but early analysis is constrained by incomplete evidence, fragmented stakeholder maps, and slow feedback loops. Draft regulations and program documents may contain technical language that different groups interpret differently. Risk narratives can form before official clarification, while indirect impacts may only become visible after rollout.

RekaKebijakan addresses this gap by providing a repeatable simulation workflow that surfaces likely stakeholder concerns, narrative risks, evidence gaps, and follow-up questions while keeping outputs traceable to source material.

## Target Users

- Policy analysis units evaluating draft regulations, programs, or implementation plans.
- Local governments reviewing service delivery, MSME, community, or vulnerable-group impacts.
- Researchers and academic teams testing policy hypotheses with traceable scenarios.
- Civil society organizations identifying stakeholder risks and consultation priorities.

## Value Proposition

RekaKebijakan helps teams move from static documents to structured, inspectable policy simulations.

Core value:

- Map affected groups, policy issues, obligations, risks, and relationships from uploaded sources.
- Convert policy graph entities into synthetic personas grounded in available evidence.
- Run scenario simulations across bounded rounds and channels.
- Track support, concern, narrative risk, and emerging issues over time.
- Generate reports with structured citations and evidence references.
- Ask follow-up questions about reports, personas, evidence, risks, comparisons, and revisions.

## Core Workflow

RekaKebijakan uses a five-stage workflow.

1. **Source Intake**
   Users create a policy project by providing project metadata, an institution or team name, an analysis objective, and source files such as PDF, DOCX, Markdown, or text documents.

2. **Graph Build**
   The system extracts policy concepts, stakeholder groups, issues, objectives, risks, indicators, and relationships into a source-grounded policy graph.

3. **Environment Setup**
   The system prepares simulation configuration, creates synthetic personas from eligible graph entities, and links them to evidence where possible.

4. **Simulation**
   Personas respond to the policy scenario across configured rounds. In the full runtime, Twitter-like and Reddit-like social environments can run in parallel through the bundled OASIS simulation engine.

5. **Report and Interaction**
   The system generates report sections, risk narratives, cited evidence, and follow-up tools for questioning findings, interviewing personas, comparing scenarios, and exploring revisions.

## Key Capabilities

### Document-Grounded Project Creation

Users can upload real policy sources and define the question they want to test. Uploaded documents are parsed, chunked, and assigned stable evidence identifiers so downstream artifacts can cite the source material.

### Policy Graph Construction

The graph captures entities and relationships relevant to the policy scenario, such as affected groups, implementing institutions, obligations, risks, issues, and indicators. Users can provide feedback on graph nodes and edges, with downstream artifacts invalidated when reviewed graph changes affect the simulation context.

### Synthetic Persona Generation

Graph entities can become synthetic personas with roles, stances, concerns, topics, and group membership. Personas are meant to approximate plausible viewpoints for scenario exploration, not represent real individuals.

### Scenario Simulation

The simulation engine produces event streams across rounds and channels. Events record persona statements, concerns, stance, risk narratives, influence sources, platform metadata, and citations where available.

### Evidence-Aware Reporting

Reports summarize findings, risks, and policy-relevant observations while preserving citations to documents, graph nodes, simulation events, interview answers, or report sections. The frontend exposes citation details instead of synthesizing missing evidence.

### Follow-Up Interaction

Users can ask questions about the generated report, inspect persona viewpoints, request evidence explanations, review risk narratives, compare scenarios, and explore revision-oriented questions.

### Scenario and Persona Control

The product supports scenario configuration, persona overrides, custom personas, run controls, version-aware mutations, and project lifecycle operations for managing policy experiments over time.

## Evidence and Provenance Principles

RekaKebijakan treats evidence traceability as a core product requirement.

- Source documents are preserved separately from generated outputs.
- Document chunks use stable identifiers for citation and retrieval.
- Graph nodes, report sections, risks, and interaction answers expose structured evidence references.
- Model-provided source IDs are not trusted without backend validation against stored evidence.
- Internal storage paths are not exposed through project or evidence APIs.

The product should make uncertainty visible. When a finding is based on simulation behavior rather than source evidence, the interface should preserve that distinction.

## Simulation Model

RekaKebijakan supports two simulation modes.

- **Deterministic provider:** A reproducible, offline provider for local development, tests, and network-free evaluation.
- **OASIS runtime:** A fuller social simulation runtime where graph entities become agents, platform worlds run in parallel, actions stream into PostgreSQL, and completed actions can update temporal graph memory.

Both modes should preserve the same product contract: bounded scenarios, inspectable outputs, and evidence-aware reporting.

## Responsible Use

RekaKebijakan is intended to support earlier, better-informed policy analysis. It should not be used as a sole basis for policy decisions.

Responsible-use expectations:

- Treat personas as synthetic approximations, not actual public opinion.
- Use findings to identify questions, risks, and consultation priorities.
- Validate high-impact recommendations with affected communities and subject-matter experts.
- Preserve citations and expose evidence gaps rather than overclaiming certainty.
- Avoid representing simulation outputs as predictions of real-world outcomes.

## Current Product Status

The current implementation is a prototype with a React frontend and FastAPI backend. It supports authenticated user workspaces, project creation, document upload, graph construction, environment generation, simulation runs, reports, interactions, interviews, provenance, and deterministic evaluation.

The full Docker workflow can run the bundled OASIS runtime when configured with the required external services. Demo-mode flows remain available for local frontend scenarios.

## Success Criteria

Product success should be evaluated by whether RekaKebijakan helps users produce more grounded and reviewable policy analysis earlier in the policy design process.

Practical signals include:

- Users can upload source material and receive a coherent policy graph.
- Personas and simulation events reflect source-grounded stakeholder concerns.
- Reports include valid citations and sufficient citation coverage.
- Users can trace claims back to documents, events, or graph elements.
- Follow-up questions reveal useful risks, evidence gaps, or revision options.
- Teams can compare scenarios without losing provenance or version context.

Formal evaluation currently focuses on concept recall, citation validity, and citation coverage through deterministic fixtures.
