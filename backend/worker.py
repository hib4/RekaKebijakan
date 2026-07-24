import logging
import os
import time
from app.config import Settings
from app.providers import make_provider
from app.repository import Repository
from app.service import WorkflowService


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("rekakebijakan.worker")


def main() -> None:
    settings = Settings.load({"EMBEDDED_WORKER": False})
    repository = Repository(settings.database_url)
    workflow = WorkflowService(
        repository, make_provider(settings), settings.upload_dir, settings.job_delay,
        settings.chunk_size, settings.chunk_overlap, False, settings.worker_lease_seconds,
    )
    logger.info("Worker %s started", workflow.worker_id)
    try:
        while True:
            if not workflow.run_once():
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        workflow.shutdown()
        repository.close()


if __name__ == "__main__":
    main()
