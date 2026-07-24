from __future__ import annotations

import json
import sqlite3
import threading
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
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, simulation_id TEXT NOT NULL, name TEXT NOT NULL,
                    path TEXT NOT NULL, text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, simulation_id TEXT NOT NULL, stage TEXT NOT NULL,
                    status TEXT NOT NULL, config TEXT NOT NULL
                );
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, state: dict) -> dict:
        with self.lock, self._connect() as db:
            db.execute("INSERT INTO simulations VALUES (?, ?, ?, ?)", (state["id"], state["project"]["id"], json.dumps(state), state["updated_at"]))
        return state

    def get(self, simulation_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT state FROM simulations WHERE id=?", (simulation_id,)).fetchone()
        return json.loads(row["state"]) if row else None

    def list(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT state FROM simulations ORDER BY updated_at DESC").fetchall()
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
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?)", (job_id, simulation_id, stage, status, json.dumps(config)))

    def job_status(self, job_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row["status"] if row else None

    def set_job_status(self, job_id: str, status: str):
        with self.lock, self._connect() as db:
            db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))

    def claim_job(self, job_id: str):
        with self.lock, self._connect() as db:
            db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (job_id,))

    def recoverable_jobs(self) -> list[dict]:
        with self.lock, self._connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE status IN ('queued','running')").fetchall()
            db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        return [{**dict(row), "config": json.loads(row["config"])} for row in rows]
