from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_path: Path
    upload_dir: Path
    max_upload_bytes: int
    job_delay: float
    testing: bool
    cors_origins: list[str]
    session_cookie_name: str
    session_ttl_seconds: int
    session_cookie_secure: bool

    @classmethod
    def load(cls, overrides: dict | None = None) -> "Settings":
        load_dotenv()
        root = Path(__file__).resolve().parent.parent
        data_dir = Path(os.getenv("DATA_DIR", root / "data"))
        values = {
            "DATABASE_PATH": os.getenv("DATABASE_PATH", data_dir / "rekakebijakan.sqlite3"),
            "UPLOAD_DIR": os.getenv("UPLOAD_DIR", data_dir / "uploads"),
            "MAX_UPLOAD_BYTES": int(os.getenv("MAX_UPLOAD_BYTES", 16 * 1024 * 1024)),
            "JOB_DELAY": float(os.getenv("JOB_DELAY", "0.08")),
            "TESTING": False,
            "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
            "SESSION_COOKIE_NAME": os.getenv("SESSION_COOKIE_NAME", "rk_session"),
            "SESSION_TTL_SECONDS": int(os.getenv("SESSION_TTL_SECONDS", 7 * 24 * 60 * 60)),
            "SESSION_COOKIE_SECURE": os.getenv("SESSION_COOKIE_SECURE", "false"),
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
        return cls(
            database_path=Path(values["DATABASE_PATH"]),
            upload_dir=Path(values["UPLOAD_DIR"]),
            max_upload_bytes=int(values["MAX_UPLOAD_BYTES"]),
            job_delay=float(values["JOB_DELAY"]),
            testing=bool(values["TESTING"]),
            cors_origins=list(origins),
            session_cookie_name=str(values["SESSION_COOKIE_NAME"]),
            session_ttl_seconds=int(values["SESSION_TTL_SECONDS"]),
            session_cookie_secure=bool(secure),
        )
