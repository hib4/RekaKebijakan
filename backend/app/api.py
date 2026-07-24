from __future__ import annotations

from json import JSONDecodeError

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .errors import InvalidControl, ResourceNotFound, StageConflict, UnsupportedDocument
from .auth import current_user
from .models import EnvironmentInput, InteractionInput, ProjectInput

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
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
    return {"status": "ok", "service": "rekakebijakan", "engine": "deterministic-demo"}


@router.post("/projects")
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
    states = await run_in_threadpool(repository(request).list_for_user, user_id(request))
    return {"projects": [state["project"] | {"simulation_id": state["id"]} for state in states]}


@router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str):
    states = await run_in_threadpool(repository(request).list_for_user, user_id(request))
    state = next((item for item in states if item["project"]["id"] == project_id), None)
    if not state:
        raise ResourceNotFound()
    documents = await run_in_threadpool(repository(request).documents, state["id"])
    return state["project"] | {"simulation_id": state["id"], "documents": documents}


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
        state["environment"]["config"] = config
        state["updated_at"] = now()

    state = await run_in_threadpool(repository(request).mutate_for_user, simulation_id, user_id(request), update)
    if not state:
        raise ResourceNotFound()
    return state


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
    return {"events": events[after:], "event_count": len(events)}


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
    documents = await run_in_threadpool(repository(request).documents, simulation_id)
    return {"documents": documents, "events": state["simulation"].get("events", []), "risks": state["report"].get("risks", [])}


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
