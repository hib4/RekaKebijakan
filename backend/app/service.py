from __future__ import annotations

import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename

from .documents import chunk_text, extract_text
from .providers import PolicyProvider
from .repository import Repository


STAGES = ("graph", "environment", "simulation", "report", "interaction")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def upgrade_state(state: dict) -> dict:
    state.setdefault("schema_version", 2)
    state.setdefault("revision", 1)
    state.setdefault("ontology", {"status": "ready", "version": 0, "entity_types": [], "relation_types": [], "analysis_summary": "", "citations": []})
    state.setdefault("interviews", {"items": []})
    state.setdefault("graph_feedback", {"items": []})
    state.setdefault("provider", {})
    state.setdefault("stages", {})
    for index, stage in enumerate(STAGES):
        state["stages"].setdefault(stage, {"status": "ready" if index == 0 else "locked", "progress": 0, "active_task": None})
        state.setdefault(stage, {})
    return state


class WorkflowService:
    def __init__(
        self,
        repository: Repository,
        provider: PolicyProvider,
        upload_dir: Path,
        delay: float,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        embedded_worker: bool = False,
        lease_seconds: int = 180,
    ):
        self.repository = repository
        self.provider = provider
        self.upload_dir = upload_dir
        self.delay = delay
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedded_worker = embedded_worker
        self.lease_seconds = lease_seconds
        self.worker_id = f"worker_{uuid.uuid4().hex[:12]}"
        self.threads: dict[str, threading.Thread] = {}
        self.thread_lock = threading.RLock()
        self.stopping = threading.Event()

    def create_project(self, project: dict, files: list, owner_user_id: str | None = None) -> dict:
        if not files or not any(upload.filename for upload in files):
            raise ValueError("Minimal satu dokumen kebijakan diperlukan")
        project_id, simulation_id = identifier("project"), identifier("sim")
        timestamp = now()
        state = upgrade_state({
            "id": simulation_id,
            "simulation_id": simulation_id,
            "status": "ready",
            "current_stage": "graph",
            "project": {
                "id": project_id, "name": project["project_name"], "project_name": project["project_name"],
                "institution": project["institution"], "objective": project["objective"], "question": project["objective"],
            },
            "stages": {}, "graph": {"revision": 0, "nodes": [], "edges": []}, "environment": {},
            "simulation": {"events": [], "event_count": 0, "speed": 1},
            "report": {"sections": [], "risks": []}, "interaction": {}, "interactions": {"messages": []},
            "logs": [], "updated_at": timestamp,
            "provider": {"name": self.provider.name},
        })
        self._sync_stages(state)
        target_dir = self.upload_dir / simulation_id
        target_dir.mkdir(parents=True, exist_ok=True)
        ingested = []
        try:
            for upload in files:
                if not upload.filename:
                    continue
                document_id = identifier("doc")
                filename = secure_filename(upload.filename) or f"document{Path(upload.filename).suffix.lower()}"
                path = target_dir / f"{document_id}_{filename}"
                upload.file.seek(0)
                with path.open("wb") as destination:
                    shutil.copyfileobj(upload.file, destination)
                text = extract_text(path)
                document = {"id": document_id, "simulation_id": simulation_id, "name": filename, "path": str(path), "text": text}
                ingested.append((document, chunk_text(document_id, text, self.chunk_size, self.chunk_overlap)))
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise
        self.repository.create(state, owner_user_id)
        try:
            for document, chunks in ingested:
                self.repository.add_document_with_chunks(document, chunks)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise
        return state

    def start(self, simulation_id: str, stage: str, config: dict | None = None, owner_user_id: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state or stage not in STAGES[:4]:
            return None
        state = upgrade_state(state)
        if stage != "graph" and state["stages"][stage]["status"] == "locked":
            raise ValueError("Tahap sebelumnya belum selesai")
        if state["stages"][stage]["status"] in {"queued", "running", "paused"}:
            raise ValueError("Tahap sedang diproses")
        job_id = identifier("job")
        if not self.repository.put_job(job_id, simulation_id, stage, "queued", config or {}, state["revision"]):
            raise ValueError("Tahap lain sedang diproses")

        def queued(current):
            upgrade_state(current)
            current["stages"][stage].update(
                status="queued", progress=0, active_task=f"Menyiapkan {stage}", started_at=now(), job_id=job_id
            )
            current["status"] = "processing"
            current["current_stage"] = stage
            self._touch(current, f"Tahap {stage} masuk antrean")
            self._sync_stages(current)

        state = self.repository.mutate(simulation_id, queued)
        if self.embedded_worker:
            self._spawn(job_id)
        return state

    def _spawn(self, job_id: str) -> None:
        if self.stopping.is_set():
            return
        thread = threading.Thread(target=self.run_once, args=(job_id,), daemon=True, name=job_id)
        with self.thread_lock:
            self.threads[job_id] = thread
        thread.start()

    def run_once(self, job_id: str | None = None) -> bool:
        self.repository.requeue_expired_jobs()
        job = self.repository.claim_next_job(self.worker_id, self.lease_seconds, job_id)
        if not job:
            return False
        try:
            self._execute(job)
            self.repository.finish_job(job["id"], self.worker_id, {"stage": job["stage"]})
        except Exception as error:
            retry = job["attempts"] < job["max_attempts"]
            self.repository.fail_job(job["id"], self.worker_id, str(error), retry_delay=min(60, 2 ** job["attempts"]) if retry else None)
            if retry:
                self.repository.mutate(job["simulation_id"], lambda state: self._retry(state, job["stage"], str(error)))
            else:
                self.repository.mutate(job["simulation_id"], lambda state: self._fail(state, job["stage"], str(error)))
        finally:
            with self.thread_lock:
                self.threads.pop(job["id"], None)
        return True

    def _execute(self, job: dict) -> None:
        simulation_id, stage, config = job["simulation_id"], job["stage"], job["config"]
        self.repository.mutate(simulation_id, lambda state: self._progress(state, stage, 15, "Mengumpulkan bukti"))
        state = upgrade_state(self.repository.get(simulation_id))
        chunks = self.repository.chunks(simulation_id)
        if stage == "graph":
            ontology = self.provider.ontology(state["project"], chunks)
            graph = self.provider.graph(state["project"], ontology, chunks)
            self._validate_graph(graph)
            result = {"ontology": ontology, "graph": graph}
        elif stage == "environment":
            result = {"environment": self.provider.environment(simulation_id, state["graph"], config)}
        elif stage == "simulation":
            simulation = self.provider.simulate(
                simulation_id, state["graph"], state["environment"]["personas"], state["environment"]["config"]
            )
            result = {"simulation": simulation, "graph": self.provider.graph_memory(state["graph"], simulation["events"])}
        else:
            result = {"report": self.provider.report(state["project"], chunks, state["simulation"].get("events", []))}
            self._validate_citations(simulation_id, result["report"].get("citations", []))
        self.repository.renew_job_lease(job["id"], self.worker_id, self.lease_seconds)
        self.repository.mutate(simulation_id, lambda current: self._progress(current, stage, 70, "Memvalidasi hasil"))
        if self.delay:
            time.sleep(self.delay)
        current = self.repository.get(simulation_id)
        if self.repository.job_status(job["id"]) != "running":
            return
        if current.get("revision", 1) != job["input_revision"]:
            raise ValueError("Workflow changed while the job was running")
        self.repository.mutate(simulation_id, lambda current: self._complete(current, stage, result))
        self._persist_result_citations(simulation_id, stage, result)

    def _persist_result_citations(self, simulation_id: str, stage: str, result: dict) -> None:
        if stage == "graph":
            for node in result["graph"]["nodes"]:
                self.repository.replace_citations(simulation_id, "graph_node", node["id"], node.get("citations", []))
        elif stage == "report":
            report = result["report"]
            for section in report.get("sections", []):
                self.repository.replace_citations(simulation_id, "report_section", f"{report['id']}:{section['id']}", section.get("citations", []))
            for risk in report.get("risks", []):
                self.repository.replace_citations(simulation_id, "risk", f"{report['id']}:{risk['id']}", risk.get("citations", []))

    def _validate_citations(self, simulation_id: str, values: list[dict]) -> None:
        for item in values:
            if item.get("source_type") == "document_chunk":
                chunk = self.repository.chunk(item.get("chunk_id") or item["source_id"])
                if not chunk or chunk["simulation_id"] != simulation_id:
                    raise ValueError("Citation references an unknown document chunk")

    def _validate_graph(self, graph: dict) -> None:
        node_ids = {node["id"] for node in graph.get("nodes", [])}
        if len(node_ids) != len(graph.get("nodes", [])):
            raise ValueError("Graph contains duplicate node IDs")
        if any(edge["source"] not in node_ids or edge["target"] not in node_ids for edge in graph.get("edges", [])):
            raise ValueError("Graph edge references an unknown node")

    def _progress(self, state: dict, stage: str, progress: int, task: str) -> None:
        upgrade_state(state)
        state["stages"][stage].update(status="running", progress=progress, active_task=task)
        self._touch(state)
        self._sync_stages(state)

    def _complete(self, state: dict, stage: str, result: dict) -> None:
        upgrade_state(state)
        for key, value in result.items():
            state[key].update(value)
        state["stages"][stage].update(status="completed", progress=100, active_task=None, completed_at=now())
        next_index = STAGES.index(stage) + 1
        if next_index < len(STAGES):
            state["stages"][STAGES[next_index]]["status"] = "ready"
            state["current_stage"] = STAGES[next_index]
        state["status"] = "completed" if stage == "report" else "ready"
        self._touch(state, f"Tahap {stage} selesai", "DONE")
        self._sync_stages(state)

    def _fail(self, state: dict, stage: str, message: str) -> None:
        upgrade_state(state)
        state["stages"][stage].update(status="failed", active_task=None, error=message)
        state["status"] = "failed"
        self._touch(state, f"Tahap {stage} gagal: {message}", "WARN")
        self._sync_stages(state)

    def _retry(self, state: dict, stage: str, message: str) -> None:
        upgrade_state(state)
        state["stages"][stage].update(status="queued", active_task="Menunggu percobaan ulang", error=message)
        self._touch(state, f"Tahap {stage} dijadwalkan ulang setelah gagal", "WARN")
        self._sync_stages(state)

    def control(self, simulation_id: str, action: str, owner_user_id: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state:
            return None
        if action not in {"pause", "resume", "cancel"}:
            raise ValueError("Aksi simulasi tidak valid")
        active = self.repository.active_jobs(simulation_id)
        if not active or state["current_stage"] != "simulation":
            raise ValueError("Tidak ada simulasi aktif")
        value = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[action]
        for job in active:
            self.repository.set_job_status(job["id"], value)

        def apply(current):
            display = "running" if action == "resume" else value
            current["stages"]["simulation"]["status"] = display
            current["status"] = display
            self._touch(current, f"Simulasi {action}")
            self._sync_stages(current)

        updated = self.repository.mutate(simulation_id, apply)
        if action == "resume" and self.embedded_worker:
            self._spawn(active[0]["id"])
        return updated

    def interact(self, simulation_id: str, payload: dict, owner_user_id: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state:
            return None
        response = self.provider.answer(payload, state, self.repository.chunks(simulation_id))
        user = {"id": identifier("msg"), "role": "user", "author": "Anda", "tool": payload["tool"], "text": payload["question"], "citations": []}
        assistant = {"id": identifier("msg"), "role": "assistant", "author": "Report Agent", "tool": payload["tool"], **response}

        def apply(current):
            current["interactions"]["messages"].extend([user, assistant])
            current["stages"]["interaction"].update(status="completed", progress=100)
            self._touch(current, "Interaksi dijawab", "DONE")
            self._sync_stages(current)

        self.repository.mutate(simulation_id, apply)
        return assistant

    def interview(self, simulation_id: str, question: str, persona_ids: list[str] | None = None, owner_user_id: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state:
            return None
        personas = state["environment"].get("personas", [])
        if persona_ids:
            personas = [item for item in personas if item["id"] in persona_ids]
        result = self.provider.interview(question, personas, state["simulation"].get("events", []))
        interview = {"id": identifier("interview"), "question": question, "created_at": now(), "status": "completed", **result}
        self.repository.mutate(simulation_id, lambda current: (upgrade_state(current)["interviews"]["items"].append(interview), self._touch(current)))
        return interview

    def apply_graph_feedback(self, simulation_id: str, payload: dict, owner_user_id: str) -> dict | None:
        def apply(state):
            graph = state["graph"]
            action, patch, target = payload["action"], payload.get("patch", {}), payload.get("target_id")
            if payload.get("base_revision", graph.get("revision", 1)) != graph.get("revision", 1):
                raise ValueError("Graph revision conflict")
            collection = graph["edges"] if action.endswith("edge") else graph["nodes"]
            if action.startswith("add_"):
                collection.append(patch)
            elif action.startswith("update_"):
                item = next((item for item in collection if item["id"] == target), None)
                if not item:
                    raise ValueError("Graph target not found")
                item.update(patch)
            else:
                collection[:] = [item for item in collection if item["id"] != target]
                if action == "remove_node":
                    graph["edges"][:] = [edge for edge in graph["edges"] if target not in {edge["source"], edge["target"]}]
            self._validate_graph(graph)
            base = graph.get("revision", 1)
            graph["revision"] = base + 1
            state["revision"] = state.get("revision", 1) + 1
            feedback = {"id": identifier("feedback"), "base_revision": base, "resulting_revision": graph["revision"], "status": "accepted", "created_at": now(), **payload}
            upgrade_state(state)["graph_feedback"]["items"].append(feedback)
            for stage in ("environment", "simulation", "report"):
                state[stage]["stale"] = True
                state[stage]["stale_reason"] = "graph_revision_changed"
                state["stages"][stage]["status"] = "ready" if stage == "environment" else "locked"
            self._touch(state, "Graph diperbarui; hasil turunan ditandai stale", "WARN")
            self._sync_stages(state)

        return self.repository.mutate_for_user(simulation_id, owner_user_id, apply)

    def recover(self) -> None:
        self.repository.requeue_expired_jobs()
        if self.embedded_worker:
            for job in self.repository.recoverable_jobs():
                self._spawn(job["id"])

    def shutdown(self, timeout: float = 2.0) -> None:
        self.stopping.set()
        with self.thread_lock:
            threads = list(self.threads.values())
        deadline = time.monotonic() + timeout
        for thread in threads:
            thread.join(max(0, deadline - time.monotonic()))

    @staticmethod
    def _sync_stages(state: dict) -> None:
        for stage in STAGES:
            state[stage].update(state["stages"][stage])

    @staticmethod
    def _touch(state: dict, message: str | None = None, level: str = "INFO") -> None:
        state["updated_at"] = now()
        if message:
            state["logs"].append({"id": identifier("log"), "time": state["updated_at"], "level": level, "message": message})
