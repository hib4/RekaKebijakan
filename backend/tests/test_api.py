import io
import time

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    application = create_app({
        "TESTING": True,
        "DATABASE_PATH": tmp_path / "test.sqlite3",
        "UPLOAD_DIR": tmp_path / "uploads",
        "JOB_DELAY": 0.001,
    })
    return application.test_client()


def wait_for(client, simulation_id, stage, status="completed"):
    for _ in range(300):
        snapshot = client.get(f"/api/simulations/{simulation_id}").get_json()
        if snapshot["stages"][stage]["status"] == status:
            return snapshot
        time.sleep(0.002)
    raise AssertionError(f"{stage} did not reach {status}")


def start_and_wait(client, simulation_id, stage, payload=None):
    response = client.post(f"/api/simulations/{simulation_id}/stages/{stage}/start", json=payload or {})
    assert response.status_code == 202
    return wait_for(client, simulation_id, stage)


def test_full_frontend_workflow(client):
    response = client.post("/api/projects", data={
        "project_name": "Uji Kebijakan Transportasi",
        "institution": "Pemda Contoh",
        "objective": "Menilai dampak perubahan tarif",
        "files": (io.BytesIO(b"Tarif harus menjaga akses dan transparansi."), "kebijakan.md"),
    }, content_type="multipart/form-data")
    assert response.status_code == 201
    simulation_id = response.get_json()["simulation_id"]

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
    assert interaction.get_json()["citations"]
    messages = client.get(f"/api/interactions/{simulation_id}/messages").get_json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert client.get("/api/health").get_json()["status"] == "ok"


def test_round_validation_and_pause_resume(tmp_path):
    application = create_app({"TESTING": True, "DATABASE_PATH": tmp_path / "pause.sqlite3", "UPLOAD_DIR": tmp_path / "uploads", "JOB_DELAY": 0.03})
    client = application.test_client()
    created = client.post("/api/projects", data={"project_name": "Kebijakan A", "institution": "Instansi A", "objective": "Tujuan kebijakan", "files": (io.BytesIO(b"Isi kebijakan"), "policy.txt")}, content_type="multipart/form-data")
    simulation_id = created.get_json()["simulation_id"]
    invalid = client.post(f"/api/simulations/{simulation_id}/stages/environment/start", json={"rounds": 4})
    assert invalid.status_code == 422
    start_and_wait(client, simulation_id, "graph")
    start_and_wait(client, simulation_id, "environment", {"rounds": 3})
    assert client.post(f"/api/simulations/{simulation_id}/stages/simulation/start", json={}).status_code == 202
    paused = client.post(f"/api/simulations/{simulation_id}/pause")
    assert paused.get_json()["simulation"]["status"] == "paused"
    resumed = client.post(f"/api/simulations/{simulation_id}/resume")
    assert resumed.get_json()["simulation"]["status"] == "running"
    final = wait_for(client, simulation_id, "simulation")
    assert final["simulation"]["event_count"] == 18


def test_environment_patch_and_all_interaction_tools(client):
    created = client.post("/api/projects", data={
        "project_name": "Kebijakan Air",
        "institution": "Pemda Contoh",
        "objective": "Menilai akses air",
        "files": (io.BytesIO(b"Akses air harus adil."), "policy.txt"),
    }, content_type="multipart/form-data")
    simulation_id = created.get_json()["simulation_id"]
    start_and_wait(client, simulation_id, "graph")
    start_and_wait(client, simulation_id, "environment")
    patched = client.patch(f"/api/simulations/{simulation_id}/environment", json={"rounds": 3, "socialization": "Tinggi", "response_mode": "Revisi"})
    assert patched.status_code == 200
    assert patched.get_json()["environment"]["config"]["rounds"] == 3
    start_and_wait(client, simulation_id, "simulation")
    start_and_wait(client, simulation_id, "report")

    for tool in ("report", "persona", "evidence", "risk", "compare", "revision"):
        response = client.post(f"/api/simulations/{simulation_id}/interactions", json={"tool": tool, "question": "Apa tindak lanjut?"})
        assert response.status_code == 201
        assert response.get_json()["citations"]
    assert len(client.get(f"/api/interactions/{simulation_id}").get_json()["messages"]) == 12
    assert client.get("/health").status_code == 200


def test_project_requires_document(client):
    response = client.post("/api/projects", data={"project_name": "Kebijakan A", "institution": "Instansi A", "objective": "Tujuan kebijakan"})
    assert response.status_code == 422
    assert "dokumen" in response.get_json()["message"].lower()
