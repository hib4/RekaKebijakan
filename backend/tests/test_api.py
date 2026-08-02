import io
import time

import pytest
from fastapi.testclient import TestClient

from app import create_app


@pytest.fixture
def client(tmp_path, database_url):
    application = create_app({
        "TESTING": True,
        "DATABASE_URL": database_url,
        "UPLOAD_DIR": tmp_path / "uploads",
        "JOB_DELAY": 0.001,
        "MAX_UPLOAD_BYTES": 1024 * 1024,
        "CORS_ORIGINS": "http://localhost:5173",
    })
    with TestClient(application) as test_client:
        response = test_client.post(
            "/api/auth/register",
            json={"name": "Pengguna Uji", "email": "api@example.com", "password": "rahasia-kuat"},
        )
        assert response.status_code == 201
        yield test_client


def project(client, name="Uji Kebijakan", content=b"Akses layanan dan transparansi."):
    return client.post(
        "/api/projects",
        data={"project_name": name, "institution": "Pemda Contoh", "objective": "Menilai dampak kebijakan"},
        files=[("files", ("kebijakan.md", io.BytesIO(content), "text/markdown"))],
    )


def wait_for(client, simulation_id, stage, status="completed"):
    for _ in range(300):
        snapshot = client.get(f"/api/simulations/{simulation_id}").json()
        if snapshot["stages"][stage]["status"] == status:
            return snapshot
        time.sleep(0.002)
    raise AssertionError(f"{stage} did not reach {status}")


def start_and_wait(client, simulation_id, stage, payload=None):
    response = client.post(f"/api/simulations/{simulation_id}/stages/{stage}/start", json=payload or {})
    assert response.status_code == 202
    return wait_for(client, simulation_id, stage)


def test_full_frontend_workflow(client):
    response = project(client, "Uji Kebijakan Transportasi", b"Tarif harus menjaga akses dan transparansi.")
    assert response.status_code == 201
    simulation_id = response.json()["simulation_id"]

    graph = start_and_wait(client, simulation_id, "graph")
    assert graph["graph"]["nodes"] and graph["graph"]["edges"]
    environment = start_and_wait(client, simulation_id, "environment", {"rounds": 8})
    assert environment["environment"]["persona_count"] == 30
    assert environment["environment"]["config"]["rounds"] == 8
    simulation = start_and_wait(client, simulation_id, "simulation")
    assert simulation["simulation"]["event_count"] == 48
    assert max(event["round"] for event in simulation["simulation"]["events"]) == 8
    report = start_and_wait(client, simulation_id, "report")
    assert report["report"]["sections"]
    assert "[dok:" in report["report"]["risks"][0]["evidence"]
    assert "[event:" in report["report"]["risks"][0]["evidence"]

    interaction = client.post(f"/api/simulations/{simulation_id}/interactions", json={"tool": "risk", "question": "Apa mitigasi utama?", "persona_group": "Warga terdampak"})
    assert interaction.status_code == 201
    assert interaction.json()["citations"]
    messages = client.get(f"/api/interactions/{simulation_id}/messages").json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert client.get("/api/health").json()["status"] == "ok"


def test_round_validation_and_pause_resume(tmp_path, database_url):
    application = create_app({"TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads", "JOB_DELAY": 0.03})
    with TestClient(application) as client:
        assert client.post(
            "/api/auth/register",
            json={"name": "Pengguna Uji", "email": "pause@example.com", "password": "rahasia-kuat"},
        ).status_code == 201
        created = project(client, "Kebijakan A", b"Isi kebijakan")
        simulation_id = created.json()["simulation_id"]
        invalid = client.post(f"/api/simulations/{simulation_id}/stages/environment/start", json={"rounds": 0})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"
        start_and_wait(client, simulation_id, "graph")
        start_and_wait(client, simulation_id, "environment", {"rounds": 7})
        assert client.post(f"/api/simulations/{simulation_id}/stages/simulation/start", json={}).status_code == 202
        paused = client.post(f"/api/simulations/{simulation_id}/pause")
        assert paused.json()["simulation"]["status"] == "paused"
        resumed = client.post(f"/api/simulations/{simulation_id}/resume")
        assert resumed.json()["simulation"]["status"] == "running"
        final = wait_for(client, simulation_id, "simulation")
        assert final["simulation"]["event_count"] == 42


def test_rounds_default_to_ten_and_simulation_payload_is_validated(client):
    simulation_id = project(client, "Kebijakan Ronde", b"Kebijakan membutuhkan simulasi sepuluh ronde.").json()["simulation_id"]
    start_and_wait(client, simulation_id, "graph")
    environment = start_and_wait(client, simulation_id, "environment")
    assert environment["environment"]["config"]["rounds"] == 10
    assert environment["environment"]["config"]["max_rounds"] == 10
    invalid = client.post(f"/api/simulations/{simulation_id}/stages/simulation/start", json={"rounds": 1001})
    assert invalid.status_code == 422


def test_environment_patch_and_all_interaction_tools(client):
    simulation_id = project(client, "Kebijakan Air", b"Akses air harus adil.").json()["simulation_id"]
    start_and_wait(client, simulation_id, "graph")
    start_and_wait(client, simulation_id, "environment")
    patched = client.patch(f"/api/simulations/{simulation_id}/environment", json={"rounds": 3, "socialization": "Tinggi", "response_mode": "Revisi"})
    assert patched.status_code == 200
    assert patched.json()["environment"]["config"]["rounds"] == 3
    start_and_wait(client, simulation_id, "simulation")
    start_and_wait(client, simulation_id, "report")

    for tool in ("report", "persona", "evidence", "risk", "compare", "revision"):
        response = client.post(f"/api/simulations/{simulation_id}/interactions", json={"tool": tool, "question": "Apa tindak lanjut?"})
        assert response.status_code == 201
        assert response.json()["citations"]
    assert len(client.get(f"/api/interactions/{simulation_id}").json()["messages"]) == 12
    assert client.get("/health").status_code == 200
    readiness = client.get("/ready").json()
    assert readiness["status"] == "ok"
    assert readiness["database"] == "postgresql"
    assert readiness["storage"] == "local"
    assert readiness["schema_revision"] == "0012_oasis_run_scope"


