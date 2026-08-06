from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


def configure_runtime() -> Path:
    runtime = Path(os.environ["REKAKEBIJAKAN_OASIS_RUNTIME_PATH"]).resolve()
    sys.path.insert(0, str(runtime))
    return runtime


def sync_graph(payload: dict, emit=None) -> dict:
    from app.services.graph_builder import GraphBuilderService

    texts = [item["text"] for item in payload["chunks"] if item.get("text")]
    ontology = dict(payload["ontology"])
    if not ontology.get("edge_types") and ontology.get("relation_types"):
        ontology["edge_types"] = [{
            "name": relation["name"],
            "description": relation.get("description") or f"Relasi {relation['name']}",
            "source_targets": [
                {"source": source, "target": target}
                for source in relation.get("source_types", ["Entity"])
                for target in relation.get("target_types", ["Entity"])
            ],
            "attributes": relation.get("attributes", []),
        } for relation in ontology["relation_types"]]
    builder = GraphBuilderService()
    graph_id = payload.get("graph_id")
    build_id = payload.get("build_id") or graph_id
    known_nodes: dict[str, str] = {}
    known_edges: dict[str, str] = {}
    last_scan_at = 0.0
    last_scan_progress = -1.0

    def milestone(name: str, progress: float, message: str, **details) -> None:
        if emit:
            emit({
                "kind": "milestone", "milestone": name, "progress": progress,
                "message": message, "graph_id": graph_id, "build_id": build_id, **details,
            })

    def normalized_id(item: dict) -> str | None:
        value = item.get("id") or item.get("uuid")
        return str(value) if value else None

    def emit_topology(*, force: bool = False, progress: float = 0.0) -> dict | None:
        nonlocal last_scan_at, last_scan_progress
        if not emit or not graph_id:
            return None
        now = time.monotonic()
        if not force and now - last_scan_at < 2 and progress - last_scan_progress < 0.05:
            return None
        try:
            graph = builder.get_graph_data(graph_id)
        except Exception as error:
            milestone("topology-pending", progress, "Topologi Zep belum tersedia", detail=str(error))
            return None
        last_scan_at = now
        last_scan_progress = progress
        for kind, items, known in (
            ("node", graph.get("nodes", []), known_nodes),
            ("edge", graph.get("edges", []), known_edges),
        ):
            for item in items:
                item_id = normalized_id(item)
                if not item_id:
                    continue
                digest = hashlib.sha256(
                    json.dumps(item, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
                ).hexdigest()
                if known.get(item_id) == digest:
                    continue
                known[item_id] = digest
                emit({
                    "kind": kind, "graph_id": graph_id, "build_id": build_id,
                    "progress": progress, kind: item,
                    "node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", [])),
                })
        return graph

    if payload.get("graph_exists") and graph_id:
        milestone("graph-resumed", 0.04, "Melanjutkan graf runtime yang tersimpan")
    else:
        print("OASIS sync-graph: creating Zep graph", file=sys.stderr, flush=True)
        milestone("graph-creating", 0.02, "Membuat graf runtime Zep")
        if emit:
            graph_id = builder.create_graph(
                payload["project_name"], graph_id=graph_id,
                graph_id_callback=lambda value: milestone("graph-reserved", 0.03, "ID graf runtime disiapkan", graph_id=value),
            )
        else:
            graph_id = (
                builder.create_graph(payload["project_name"], graph_id=graph_id)
                if graph_id else builder.create_graph(payload["project_name"])
            )
        milestone("graph-created", 0.08, "Graf runtime Zep tersedia")
    print("OASIS sync-graph: uploading ontology", file=sys.stderr, flush=True)
    builder.set_ontology(graph_id, ontology)
    milestone("ontology-installed", 0.15, "Ontology dipasang pada graf runtime")
    print(f"OASIS sync-graph: submitting {len(texts)} evidence chunks", file=sys.stderr, flush=True)
    if payload.get("batch_id"):
        submission = SimpleNamespace(
            batch_id=payload["batch_id"], operation_id=payload.get("operation_id") or "resumed",
            episode_uuids=[], item_count=len(texts),
        )
        milestone("batch-resumed", 0.35, "Melanjutkan pemrosesan batch Zep", batch_id=submission.batch_id)
    elif emit:
        submission = builder.add_text_batches(
            graph_id, texts,
            progress_callback=lambda message, progress: milestone(
                "evidence-submitting", 0.15 + progress * 0.2, message,
            ),
            batch_created_callback=lambda batch_id, operation_id: milestone(
                "batch-created" if batch_id else "batch-reserved", 0.18,
                "Batch Zep disiapkan" if not batch_id else "Batch Zep dikonfirmasi",
                batch_id=batch_id, operation_id=operation_id,
            ),
        )
    else:
        submission = builder.add_text_batches(graph_id, texts)
    print(f"OASIS sync-graph: processing Zep batch {submission.batch_id}", file=sys.stderr, flush=True)
    if emit:
        def processing(message, progress):
            milestone("batch-processing", 0.35 + progress * 0.5, message, batch_id=submission.batch_id)
            emit_topology(progress=progress)
        episodes = builder._wait_for_batch(submission, processing)
    else:
        episodes = builder._wait_for_batch(submission)
    print("OASIS sync-graph: retrieving graph summary", file=sys.stderr, flush=True)
    milestone("topology-reconciling", 0.9, "Menyelaraskan topologi graf runtime")
    final_graph = emit_topology(force=True, progress=1.0)
    info = builder._get_graph_info(graph_id)
    if emit and final_graph is not None:
        emit({
            "kind": "snapshot", "graph_id": graph_id, "build_id": build_id,
            "progress": 1.0, "graph": final_graph,
        })
    milestone("completed", 1.0, "Graf runtime selesai dibuat")
    return {"project_id": payload["simulation_id"], "graph_id": graph_id, "graph_info": info.to_dict(),
            "episode_uuids": episodes, "ontology": ontology}


