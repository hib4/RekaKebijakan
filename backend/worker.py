import logging
import os
import time
from app.config import Settings
from app.providers import make_provider
from app.oasis_runtime import OasisRuntimeClient
from app.repository import Repository
from app.service import WorkflowService
from app.storage import make_storage_backend


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("rekakebijakan.worker")


def main() -> None:
    settings = Settings.load({"EMBEDDED_WORKER": False})
    repository = Repository(settings.database_url, project_retention_days=settings.project_retention_days)
    workflow = WorkflowService(
        repository, make_provider(settings), settings.upload_dir, settings.job_delay,
        settings.chunk_size, settings.chunk_overlap, False, settings.worker_lease_seconds,
        make_storage_backend(settings),
        settings.max_active_projects_per_user, settings.max_files_per_project,
        settings.max_file_upload_bytes, settings.max_total_upload_bytes,
        settings.max_pdf_pages, settings.max_extracted_chars, settings.max_chunks_per_document,
        OasisRuntimeClient(settings.oasis_runtime_base_url, settings.oasis_runtime_service_token)
        if settings.oasis_runtime_enabled else None,
    )
    logger.info("Worker %s started", workflow.worker_id)
    try:
        while True:
            try:
                workflow.purge_due_projects()
            except Exception:
                logger.exception("Pending-delete purge failed; it will be retried")
            if not workflow.run_once():
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        workflow.shutdown()
        repository.close()


if __name__ == "__main__":
    main()
