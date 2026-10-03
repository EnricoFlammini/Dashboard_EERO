"""
Router FastAPI per la gestione delle regole di Parental Scheduling e automazioni orarie (v1.6.0 Modulo 1).
Fornisce endpoint REST per creare, modificare, attivare/disattivare e valutare le regole temporali di pausa internet.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.routers.dependencies import require_permission
from app.services.db import db_service
from app.services.scheduler import schedule_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedules", tags=["Parental Scheduling & Rules"])


class ScheduleCreateRequest(BaseModel):
    name: str = Field(..., description="Nome descrittivo della regola (es. 'Nanna Bambini', 'Luce Notturna')")
    target_type: str = Field("profile", description="Tipo target: 'profile', 'all_profiles', 'node_led', 'all_nodes_led', 'node_reboot', 'all_nodes_reboot'")
    target_ids: Optional[List[str]] = Field(default=None, description="Elenco ID profili o nodi da sottoporre a regola")
    target_id: Optional[str] = Field(None, description="Identificativo singolo (compatibilità payload frontend)")
    days_of_week: Optional[List[str]] = Field(default=None, description="Giorni della settimana attivi")
    days: Optional[List[str]] = Field(default=None, description="Alias per days_of_week")
    start_time: str = Field("22:00", description="Orario di inizio regola (HH:MM)")
    end_time: str = Field("07:00", description="Orario di fine regola (HH:MM)")
    action: str = Field("pause", description="Azione applicata: 'pause', 'unpause', 'turn_off', 'turn_on', 'reboot'")
    enabled: Optional[bool] = Field(True, description="Stato di abilitazione della regola")
    is_active: Optional[bool] = Field(None, description="Alias per enabled")


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    target_type: Optional[str] = None
    target_ids: Optional[List[str]] = None
    target_id: Optional[str] = None
    days_of_week: Optional[List[str]] = None
    days: Optional[List[str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    action: Optional[str] = None
    enabled: Optional[bool] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_schedules():
    """Restituisce l'elenco di tutte le pianificazioni salvate."""
    return await db_service.get_device_schedules()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreateRequest,
    _auth=Depends(require_permission("action_manage_rules"))
):
    """Crea una nuova regola di pianificazione per utenti o nodi mesh."""
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Il nome della regola non può essere vuoto.")

    target_ids = []
    if payload.target_ids is not None:
        target_ids = list(payload.target_ids)
    elif payload.target_id:
        target_ids = [payload.target_id]
    elif payload.target_type in ("all_profiles", "all_nodes_led", "all_nodes_reboot", "all"):
        target_ids = ["all"]

    if not target_ids:
        raise HTTPException(status_code=400, detail="Specificare almeno un utente o nodo target.")

    days_list = payload.days if payload.days is not None else (payload.days_of_week or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    is_enabled = payload.is_active if payload.is_active is not None else (payload.enabled if payload.enabled is not None else True)

    new_id = await db_service.create_device_schedule(
        name=payload.name.strip(),
        target_type=payload.target_type,
        target_ids=target_ids,
        days_of_week=days_list,
        start_time=payload.start_time,
        end_time=payload.end_time,
        action=payload.action,
        enabled=is_enabled
    )

    created = await db_service.get_device_schedule_by_id(new_id)
    # Valuta immediatamente l'eventuale applicazione della nuova regola
    try:
        await schedule_engine.evaluate_schedules()
    except Exception as ex:
        logger.warning(f"Error evaluating schedules after create: {ex}")

    return {"status": "success", "schedule": created}


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: int):
    """Recupera i dettagli di una specifica pianificazione."""
    schedule = await db_service.get_device_schedule_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Pianificazione non trovata.")
    return schedule


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdateRequest,
    _auth=Depends(require_permission("action_manage_rules"))
):
    """Modifica i parametri di una pianificazione esistente."""
    existing = await db_service.get_device_schedule_by_id(schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pianificazione non trovata.")

    update_dict = payload.model_dump(exclude_unset=True)
    if not update_dict:
        return {"status": "success", "schedule": existing}

    # Normalizza alias frontend
    if "days" in update_dict:
        update_dict["days_of_week"] = update_dict.pop("days")
    if "is_active" in update_dict:
        update_dict["enabled"] = update_dict.pop("is_active")
    if "target_id" in update_dict:
        tid = update_dict.pop("target_id")
        if tid:
            update_dict["target_ids"] = [tid]

    success = await db_service.update_device_schedule(schedule_id, **update_dict)
    if not success:
        raise HTTPException(status_code=500, detail="Errore durante l'aggiornamento della regola.")

    updated = await db_service.get_device_schedule_by_id(schedule_id)
    try:
        await schedule_engine.evaluate_schedules()
    except Exception as ex:
        logger.warning(f"Error evaluating schedules after update: {ex}")

    return {"status": "success", "schedule": updated}


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    _auth=Depends(require_permission("action_manage_rules"))
):
    """Elimina una pianificazione."""
    existing = await db_service.get_device_schedule_by_id(schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pianificazione non trovata.")

    success = await db_service.delete_device_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=500, detail="Errore durante l'eliminazione della regola.")

    return {"status": "success", "message": f"Regola #{schedule_id} eliminata."}


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: int,
    _auth=Depends(require_permission("action_manage_rules"))
):
    """Attiva o disattiva una regola di pianificazione."""
    existing = await db_service.get_device_schedule_by_id(schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pianificazione non trovata.")

    new_state = not existing.get("enabled", True)
    await db_service.toggle_device_schedule(schedule_id, enabled=new_state)

    updated = await db_service.get_device_schedule_by_id(schedule_id)
    try:
        await schedule_engine.evaluate_schedules()
    except Exception as ex:
        logger.warning(f"Error evaluating schedules after toggle: {ex}")

    return {"status": "success", "schedule": updated}


@router.post("/evaluate")
async def evaluate_schedules_now():
    """Forza la valutazione istantanea delle regole di pianificazione."""
    result = await schedule_engine.evaluate_schedules()
    return {"status": "success", "evaluation": result}
