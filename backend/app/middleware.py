from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import Headers
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .metrics import metrics

logger = logging.getLogger("rekakebijakan.access")
request_id_pattern = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestSecurityMiddleware:
    def __init__(self, app: ASGIApp, production: bool):
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied_id = Headers(scope=scope).get("x-request-id", "")
        request_id = supplied_id if request_id_pattern.fullmatch(supplied_id) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def secure_send(message: Message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                if self.production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        try:
            await self.app(scope, receive, secure_send)
        finally:
            duration_seconds = time.perf_counter() - started
            duration_ms = duration_seconds * 1000
            metrics.observe_request(scope["method"], scope.get("path", ""), status_code, duration_seconds)
            logger.info(
                "%s %s %s %.2fms request_id=%s",
                scope["method"],
                scope.get("path", ""),
                status_code,
                duration_ms,
                request_id,
            )


def too_large_response() -> JSONResponse:
    message = "Berkas terlalu besar"
    return JSONResponse(
        {"error": {"code": "payload_too_large", "message": message}, "message": message},
        status_code=413,
    )


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > self.max_bytes:
            await too_large_response()(scope, receive, send)
            return
        received = 0

        class PayloadTooLarge(Exception):
            pass

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise PayloadTooLarge
            return message
        try:
            await self.app(scope, limited_receive, send)
        except PayloadTooLarge:
            await too_large_response()(scope, receive, send)


class OriginValidationMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: list[str], cookie_name: str):
        self.app = app
        self.allowed_origins = set(allowed_origins)
        self.cookie_name = cookie_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope["method"] not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if origin and origin not in self.allowed_origins:
                message = "Origin permintaan tidak diizinkan"
                response = JSONResponse(
                    {"error": {"code": "invalid_origin", "message": message}, "message": message},
                    status_code=403,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
