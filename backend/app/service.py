from __future__ import annotations

import logging
import threading
import time
import uuid
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename

from .documents import chunk_text, extract_document
from .errors import UploadQuotaExceeded
from .provider_errors import ProviderError
from .providers import PolicyProvider
from .repository import Repository
from .storage import LocalStorageBackend, StorageBackend

logger = logging.getLogger("rekakebijakan.worker")


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
        storage: StorageBackend | None = None,
        max_active_projects_per_user: int = 100,
        max_files_per_project: int = 20,
        max_file_upload_bytes: int = 16 * 1024 * 1024,
        max_total_upload_bytes: int = 1024 * 1024 * 1024,
        max_pdf_pages: int = 200,
        max_extracted_chars: int = 2_000_000,
        max_chunks_per_document: int = 5000,
    ):
        self.repository = repository
        self.provider = provider
        self.upload_dir = upload_dir
        self.delay = delay
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedded_worker = embedded_worker
        self.lease_seconds = lease_seconds
        self.storage = storage or LocalStorageBackend(upload_dir)
        self.max_active_projects_per_user = max_active_projects_per_user
        self.max_files_per_project = max_files_per_project
        self.max_file_upload_bytes = max_file_upload_bytes
        self.max_total_upload_bytes = max_total_upload_bytes
        self.max_pdf_pages = max_pdf_pages
        self.max_extracted_chars = max_extracted_chars
        self.max_chunks_per_document = max_chunks_per_document
        self.worker_id = f"worker_{uuid.uuid4().hex[:12]}"
        self.threads: dict[str, threading.Thread] = {}
        self.thread_lock = threading.RLock()
        self.stopping = threading.Event()

    def create_project(self, project: dict, files: list, owner_user_id: str | None = None) -> dict:
        if not files or not any(upload.filename for upload in files):
            raise ValueError("Minimal satu dokumen kebijakan diperlukan")
        files = [upload for upload in files if upload.filename]
        if len(files) > self.max_files_per_project:
            raise UploadQuotaExceeded("Jumlah berkas per proyek melebihi batas")
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
        ingested = []
        saved_keys: list[str] = []
        try:
            incoming_bytes = 0
            for upload in files:
                document_id = identifier("doc")
                filename = secure_filename(upload.filename) or f"document{Path(upload.filename).suffix.lower()}"
                storage_key = f"{simulation_id}/{document_id}_{filename}"
                upload.file.seek(0)
                suffix = Path(filename).suffix
                with tempfile.NamedTemporaryFile(suffix=suffix) as temporary:
                    file_bytes = 0
                    while chunk := upload.file.read(1024 * 1024):
                        file_bytes += len(chunk)
                        incoming_bytes += len(chunk)
                        if file_bytes > self.max_file_upload_bytes:
                            raise UploadQuotaExceeded(f"Berkas {filename} melebihi batas ukuran")
                        if incoming_bytes > self.max_total_upload_bytes:
                            raise UploadQuotaExceeded("Kuota penyimpanan pengguna telah terlampaui")
                        temporary.write(chunk)
                    temporary.flush()
                    extraction = extract_document(
                        Path(temporary.name), self.max_pdf_pages, self.max_extracted_chars,
                    )
                    temporary.seek(0)
                    metadata = self.storage.save(storage_key, temporary)
                    saved_keys.append(storage_key)
                checksum = self.storage.checksum(storage_key)
                document = {
                    "id": document_id, "simulation_id": simulation_id, "name": filename, "path": storage_key, "text": extraction.text,
                    "media_type": getattr(upload, "content_type", None) or metadata.content_type, "size_bytes": metadata.size, "sha256": checksum,
                    "page_count": max((segment.page or 0 for segment in extraction.segments), default=0) or None,
                    "language": "id", "extraction_version": "2", "status": "ready",
                }
                pages = []
                page_numbers = sorted({segment.page for segment in extraction.segments if segment.page is not None})
                for page_number in page_numbers:
                    segments = [segment for segment in extraction.segments if segment.page == page_number]
                    pages.append({
                        "page_number": page_number, "text": " ".join(segment.text for segment in segments),
                        "char_start": min(segment.char_start for segment in segments),
                        "char_end": max(segment.char_end for segment in segments), "metadata": {},
                    })
                ingested.append((document, chunk_text(
                    document_id, extraction, self.chunk_size, self.chunk_overlap, self.max_chunks_per_document,
                ), pages))
        except Exception:
            for key in saved_keys:
                self.storage.delete(key)
            raise
        try:
            if owner_user_id:
                self.repository.create_project_bundle(
                    state, owner_user_id, ingested, self.max_active_projects_per_user,
                    self.max_files_per_project, self.max_total_upload_bytes,
                )
            else:
                self.repository.create(state, owner_user_id)
                for document, chunks, pages in ingested:
                    self.repository.add_document_with_chunks(document, chunks)
                    self.repository.add_document_pages(simulation_id, document["id"], pages)
        except Exception:
            for key in saved_keys:
                self.storage.delete(key)
            raise
        return state

    def purge_due_projects(self, limit: int = 100) -> int:
        return self.repository.purge_due_projects(self.storage.delete, limit)

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
        logger.info(
            "job_claimed job_id=%s simulation_id=%s stage=%s attempt=%s worker_id=%s",
            job["id"], job["simulation_id"], job["stage"], job["attempts"], self.worker_id,
        )
        try:
            heartbeat_stop = threading.Event()
            heartbeat = threading.Thread(target=self._heartbeat, args=(job, heartbeat_stop), daemon=True)
            heartbeat.start()
            published = self._execute(job)
            if published and not self.repository.finish_job(job["id"], self.worker_id, job["execution_token"], {"stage": job["stage"]}):
                raise RuntimeError("Job lease was lost before completion")
            if published:
                logger.info(
                    "job_completed job_id=%s simulation_id=%s stage=%s worker_id=%s",
                    job["id"], job["simulation_id"], job["stage"], self.worker_id,
                )
        except Exception as error:
            retry = job["attempts"] < job["max_attempts"]
            retry = retry and (not isinstance(error, ProviderError) or error.retryable)
            code = error.category if isinstance(error, ProviderError) else "worker_error"
            self.repository.fail_job(
                job["id"], self.worker_id, job["execution_token"], str(error),
                retry_delay=min(60, 2 ** job["attempts"]) if retry else None, error_code=code,
            )
            logger.error(
                "job_failed job_id=%s simulation_id=%s stage=%s retry=%s error_code=%s error=%s",
                job["id"], job["simulation_id"], job["stage"], retry, code, error,
                exc_info=True,
            )
            if retry:
                self.repository.mutate(job["simulation_id"], lambda state: self._retry(state, job["stage"], str(error)))
            else:
                self.repository.mutate(job["simulation_id"], lambda state: self._fail(state, job["stage"], str(error)))
        finally:
            if "heartbeat_stop" in locals():
                heartbeat_stop.set()
                heartbeat.join(timeout=1)
            with self.thread_lock:
                self.threads.pop(job["id"], None)
        return True

    def _heartbeat(self, job: dict, stop: threading.Event) -> None:
        interval = max(1, self.lease_seconds / 3)
        while not stop.wait(interval):
            if not self.repository.renew_job_lease(job["id"], self.worker_id, job["execution_token"], self.lease_seconds):
                return

    def _execute(self, job: dict) -> bool:
        simulation_id, stage, config = job["simulation_id"], job["stage"], job["config"]
        self.repository.mutate(simulation_id, lambda state: self._progress(state, stage, 15, "Mengumpulkan bukti"))
        state = upgrade_state(self.repository.get(simulation_id))
        chunks = self.repository.chunks(simulation_id)
        if self.repository.job_control_state(job["id"], job["execution_token"]) != "running":
            return False
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
        if not self.repository.renew_job_lease(job["id"], self.worker_id, job["execution_token"], self.lease_seconds):
            return False
        self.repository.mutate(simulation_id, lambda current: self._progress(current, stage, 70, "Memvalidasi hasil"))
        if self.delay:
            time.sleep(self.delay)
        current = self.repository.get(simulation_id)
        if self.repository.job_status(job["id"]) != "running":
            return False
        if current.get("revision", 1) != job["input_revision"]:
            raise ValueError("Workflow changed while the job was running")
        self.repository.mutate(simulation_id, lambda current: self._complete(current, stage, result))
        self._persist_result_citations(simulation_id, stage, result)
        return True

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
