from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field


SESSION_COOKIE_NAME = "public_auth_session"
SESSION_COOKIE_PATH = "/"
SIGNUP_BONUS_CENTS = 100


class PublicAuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class PublicAuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


def register_public_auth_routes(router: APIRouter, *, auth_service, billing_store) -> None:
    @router.post("/api/public-auth/register")
    async def register(body: PublicAuthRegisterRequest, response: Response):
        user = _create_user(billing_store, auth_service, body.username, body.password)
        token, _ = auth_service.create_session(user["id"])
        _set_session_cookie(response, token)
        return {"user": user}

    @router.post("/api/public-auth/login")
    async def login(body: PublicAuthLoginRequest, response: Response):
        user = billing_store.get_user_auth_by_username(body.username)
        if user is None or not auth_service.verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail={"error": "invalid credentials"})
        token, _ = auth_service.create_session(user["id"])
        _set_session_cookie(response, token)
        return {"user": _public_user(user)}

    @router.post("/api/public-auth/logout")
    async def logout(response: Response, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
        if session_token:
            auth_service.delete_session_by_token(session_token)
        response.delete_cookie(SESSION_COOKIE_NAME, path=SESSION_COOKIE_PATH)
        return {"ok": True}

    @router.get("/api/public-auth/me")
    async def me(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
        user = _require_session(auth_service, session_token)
        return {"user": user}

    @router.post("/api/public-auth/redeem")
    async def redeem(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
        _require_session(auth_service, session_token)
        raise HTTPException(status_code=501, detail={"error": "redeem is not implemented yet"})


def _create_user(billing_store, auth_service, username: str, password: str) -> dict[str, str]:
    try:
        return billing_store.create_user(
            username=username,
            password_hash=auth_service.hash_password(password),
            signup_bonus_cents=SIGNUP_BONUS_CENTS,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"error": "username already exists"}) from exc


def _require_session(auth_service, session_token: str | None) -> dict[str, str]:
    if not session_token:
        raise HTTPException(status_code=401, detail={"error": "login required"})
    user = auth_service.get_user_by_session_token(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "login required"})
    return _public_user(user)


def _public_user(user: dict[str, str]) -> dict[str, str]:
    return {
        "id": user["id"],
        "username": user["username"],
        "balance": user["balance"],
        "status": user["status"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
