"""
Router per l'autenticazione locale e gestione sessioni utente (v1.6.0 Modulo 1).
Fornisce rotte per login, logout, verifica stato sessione e catalogo permessi RBAC.
"""

import json
import logging
from typing import Optional
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.routers.dependencies import get_current_user, _extract_token_from_request
from app.services.auth_service import auth_service
from app.services.db import db_service
from app.services.rate_limiter import auth_rate_limiter, get_client_ip
from app.i18n import log_event, tr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/local", tags=["Local Authentication"])


class LocalAdminSetupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Nome utente amministratore")
    password: str = Field(..., min_length=6, max_length=128, description="Password amministratore")
    display_name: Optional[str] = Field(None, max_length=60, description="Nome visualizzato opzionale")
    remember_me: Optional[bool] = Field(False, description="Se True, sessione persistente (7 giorni), altrimenti volatile")


class LocalLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Nome utente locale registrato")
    password: str = Field(..., min_length=1, description="Password in chiaro")
    remember_me: Optional[bool] = Field(False, description="Se True, sessione persistente (7 giorni), altrimenti volatile")


@router.get("/status")
async def get_local_auth_status():
    """
    Restituisce lo stato dell'autenticazione locale, indicando se è richiesto
    il setup iniziale dell'amministratore (nessun admin configurato).
    """
    setup_required = await db_service.is_admin_setup_required()
    return {
        "status": "success",
        "setup_required": setup_required
    }


@router.post("/setup")
async def setup_initial_admin(payload: LocalAdminSetupRequest, request: Request, response: Response):
    """
    Esegue il primo setup dell'amministratore (Setup Wizard) quando nessun admin è registrato.
    Crea l'account admin iniziale con pieni permessi RBAC e restituisce il token di sessione.
    """
    setup_required = await db_service.is_admin_setup_required()
    if not setup_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=tr("auth.setup_already_done")
        )

    username = payload.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=tr("auth.invalid_username")
        )

    p_hash, p_salt = auth_service.hash_password(payload.password)
    from app.services.auth_service import ALL_PERMISSION_KEYS
    all_perms_json = json.dumps(ALL_PERMISSION_KEYS)
    display_name = (payload.display_name or "").strip() or username.capitalize()

    async with db_service._write_lock:
        async with aiosqlite.connect(db_service.db_path, timeout=60.0) as db:
            await db.execute("PRAGMA busy_timeout = 60000;")
            cursor = await db.execute(
                """
                INSERT INTO local_users (username, display_name, role, password_hash, salt, is_admin, is_active, permissions_json, created_at)
                VALUES (?, ?, 'admin', ?, ?, 1, 1, ?, CURRENT_TIMESTAMP);
                """,
                (username, display_name, p_hash, p_salt, all_perms_json)
            )
            await db.commit()
            user_id = cursor.lastrowid

    duration_days = 7 if payload.remember_me else 1
    cookie_max_age = (7 * 24 * 3600) if payload.remember_me else None

    token = await db_service.create_user_session(user_id=user_id, duration_days=duration_days)
    await db_service.update_user_last_login(user_id=user_id)

    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=cookie_max_age,
        httponly=True,
        samesite="lax",
        secure=is_https
    )

    clean_user = {
        "id": user_id,
        "username": username,
        "display_name": display_name,
        "role": "admin",
        "is_admin": True,
        "is_active": True,
        "permissions": ALL_PERMISSION_KEYS,
        "created_at": None,
        "last_login": None
    }

    log_event(logger, logging.INFO, "log_system.admin_setup_completed", username=username)
    return {
        "status": "success",
        "message": tr("auth.setup_completed"),
        "token": token,
        "remember_me": bool(payload.remember_me),
        "user": clean_user
    }


