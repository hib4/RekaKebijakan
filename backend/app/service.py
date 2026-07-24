from __future__ import annotations

import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from . import engine
from .documents import extract_text
from .repository import Repository

STAGES = ("graph", "environment", "simulation", "report", "interaction")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class WorkflowService:
    def __init__(self, repository: Repository, upload_dir: Path, delay: float):
        self.repository = repository
        self.upload_dir = upload_dir
        self.delay = delay
        self.threads: dict[str, threading.Thread] = {}
        self.job_simulations: dict[str, str] = {}

    def create_project(self, project: dict, files: list[FileStorage]) -> dict:
        if not files or not any(upload.filename for upload in files):
            raise ValueError("Minimal satu dokumen kebijakan diperlukan")
        project_id, simulation_id = identifier("project"), identifier("sim")
        timestamp = now()
        state = {"id": simulation_id, "simulation_id": simulation_id, "status": "ready", "current_stage": "graph", "project": {"id": project_id, "name": project["project_name"], "project_name": project["project_name"], "institution": project["institution"], "objective": project["objective"], "question": project["objective"]}, "stages": {}, "graph": {}, "environment": {}, "simulation": {"events": [], "event_count": 0, "speed": 1}, "report": {"sections": [], "risks": []}, "interaction": {}, "interactions": {"messages": []}, "logs": [], "updated_at": timestamp}
        for index, stage in enumerate(STAGES):
            state["stages"][stage] = {"status": "ready" if index == 0 else "locked", "progress": 0, "active_task": None}
        self._sync_stages(state)
        target_dir = self.upload_dir / simulation_id
        target_dir.mkdir(parents=True, exist_ok=True)
        documents = []
        try:
            for upload in files:
                if not upload.filename:
                    continue
                document_id = identifier("doc")
                filename = secure_filename(upload.filename)
                path = target_dir / f"{document_id}_{filename}"
                upload.save(path)
                text = extract_text(path)
                documents.append({"id": document_id, "simulation_id": simulation_id, "name": filename, "path": str(path), "text": text})
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise
        self.repository.create(state)
        for document in documents:
            self.repository.add_document(document)
        return state

    def start(self, simulation_id: str, stage: str, config: dict | None = None) -> dict | None:
        state = self.repository.get(simulation_id)
        if not state or stage not in STAGES[:4]:
            return None
        if stage != "graph" and state["stages"][stage]["status"] == "locked":
            raise ValueError("Tahap sebelumnya belum selesai")
        if state["stages"][stage]["status"] in {"queued", "running", "paused"}:
            raise ValueError("Tahap sedang diproses")
        job_id = identifier("job")
        config = config or {}
        self.repository.put_job(job_id, simulation_id, stage, "queued", config)

        def queued(current):
            metadata = current["stages"][stage]
            metadata.update(status="queued", progress=0, active_task=f"Menyiapkan {stage}", started_at=now())
            current["status"] = "processing"
            current["current_stage"] = stage
            self._touch(current, f"Tahap {stage} masuk antrean")
            self._sync_stages(current)

        state = self.repository.mutate(simulation_id, queued)
        self._spawn(job_id, simulation_id, stage, config)
        return state

    def _spawn(self, job_id: str, simulation_id: str, stage: str, config: dict):
        thread = threading.Thread(target=self._run, args=(job_id, simulation_id, stage, config), daemon=True, name=job_id)
        self.threads[job_id] = thread
        self.job_simulations[job_id] = simulation_id
        thread.start()

    def _run(self, job_id: str, simulation_id: str, stage: str, config: dict):
        try:
            self.repository.claim_job(job_id)
            for progress in (15, 40, 70):
                while self.repository.job_status(job_id) == "paused":
                    time.sleep(max(self.delay, 0.01))
                if self.repository.job_status(job_id) == "cancelled":
                    return
                self.repository.mutate(simulation_id, lambda state, p=progress: self._progress(state, stage, p))
                if self.delay:
                    time.sleep(self.delay)
            state = self.repository.get(simulation_id)
            documents = self.repository.documents(simulation_id)
            if stage == "graph":
                result = engine.graph(simulation_id, state["project"]["name"], [doc["name"] for doc in documents])
            elif stage == "environment":
                from .models import EnvironmentInput
                result = engine.environment(simulation_id, EnvironmentInput.model_validate(config).model_dump())
            elif stage == "simulation":
                result = {"events": engine.events(simulation_id, state["environment"]["config"]["rounds"])}
                result["event_count"] = len(result["events"])
            else:
                result = engine.report(state["project"]["name"], state["simulation"]["events"], documents)
            self.repository.mutate(simulation_id, lambda current: self._complete(current, stage, result))
            self.repository.set_job_status(job_id, "completed")
        except Exception as error:
            self.repository.set_job_status(job_id, "failed")
            self.repository.mutate(simulation_id, lambda state: self._fail(state, stage, str(error)))
        finally:
            self.threads.pop(job_id, None)
            self.job_simulations.pop(job_id, None)

    def _progress(self, state: dict, stage: str, progress: int):
        state["stages"][stage].update(status="running", progress=progress, active_task=f"Memproses {stage}: {progress}%")
        self._touch(state)
        self._sync_stages(state)

    def _complete(self, state: dict, stage: str, result: dict):
        state[stage].update(result)
        state["stages"][stage].update(status="completed", progress=100, active_task=None, completed_at=now())
        next_index = STAGES.index(stage) + 1
        if next_index < len(STAGES):
            state["stages"][STAGES[next_index]]["status"] = "ready"
            state["current_stage"] = STAGES[next_index]
        state["status"] = "completed" if stage == "report" else "ready"
        self._touch(state, f"Tahap {stage} selesai", "DONE")
        self._sync_stages(state)

    def _fail(self, state: dict, stage: str, message: str):
        state["stages"][stage].update(status="failed", active_task=None, error=message)
        state["status"] = "failed"
        self._touch(state, f"Tahap {stage} gagal: {message}", "WARN")
        self._sync_stages(state)

    def control(self, simulation_id: str, action: str) -> dict | None:
        state = self.repository.get(simulation_id)
        if not state:
            return None
        jobs = [job_id for job_id, owner in self.job_simulations.items() if owner == simulation_id]
        if not jobs or state["current_stage"] != "simulation" or state["stages"]["simulation"]["status"] not in {"queued", "running", "paused"}:
            raise ValueError("Tidak ada simulasi aktif")
        # Only one progressive job is allowed per simulation by the API workflow.
        for job_id in jobs:
            status = self.repository.job_status(job_id)
            if status in ("running", "queued", "paused"):
                self.repository.set_job_status(job_id, {"pause": "paused", "resume": "running", "cancel": "cancelled"}[action])
        def update(current):
            stage = current["current_stage"]
            value = {"pause": "paused", "resume": "running", "cancel": "cancelled"}[action]
            current["stages"][stage]["status"] = value
            current["status"] = value
            self._touch(current, f"Simulasi {action}")
            self._sync_stages(current)
        return self.repository.mutate(simulation_id, update)

    def interact(self, simulation_id: str, payload: dict) -> dict | None:
        state = self.repository.get(simulation_id)
        if not state:
            return None
        response = engine.answer(payload["tool"], payload["question"], payload.get("persona_group"), state)
        user = {"id": identifier("msg"), "role": "user", "author": "Anda", "tool": payload["tool"], "text": payload["question"], "citations": []}
        assistant = {"id": identifier("msg"), "role": "assistant", "author": "Report Agent", "tool": payload["tool"], **response}
        def update(current):
            current["interactions"]["messages"].extend([user, assistant])
            current["stages"]["interaction"].update(status="completed", progress=100)
            self._touch(current, "Interaksi dijawab", "DONE")
            self._sync_stages(current)
        self.repository.mutate(simulation_id, update)
        return assistant

    def recover(self):
        for job in self.repository.recoverable_jobs():
            self._spawn(job["id"], job["simulation_id"], job["stage"], job["config"])

    @staticmethod
    def _sync_stages(state: dict):
        for stage in STAGES:
            state[stage].update(state["stages"][stage])

    @staticmethod
    def _touch(state: dict, message: str | None = None, level: str = "INFO"):
        state["updated_at"] = now()
        if message:
            state["logs"].append({"id": identifier("log"), "time": state["updated_at"], "level": level, "message": message})
