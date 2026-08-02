import importlib.util
import json
import subprocess
import sys
import textwrap
import time
import types
from pathlib import Path

import pytest

from app import oasis_direct_bridge
from app.oasis_direct import DirectOasisEngine
from app.oasis_runtime import normalize_action
from app.provider_errors import ProviderTransportError


def test_bundled_oasis_locale_assets_load(monkeypatch):
    runtime = Path("/opt/rekakebijakan/oasis_engine_runtime")
    if not runtime.exists():
        runtime = Path(__file__).resolve().parents[1] / "oasis_engine_runtime"
    flask = types.ModuleType("flask")
    flask.request = types.SimpleNamespace(headers={})
    flask.has_request_context = lambda: False
    monkeypatch.setitem(sys.modules, "flask", flask)

    spec = importlib.util.spec_from_file_location("bundled_oasis_locale", runtime / "app" / "utils" / "locale.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.set_locale("en")
    assert module.get_language_instruction() == "Please respond in English."
    assert module.t("common.confirm") == "Confirm"

    module.set_locale("zh")
    assert module.get_locale() == "en"
    assert module.get_language_instruction() == "Please respond in English."
    assert module.t("common.confirm") == "Confirm"


def test_direct_engine_timeout_reports_last_sync_stage(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    engine = DirectOasisEngine(runtime, tmp_path / "data", timeout=12)

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd="oasis-direct", timeout=12,
            stderr="OASIS sync-graph: uploading ontology\n",
        )

    monkeypatch.setattr(subprocess, "run", timeout)

    with pytest.raises(ProviderTransportError, match="timed out after 12s.*uploading ontology") as captured:
        engine._call("sync-graph", {})

    assert captured.value.retryable is True


def test_direct_engine_suppresses_third_party_invalid_escape_warnings(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("PYTHONWARNINGS", "error")
    engine = DirectOasisEngine(runtime, tmp_path / "data")

    assert engine._environment()["PYTHONWARNINGS"] == "ignore:invalid escape sequence:SyntaxWarning"


def test_direct_engine_forwards_success_diagnostics(monkeypatch, tmp_path: Path, capsys):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    engine = DirectOasisEngine(runtime, tmp_path / "data")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"success": true, "data": {}}',
            stderr="LLM request completed model=test duration_ms=100\n",
        ),
    )

    engine._call("report", {})

    assert "LLM request completed model=test duration_ms=100" in capsys.readouterr().err


