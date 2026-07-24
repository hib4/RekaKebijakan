from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import and_, create_engine, delete, insert, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine

from .database import citations, document_chunks, documents, jobs, sessions, simulations, users


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

    def add_document_with_chunks(self, document: dict, chunks: list[dict]) -> None:
        with self.lock, self.engine.begin() as db:
            db.execute(insert(documents).values(**document))
            if chunks:
                db.execute(insert(document_chunks), [item | {"simulation_id": document["simulation_id"]} for item in chunks])

    def documents(self, simulation_id: str) -> list[dict]:
        with self.engine.connect() as db:
            statement = select(documents).where(documents.c.simulation_id == simulation_id).order_by(documents.c.name)
            return [dict(row) for row in db.execute(statement).mappings()]

    def public_documents(self, simulation_id: str) -> list[dict]:
        with self.engine.connect() as db:
            statement = select(documents.c.id, documents.c.simulation_id, documents.c.name).where(
                documents.c.simulation_id == simulation_id
            ).order_by(documents.c.name)
            return [dict(row) for row in db.execute(statement).mappings()]

    def chunks(self, simulation_id: str, document_id: str | None = None) -> list[dict]:
        with self.engine.connect() as db:
            statement = select(document_chunks).where(document_chunks.c.simulation_id == simulation_id)
            if document_id:
                statement = statement.where(document_chunks.c.document_id == document_id)
            statement = statement.order_by(document_chunks.c.document_id, document_chunks.c.ordinal)
            return [dict(row) for row in db.execute(statement).mappings()]

    def chunk(self, chunk_id: str) -> dict | None:
        with self.engine.connect() as db:
            row = db.execute(select(document_chunks).where(document_chunks.c.id == chunk_id)).mappings().one_or_none()
            return dict(row) if row else None

    def replace_citations(self, simulation_id: str, artifact_type: str, artifact_id: str, values: list[dict]) -> None:
        with self.lock, self.engine.begin() as db:
            db.execute(delete(citations).where(
                citations.c.simulation_id == simulation_id,
                citations.c.artifact_type == artifact_type,
                citations.c.artifact_id == artifact_id,
            ))
            if values:
                rows = []
                for index, item in enumerate(values):
                    citation_key = f"{artifact_type}:{artifact_id}:{index}:{item['source_id']}"
                    rows.append({
                    "id": item.get("id") or f"cite_{hashlib.sha256(citation_key.encode()).hexdigest()[:16]}",
                    "simulation_id": simulation_id,
                    "artifact_type": artifact_type,
                    "artifact_id": artifact_id,
                    "ordinal": index,
                    "source_type": item["source_type"],
                    "source_id": item["source_id"],
                    "document_id": item.get("document_id"),
                    "chunk_id": item.get("chunk_id"),
                    "locator": item.get("locator", {}),
                    "quote": item.get("quote"),
                    "created_at": utc_now(),
                    })
                db.execute(insert(citations), rows)

    def citations(self, simulation_id: str, artifact_type: str | None = None, artifact_id: str | None = None) -> list[dict]:
        with self.engine.connect() as db:
            statement = select(citations).where(citations.c.simulation_id == simulation_id)
            if artifact_type:
                statement = statement.where(citations.c.artifact_type == artifact_type)
            if artifact_id:
                statement = statement.where(citations.c.artifact_id == artifact_id)
            return [dict(row) for row in db.execute(statement.order_by(citations.c.artifact_id, citations.c.ordinal)).mappings()]

    def put_job(
        self, job_id: str, simulation_id: str, stage: str, status: str, config: dict, input_revision: int = 0
    ) -> bool:
        timestamp = utc_now()
        try:
            with self.lock, self.engine.begin() as db:
                db.execute(
                    insert(jobs).values(
                        id=job_id,
                        simulation_id=simulation_id,
                        stage=stage,
                        status=status,
                        config=config,
                        created_at=timestamp,
                        updated_at=timestamp,
                        available_at=timestamp,
                        input_revision=input_revision,
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
            values = {"status": status, "updated_at": utc_now()}
            if status == "completed":
                values["completed_at"] = utc_now()
            db.execute(update(jobs).where(jobs.c.id == job_id).values(**values))

    def claim_job(self, job_id: str) -> bool:
        with self.lock, self.engine.begin() as db:
            result = db.execute(
                update(jobs)
                .where(jobs.c.id == job_id, jobs.c.status == "queued")
                .values(status="running", started_at=utc_now(), updated_at=utc_now())
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
        now = utc_now()
        with self.engine.begin() as db:
            db.execute(update(jobs).where(
                jobs.c.status == "running",
                or_(jobs.c.lease_owner.is_(None), jobs.c.lease_expires_at < now),
            ).values(status="queued", available_at=now, lease_owner=None, lease_expires_at=None, updated_at=now))
            statement = select(jobs).where(jobs.c.status == "queued").order_by(jobs.c.created_at)
            return [dict(row) for row in db.execute(statement).mappings()]

    def claim_next_job(self, worker_id: str, lease_seconds: int = 60, job_id: str | None = None) -> dict | None:
        now = utc_now()
        with self.lock, self.engine.begin() as db:
            condition = and_(jobs.c.status == "queued", jobs.c.available_at <= now)
            if job_id:
                condition = and_(condition, jobs.c.id == job_id)
            statement = select(jobs).where(condition).order_by(jobs.c.created_at).with_for_update(skip_locked=True).limit(1)
            row = db.execute(statement).mappings().one_or_none()
            if not row:
                return None
            db.execute(update(jobs).where(jobs.c.id == row["id"]).values(
                status="running",
                lease_owner=worker_id,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                heartbeat_at=now,
                started_at=row["started_at"] or now,
                updated_at=now,
                attempts=jobs.c.attempts + 1,
            ))
            return dict(row) | {"status": "running", "lease_owner": worker_id, "attempts": row["attempts"] + 1}

    def renew_job_lease(self, job_id: str, worker_id: str, lease_seconds: int = 60) -> bool:
        now = utc_now()
        with self.engine.begin() as db:
            result = db.execute(update(jobs).where(
                jobs.c.id == job_id, jobs.c.status == "running", jobs.c.lease_owner == worker_id
            ).values(heartbeat_at=now, lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now))
            return result.rowcount == 1

    def finish_job(self, job_id: str, worker_id: str, result: dict | None = None) -> bool:
        now = utc_now()
        with self.engine.begin() as db:
            changed = db.execute(update(jobs).where(
                jobs.c.id == job_id, jobs.c.status == "running", jobs.c.lease_owner == worker_id
            ).values(status="completed", result=result, completed_at=now, updated_at=now, lease_owner=None, lease_expires_at=None))
            return changed.rowcount == 1

    def fail_job(self, job_id: str, worker_id: str, error: str, retry_delay: float | None = None) -> bool:
        now = utc_now()
        with self.engine.begin() as db:
            row = db.execute(select(jobs).where(jobs.c.id == job_id).with_for_update()).mappings().one_or_none()
            if not row or row["lease_owner"] != worker_id:
                return False
            retry = retry_delay is not None and row["attempts"] < row["max_attempts"]
            db.execute(update(jobs).where(jobs.c.id == job_id).values(
                status="queued" if retry else "failed",
                available_at=now + timedelta(seconds=retry_delay or 0),
                last_error=error[:4000], updated_at=now, completed_at=None if retry else now,
                lease_owner=None, lease_expires_at=None,
            ))
            return True

    def requeue_expired_jobs(self) -> int:
        now = utc_now()
        with self.engine.begin() as db:
            result = db.execute(update(jobs).where(
                jobs.c.status == "running", jobs.c.lease_expires_at < now
            ).values(status="queued", available_at=now, lease_owner=None, lease_expires_at=None, updated_at=now))
            return result.rowcount
