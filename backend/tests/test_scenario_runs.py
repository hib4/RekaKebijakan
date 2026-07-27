import io
import time

from fastapi.testclient import TestClient

from app import create_app


def wait_for(client, simulation_id, stage):
    for _ in range(200):
        state = client.get(f"/api/simulations/{simulation_id}").json()
        if state["stages"][stage]["status"] == "completed":
            return state
        time.sleep(0.01)
    raise AssertionError(f"{stage} did not complete")


def test_immutable_runs_custom_personas_and_persisted_artifacts(tmp_path, database_url):
    app = create_app({"TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads", "JOB_DELAY": 0, "STORAGE_BACKEND": "local"})
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"name": "Run User", "email": "runs@example.com", "password": "password-kuat"})
        created = client.post("/api/projects", data={
            "project_name": "Run Project", "institution": "Instansi", "objective": "Uji run",
        }, files=[("files", ("policy.txt", io.BytesIO(b"Akses layanan harus adil"), "text/plain"))]).json()
        project_id, simulation_id = created["id"], created["simulation_id"]
        wait_for(client, simulation_id, "graph")
        started = client.post(f"/api/simulations/{simulation_id}/stages/environment/start", json={"rounds": 3})
        assert started.status_code == 202, started.text
        environment = wait_for(client, simulation_id, "environment")

        scenario = client.post(f"/api/v1/projects/{project_id}/scenarios", json={"name": "Baseline", "config": {"rounds": 3}}).json()
        custom = client.post(f"/api/v1/projects/{project_id}/scenarios/{scenario['id']}/personas", json={
            "name": "Persona Lokal", "group": "Warga", "concern": "Akses", "active": True,
        })
        assert custom.status_code == 201
        personas = client.get(f"/api/v1/projects/{project_id}/scenarios/{scenario['id']}/personas").json()["items"]
        assert any(item.get("custom") for item in personas)

        run = client.post(f"/api/v1/projects/{project_id}/scenarios/{scenario['id']}/runs", json={
            "expected_scenario_version": scenario["version"],
        })
        assert run.status_code == 202
        run_id = run.json()["run_id"]
        wait_for(client, simulation_id, "simulation")
        detail = client.get(f"/api/v1/runs/{run_id}").json()
        assert detail["status"] == "completed"
        assert detail["input_snapshot"]["scenario"]["version"] == 1
        event_page = client.get(f"/api/v1/runs/{run_id}/events?cursor=0").json()
        assert event_page["items"]
        assert event_page["run"]["id"] == run_id
        assert client.post(f"/api/v1/runs/{run_id}/interactions", json={
            "tool": "evidence", "question": "Apa bukti utamanya?",
        }).status_code == 201
        assert client.post(f"/api/v1/runs/{run_id}/interviews", json={
            "question": "Apa perhatian utama?", "group": environment["environment"]["personas"][0]["group"],
        }).json()["answers"]
        assert client.get(f"/api/v1/projects/{project_id}/provenance").status_code == 200
        assert client.get(f"/api/v1/runs/{run_id}/provenance").json()["provenance"]["scenario_revision"] == 1
        assert client.get(f"/api/v1/runs/{run_id}/logs").status_code == 200

        client.patch(f"/api/v1/projects/{project_id}/scenarios/{scenario['id']}", json={
            "description": "Changed after run", "expected_version": 1,
        })
        assert client.get(f"/api/v1/runs/{run_id}").json()["input_snapshot"]["scenario"]["description"] == ""
        reproduced = client.post(f"/api/v1/runs/{run_id}/reproduce")
        assert reproduced.status_code == 202
        reproduced_id = reproduced.json()["run_id"]
        assert client.get(f"/api/v1/runs/{reproduced_id}").json()["input_snapshot"] == detail["input_snapshot"]
        wait_for(client, simulation_id, "simulation")

        interview = client.post(f"/api/simulations/{simulation_id}/interviews", json={
            "question": "Apa perhatian utama?", "persona_ids": [environment["environment"]["personas"][0]["id"]],
        }).json()
        assert client.get(f"/api/simulations/{simulation_id}/interviews").json()["items"][0]["id"] == interview["id"]


def test_run_ownership_and_public_pilot_contact(tmp_path, database_url):
    app = create_app({"TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads", "JOB_DELAY": 0, "STORAGE_BACKEND": "local"})
    with TestClient(app) as first, TestClient(app) as second:
        contact = first.post("/api/pilot/contact", json={
            "name": "Pilot User", "email": "pilot@example.com", "institution": "Pemda", "consent": True,
        })
        assert contact.status_code == 201
        first.post("/api/auth/register", json={"name": "First", "email": "first-run@example.com", "password": "password-kuat"})
        created = first.post("/api/projects", data={
            "project_name": "Private Run", "institution": "Instansi", "objective": "Private",
        }, files=[("files", ("policy.txt", io.BytesIO(b"Private policy"), "text/plain"))]).json()
        wait_for(first, created["simulation_id"], "graph")
        started = first.post(f"/api/simulations/{created['simulation_id']}/stages/environment/start", json={"rounds": 3})
        assert started.status_code == 202, started.text
        wait_for(first, created["simulation_id"], "environment")
        scenario = first.post(f"/api/v1/projects/{created['id']}/scenarios", json={"name": "Private Scenario"}).json()
        run_id = first.post(f"/api/v1/projects/{created['id']}/scenarios/{scenario['id']}/run").json()["run_id"]
        second.post("/api/auth/register", json={"name": "Second", "email": "second-run@example.com", "password": "password-kuat"})
        assert second.get(f"/api/v1/runs/{run_id}").status_code == 404
        assert second.post(f"/api/v1/runs/{run_id}/reproduce").status_code == 404
