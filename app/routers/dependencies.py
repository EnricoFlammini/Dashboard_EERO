"""
Dependency Injection per autenticazione locale e controllo accessi RBAC (v1.6.0 Modulo 1).
Fornisce get_current_user, require_admin e require_permission(perm_key).
"""

import logging
from typing import Any, Callable, Dict, Optional
from fastapi import Depends, HTTPException, Request, status
from app.config import settings
from app.services.db import db_service

logger = logging.getLogger(__name__)


def _extract_token_from_request(request: Request) -> Optional[str]:
    """Estrae il token di sessione dall'header Authorization (Bearer), dai cookie o dai query params."""
    # 1. Header Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.strip():
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        elif len(parts) == 1:
            return parts[0].strip()

    # 2. Cookie session_token
    cookie_token = request.cookies.get("session_token")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    # 3. Query param opzionale token
    query_token = request.query_params.get("token")
    if query_token and query_token.strip():
        return query_token.strip()

    return None


async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Restituisce l'utente autenticato se è presente una sessione valida, altrimenti None."""
    token = _extract_token_from_request(request)
    if not token:
        return None
    
    user = await db_service.get_user_by_session_token(token)
    if not user:
        return None
    return user


async def get_current_user(
    request: Request,
    user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Richiede obbligatoriamente un utente autenticato con sessione valida (HTTP 401 se assente)."""
    if not user:
        token = _extract_token_from_request(request)
        detail = "Sessione non valida o scaduta" if token else "Autenticazione richiesta"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Richiede privilegi di superamministratore (is_admin=True), bloccando con HTTP 403 Forbidden."""
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operazione riservata esclusivamente agli amministratori."
        )
    return user


def require_permission(perm_key: str) -> Callable:
    """
    Dependency injection factory per la protezione granulare delle rotte operative.
    - Se l'utente è un amministratore (is_admin=True), l'operazione è sempre consentita.
    - Se l'utente possiede il permesso perm_key, l'operazione è consentita.
    - Se l'utente non possiede il permesso richiesto, blocca tassativamente con HTTP 403 Forbidden.
    - Se la richiesta non include un token:
        - Se è stato fornito un token non valido/scaduto, solleva HTTP 401.
        - Se require_local_auth è abilitato da env, solleva HTTP 401.
        - Altrimenti consente l'operazione in modalità legacy/unauthenticated.
    """
    async def _dependency(
        request: Request,
        user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
    ) -> Optional[Dict[str, Any]]:
        raw_token = _extract_token_from_request(request)
        
        # Token fornito ma non valido o scaduto
        if raw_token and not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessione non valida o scaduta",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user:
            # Superadmin bypass
            if user.get("is_admin"):
                return user
            
            perms = set(user.get("permissions") or [])
            alias_map = {
                "action_pause_devices": {"action_pause_devices", "action_manage_schedules"},
                "action_manage_schedules": {"action_manage_schedules", "action_pause_devices"},
                "view_clients": {"view_clients", "view_devices"},
                "view_devices": {"view_devices", "view_clients"},
                "view_analytics": {"view_analytics", "view_speedtest"},
                "view_speedtest": {"view_speedtest", "view_analytics"},
            }
            allowed_keys = alias_map.get(perm_key, {perm_key})
            if perms.intersection(allowed_keys) or "*" in perms:
                return user
            
            logger.warning(
                f"Accesso negato: utente '{user.get('username')}' non ha il permesso richiesto '{perm_key}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permesso non sufficiente: richiesta autorizzazione '{perm_key}'."
            )

        # Nessun token fornito
        if getattr(settings, "require_local_auth", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Autenticazione richiesta per questa operazione",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return None

    return _dependency
