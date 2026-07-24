from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine

from .database import documents, jobs, sessions, simulations, users


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class Repository:
    def __init__(self, database_url: str, engine: Engine | None = None):
        self.database_url = database_url
        self.engine = engine or create_engine(database_url, pool_pre_ping=True)
        self.lock = threading.RLock()

    def close(self) -> None:
        self.engine.dispose()

    def ping(self) -> None:
        with self.engine.connect() as db:
            db.execute(text("SELECT 1"))

    def create(self, state: dict, owner_user_id: str | None = None) -> dict:
        with self.lock, self.engine.begin() as db:
            db.execute(
                insert(simulations).values(
                    id=state["id"],
                    project_id=state["project"]["id"],
                    state=state,
                    updated_at=parse_timestamp(state["updated_at"]),
                    owner_user_id=owner_user_id,
                )
            )
        return state

    def get(self, simulation_id: str) -> dict | None:
        with self.engine.connect() as db:
            return db.execute(select(simulations.c.state).where(simulations.c.id == simulation_id)).scalar_one_or_none()

    def list(self) -> list[dict]:
        with self.engine.connect() as db:
            return list(db.execute(select(simulations.c.state).order_by(simulations.c.updated_at.desc())).scalars())

    def get_for_user(self, simulation_id: str, user_id: str) -> dict | None:
        with self.engine.connect() as db:
            statement = select(simulations.c.state).where(
                simulations.c.id == simulation_id,
                simulations.c.owner_user_id == user_id,
            )
            return db.execute(statement).scalar_one_or_none()

    def list_for_user(self, user_id: str) -> list[dict]:
        with self.engine.connect() as db:
            statement = (
                select(simulations.c.state)
                .where(simulations.c.owner_user_id == user_id)
                .order_by(simulations.c.updated_at.desc())
            )
            return list(db.execute(statement).scalars())

    def mutate(self, simulation_id: str, callback: Callable[[dict], None]) -> dict | None:
        return self._mutate(simulation_id, callback)

    def mutate_for_user(
        self, simulation_id: str, user_id: str, callback: Callable[[dict], None]
    ) -> dict | None:
        return self._mutate(simulation_id, callback, user_id)

    def _mutate(
        self,
        simulation_id: str,
        callback: Callable[[dict], None],
        user_id: str | None = None,
    ) -> dict | None:
        with self.lock, self.engine.begin() as db:
            statement = select(simulations.c.state).where(simulations.c.id == simulation_id)
            if user_id is not None:
                statement = statement.where(simulations.c.owner_user_id == user_id)
            state = db.execute(statement.with_for_update()).scalar_one_or_none()
            if state is None:
                return None
            callback(state)
            db.execute(
                update(simulations)
                .where(simulations.c.id == simulation_id)
                .values(state=state, updated_at=parse_timestamp(state["updated_at"]))
            )
            return state

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_user(self, user_id: str, name: str, email: str, password_hash: str) -> dict | None:
        created_at = utc_now()
        try:
            with self.lock, self.engine.begin() as db:
                db.execute(
                    insert(users).values(
                        id=user_id,
                        name=name,
                        email=email,
                        password_hash=password_hash,
                        created_at=created_at,
                    )
                )
        except IntegrityError:
            return None
        return {"id": user_id, "name": name, "email": email, "created_at": created_at}

    def user_by_email(self, email: str) -> dict | None:
        with self.engine.connect() as db:
            row = db.execute(select(users).where(users.c.email == email)).mappings().one_or_none()
            return dict(row) if row else None

    def create_session(self, token: str, user_id: str, ttl_seconds: int) -> None:
        created_at = utc_now()
        with self.lock, self.engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.expires_at <= created_at))
            db.execute(
                insert(sessions).values(
                    token_hash=self.token_hash(token),
                    user_id=user_id,
                    created_at=created_at,
                    expires_at=created_at + timedelta(seconds=ttl_seconds),
                )
            )

    def user_for_session(self, token: str) -> dict | None:
        current_time = utc_now()
        with self.lock, self.engine.begin() as db:
            statement = (
                select(users.c.id, users.c.name, users.c.email, users.c.created_at)
                .select_from(sessions.join(users, users.c.id == sessions.c.user_id))
                .where(
                    sessions.c.token_hash == self.token_hash(token),
                    sessions.c.expires_at > current_time,
                )
            )
            row = db.execute(statement).mappings().one_or_none()
            db.execute(delete(sessions).where(sessions.c.expires_at <= current_time))
            return dict(row) if row else None

    def delete_session(self, token: str) -> None:
        with self.lock, self.engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.token_hash == self.token_hash(token)))

    def add_document(self, document: dict) -> None:
        with self.lock, self.engine.begin() as db:
            db.execute(insert(documents).values(**document))

    def documents(self, simulation_id: str) -> list[dict]:
        with self.engine.connect() as db:
            statement = select(documents).where(documents.c.simulation_id == simulation_id).order_by(documents.c.name)
            return [dict(row) for row in db.execute(statement).mappings()]

    def put_job(self, job_id: str, simulation_id: str, stage: str, status: str, config: dict) -> bool:
        try:
            with self.lock, self.engine.begin() as db:
                db.execute(
                    insert(jobs).values(
                        id=job_id,
                        simulation_id=simulation_id,
                        stage=stage,
                        status=status,
                        config=config,
                    )
                )
            return True
        except IntegrityError:
            return False

    def job_status(self, job_id: str) -> str | None:
        with self.engine.connect() as db:
            return db.execute(select(jobs.c.status).where(jobs.c.id == job_id)).scalar_one_or_none()

    def set_job_status(self, job_id: str, status: str) -> None:
        with self.lock, self.engine.begin() as db:
            db.execute(update(jobs).where(jobs.c.id == job_id).values(status=status))

    def claim_job(self, job_id: str) -> bool:
        with self.lock, self.engine.begin() as db:
            result = db.execute(
                update(jobs)
                .where(jobs.c.id == job_id, jobs.c.status == "queued")
                .values(status="running")
            )
            return result.rowcount == 1

    def active_jobs(self, simulation_id: str) -> list[dict]:
        with self.engine.connect() as db:
            statement = select(jobs).where(
                jobs.c.simulation_id == simulation_id,
                jobs.c.status.in_(("queued", "running", "paused")),
            )
            return [dict(row) for row in db.execute(statement).mappings()]

    def recoverable_jobs(self) -> list[dict]:
        with self.lock, self.engine.begin() as db:
            statement = select(jobs).where(jobs.c.status.in_(("queued", "running"))).with_for_update()
            rows = [dict(row) for row in db.execute(statement).mappings()]
            db.execute(update(jobs).where(jobs.c.status == "running").values(status="queued"))
            return rows
