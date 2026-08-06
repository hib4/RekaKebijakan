from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from .errors import InvalidControl, ResourceNotFound, RevisionConflict, StageConflict, UnsupportedDocument
from .auth import current_user
from .models import (
    EnvironmentInput,
    EnvironmentUpdateInput,
    GraphFeedbackInput,
    InteractionInput,
    InterviewInput,
    CustomPersonaInput,
    CustomPersonaUpdateInput,
    PersonaBulkInput,
    PilotContactInput,
    ProjectBulkLifecycleInput,
    ProjectDuplicateInput,
    PersonaOverrideDeleteInput,
    PersonaOverrideInput,
    ProjectInput,
    ProjectUpdateInput,
    ScenarioInput,
    ScenarioUpdateInput,
    SimulationInput,
)

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(current_user)])
public_router = APIRouter(prefix="/api")


def service(request: Request):
    return request.app.state.workflow


def repository(request: Request):
    return request.app.state.repository


def user_id(request: Request) -> str:
    return current_user(request)["id"]


def require_state(request: Request, simulation_id: str):
    state = repository(request).get_for_user(simulation_id, user_id(request))
    if not state:
        raise ResourceNotFound()
    actions = repository(request).list_oasis_actions(simulation_id, limit=5000)
    engine = state.get("environment", {}).get("config", {}).get("engine")
    if actions and engine == "oasis":
        state = dict(state)
        events = [dict(item["event"]) | {"sequence": item["sequence"]} for item in actions]
        state["simulation"] = dict(state.get("simulation", {})) | {
            "events": events, "event_count": len(events),
        }
    return state


async def silent_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except (JSONDecodeError, UnicodeDecodeError, RuntimeError):
        return {}
    return payload if isinstance(payload, dict) else {}


async def start_stage(request: Request, simulation_id: str, stage: str, payload: dict | None = None):
    if stage not in {"graph", "environment", "simulation", "report"}:
        raise ResourceNotFound()
    try:
        state = await run_in_threadpool(service(request).start, simulation_id, stage, payload, user_id(request))
    except ValueError as error:
        raise StageConflict(str(error)) from error
    if not state:
        raise ResourceNotFound()
    return JSONResponse(state, status_code=202)


@public_router.get("/health")
async def health():
    return {"status": "ok", "service": "rekakebijakan", "engine": "configurable"}


@public_router.post("/pilot/contact", status_code=201)
@public_router.post("/v1/contact-requests", status_code=201, include_in_schema=False)
async def pilot_contact(request: Request):
    payload = await silent_json(request)
    if "organization" in payload or "use_case" in payload:
        payload = {
            "name": payload.get("name"), "email": payload.get("email"),
            "institution": payload.get("organization"), "message": payload.get("use_case"), "consent": True,
        }
    model = PilotContactInput.model_validate(payload)
    row = await run_in_threadpool(repository(request).create_pilot_contact, model.model_dump())
    return {"id": row["id"], "created_at": row["created_at"], "received_at": row["created_at"], "status": "received"}


@router.post("/projects")
@v1_router.post("/projects", include_in_schema=False)
async def create_project(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
):
    form = await request.form()
    values = {
        "project_name": form.get("project_name") or form.get("name"),
        "institution": form.get("institution"),
        "objective": form.get("objective") or form.get("description"),
    }
    model = ProjectInput.model_validate(values)
    files = [item for item in form.getlist("files") if hasattr(item, "file")]
    try:
        state = await run_in_threadpool(
            service(request).create_project,
            model.model_dump(), files, user_id(request), idempotency_key.strip() if idempotency_key else None,
        )
    except ValueError as error:
        raise UnsupportedDocument(str(error)) from error
    return JSONResponse({"id": state["project"]["id"], "project": state["project"], "simulation_id": state["id"]}, status_code=201)


@router.get("/projects")
async def list_projects(request: Request):
    result = await run_in_threadpool(repository(request).list_projects, user_id(request), "", "active", 100, 0)
    return {"projects": [project_summary(row) for row in result["items"]]}


