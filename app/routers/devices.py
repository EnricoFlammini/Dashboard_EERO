import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.poller import background_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["Device Management"])


class DeviceMetadataRequest(BaseModel):
    custom_name: Optional[str] = None
    custom_icon: Optional[str] = Field("device", description="Icona: laptop, smartphone, server, tv, gamepad, iot, camera, printer, tablet, speaker")
    category: Optional[str] = Field("Altro", description="Categoria: Computer, Mobile, Smart Home, Intrattenimento, Server/Rete, Gaming")
    custom_notes: Optional[str] = None
    static_ip: Optional[str] = None
    is_favorite: Optional[bool] = False
    is_low_latency_target: Optional[bool] = False


class DevicePauseRequest(BaseModel):
    paused: bool = Field(..., description="Mette in pausa (True) o riabilita (False) l'accesso a Internet")


class DeviceRenameRequest(BaseModel):
    nickname: str = Field(..., description="Nuovo nome dispositivo da sincronizzare con il cloud eero")


class PortForwardRequest(BaseModel):
    ip: str = Field(..., description="Indirizzo IP interno di destinazione")
    port_from: int = Field(..., description="Porta esterna WAN")
    port_to: int = Field(..., description="Porta interna LAN")
    protocol: str = Field("tcp", description="Protocollo: tcp, udp, o both")
    description: str = Field("Custom Service", description="Etichetta descrittiva della regola")


@router.get("")
async def list_devices(
    search: Optional[str] = None,
    band: Optional[str] = None,
    node: Optional[str] = None,
    connected_only: Optional[bool] = None,
    category: Optional[str] = None,
):
    """Restituisce l'elenco dei dispositivi arricchiti con metadati locali e filtri."""
    cached = background_poller.get_cached_state()
    devices = cached.get("devices", [])

    filtered = []
    for d in devices:
        # Filtro connessione
        if connected_only is not None and d.get("connected") != connected_only:
            continue
        
        # Filtro frequenza wireless
        if band and d.get("wireless_band") != band and band != "all":
            if band == "wired" and d.get("connection_type") != "wired":
                continue
            elif band != "wired" and d.get("wireless_band") != band:
                continue

        # Filtro nodo eero collegato
        if node and node != "all":
            if str(d.get("connected_eero_id")) != node and str(d.get("connected_eero_name")) != node:
                continue

        # Filtro categoria
        if category and category != "all" and d.get("category") != category:
            continue

        # Filtro ricerca testuale
        if search:
            s = search.lower()
            name = (d.get("custom_name") or d.get("nickname") or d.get("hostname") or "").lower()
            ip = (d.get("ip") or "").lower()
            mac = (d.get("mac") or d.get("mac_address") or "").lower()
            notes = (d.get("custom_notes") or "").lower()
            if s not in name and s not in ip and s not in mac and s not in notes:
                continue

        filtered.append(d)

    return {
        "status": "success",
        "total": len(devices),
        "count": len(filtered),
        "devices": filtered
    }


@router.get("/{mac_address}")
async def get_device_detail(mac_address: str):
    """Restituisce la scheda completa del dispositivo: stato live, metadati locali, storico traffico e regole porte."""
    mac_clean = mac_address.upper()
    cached = background_poller.get_cached_state()
    live_device = next((d for d in cached.get("devices", []) if (d.get("mac") or "").upper() == mac_clean), None)
    
    metadata = await db_service.get_device_metadata(mac_clean)
    history = await db_service.get_device_metrics_history(mac_clean, hours=24)
    forwards_res = await eero_client.get_forwards_and_reservations()
    
    # Filtra port forwards associati all'IP del dispositivo
    dev_ip = live_device.get("ip") if live_device else (metadata.get("static_ip") if metadata else "")
    dev_forwards = [f for f in forwards_res.get("forwards", []) if f.get("ip") == dev_ip] if dev_ip else []

    return {
        "status": "success",
        "device": live_device,
        "metadata": metadata,
        "forwards": dev_forwards,
        "traffic_history": history,
    }


@router.post("/{mac_address}/metadata")
async def save_device_metadata(mac_address: str, payload: DeviceMetadataRequest):
    """Salva nel database SQLite locale note, categoria, icona personalizzata e preferiti per il dispositivo."""
    mac_clean = mac_address.upper()
    updated = await db_service.upsert_device_metadata(
        mac_address=mac_clean,
        **payload.model_dump(exclude_unset=True)
    )
    return {"status": "success", "metadata": updated}


@router.post("/{device_id}/pause")
async def toggle_device_pause(device_id: str, payload: DevicePauseRequest):
    """Mette in pausa o riabilita l'accesso a internet per il dispositivo."""
    try:
        res = await eero_client.update_device(device_id=device_id, paused=payload.paused)
        return res
    except Exception as e:
        logger.error(f"Failed to set pause on device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{device_id}/rename")
async def rename_device(device_id: str, payload: DeviceRenameRequest):
    """Rinomina il dispositivo sincronizzando il nuovo nickname con il cloud eero."""
    try:
        res = await eero_client.update_device(device_id=device_id, nickname=payload.nickname.strip())
        return res
    except Exception as e:
        logger.error(f"Failed to rename device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{mac_address}/traffic")
async def get_device_traffic_history(mac_address: str, hours: int = Query(24, ge=1, le=720)):
    """Restituisce la serie temporale di download/upload per il singolo dispositivo."""
    history = await db_service.get_device_metrics_history(mac_address.upper(), hours=hours)
    return {
        "status": "success",
        "mac_address": mac_address,
        "hours": hours,
        "points_count": len(history),
        "history": history
    }


@router.get("/rules/forwards")
async def get_port_forwards_and_reservations():
    """Restituisce tutte le regole di port forwarding e prenotazioni IP configurate."""
    try:
        res = await eero_client.get_forwards_and_reservations()
        return {"status": "success", **res}
    except Exception as e:
        logger.error(f"Error fetching port forwards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/forwards")
async def create_port_forward(payload: PortForwardRequest):
    """Aggiunge una nuova regola di inoltro porte."""
    try:
        res = await eero_client.add_port_forward(
            ip=payload.ip,
            port_from=payload.port_from,
            port_to=payload.port_to,
            protocol=payload.protocol,
            description=payload.description
        )
        return res
    except Exception as e:
        logger.error(f"Failed to add port forward: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/forwards/{forward_id}")
async def delete_port_forward(forward_id: str):
    """Elimina una regola di inoltro porte."""
    try:
        res = await eero_client.delete_port_forward(forward_id)
        return res
    except Exception as e:
        logger.error(f"Failed to delete port forward {forward_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
