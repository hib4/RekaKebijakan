from __future__ import annotations

import logging
import hashlib
import threading
import time
import uuid
import tempfile
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename

from .documents import chunk_text, extract_document
from .errors import UploadQuotaExceeded
from .provider_errors import ProviderError
from .providers import PolicyProvider
from .oasis_runtime import OasisRuntimeClient, normalize_action, normalize_environment, source_identity
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
        oasis_runtime: OasisRuntimeClient | None = None,
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
        self.oasis_runtime = oasis_runtime
        self.worker_id = f"worker_{uuid.uuid4().hex[:12]}"
        self.threads: dict[str, threading.Thread] = {}
        self.thread_lock = threading.RLock()
        self.stopping = threading.Event()

    def create_project(
        self, project: dict, files: list, owner_user_id: str | None = None, idempotency_key: str | None = None,
    ) -> dict:
        if owner_user_id and idempotency_key:
            existing = self.repository.project_state_for_idempotency_key(owner_user_id, idempotency_key)
            if existing:
                return existing
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
                    temporary.seek(0)
                    metadata = self.storage.save(storage_key, temporary)
                    saved_keys.append(storage_key)
                document = {
                    "id": document_id, "simulation_id": simulation_id, "name": filename, "path": storage_key, "text": "",
                    "media_type": getattr(upload, "content_type", None) or metadata.content_type, "size_bytes": metadata.size,
                    "sha256": None, "page_count": None, "language": "id", "extraction_version": "2", "status": "processing",
                }
                ingested.append((document, [], []))
        except Exception:
            for key in saved_keys:
                self.storage.delete(key)
            raise
        graph_job_id = identifier("job")
        state["stages"]["graph"].update(
            status="queued", progress=0, active_task="Menyiapkan graph", started_at=now(), job_id=graph_job_id,
        )
        state["status"] = "processing"
        self._touch(state, "Tahap graph masuk antrean")
        self._sync_stages(state)
        try:
            if owner_user_id:
                stored_state = self.repository.create_project_bundle(
                    state, owner_user_id, ingested, self.max_active_projects_per_user,
                    self.max_files_per_project, self.max_total_upload_bytes, idempotency_key,
                    {
                        "id": graph_job_id, "simulation_id": simulation_id, "stage": "graph", "status": "queued",
                        "config": {}, "input_revision": state["revision"],
                    },
                )
                if stored_state["id"] != simulation_id:
                    for key in saved_keys:
                        self.storage.delete(key)
                    return stored_state
            else:
                self.repository.create(state, owner_user_id)
                for document, chunks, pages in ingested:
                    self.repository.add_document_with_chunks(document, chunks)
                    self.repository.add_document_pages(simulation_id, document["id"], pages)
        except Exception:
            for key in saved_keys:
                self.storage.delete(key)
            raise
        if self.embedded_worker:
            self._spawn(graph_job_id)
        return state

    def purge_due_projects(self, limit: int = 100) -> int:
        return self.repository.purge_due_projects(self.storage.delete, limit)

    def duplicate_project(self, project_id: str, owner_user_id: str, name: str | None = None) -> dict | None:
        source = self.repository.project(project_id, owner_user_id)
        if not source:
            return None
        documents = self.repository.documents(source["simulation_id"])
        opened = []
        try:
            for document in documents:
                body = self.storage.open(document["path"])
                opened.append(body)
                opened[-1] = body
                document["upload"] = SimpleNamespace(file=body, filename=document["name"], content_type=document.get("media_type"))
            project = {
                "project_name": name or f"{source['name']} (Salinan)", "institution": source["institution"],
                "objective": source["objective"],
            }
            created = self.create_project(project, [document["upload"] for document in documents], owner_user_id)
            for scenario in self.repository.list_scenarios(project_id, owner_user_id) or []:
                copied = self.repository.create_scenario(created["project"]["id"], owner_user_id, {
                    "name": scenario["name"], "description": scenario["description"],
                    "kind": scenario["kind"], "config": scenario["config"],
                })
                for persona in self.repository.effective_personas(project_id, scenario["id"], owner_user_id) or []:
                    if persona.get("custom"):
                        data = {key: value for key, value in persona.items() if key not in {"id", "custom", "source"}}
                        self.repository.create_custom_persona(created["project"]["id"], copied["id"], owner_user_id, data)
            return created
        finally:
            for body in opened:
                body.close()

    def start(self, simulation_id: str, stage: str, config: dict | None = None, owner_user_id: str | None = None,
              run_id: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state or stage not in STAGES[:4]:
            return None
        state = upgrade_state(state)
        if stage != "graph" and state["stages"][stage]["status"] == "locked":
            raise ValueError("Tahap sebelumnya belum selesai")
        if stage == "graph" and state["stages"][stage]["status"] in {"queued", "running", "paused"}:
            return state
        if state["stages"][stage]["status"] in {"queued", "running", "paused"}:
            raise ValueError("Tahap sedang diproses")
        job_id = identifier("job")
        queued = self.repository.put_job(job_id, simulation_id, stage, "queued", config or {}, state["revision"], run_id)
        # A worker publishes the completed snapshot immediately before closing
        # its job row. Briefly wait for that handoff instead of rejecting the
        # next stage with a spurious active-job conflict.
        if not queued and any(item.get("status") == "completed" for item in state["stages"].values()):
            for _ in range(10):
                time.sleep(0.01)
                queued = self.repository.put_job(job_id, simulation_id, stage, "queued", config or {}, state["revision"], run_id)
                if queued:
                    break
        if not queued:
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
        if job.get("run_id"):
            self.repository.sync_run_status(job["run_id"], "running")
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
                if job.get("run_id"):
                    completed_state = self.repository.get(job["simulation_id"])
                    self.repository.sync_run_status(job["run_id"], "completed", {
                        "simulation": completed_state.get("simulation", {}), "report": completed_state.get("report", {}),
                        "graph": completed_state.get("graph", {}), "logs": completed_state.get("logs", []),
                    })
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
            if job.get("run_id") and not retry:
                self.repository.sync_run_status(job["run_id"], "failed", {"error": str(error)})
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
        if stage == "graph":
            self.repository.mutate(simulation_id, lambda state: self._progress(state, stage, 5, "Memproses dokumen"))
            self._ingest_pending_documents(simulation_id)
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
            if self.oasis_runtime:
                result = {"environment": self._prepare_oasis_environment(simulation_id, state, chunks, config)}
            else:
                result = {"environment": self.provider.environment(simulation_id, state["graph"], config)}
        elif stage == "simulation":
            if self.oasis_runtime:
                simulation = self._run_oasis_simulation(job, state, config)
                graph = dict(state["graph"]) | {
                    "memory_revision": int(state["graph"].get("memory_revision", 0)) + 1,
                    "memory_event_ids": [event["id"] for event in simulation["events"]],
                }
                result = {"simulation": simulation, "graph": graph}
            else:
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
        if job.get("run_id"):
            completed_state = self.repository.get(simulation_id)
            self.repository.sync_run_status(job["run_id"], "completed", {
                "simulation": completed_state.get("simulation", {}), "report": completed_state.get("report", {}),
                "graph": completed_state.get("graph", {}), "logs": completed_state.get("logs", []),
            })
        return True

    def _prepare_oasis_environment(
        self, simulation_id: str, state: dict, chunks: list[dict], config: dict,
    ) -> dict:
        mapping = self.repository.get_oasis_mapping(simulation_id)
        graph_revision = int(state["graph"].get("revision", 0))
        if not mapping or mapping.get("graph_revision") != graph_revision or not mapping.get("zep_graph_id"):
            self.repository.mutate(
                simulation_id, lambda current: self._progress(current, "environment", 10, "Menyinkronkan bukti ke Zep")
            )
            synced = self.oasis_runtime.sync_graph(simulation_id, state, chunks)
            mapping = self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
                "external_project_id": synced["project_id"], "zep_graph_id": synced["graph_id"],
                "graph_revision": graph_revision, "status": "graph_ready", "config": config,
                "metadata": {"graph_info": synced.get("graph_info", {}), "episode_uuids": synced.get("episode_uuids", [])},
            })
        self.repository.mutate(
            simulation_id, lambda current: self._progress(current, "environment", 35, "Membentuk profil agent dari entitas")
        )
        prepared = self.oasis_runtime.prepare_environment(mapping, state, config)
        environment = normalize_environment(simulation_id, state["graph"], prepared, config)
        external_state = prepared["state"]
        self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
            "external_project_id": mapping["external_project_id"],
            "external_simulation_id": external_state["simulation_id"],
            "zep_graph_id": mapping["zep_graph_id"], "graph_revision": graph_revision,
            "status": "ready", "config": environment["config"],
            "metadata": dict(mapping.get("metadata") or {}) | {
                "entity_types": external_state.get("entity_types", []),
                "entities_count": external_state.get("entities_count", 0),
                "profiles_count": external_state.get("profiles_count", 0),
            },
        })
        return environment

    def _run_oasis_simulation(self, job: dict, state: dict, config: dict) -> dict:
        simulation_id = job["simulation_id"]
        mapping = self.repository.get_oasis_mapping(simulation_id)
        if not mapping or not mapping.get("external_simulation_id"):
            raise ValueError("OASIS environment must be prepared before simulation")
        environment_config = state["environment"]["config"]
        run_config = {
            "max_rounds": config.get("max_rounds") or environment_config.get("max_rounds", 40),
            "enable_graph_memory_update": config.get("enable_graph_memory_update", True),
            "force": config.get("force", False),
        }
        if run_config["force"]:
            self.repository.clear_oasis_actions(simulation_id)
        self.oasis_runtime.start_simulation(mapping, run_config)
        self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
            "external_project_id": mapping["external_project_id"],
            "external_simulation_id": mapping["external_simulation_id"],
            "zep_graph_id": mapping["zep_graph_id"], "graph_revision": mapping["graph_revision"],
            "status": "running", "config": run_config, "metadata": mapping.get("metadata") or {},
        })
        terminal = {"completed", "failed", "stopped"}
        runtime = {}
        while True:
            if self.repository.job_control_state(job["id"], job["execution_token"]) != "running":
                self.oasis_runtime.stop_simulation(mapping["external_simulation_id"])
                raise RuntimeError("OASIS simulation was stopped by job control")
            snapshot = self.oasis_runtime.simulation_snapshot(mapping["external_simulation_id"])
            runtime = snapshot["status"]
            persisted = self.repository.list_oasis_actions(simulation_id, limit=5000)
            known = {(item["platform"], item["external_sequence"], item["source_identity"]) for item in persisted}
            incoming = []
            per_platform: dict[str, int] = {}
            for action in snapshot.get("actions", []):
                platform = str(action.get("platform", "oasis"))
                external_sequence = per_platform.get(platform, 0) + 1
                per_platform[platform] = external_sequence
                identity = source_identity(action, external_sequence)
                if (platform, external_sequence, identity) in known:
                    continue
                normalized = normalize_action(
                    action, len(persisted) + len(incoming) + 1, state["environment"]["personas"],
                    int(state["graph"].get("revision", 0)), int(environment_config.get("version", 1)),
                )
                incoming.append({
                    "platform": platform, "external_sequence": external_sequence,
                    "source_identity": identity, "round": action.get("round_num"),
                    "event": normalized, "occurred_at": action.get("timestamp"),
                })
            self.repository.append_oasis_actions(simulation_id, incoming)
            progress = int(float(runtime.get("progress_percent", 0) or 0))
            self.repository.mutate(
                simulation_id,
                lambda current: self._progress(
                    current, "simulation", min(69, max(15, progress)),
                    f"OASIS ronde {runtime.get('current_round', 0)}/{runtime.get('total_rounds', 0)}",
                ),
            )
            status = runtime.get("runner_status", "idle")
            if status in terminal:
                if status != "completed":
                    raise RuntimeError(runtime.get("error") or f"OASIS runtime ended as {status}")
                break
            time.sleep(2)
        rows = self.repository.list_oasis_actions(simulation_id, limit=5000)
        events = [dict(row["event"]) | {"sequence": index} for index, row in enumerate(rows, 1)]
        self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
            "external_project_id": mapping["external_project_id"],
            "external_simulation_id": mapping["external_simulation_id"],
            "zep_graph_id": mapping["zep_graph_id"], "graph_revision": mapping["graph_revision"],
            "status": "completed", "config": run_config,
            "metadata": dict(mapping.get("metadata") or {}) | {"runtime_status": runtime},
        })
        return {
            "id": f"run_{hashlib.sha256(simulation_id.encode()).hexdigest()[:12]}",
            "events": events, "event_count": len(events),
        }

    def _ingest_pending_documents(self, simulation_id: str) -> None:
        for document in self.repository.documents(simulation_id):
            if document.get("status") == "ready":
                continue
            suffix = Path(document["name"]).suffix
            with self.storage.open(document["path"]) as stored, tempfile.NamedTemporaryFile(suffix=suffix) as temporary:
                while chunk := stored.read(1024 * 1024):
                    temporary.write(chunk)
                temporary.flush()
                extraction = extract_document(
                    Path(temporary.name), self.max_pdf_pages, self.max_extracted_chars,
                )
            pages = []
            page_numbers = sorted({segment.page for segment in extraction.segments if segment.page is not None})
            for page_number in page_numbers:
                segments = [segment for segment in extraction.segments if segment.page == page_number]
                pages.append({
                    "page_number": page_number, "text": " ".join(segment.text for segment in segments),
                    "char_start": min(segment.char_start for segment in segments),
                    "char_end": max(segment.char_end for segment in segments), "metadata": {},
                })
            self.repository.complete_document_ingestion(
                document["id"],
                {
                    "text": extraction.text,
                    "sha256": self.storage.checksum(document["path"]),
                    "page_count": max((segment.page or 0 for segment in extraction.segments), default=0) or None,
                    "status": "ready",
                },
                chunk_text(document["id"], extraction, self.chunk_size, self.chunk_overlap, self.max_chunks_per_document),
                pages,
            )

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
            if not self.repository.set_job_status(job["id"], value):
                raise ValueError("Status simulasi telah berubah")
            if job.get("run_id"):
                self.repository.sync_run_status(job["run_id"], value)

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
        if owner_user_id:
            self.repository.save_interview(simulation_id, owner_user_id, interview)
        return interview

    def apply_graph_feedback(self, simulation_id: str, payload: dict, owner_user_id: str) -> dict | None:
        def apply(state):
            graph = state["graph"]
            action, patch, target = payload["action"], payload.get("patch", {}), payload.get("target_id")
            if payload.get("base_revision", graph.get("revision", 1)) != graph.get("revision", 1):
                raise ValueError("Graph revision conflict")
            collection = graph["edges"] if action.endswith("edge") else graph["nodes"]
            if action.startswith("add_"):
                if not patch.get("id") or any(item.get("id") == patch["id"] for item in collection):
                    raise ValueError("Graph item ID must be present and unique")
                collection.append(patch)
            elif action.startswith("update_"):
                if "id" in patch and patch["id"] != target:
                    raise ValueError("Graph item ID cannot be changed")
                item = next((item for item in collection if item["id"] == target), None)
                if not item:
                    raise ValueError("Graph target not found")
                item.update(patch)
            else:
                if not target or not any(item.get("id") == target for item in collection):
                    raise ValueError("Graph target not found")
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

        state = self.repository.mutate_for_user(simulation_id, owner_user_id, apply)
        if state:
            self.repository.save_graph_feedback(simulation_id, owner_user_id, state["graph_feedback"]["items"][-1])
        return state

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
        if self.oasis_runtime:
            self.oasis_runtime.close()

    @staticmethod
    def _sync_stages(state: dict) -> None:
        for stage in STAGES:
            state[stage].update(state["stages"][stage])

    @staticmethod
    def _touch(state: dict, message: str | None = None, level: str = "INFO") -> None:
        state["updated_at"] = now()
        if message:
            state["logs"].append({"id": identifier("log"), "time": state["updated_at"], "level": level, "message": message})