@router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str):
    row = await run_in_threadpool(repository(request).project, project_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    documents = await run_in_threadpool(repository(request).public_documents, row["simulation_id"])
    return project_summary(row) | {"documents": documents}


def project_summary(row: dict) -> dict:
    state = row["state"]
    report = state.get("report", {})
    risks = report.get("risks", [])
    risk_order = {"Rendah": 1, "Sedang": 2, "Tinggi": 3}
    highest = max((item.get("level", "Rendah") for item in risks), key=lambda value: risk_order.get(value, 0), default="Rendah")
    return {
        "id": row["id"], "name": row["name"], "project_name": row["name"], "institution": row["institution"],
        "objective": row["objective"], "status": row["status"], "version": row["version"],
        "simulation_id": row["simulation_id"], "current_stage": state.get("current_stage", "graph"),
        "workflow_status": state.get("status", "ready"), "highest_risk": highest,
        "report_available": bool(report.get("sections")), "updated_at": row["updated_at"],
        "created_at": row["created_at"], "archived_at": row["archived_at"],
        "delete_after": row.get("delete_after"), "deleted_at": row.get("deleted_at"),
        "pending_delete": row["status"] == "pending_delete",
        "scenario_count": row.get("scenario_count", 0),
    }


def run_summary(row: dict, state: dict | None = None) -> dict:
    state = state or {}
    simulation = state.get("simulation", {})
    stage = state.get("stages", {}).get("simulation", {})
    events = (row.get("output_snapshot") or {}).get("simulation", {}).get("events") or simulation.get("events", [])
    environment_config = row.get("input_snapshot", {}).get("environment", {}).get("config", {})
    rounds = int(environment_config.get("rounds", environment_config.get("max_rounds", 10)))
    return {
        **row, "run_id": row["id"], "version": 1, "engine": row.get("engine", "deterministic"),
        "progress": 100 if row["status"] == "completed" else int(stage.get("progress", 0)),
        "current_round": max((int(item.get("round", 0)) for item in events), default=0),
        "total_rounds": rounds, "event_count": len(events),
        "updated_at": row.get("completed_at") or row.get("started_at") or row["created_at"],
    }


@v1_router.get("/projects")
async def list_projects_v1(
    request: Request,
    q: str = Query(default="", max_length=160),
    status: str = Query(default="active", pattern="^(draft|active|archived|pending_delete|deleted|all)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    result = await run_in_threadpool(
        repository(request).list_projects, user_id(request), q, status, limit, offset
    )
    return {"items": [project_summary(row) for row in result["items"]], "total": result["total"], "limit": result["limit"], "offset": result["offset"]}


@v1_router.get("/projects/{project_id}")
async def get_project_v1(request: Request, project_id: str):
    row = await run_in_threadpool(repository(request).project, project_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    return project_summary(row) | {
        "documents": await run_in_threadpool(repository(request).public_documents, row["simulation_id"]),
        "snapshot": row["state"],
    }


@v1_router.patch("/projects/{project_id}")
async def update_project_v1(request: Request, project_id: str):
    model = ProjectUpdateInput.model_validate(await silent_json(request))
    row = await run_in_threadpool(
        repository(request).update_project, project_id, user_id(request), model.expected_version,
        model.model_dump(exclude={"expected_version"}, exclude_none=True),
    )
    if not row:
        existing = await run_in_threadpool(repository(request).project, project_id, user_id(request))
        if existing:
            raise RevisionConflict()
        raise ResourceNotFound()
    return dict(row)


async def project_status(request: Request, project_id: str, status: str):
    try:
        row = await run_in_threadpool(repository(request).set_project_status, project_id, user_id(request), status)
    except ValueError as error:
        row = None
        if "active job" in str(error).lower():
            for _ in range(10):
                await asyncio.sleep(0.01)
                try:
                    row = await run_in_threadpool(repository(request).set_project_status, project_id, user_id(request), status)
                    break
                except ValueError:
                    continue
        if not row:
            raise StageConflict(str(error)) from error
    if not row:
        raise ResourceNotFound()
    return row


@v1_router.post("/projects/{project_id}/archive")
async def archive_project_v1(request: Request, project_id: str):
    return await project_status(request, project_id, "archived")


@v1_router.post("/projects/{project_id}/restore")
async def restore_project_v1(request: Request, project_id: str):
    return await project_status(request, project_id, "active")


@v1_router.delete("/projects/{project_id}")
async def delete_project_v1(request: Request, project_id: str):
    return await project_status(request, project_id, "pending_delete")


@v1_router.post("/projects/{project_id}/duplicate", status_code=201)
async def duplicate_project_v1(request: Request, project_id: str):
    model = ProjectDuplicateInput.model_validate(await silent_json(request))
    state = await run_in_threadpool(service(request).duplicate_project, project_id, user_id(request), model.name)
    if not state:
        raise ResourceNotFound()
    row = await run_in_threadpool(repository(request).project, state["project"]["id"], user_id(request))
    return project_summary(row)


@v1_router.post("/projects/bulk-lifecycle")
@v1_router.post("/projects/bulk-actions", include_in_schema=False)
async def bulk_project_lifecycle_v1(request: Request):
    model = ProjectBulkLifecycleInput.model_validate(await silent_json(request))
    target = {"archive": "archived", "restore": "active", "delete": "pending_delete"}[model.action]
    items = []
    for project_id in model.project_ids:
        try:
            row = await run_in_threadpool(repository(request).set_project_status, project_id, user_id(request), target)
            items.append({"id": project_id, "ok": bool(row), "status": row.get("status") if row else None})
        except ValueError as error:
            items.append({"id": project_id, "ok": False, "error": str(error)})
    return {
        "items": items,
        "succeeded": sum(item["ok"] for item in items),
        "failed": [{"id": item["id"], "message": item.get("error", "Resource tidak ditemukan")} for item in items if not item["ok"]],
    }


@v1_router.get("/projects/{project_id}/scenarios")
async def list_scenarios_v1(request: Request, project_id: str):
    items = await run_in_threadpool(repository(request).list_scenarios, project_id, user_id(request))
    if items is None:
        raise ResourceNotFound()
    return {"items": items}


@v1_router.post("/projects/{project_id}/scenarios", status_code=201)
async def create_scenario_v1(request: Request, project_id: str):
    model = ScenarioInput.model_validate(await silent_json(request))
    row = await run_in_threadpool(
        repository(request).create_scenario, project_id, user_id(request), model.model_dump(exclude_none=True)
    )
    if not row:
        raise ResourceNotFound()
    return row


@v1_router.get("/projects/{project_id}/scenarios/{scenario_id}")
async def get_scenario_v1(request: Request, project_id: str, scenario_id: str):
    row = await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    return row


@v1_router.patch("/projects/{project_id}/scenarios/{scenario_id}")
async def update_scenario_v1(request: Request, project_id: str, scenario_id: str):
    model = ScenarioUpdateInput.model_validate(await silent_json(request))
    row = await run_in_threadpool(
        repository(request).update_scenario,
        project_id,
        scenario_id,
        user_id(request),
        model.expected_version,
        model.model_dump(exclude={"expected_version"}, exclude_none=True),
    )
    if row:
        return row
    if await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request)):
        raise RevisionConflict()
    raise ResourceNotFound()


async def scenario_archive_status(request: Request, project_id: str, scenario_id: str, archived: bool):
    row = await run_in_threadpool(
        repository(request).set_scenario_archived, project_id, scenario_id, user_id(request), archived
    )
    if row:
        return row
    if await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request)):
        raise StageConflict("Skenario sudah berada pada status tersebut atau proyek tidak aktif")
    raise ResourceNotFound()


