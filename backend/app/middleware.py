from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


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
