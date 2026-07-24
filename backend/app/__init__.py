from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from .api import public_router, router
from .auth import router as auth_router
from .config import Settings
from .errors import ApiError
from .middleware import OriginValidationMiddleware, RequestSizeLimitMiddleware
from .repository import Repository
from .service import WorkflowService

logger = logging.getLogger("rekakebijakan")


def error_response(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = jsonable_encoder(details)
    return JSONResponse({"error": error, "message": message}, status_code=status_code)


def create_app(config: dict | None = None) -> FastAPI:
    settings = Settings.load(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        alembic_config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")
        repository = Repository(settings.database_url)
        service = WorkflowService(repository, settings.upload_dir, settings.job_delay)
        app.state.settings = settings
        app.state.repository = repository
        app.state.workflow = service
        service.recover()
        try:
            yield
        finally:
            service.shutdown()
            repository.close()

    app = FastAPI(title="RekaKebijakan API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_upload_bytes)
    app.add_middleware(
        OriginValidationMiddleware,
        allowed_origins=settings.cors_origins,
        cookie_name=settings.session_cookie_name,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(public_router)
    app.include_router(auth_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "rekakebijakan", "engine": "deterministic-demo"}

    @app.get("/ready")
    async def ready(request: Request):
        request.app.state.repository.ping()
        return {"status": "ok", "database": "postgresql"}

    @app.exception_handler(ApiError)
    async def api_error(_request: Request, error: ApiError):
        return error_response(error.status_code, error.code, error.message, error.details)

    @app.exception_handler(ValidationError)
    async def validation_error(_request: Request, error: ValidationError):
        return error_response(422, "validation_error", "Input tidak valid", error.errors(include_url=False))

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(_request: Request, error: RequestValidationError):
        return error_response(422, "validation_error", "Input tidak valid", error.errors())

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException):
        if error.status_code == 404:
            return error_response(404, "not_found", "Sumber daya tidak ditemukan")
        message = str(error.detail) if error.detail else "Permintaan tidak dapat diproses"
        return error_response(error.status_code, "http_error", message)

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, error: Exception):
        logger.exception("Unhandled API error", exc_info=error)
        return error_response(500, "internal_error", "Terjadi kesalahan internal")

    return app