@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/archive")
async def archive_scenario_v1(request: Request, project_id: str, scenario_id: str):
    return await scenario_archive_status(request, project_id, scenario_id, True)


@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/restore")
async def restore_scenario_v1(request: Request, project_id: str, scenario_id: str):
    return await scenario_archive_status(request, project_id, scenario_id, False)


@v1_router.delete("/projects/{project_id}/scenarios/{scenario_id}")
async def delete_scenario_v1(request: Request, project_id: str, scenario_id: str):
    removed = await run_in_threadpool(
        repository(request).delete_scenario, project_id, scenario_id, user_id(request)
    )
    if not removed:
        raise ResourceNotFound()
    return {"ok": True}


@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/duplicate", status_code=201)
async def duplicate_scenario_v1(request: Request, project_id: str, scenario_id: str):
    payload = await silent_json(request)
    row = await run_in_threadpool(repository(request).duplicate_scenario, project_id, scenario_id, user_id(request), payload.get("name"))
    if not row:
        raise ResourceNotFound()
    return row


@v1_router.get("/projects/{project_id}/scenarios/{scenario_id}/personas")
async def effective_personas_v1(request: Request, project_id: str, scenario_id: str):
    items = await run_in_threadpool(
        repository(request).effective_personas, project_id, scenario_id, user_id(request)
    )
    if items is None:
        raise ResourceNotFound()
    return {"items": items}


@v1_router.post("/projects/{project_id}/scenarios/compare")
async def compare_scenarios_v1(request: Request, project_id: str):
    from .models import ScenarioCompareInput
    model = ScenarioCompareInput.model_validate(await silent_json(request))
    rows = []
    for scenario_id in model.scenario_ids:
        row = await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request))
        if not row:
            raise ResourceNotFound()
        rows.append(row)
    fields = ("name", "description", "kind", "config", "persona_overrides")
    differences = [
        {"field": field, "values": {row["id"]: row[field] for row in rows}}
        for field in fields if len({str(row[field]) for row in rows}) > 1
    ]
    return {"scenarios": rows, "differences": differences}


@v1_router.put("/projects/{project_id}/scenarios/{scenario_id}/persona-overrides/{persona_id}")
async def put_persona_override_v1(request: Request, project_id: str, scenario_id: str, persona_id: str):
    model = PersonaOverrideInput.model_validate(await silent_json(request))
    try:
        row = await run_in_threadpool(
            repository(request).put_persona_override,
            project_id,
            scenario_id,
            persona_id,
            user_id(request),
            model.expected_version,
            model.base_environment_revision,
            model.patch.model_dump(exclude_none=True),
        )
    except ValueError as error:
        raise RevisionConflict() from error
    except KeyError as error:
        raise ResourceNotFound() from error
    if row:
        return row
    if await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request)):
        raise RevisionConflict()
    raise ResourceNotFound()


@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/personas", status_code=201)
async def create_custom_persona_v1(request: Request, project_id: str, scenario_id: str):
    model = CustomPersonaInput.model_validate(await silent_json(request))
    row = await run_in_threadpool(repository(request).create_custom_persona, project_id, scenario_id, user_id(request), model.model_dump(exclude={"expected_version"}))
    if not row:
        raise ResourceNotFound()
    return row


@v1_router.patch("/projects/{project_id}/scenarios/{scenario_id}/personas/{persona_id}")
async def update_custom_persona_v1(request: Request, project_id: str, scenario_id: str, persona_id: str):
    model = CustomPersonaUpdateInput.model_validate(await silent_json(request))
    row = await run_in_threadpool(repository(request).update_custom_persona, project_id, scenario_id, persona_id,
                                  user_id(request), model.model_dump(exclude_none=True))
    if not row:
        raise ResourceNotFound()
    return row


@v1_router.delete("/projects/{project_id}/scenarios/{scenario_id}/personas/{persona_id}")
async def delete_custom_persona_v1(request: Request, project_id: str, scenario_id: str, persona_id: str):
    removed = await run_in_threadpool(repository(request).delete_custom_persona, project_id, scenario_id, persona_id, user_id(request))
    if not removed:
        raise ResourceNotFound()
    return {"ok": True}


