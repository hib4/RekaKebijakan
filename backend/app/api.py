from __future__ import annotations

from json import JSONDecodeError

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .errors import InvalidControl, ResourceNotFound, RevisionConflict, StageConflict, UnsupportedDocument
from .auth import current_user
from .models import (
    EnvironmentInput,
    GraphFeedbackInput,
    InteractionInput,
    InterviewInput,
    PersonaOverrideDeleteInput,
    PersonaOverrideInput,
    ProjectInput,
    ProjectUpdateInput,
    ScenarioInput,
    ScenarioUpdateInput,
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


@router.post("/projects")
@v1_router.post("/projects", include_in_schema=False)
async def create_project(request: Request):
    form = await request.form()
    values = {
        "project_name": form.get("project_name") or form.get("name"),
        "institution": form.get("institution"),
        "objective": form.get("objective") or form.get("description"),
    }
    model = ProjectInput.model_validate(values)
    files = [item for item in form.getlist("files") if hasattr(item, "file")]
    try:
        state = await run_in_threadpool(service(request).create_project, model.model_dump(), files, user_id(request))
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
        "scenario_count": row.get("scenario_count", 0),
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


@v1_router.get("/projects/{project_id}/scenarios/{scenario_id}/personas")
async def effective_personas_v1(request: Request, project_id: str, scenario_id: str):
    items = await run_in_threadpool(
        repository(request).effective_personas, project_id, scenario_id, user_id(request)
    )
    if items is None:
        raise ResourceNotFound()
    return {"items": items}


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


@v1_router.delete("/projects/{project_id}/scenarios/{scenario_id}/persona-overrides/{persona_id}")
async def delete_persona_override_v1(request: Request, project_id: str, scenario_id: str, persona_id: str):
    model = PersonaOverrideDeleteInput.model_validate(await silent_json(request))
    try:
        row = await run_in_threadpool(
            repository(request).put_persona_override,
            project_id,
            scenario_id,
            persona_id,
            user_id(request),
            model.expected_version,
            model.base_environment_revision,
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
async def run_scenario_v1(request: Request, project_id: str, scenario_id: str):
    try:
        simulation_id = await run_in_threadpool(
            repository(request).apply_scenario, project_id, scenario_id, user_id(request)
        )
    except ValueError as error:
        raise StageConflict(str(error)) from error
    if not simulation_id:
        raise ResourceNotFound()
    return await start_stage(request, simulation_id, "simulation")


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


@router.post("/simulations/{simulation_id}/stages/{stage}/start")
@router.post("/simulations/{simulation_id}/{stage}/start", include_in_schema=False)
@router.post("/simulations/{simulation_id}/start/{stage}", include_in_schema=False)
async def stage_alias(request: Request, simulation_id: str, stage: str):
    payload = await silent_json(request)
    if stage == "environment":
        payload = EnvironmentInput.model_validate(payload).model_dump()
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
    config = EnvironmentInput.model_validate(await silent_json(request)).model_dump()

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
    return await start_stage(request, simulation_id, "simulation", await silent_json(request))


@router.get("/runs/{simulation_id}")
async def get_run(request: Request, simulation_id: str):
    return require_state(request, simulation_id)["simulation"] | {"id": simulation_id, "simulation_id": simulation_id}


@router.get("/runs/{simulation_id}/events")
async def get_events(request: Request, simulation_id: str):
    events = require_state(request, simulation_id)["simulation"].get("events", [])
    try:
        after = int(request.query_params.get("after", "0"))
    except ValueError:
        after = 0
    selected = [event for index, event in enumerate(events) if event.get("sequence", index + 1) > after]
    return {"events": selected, "event_count": len(events)}


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


@router.get("/simulations/{simulation_id}/interviews")
async def list_interviews(request: Request, simulation_id: str):
    return require_state(request, simulation_id).get("interviews", {"items": []})


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
    return require_state(request, simulation_id).get("graph_feedback", {"items": []})


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
