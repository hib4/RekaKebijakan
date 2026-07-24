from __future__ import annotations

import secrets
import hashlib
import math
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request, Response
from pwdlib import PasswordHash

from .errors import AuthenticationRequired, EmailConflict, RateLimitExceeded
from .models import LoginInput, RegisterInput

router = APIRouter(prefix="/api/auth", tags=["auth"])
password_hash = PasswordHash.recommended()
dummy_password_hash = password_hash.hash("not-a-real-account-password")


class LoginRateLimiter:
    def __init__(self, max_failures: int, window_seconds: int):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.attempts: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    @staticmethod
    def client_key(request: Request) -> str:
        client = request.client.host if request.client else "unknown"
        return f"client:{client}"

    @staticmethod
    def account_key(email: str) -> str:
        email_digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return f"account:{email_digest}"

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self.lock:
            attempts = self.attempts[key]
            while attempts and attempts[0] <= now - self.window_seconds:
                attempts.popleft()
            if len(attempts) < self.max_failures:
                return 0
            return max(1, math.ceil(self.window_seconds - (now - attempts[0])))

    def record_failure(self, key: str):
        with self.lock:
            self.attempts[key].append(time.monotonic())

    def reset(self, key: str):
        with self.lock:
            self.attempts.pop(key, None)


def public_user(user: dict) -> dict:
    return {key: user[key] for key in ("id", "name", "email", "created_at")}


def current_user(request: Request) -> dict:
    cached = getattr(request.state, "current_user", None)
    if cached:
        return cached
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if not token:
        raise AuthenticationRequired()
    user = request.app.state.repository.user_for_session(token)
    if not user:
        raise AuthenticationRequired("Sesi tidak valid atau sudah kedaluwarsa")
    request.state.current_user = user
    return user


def set_session(request: Request, response: Response, user_id: str):
    settings = request.app.state.settings
    token = secrets.token_urlsafe(32)
    request.app.state.repository.create_session(token, user_id, settings.session_ttl_seconds)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, response: Response):
    limiter = request.app.state.registration_limiter
    limit_key = limiter.client_key(request)
    retry_after = limiter.retry_after(limit_key)
    if retry_after:
        raise RateLimitExceeded(retry_after)
    limiter.record_failure(limit_key)
    user = request.app.state.repository.create_user(
        f"user_{uuid.uuid4().hex}", payload.name, payload.email, password_hash.hash(payload.password)
    )
    if not user:
        raise EmailConflict()
    set_session(request, response, user["id"])
    return {"user": public_user(user)}


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response):
    limiter = request.app.state.login_limiter
    limit_keys = (limiter.client_key(request), limiter.account_key(payload.email))
    retry_after = max(limiter.retry_after(key) for key in limit_keys)
    if retry_after:
        raise RateLimitExceeded(retry_after)
    user = request.app.state.repository.user_by_email(payload.email)
    password_matches = password_hash.verify(
        payload.password,
        user["password_hash"] if user else dummy_password_hash,
    )
    if not user or not password_matches:
        for key in limit_keys:
            limiter.record_failure(key)
        raise AuthenticationRequired("Email atau kata sandi salah")
    for key in limit_keys:
        limiter.reset(key)
    set_session(request, response, user["id"])
    return {"user": public_user(user)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response):
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        request.app.state.repository.delete_session(token)
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.session_cookie_secure, samesite="lax")
    return {"ok": True}
