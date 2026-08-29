import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.eero_client import eero_client
from app.services.poller import background_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profiles", tags=["Profile & User Management"])


class CreateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60, description="Nome del profilo o utente (es. Marco, Ufficio)")
    device_ids: Optional[List[str]] = Field(default=[], description="Lista di ID o MAC dei dispositivi da associare inizialmente")


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60, description="Nuovo nome del profilo")
    device_ids: Optional[List[str]] = Field(None, description="Nuova lista completa di dispositivi associati")


class AssignDevicesRequest(BaseModel):
    device_ids: List[str] = Field(..., description="Lista di ID o MAC da assegnare a questo profilo")


class AssignSingleDeviceRequest(BaseModel):
    profile_id: Optional[str] = Field(None, description="ID del profilo a cui assegnare il dispositivo (null per disassociare)")


@router.get("")
async def list_profiles():
    """Restituisce l'elenco dei profili utente configurati e i relativi dispositivi."""
    cached = background_poller.get_cached_state()
    profiles = cached.get("profiles", [])
    
    # Se la cache è vuota ma il client è configurato, recupera direttamente
    if not profiles and eero_client.is_authenticated:
        try:
            profiles = await eero_client.get_profiles()
        except Exception as e:
            logger.warning(f"Failed to directly fetch profiles: {e}")
            profiles = []

    return {
        "status": "success",
        "count": len(profiles),
        "profiles": profiles
    }


@router.post("")
async def create_profile(req: CreateProfileRequest):
    """Crea un nuovo profilo utente su eero Cloud."""
    try:
        res = await eero_client.create_profile(name=req.name, device_ids=req.device_ids)
        # Forza un polling rapido in background
        cached_p = await eero_client.get_profiles()
        background_poller.update_cached_profiles(cached_p)
        return {
            "status": "success",
            "message": f"Profilo '{req.name}' creato con successo.",
            "profile": res.get("profile")
        }
    except Exception as e:
        logger.error(f"Errore creazione profilo: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{profile_id}")
async def update_profile(profile_id: str, req: UpdateProfileRequest):
    """Aggiorna il nome o i dispositivi di un profilo."""
    try:
        res = await eero_client.update_profile(
            profile_id=profile_id,
            name=req.name,
            device_ids=req.device_ids
        )
        cached_p = await eero_client.get_profiles()
        background_poller.update_cached_profiles(cached_p)
        return {
            "status": "success",
            "message": "Profilo aggiornato con successo.",
            "profile": res.get("profile")
        }
    except Exception as e:
        logger.error(f"Errore aggiornamento profilo {profile_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    """Elimina un profilo utente da eero Cloud."""
    try:
        res = await eero_client.delete_profile(profile_id=profile_id)
        cached_p = await eero_client.get_profiles()
        background_poller.update_cached_profiles(cached_p)
        return {
            "status": "success",
            "message": "Profilo eliminato con successo.",
            "result": res
        }
    except Exception as e:
        logger.error(f"Errore eliminazione profilo {profile_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{profile_id}/assign")
async def assign_devices_to_profile(profile_id: str, req: AssignDevicesRequest):
    """Assegna una lista di dispositivi al profilo specificato."""
    try:
        for dev_id in req.device_ids:
            await eero_client.assign_device_to_profile(device_id_or_mac=dev_id, profile_id=profile_id)
        
        cached_p = await eero_client.get_profiles()
        background_poller.update_cached_profiles(cached_p)
        return {
            "status": "success",
            "message": f"{len(req.device_ids)} dispositivi assegnati al profilo.",
            "profile_id": profile_id
        }
    except Exception as e:
        logger.error(f"Errore assegnazione dispositivi a profilo {profile_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
