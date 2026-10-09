"""
Router CRUD per la gestione degli utenti locali (v1.6.0 Modulo 1).
Tutte le operazioni sono riservate esclusivamente agli amministratori (require_admin).
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.routers.dependencies import require_admin
from app.services.auth_service import auth_service, ALL_PERMISSION_KEYS
from app.services.db import db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["Local Users Management"])


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="Nome utente univoco")
    password: str = Field(..., min_length=4, max_length=128, description="Password in chiaro")
    display_name: Optional[str] = Field("", max_length=100, description="Nome visualizzato utente")
    role: Optional[str] = Field("operator", max_length=50, description="Ruolo utente (admin, operator, viewer)")
    is_admin: Optional[bool] = Field(False, description="Flag per privilegi di amministratore")
    is_active: Optional[bool] = Field(True, description="Stato abilitato/disabilitato dell'account")
    permissions: List[str] = Field(default_factory=list, description="Elenco chiavi di permesso assegnate")


class UpdateUserRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    password: Optional[str] = Field(None, min_length=4, max_length=128)
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[str]] = None


@router.get("")
@router.get("/")
async def list_users(admin: dict = Depends(require_admin)):
    """
    Restituisce la lista di tutti gli account locali registrati.
    Riservato agli amministratori.
    """
    users = await db_service.list_local_users()
    return {
        "status": "success",
        "users": users,
        "count": len(users)
    }


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, admin: dict = Depends(require_admin)):
    """
    Crea un nuovo account utente locale con password hashata PBKDF2/SHA-256 e permessi granulari.
    Riservato agli amministratori.
    """
    clean_username = payload.username.strip()
    
    # Verifica unicità username
    existing = await db_service.get_local_user_by_username(clean_username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lo username '{clean_username}' è già in uso."
        )

    # Coerenza ruolo e flag is_admin
    effective_is_admin = bool(payload.is_admin or payload.role == "admin")
    effective_role = "admin" if effective_is_admin else (payload.role or "operator")
    effective_is_active = True if payload.is_active is None else bool(payload.is_active)

    # Validazione permessi: se admin, assegna automaticamente tutti i permessi se non specificati
    valid_perms = auth_service.validate_permissions(payload.permissions)
    if effective_is_admin and not valid_perms:
        valid_perms = ALL_PERMISSION_KEYS

    # Hashing crittografico password
    pwd_hash, pwd_salt = auth_service.hash_password(payload.password)

    new_id = await db_service.create_local_user(
        username=clean_username,
        display_name=payload.display_name or "",
        role=effective_role,
        password_hash=pwd_hash,
        salt=pwd_salt,
        is_admin=effective_is_admin,
        is_active=effective_is_active,
        permissions=valid_perms
    )

    created_user = await db_service.get_local_user_by_id(new_id)
    if not created_user:
        raise HTTPException(status_code=500, detail="Errore durante la creazione dell'utente.")

    # Rimuovi dati sensibili
    created_user.pop("password_hash", None)
    created_user.pop("salt", None)

    logger.info(f"Local Auth: Utente '{clean_username}' (id: {new_id}, admin: {effective_is_admin}) creato con successo da '{admin.get('username')}'.")
    return {
        "status": "success",
        "message": f"Utente '{clean_username}' creato con successo.",
        "user": created_user
    }


@router.get("/{user_id}")
async def get_user(user_id: int, admin: dict = Depends(require_admin)):
    """
    Recupera i dettagli di un singolo utente locale per ID.
    Riservato agli amministratori.
    """
    user = await db_service.get_local_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato.")
    
    user.pop("password_hash", None)
    user.pop("salt", None)
    return {
        "status": "success",
        "user": user
    }


@router.put("/{user_id}")
async def update_user(user_id: int, payload: UpdateUserRequest, admin: dict = Depends(require_admin)):
    """
    Aggiorna username, password, stato admin, stato attivo o permessi di un utente locale.
    Riservato agli amministratori.
    """
    user = await db_service.get_local_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato.")

    new_username = payload.username.strip() if payload.username else None
    if new_username and new_username.lower() != user["username"].lower():
        existing = await db_service.get_local_user_by_username(new_username)
        if existing and existing["id"] != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Username '{new_username}' già utilizzato da un altro utente.")

    # Determina is_admin target
    target_is_admin = None
    if payload.is_admin is not None:
        target_is_admin = bool(payload.is_admin)
    elif payload.role is not None:
        target_is_admin = (payload.role == "admin")

    # Protezione rimozione ultimo amministratore
    if target_is_admin is False and user.get("is_admin"):
        admin_count = await db_service.count_admin_users()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossibile revocare i permessi di amministratore: deve rimanere almeno un amministratore attivo nel sistema."
            )

    # Determina role coerente
    target_role = payload.role
    if target_is_admin is True:
        target_role = "admin"
    elif target_is_admin is False and (not target_role or target_role == "admin"):
        target_role = "operator"

    pwd_hash = None
    pwd_salt = None
    if payload.password:
        pwd_hash, pwd_salt = auth_service.hash_password(payload.password)

    valid_perms = None
    if payload.permissions is not None:
        valid_perms = auth_service.validate_permissions(payload.permissions)

    success = await db_service.update_local_user(
        user_id=user_id,
        username=new_username,
        display_name=payload.display_name,
        role=target_role,
        password_hash=pwd_hash,
        salt=pwd_salt,
        is_admin=target_is_admin,
        is_active=payload.is_active,
        permissions=valid_perms
    )

    if not success:
        raise HTTPException(status_code=500, detail="Errore durante l'aggiornamento dell'utente.")

    updated_user = await db_service.get_local_user_by_id(user_id)
    updated_user.pop("password_hash", None)
    updated_user.pop("salt", None)

    logger.info(f"Local Auth: Utente id={user_id} aggiornato con successo dall'admin '{admin.get('username')}'.")
    return {
        "status": "success",
        "message": "Utente aggiornato con successo.",
        "user": updated_user
    }


@router.delete("/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """
    Elimina un account locale dal sistema.
    Impedisce l'eliminazione dell'ultimo amministratore rimanente.
    """
    user = await db_service.get_local_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato.")

    # Verifica se l'utente da eliminare è un admin
    if user.get("is_admin"):
        admin_count = await db_service.count_admin_users()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossibile eliminare l'utente: deve rimanere almeno un amministratore attivo nel sistema."
            )

    success = await db_service.delete_local_user(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Errore durante l'eliminazione dell'utente.")

    logger.info(f"Local Auth: Utente '{user.get('username')}' (id={user_id}) eliminato dall'admin '{admin.get('username')}'.")
    return {
        "status": "success",
        "message": f"Utente '{user.get('username')}' eliminato con successo."
    }
