"""
Router per l'autenticazione locale e gestione sessioni utente (v1.6.0 Modulo 1).
Fornisce rotte per login, logout, verifica stato sessione e catalogo permessi RBAC.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.routers.dependencies import get_current_user, _extract_token_from_request
from app.services.auth_service import auth_service
from app.services.db import db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/local", tags=["Local Authentication"])


class LocalLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Nome utente locale registrato")
    password: str = Field(..., min_length=1, description="Password in chiaro")


@router.post("/login")
async def local_login(payload: LocalLoginRequest, response: Response):
    """
    Autentica un utente locale tramite username e password PBKDF2/SHA-256.
    Restituisce un session token e imposta un cookie HTTP-only sicuro.
    """
    username = payload.username.strip()
    user = await db_service.get_local_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide (username o password errati)."
        )

    # Verifica password
    is_valid = auth_service.verify_password(
        payload.password,
        user.get("password_hash", ""),
        user.get("salt", "")
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide (username o password errati)."
        )

    # Verifica se l'account è disattivato dall'amministratore
    if user.get("is_active") is False or user.get("is_active") == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disattivato dall'amministratore. Contatta l'amministratore di sistema."
        )

    user_id = user["id"]
    token = await db_service.create_user_session(user_id=user_id, duration_days=7)
    await db_service.update_user_last_login(user_id=user_id)

    # Impostazione cookie HTTP-only
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=False  # Consentito anche su reti locali HTTP standard
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

    logger.info(f"Local Auth: Utente '{username}' autenticato con successo.")
    return {
        "status": "success",
        "token": token,
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
        "message": "Sessione terminata con successo."
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
    logger.info(f"Local Auth: Aggiornato timeout inattività a {payload.minutes} minuti.")
    return {
        "status": "success",
        "session_timeout_minutes": payload.minutes,
        "message": f"Timeout sessione impostato a {payload.minutes} minuti." if payload.minutes > 0 else "Logout automatico disattivato."
    }