@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/personas/bulk-activation")
async def bulk_persona_activation_v1(request: Request, project_id: str, scenario_id: str):
    model = PersonaBulkInput.model_validate(await silent_json(request))
    try:
        row = await run_in_threadpool(repository(request).bulk_persona_activation, project_id, scenario_id, user_id(request),
            model.persona_ids, model.active, model.expected_version, model.base_environment_revision)
    except (KeyError, ValueError) as error:
        raise RevisionConflict() from error
    if not row:
        raise RevisionConflict()
    return row


@v1_router.patch("/projects/{project_id}/scenarios/{scenario_id}/personas/bulk")
async def bulk_persona_patch_v1(request: Request, project_id: str, scenario_id: str):
    from .models import PersonaBulkPatchInput
    model = PersonaBulkPatchInput.model_validate(await silent_json(request))
    patch = model.patch.model_dump(exclude_none=True)
    if set(patch) != {"active"}:
        raise StageConflict("Aksi massal saat ini hanya mendukung status aktif")
    scenario = await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request))
    if not scenario:
        raise ResourceNotFound()
    row = await run_in_threadpool(
        repository(request).bulk_persona_activation, project_id, scenario_id, user_id(request),
        model.persona_ids, patch["active"], model.expected_version,
        model.base_environment_revision if model.base_environment_revision is not None else scenario["base_environment_revision"],
    )
    if not row:
        raise RevisionConflict()
    items = await run_in_threadpool(repository(request).effective_personas, project_id, scenario_id, user_id(request))
    return {"items": items, "scenario": row}


@v1_router.delete("/projects/{project_id}/scenarios/{scenario_id}/persona-overrides/{persona_id}")
async def delete_persona_override_v1(request: Request, project_id: str, scenario_id: str, persona_id: str):
    model = PersonaOverrideDeleteInput.model_validate(await silent_json(request))
    scenario = await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request))
    if not scenario:
        raise ResourceNotFound()
    try:
        row = await run_in_threadpool(
            repository(request).put_persona_override,
            project_id,
            scenario_id,
            persona_id,
            user_id(request),
            model.expected_version,
            model.base_environment_revision if model.base_environment_revision is not None else scenario["base_environment_revision"],
            None,
        )
    except ValueError as error:
        raise RevisionConflict() from error
    except KeyError as error:
        raise ResourceNotFound() from error
    if not row:
        raise RevisionConflict()
    return row


@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/run")
@v1_router.post("/projects/{project_id}/scenarios/{scenario_id}/runs", include_in_schema=False)
async def run_scenario_v1(request: Request, project_id: str, scenario_id: str):
    from .models import ScenarioRunInput
    model = ScenarioRunInput.model_validate(await silent_json(request))
    current = await run_in_threadpool(repository(request).scenario, project_id, scenario_id, user_id(request))
    if model.expected_scenario_version and current and current["version"] != model.expected_scenario_version:
        raise RevisionConflict()
    try:
        run = await run_in_threadpool(
            repository(request).prepare_scenario_run, project_id, scenario_id, user_id(request), None, model.engine
        )
    except ValueError as error:
        raise StageConflict(str(error)) from error
    if not run:
        raise ResourceNotFound()
    state = await run_in_threadpool(service(request).start, run["simulation_id"], "simulation", {"engine": run["engine"]}, user_id(request), run["id"])
    stored = await run_in_threadpool(repository(request).run, run["id"], user_id(request))
    return JSONResponse(jsonable_encoder(run_summary(stored, state)), status_code=202)


@v1_router.get("/projects/{project_id}/scenarios/{scenario_id}/runs")
async def list_scenario_runs_v1(request: Request, project_id: str, scenario_id: str):
    items = await run_in_threadpool(repository(request).list_runs, project_id, scenario_id, user_id(request))
    if items is None:
        raise ResourceNotFound()
    return {"items": items}


@v1_router.get("/projects/{project_id}/scenarios/{scenario_id}/comparison")
async def compare_scenario_runs_v1(request: Request, project_id: str, scenario_id: str, run_ids: str = ""):
    result = await run_in_threadpool(repository(request).compare_runs, project_id, scenario_id, user_id(request),
                                     [item for item in run_ids.split(",") if item] or None)
    if result is None:
        raise ResourceNotFound()
    return result


@v1_router.get("/runs/{run_id}")
async def get_scenario_run_v1(request: Request, run_id: str):
    row = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    return run_summary(row, await run_in_threadpool(repository(request).get_for_user, row["simulation_id"], user_id(request)))


@v1_router.get("/runs/{run_id}/events")
async def scenario_run_events_v1(request: Request, run_id: str, after: int = Query(default=0, ge=0), cursor: str | None = None):
    if cursor:
        try:
            after = max(after, int(cursor))
        except ValueError:
            after = 0
    items = await run_in_threadpool(repository(request).run_events, run_id, user_id(request), after)
    if items is None:
        raise ResourceNotFound()
    row = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    state = await run_in_threadpool(repository(request).get_for_user, row["simulation_id"], user_id(request))
    next_cursor = str(max([after, *[int(item.get("sequence", 0)) for item in items]])) if items else None
    return {"events": items, "items": items, "event_count": len(items), "next_cursor": next_cursor, "run": run_summary(row, state)}


