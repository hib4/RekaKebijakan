import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.database import documents, projects, simulations
from app.repository import Repository


def application(tmp_path, database_url, **overrides):
    return create_app({
        "TESTING": True,
        "DATABASE_URL": database_url,
        "UPLOAD_DIR": tmp_path / "uploads",
        "STORAGE_PATH": tmp_path / "uploads",
        "JOB_DELAY": 0,
        "CORS_ORIGINS": "http://localhost:5173",
        **overrides,
    })


def register(client, email="storage@example.com"):
    assert client.post("/api/auth/register", json={
        "name": "Storage User", "email": email, "password": "password-kuat",
    }).status_code == 201


def create_project(client, name="Project", files=None):
    return client.post(
        "/api/projects",
        data={"project_name": name, "institution": "Instansi", "objective": "Tujuan kebijakan"},
        files=files or [("files", ("policy.txt", io.BytesIO(b"valid policy text"), "text/plain"))],
    )


def test_enforces_project_file_file_size_and_total_byte_quotas(tmp_path, database_url):
    app = application(
        tmp_path, database_url, MAX_ACTIVE_PROJECTS_PER_USER=1, MAX_FILES_PER_PROJECT=1,
        MAX_FILE_UPLOAD_BYTES=32, MAX_TOTAL_UPLOAD_BYTES=20,
    )
    with TestClient(app) as client:
        register(client)
        assert create_project(client).status_code == 201
        active_limit = create_project(client, "Second")
        assert active_limit.status_code == 413
        assert active_limit.json()["error"]["code"] == "upload_quota_exceeded"

    app = application(tmp_path, database_url, MAX_FILES_PER_PROJECT=1)
    with TestClient(app) as client:
        register(client, "count@example.com")
        response = create_project(client, files=[
            ("files", ("a.txt", io.BytesIO(b"first"), "text/plain")),
            ("files", ("b.txt", io.BytesIO(b"second"), "text/plain")),
        ])
        assert response.status_code == 413

    app = application(tmp_path, database_url, MAX_FILE_UPLOAD_BYTES=4)
    with TestClient(app) as client:
        register(client, "size@example.com")
        assert create_project(client).status_code == 413

    app = application(tmp_path, database_url, MAX_FILE_UPLOAD_BYTES=32, MAX_TOTAL_UPLOAD_BYTES=20)
    with TestClient(app) as client:
        register(client, "bytes@example.com")
        first = [("files", ("first.txt", io.BytesIO(b"first policy"), "text/plain"))]
        second = [("files", ("second.txt", io.BytesIO(b"second policy"), "text/plain"))]
        assert create_project(client, "First bytes", first).status_code == 201
        response = create_project(client, "Second bytes", second)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "upload_quota_exceeded"


def test_metadata_failure_rolls_back_database_and_saved_objects(tmp_path, database_url):
    app = application(tmp_path, database_url)
    with TestClient(app, raise_server_exceptions=False) as client:
        register(client)
        original = app.state.repository.create_project_bundle

        def fail(*args, **kwargs):
            raise RuntimeError("database write failed")

        app.state.repository.create_project_bundle = fail
        assert create_project(client).status_code == 500
        app.state.repository.create_project_bundle = original
        assert client.get("/api/projects").json()["projects"] == []
        assert not any(path.is_file() for path in (tmp_path / "uploads").rglob("*"))


def test_bundle_transaction_rolls_back_all_metadata_on_late_insert_failure(database_url):
    repository = Repository(database_url)
    repository.create_user("user-rollback", "Rollback", "rollback@example.com", "hash")
    timestamp = datetime.now(timezone.utc).isoformat()
    state = {
        "id": "sim-rollback", "updated_at": timestamp, "revision": 1,
        "project": {
            "id": "project-rollback", "name": "Rollback", "project_name": "Rollback",
            "institution": "Instansi", "objective": "Tujuan",
        },
    }
    document = {
        "id": "doc-rollback", "simulation_id": state["id"], "name": "policy.txt",
        "path": "sim-rollback/policy.txt", "text": "policy", "size_bytes": 6,
    }
    duplicate_pages = [
        {"page_number": 1, "text": "a", "char_start": 0, "char_end": 1, "metadata": {}},
        {"page_number": 1, "text": "b", "char_start": 1, "char_end": 2, "metadata": {}},
    ]
    with pytest.raises(IntegrityError):
        repository.create_project_bundle(
            state, "user-rollback", [(document, [], duplicate_pages)], 10, 10, 100,
        )
    with repository.engine.connect() as db:
        assert db.execute(select(projects.c.id).where(projects.c.id == state["project"]["id"])).scalar_one_or_none() is None
        assert db.execute(select(simulations.c.id).where(simulations.c.id == state["id"])).scalar_one_or_none() is None
        assert db.execute(select(documents.c.id).where(documents.c.id == document["id"])).scalar_one_or_none() is None
    repository.close()


def test_archived_project_rejects_workflow_mutation(tmp_path, database_url):
    app = application(tmp_path, database_url)
    with TestClient(app) as client:
        register(client)
        created = create_project(client).json()
        assert client.post(f"/api/v1/projects/{created['id']}/archive").status_code == 200
        response = client.post(f"/api/simulations/{created['simulation_id']}/graph-build")
        assert response.status_code == 409
        state = client.get(f"/api/simulations/{created['simulation_id']}").json()
        assert state["stages"]["graph"]["status"] == "ready"


def test_purge_is_retry_safe_and_removes_objects_and_database_data(tmp_path, database_url):
    app = application(tmp_path, database_url, PROJECT_RETENTION_DAYS=7)
    with TestClient(app) as client:
        register(client)
        created = create_project(client).json()
        assert client.delete(f"/api/v1/projects/{created['id']}").status_code == 200
        engine = create_engine(database_url)
        with engine.begin() as db:
            db.execute(update(projects).where(projects.c.id == created["id"]).values(
                delete_after=datetime.now(timezone.utc) - timedelta(seconds=1),
            ))
            storage_key = db.execute(select(documents.c.path).where(
                documents.c.simulation_id == created["simulation_id"]
            )).scalar_one()

        real_delete = app.state.workflow.storage.delete
        attempts = 0

        def flaky_delete(key):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("temporary object-store failure")
            real_delete(key)

        app.state.workflow.storage.delete = flaky_delete
        try:
            app.state.workflow.purge_due_projects()
        except OSError:
            pass
        with engine.connect() as db:
            assert db.execute(select(projects.c.id).where(projects.c.id == created["id"])).scalar_one() == created["id"]
        assert app.state.workflow.purge_due_projects() == 1
        assert not app.state.workflow.storage.exists(storage_key)
        with engine.connect() as db:
            assert db.execute(select(projects.c.id).where(projects.c.id == created["id"])).scalar_one_or_none() is None
            assert db.execute(select(simulations.c.id).where(simulations.c.id == created["simulation_id"])).scalar_one_or_none() is None
        engine.dispose()
