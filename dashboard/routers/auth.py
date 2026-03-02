"""Authentication routes: login, logout, session check."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from dashboard.deps import (
    COOKIE_NAME,
    SESSION_TTL,
    create_session_token,
    get_settings,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    ok: bool
    username: str = ""
    error: str = ""


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, response: Response):
    settings = get_settings()
    if not settings.dashboard_user or not settings.dashboard_pass:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard credentials not configured.",
        )

    user_ok = secrets.compare_digest(
        req.username.encode("utf-8"),
        settings.dashboard_user.encode("utf-8"),
    )
    pass_ok = secrets.compare_digest(
        req.password.encode("utf-8"),
        settings.dashboard_pass.encode("utf-8"),
    )
    if not (user_ok and pass_ok):
        return LoginResponse(ok=False, error="Invalid username or password")

    token = create_session_token(req.username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return LoginResponse(ok=True, username=req.username)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}
