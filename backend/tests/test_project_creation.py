import io
import time

from fastapi.testclient import TestClient

from app import create_app


def create_project(client, key: str, name: str = "Proyek Idempoten"):
    return client.post(
        "/api/projects",
        headers={"Idempotency-Key": key},
        data={"project_name": name, "institution": "Instansi", "objective": "Tujuan kebijakan"},
        files=[("files", ("policy.txt", io.BytesIO(b"Akses layanan publik"), "text/plain"))],
    )


def wait_for_graph(client, simulation_id: str):
    for _ in range(200):
        state = client.get(f"/api/simulations/{simulation_id}").json()
        if state["stages"]["graph"]["status"] in {"completed", "failed"}:
            return state
        time.sleep(0.01)
    raise AssertionError("automatic graph job did not finish")


def test_project_creation_is_owner_scoped_idempotent_and_starts_graph(tmp_path, database_url):
    app = create_app({
        "TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads", "JOB_DELAY": 0,
    })
    with TestClient(app) as first, TestClient(app) as second:
        assert first.post("/api/auth/register", json={
            "name": "First User", "email": "first-create@example.com", "password": "password-kuat",
        }).status_code == 201

        initial = create_project(first, "create-project-1")
        replay = create_project(first, "create-project-1", "Nama yang Diabaikan")

        assert initial.status_code == replay.status_code == 201
        assert replay.json() == initial.json()
        assert len(first.get("/api/projects").json()["projects"]) == 1
        assert len(first.get(f"/api/projects/{initial.json()['id']}").json()["documents"]) == 1
        graph = wait_for_graph(first, initial.json()["simulation_id"])
        assert graph["stages"]["graph"]["status"] == "completed"
        assert graph["graph"]["nodes"]

        assert second.post("/api/auth/register", json={
            "name": "Second User", "email": "second-create@example.com", "password": "password-kuat",
        }).status_code == 201
        other_owner = create_project(second, "create-project-1")
        assert other_owner.status_code == 201
        assert other_owner.json()["id"] != initial.json()["id"]