@v1_router.get("/runs/{run_id}/actions")
async def scenario_run_actions_v1(request: Request, run_id: str, after: int = Query(default=0, ge=0), limit: int = Query(default=1000, ge=1, le=5000)):
    items = await run_in_threadpool(repository(request).run_oasis_actions, run_id, user_id(request), after, limit)
    if items is None:
        raise ResourceNotFound()
    return {"items": items, "next_cursor": str(items[-1]["sequence"]) if items else None}


@v1_router.get("/runs/{run_id}/artifacts")
async def scenario_run_artifacts_v1(request: Request, run_id: str):
    artifacts = await run_in_threadpool(repository(request).run_oasis_artifacts, run_id, user_id(request))
    if artifacts is None:
        raise ResourceNotFound()
    return {"posts": [], "comments": [], "timeline": [], "stats": [], **artifacts}


@v1_router.get("/runs/{run_id}/provenance")
async def scenario_run_provenance_v1(request: Request, run_id: str):
    row = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    return {"run_id": run_id, "provenance": row["provenance"], "input_snapshot": row["input_snapshot"],
            "logs": (row.get("output_snapshot") or {}).get("logs", [])}


@v1_router.get("/runs/{run_id}/logs")
async def scenario_run_logs_v1(request: Request, run_id: str):
    row = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    return {"items": (row.get("output_snapshot") or {}).get("logs", [])}


async def control_scenario_run_v1(request: Request, run_id: str, action: str):
    row = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    state = await control(request, row["simulation_id"], action)
    updated = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    return run_summary(updated, state)


@v1_router.post("/runs/{run_id}/pause")
async def pause_scenario_run_v1(request: Request, run_id: str):
    return await control_scenario_run_v1(request, run_id, "pause")


@v1_router.post("/runs/{run_id}/resume")
async def resume_scenario_run_v1(request: Request, run_id: str):
    return await control_scenario_run_v1(request, run_id, "resume")


@v1_router.post("/runs/{run_id}/cancel")
async def cancel_scenario_run_v1(request: Request, run_id: str):
    return await control_scenario_run_v1(request, run_id, "cancel")


@v1_router.post("/runs/{run_id}/reproduce", status_code=202)
async def reproduce_scenario_run_v1(request: Request, run_id: str):
    prepared = await run_in_threadpool(repository(request).prepare_reproduction, run_id, user_id(request))
    if not prepared:
        raise ResourceNotFound()
    state = await run_in_threadpool(service(request).start, prepared["simulation_id"], "simulation", {"engine": prepared["engine"]}, user_id(request), prepared["id"])
    return state | {"run_id": prepared["id"], "reproduces_run_id": run_id}


@v1_router.post("/runs/{run_id}/interviews", status_code=201)
async def create_run_interview_v1(request: Request, run_id: str):
    from .models import RunInterviewInput
    model = RunInterviewInput.model_validate(await silent_json(request))
    run = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    if not run:
        raise ResourceNotFound()
    persona_ids = model.persona_ids
    if model.group and not persona_ids:
        personas = run["input_snapshot"].get("environment", {}).get("personas", [])
        persona_ids = [item["id"] for item in personas if item.get("group") == model.group]
    result = await run_in_threadpool(
        service(request).interview, run["simulation_id"], model.question, persona_ids, user_id(request), run_id, model.platform
    )
    if not result:
        raise ResourceNotFound()
    answers = [{
        "id": item["id"], "role": "assistant", "author": item.get("persona_name") or item.get("persona_id", "Persona"),
        "tool": "interview", "text": item.get("answer", ""), "content": item.get("answer", ""),
        "citations": item.get("citations", []),
    } for item in result.get("answers", [])]
    return {"id": result["id"], "answers": answers}


@v1_router.post("/runs/{run_id}/interactions", status_code=201)
async def create_run_interaction_v1(request: Request, run_id: str):
    from .models import RunInteractionInput
    model = RunInteractionInput.model_validate(await silent_json(request))
    run = await run_in_threadpool(repository(request).run, run_id, user_id(request))
    if not run:
        raise ResourceNotFound()
    message = await run_in_threadpool(
        service(request).interact, run["simulation_id"], model.model_dump(), user_id(request)
    )
    if not message:
        raise ResourceNotFound()
    return message | {"content": message.get("text", "")}