def prepare(payload: dict) -> dict:
    from app.services.simulation_manager import SimulationManager, SimulationState

    data_dir = Path(os.environ["OASIS_DATA_DIR"])
    SimulationManager.SIMULATION_DATA_DIR = str(data_dir)
    manager = SimulationManager()
    state = SimulationState(
        simulation_id=payload["simulation_id"], project_id=payload["project_id"], graph_id=payload["graph_id"]
    )
    manager._save_simulation_state(state)
    config = payload.get("config") or {}
    prepared = manager.prepare_simulation(
        payload["simulation_id"], payload["simulation_requirement"], payload.get("document_text", ""),
        defined_entity_types=config.get("entity_types"),
        use_llm_for_profiles=config.get("use_llm_for_profiles", True),
        use_llm_for_config=config.get("use_llm_for_config", False),
        parallel_profile_count=config.get("parallel_profile_count", 5),
        max_profile_count=config.get("max_profile_count"),
    )
    profiles = manager.get_profiles(payload["simulation_id"], "reddit")
    return {"profiles": profiles, "config": manager.get_simulation_config(payload["simulation_id"]), "state": prepared.to_dict()}


def runtime_graph(payload: dict) -> dict:
    from app.services.graph_builder import GraphBuilderService
    return GraphBuilderService().get_graph_data(payload["graph_id"])


def table_rows(database: Path, table: str) -> list[dict]:
    if not database.exists():
        return []
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')] if exists else []


def artifacts(payload: dict) -> dict:
    simulation_dir = Path(os.environ["OASIS_DATA_DIR"]) / payload["simulation_id"]
    posts = []
    comments = []
    for platform in ("twitter", "reddit"):
        database = simulation_dir / f"{platform}_simulation.db"
        posts.extend(dict(item) | {"platform": platform} for item in table_rows(database, "post"))
        comments.extend(dict(item) | {"platform": platform} for item in table_rows(database, "comment"))
    actions = []
    for platform in ("twitter", "reddit"):
        path = simulation_dir / platform / "actions.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    "agent_id" in item
                    and "event_type" not in item
                    and not item.get("synthetic")
                ):
                    actions.append(item | {"platform": item.get("platform", platform)})
    timeline = {}
    stats = {}
    for action in actions:
        round_number = str(action.get("round", 0))
        timeline.setdefault(round_number, {"round": int(round_number), "actions": 0, "platforms": {}})
        timeline[round_number]["actions"] += 1
        platform = action["platform"]
        timeline[round_number]["platforms"][platform] = timeline[round_number]["platforms"].get(platform, 0) + 1
        agent = str(action.get("agent_id"))
        stats.setdefault(agent, {"agent_id": action.get("agent_id"), "agent_name": action.get("agent_name"), "actions": 0, "platforms": {}})
        stats[agent]["actions"] += 1
        stats[agent]["platforms"][platform] = stats[agent]["platforms"].get(platform, 0) + 1
    return {"posts": posts, "comments": comments, "timeline": list(timeline.values()), "stats": list(stats.values())}


