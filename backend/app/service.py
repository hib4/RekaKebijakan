from __future__ import annotations

import logging
import hashlib
import json
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
from .provider_errors import ProviderError, ProviderResponseError, ProviderTransportError
from .providers import DeterministicPolicyProvider, PolicyProvider
from .quick_demo import QUICK_DEMO_SOURCE, build_quick_demo, bundle_metadata
from .oasis_runtime import normalize_action, normalize_environment, source_identity
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
    state.setdefault("project", {}).setdefault("language", "id")
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
        oasis_runtime: object | None = None,
        default_simulation_engine: str | None = None,
        quick_interaction_provider: PolicyProvider | None = None,
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
        self.default_simulation_engine = default_simulation_engine or ("oasis" if oasis_runtime else "deterministic")
        self.quick_interaction_provider = quick_interaction_provider
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
        files = [upload for upload in files if upload.filename]
        workflow_mode = project.get("workflow_mode", "full_simulation")
        demo_bundle_id = project.get("demo_bundle_id")
        if workflow_mode == "quick_demo":
            if demo_bundle_id != "makan-bergizi-gratis-v1":
                raise ValueError("Quick demo requires demo_bundle_id makan-bergizi-gratis-v1")
            if files:
                raise ValueError("Quick demo tidak menerima unggahan dokumen")
        elif workflow_mode == "full_simulation":
            if demo_bundle_id is not None:
                raise ValueError("demo_bundle_id hanya berlaku untuk quick_demo")
            if not files:
                raise ValueError("Minimal satu dokumen kebijakan diperlukan")
        else:
            raise ValueError("workflow_mode tidak valid")
        if len(files) > self.max_files_per_project:
            raise UploadQuotaExceeded("Jumlah berkas per proyek melebihi batas")
        project_id, simulation_id = identifier("project"), identifier("sim")
        timestamp = now()
        workflow = {
            "mode": workflow_mode,
            "accelerated_steps": ["graph", "environment", "simulation"] if workflow_mode == "quick_demo" else [],
        }
        if demo_bundle_id:
            workflow["bundle"] = bundle_metadata()
        state = upgrade_state({
            "id": simulation_id,
            "simulation_id": simulation_id,
            "status": "ready",
            "current_stage": "graph",
            "workflow_mode": workflow_mode,
            "demo_bundle_id": demo_bundle_id,
            "workflow": workflow,
            "provenance": {
                "workflow_mode": workflow_mode,
                "demo_bundle_id": demo_bundle_id,
                "execution_kind": "accelerated_fixture" if workflow_mode == "quick_demo" else "provider_workflow",
            },
            "project": {
                "id": project_id, "name": project["project_name"], "project_name": project["project_name"],
                "institution": project["institution"], "objective": project["objective"], "question": project["objective"],
                "language": project.get("language", "id"),
                "workflow_mode": workflow_mode, "demo_bundle_id": demo_bundle_id,
                "workflow": workflow,
            },
            "stages": {}, "graph": {"revision": 0, "nodes": [], "edges": []}, "environment": {},
            "simulation": {"events": [], "event_count": 0, "speed": 1},
            "report": {"sections": [], "risks": []}, "interaction": {}, "interactions": {"messages": []},
            "logs": [], "updated_at": timestamp,
            "provider": {"name": self.provider.name},
        })
        self._sync_stages(state)
        if workflow_mode == "quick_demo":
            self._bootstrap_quick_demo(state)
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
        graph_job_id = identifier("job") if workflow_mode == "full_simulation" else None
        if graph_job_id:
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
                    } if graph_job_id else None,
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
        if self.embedded_worker and graph_job_id:
            self._spawn(graph_job_id)
        return state

    def _bootstrap_quick_demo(self, state: dict) -> None:
        ontology, graph, environment, simulation, runtime_graph, report = self._quick_demo_artifacts()
        state.update(
            ontology=ontology,
            graph=graph,
            environment=environment,
            simulation=simulation,
            runtime_graph=runtime_graph,
            report=report,
        )
        completed_at = now()
        for stage in ("graph", "environment", "simulation"):
            state["stages"][stage].update(
                status="completed", progress=100, active_task=None, completed_at=completed_at,
                execution_kind="accelerated_fixture", error=None,
            )
        report.update(status="completed", progress=100, completed_at=completed_at)
        state["stages"]["report"].update(
            status="completed", progress=100, active_task=None,
            completed_at=completed_at, execution_kind="accelerated_fixture",
        )
        state["stages"]["interaction"].update(status="ready", progress=0, active_task=None)
        state["current_stage"] = "report"
        state["status"] = "ready"
        self._touch(state, "Tahap simulation selesai", "DONE")
        self._sync_stages(state)

    def _quick_demo_artifacts(self) -> tuple[dict, dict, dict, dict, dict, dict]:
        return build_quick_demo(DeterministicPolicyProvider())

    def public_quick_demo(self) -> dict:
        ontology, graph, environment, simulation, runtime_graph, report = self._quick_demo_artifacts()
        state = upgrade_state({
            "id": "demo-mbg",
            "simulation_id": "demo-mbg",
            "status": "ready",
            "current_stage": "report",
            "workflow_mode": "quick_demo",
            "demo_bundle_id": "makan-bergizi-gratis-v1",
            "workflow": {
                "mode": "quick_demo",
                "accelerated_steps": ["graph", "environment", "simulation"],
                "bundle": bundle_metadata(),
            },
            "provenance": {
                "workflow_mode": "quick_demo",
                "demo_bundle_id": "makan-bergizi-gratis-v1",
                "execution_kind": "accelerated_fixture",
            },
            "project": {
                "id": "makan-bergizi-gratis-v1",
                "name": "Makan Bergizi Gratis (MBG)",
                "project_name": "Makan Bergizi Gratis (MBG)",
                "institution": "Badan Gizi Nasional",
                "objective": "Mengkritisi desain tata kelola nasional MBG terhadap risiko salah sasaran, ekspansi terlalu cepat, akuntabilitas pengadaan, dan biaya peluang anggaran.",
                "question": "Mengkritisi desain tata kelola nasional MBG terhadap risiko salah sasaran, ekspansi terlalu cepat, akuntabilitas pengadaan, dan biaya peluang anggaran.",
                "language": "id",
                "workflow_mode": "quick_demo",
                "demo_bundle_id": "makan-bergizi-gratis-v1",
            },
            "ontology": ontology,
            "graph": graph,
            "environment": environment,
            "simulation": simulation,
            "runtime_graph": runtime_graph,
            "report": report,
            "interactions": {"messages": []},
            "interaction": {},
            "logs": [{"message": "Tahap simulation selesai", "level": "DONE"}],
        })
        for stage in ("graph", "environment", "simulation", "report"):
            state["stages"][stage].update(status="completed", progress=100, execution_kind="accelerated_fixture")
        state["stages"]["interaction"].update(status="ready", progress=0)
        return state

    def public_quick_demo_interact(self, payload: dict) -> dict:
        state = self.public_quick_demo()
        chunk = {
            "id": "quick-demo-source",
            "document_id": "quick-demo-bundle",
            "ordinal": 0,
            "text": QUICK_DEMO_SOURCE,
            "char_start": 0,
            "char_end": len(QUICK_DEMO_SOURCE),
        }
        provider = self.quick_interaction_provider or self.provider
        response = provider.answer(payload, state, [chunk])
        return {
            "id": identifier("msg"),
            "role": "assistant",
            "author": "Report Agent",
            "tool": payload["tool"],
            "created_at": now(),
            **response,
        }

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
                "workflow_mode": source.get("workflow_mode", "full_simulation"),
                "demo_bundle_id": source.get("demo_bundle_id"),
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
        if state.get("workflow_mode") == "quick_demo" and stage in {"graph", "environment", "simulation", "report"}:
            raise ValueError(f"Tahap {stage} sudah selesai dan tidak dapat dijalankan ulang")
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
                    mapping = self.repository.get_oasis_mapping(job["simulation_id"])
                    self.repository.sync_run_status(job["run_id"], "completed", {
                        "simulation": completed_state.get("simulation", {}), "report": completed_state.get("report", {}),
                        "graph": completed_state.get("graph", {}), "logs": completed_state.get("logs", []),
                        "oasis_artifacts": (mapping or {}).get("artifacts", {}),
                        "oasis_runtime": (mapping or {}).get("runtime_status", {}),
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
            build_id = f"graph-build-{uuid.uuid4().hex[:12]}"
            graph_revision = int(state.get("graph", {}).get("revision", 0)) + 1
            self.repository.mutate_with_events(
                simulation_id,
                lambda current: self._start_policy_graph_build(current, build_id, graph_revision),
                lambda current: [
                    ("graph.snapshot", {"graph": self._policy_graph_payload(current["graph"])}),
                    ("stage.updated", {"stage": {"name": "graph", **current["stages"]["graph"]}}),
                ],
            )
            ontology = self.provider.ontology(state["project"], chunks)
            self.repository.mutate(
                simulation_id,
                lambda current: self._publish_policy_ontology(current, ontology),
            )
            fallback_provider = getattr(self.provider, "fallback_provider", None)
            baseline = fallback_provider.graph(state["project"], ontology, chunks) if fallback_provider else None
            if baseline:
                self._stream_policy_graph(simulation_id, build_id, graph_revision, baseline, 35, 58)
            graph = self.provider.graph(state["project"], ontology, chunks)
            graph["revision"] = graph_revision
            self._stream_policy_graph(
                simulation_id, build_id, graph_revision, graph,
                59 if baseline else 35, 66,
            )
            self._validate_graph(graph)
            result = {"ontology": ontology, "graph": graph}
        elif stage == "environment":
            engine = config.get("engine") or self.default_simulation_engine
            if engine == "oasis":
                if not self.oasis_runtime:
                    raise ValueError("Direct OASIS engine is not configured")
                result = {"environment": self._prepare_oasis_environment(simulation_id, state, chunks, config)}
            else:
                result = {"environment": self.provider.environment(simulation_id, state["graph"], config)}
        elif stage == "simulation":
            run = self.repository.run_by_id(job["run_id"]) if job.get("run_id") else None
            engine = config.get("engine") or (run or {}).get("engine") or state.get("environment", {}).get("config", {}).get("engine") or self.default_simulation_engine
            if engine == "oasis":
                if not self.oasis_runtime:
                    raise ValueError("Direct OASIS engine is not configured")
                environment = state.get("environment", {})
                mapping = self.repository.get_oasis_mapping(simulation_id)
                if not mapping or not mapping.get("external_simulation_id"):
                    environment = self._prepare_oasis_environment(simulation_id, state, chunks, dict(environment.get("config", {})) | {"engine": "oasis"})
                    state = dict(state) | {"environment": environment}
                simulation = self._run_oasis_simulation(job, state, config)
                graph = dict(state["graph"]) | {
                    "memory_revision": int(state["graph"].get("memory_revision", 0)) + 1,
                    "memory_event_ids": [event["id"] for event in simulation["events"]],
                }
                result = {"simulation": simulation, "graph": graph, "environment": environment}
            else:
                simulation = self.provider.simulate(
                    simulation_id, state["graph"], state["environment"]["personas"], state["environment"]["config"]
                )
                result = {"simulation": simulation, "graph": self.provider.graph_memory(state["graph"], simulation["events"])}
        else:
            mapping = self.repository.get_oasis_mapping(simulation_id)
            if (state.get("workflow_mode") != "quick_demo" and mapping and mapping.get("zep_graph_id") and self.oasis_runtime
                    and state.get("environment", {}).get("config", {}).get("engine") == "oasis"):
                raw_report = self.oasis_runtime.generate_report(
                    mapping.get("external_simulation_id") or simulation_id,
                    mapping["zep_graph_id"], state["project"]["objective"],
                    language=state.get("project", {}).get("language", "id"),
                    progress_callback=lambda partial: self.repository.mutate(
                        simulation_id,
                        lambda current: self._update_oasis_report_progress(current, partial, chunks),
                    ),
                )
                result = {"report": self._project_oasis_report(raw_report, chunks)}
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
        if job.get("run_id"):
            mapping = self.repository.get_oasis_mapping(simulation_id)
            self.repository.mutate_and_complete_run(
                simulation_id,
                lambda current: self._complete(current, stage, result),
                job["run_id"],
                lambda completed_state, _db: {
                    "simulation": completed_state.get("simulation", {}),
                    "report": completed_state.get("report", {}),
                    "graph": completed_state.get("graph", {}),
                    "logs": completed_state.get("logs", []),
                    "oasis_artifacts": (mapping or {}).get("artifacts", {}),
                    "oasis_runtime": (mapping or {}).get("runtime_status", {}),
                },
            )
        else:
            self.repository.mutate(simulation_id, lambda current: self._complete(current, stage, result))
        self._persist_result_citations(simulation_id, stage, result)
        return True

    def _prepare_oasis_environment(
        self, simulation_id: str, state: dict, chunks: list[dict], config: dict,
    ) -> dict:
        config = dict(config) | {"language": state.get("project", {}).get("language", "id")}
        mapping = self.repository.get_oasis_mapping(simulation_id)
        graph_revision = int(state["graph"].get("revision", 0))
        evidence_hash = hashlib.sha256("\n".join(
            f"{chunk['id']}:{chunk.get('content_sha256', '')}" for chunk in chunks
        ).encode()).hexdigest()
        ontology_hash = hashlib.sha256(
            json.dumps(state.get("ontology", {}), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        mapping_metadata = (mapping or {}).get("metadata") or {}
        if (
            not mapping or mapping.get("graph_revision") != graph_revision or not mapping.get("zep_graph_id")
            or mapping_metadata.get("evidence_hash") != evidence_hash
            or mapping_metadata.get("ontology_hash") != ontology_hash
            or mapping.get("status") not in {"graph_ready", "ready", "completed"}
        ):
            self.repository.mutate(
                simulation_id, lambda current: self._progress(current, "environment", 16, "Menyinkronkan bukti ke Zep")
            )
            resumable = bool(
                mapping and mapping.get("status") == "creating" and mapping.get("zep_graph_id")
                and mapping_metadata.get("evidence_hash") == evidence_hash
                and mapping_metadata.get("ontology_hash") == ontology_hash
            )
            existing_sync = mapping_metadata.get("graph_sync", {}) if resumable else {}
            graph_id = mapping["zep_graph_id"] if resumable else f"rekakebijakan_{uuid.uuid4().hex[:16]}"
            build_id = existing_sync.get("build_id") or f"runtime-build-{uuid.uuid4().hex[:12]}"
            graph_metadata = dict(mapping_metadata) | {
                "evidence_hash": evidence_hash, "ontology_hash": ontology_hash,
                "graph_sync": existing_sync or {"build_id": build_id, "status": "creating", "progress": 0},
            }
            self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
                "external_project_id": simulation_id, "zep_graph_id": graph_id,
                "graph_revision": graph_revision, "status": "creating", "config": config,
                "metadata": graph_metadata,
            })
            synced = self.oasis_runtime.sync_graph(
                simulation_id, state, chunks, graph_id=graph_id,
                progress_callback=lambda message: self._publish_runtime_graph_progress(
                    simulation_id, state["project"]["id"], graph_revision,
                    graph_id, build_id, graph_metadata, config, message,
                ),
                checkpoint=existing_sync if resumable else None,
            )
            mapping = self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
                "external_project_id": synced["project_id"], "zep_graph_id": synced["graph_id"],
                "graph_revision": graph_revision, "status": "graph_ready", "config": config,
                "metadata": graph_metadata | {
                    "graph_info": synced.get("graph_info", {}), "episode_uuids": synced.get("episode_uuids", []),
                    "ontology": synced.get("ontology", {}),
                    "evidence_hash": evidence_hash, "ontology_hash": ontology_hash,
                    "graph_sync": {"build_id": build_id, "status": "completed", "progress": 100},
                },
            })
        self.repository.mutate(
            simulation_id, lambda current: self._progress(current, "environment", 35, "Membentuk profil agent dari entitas")
        )
        prepared = self.oasis_runtime.prepare_environment(mapping, state, dict(config) | {"_chunks": chunks})
        environment = normalize_environment(simulation_id, state["graph"], prepared, config)
        external_state = prepared["state"]
        self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
            "external_project_id": mapping["external_project_id"],
            "external_simulation_id": external_state["simulation_id"],
            "zep_graph_id": mapping["zep_graph_id"], "graph_revision": graph_revision,
            "status": "ready", "config": environment["config"], "runtime_status": {}, "artifacts": {},
            "metadata": dict(mapping.get("metadata") or {}) | {
                "entity_types": external_state.get("entity_types", []),
                "entities_count": external_state.get("entities_count", 0),
                "profiles_count": external_state.get("profiles_count", 0),
            },
        })
        try:
            graph = self.runtime_graph(simulation_id)
            if graph is not None:
                self.repository.append_workflow_event(
                    simulation_id, "graph.snapshot", {"graph": {
                        "available": True, "graph_kind": "runtime",
                        "build_id": (mapping.get("metadata") or {}).get("graph_sync", {}).get("build_id"),
                        **graph,
                    }},
                )
        except Exception:
            # Zep may need a short consistency window after initial ingestion.
            pass
        return environment

    def _publish_runtime_graph_progress(
        self, simulation_id: str, project_id: str, graph_revision: int,
        graph_id: str, build_id: str, metadata: dict, config: dict, message: dict,
    ) -> None:
        kind = message.get("kind")
        progress = min(100, max(0, int(float(message.get("progress", 0) or 0) * 100)))
        if kind == "milestone":
            sync = {
                "build_id": build_id, "status": message.get("milestone", "processing"),
                "progress": progress, "message": message.get("message"),
                "batch_id": message.get("batch_id"), "operation_id": message.get("operation_id"),
            }
            metadata["graph_sync"] = sync
            self.repository.upsert_oasis_mapping(simulation_id, project_id, {
                "external_project_id": simulation_id, "zep_graph_id": graph_id,
                "graph_revision": graph_revision, "status": "creating", "config": config,
                "metadata": metadata,
            })

            def update_stage(current: dict) -> None:
                stage_progress = max(
                    int(current["stages"]["environment"].get("progress", 0)),
                    min(34, 16 + int(progress * 0.18)),
                )
                self._progress(
                    current, "environment", stage_progress,
                    message.get("message") or "Membangun graf runtime",
                )

            self.repository.mutate_with_events(
                simulation_id,
                update_stage,
                lambda current: [
                    ("stage.updated", {"stage": {"name": "environment", **current["stages"]["environment"]}}),
                    ("graph.delta", {"graph": {
                        "available": True, "graph_kind": "runtime", "graph_id": graph_id,
                        "build_id": build_id, "revision": graph_revision,
                        "mapping_status": "creating", "milestone": message.get("message"),
                        "milestone_progress": progress, "nodes": [], "edges": [],
                    }}),
                ],
            )
            return

        if kind in {"node", "edge"}:
            item_key = "nodes" if kind == "node" else "edges"
            self.repository.append_workflow_event(simulation_id, "graph.delta", {"graph": {
                "available": True, "graph_kind": "runtime", "graph_id": graph_id,
                "build_id": build_id, "revision": graph_revision,
                "mapping_status": "creating", "milestone_progress": progress,
                "nodes": [message["node"]] if kind == "node" else [],
                "edges": [message["edge"]] if kind == "edge" else [],
                "node_count": message.get("node_count"), "edge_count": message.get("edge_count"),
                "removed_node_ids": [], "removed_edge_ids": [], "item_kind": item_key,
            }})
            return

        if kind == "snapshot" and isinstance(message.get("graph"), dict):
            graph = message["graph"]
            self.repository.append_workflow_event(simulation_id, "graph.snapshot", {"graph": {
                "available": True, "graph_kind": "runtime", "graph_id": graph_id,
                "build_id": build_id, "revision": graph_revision,
                "source_revision": graph_revision, "mapping_status": "graph_ready",
                **graph,
            }})

    def _start_policy_graph_build(self, state: dict, build_id: str, revision: int) -> None:
        graph = state.setdefault("graph", {})
        graph.update({
            "graph_kind": "policy", "graph_id": f"policy:{state['id']}",
            "build_id": build_id, "revision": revision,
            "nodes": [], "edges": [], "status": "running", "progress": 20,
            "active_task": "Menyusun ontology kebijakan",
        })
        state["stages"]["graph"].update(
            status="running", progress=20, active_task="Menyusun ontology kebijakan",
        )
        self._touch(state)
        self._sync_stages(state)

    def _publish_policy_ontology(self, state: dict, ontology: dict) -> None:
        state["ontology"] = ontology
        state["graph"]["progress"] = 32
        state["graph"]["active_task"] = "Ontology selesai; menyusun entitas graf"
        state["stages"]["graph"].update(
            status="running", progress=32, active_task="Ontology selesai; menyusun entitas graf",
        )
        self._touch(state)
        self._sync_stages(state)

    @staticmethod
    def _policy_graph_payload(graph: dict, *, nodes: list[dict] | None = None,
                              edges: list[dict] | None = None) -> dict:
        return {
            "available": True, "graph_kind": "policy", "graph_id": graph.get("graph_id"),
            "build_id": graph.get("build_id"), "revision": graph.get("revision", 0),
            "mapping_status": graph.get("status", "building"),
            "milestone": graph.get("active_task"), "milestone_progress": graph.get("progress", 0),
            "node_count": len(graph.get("nodes", [])), "edge_count": len(graph.get("edges", [])),
            "nodes": graph.get("nodes", []) if nodes is None else nodes,
            "edges": graph.get("edges", []) if edges is None else edges,
            "removed_node_ids": [], "removed_edge_ids": [],
        }

    def _stream_policy_graph(self, simulation_id: str, build_id: str, revision: int,
                             graph: dict, start_progress: int, end_progress: int) -> None:
        items = [("node", item) for item in graph.get("nodes", [])]
        items.extend(("edge", item) for item in graph.get("edges", []))
        total = max(1, len(items))
        for index, (kind, item) in enumerate(items, 1):
            progress = start_progress + int((end_progress - start_progress) * index / total)

            def mutate(current: dict, kind=kind, item=item, progress=progress) -> None:
                current_graph = current["graph"]
                if current_graph.get("build_id") != build_id:
                    return
                key = "nodes" if kind == "node" else "edges"
                values = current_graph.setdefault(key, [])
                existing = next((position for position, value in enumerate(values) if value.get("id") == item.get("id")), None)
                if existing is None:
                    values.append(item)
                else:
                    values[existing] = values[existing] | item
                current_graph.update(progress=progress, active_task=(
                    "Menyusun entitas graf" if kind == "node" else "Menghubungkan relasi graf"
                ))
                current["stages"]["graph"].update(
                    status="running", progress=progress, active_task=current_graph["active_task"],
                )
                self._touch(current)
                self._sync_stages(current)

            self.repository.mutate_with_events(
                simulation_id,
                mutate,
                lambda current, kind=kind, item=item: [
                    ("graph.delta", {"graph": self._policy_graph_payload(
                        current["graph"], nodes=[item] if kind == "node" else [],
                        edges=[item] if kind == "edge" else [],
                    )}),
                    ("stage.updated", {"stage": {"name": "graph", **current["stages"]["graph"]}}),
                ],
            )

    def _run_oasis_simulation(self, job: dict, state: dict, config: dict) -> dict:
        simulation_id = job["simulation_id"]
        mapping = self.repository.get_oasis_mapping(simulation_id)
        if not mapping or not mapping.get("external_simulation_id"):
            raise ValueError("OASIS environment must be prepared before simulation")
        environment_config = state["environment"]["config"]
        if hasattr(self.oasis_runtime, "apply_persona_overrides"):
            self.oasis_runtime.apply_persona_overrides(
                mapping["external_simulation_id"], state["environment"].get("personas", [])
            )
        requested_rounds = config.get("rounds")
        if requested_rounds is None:
            requested_rounds = config.get("max_rounds")
        if requested_rounds is None:
            requested_rounds = environment_config.get("rounds", environment_config.get("max_rounds", 10))
        step_timeout_seconds = config.get("step_timeout_seconds", 600)
        stale_timeout_seconds = config.get("stale_timeout_seconds")
        if stale_timeout_seconds is None:
            stale_timeout_seconds = max(600, float(step_timeout_seconds) + 60)
        run_config = {
            "rounds": int(requested_rounds),
            "max_rounds": int(requested_rounds),
            "enable_graph_memory_update": config.get("enable_graph_memory_update", True),
            "force": config.get("force", False),
            "step_timeout_seconds": step_timeout_seconds,
            "step_cleanup_grace_seconds": config.get("step_cleanup_grace_seconds", 5),
            "stale_timeout_seconds": stale_timeout_seconds,
            "max_run_seconds": config.get("max_run_seconds", 3600),
            "oasis_concurrency": config.get("oasis_concurrency") or 2,
            "language": state.get("project", {}).get("language", "id"),
        }
        run_id = job.get("run_id")
        self.repository.clear_oasis_actions(simulation_id, run_id)
        terminal = {"completed", "failed", "stopped"}
        runtime = {}
        cursor = None
        synthetic_failure_count = 0
        pending_graph_actions: list[dict] = []
        graph_memory: dict = {}
        graph_memory_enabled = (
            run_config["enable_graph_memory_update"]
            and hasattr(self.oasis_runtime, "ingest_actions")
        )
        try:
            self.oasis_runtime.start_simulation(mapping, run_config)
            self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
                "external_project_id": mapping["external_project_id"],
                "external_simulation_id": mapping["external_simulation_id"],
                "zep_graph_id": mapping["zep_graph_id"], "graph_revision": mapping["graph_revision"],
                "status": "running", "config": run_config, "metadata": mapping.get("metadata") or {},
            })
            while True:
                if self.repository.job_control_state(job["id"], job["execution_token"]) != "running":
                    self.oasis_runtime.stop_simulation(mapping["external_simulation_id"])
                    raise RuntimeError("OASIS simulation was stopped by job control")
                snapshot = self.oasis_runtime.simulation_snapshot(mapping["external_simulation_id"], cursor)
                runtime = snapshot["status"]
                cursor = snapshot.get("next_cursor") or cursor
                persisted_count = self.repository.summarize_oasis_actions(simulation_id, run_id)["total_actions"]
                incoming = []
                for action in snapshot.get("actions", []):
                    if action.get("synthetic") and action.get("success") is False:
                        synthetic_failure_count += 1
                        continue
                    platform = str(action.get("platform", "oasis"))
                    external_sequence = int(action.get("source_sequence", 0))
                    identity = source_identity(action, external_sequence)
                    normalized = normalize_action(
                        action, persisted_count + len(incoming) + 1, state["environment"]["personas"],
                        int(state["graph"].get("revision", 0)), int(environment_config.get("version", 1)),
                    )
                    incoming.append({
                        "platform": platform, "external_sequence": external_sequence,
                        "source_identity": identity, "round": action.get("round_num", action.get("round")),
                        "event": normalized, "raw_action": action, "occurred_at": action.get("timestamp"),
                    })
                self.repository.append_oasis_actions(simulation_id, incoming, run_id)
                if graph_memory_enabled and incoming:
                    pending_graph_actions.extend(item["raw_action"] for item in incoming)
                progress = int(float(runtime.get("progress_percent", 0) or 0))
                self.repository.mutate(
                    simulation_id,
                    lambda current: self._oasis_progress(current, runtime, progress),
                )
                self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
                    "external_project_id": mapping["external_project_id"],
                    "external_simulation_id": mapping["external_simulation_id"],
                    "zep_graph_id": mapping["zep_graph_id"], "graph_revision": mapping["graph_revision"],
                    "status": status if (status := runtime.get("runner_status", "running")) else "running",
                    "config": run_config, "runtime_status": runtime,
                    "metadata": dict(mapping.get("metadata") or {}) | {"runtime_status": runtime},
                })
                status = runtime.get("runner_status", "idle")
                if status in terminal:
                    if status != "completed":
                        runtime_error = runtime.get("error") or f"OASIS runtime ended as {status}"
                        if "timed out" in runtime_error.lower() or "timeout" in runtime_error.lower():
                            raise ProviderTransportError("simulate", runtime_error)
                        raise ProviderResponseError("simulate", runtime_error)
                    if self.repository.summarize_oasis_actions(simulation_id, run_id)["total_actions"] == 0:
                        if synthetic_failure_count:
                            raise ProviderTransportError(
                                "simulate",
                                "OASIS could not obtain persona actions from the configured model/provider "
                                f"({synthetic_failure_count} active-agent attempts produced no action). "
                                "Check provider permissions and tool-calling support.",
                            )
                        raise ProviderResponseError(
                            "simulate", "OASIS completed without producing persona activity"
                        )
                    break
                time.sleep(2)

            if graph_memory_enabled and pending_graph_actions:
                self.repository.mutate(
                    simulation_id,
                    lambda current: self._oasis_graph_sync_progress(
                        current, runtime, len(pending_graph_actions)
                    ),
                )
                graph_memory.update(self.oasis_runtime.ingest_actions(
                    mapping["external_simulation_id"], mapping["zep_graph_id"],
                    f"{run_id or job['id']}-final", pending_graph_actions,
                ))
                if hasattr(self.oasis_runtime, "runtime_graph"):
                    graph = self.runtime_graph(simulation_id)
                    if graph is not None:
                        self.repository.append_workflow_event(
                            simulation_id, "graph.snapshot", {"graph": {
                                "available": True, "graph_kind": "runtime",
                                "build_id": (mapping.get("metadata") or {}).get("graph_sync", {}).get("build_id"),
                                **graph,
                            }},
                        )
        except Exception as error:
            self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
                "external_project_id": mapping["external_project_id"],
                "external_simulation_id": mapping["external_simulation_id"],
                "zep_graph_id": mapping["zep_graph_id"], "graph_revision": mapping["graph_revision"],
                "status": "failed", "config": run_config,
                "metadata": dict(mapping.get("metadata") or {}) | {"runtime_status": runtime, "error": str(error)},
            })
            raise
        rows = self.repository.list_oasis_actions(simulation_id, limit=5000, run_id=run_id)
        events = [dict(row["event"]) | {"sequence": index} for index, row in enumerate(rows, 1)]
        artifacts = self.oasis_runtime.artifacts(mapping["external_simulation_id"]) if hasattr(self.oasis_runtime, "artifacts") else {}
        self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
            "external_project_id": mapping["external_project_id"],
            "external_simulation_id": mapping["external_simulation_id"],
            "zep_graph_id": mapping["zep_graph_id"], "graph_revision": mapping["graph_revision"],
            "status": "completed", "config": run_config,
            "runtime_status": runtime, "artifacts": artifacts,
            "metadata": dict(mapping.get("metadata") or {}) | {"runtime_status": runtime, "environment_alive": runtime.get("environment_alive", False)},
        })
        return {
            "id": f"run_{hashlib.sha256(simulation_id.encode()).hexdigest()[:12]}",
            "events": events, "event_count": len(events), "graph_memory": graph_memory,
        }

    def runtime_graph(self, simulation_id: str) -> dict | None:
        get_state = getattr(self.repository, "get", None)
        state = get_state(simulation_id) if get_state else None
        if isinstance(state, dict) and state.get("runtime_graph"):
            return state["runtime_graph"]
        mapping = self.repository.get_oasis_mapping(simulation_id)
        if not mapping or not mapping.get("zep_graph_id") or not self.oasis_runtime:
            return None
        graph = self.oasis_runtime.runtime_graph(mapping["zep_graph_id"])
        nodes = []
        for item in graph.get("nodes", []):
            node_id = item.get("id") or item.get("uuid")
            if not node_id:
                continue
            labels = item.get("labels") or []
            nodes.append(dict(item) | {
                "id": str(node_id),
                "label": item.get("label") or item.get("name") or str(node_id),
                "type": item.get("type") or item.get("entity_type") or (labels[0] if labels else "Entity"),
            })
        node_ids = {item["id"] for item in nodes}
        edges = []
        for index, item in enumerate(graph.get("edges", [])):
            source = item.get("source") or item.get("source_node_uuid")
            target = item.get("target") or item.get("target_node_uuid")
            if str(source) not in node_ids or str(target) not in node_ids:
                continue
            edges.append(dict(item) | {
                "id": str(item.get("id") or item.get("uuid") or f"runtime-edge-{index}"),
                "source": str(source), "target": str(target),
                "type": item.get("type") or item.get("relation_type") or item.get("fact_type") or "RELATED_TO",
            })
        return graph | {
            "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges),
            "graph_id": mapping["zep_graph_id"],
            "source_revision": mapping["graph_revision"],
            "mapping_status": mapping["status"],
        }

    @staticmethod
    def _project_oasis_report(raw: dict, chunks: list[dict]) -> dict:
        outline = raw.get("outline") or {}
        citation = None
        if chunks:
            chunk = chunks[0]
            citation = {
                "source_type": "document_chunk", "source_id": chunk["id"], "chunk_id": chunk["id"],
                "document_id": chunk["document_id"],
                "locator": {"char_start": chunk.get("char_start"), "char_end": chunk.get("char_end")},
                "quote": chunk.get("text", "")[:300], "label": "Dokumen sumber",
            }
        generated = raw.get("generated_sections")
        source_sections = generated if isinstance(generated, list) else outline.get("sections") or []
        sections = []
        for fallback_index, section in enumerate(source_sections, 1):
            index = int(section.get("index", fallback_index - 1)) + 1 if isinstance(generated, list) else fallback_index
            content = str(section.get("content", "")).strip()
            if not content:
                continue
            sections.append({
                "id": f"section-{index}", "title": section.get("title") or f"Bagian {index}",
                "content_markdown": content,
                "paragraphs": [content],
                "citations": [citation] if citation else [],
                "completed_at": section.get("completed_at") or raw.get("updated_at"),
            })
        return {
            "id": raw.get("report_id") or identifier("report"), "version": 1,
            "title": outline.get("title") or "Laporan Prediksi Simulasi",
            "generated_by": "rekakebijakan-oasis-report-agent", "sections": sections, "risks": [],
            "citations": [citation] if citation else [], "markdown_content": raw.get("markdown_content", ""),
            "outline": outline, "agent_log": raw.get("agent_log", []), "console_log": raw.get("console_log", []),
            "artifact_dir": raw.get("artifact_dir"), "status": raw.get("status"),
            "progress": raw.get("progress", 100 if raw.get("markdown_content") else 0),
            "active_task": raw.get("message"), "current_section": raw.get("current_section"),
        }

    def _update_oasis_report_progress(self, state: dict, raw: dict, chunks: list[dict]) -> None:
        partial = self._project_oasis_report(raw, chunks)
        state.setdefault("report", {}).update(partial)
        progress = max(0, min(99, int(raw.get("progress", 0) or 0)))
        state["stages"]["report"].update(
            status="running", progress=min(69, max(15, progress)),
            active_task=raw.get("message") or "Menyusun laporan",
        )
        self._touch(state)
        self._sync_stages(state)

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

    def _oasis_progress(self, state: dict, runtime: dict, progress: int) -> None:
        state.setdefault("simulation", {})["runtime"] = runtime
        self._progress(
            state, "simulation", min(69, max(15, progress)),
            f"OASIS ronde {runtime.get('current_round', 0)}/{runtime.get('total_rounds', 0)}",
        )

    def _oasis_graph_sync_progress(self, state: dict, runtime: dict, action_count: int) -> None:
        state.setdefault("simulation", {})["runtime"] = runtime
        self._progress(
            state, "simulation", 85,
            f"Menyinkronkan {action_count} aksi ke graph Zep",
        )

    def _complete(self, state: dict, stage: str, result: dict) -> None:
        upgrade_state(state)
        for key, value in result.items():
            state[key].update(value)
        state["stages"][stage].update(
            status="completed", progress=100, active_task=None,
            completed_at=now(), error=None,
        )
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
        if (state.get("workflow_mode") == "quick_demo"
                and state.get("stages", {}).get("report", {}).get("status") != "completed"):
            raise ValueError("Laporan harus selesai sebelum interaksi")
        mapping = self.repository.get_oasis_mapping(simulation_id)
        if payload.get("tool") == "report" and mapping and mapping.get("zep_graph_id") and self.oasis_runtime:
            raw = self.oasis_runtime.report_chat(
                mapping.get("external_simulation_id") or simulation_id,
                mapping["zep_graph_id"], state["project"]["objective"], payload["question"],
                state.get("interactions", {}).get("messages", []),
                language=state.get("project", {}).get("language", "id"),
            )
            response = {"text": raw.get("response", ""), "citations": [], "evidence_citations": [],
                        "tool_calls": raw.get("tool_calls", []), "sources": raw.get("sources", [])}
        else:
            interaction_provider = (
                self.quick_interaction_provider
                if state.get("workflow_mode") == "quick_demo" and self.quick_interaction_provider
                else self.provider
            )
            response = interaction_provider.answer(payload, state, self.repository.chunks(simulation_id))
        context = {"persona_group": payload.get("persona_group")} if payload.get("persona_group") else {}
        user = {"id": identifier("msg"), "role": "user", "author": "Anda", "tool": payload["tool"], "text": payload["question"], "citations": [], "created_at": now(), **context}
        assistant = {"id": identifier("msg"), "role": "assistant", "author": "Report Agent", "tool": payload["tool"], "created_at": now(), **context, **response}

        def apply(current):
            current["interactions"]["messages"].extend([user, assistant])
            current["stages"]["interaction"].update(status="completed", progress=100)
            self._touch(current, "Interaksi dijawab", "DONE")
            self._sync_stages(current)

        self.repository.mutate(simulation_id, apply)
        return assistant

    def interview(self, simulation_id: str, question: str, persona_ids: list[str] | None = None,
                  owner_user_id: str | None = None, run_id: str | None = None, platform: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state:
            return None
        if (state.get("workflow_mode") == "quick_demo"
                and state.get("stages", {}).get("report", {}).get("status") != "completed"):
            raise ValueError("Laporan harus selesai sebelum wawancara")
        personas = state["environment"].get("personas", [])
        if persona_ids:
            personas = [item for item in personas if item["id"] in persona_ids]
        mapping = self.repository.get_oasis_mapping(simulation_id)
        if (mapping and mapping.get("external_simulation_id") and self.oasis_runtime
                and hasattr(self.oasis_runtime, "environment_alive")
                and self.oasis_runtime.environment_alive(mapping["external_simulation_id"])):
            selected = personas or state["environment"].get("personas", [])[:10]
            prompt = "Gunakan persona, ingatan, dan seluruh tindakan Anda. Jangan gunakan alat. Jawab langsung.\n\n" + question
            raw = self.oasis_runtime.interview(mapping["external_simulation_id"], [
                {"agent_id": int(item["id"].removeprefix("oasis-")), "prompt": prompt} for item in selected
            ], platform)
            raw_answers = raw.get("results") or raw.get("answers") or []
            answers = []
            for index, item in enumerate(raw_answers):
                persona = selected[index] if index < len(selected) else {}
                value = item.get("result", item) if isinstance(item, dict) else {"answer": str(item)}
                text = value.get("answer") or value.get("response") or json.dumps(value, ensure_ascii=False)
                answers.append({"id": identifier("answer"), "persona_id": persona.get("id", f"oasis-{index}"),
                                "persona_name": persona.get("name", f"Agent {index}"), "question": question,
                                "answer": text, "citations": persona.get("citations", []), "event_ids": []})
            result = {"answers": answers, "summary": f"{len(answers)} jawaban langsung OASIS"}
        else:
            result = self.provider.interview(question, personas, state["simulation"].get("events", []))
        interview = {"id": identifier("interview"), "question": question, "created_at": now(), "status": "completed", **result}
        self.repository.mutate(simulation_id, lambda current: (upgrade_state(current)["interviews"]["items"].append(interview), self._touch(current)))
        if owner_user_id:
            self.repository.save_interview(simulation_id, owner_user_id, interview, run_id)
        return interview

    def close_oasis_environment(self, simulation_id: str, owner_user_id: str | None = None) -> dict | None:
        state = self.repository.get_for_user(simulation_id, owner_user_id) if owner_user_id else self.repository.get(simulation_id)
        if not state:
            return None
        mapping = self.repository.get_oasis_mapping(simulation_id)
        if not mapping or not mapping.get("external_simulation_id") or not self.oasis_runtime:
            raise ValueError("OASIS environment is not available")
        result = self.oasis_runtime.stop_simulation(mapping["external_simulation_id"])
        self.repository.upsert_oasis_mapping(simulation_id, state["project"]["id"], {
            "external_project_id": mapping.get("external_project_id"),
            "external_simulation_id": mapping["external_simulation_id"],
            "zep_graph_id": mapping.get("zep_graph_id"), "graph_revision": mapping.get("graph_revision", 0),
            "status": "closed", "config": mapping.get("config") or {},
            "runtime_status": dict(mapping.get("runtime_status") or {}) | {"environment_alive": False},
            "artifacts": mapping.get("artifacts") or {}, "metadata": mapping.get("metadata") or {},
        })
        return result | {"environment_alive": False}

    def apply_graph_feedback(self, simulation_id: str, payload: dict, owner_user_id: str) -> dict | None:
        def apply(state):
            if state.get("workflow_mode") == "quick_demo":
                raise ValueError("Graf pada proyek ini dikunci dan tidak dapat diubah")
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