@v1_router.get("/projects/{project_id}/provenance")
async def project_provenance_v1(request: Request, project_id: str):
    row = await run_in_threadpool(repository(request).project, project_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    stored = await run_in_threadpool(repository(request).citations, row["simulation_id"])
    grouped = {}
    for citation in stored:
        key = (citation["artifact_type"], citation["artifact_id"])
        grouped.setdefault(key, []).append(citation)
    return {"items": [{
        "id": f"{kind}:{artifact_id}", "subject_type": kind, "subject_id": artifact_id,
        "label": artifact_id, "citations": values, "inputs": [],
    } for (kind, artifact_id), values in grouped.items()]}


@v1_router.post("/projects/{project_id}/graph/feedback")
async def project_graph_feedback_v1(request: Request, project_id: str):
    payload = await silent_json(request)
    row = await run_in_threadpool(repository(request).project, project_id, user_id(request))
    if not row:
        raise ResourceNotFound()
    action = payload.get("action")
    if action == "accept":
        return {"accepted": True, "project_version": row["version"]}
    if action in {"reject", "comment"}:
        feedback = {
            "action": "update_node", "target_id": row["state"].get("graph", {}).get("nodes", [{}])[0].get("id"),
            "patch": {}, "reason": payload.get("comment") or "Graf memerlukan tinjauan lanjutan",
            "base_revision": row["state"].get("graph", {}).get("revision", 1),
        }
        if not feedback["target_id"]:
            raise StageConflict("Graf belum tersedia")
        await run_in_threadpool(service(request).apply_graph_feedback, row["simulation_id"], feedback, user_id(request))
        return {"accepted": True, "project_version": row["version"]}
    raise StageConflict("Aksi tinjauan graf tidak valid")


@v1_router.get("/dashboard")
async def dashboard_v1(request: Request):
    rows = await run_in_threadpool(repository(request).dashboard_projects, user_id(request))
    items = [project_summary(row) for row in rows]
    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "metrics": {
            "active_projects": len(items),
            "running_simulations": sum(item["workflow_status"] in {"processing", "running", "paused"} for item in items),
            "review_items": sum(item["highest_risk"] == "Tinggi" for item in items),
            "available_reports": sum(item["report_available"] for item in items),
        },
        "recent_projects": items[:10],
        "active_runs": [item for item in items if item["workflow_status"] in {"processing", "running", "paused"}][:10],
        "attention": [item for item in items if item["highest_risk"] == "Tinggi"][:10],
    }


@router.get("/simulations/{simulation_id}")
async def get_simulation(request: Request, simulation_id: str):
    return require_state(request, simulation_id)


