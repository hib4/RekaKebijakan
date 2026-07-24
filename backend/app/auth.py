from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, Request, Response
from pwdlib import PasswordHash

from .errors import AuthenticationRequired, EmailConflict
from .models import LoginInput, RegisterInput

router = APIRouter(prefix="/api/auth", tags=["auth"])
password_hash = PasswordHash.recommended()


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
    user = request.app.state.repository.create_user(
        f"user_{uuid.uuid4().hex}", payload.name, payload.email, password_hash.hash(payload.password)
    )
    if not user:
        raise EmailConflict()
    set_session(request, response, user["id"])
    return {"user": public_user(user)}


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response):
    user = request.app.state.repository.user_by_email(payload.email)
    if not user or not password_hash.verify(payload.password, user["password_hash"]):
        raise AuthenticationRequired("Email atau kata sandi salah")
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
