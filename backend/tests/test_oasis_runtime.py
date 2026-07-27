from pathlib import Path

import pytest

from app.oasis_runtime import OasisRuntimeClient, normalize_action, normalize_environment, source_identity
from app.service import WorkflowService


def graph():
    citation = {
        "source_type": "document_chunk", "source_id": "chunk-1", "chunk_id": "chunk-1",
        "document_id": "doc-1", "locator": {"ordinal": 0}, "quote": "Bukti kebijakan",
    }
    return {
        "revision": 2,
        "nodes": [{"id": "stakeholder-1", "label": "Rina", "type": "Stakeholder", "citations": [citation]}],
        "edges": [],
    }


def test_oasis_environment_preserves_local_evidence():
    prepared = {
        "profiles": [{
            "user_id": 7, "name": "Rina", "username": "rina", "bio": "Warga",
            "persona": "Warga yang aktif", "profession": "Warga", "interested_topics": ["Akses"],
            "source_entity_type": "Stakeholder",
        }],
        "config": {
            "time_config": {"total_simulation_hours": 72, "minutes_per_round": 60},
            "agent_configs": [{"agent_id": 7, "stance": "critical", "influence_weight": 0.8}],
            "generation_reasoning": "Konfigurasi OASIS",
        },
    }

    environment = normalize_environment("sim-1", graph(), prepared, {"max_rounds": 40})

    assert environment["persona_count"] == 1
    assert environment["config"]["rounds"] == 40
    assert environment["config"]["platforms"] == ["twitter", "reddit"]
    assert environment["personas"][0]["id"] == "oasis-7"
    assert environment["personas"][0]["source_node_ids"] == ["stakeholder-1"]
    assert environment["personas"][0]["citations"][0]["source_id"] == "chunk-1"


def test_oasis_action_normalization_is_stable_and_cited():
    environment = normalize_environment("sim-1", graph(), {
        "profiles": [{
            "user_id": 7, "name": "Rina", "bio": "Warga", "persona": "Warga aktif",
            "profession": "Warga", "interested_topics": ["Akses"], "source_entity_type": "Stakeholder",
        }],
        "config": {"agent_configs": [{"agent_id": 7}], "time_config": {}},
    }, {})
    action = {
        "round_num": 3, "timestamp": "2026-07-27T10:00:00+00:00", "platform": "twitter",
        "agent_id": 7, "agent_name": "Rina", "action_type": "CREATE_POST",
        "action_args": {"content": "Akses perlu diperbaiki"}, "success": True,
    }

    event = normalize_action(action, 1, environment["personas"], 2, 1)

    assert event["channel"] == "twitter"
    assert event["event_type"] == "CREATE_POST"
    assert event["statement"] == "Akses perlu diperbaiki"
    assert event["citations"][0]["source_id"] == "chunk-1"
    assert source_identity(action, 1) == source_identity(action, 1)


def test_runtime_client_enforces_indonesian_locale():
    client = OasisRuntimeClient("http://runtime", "token")
    try:
        assert client.client.headers["Accept-Language"] == "id-ID,id;q=0.9"
    finally:
        client.close()


def test_source_identity_prefers_runtime_source_id():
    action = {"source_id": "run/twitter:42", "timestamp": "2026-01-01T00:00:00Z"}
    assert source_identity(action, 1) == "run/twitter:42"
    assert source_identity(action, 99) == "run/twitter:42"


