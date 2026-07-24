from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import and_, create_engine, delete, func, insert, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine

from .database import audit_events, citations, document_chunks, document_pages, documents, job_attempts, jobs, projects, scenarios, sessions, simulations, users
from .errors import UploadQuotaExceeded


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class Repository:
    def __init__(self, database_url: str, engine: Engine | None = None, project_retention_days: int = 30):
        self.database_url = database_url
        self.engine = engine or create_engine(database_url, pool_pre_ping=True)
        self.lock = threading.RLock()
        self.project_retention_days = project_retention_days

    def close(self) -> None:
        self.engine.dispose()

    def ping(self) -> None:
        with self.engine.connect() as db:
            db.execute(text("SELECT 1"))

    def schema_revision(self) -> str:
        with self.engine.connect() as db:
            return str(db.execute(text("SELECT version_num FROM alembic_version")).scalar_one())

    def operational_metrics(self) -> dict[str, int | float]:
        current = utc_now()
        with self.engine.connect() as db:
            counts = dict(db.execute(select(jobs.c.status, func.count()).group_by(jobs.c.status)).all())
            oldest = db.execute(select(func.min(jobs.c.created_at)).where(jobs.c.status == "queued")).scalar_one()
        counts["oldest_queued_age_seconds"] = max(0.0, (current - oldest).total_seconds()) if oldest else 0.0
        return counts

    def create(self, state: dict, owner_user_id: str | None = None) -> dict:
        with self.lock, self.engine.begin() as db:
            if owner_user_id:
                project = state["project"]
                db.execute(insert(projects).values(
                    id=project["id"], owner_user_id=owner_user_id, name=project.get("name") or project["project_name"],
                    institution=project["institution"], objective=project["objective"], status="active",
                    version=state.get("revision", 1), created_at=parse_timestamp(state["updated_at"]),
                    updated_at=parse_timestamp(state["updated_at"]),
                ))
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

    def create_project_bundle(
        self,
        state: dict,
        owner_user_id: str,
        document_values: list[tuple[dict, list[dict], list[dict]]],
        max_active_projects: int,
        max_files_per_project: int,
        max_total_upload_bytes: int,
    ) -> dict:
        """Create all metadata atomically while serializing quota checks per user."""
        if len(document_values) > max_files_per_project:
            raise UploadQuotaExceeded("Jumlah berkas per proyek melebihi batas")
        incoming_bytes = sum(int(document.get("size_bytes") or 0) for document, _, _ in document_values)
        with self.lock, self.engine.begin() as db:
            if db.execute(select(users.c.id).where(users.c.id == owner_user_id).with_for_update()).scalar_one_or_none() is None:
                raise ValueError("Pemilik proyek tidak ditemukan")
            active_count = db.execute(select(func.count()).select_from(projects).where(
                projects.c.owner_user_id == owner_user_id,
                projects.c.status == "active",
                projects.c.deleted_at.is_(None),
            )).scalar_one()
            if active_count >= max_active_projects:
                raise UploadQuotaExceeded("Batas proyek aktif pengguna telah tercapai")
            used_bytes = db.execute(
                select(func.coalesce(func.sum(documents.c.size_bytes), 0))
                .select_from(documents.join(simulations).join(projects, projects.c.id == simulations.c.project_id))
                .where(projects.c.owner_user_id == owner_user_id, projects.c.deleted_at.is_(None))
            ).scalar_one()
            if used_bytes + incoming_bytes > max_total_upload_bytes:
                raise UploadQuotaExceeded("Kuota penyimpanan pengguna telah terlampaui")

            project = state["project"]
            timestamp = parse_timestamp(state["updated_at"])
            db.execute(insert(projects).values(
                id=project["id"], owner_user_id=owner_user_id,
                name=project.get("name") or project["project_name"], institution=project["institution"],
                objective=project["objective"], status="active", version=state.get("revision", 1),
                created_at=timestamp, updated_at=timestamp,
            ))
            db.execute(insert(simulations).values(
                id=state["id"], project_id=project["id"], state=state,
                updated_at=timestamp, owner_user_id=owner_user_id,
            ))
            for document, chunks, pages in document_values:
                db.execute(insert(documents).values(**(document | {"created_at": document.get("created_at", timestamp)})))
                if chunks:
                    db.execute(insert(document_chunks), [item | {"simulation_id": state["id"]} for item in chunks])
                if pages:
                    rows = []
                    for item in pages:
                        key = f"{document['id']}:{item['page_number']}"
                        rows.append({
                            "id": f"page_{hashlib.sha256(key.encode()).hexdigest()[:16]}",
                            "simulation_id": state["id"], "document_id": document["id"], **item,
                        })
                    db.execute(insert(document_pages), rows)
            self._audit(db, owner_user_id, project["id"], "project.created", "project", project["id"], {
                "file_count": len(document_values), "size_bytes": incoming_bytes,
            })
        return state

    def project(self, project_id: str, user_id: str, include_archived: bool = True) -> dict | None:
        with self.engine.connect() as db:
            scenario_count = select(func.count()).where(
                scenarios.c.project_id == projects.c.id, scenarios.c.archived_at.is_(None)
            ).correlate(projects).scalar_subquery()
            statement = (
                select(projects, simulations.c.id.label("simulation_id"), simulations.c.state, scenario_count.label("scenario_count"))
                .join(simulations, simulations.c.project_id == projects.c.id)
                .where(projects.c.id == project_id, projects.c.owner_user_id == user_id, projects.c.deleted_at.is_(None))
            )
            if not include_archived:
                statement = statement.where(projects.c.status == "active")
            row = db.execute(statement.order_by(simulations.c.updated_at.desc()).limit(1)).mappings().one_or_none()
            return dict(row) if row else None

    def list_projects(
        self, user_id: str, query: str = "", status: str | None = "active", limit: int = 50, offset: int = 0
    ) -> dict:
        with self.engine.connect() as db:
            conditions = [projects.c.owner_user_id == user_id, projects.c.deleted_at.is_(None)]
            if status and status != "all":
                conditions.append(projects.c.status == status)
            if query:
                pattern = f"%{query.strip()}%"
                conditions.append(or_(projects.c.name.ilike(pattern), projects.c.institution.ilike(pattern)))
            base = projects.join(simulations, simulations.c.project_id == projects.c.id)
            scenario_count = select(func.count()).where(
                scenarios.c.project_id == projects.c.id, scenarios.c.archived_at.is_(None)
            ).correlate(projects).scalar_subquery()
            total = db.execute(select(func.count(func.distinct(projects.c.id))).select_from(base).where(*conditions)).scalar_one()
            statement = (
                select(projects, simulations.c.id.label("simulation_id"), simulations.c.state, scenario_count.label("scenario_count"))
                .select_from(base)
                .where(*conditions)
                .order_by(projects.c.updated_at.desc())
                .limit(max(1, min(limit, 100)))
                .offset(max(0, offset))
            )
            rows = [dict(row) for row in db.execute(statement).mappings()]
            return {"items": rows, "total": total, "limit": max(1, min(limit, 100)), "offset": max(0, offset)}

    def dashboard_projects(self, user_id: str) -> list[dict]:
        with self.engine.connect() as db:
            scenario_count = select(func.count()).where(
                scenarios.c.project_id == projects.c.id, scenarios.c.archived_at.is_(None)
            ).correlate(projects).scalar_subquery()
            rows = db.execute(select(
                projects, simulations.c.id.label("simulation_id"), simulations.c.state,
                scenario_count.label("scenario_count"),
            ).select_from(projects.join(simulations, simulations.c.project_id == projects.c.id)).where(
                projects.c.owner_user_id == user_id, projects.c.status == "active", projects.c.deleted_at.is_(None),
            ).order_by(projects.c.updated_at.desc())).mappings()
            return [dict(row) for row in rows]

    def update_project(self, project_id: str, user_id: str, expected_version: int, values: dict) -> dict | None:
        now = utc_now()
        allowed = {key: value for key, value in values.items() if key in {"name", "institution", "objective"}}
        with self.engine.begin() as db:
            result = db.execute(update(projects).where(
                projects.c.id == project_id, projects.c.owner_user_id == user_id,
                projects.c.version == expected_version, projects.c.status == "active", projects.c.deleted_at.is_(None),
            ).values(**allowed, version=projects.c.version + 1, updated_at=now).returning(projects))
            row = result.mappings().one_or_none()
            if not row:
                return None
            simulation = db.execute(select(simulations.c.id, simulations.c.state).where(
                simulations.c.project_id == project_id
            ).order_by(simulations.c.updated_at.desc()).with_for_update().limit(1)).mappings().one()
            state = simulation["state"]
            state["project"].update({
                "name": allowed.get("name", state["project"].get("name")),
                "project_name": allowed.get("name", state["project"].get("project_name")),
                "institution": allowed.get("institution", state["project"].get("institution")),
                "objective": allowed.get("objective", state["project"].get("objective")),
                "question": allowed.get("objective", state["project"].get("question")),
            })
            state["revision"] = row["version"]
            state["updated_at"] = now.isoformat()
            db.execute(update(simulations).where(simulations.c.id == simulation["id"]).values(state=state, updated_at=now))
            self._audit(db, user_id, project_id, "project.updated", "project", project_id, allowed)
            return dict(row)

    def set_project_status(self, project_id: str, user_id: str, status: str) -> dict | None:
        now = utc_now()
        values = {"status": status, "updated_at": now, "version": projects.c.version + 1}
        if status == "archived":
            values["archived_at"] = now
        elif status == "active":
            values["archived_at"] = None
            values["delete_after"] = None
        elif status == "pending_delete":
            values["delete_after"] = now + timedelta(days=self.project_retention_days)
        with self.engine.begin() as db:
            active = db.execute(select(func.count()).select_from(jobs.join(simulations)).where(
                simulations.c.project_id == project_id, jobs.c.status.in_(("queued", "running", "paused"))
            )).scalar_one()
            if active:
                raise ValueError("Project has an active job")
            source_statuses = {
                "active": ("archived", "pending_delete"),
                "archived": ("active",),
                "pending_delete": ("active", "archived"),
            }.get(status, ())
            row = db.execute(update(projects).where(
                projects.c.id == project_id, projects.c.owner_user_id == user_id, projects.c.deleted_at.is_(None),
                projects.c.status.in_(source_statuses),
            ).values(**values).returning(projects)).mappings().one_or_none()
            if row:
                self._audit(db, user_id, project_id, f"project.{status}", "project", project_id, {})
            return dict(row) if row else None

    def create_scenario(self, project_id: str, user_id: str, values: dict) -> dict | None:
        timestamp = utc_now()
        scenario_id = values.get("id") or f"scenario_{uuid.uuid4().hex[:16]}"
        with self.engine.begin() as db:
            owned = db.execute(select(projects.c.id, simulations.c.state).select_from(
                projects.join(simulations, simulations.c.project_id == projects.c.id)
            ).where(
                projects.c.id == project_id, projects.c.owner_user_id == user_id, projects.c.status == "active"
            )).mappings().one_or_none()
            if not owned:
                return None
            environment_revision = owned["state"].get("environment", {}).get("config", {}).get("version", 0)
            row = db.execute(insert(scenarios).values(
                id=scenario_id, project_id=project_id, name=values["name"], description=values.get("description", ""),
                kind=values.get("kind", "custom"), config=values.get("config", {}), persona_overrides={},
                base_environment_revision=environment_revision, version=1,
                created_at=timestamp, updated_at=timestamp,
            ).returning(scenarios)).mappings().one()
            self._audit(db, user_id, project_id, "scenario.created", "scenario", scenario_id, {})
            return dict(row)

    def list_scenarios(self, project_id: str, user_id: str) -> list[dict] | None:
        with self.engine.connect() as db:
            owned = db.execute(select(projects.c.id).where(
                projects.c.id == project_id, projects.c.owner_user_id == user_id, projects.c.deleted_at.is_(None)
            )).scalar_one_or_none()
            if not owned:
                return None
            return [dict(row) for row in db.execute(select(scenarios).where(
                scenarios.c.project_id == project_id, scenarios.c.archived_at.is_(None)
            ).order_by(scenarios.c.updated_at.desc())).mappings()]

    def scenario(self, project_id: str, scenario_id: str, user_id: str) -> dict | None:
        with self.engine.connect() as db:
            row = db.execute(select(scenarios).select_from(
                scenarios.join(projects, projects.c.id == scenarios.c.project_id)
            ).where(
                scenarios.c.id == scenario_id, scenarios.c.project_id == project_id,
                projects.c.owner_user_id == user_id, projects.c.deleted_at.is_(None),
            )).mappings().one_or_none()
            return dict(row) if row else None

    def update_scenario(
        self, project_id: str, scenario_id: str, user_id: str, expected_version: int, values: dict
    ) -> dict | None:
        allowed = {key: value for key, value in values.items() if key in {"name", "description", "kind", "config"}}
        with self.engine.begin() as db:
            row = db.execute(update(scenarios).where(
                scenarios.c.id == scenario_id,
                scenarios.c.project_id == project_id,
                scenarios.c.version == expected_version,
                scenarios.c.archived_at.is_(None),
                scenarios.c.project_id.in_(select(projects.c.id).where(
                    projects.c.owner_user_id == user_id, projects.c.status == "active"
                )),
            ).values(**allowed, version=scenarios.c.version + 1, updated_at=utc_now()).returning(scenarios)).mappings().one_or_none()
            if row:
                self._audit(db, user_id, project_id, "scenario.updated", "scenario", scenario_id, allowed)
            return dict(row) if row else None

    def set_scenario_archived(
        self, project_id: str, scenario_id: str, user_id: str, archived: bool
    ) -> dict | None:
        with self.engine.begin() as db:
            condition = scenarios.c.archived_at.is_(None) if archived else scenarios.c.archived_at.is_not(None)
            row = db.execute(update(scenarios).where(
                scenarios.c.id == scenario_id, scenarios.c.project_id == project_id, condition,
                scenarios.c.project_id.in_(select(projects.c.id).where(
                    projects.c.owner_user_id == user_id, projects.c.status == "active"
                )),
            ).values(
                archived_at=utc_now() if archived else None,
                version=scenarios.c.version + 1,
                updated_at=utc_now(),
            ).returning(scenarios)).mappings().one_or_none()
            if row:
                action = "scenario.archived" if archived else "scenario.restored"
                self._audit(db, user_id, project_id, action, "scenario", scenario_id, {})
            return dict(row) if row else None

    def delete_scenario(self, project_id: str, scenario_id: str, user_id: str) -> bool:
        with self.engine.begin() as db:
            removed = db.execute(delete(scenarios).where(
                scenarios.c.id == scenario_id, scenarios.c.project_id == project_id,
                scenarios.c.project_id.in_(select(projects.c.id).where(
                    projects.c.owner_user_id == user_id, projects.c.status == "active"
                )),
            ))
            if removed.rowcount:
                self._audit(db, user_id, project_id, "scenario.deleted", "scenario", scenario_id, {})
            return removed.rowcount == 1

    @staticmethod
    def _environment_revision(state: dict) -> int:
        return int(state.get("environment", {}).get("config", {}).get("version", 0))

    def put_persona_override(
        self, project_id: str, scenario_id: str, persona_id: str, user_id: str,
        expected_version: int, base_environment_revision: int, patch: dict | None,
    ) -> dict | None:
        with self.engine.begin() as db:
            row = db.execute(select(scenarios, simulations.c.state).select_from(
                scenarios.join(projects, projects.c.id == scenarios.c.project_id).join(
                    simulations, simulations.c.project_id == projects.c.id
                )
            ).where(
                scenarios.c.id == scenario_id, scenarios.c.project_id == project_id,
                scenarios.c.version == expected_version, scenarios.c.archived_at.is_(None),
                projects.c.owner_user_id == user_id, projects.c.status == "active",
            ).with_for_update(of=scenarios)).mappings().one_or_none()
            if not row:
                return None
            current_revision = self._environment_revision(row["state"])
            if current_revision != base_environment_revision:
                raise ValueError("Environment revision conflict")
            personas = row["state"].get("environment", {}).get("personas", [])
            if not any(persona.get("id") == persona_id for persona in personas):
                raise KeyError(persona_id)
            overrides = dict(row["persona_overrides"] or {})
            if patch is None:
                overrides.pop(persona_id, None)
                action = "persona_override.deleted"
            else:
                overrides[persona_id] = patch
                action = "persona_override.updated"
            updated = db.execute(update(scenarios).where(
                scenarios.c.id == scenario_id, scenarios.c.version == expected_version
            ).values(
                persona_overrides=overrides,
                base_environment_revision=current_revision,
                version=scenarios.c.version + 1,
                updated_at=utc_now(),
            ).returning(scenarios)).mappings().one()
            self._audit(db, user_id, project_id, action, "persona", persona_id, {"scenario_id": scenario_id})
            return dict(updated)

    def effective_personas(self, project_id: str, scenario_id: str, user_id: str) -> list[dict] | None:
        with self.engine.connect() as db:
            row = db.execute(select(scenarios.c.persona_overrides, simulations.c.state).select_from(
                scenarios.join(projects, projects.c.id == scenarios.c.project_id).join(
                    simulations, simulations.c.project_id == projects.c.id
                )
            ).where(
                scenarios.c.id == scenario_id, scenarios.c.project_id == project_id,
                projects.c.owner_user_id == user_id, projects.c.deleted_at.is_(None),
            )).mappings().one_or_none()
            if not row:
                return None
            overrides = row["persona_overrides"] or {}
            return [dict(persona) | overrides.get(persona.get("id"), {}) for persona in row["state"].get("environment", {}).get("personas", [])]

    def apply_scenario(self, project_id: str, scenario_id: str, user_id: str) -> str | None:
        with self.engine.begin() as db:
            row = db.execute(select(scenarios, simulations.c.id.label("simulation_id"), simulations.c.state).select_from(
                scenarios.join(projects, projects.c.id == scenarios.c.project_id).join(
                    simulations, simulations.c.project_id == projects.c.id
                )
            ).where(
                scenarios.c.id == scenario_id, scenarios.c.project_id == project_id,
                scenarios.c.archived_at.is_(None), projects.c.owner_user_id == user_id,
                projects.c.status == "active",
            ).with_for_update(of=simulations)).mappings().one_or_none()
            if not row:
                return None
            state = row["state"]
            environment = state.get("environment", {})
            personas = environment.get("personas", [])
            if not personas:
                raise ValueError("Environment must be generated before applying a scenario")
            current_revision = self._environment_revision(state)
            overrides = row["persona_overrides"] or {}
            if overrides and row["base_environment_revision"] != current_revision:
                raise ValueError("Environment revision conflict")
            environment["personas"] = [
                dict(persona) | overrides.get(persona.get("id"), {}) for persona in personas
            ]
            environment["persona_count"] = sum(
                int(persona.get("count", 1)) for persona in environment["personas"] if persona.get("active", True)
            )
            environment["config"] = dict(environment.get("config", {})) | dict(row["config"] or {})
            state["environment"] = environment
            state["revision"] = int(state.get("revision", 1)) + 1
            state["updated_at"] = utc_now().isoformat()
            db.execute(update(simulations).where(simulations.c.id == row["simulation_id"]).values(
                state=state, updated_at=parse_timestamp(state["updated_at"])
            ))
            self._audit(db, user_id, project_id, "scenario.applied", "scenario", scenario_id, {})
            return row["simulation_id"]

    @staticmethod
    def _audit(db, user_id: str | None, project_id: str | None, action: str, resource_type: str, resource_id: str, metadata: dict) -> None:
        db.execute(insert(audit_events).values(
            id=f"audit_{uuid.uuid4().hex[:16]}", actor_user_id=user_id, project_id=project_id,
            action=action, resource_type=resource_type, resource_id=resource_id, metadata=metadata, created_at=utc_now(),
        ))

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
            statement = select(simulations.c.state).select_from(
                simulations.outerjoin(projects, projects.c.id == simulations.c.project_id)
            ).where(
                simulations.c.id == simulation_id,
                or_(projects.c.id.is_(None), and_(projects.c.status == "active", projects.c.deleted_at.is_(None))),
            )
            if user_id is not None:
                statement = statement.where(simulations.c.owner_user_id == user_id)
            state = db.execute(statement.with_for_update(of=simulations)).scalar_one_or_none()
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
            values = document | {"created_at": document.get("created_at", utc_now())}
            db.execute(insert(documents).values(**values))
            if chunks:
                db.execute(insert(document_chunks), [item | {"simulation_id": document["simulation_id"]} for item in chunks])

    def add_document_pages(self, simulation_id: str, document_id: str, pages: list[dict]) -> None:
        if not pages:
            return
        with self.engine.begin() as db:
            values = []
            for item in pages:
                key = f"{document_id}:{item['page_number']}"
                values.append({
                    "id": f"page_{hashlib.sha256(key.encode()).hexdigest()[:16]}",
                    "simulation_id": simulation_id,
                    "document_id": document_id,
                    **item,
                })
            db.execute(insert(document_pages), values)

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

    def search_chunks(self, simulation_id: str, query: str, limit: int = 5) -> list[dict]:
        with self.engine.connect() as db:
            search_query = func.websearch_to_tsquery("simple", query)
            rank = func.ts_rank_cd(document_chunks.c.search_vector, search_query).label("relevance_score")
            statement = (
                select(document_chunks, rank)
                .where(document_chunks.c.simulation_id == simulation_id, document_chunks.c.search_vector.op("@@")(search_query))
                .order_by(rank.desc(), document_chunks.c.document_id, document_chunks.c.ordinal)
                .limit(limit)
            )
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
                mutable = db.execute(select(simulations.c.id).select_from(
                    simulations.outerjoin(projects, projects.c.id == simulations.c.project_id)
                ).where(
                    simulations.c.id == simulation_id,
                    or_(projects.c.id.is_(None), projects.c.status == "active"),
                ).with_for_update(of=simulations)).scalar_one_or_none()
                if mutable is None:
                    return False
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

    def purge_due_projects(self, delete_object: Callable[[str], None], limit: int = 100) -> int:
        """Delete objects before metadata; partial object deletion is safe to retry."""
        now = utc_now()
        with self.engine.connect() as db:
            due_ids = list(db.execute(select(projects.c.id).where(
                projects.c.status == "pending_delete", projects.c.delete_after <= now,
                projects.c.deleted_at.is_(None),
            ).order_by(projects.c.delete_after).limit(limit)).scalars())
        purged = 0
        for project_id in due_ids:
            with self.engine.begin() as db:
                locked = db.execute(select(projects.c.id).where(
                    projects.c.id == project_id, projects.c.status == "pending_delete",
                    projects.c.delete_after <= now, projects.c.deleted_at.is_(None),
                ).with_for_update()).scalar_one_or_none()
                if locked is None:
                    continue
                simulation_ids = select(simulations.c.id).where(simulations.c.project_id == project_id)
                paths = list(db.execute(select(documents.c.path).where(
                    documents.c.simulation_id.in_(simulation_ids)
                )).scalars())
                for path in paths:
                    delete_object(path)
                db.execute(delete(simulations).where(simulations.c.project_id == project_id))
                db.execute(delete(projects).where(projects.c.id == project_id))
                purged += 1
        return purged

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
            token = uuid.uuid4().hex
            generation = row["lease_generation"] + 1
            attempt = row["attempts"] + 1
            db.execute(update(jobs).where(jobs.c.id == row["id"]).values(
                status="running",
                lease_owner=worker_id,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                heartbeat_at=now,
                execution_token=token,
                lease_generation=generation,
                started_at=row["started_at"] or now,
                updated_at=now,
                attempts=attempt,
            ))
            db.execute(insert(job_attempts).values(
                id=f"attempt_{uuid.uuid4().hex[:16]}", job_id=row["id"], attempt=attempt,
                worker_id=worker_id, execution_token=token, started_at=now, heartbeat_at=now,
            ))
            return dict(row) | {
                "status": "running", "lease_owner": worker_id, "attempts": attempt,
                "execution_token": token, "lease_generation": generation,
            }

    def renew_job_lease(self, job_id: str, worker_id: str, execution_token: str | None = None, lease_seconds: int = 60) -> bool:
        now = utc_now()
        with self.engine.begin() as db:
            condition = and_(jobs.c.id == job_id, jobs.c.status == "running", jobs.c.lease_owner == worker_id)
            if execution_token:
                condition = and_(condition, jobs.c.execution_token == execution_token)
            result = db.execute(update(jobs).where(condition).values(
                heartbeat_at=now, lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now
            ))
            attempt_condition = and_(job_attempts.c.job_id == job_id, job_attempts.c.worker_id == worker_id, job_attempts.c.completed_at.is_(None))
            if execution_token:
                attempt_condition = and_(attempt_condition, job_attempts.c.execution_token == execution_token)
            db.execute(update(job_attempts).where(
                attempt_condition
            ).values(heartbeat_at=now))
            return result.rowcount == 1

    def finish_job(self, job_id: str, worker_id: str, execution_token: str | None = None, result: dict | None = None) -> bool:
        now = utc_now()
        with self.engine.begin() as db:
            condition = and_(jobs.c.id == job_id, jobs.c.status == "running", jobs.c.lease_owner == worker_id)
            if execution_token:
                condition = and_(condition, jobs.c.execution_token == execution_token)
            changed = db.execute(update(jobs).where(condition).values(
                status="completed", result=result, completed_at=now, updated_at=now, lease_owner=None, lease_expires_at=None
            ))
            if changed.rowcount:
                attempt_condition = and_(job_attempts.c.job_id == job_id, job_attempts.c.worker_id == worker_id, job_attempts.c.completed_at.is_(None))
                if execution_token:
                    attempt_condition = and_(attempt_condition, job_attempts.c.execution_token == execution_token)
                db.execute(update(job_attempts).where(attempt_condition).values(completed_at=now, outcome="completed"))
            return changed.rowcount == 1

    def fail_job(self, job_id: str, worker_id: str, execution_token: str, error: str, retry_delay: float | None = None, error_code: str = "worker_error") -> bool:
        now = utc_now()
        with self.engine.begin() as db:
            row = db.execute(select(jobs).where(jobs.c.id == job_id).with_for_update()).mappings().one_or_none()
            if not row or row["lease_owner"] != worker_id or row["execution_token"] != execution_token:
                return False
            retry = retry_delay is not None and row["attempts"] < row["max_attempts"]
            db.execute(update(jobs).where(jobs.c.id == job_id).values(
                status="queued" if retry else "failed",
                available_at=now + timedelta(seconds=retry_delay or 0),
                last_error=error[:4000], error_code=error_code, error_class="retryable" if retry else "terminal",
                retryable="true" if retry else "false", next_retry_at=now + timedelta(seconds=retry_delay or 0) if retry else None,
                updated_at=now, completed_at=None if retry else now, dead_lettered_at=None if retry else now,
                lease_owner=None, lease_expires_at=None,
            ))
            db.execute(update(job_attempts).where(
                job_attempts.c.job_id == job_id, job_attempts.c.execution_token == execution_token
            ).values(completed_at=now, outcome="retry" if retry else "failed", error_code=error_code, error_message=error[:4000]))
            return True

    def job_control_state(self, job_id: str, execution_token: str) -> str | None:
        with self.engine.connect() as db:
            return db.execute(select(jobs.c.status).where(
                jobs.c.id == job_id, jobs.c.execution_token == execution_token
            )).scalar_one_or_none()

    def requeue_expired_jobs(self) -> int:
        now = utc_now()
        with self.engine.begin() as db:
            result = db.execute(update(jobs).where(
                jobs.c.status == "running", jobs.c.lease_expires_at < now
            ).values(status="queued", available_at=now, lease_owner=None, lease_expires_at=None, updated_at=now))
            return result.rowcount
