from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request
from pydantic import ValidationError

from .models import EnvironmentInput, InteractionInput, ProjectInput

api = Blueprint("api", __name__, url_prefix="/api")


def service():
    return current_app.extensions["workflow"]


def repository():
    return current_app.extensions["repository"]


def require_state(simulation_id: str):
    state = repository().get(simulation_id)
    if not state:
        abort(404)
    return state


def start_stage(simulation_id: str, stage: str, payload: dict | None = None):
    if stage not in {"graph", "environment", "simulation", "report"}:
        abort(404)
    try:
        state = service().start(simulation_id, stage, payload)
    except ValueError as error:
        return jsonify(error={"code": "stage_locked", "message": str(error)}, message=str(error)), 409
    if not state:
        abort(404)
    return jsonify(state), 202


@api.get("/health")
def health():
    return jsonify(status="ok", service="rekakebijakan", engine="deterministic-demo")


@api.post("/projects")
def create_project():
    values = {
        "project_name": request.form.get("project_name") or request.form.get("name"),
        "institution": request.form.get("institution"),
        "objective": request.form.get("objective") or request.form.get("description"),
    }
    model = ProjectInput.model_validate(values)
    try:
        state = service().create_project(model.model_dump(), request.files.getlist("files"))
    except ValueError as error:
        return jsonify(error={"code": "unsupported_document", "message": str(error)}, message=str(error)), 422
    return jsonify(id=state["project"]["id"], project=state["project"], simulation_id=state["id"]), 201


@api.get("/projects")
def list_projects():
    return jsonify(projects=[state["project"] | {"simulation_id": state["id"]} for state in repository().list()])


@api.get("/projects/<project_id>")
def get_project(project_id: str):
    state = next((item for item in repository().list() if item["project"]["id"] == project_id), None)
    if not state:
        abort(404)
    return jsonify(state["project"] | {"simulation_id": state["id"], "documents": repository().documents(state["id"])})


@api.get("/simulations/<simulation_id>")
def get_simulation(simulation_id: str):
    return jsonify(require_state(simulation_id))


@api.post("/simulations/<simulation_id>/stages/<stage>/start")
def stage_alias(simulation_id: str, stage: str):
    payload = request.get_json(silent=True) or {}
    if stage == "environment":
        payload = EnvironmentInput.model_validate(payload).model_dump()
    return start_stage(simulation_id, stage, payload)


@api.post("/simulations/<simulation_id>/graph-build")
def graph_build(simulation_id: str):
    return start_stage(simulation_id, "graph")


@api.get("/simulations/<simulation_id>/graph")
def get_graph(simulation_id: str):
    return jsonify(require_state(simulation_id)["graph"])


@api.post("/simulations/<simulation_id>/environment/generate")
def generate_environment(simulation_id: str):
    payload = EnvironmentInput.model_validate(request.get_json(silent=True) or {}).model_dump()
    return start_stage(simulation_id, "environment", payload)


@api.get("/simulations/<simulation_id>/environment")
def get_environment(simulation_id: str):
    return jsonify(require_state(simulation_id)["environment"])


@api.patch("/simulations/<simulation_id>/environment")
def update_environment(simulation_id: str):
    config = EnvironmentInput.model_validate(request.get_json(silent=True) or {}).model_dump()
    def update(state):
        state["environment"]["config"] = config
        state["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    state = repository().mutate(simulation_id, update)
    if not state:
        abort(404)
    return jsonify(state)


@api.post("/simulations/<simulation_id>/runs")
def create_run(simulation_id: str):
    response = start_stage(simulation_id, "simulation", request.get_json(silent=True) or {})
    return response


@api.get("/runs/<simulation_id>")
def get_run(simulation_id: str):
    return jsonify(require_state(simulation_id)["simulation"] | {"id": simulation_id, "simulation_id": simulation_id})


@api.get("/runs/<simulation_id>/events")
def get_events(simulation_id: str):
    events = require_state(simulation_id)["simulation"].get("events", [])
    after = request.args.get("after", type=int, default=0)
    return jsonify(events=events[after:], event_count=len(events))


def control(simulation_id: str, action: str):
    try:
        state = service().control(simulation_id, action)
    except ValueError as error:
        return jsonify(error={"code": "invalid_control", "message": str(error)}, message=str(error)), 409
    if not state:
        abort(404)
    return jsonify(state)


@api.post("/simulations/<simulation_id>/pause")
@api.post("/runs/<simulation_id>/pause")
def pause(simulation_id: str):
    return control(simulation_id, "pause")


@api.post("/simulations/<simulation_id>/resume")
@api.post("/runs/<simulation_id>/resume")
def resume(simulation_id: str):
    return control(simulation_id, "resume")


@api.post("/simulations/<simulation_id>/cancel")
@api.post("/runs/<simulation_id>/cancel")
def cancel(simulation_id: str):
    return control(simulation_id, "cancel")


@api.post("/simulations/<simulation_id>/reports")
def create_report(simulation_id: str):
    return start_stage(simulation_id, "report", request.get_json(silent=True) or {})


@api.get("/reports")
def list_reports():
    reports = [{**state["report"], "simulation_id": state["id"]} for state in repository().list() if state["report"].get("sections")]
    return jsonify(reports=reports)


@api.get("/reports/<simulation_id>")
def get_report(simulation_id: str):
    return jsonify(require_state(simulation_id)["report"] | {"simulation_id": simulation_id})


@api.get("/reports/<simulation_id>/evidence")
def get_evidence(simulation_id: str):
    state = require_state(simulation_id)
    return jsonify(documents=repository().documents(simulation_id), events=state["simulation"].get("events", []), risks=state["report"].get("risks", []))


@api.post("/simulations/<simulation_id>/interactions")
@api.post("/reports/<simulation_id>/interactions")
def create_interaction(simulation_id: str):
    model = InteractionInput.model_validate(request.get_json(silent=True) or {})
    message = service().interact(simulation_id, model.model_dump())
    if not message:
        abort(404)
    return jsonify(message), 201


@api.post("/interactions/<simulation_id>/messages")
def interaction_message(simulation_id: str):
    return create_interaction(simulation_id)


@api.get("/interactions/<simulation_id>/messages")
def interaction_messages(simulation_id: str):
    return jsonify(messages=require_state(simulation_id)["interactions"]["messages"])


@api.get("/interactions/<simulation_id>")
def get_interaction(simulation_id: str):
    return jsonify(require_state(simulation_id)["interactions"] | {"simulation_id": simulation_id})
