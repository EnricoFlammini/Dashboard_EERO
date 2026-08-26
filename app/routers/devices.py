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


class ReservationRequest(BaseModel):
    ip: str = Field(..., description="Indirizzo IP statico da riservare per il dispositivo")
    description: Optional[str] = Field(None, description="Descrizione della prenotazione")


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
    """Restituisce la scheda completa del dispositivo: stato live e metadati locali."""
    mac_clean = mac_address.lower()
    cached = background_poller.get_cached_state()
    live_device = next((d for d in cached.get("devices", []) if (d.get("mac") or "").lower() == mac_clean), None)
    
    metadata = await db_service.get_device_metadata(mac_clean)

    return {
        "status": "success",
        "device": live_device,
        "metadata": metadata,
    }


@router.post("/{mac_address}/metadata")
async def save_device_metadata(mac_address: str, payload: DeviceMetadataRequest):
    """Salva nel database SQLite locale note, categoria, icona personalizzata e preferiti per il dispositivo."""
    mac_clean = mac_address.lower()
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


@router.get("/{mac_address}/rules")
async def get_device_rules(mac_address: str):
    """Restituisce la prenotazione DHCP attiva e tutte le regole di port forwarding per questo dispositivo."""
    mac_clean = mac_address.lower()
    cached = background_poller.get_cached_state()
    live_device = next((d for d in cached.get("devices", []) if (d.get("mac") or "").lower() == mac_clean), None)
    
    forwards_res = await eero_client.get_forwards_and_reservations()
    all_reservations = forwards_res.get("reservations", [])
    all_forwards = forwards_res.get("forwards", [])
    
    # Trova prenotazione per questo MAC o IP
    dev_reservation = next((r for r in all_reservations if (r.get("mac") or "").lower() == mac_clean), None)
    
    # Determina l'IP effettivo o prenotato
    dev_ip = dev_reservation.get("ip") if dev_reservation else (live_device.get("ip") if live_device else "")
    dev_forwards = [f for f in all_forwards if f.get("ip") == dev_ip] if dev_ip else []
    
    return {
        "status": "success",
        "mac_address": mac_clean,
        "current_ip": dev_ip or (live_device.get("ip") if live_device else None),
        "reservation": dev_reservation,
        "forwards": dev_forwards,
        "all_reservations": all_reservations,
        "all_forwards": all_forwards,
    }


@router.post("/{mac_address}/reservation")
async def set_device_reservation(mac_address: str, payload: ReservationRequest):
    """Riserva un IP statico DHCP per il dispositivo su Amazon eero, riassegnando se necessario."""
    mac_clean = mac_address.lower()
    target_ip = payload.ip.strip()
    
    # Se l'IP era già prenotato per un vecchio MAC o un'altra interfaccia dello stesso host, elimina prima la vecchia prenotazione per evitare conflitti su eero
    forwards_res = await eero_client.get_forwards_and_reservations()
    for res in forwards_res.get("reservations", []):
        if res.get("ip") == target_ip and (res.get("mac") or "").lower() != mac_clean:
            old_res_id = res.get("id") or res.get("mac")
            logger.info(f"Reassigning IP {target_ip} from {res.get('mac')} to {mac_clean}. Deleting old reservation {old_res_id}...")
            try:
                await eero_client.delete_reservation(old_res_id)
            except Exception as e:
                logger.warning(f"Could not delete old reservation {old_res_id}: {e}")
            
    try:
        res = await eero_client.add_reservation(
            ip=target_ip,
            mac=mac_clean,
            description=payload.description or "Static IP"
        )
        # Aggiorna anche static_ip nei metadati locali
        await db_service.upsert_device_metadata(mac_address=mac_clean, static_ip=target_ip)
        return {"status": "success", "reservation": res}
    except Exception as e:
        logger.error(f"Failed to add DHCP reservation for {mac_clean}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{mac_address}/reservation")
async def delete_device_reservation(mac_address: str):
    """Rimuove la prenotazione IP statico dal router eero."""
    mac_clean = mac_address.lower()
    forwards_res = await eero_client.get_forwards_and_reservations()
    target_res = next((r for r in forwards_res.get("reservations", []) if (r.get("mac") or "").lower() == mac_clean), None)
    
    res_id = target_res.get("id") if target_res else mac_clean
    try:
        res = await eero_client.delete_reservation(res_id)
        # Pulisce static_ip nei metadati locali
        await db_service.upsert_device_metadata(mac_address=mac_clean, static_ip="")
        return {"status": "success", "deleted": res}
    except Exception as e:
        logger.error(f"Failed to delete DHCP reservation for {mac_clean}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules/forwards")
async def get_port_forwards_and_reservations():
    """Restituisce tutte le regole di port forwarding e prenotazioni IP configurate."""
    try:
        res = await eero_client.get_forwards_and_reservations()
        return {"status": "success", **res}
    except Exception as e:
        logger.error(f"Error fetching port forwards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{mac_address}/forwards")
async def create_device_port_forward(mac_address: str, payload: PortForwardRequest):
    """Aggiunge una nuova regola di inoltro porte per il dispositivo."""
    try:
        res = await eero_client.add_port_forward(
            ip=payload.ip.strip(),
            port_from=payload.port_from,
            port_to=payload.port_to,
            protocol=payload.protocol,
            description=payload.description.strip()
        )
        return {"status": "success", "forward": res}
    except Exception as e:
        logger.error(f"Failed to add port forward: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{mac_address}/forwards/{forward_id}")
async def delete_device_port_forward(mac_address: str, forward_id: str):
    """Elimina una regola di inoltro porte."""
    try:
        res = await eero_client.delete_port_forward(forward_id)
        return {"status": "success", "deleted": res}
    except Exception as e:
        logger.error(f"Failed to delete port forward {forward_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
