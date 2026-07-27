from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from .api import public_router, router, v1_router
from .auth import LoginRateLimiter, router as auth_router
from .config import Settings
from .errors import ApiError
from .middleware import OriginValidationMiddleware, RequestSecurityMiddleware, RequestSizeLimitMiddleware
from .metrics import metrics
from .oasis_runtime import OasisRuntimeClient
from .repository import Repository
from .providers import make_provider
from .service import WorkflowService
from .storage import make_storage_backend
from starlette.middleware.trustedhost import TrustedHostMiddleware

logger = logging.getLogger("rekakebijakan")


def error_response(status_code: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = jsonable_encoder(details)
    return JSONResponse({"error": error, "message": message}, status_code=status_code, headers=headers)


def create_app(config: dict | None = None) -> FastAPI:
    settings = Settings.load(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        repository = Repository(settings.database_url, project_retention_days=settings.project_retention_days)
        provider = make_provider(settings)
        storage = make_storage_backend(settings)
        service = WorkflowService(
            repository,
            provider,
            settings.upload_dir,
            settings.job_delay,
            settings.chunk_size,
            settings.chunk_overlap,
            settings.embedded_worker,
            settings.worker_lease_seconds,
            storage,
            settings.max_active_projects_per_user,
            settings.max_files_per_project,
            settings.max_file_upload_bytes,
            settings.max_total_upload_bytes,
            settings.max_pdf_pages,
            settings.max_extracted_chars,
            settings.max_chunks_per_document,
            OasisRuntimeClient(settings.oasis_runtime_base_url, settings.oasis_runtime_service_token)
            if settings.oasis_runtime_enabled else None,
        )
        app.state.settings = settings
        app.state.repository = repository
        app.state.workflow = service
        app.state.storage = storage
        service.recover()
        try:
            yield
        finally:
            service.shutdown()
            repository.close()

    app = FastAPI(title="RekaKebijakan API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.login_limiter = LoginRateLimiter(settings.auth_max_failures, settings.auth_window_seconds)
    app.state.registration_limiter = LoginRateLimiter(settings.auth_max_failures, settings.auth_window_seconds)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
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
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestSecurityMiddleware, production=settings.production)
    app.include_router(router)
    app.include_router(v1_router)
    app.include_router(public_router)
    app.include_router(auth_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "rekakebijakan", "engine": settings.policy_provider}

    @app.get("/ready")
    async def ready(request: Request):
        request.app.state.repository.ping()
        request.app.state.storage.healthcheck()
        return {
            "status": "ok",
            "database": "postgresql",
            "schema_revision": request.app.state.repository.schema_revision(),
            "storage": settings.storage_backend,
        }

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics(request: Request):
        queue = request.app.state.repository.operational_metrics()
        return PlainTextResponse(metrics.render(queue), media_type="text/plain; version=0.0.4")

    @app.exception_handler(ApiError)
    async def api_error(_request: Request, error: ApiError):
        return error_response(error.status_code, error.code, error.message, error.details, error.headers)

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
