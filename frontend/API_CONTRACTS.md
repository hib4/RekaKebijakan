# Frontend API v1 contracts

The production workspace uses `/api/v1`. JSON mutations use `Content-Type: application/json`; authenticated requests include cookies. Existing `/api/simulations/*` calls remain only as the compatibility bridge for the five-step workflow and `demo-*` continues to use local demo data.

## Concurrency and errors

- Mutable projects, scenarios, persona overrides, and runs expose an integer `version`.
- Mutations send `expected_version`, `expected_scenario_version`, or `base_environment_revision` as named by the endpoint.
- A stale write should return `409` with the standard `{ error: { code, message, details } }` envelope.
- Deletes are explicit server operations. Project/scenario duplication is performed server-side and returns a new resource ID.

## Projects and scenarios

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/projects/:id/duplicate` | Deep-copy a project and owned resources |
| `POST` | `/api/v1/projects/bulk-actions` | Archive, restore, or schedule deletion for `project_ids` |
| `DELETE` | `/api/v1/projects/:id` | Schedule a project for deletion during the retention period |
| `POST` | `/api/v1/projects/:id/scenarios/:scenarioId/duplicate` | Copy a scenario |
| `POST` | `/api/v1/projects/:id/scenarios/:scenarioId/archive` | Archive a scenario |
| `DELETE` | `/api/v1/projects/:id/scenarios/:scenarioId` | Delete a scenario |
| `POST` | `/api/v1/projects/:id/scenarios/compare` | Compare `scenario_ids`; returns scenarios and field differences |
| `POST` | `/api/v1/projects/:id/scenarios/:scenarioId/runs` | Start a version-pinned scenario run |

## Personas and graph review

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/projects/:id/scenarios/:scenarioId/personas` | Effective persona list with `source` and `active` |
| `PUT` | `/api/v1/projects/:id/scenarios/:scenarioId/persona-overrides/:personaId` | Create/update an override |
| `DELETE` | same override URL | Reset to the environment persona |
| `POST` | `/api/v1/projects/:id/scenarios/:scenarioId/personas` | Create a custom synthetic persona |
| `PATCH` | `/api/v1/projects/:id/scenarios/:scenarioId/personas/bulk` | Apply a patch to `persona_ids` |
| `POST` | `/api/v1/projects/:id/graph/feedback` | Accept, reject, or comment on a graph/node/edge |

## Runs and interaction

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/runs/:runId` | Current run status and version |
| `GET` | `/api/v1/runs/:runId/events?cursor=...` | Event page with `next_cursor` and current run |
| `POST` | `/api/v1/runs/:runId/pause` | Pause with `expected_version` |
| `POST` | `/api/v1/runs/:runId/resume` | Resume with `expected_version` |
| `POST` | `/api/v1/runs/:runId/cancel` | Cancel with `expected_version` |
| `POST` | `/api/v1/runs/:runId/interviews` | Persona/group interview; returns distinct answers |
| `POST` | `/api/v1/runs/:runId/interactions` | Report, evidence, compare, or revision tool response |

Event cursors are opaque. Clients append events by unique event ID, advance only to `next_cursor`, and continue polling while the run is queued, running, or paused.

## Provenance and contact

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/projects/:id/provenance` | Evidence chains, optionally filtered by subject type and ID |
| `POST` | `/api/v1/contact-requests` | Store a public pilot/contact request |

Provenance citations use `source_type`, `source_id`, optional document/chunk IDs, locator, label, and exact quote. The frontend displays these values without synthesizing missing evidence.