def test_prepare_uses_longer_bounded_timeout(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    engine = DirectOasisEngine(runtime, tmp_path / "data", timeout=120)
    captured = {}
    monkeypatch.setenv("OASIS_PREPARE_TIMEOUT_SECONDS", "900")

    def call(operation, payload, timeout=None):
        captured.update(operation=operation, payload=payload, timeout=timeout)
        return {}

    monkeypatch.setattr(engine, "_call", call)
    engine.prepare_environment(
        {"zep_graph_id": "graph-1"},
        {"id": "sim-1", "project": {"id": "project-1", "objective": "Objective"}},
        {"_chunks": [{"text": "Evidence"}]},
    )

    assert captured["operation"] == "prepare"
    assert captured["timeout"] == 900


def test_ingest_actions_uses_longer_bounded_timeout(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    engine = DirectOasisEngine(runtime, tmp_path / "data", timeout=120)
    captured = {}

    def call(operation, payload, timeout=None):
        captured.update(operation=operation, payload=payload, timeout=timeout)
        return {}

    monkeypatch.setattr(engine, "_call", call)
    monkeypatch.setenv("OASIS_INGESTION_TIMEOUT_SECONDS", "900")
    actions = [{"platform": "twitter", "action_type": "CREATE_POST"}]
    engine.ingest_actions("sim-1", "graph-1", "run-1", actions)

    assert captured == {
        "operation": "ingest-actions",
        "payload": {
            "simulation_id": "sim-1", "graph_id": "graph-1", "run_id": "run-1",
            "actions": actions, "timeout_seconds": 900,
        },
        "timeout": 930,
    }


def test_report_uses_configured_bounded_timeout(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    engine = DirectOasisEngine(runtime, tmp_path / "data", timeout=120)
    captured = {}

    def call(operation, payload, timeout=None):
        captured.update(operation=operation, payload=payload, timeout=timeout)
        return {}

    monkeypatch.setenv("OASIS_REPORT_TIMEOUT_SECONDS", "900")
    monkeypatch.setattr(engine, "_call", call)
    engine.generate_report("sim-1", "graph-1", "Objective")

    assert captured == {
        "operation": "report",
        "payload": {"simulation_id": "sim-1", "graph_id": "graph-1", "simulation_requirement": "Objective"},
        "timeout": 900,
    }


def test_start_simulation_resumes_alive_process(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    data = tmp_path / "data"
    simulation = data / "sim-1"
    simulation.mkdir(parents=True)
    (simulation / "simulation_config.json").write_text("{}")
    existing = {"pid": 123, "runner_status": "running", "cursors": {"twitter": 1, "reddit": 2}}
    (simulation / "direct_runtime.json").write_text(json.dumps(existing))
    engine = DirectOasisEngine(runtime, data)
    monkeypatch.setattr(engine, "_pid_alive", lambda _pid: True)
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("started a second process"))

    resumed = engine.start_simulation({"external_simulation_id": "sim-1"}, {"max_rounds": 3})

    assert resumed == existing


def test_start_simulation_replaces_failed_alive_process(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    (runtime / "scripts").mkdir(parents=True)
    data = tmp_path / "data"
    simulation = data / "sim-1"
    simulation.mkdir(parents=True)
    (simulation / "simulation_config.json").write_text("{}")
    (simulation / "direct_runtime.json").write_text(json.dumps({"pid": 123, "runner_status": "failed"}))
    engine = DirectOasisEngine(runtime, data)
    alive = iter([True, False])
    monkeypatch.setattr(engine, "_pid_alive", lambda _pid: next(alive, False))
    monkeypatch.setattr(engine, "stop_simulation", lambda _simulation_id: {"runner_status": "stopped"})

    class Process:
        pid = 456

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: Process())

    started = engine.start_simulation({"external_simulation_id": "sim-1"}, {"rounds": 10})

    assert started["pid"] == 456
    assert started["runner_status"] == "running"
    assert started["max_rounds"] == 10


def test_hard_step_timeout_exits_when_cancellation_hangs(tmp_path: Path):
    runtime = Path("/opt/rekakebijakan/oasis_engine_runtime")
    if not runtime.exists():
        runtime = Path(__file__).resolve().parents[1] / "oasis_engine_runtime"
    scripts = runtime / "scripts"
    program = tmp_path / "hard_timeout_reproduction.py"
    program.write_text(textwrap.dedent(f"""
        import asyncio
        import os
        import sys
        sys.path.insert(0, {str(scripts)!r})
        from hard_timeout import HardOperationTimeout, run_with_hard_timeout

        async def stuck():
            while True:
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    pass

        async def main():
            await run_with_hard_timeout(
                stuck(), timeout_seconds=0.25, cleanup_grace_seconds=0.25,
                platform="twitter", phase="step", round_num=4,
            )

        try:
            asyncio.run(main())
        except HardOperationTimeout as error:
            print(error, file=sys.stderr, flush=True)
            os._exit(2)
    """), encoding="utf-8")

    started = time.monotonic()
    result = subprocess.run([sys.executable, str(program)], text=True, capture_output=True, timeout=2)

    assert time.monotonic() - started < 1.5
    assert result.returncode == 2
    assert "OASIS twitter step round 4 timed out after 0.25s" in result.stderr
    assert "cancellation grace 0.25s expired" in result.stderr


def test_sync_graph_reuses_existing_ontology(monkeypatch):
    calls = {}

    class Info:
        def to_dict(self):
            return {"node_count": 1}

    class Submission:
        batch_id = "batch-1"

    class Builder:
        def create_graph(self, name):
            calls["name"] = name
            return "graph-1"

        def set_ontology(self, graph_id, ontology):
            calls["ontology"] = (graph_id, ontology)

        def add_text_batches(self, graph_id, texts):
            calls["texts"] = (graph_id, texts)
            return Submission()

        def _wait_for_batch(self, submission):
            assert submission.batch_id == "batch-1"
            return ["episode-1"]

        def _get_graph_info(self, graph_id):
            assert graph_id == "graph-1"
            return Info()

    services = types.ModuleType("app.services")
    graph_builder = types.ModuleType("app.services.graph_builder")
    graph_builder.GraphBuilderService = Builder
    monkeypatch.setitem(sys.modules, "app.services", services)
    monkeypatch.setitem(sys.modules, "app.services.graph_builder", graph_builder)
    ontology = {"entity_types": [{"name": "Stakeholder"}]}

    result = oasis_direct_bridge.sync_graph({
        "simulation_id": "sim-1",
        "project_name": "Project",
        "simulation_requirement": "unused",
        "ontology": ontology,
        "chunks": [{"text": "Evidence"}, {"text": ""}],
    })

    assert calls["ontology"] == ("graph-1", ontology)
    assert calls["texts"] == ("graph-1", ["Evidence"])
    assert result["graph_id"] == "graph-1"
    assert result["episode_uuids"] == ["episode-1"]


def test_ingest_actions_bridge_matches_bundled_updater_contract(monkeypatch, tmp_path: Path):
    calls = {}

    class Updater:
        def __init__(self, graph_id, api_key=None, simulation_id=None):
            calls.update(graph_id=graph_id, simulation_id=simulation_id, api_key=api_key)

        def start(self):
            calls["started"] = True

        def add_activity_from_dict(self, item, platform):
            calls.setdefault("actions", []).append((item, platform))

        def stop(self, timeout_seconds=None):
            calls["timeout_seconds"] = timeout_seconds

        def get_stats(self):
            return {"total": len(calls.get("actions", []))}

    services = types.ModuleType("app.services")
    updater_module = types.ModuleType("app.services.zep_graph_memory_updater")
    updater_module.ZepGraphMemoryUpdater = Updater
    monkeypatch.setitem(sys.modules, "app.services", services)
    monkeypatch.setitem(sys.modules, "app.services.zep_graph_memory_updater", updater_module)
    monkeypatch.setenv("OASIS_DATA_DIR", str(tmp_path))
    payload = {
        "simulation_id": "sim-1", "run_id": "run-1", "graph_id": "graph-1",
        "actions": [{"platform": "twitter", "action_type": "CREATE_POST"}],
        "timeout_seconds": 900,
    }

    result = oasis_direct_bridge.ingest_actions(payload)

    assert result == {"total": 1}
    assert calls["graph_id"] == "graph-1"
    assert calls["simulation_id"] == "sim-1"
    assert calls["timeout_seconds"] == 900


def test_direct_engine_reads_incremental_platform_actions(tmp_path: Path):
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    data = tmp_path / "data"
    simulation = data / "sim-1"
    (simulation / "twitter").mkdir(parents=True)
    (simulation / "reddit").mkdir(parents=True)
    (simulation / "simulation_config.json").write_text(json.dumps({
        "time_config": {"total_simulation_hours": 1, "minutes_per_round": 30}
    }))
    (simulation / "direct_runtime.json").write_text(json.dumps({"pid": None, "max_rounds": 2}))
    twitter = simulation / "twitter" / "actions.jsonl"
    twitter.write_text("\n".join(json.dumps(item) for item in [
        {"event_type": "round_start", "round": 0},
        {"round": 0, "agent_id": 1, "agent_name": "A", "action_type": "CREATE_POST", "action_args": {"content": "awal"}},
        {"event_type": "simulation_end", "round": 2},
    ]) + "\n")
    (simulation / "reddit" / "actions.jsonl").write_text(json.dumps({"event_type": "simulation_end", "round": 2}) + "\n")

    engine = DirectOasisEngine(source, data)
    first = engine.simulation_snapshot("sim-1")
    second = engine.simulation_snapshot("sim-1", first["next_cursor"])

    assert first["status"]["runner_status"] == "completed"
    assert first["actions"][0]["round"] == 0
    assert second["actions"] == []


def test_dead_child_reports_step_timeout_before_stale_timeout(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    simulation = tmp_path / "data" / "sim-1"
    (simulation / "twitter").mkdir(parents=True)
    (simulation / "reddit").mkdir(parents=True)
    (simulation / "simulation_config.json").write_text("{}", encoding="utf-8")
    (simulation / "direct_runtime.json").write_text(json.dumps({
        "pid": 123, "runner_status": "running", "started_at": time.time() - 200,
        "last_progress_at": time.time() - 200, "stale_timeout_seconds": 150,
        "max_run_seconds": 3600, "max_rounds": 10,
    }), encoding="utf-8")
    (simulation / "simulation.log").write_text(
        "Fatal timeout: OASIS reddit step round 4 timed out after 120s; "
        "cancellation grace 5s expired\n", encoding="utf-8",
    )
    engine = DirectOasisEngine(runtime, tmp_path / "data")
    monkeypatch.setattr(engine, "_pid_alive", lambda _pid: False)

    status = engine.simulation_snapshot("sim-1")["status"]

    assert status["runner_status"] == "failed"
    assert "reddit step round 4 timed out after 120s" in status["error"]
    assert "made no round progress" not in status["error"]


def test_oasis_projection_preserves_initial_round():
    event = normalize_action(
        {"platform": "twitter", "round_num": 0, "agent_id": 1, "agent_name": "A", "action_type": "CREATE_POST",
         "action_args": {"content": "awal"}, "timestamp": "2026-01-01T00:00:00+00:00"},
        1, [], 1, 1,
    )
    assert event["round"] == 0


def test_report_context_fetches_graph_once():
    runtime = Path(__file__).resolve().parents[1] / "oasis_engine_runtime"
    runtime_python = runtime / ".venv" / "bin" / "python"
    if not runtime_python.exists():
        pytest.skip("bundled OASIS environment is not installed")
    script = """
import json
from types import SimpleNamespace
from app.services.zep_tools import ZepToolsService

service = object.__new__(ZepToolsService)
calls = {"nodes": 0, "edges": 0}
service.search_graph = lambda **_kwargs: SimpleNamespace(facts=["Operator requires compensation"])
def nodes(_graph_id):
    calls["nodes"] += 1
    return [SimpleNamespace(name="Operator", labels=["Entity", "Stakeholder"], summary="Transport operator")]
def edges(_graph_id):
    calls["edges"] += 1
    return [SimpleNamespace(name="AFFECTS")]
service.get_all_nodes = nodes
service.get_all_edges = edges
context = service.get_simulation_context("graph-1", "Assess transport policy")
print(json.dumps({"calls": calls, "context": context}))
"""

    result = subprocess.run(
        [str(runtime_python), "-c", script], cwd=runtime, text=True, capture_output=True, check=True,
    )
    value = json.loads(result.stdout)

    assert value["calls"] == {"nodes": 1, "edges": 1}
    assert value["context"]["graph_statistics"]["entity_types"] == {"Stakeholder": 1}
    assert value["context"]["graph_statistics"]["relation_types"] == {"AFFECTS": 1}
    assert value["context"]["entities"] == [
        {"name": "Operator", "type": "Stakeholder", "summary": "Transport operator"}
    ]


def test_namespaced_gpt5_uses_completion_token_parameter():
    runtime = Path("/opt/rekakebijakan/oasis_engine_runtime")
    if not runtime.exists():
        runtime = Path(__file__).resolve().parents[1] / "oasis_engine_runtime"
    compat_path = runtime / "app" / "utils" / "openai_chat_compat.py"
    spec = importlib.util.spec_from_file_location("oasis_openai_chat_compat", compat_path)
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return object()

    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Completions()))
    compat.create_chat_completion(
        client,
        model="jtv/gpt-5.4-mini",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.3,
        max_tokens=512,
    )

    assert compat.is_gpt5_family("jtv/gpt-5.4-mini") is True
    assert captured["max_completion_tokens"] == 512
    assert "max_tokens" not in captured
    assert "temperature" not in captured