@router.post("/login")
async def local_login(payload: LocalLoginRequest, request: Request, response: Response):
    """
    Autentica un utente locale tramite username e password PBKDF2/SHA-256.
    Include protezione anti brute-force via sliding window rate limiter e cookie sicuro.
    """
    ip = get_client_ip(request)
    is_limited, retry_after = auth_rate_limiter.is_limited(ip)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=tr("auth.too_many_attempts", retry_after=retry_after),
            headers={"Retry-After": str(retry_after)},
        )

    username = payload.username.strip()
    user = await db_service.get_local_user_by_username(username)
    if not user:
        auth_rate_limiter.record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=tr("auth.invalid_credentials")
        )

    # Verifica password
    is_valid = auth_service.verify_password(
        payload.password,
        user.get("password_hash", ""),
        user.get("salt", "")
    )
    if not is_valid:
        auth_rate_limiter.record_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=tr("auth.invalid_credentials")
        )

    # Verifica se l'account è disattivato dall'amministratore
    if user.get("is_active") is False or user.get("is_active") == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tr("auth.account_disabled")
        )

    # Login riuscito: reset tentativi falliti per questo client IP
    auth_rate_limiter.reset(ip)

    user_id = user["id"]
    duration_days = 7 if payload.remember_me else 1
    cookie_max_age = (7 * 24 * 3600) if payload.remember_me else None

    token = await db_service.create_user_session(user_id=user_id, duration_days=duration_days)
    await db_service.update_user_last_login(user_id=user_id)

    # Impostazione cookie HTTP-only (Secure se su HTTPS o reverse proxy HTTPS)
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=cookie_max_age,
        httponly=True,
        samesite="lax",
        secure=is_https
    )

    clean_user = {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", ""),
        "role": user.get("role") or ("admin" if user.get("is_admin") else "operator"),
        "is_admin": user["is_admin"],
        "is_active": bool(user.get("is_active", 1)),
        "permissions": user["permissions"],
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login")
    }

    log_event(logger, logging.INFO, "log_system.user_logged_in", username=username)
    return {
        "status": "success",
        "token": token,
        "remember_me": bool(payload.remember_me),
        "user": clean_user
    }


@router.post("/logout")
async def local_logout(request: Request, response: Response):
    """
    Invalida il token di sessione attivo e rimuove il cookie HTTP-only.
    """
    token = _extract_token_from_request(request)
    if token:
        await db_service.delete_user_session(token)
    
    response.delete_cookie(key="session_token")
    return {
        "status": "success",
        "message": tr("auth.logged_out")
    }


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    """
    Restituisce le informazioni del profilo utente attualmente loggato e la lista dei suoi permessi.
    """
    return {
        "status": "success",
        "user": user
    }


@router.get("/permissions")
async def get_permissions_catalog():
    """
    Restituisce il catalogo descrittivo bilingue di tutti i permessi granulari supportati dalla dashboard.
    """
    catalog = auth_service.get_permissions_catalog()
    return {
        "status": "success",
        "data": catalog,
        "permissions": catalog.get("permissions", [])
    }


class SessionTimeoutRequest(BaseModel):
    minutes: int = Field(..., ge=0, le=1440, description="Minuti di inattività prima del logout automatico (0 = disattivato)")


@router.get("/session-timeout")
async def get_session_timeout():
    """Restituisce il timeout di inattività configurato in minuti (0 = disattivato)."""
    raw_val = await db_service.get_setting("session_timeout_minutes", "15")
    try:
        minutes = int(raw_val)
    except (TypeError, ValueError):
        minutes = 15
    return {
        "status": "success",
        "session_timeout_minutes": minutes
    }


@router.post("/session-timeout")
async def set_session_timeout(payload: SessionTimeoutRequest):
    """Aggiorna il timeout di inattività per il logout automatico in minuti."""
    await db_service.set_setting("session_timeout_minutes", str(payload.minutes))
    log_event(logger, logging.INFO, "log_system.session_timeout_updated", minutes=payload.minutes)
    return {
        "status": "success",
        "session_timeout_minutes": payload.minutes,
        "message": tr("auth.session_timeout_set", minutes=payload.minutes) if payload.minutes > 0 else tr("auth.session_timeout_disabled")
    }

