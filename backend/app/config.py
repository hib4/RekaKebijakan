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
        )
