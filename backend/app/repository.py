from __future__ import annotations

import json
import hashlib
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable


class Repository:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL,
                    owner_user_id TEXT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, simulation_id TEXT NOT NULL, name TEXT NOT NULL,
                    path TEXT NOT NULL, text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, simulation_id TEXT NOT NULL, stage TEXT NOT NULL,
                    status TEXT NOT NULL, config TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_simulation_status
                    ON jobs(simulation_id, status);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_simulation
                    ON jobs(simulation_id)
                    WHERE status IN ('queued','running','paused');
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(simulations)")}
            if "owner_user_id" not in columns:
                db.execute("ALTER TABLE simulations ADD COLUMN owner_user_id TEXT NULL")
            db.execute("CREATE INDEX IF NOT EXISTS simulations_owner_updated ON simulations(owner_user_id, updated_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS sessions_expires_at ON sessions(expires_at)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, state: dict, owner_user_id: str | None = None) -> dict:
        with self.lock, self._connect() as db:
            db.execute(
                "INSERT INTO simulations (id, project_id, state, updated_at, owner_user_id) VALUES (?, ?, ?, ?, ?)",
                (state["id"], state["project"]["id"], json.dumps(state), state["updated_at"], owner_user_id),
            )
        return state

    def get(self, simulation_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT state FROM simulations WHERE id=?", (simulation_id,)).fetchone()
        return json.loads(row["state"]) if row else None

    def list(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT state FROM simulations ORDER BY updated_at DESC").fetchall()
        return [json.loads(row["state"]) for row in rows]

    def get_for_user(self, simulation_id: str, user_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT state FROM simulations WHERE id=? AND owner_user_id=?",
                (simulation_id, user_id),
            ).fetchone()
        return json.loads(row["state"]) if row else None

    def list_for_user(self, user_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT state FROM simulations WHERE owner_user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [json.loads(row["state"]) for row in rows]

    def mutate(self, simulation_id: str, callback: Callable[[dict], None]) -> dict | None:
        with self.lock, self._connect() as db:
            row = db.execute("SELECT state FROM simulations WHERE id=?", (simulation_id,)).fetchone()
            if not row:
                return None
            state = json.loads(row["state"])
            callback(state)
            db.execute("UPDATE simulations SET state=?, updated_at=? WHERE id=?", (json.dumps(state), state["updated_at"], simulation_id))
            return state

    def mutate_for_user(self, simulation_id: str, user_id: str, callback: Callable[[dict], None]) -> dict | None:
        with self.lock, self._connect() as db:
            row = db.execute(
                "SELECT state FROM simulations WHERE id=? AND owner_user_id=?",
                (simulation_id, user_id),
            ).fetchone()
            if not row:
                return None
            state = json.loads(row["state"])
            callback(state)
            db.execute(
                "UPDATE simulations SET state=?, updated_at=? WHERE id=? AND owner_user_id=?",
                (json.dumps(state), state["updated_at"], simulation_id, user_id),
            )
            return state

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_user(self, user_id: str, name: str, email: str, password_hash: str) -> dict | None:
        created_at = int(time.time())
        with self.lock, self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, name, email, password_hash, created_at),
                )
            except sqlite3.IntegrityError:
                return None
        return {"id": user_id, "name": name, "email": email, "created_at": created_at}

    def user_by_email(self, email: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None

    def create_session(self, token: str, user_id: str, ttl_seconds: int):
        created_at = int(time.time())
        with self.lock, self._connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (created_at,))
            db.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (self.token_hash(token), user_id, created_at, created_at + ttl_seconds),
            )

    def user_for_session(self, token: str) -> dict | None:
        current_time = int(time.time())
        with self.lock, self._connect() as db:
            row = db.execute(
                """SELECT users.id, users.name, users.email, users.created_at
                   FROM sessions JOIN users ON users.id=sessions.user_id
                   WHERE sessions.token_hash=? AND sessions.expires_at>?""",
                (self.token_hash(token), current_time),
            ).fetchone()
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (current_time,))
        return dict(row) if row else None

    def delete_session(self, token: str):
        with self.lock, self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (self.token_hash(token),))

    def add_document(self, document: dict):
        with self.lock, self._connect() as db:
            values = tuple(document[key] for key in ("id", "simulation_id", "name", "path", "text"))
            db.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)", values)

    def documents(self, simulation_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM documents WHERE simulation_id=? ORDER BY name", (simulation_id,))
            return [dict(row) for row in rows]

    def put_job(self, job_id: str, simulation_id: str, stage: str, status: str, config: dict):
        with self.lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute(
                "SELECT 1 FROM jobs WHERE simulation_id=? AND status IN ('queued','running','paused') LIMIT 1",
                (simulation_id,),
            ).fetchone()
            if active:
                return False
            try:
                db.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?)", (job_id, simulation_id, stage, status, json.dumps(config)))
            except sqlite3.IntegrityError:
                return False
            return True

    def job_status(self, job_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row["status"] if row else None

    def set_job_status(self, job_id: str, status: str):
        with self.lock, self._connect() as db:
            db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))

    def claim_job(self, job_id: str) -> bool:
        with self.lock, self._connect() as db:
            cursor = db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (job_id,))
            return cursor.rowcount == 1

    def active_jobs(self, simulation_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE simulation_id=? AND status IN ('queued','running','paused')",
                (simulation_id,),
            ).fetchall()
        return [{**dict(row), "config": json.loads(row["config"])} for row in rows]

    def recoverable_jobs(self) -> list[dict]:
        with self.lock, self._connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE status IN ('queued','running')").fetchall()
            db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        return [{**dict(row), "config": json.loads(row["config"])} for row in rows]