class RuntimeRepository:
    def __init__(self):
        self.mapping = {
            "external_project_id": "project-remote",
            "external_simulation_id": "simulation-remote",
            "zep_graph_id": "graph-remote",
            "graph_revision": 2,
            "status": "ready",
            "metadata": {"prepared": True},
        }
        self.actions = []

    def get_oasis_mapping(self, _simulation_id):
        return self.mapping

    def clear_oasis_actions(self, _simulation_id):
        self.actions.clear()

    def upsert_oasis_mapping(self, _simulation_id, _project_id, values):
        self.mapping = self.mapping | values
        return self.mapping

    def job_control_state(self, _job_id, _execution_token):
        return "running"

    def summarize_oasis_actions(self, _simulation_id):
        return {"total_actions": len(self.actions)}

    def append_oasis_actions(self, _simulation_id, actions):
        self.actions.extend(actions)
        return len(actions)

    def list_oasis_actions(self, _simulation_id, limit=5000):
        return [{"event": action["event"]} for action in self.actions[:limit]]

    def mutate(self, _simulation_id, callback):
        callback({
            "stages": {"simulation": {}},
            "simulation": {},
            "graph": {},
            "environment": {},
            "report": {},
            "interaction": {},
            "logs": [],
        })


def runtime_service(repository, runtime, tmp_path):
    return WorkflowService(repository, object(), Path(tmp_path), 0, oasis_runtime=runtime)


def runtime_state():
    return {
        "project": {"id": "project-local"},
        "graph": {"revision": 2},
        "environment": {"personas": [], "config": {"version": 1, "max_rounds": 2}},
    }


def test_host_runtime_uses_cursor_and_runtime_source_sequence(monkeypatch, tmp_path):
    repository = RuntimeRepository()

    class Runtime:
        def __init__(self):
            self.cursors = []

        def start_simulation(self, _mapping, _config):
            return {"runner_status": "running"}

        def simulation_snapshot(self, _simulation_id, cursor):
            self.cursors.append(cursor)
            if cursor is None:
                return {
                    "status": {"runner_status": "running", "current_round": 1, "total_rounds": 2},
                    "actions": [{
                        "source_id": "simulation-remote/twitter:8", "source_sequence": 8,
                        "platform": "twitter", "round_num": 1, "action_type": "CREATE_POST",
                        "action_args": {"content": "Pendapat warga"},
                    }],
                    "next_cursor": "cursor-1",
                }
            return {
                "status": {"runner_status": "completed", "current_round": 2, "total_rounds": 2},
                "actions": [],
                "next_cursor": "cursor-2",
            }

    runtime = Runtime()
    monkeypatch.setattr("app.service.time.sleep", lambda _seconds: None)

    result = runtime_service(repository, runtime, tmp_path)._run_oasis_simulation(
        {"id": "job-1", "simulation_id": "simulation-local", "execution_token": "token"},
        runtime_state(),
        {},
    )

    assert runtime.cursors == [None, "cursor-1"]
    assert repository.actions[0]["external_sequence"] == 8
    assert repository.actions[0]["source_identity"] == "simulation-remote/twitter:8"
    assert result["event_count"] == 1
    assert repository.mapping["status"] == "completed"


def test_host_runtime_marks_mapping_failed_when_start_fails(tmp_path):
    repository = RuntimeRepository()

    class Runtime:
        def start_simulation(self, _mapping, _config):
            raise RuntimeError("runtime unavailable")

    with pytest.raises(RuntimeError, match="runtime unavailable"):
        runtime_service(repository, Runtime(), tmp_path)._run_oasis_simulation(
            {"id": "job-1", "simulation_id": "simulation-local", "execution_token": "token"},
            runtime_state(),
            {},
        )

    assert repository.mapping["status"] == "failed"
    assert repository.mapping["metadata"]["error"] == "runtime unavailable"


def test_runtime_graph_is_supplemental_and_includes_mapping_metadata(tmp_path):
    repository = RuntimeRepository()

    class Runtime:
        def runtime_graph(self, graph_id):
            assert graph_id == "graph-remote"
            return {"nodes": [{"id": "node-1"}], "edges": [], "node_count": 1, "edge_count": 0}

    graph = runtime_service(repository, Runtime(), tmp_path).runtime_graph("simulation-local")

    assert graph["graph_id"] == "graph-remote"
    assert graph["source_revision"] == 2
    assert graph["mapping_status"] == "ready"
    assert graph["nodes"] == [{"id": "node-1"}]
