from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    upload_dir: Path
    max_upload_bytes: int
    job_delay: float
    testing: bool
    cors_origins: list[str]
    session_cookie_name: str
    session_ttl_seconds: int
    session_cookie_secure: bool
    policy_provider: str
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str
    chunk_size: int
    chunk_overlap: int
    provider_timeout_seconds: float
    embedded_worker: bool
    worker_poll_seconds: float
    worker_lease_seconds: int
    storage_backend: str
    storage_path: Path
    s3_bucket: str | None
    s3_prefix: str
    s3_endpoint_url: str | None
    s3_region: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None
    trusted_hosts: list[str]
    production: bool
    auth_max_failures: int
    auth_window_seconds: int
    project_retention_days: int
    max_active_projects_per_user: int
    max_files_per_project: int
    max_file_upload_bytes: int
    max_total_upload_bytes: int
    max_pdf_pages: int
    max_extracted_chars: int
    max_chunks_per_document: int

    @classmethod
    def load(cls, overrides: dict | None = None) -> "Settings":
        load_dotenv()
        root = Path(__file__).resolve().parent.parent
        data_dir = Path(os.getenv("DATA_DIR", root / "data"))
        values = {
            "DATABASE_URL": os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://rekakebijakan:rekakebijakan@localhost:5432/rekakebijakan",
            ),
            "UPLOAD_DIR": os.getenv("UPLOAD_DIR", data_dir / "uploads"),
            "MAX_UPLOAD_BYTES": int(os.getenv("MAX_UPLOAD_BYTES", 16 * 1024 * 1024)),
            "JOB_DELAY": float(os.getenv("JOB_DELAY", "0.08")),
            "TESTING": False,
            "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
            "SESSION_COOKIE_NAME": os.getenv("SESSION_COOKIE_NAME", "rk_session"),
            "SESSION_TTL_SECONDS": int(os.getenv("SESSION_TTL_SECONDS", 7 * 24 * 60 * 60)),
            "SESSION_COOKIE_SECURE": os.getenv("SESSION_COOKIE_SECURE", "false"),
            "POLICY_PROVIDER": os.getenv("POLICY_PROVIDER", "deterministic"),
            "LLM_BASE_URL": os.getenv("LLM_BASE_URL") or None,
            "LLM_API_KEY": os.getenv("LLM_API_KEY") or None,
            "LLM_MODEL": os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "CHUNK_SIZE": int(os.getenv("CHUNK_SIZE", "1200")),
            "CHUNK_OVERLAP": int(os.getenv("CHUNK_OVERLAP", "150")),
            "PROVIDER_TIMEOUT_SECONDS": float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "120")),
            "EMBEDDED_WORKER": os.getenv("EMBEDDED_WORKER", "false"),
            "WORKER_POLL_SECONDS": float(os.getenv("WORKER_POLL_SECONDS", "0.5")),
            "WORKER_LEASE_SECONDS": int(os.getenv("WORKER_LEASE_SECONDS", "180")),
            "STORAGE_BACKEND": os.getenv("STORAGE_BACKEND", "local"),
            "STORAGE_PATH": os.getenv("STORAGE_PATH", os.getenv("UPLOAD_DIR", data_dir / "uploads")),
            "S3_BUCKET": os.getenv("S3_BUCKET") or None,
            "S3_PREFIX": os.getenv("S3_PREFIX", "rekakebijakan"),
            "S3_ENDPOINT_URL": os.getenv("S3_ENDPOINT_URL") or None,
            "S3_REGION": os.getenv("S3_REGION") or None,
            "S3_ACCESS_KEY_ID": os.getenv("S3_ACCESS_KEY_ID") or None,
            "S3_SECRET_ACCESS_KEY": os.getenv("S3_SECRET_ACCESS_KEY") or None,
            "TRUSTED_HOSTS": os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver"),
            "PRODUCTION": os.getenv("PRODUCTION", "false"),
            "AUTH_MAX_FAILURES": int(os.getenv("AUTH_MAX_FAILURES", "10")),
            "AUTH_WINDOW_SECONDS": int(os.getenv("AUTH_WINDOW_SECONDS", "300")),
            "PROJECT_RETENTION_DAYS": int(os.getenv("PROJECT_RETENTION_DAYS", "30")),
            "MAX_ACTIVE_PROJECTS_PER_USER": int(os.getenv("MAX_ACTIVE_PROJECTS_PER_USER", "100")),
            "MAX_FILES_PER_PROJECT": int(os.getenv("MAX_FILES_PER_PROJECT", "20")),
            "MAX_FILE_UPLOAD_BYTES": int(os.getenv("MAX_FILE_UPLOAD_BYTES", 16 * 1024 * 1024)),
            "MAX_TOTAL_UPLOAD_BYTES": int(os.getenv("MAX_TOTAL_UPLOAD_BYTES", 1024 * 1024 * 1024)),
            "MAX_PDF_PAGES": int(os.getenv("MAX_PDF_PAGES", "200")),
            "MAX_EXTRACTED_CHARS": int(os.getenv("MAX_EXTRACTED_CHARS", "2000000")),
            "MAX_CHUNKS_PER_DOCUMENT": int(os.getenv("MAX_CHUNKS_PER_DOCUMENT", "5000")),
        }
        values.update(overrides or {})
        origins = values["CORS_ORIGINS"]
        if isinstance(origins, str):
            origins = [item.strip() for item in origins.split(",") if item.strip()]
        if not origins or "*" in origins:
            raise ValueError("CORS_ORIGINS must contain explicit origins when credentials are enabled")
        secure = values["SESSION_COOKIE_SECURE"]
        if isinstance(secure, str):
            secure = secure.strip().lower() in {"1", "true", "yes", "on"}
        embedded_worker = values["EMBEDDED_WORKER"]
        if isinstance(embedded_worker, str):
            embedded_worker = embedded_worker.strip().lower() in {"1", "true", "yes", "on"}
        provider = str(values["POLICY_PROVIDER"]).strip().lower()
        if provider not in {"deterministic", "openai"}:
            raise ValueError("POLICY_PROVIDER must be deterministic or openai")
        storage_backend = str(values["STORAGE_BACKEND"]).strip().lower()
        if storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be local or s3")
        if storage_backend == "s3" and not values["S3_BUCKET"]:
            raise ValueError("S3_BUCKET is required for S3 storage")
        trusted_hosts = values["TRUSTED_HOSTS"]
        if isinstance(trusted_hosts, str):
            trusted_hosts = [item.strip() for item in trusted_hosts.split(",") if item.strip()]
        production = values["PRODUCTION"]
        if isinstance(production, str):
            production = production.strip().lower() in {"1", "true", "yes", "on"}
        if production and not secure:
            raise ValueError("SESSION_COOKIE_SECURE must be enabled in production")
        if int(values["AUTH_MAX_FAILURES"]) < 1 or int(values["AUTH_WINDOW_SECONDS"]) < 1:
            raise ValueError("Authentication rate-limit settings must be positive")
        limit_names = (
            "PROJECT_RETENTION_DAYS", "MAX_ACTIVE_PROJECTS_PER_USER", "MAX_FILES_PER_PROJECT",
            "MAX_FILE_UPLOAD_BYTES", "MAX_TOTAL_UPLOAD_BYTES", "MAX_PDF_PAGES",
            "MAX_EXTRACTED_CHARS", "MAX_CHUNKS_PER_DOCUMENT",
        )
        if any(int(values[name]) < 1 for name in limit_names):
            raise ValueError("Storage lifecycle and upload limits must be positive")
        return cls(
            database_url=str(values["DATABASE_URL"]),
            upload_dir=Path(values["UPLOAD_DIR"]),
            max_upload_bytes=int(values["MAX_UPLOAD_BYTES"]),
            job_delay=float(values["JOB_DELAY"]),
            testing=bool(values["TESTING"]),
            cors_origins=list(origins),
            session_cookie_name=str(values["SESSION_COOKIE_NAME"]),
            session_ttl_seconds=int(values["SESSION_TTL_SECONDS"]),
            session_cookie_secure=bool(secure),
            policy_provider=provider,
            llm_base_url=values["LLM_BASE_URL"],
            llm_api_key=values["LLM_API_KEY"],
            llm_model=str(values["LLM_MODEL"]),
            chunk_size=int(values["CHUNK_SIZE"]),
            chunk_overlap=int(values["CHUNK_OVERLAP"]),
            provider_timeout_seconds=float(values["PROVIDER_TIMEOUT_SECONDS"]),
            embedded_worker=bool(embedded_worker) or bool(values["TESTING"]),
            worker_poll_seconds=float(values["WORKER_POLL_SECONDS"]),
            worker_lease_seconds=int(values["WORKER_LEASE_SECONDS"]),
            storage_backend=storage_backend,
            storage_path=Path(values["STORAGE_PATH"]),
            s3_bucket=values["S3_BUCKET"],
            s3_prefix=str(values["S3_PREFIX"]),
            s3_endpoint_url=values["S3_ENDPOINT_URL"],
            s3_region=values["S3_REGION"],
            s3_access_key_id=values["S3_ACCESS_KEY_ID"],
            s3_secret_access_key=values["S3_SECRET_ACCESS_KEY"],
            trusted_hosts=list(trusted_hosts),
            production=bool(production),
            auth_max_failures=int(values["AUTH_MAX_FAILURES"]),
            auth_window_seconds=int(values["AUTH_WINDOW_SECONDS"]),
            project_retention_days=int(values["PROJECT_RETENTION_DAYS"]),
            max_active_projects_per_user=int(values["MAX_ACTIVE_PROJECTS_PER_USER"]),
            max_files_per_project=int(values["MAX_FILES_PER_PROJECT"]),
            max_file_upload_bytes=int(values["MAX_FILE_UPLOAD_BYTES"]),
            max_total_upload_bytes=int(values["MAX_TOTAL_UPLOAD_BYTES"]),
            max_pdf_pages=int(values["MAX_PDF_PAGES"]),
            max_extracted_chars=int(values["MAX_EXTRACTED_CHARS"]),
            max_chunks_per_document=int(values["MAX_CHUNKS_PER_DOCUMENT"]),
        )