@router.get("/simulations/{simulation_id}/stream")
async def simulation_stream(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    raw_cursor = request.headers.get("last-event-id") or request.query_params.get("after") or "0"
    try:
        cursor = max(0, int(raw_cursor))
    except ValueError:
        cursor = 0

    async def events():
        nonlocal cursor
        yield "retry: 2000\n: aliran terhubung\n\n"
        heartbeat_at = asyncio.get_running_loop().time()
        while not await request.is_disconnected():
            rows = await run_in_threadpool(repository(request).list_workflow_events, simulation_id, cursor, 200)
            for row in rows:
                cursor = int(row["sequence"])
                payload = json.dumps(jsonable_encoder(row["payload"]), ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {row['type']}\ndata: {payload}\n\n"
            now = asyncio.get_running_loop().time()
            if now - heartbeat_at >= 15:
                yield f": heartbeat {cursor}\n\n"
                heartbeat_at = now
            if not rows:
                await asyncio.sleep(0.5)

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@router.post("/simulations/{simulation_id}/stages/{stage}/start")
@router.post("/simulations/{simulation_id}/{stage}/start", include_in_schema=False)
@router.post("/simulations/{simulation_id}/start/{stage}", include_in_schema=False)
async def stage_alias(request: Request, simulation_id: str, stage: str):
    payload = await silent_json(request)
    if stage == "environment":
        payload = EnvironmentInput.model_validate(payload).model_dump()
    elif stage == "simulation":
        payload = SimulationInput.model_validate(payload).model_dump(exclude_none=True)
    return await start_stage(request, simulation_id, stage, payload)


@router.post("/simulations/{simulation_id}/graph-build")
async def graph_build(request: Request, simulation_id: str):
    return await start_stage(request, simulation_id, "graph")


@router.get("/simulations/{simulation_id}/graph")
async def get_graph(request: Request, simulation_id: str):
    return require_state(request, simulation_id)["graph"]


@router.get("/simulations/{simulation_id}/ontology")
async def get_ontology(request: Request, simulation_id: str):
    return require_state(request, simulation_id).get("ontology", {})


@router.post("/simulations/{simulation_id}/ontology/generate")
async def generate_ontology(request: Request, simulation_id: str):
    return await start_stage(request, simulation_id, "graph")


@router.get("/projects/{project_id}/chunks")
async def get_project_chunks(request: Request, project_id: str):
    states = await run_in_threadpool(repository(request).list_for_user, user_id(request))
    state = next((item for item in states if item["project"]["id"] == project_id), None)
    if not state:
        raise ResourceNotFound()
    return {"chunks": await run_in_threadpool(repository(request).chunks, state["id"])}


@router.post("/simulations/{simulation_id}/environment/generate")
async def generate_environment(request: Request, simulation_id: str):
    payload = EnvironmentInput.model_validate(await silent_json(request)).model_dump()
    return await start_stage(request, simulation_id, "environment", payload)


@router.get("/simulations/{simulation_id}/environment")
async def get_environment(request: Request, simulation_id: str):
    return require_state(request, simulation_id)["environment"]


@router.patch("/simulations/{simulation_id}/environment")
async def update_environment(request: Request, simulation_id: str):
    model = EnvironmentUpdateInput.model_validate(await silent_json(request))
    config = model.model_dump(exclude_unset=True, exclude_none=True)
    if model.rounds is not None:
        config.update(rounds=model.rounds, max_rounds=model.rounds)

    def update(state):
        from .service import now
        current = state["environment"].get("config", {})
        state["environment"]["config"] = current | config | {"overrides": current.get("overrides", {}) | config}
        state["revision"] = state.get("revision", 1) + 1
        state["updated_at"] = now()

    state = await run_in_threadpool(repository(request).mutate_for_user, simulation_id, user_id(request), update)
    if not state:
        raise ResourceNotFound()
    return state


@router.get("/simulations/{simulation_id}/personas")
async def get_personas(request: Request, simulation_id: str):
    state = require_state(request, simulation_id)
    return {"personas": state["environment"].get("personas", []), "persona_count": state["environment"].get("persona_count", 0)}


@router.post("/simulations/{simulation_id}/personas/generate")
async def generate_personas(request: Request, simulation_id: str):
    payload = EnvironmentInput.model_validate(await silent_json(request)).model_dump()
    return await start_stage(request, simulation_id, "environment", payload)


@router.get("/simulations/{simulation_id}/config")
async def get_config(request: Request, simulation_id: str):
    return require_state(request, simulation_id)["environment"].get("config", {})


@router.post("/simulations/{simulation_id}/config/generate")
async def generate_config(request: Request, simulation_id: str):
    payload = EnvironmentInput.model_validate(await silent_json(request)).model_dump()
    return await start_stage(request, simulation_id, "environment", payload)


@router.post("/simulations/{simulation_id}/runs")
async def create_run(request: Request, simulation_id: str):
    payload = SimulationInput.model_validate(await silent_json(request)).model_dump(exclude_none=True)
    return await start_stage(request, simulation_id, "simulation", payload)


@router.get("/runs/{simulation_id}")
async def get_run(request: Request, simulation_id: str):
    state = require_state(request, simulation_id)
    summary = await run_in_threadpool(repository(request).summarize_oasis_actions, simulation_id)
    mapping = await run_in_threadpool(repository(request).get_oasis_mapping, simulation_id)
    return state["simulation"] | {
        "id": simulation_id, "simulation_id": simulation_id,
        "platform_counts": summary["platform_counts"], "platform_rounds": summary["rounds"],
        "runtime": (mapping or {}).get("runtime_status") or (mapping or {}).get("metadata", {}).get("runtime_status", {}),
    }


@router.get("/runs/{simulation_id}/events")
async def get_events(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    try:
        after = int(request.query_params.get("after", "0"))
    except ValueError:
        after = 0
    actions = await run_in_threadpool(repository(request).list_oasis_actions, simulation_id, after, 1000)
    if actions:
        total = (await run_in_threadpool(repository(request).summarize_oasis_actions, simulation_id))["total_actions"]
        return {
            "events": [dict(item["event"]) | {"sequence": item["sequence"]} for item in actions],
            "event_count": total,
        }
    events = require_state(request, simulation_id)["simulation"].get("events", [])
    selected = [event for index, event in enumerate(events) if event.get("sequence", index + 1) > after]
    return {"events": selected, "event_count": len(events)}


@router.get("/simulations/{simulation_id}/oasis/status")
async def oasis_status(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    mapping = await run_in_threadpool(repository(request).get_oasis_mapping, simulation_id)
    summary = await run_in_threadpool(repository(request).summarize_oasis_actions, simulation_id)
    return {
        "enabled": bool(mapping), "mapping_status": (mapping or {}).get("status"),
        "zep_graph_id": (mapping or {}).get("zep_graph_id"),
        "external_simulation_id": (mapping or {}).get("external_simulation_id"),
        "runtime": (mapping or {}).get("runtime_status") or (mapping or {}).get("metadata", {}).get("runtime_status", {}),
        **summary,
    }


@router.get("/simulations/{simulation_id}/runtime-graph")
async def runtime_graph(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    graph = await run_in_threadpool(service(request).runtime_graph, simulation_id)
    if graph is None:
        return {"available": False}
    return {"available": True, **graph}


@router.get("/simulations/{simulation_id}/posts")
async def simulation_posts(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    mapping = await run_in_threadpool(repository(request).get_oasis_mapping, simulation_id)
    return {"items": (mapping or {}).get("artifacts", {}).get("posts", [])}


@router.get("/simulations/{simulation_id}/comments")
async def simulation_comments(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    mapping = await run_in_threadpool(repository(request).get_oasis_mapping, simulation_id)
    return {"items": (mapping or {}).get("artifacts", {}).get("comments", [])}


@router.get("/simulations/{simulation_id}/timeline")
async def simulation_timeline(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    mapping = await run_in_threadpool(repository(request).get_oasis_mapping, simulation_id)
    return {"items": (mapping or {}).get("artifacts", {}).get("timeline", [])}


@router.get("/simulations/{simulation_id}/agent-stats")
async def simulation_agent_stats(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    mapping = await run_in_threadpool(repository(request).get_oasis_mapping, simulation_id)
    return {"items": (mapping or {}).get("artifacts", {}).get("stats", [])}


async def control(request: Request, simulation_id: str, action: str):
    try:
        state = await run_in_threadpool(service(request).control, simulation_id, action, user_id(request))
    except ValueError as error:
        raise InvalidControl(str(error)) from error
    if not state:
        raise ResourceNotFound()
    return state


@router.post("/simulations/{simulation_id}/pause")
@router.post("/runs/{simulation_id}/pause")
async def pause(request: Request, simulation_id: str):
    return await control(request, simulation_id, "pause")


@router.post("/simulations/{simulation_id}/resume")
@router.post("/runs/{simulation_id}/resume")
async def resume(request: Request, simulation_id: str):
    return await control(request, simulation_id, "resume")


@router.post("/simulations/{simulation_id}/cancel")
@router.post("/runs/{simulation_id}/cancel")
async def cancel(request: Request, simulation_id: str):
    return await control(request, simulation_id, "cancel")


@router.post("/simulations/{simulation_id}/reports")
async def create_report(request: Request, simulation_id: str):
    return await start_stage(request, simulation_id, "report", await silent_json(request))


@router.get("/reports")
async def list_reports(request: Request):
    states = await run_in_threadpool(repository(request).list_for_user, user_id(request))
    return {"reports": [{**state["report"], "simulation_id": state["id"]} for state in states if state["report"].get("sections")]}


@router.get("/reports/{simulation_id}")
async def get_report(request: Request, simulation_id: str):
    return require_state(request, simulation_id)["report"] | {"simulation_id": simulation_id}


@router.get("/reports/{simulation_id}/markdown")
async def get_report_markdown(request: Request, simulation_id: str):
    report = require_state(request, simulation_id)["report"]
    return {"report_id": report.get("id"), "markdown": report.get("markdown_content", ""), "outline": report.get("outline")}


@router.get("/reports/{simulation_id}/agent-log")
async def get_report_agent_log(request: Request, simulation_id: str):
    return {"items": require_state(request, simulation_id)["report"].get("agent_log", [])}


@router.get("/reports/{simulation_id}/console-log")
async def get_report_console_log(request: Request, simulation_id: str):
    return {"items": require_state(request, simulation_id)["report"].get("console_log", [])}


@router.get("/reports/{simulation_id}/evidence")
async def get_evidence(request: Request, simulation_id: str):
    state = require_state(request, simulation_id)
    documents = await run_in_threadpool(repository(request).public_documents, simulation_id)
    chunks = await run_in_threadpool(repository(request).chunks, simulation_id)
    citations = await run_in_threadpool(repository(request).citations, simulation_id)
    return {"documents": documents, "chunks": chunks, "citations": citations, "events": state["simulation"].get("events", []), "risks": state["report"].get("risks", [])}


@router.get("/simulations/{simulation_id}/citations")
async def get_citations(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    return {"citations": await run_in_threadpool(repository(request).citations, simulation_id)}


@router.post("/simulations/{simulation_id}/interviews")
async def create_interview(request: Request, simulation_id: str):
    model = InterviewInput.model_validate(await silent_json(request))
    result = await run_in_threadpool(
        service(request).interview, simulation_id, model.question, model.persona_ids, user_id(request)
    )
    if not result:
        raise ResourceNotFound()
    return JSONResponse(result, status_code=201)


@router.post("/simulations/{simulation_id}/oasis/close")
async def close_oasis_environment(request: Request, simulation_id: str):
    try:
        result = await run_in_threadpool(service(request).close_oasis_environment, simulation_id, user_id(request))
    except ValueError as error:
        raise StageConflict(str(error)) from error
    if not result:
        raise ResourceNotFound()
    return result


@router.get("/simulations/{simulation_id}/interviews")
async def list_interviews(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    items = await run_in_threadpool(repository(request).persisted_interviews, simulation_id, user_id(request))
    return {"items": items or []}


@router.post("/simulations/{simulation_id}/graph/feedback")
async def graph_feedback(request: Request, simulation_id: str):
    model = GraphFeedbackInput.model_validate(await silent_json(request))
    try:
        state = await run_in_threadpool(
            service(request).apply_graph_feedback, simulation_id, model.model_dump(exclude_none=True), user_id(request)
        )
    except ValueError as error:
        raise StageConflict(str(error)) from error
    if not state:
        raise ResourceNotFound()
    return state["graph"]


@router.get("/simulations/{simulation_id}/graph/feedback")
async def list_graph_feedback(request: Request, simulation_id: str):
    require_state(request, simulation_id)
    items = await run_in_threadpool(repository(request).persisted_graph_feedback, simulation_id, user_id(request))
    return {"items": items or []}


@router.post("/simulations/{simulation_id}/interactions")
@router.post("/reports/{simulation_id}/interactions")
@router.post("/interactions/{simulation_id}/messages")
async def create_interaction(request: Request, simulation_id: str):
    model = InteractionInput.model_validate(await silent_json(request))
    message = await run_in_threadpool(service(request).interact, simulation_id, model.model_dump(), user_id(request))
    if not message:
        raise ResourceNotFound()
    return JSONResponse(message, status_code=201)


@router.get("/interactions/{simulation_id}/messages")
async def interaction_messages(request: Request, simulation_id: str):
    return {"messages": require_state(request, simulation_id)["interactions"]["messages"]}


@router.get("/interactions/{simulation_id}")
async def get_interaction(request: Request, simulation_id: str):
    return require_state(request, simulation_id)["interactions"] | {"simulation_id": simulation_id}