def configure_reports() -> None:
    from app.config import Config
    from app.services.report_agent import ReportManager
    from app.services.simulation_manager import SimulationManager
    from app.services.simulation_runner import SimulationRunner

    root = Path(os.environ["OASIS_DATA_DIR"]).parent / "reports"
    root.mkdir(parents=True, exist_ok=True)
    Config.UPLOAD_FOLDER = str(root.parent)
    ReportManager.REPORTS_DIR = str(root)
    SimulationManager.SIMULATION_DATA_DIR = os.environ["OASIS_DATA_DIR"]
    SimulationRunner.RUN_STATE_DIR = os.environ["OASIS_DATA_DIR"]


def report(payload: dict) -> dict:
    from app.services.report_agent import ReportAgent, ReportManager

    configure_reports()
    agent = ReportAgent(
        graph_id=payload["graph_id"], simulation_id=payload["simulation_id"],
        simulation_requirement=payload["simulation_requirement"],
    )
    generated = agent.generate_report(report_id=payload.get("report_id"))
    ReportManager.save_report(generated)
    if generated.status.value != "completed":
        raise RuntimeError(generated.error or "OASIS report generation failed")
    value = generated.to_dict()
    value["agent_log"] = ReportManager.get_agent_log_stream(generated.report_id)
    value["console_log"] = ReportManager.get_console_log_stream(generated.report_id)
    value["artifact_dir"] = str(Path(ReportManager.REPORTS_DIR) / generated.report_id)
    return value


def report_chat(payload: dict) -> dict:
    from app.services.report_agent import ReportAgent

    configure_reports()
    return ReportAgent(
        graph_id=payload["graph_id"], simulation_id=payload["simulation_id"],
        simulation_requirement=payload["simulation_requirement"],
    ).chat(payload["message"], payload.get("history") or [])


def ingest_actions(payload: dict) -> dict:
    from app.services.zep_graph_memory_updater import ZepGraphMemoryUpdater

    simulation_dir = Path(os.environ["OASIS_DATA_DIR"]) / payload["simulation_id"]
    run_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload["run_id"]))
    checkpoint_path = simulation_dir / "ingestion" / f"{run_id}.json"
    checkpoint = read_json(checkpoint_path)
    if checkpoint.get("graph_id") not in {None, payload["graph_id"]}:
        raise RuntimeError("Zep ingestion checkpoint belongs to a different graph")
    if checkpoint.get("status") == "completed":
        return checkpoint.get("stats") or {}
    checkpoint = {
        "simulation_id": payload["simulation_id"],
        "run_id": payload["run_id"],
        "graph_id": payload["graph_id"],
        "status": "running",
    }

    write_json(checkpoint_path, checkpoint)
    updater = ZepGraphMemoryUpdater(
        payload["graph_id"],
        simulation_id=payload["simulation_id"],
    )
    updater.start()
    for item in payload.get("actions") or []:
        updater.add_activity_from_dict(item, str(item.get("platform") or "oasis"))
    updater.stop(timeout_seconds=float(payload["timeout_seconds"]))
    stats = updater.get_stats()
    checkpoint.update(status="completed", stats=stats)
    write_json(checkpoint_path, checkpoint)
    return stats


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


OPERATIONS = {
    "sync-graph": sync_graph, "prepare": prepare, "runtime-graph": runtime_graph,
    "artifacts": artifacts, "report": report, "report-chat": report_chat,
    "ingest-actions": ingest_actions,
}


def main() -> None:
    configure_runtime()
    payload = json.load(sys.stdin)
    from app.utils.locale import set_locale
    set_locale(payload.get("language", "id"))
    try:
        if sys.argv[1] == "sync-graph-stream":
            protocol_stdout = sys.stdout

            def emit(message: dict) -> None:
                protocol_stdout.write(json.dumps(message, ensure_ascii=False, default=str) + "\n")
                protocol_stdout.flush()

            with redirect_stdout(sys.stderr):
                data = sync_graph(payload, emit=emit)
            emit({"kind": "result", "data": data})
            return
        # Engine services occasionally print progress. Keep stdout as a
        # strict JSON protocol and route incidental output to stderr.
        with redirect_stdout(sys.stderr):
            data = OPERATIONS[sys.argv[1]](payload)
        print(json.dumps({"success": True, "data": data}, ensure_ascii=False, default=str))
    except Exception as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
