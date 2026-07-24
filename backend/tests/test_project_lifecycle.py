import io
import time

from fastapi.testclient import TestClient

from app import create_app


def create_client(tmp_path, database_url):
    return TestClient(create_app({
        "TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads",
        "JOB_DELAY": 0, "CORS_ORIGINS": "http://localhost:5173",
    }))


def wait_for_stage(client, simulation_id, stage):
    for _ in range(100):
        snapshot = client.get(f"/api/simulations/{simulation_id}").json()
        if snapshot["stages"][stage]["status"] in {"completed", "failed"}:
            return snapshot
        time.sleep(0.02)
    raise AssertionError(f"stage {stage} did not finish")


def test_v1_project_lifecycle_dashboard_and_scenarios(tmp_path, database_url):
    with create_client(tmp_path, database_url) as client:
        assert client.post("/api/auth/register", json={
            "name": "Lifecycle User", "email": "lifecycle@example.com", "password": "password-kuat",
        }).status_code == 201
        created = client.post(
            "/api/projects",
            data={"project_name": "Kebijakan Awal", "institution": "Instansi", "objective": "Tujuan awal"},
            files=[("files", ("policy.txt", io.BytesIO(b"Akses layanan publik"), "text/plain"))],
        ).json()
        project_id = created["id"]

        listing = client.get("/api/v1/projects").json()
        assert listing["total"] == 1
        assert listing["items"][0]["name"] == "Kebijakan Awal"
        version = listing["items"][0]["version"]

        updated = client.patch(f"/api/v1/projects/{project_id}", json={
            "name": "Kebijakan Revisi", "expected_version": version,
        })
        assert updated.status_code == 200
        assert updated.json()["name"] == "Kebijakan Revisi"
        conflict = client.patch(f"/api/v1/projects/{project_id}", json={
            "name": "Versi basi", "expected_version": version,
        })
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "revision_conflict"

        scenario = client.post(f"/api/v1/projects/{project_id}/scenarios", json={
            "name": "Baseline", "kind": "baseline", "config": {"rounds": 5},
        })
        assert scenario.status_code == 201
        assert client.get(f"/api/v1/projects/{project_id}/scenarios").json()["items"][0]["name"] == "Baseline"
        assert client.get("/api/v1/dashboard").json()["metrics"]["active_projects"] == 1

        assert client.post(f"/api/v1/projects/{project_id}/archive").status_code == 200
        assert client.get("/api/v1/projects").json()["total"] == 0
        assert client.get("/api/v1/projects?status=archived").json()["total"] == 1
        assert client.post(f"/api/v1/projects/{project_id}/restore").status_code == 200
        assert client.delete(f"/api/v1/projects/{project_id}").status_code == 200
        assert client.get("/api/v1/projects").json()["total"] == 0


def test_v1_project_resources_are_private(tmp_path, database_url):
    app = create_app({
        "TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads",
        "JOB_DELAY": 0, "CORS_ORIGINS": "http://localhost:5173",
    })
    with TestClient(app) as first, TestClient(app) as second:
        first.post("/api/auth/register", json={"name": "First User", "email": "first-v1@example.com", "password": "password-kuat"})
        project_id = first.post(
            "/api/projects",
            data={"project_name": "Private", "institution": "Instansi", "objective": "Tujuan privat"},
            files=[("files", ("policy.txt", io.BytesIO(b"Dokumen privat"), "text/plain"))],
        ).json()["id"]
        second.post("/api/auth/register", json={"name": "Second User", "email": "second-v1@example.com", "password": "password-kuat"})
        assert second.get(f"/api/v1/projects/{project_id}").status_code == 404
        assert second.post(f"/api/v1/projects/{project_id}/archive").status_code == 404
        assert second.get(f"/api/v1/projects/{project_id}/scenarios").status_code == 404


def test_v1_scenario_lifecycle_persona_overrides_and_run(tmp_path, database_url):
    with create_client(tmp_path, database_url) as client:
        client.post("/api/auth/register", json={
            "name": "Scenario User", "email": "scenario@example.com", "password": "password-kuat",
        })
        created = client.post(
            "/api/v1/projects",
            data={"project_name": "Scenario Project", "institution": "Instansi", "objective": "Uji skenario"},
            files=[("files", ("policy.txt", io.BytesIO(b"Akses layanan dan biaya publik"), "text/plain"))],
        )
        assert created.status_code == 201
        project_id = created.json()["id"]
        simulation_id = created.json()["simulation_id"]
        assert client.post(f"/api/simulations/{simulation_id}/stages/graph/start").status_code == 202
        assert wait_for_stage(client, simulation_id, "graph")["stages"]["graph"]["status"] == "completed"
        assert client.post(f"/api/simulations/{simulation_id}/stages/environment/start", json={"rounds": 3}).status_code == 202
        environment = wait_for_stage(client, simulation_id, "environment")
        assert environment["stages"]["environment"]["status"] == "completed"
        persona_id = environment["environment"]["personas"][0]["id"]
        environment_revision = environment["environment"]["config"]["version"]

        created_scenario = client.post(f"/api/v1/projects/{project_id}/scenarios", json={
            "name": "Pendampingan", "kind": "revision", "config": {"rounds": 3, "socialization": "Tinggi"},
        })
        assert created_scenario.status_code == 201
        scenario = created_scenario.json()
        scenario_id = scenario["id"]
        assert client.get(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}").status_code == 200

        overridden = client.put(
            f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/persona-overrides/{persona_id}",
            json={
                "expected_version": scenario["version"],
                "base_environment_revision": environment_revision,
                "patch": {"name": "Persona Ditinjau", "stance": "Kritis", "active": True},
            },
        )
        assert overridden.status_code == 200
        assert overridden.json()["version"] == 2
        effective = client.get(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/personas").json()["items"]
        assert next(item for item in effective if item["id"] == persona_id)["name"] == "Persona Ditinjau"

        stale = client.put(
            f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/persona-overrides/{persona_id}",
            json={"expected_version": 1, "base_environment_revision": environment_revision, "patch": {"stance": "Netral"}},
        )
        assert stale.status_code == 409
        updated = client.patch(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}", json={
            "description": "Kanal bantuan diperluas", "expected_version": 2,
        })
        assert updated.status_code == 200
        assert updated.json()["version"] == 3

        run = client.post(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/run")
        assert run.status_code == 202
        assert wait_for_stage(client, simulation_id, "simulation")["stages"]["simulation"]["status"] == "completed"

        assert client.post(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/archive").status_code == 200
        assert client.get(f"/api/v1/projects/{project_id}/scenarios").json()["items"] == []
        assert client.post(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}/restore").status_code == 200
        assert client.delete(f"/api/v1/projects/{project_id}/scenarios/{scenario_id}").json() == {"ok": True}
