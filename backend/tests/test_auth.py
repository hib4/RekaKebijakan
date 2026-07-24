import io
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select

from app import create_app
from app.database import simulations
from app.repository import Repository


def make_app(tmp_path, database_url, **overrides):
    config = {
        "TESTING": True,
        "DATABASE_URL": database_url,
        "UPLOAD_DIR": tmp_path / "uploads",
        "JOB_DELAY": 0,
        "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
    }
    config.update(overrides)
    return create_app(config)


def register(client, email="user@example.com", name="Pengguna Satu"):
    return client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "kata-sandi-kuat"},
    )


def create_project(client, name="Kebijakan Privat"):
    return client.post(
        "/api/projects",
        data={"project_name": name, "institution": "Instansi Uji", "objective": "Menguji akses privat"},
        files=[("files", ("policy.txt", io.BytesIO(b"Isi kebijakan"), "text/plain"))],
    )


def test_register_cookie_me_logout_login_duplicate_and_invalid_credentials(tmp_path, database_url):
    with TestClient(make_app(tmp_path, database_url)) as client:
        assert client.get("/api/projects").status_code == 401
        created = register(client, " User@Example.com ")
        assert created.status_code == 201
        assert created.json()["user"]["email"] == "user@example.com"
        cookie = created.headers["set-cookie"]
        assert "rk_session=" in cookie
        assert "HttpOnly" in cookie
        assert "Max-Age=604800" in cookie
        assert client.get("/api/auth/me").json()["user"]["name"] == "Pengguna Satu"

        duplicate = register(client, "user@example.com")
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "email_conflict"
        assert client.post(
            "/api/auth/login", json={"email": "user@example.com", "password": "kata-sandi-salah"}
        ).status_code == 401

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        assert logout.json() == {"ok": True}
        assert client.get("/api/auth/me").status_code == 401
        logged_in = client.post(
            "/api/auth/login", json={"email": "USER@example.com", "password": "kata-sandi-kuat"}
        )
        assert logged_in.status_code == 200
        assert client.get("/api/auth/me").status_code == 200


def test_password_minimum_is_six_characters(tmp_path, database_url):
    with TestClient(make_app(tmp_path, database_url)) as client:
        too_short = client.post(
            "/api/auth/register",
            json={"name": "Pengguna Pendek", "email": "short@example.com", "password": "12345"},
        )
        assert too_short.status_code == 422
        accepted = client.post(
            "/api/auth/register",
            json={"name": "Pengguna Enam", "email": "six@example.com", "password": "123456"},
        )
        assert accepted.status_code == 201


def test_session_and_user_persist_across_app_restart(tmp_path, database_url):
    app = make_app(tmp_path, database_url)
    with TestClient(app) as client:
        register(client)
        token = client.cookies.get("rk_session")
    with TestClient(make_app(tmp_path, database_url)) as reopened:
        reopened.cookies.set("rk_session", token)
        assert reopened.get("/api/auth/me").json()["user"]["email"] == "user@example.com"


def test_projects_are_private_and_cross_user_resources_return_404(tmp_path, database_url):
    app = make_app(tmp_path, database_url)
    with TestClient(app) as first, TestClient(app) as second:
        register(first, "first@example.com", "Pengguna Pertama")
        created = create_project(first)
        assert created.status_code == 201
        simulation_id = created.json()["simulation_id"]
        project_id = created.json()["id"]

        register(second, "second@example.com", "Pengguna Kedua")
        assert second.get("/api/projects").json() == {"projects": []}
        assert second.get(f"/api/projects/{project_id}").status_code == 404
        assert second.get(f"/api/simulations/{simulation_id}").status_code == 404
        assert second.post(f"/api/simulations/{simulation_id}/graph-build").status_code == 404
        assert second.patch(
            f"/api/simulations/{simulation_id}/environment", json={"rounds": 3}
        ).status_code == 404
        assert second.post(f"/api/simulations/{simulation_id}/pause").status_code == 404
        assert second.get(f"/api/reports/{simulation_id}").status_code == 404
        assert second.post(
            f"/api/interactions/{simulation_id}/messages",
            json={"tool": "report", "question": "Apa hasilnya?"},
        ).status_code == 404
        assert first.get(f"/api/simulations/{simulation_id}").status_code == 200


def test_unowned_simulations_remain_inaccessible(tmp_path, database_url):
    repository = Repository(database_url)
    repository.create({
        "id": "sim-legacy",
        "project": {"id": "project-legacy"},
        "updated_at": "2026-01-01T00:00:00+00:00",
    })
    with TestClient(make_app(tmp_path, database_url)) as client:
        register(client)
        assert client.get("/api/simulations/sim-legacy").status_code == 404
        assert client.get("/api/projects").json() == {"projects": []}
    with repository.engine.connect() as db:
        assert db.execute(
            select(simulations.c.owner_user_id).where(simulations.c.id == "sim-legacy")
        ).scalar_one() is None


def test_postgresql_schema_uses_jsonb_and_timezone_aware_timestamps(database_url):
    engine = create_engine(database_url)
    inspector = inspect(engine)
    simulation_columns = {column["name"]: column for column in inspector.get_columns("simulations")}
    user_columns = {column["name"]: column for column in inspector.get_columns("users")}
    session_columns = {column["name"]: column for column in inspector.get_columns("sessions")}
    assert str(simulation_columns["state"]["type"]) == "JSONB"
    assert simulation_columns["updated_at"]["type"].timezone is True
    assert user_columns["created_at"]["type"].timezone is True
    assert session_columns["created_at"]["type"].timezone is True
    assert session_columns["expires_at"]["type"].timezone is True
    engine.dispose()


def test_credentialed_cors_and_authenticated_origin_validation(tmp_path, database_url):
    with TestClient(make_app(tmp_path, database_url)) as client:
        preflight = client.options(
            "/api/projects",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert preflight.headers["access-control-allow-credentials"] == "true"
        register(client)
        blocked = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "invalid_origin"
        assert client.get("/api/auth/me").status_code == 200
        allowed = client.post("/api/auth/logout", headers={"Origin": "http://localhost:5173"})
        assert allowed.status_code == 200

        blocked_registration = client.post(
            "/api/auth/register",
            headers={"Origin": "https://evil.example"},
            json={"name": "Penyerang", "email": "attacker@example.com", "password": "kata-sandi-panjang"},
        )
        assert blocked_registration.status_code == 403


def test_wildcard_cors_is_rejected_with_credentials(tmp_path, database_url):
    try:
        make_app(tmp_path, database_url, CORS_ORIGINS="*")
    except ValueError as error:
        assert "explicit origins" in str(error)
    else:
        raise AssertionError("Wildcard credentialed CORS should be rejected")