def test_validation_errors_and_stage_conflict(client):
    response = client.post("/api/projects", data={"project_name": "Kebijakan A", "institution": "Instansi A", "objective": "Tujuan kebijakan"})
    assert response.status_code == 422
    assert "dokumen" in response.json()["message"].lower()
    simulation_id = project(client).json()["simulation_id"]
    locked = client.post(f"/api/simulations/{simulation_id}/stages/environment/start", json={})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "stage_locked"
    missing = client.get("/api/simulations/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_runtime_graph_distinguishes_pending_available_and_missing(client, monkeypatch):
    simulation_id = project(client).json()["simulation_id"]

    response = client.get(f"/api/simulations/{simulation_id}/runtime-graph")

    assert response.status_code == 200
    assert response.json() == {"available": False}

    monkeypatch.setattr(client.app.state.workflow, "runtime_graph", lambda _simulation_id: {
        "graph_id": "zep-1", "source_revision": 1, "mapping_status": "running",
        "node_count": 1, "edge_count": 0, "nodes": [{"id": "node-1"}], "edges": [],
    })
    available = client.get(f"/api/simulations/{simulation_id}/runtime-graph")
    assert available.status_code == 200
    assert available.json()["available"] is True
    assert available.json()["graph_id"] == "zep-1"

    assert client.get("/api/simulations/missing/runtime-graph").status_code == 404


def test_cors_aliases_multiple_files_and_event_cursor(client):
    preflight = client.options("/api/projects", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    created = client.post(
        "/api/projects",
        data={"name": "Kebijakan Multi", "institution": "Pemda", "description": "Uji dua berkas"},
        files=[
            ("files", ("a.txt", io.BytesIO(b"Sumber A"), "text/plain")),
            ("files", ("b.md", io.BytesIO(b"Sumber B"), "text/markdown")),
        ],
    )
    simulation_id = created.json()["simulation_id"]
    project_id = created.json()["id"]
    assert len(client.get(f"/api/projects/{project_id}").json()["documents"]) == 2
    assert client.post(f"/api/simulations/{simulation_id}/graph/start", json={}).status_code == 202
    wait_for(client, simulation_id, "graph")
    start_and_wait(client, simulation_id, "environment", {"rounds": 3})
    start_and_wait(client, simulation_id, "simulation")
    cursor = client.get(f"/api/runs/{simulation_id}/events?after=2").json()
    assert cursor["event_count"] == 18
    assert len(cursor["events"]) == 16


def test_upload_limit_returns_json_without_creating_project(tmp_path, database_url):
    application = create_app({"TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads", "MAX_UPLOAD_BYTES": 300})
    with TestClient(application) as client:
        assert client.post(
            "/api/auth/register",
            json={"name": "Pengguna Uji", "email": "limit@example.com", "password": "rahasia-kuat"},
        ).status_code == 201
        response = project(client, content=b"x" * 1000)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "payload_too_large"
        assert client.get("/api/projects").json()["projects"] == []


def test_grounded_artifacts_interviews_and_graph_feedback(client):
    created = project(client, "Kebijakan Pesisir", b"Nelayan membutuhkan akses pelabuhan, subsidi bahan bakar, dan perlindungan abrasi.")
    simulation_id = created.json()["simulation_id"]
    project_id = created.json()["id"]
    wait_for(client, simulation_id, "graph")
    chunks = client.get(f"/api/projects/{project_id}/chunks").json()["chunks"]
    assert chunks and chunks[0]["text"].startswith("Nelayan")

    graph = start_and_wait(client, simulation_id, "graph")
    assert graph["ontology"]["entity_types"]
    assert any(node["label"] in {"Nelayan", "Membutuhkan", "Akses", "Pelabuhan", "Subsidi", "Bahan"} for node in graph["graph"]["nodes"])
    assert any(node.get("citations") for node in graph["graph"]["nodes"])
    start_and_wait(client, simulation_id, "environment", {"rounds": 3})
    start_and_wait(client, simulation_id, "simulation")
    report = start_and_wait(client, simulation_id, "report")
    assert report["report"]["sections"][0]["citations"][0]["chunk_id"] == chunks[0]["id"]
    persisted = client.get(f"/api/simulations/{simulation_id}/citations").json()["citations"]
    assert any(item["source_type"] == "document_chunk" for item in persisted)

    interview = client.post(
        f"/api/simulations/{simulation_id}/interviews",
        json={"question": "Apa perhatian utama?", "persona_ids": ["persona-1"]},
    )
    assert interview.status_code == 201
    assert len(interview.json()["answers"]) == 1

    revision = report["graph"]["revision"]
    feedback = client.post(
        f"/api/simulations/{simulation_id}/graph/feedback",
        json={
            "action": "add_node",
            "patch": {"id": "risk-community", "label": "Risiko komunitas", "type": "Risk", "summary": "Hasil review manusia"},
            "reason": "Tambahkan risiko hasil review",
            "base_revision": revision,
        },
    )
    assert feedback.status_code == 200
    snapshot = client.get(f"/api/simulations/{simulation_id}").json()
    assert snapshot["graph"]["revision"] == revision + 1
    assert snapshot["report"]["stale"] is True
