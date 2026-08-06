import io

from fastapi.testclient import TestClient

from app import create_app


QUICK_DEMO = {
    "project_name": "Demo Registrasi Digital UMKM",
    "institution": "Dinas Koperasi",
    "objective": "Menilai dampak registrasi digital bagi pelaku UMKM",
    "workflow_mode": "quick_demo",
    "demo_bundle_id": "registrasi-digital-umkm-v1",
}


def test_quick_demo_bootstraps_owned_artifacts_and_local_report(tmp_path, database_url):
    app = create_app({
        "TESTING": True,
        "DATABASE_URL": database_url,
        "UPLOAD_DIR": tmp_path / "uploads",
        "JOB_DELAY": 0,
    })
    with TestClient(app) as client:
        assert client.post("/api/auth/register", json={
            "name": "Demo User", "email": "quick-demo@example.com", "password": "password-kuat",
        }).status_code == 201

        created = client.post("/api/projects", data=QUICK_DEMO)
        assert created.status_code == 201
        project_id = created.json()["id"]
        simulation_id = created.json()["simulation_id"]
        assert created.json()["project"]["workflow_mode"] == "quick_demo"
        assert created.json()["project"]["demo_bundle_id"] == "registrasi-digital-umkm-v1"

        project = client.get(f"/api/projects/{project_id}").json()
        assert project["workflow_mode"] == "quick_demo"
        assert project["demo_bundle_id"] == "registrasi-digital-umkm-v1"
        assert project["documents"] == []

        state = client.get(f"/api/simulations/{simulation_id}").json()
        assert state["provenance"] == {
            "workflow_mode": "quick_demo",
            "demo_bundle_id": "registrasi-digital-umkm-v1",
            "execution_kind": "accelerated_fixture",
        }
        assert state["workflow"]["mode"] == "quick_demo"
        assert state["workflow"]["accelerated_steps"] == ["graph", "environment", "simulation"]
        assert state["workflow"]["bundle"]["id"] == "registrasi-digital-umkm-v1"
        assert state["workflow"]["bundle"]["title"] == "Registrasi Digital UMKM"
        assert state["workflow"]["bundle"]["version"] == "1"
        assert len(state["workflow"]["bundle"]["content_digest"]) == 64
        assert state["graph"]["nodes"] and state["graph"]["edges"]
        issue_labels = {item["label"] for item in state["graph"]["nodes"] if item["type"] == "Issue"}
        assert {"Registrasi digital", "Perlindungan data", "Layanan luring"} <= issue_labels
        assert state["environment"]["personas"]
        assert state["environment"]["config"]["rounds"] == 5
        assert state["simulation"]["event_count"] == 30
        assert {event["type"] for event in state["simulation"]["events"]} >= {
            "CREATE_POST", "CREATE_COMMENT", "QUOTE_POST", "REPOST", "SEARCH_POSTS", "UPVOTE_POST",
        }
        assert {event["channel"] for event in state["simulation"]["events"]} == {"twitter", "reddit"}
        assert [event["sequence"] for event in state["simulation"]["events"]] == list(range(1, 31))
        assert state["logs"][-1]["message"] == "Tahap simulation selesai"
        for stage in ("graph", "environment", "simulation"):
            assert state["stages"][stage]["status"] == "completed"
            assert state["stages"][stage]["execution_kind"] == "accelerated_fixture"
        assert state["stages"]["report"]["status"] == "completed"
        assert state["stages"]["report"]["execution_kind"] == "accelerated_fixture"
        assert state["stages"]["interaction"]["status"] == "ready"
        assert state["report"]["generated_by"] == "deterministic-local"
        assert len(state["report"]["sections"]) == 5
        assert all(section["citations"] for section in state["report"]["sections"])
        assert {citation["source_type"] for citation in state["report"]["citations"]} == {"event"}

        runtime_graph = client.get(f"/api/simulations/{simulation_id}/runtime-graph").json()
        assert runtime_graph["available"] is True
        assert runtime_graph["mapping_status"] == "completed"
        assert runtime_graph["node_count"] == 53
        assert runtime_graph["edge_count"] == 77
        assert runtime_graph["node_count"] == len(runtime_graph["nodes"])
        assert runtime_graph["edge_count"] == len(runtime_graph["edges"])
        assert {node["type"] for node in runtime_graph["nodes"]} >= {
            "Persona", "PersonaGroup", "Concern", "PolicyIssue", "SimulationPhase",
        }
        runtime_node_ids = {node["id"] for node in runtime_graph["nodes"]}
        assert runtime_node_ids
        assert all(edge["source"] in runtime_node_ids and edge["target"] in runtime_node_ids
                   for edge in runtime_graph["edges"])

        for stage in ("graph", "environment", "simulation", "report"):
            blocked = client.post(f"/api/simulations/{simulation_id}/stages/{stage}/start", json={})
            assert blocked.status_code == 409
        blocked_feedback = client.post(f"/api/simulations/{simulation_id}/graph/feedback", json={
            "action": "add_node", "patch": {"id": "new-node"}, "reason": "Uji perubahan",
        })
        assert blocked_feedback.status_code == 409

        scenario = client.post(f"/api/v1/projects/{project_id}/scenarios", json={
            "name": "Skenario Quick", "config": {"rounds": 2},
        }).json()
        blocked_run = client.post(
            f"/api/v1/projects/{project_id}/scenarios/{scenario['id']}/runs",
            json={"expected_scenario_version": scenario["version"]},
        )
        assert blocked_run.status_code == 409
        assert client.get(f"/api/v1/projects/{project_id}/scenarios/{scenario['id']}/runs").json()["items"] == []

        assert client.app.state.repository.get_oasis_mapping(simulation_id) is None

        interaction = client.post(f"/api/simulations/{simulation_id}/interactions", json={
            "tool": "report", "question": "Apa temuan utama?",
        })
        assert interaction.status_code == 201


def test_quick_demo_contract_rejects_invalid_bundle_and_files(tmp_path, database_url):
    app = create_app({"TESTING": True, "DATABASE_URL": database_url, "UPLOAD_DIR": tmp_path / "uploads"})
    with TestClient(app) as client:
        client.post("/api/auth/register", json={
            "name": "Validation User", "email": "quick-validation@example.com", "password": "password-kuat",
        })

        missing_bundle = client.post("/api/projects", data={key: value for key, value in QUICK_DEMO.items()
                                                             if key != "demo_bundle_id"})
        assert missing_bundle.status_code == 422

        unknown_mode = client.post("/api/projects", data=QUICK_DEMO | {"workflow_mode": "fast"})
        assert unknown_mode.status_code == 422

        with_file = client.post(
            "/api/projects",
            data=QUICK_DEMO,
            files=[("files", ("policy.txt", io.BytesIO(b"not accepted"), "text/plain"))],
        )
        assert with_file.status_code == 422
        assert client.get("/api/projects").json()["projects"] == []
