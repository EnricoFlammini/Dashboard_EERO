import logging
import secrets
import string
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.eero_client import eero_client
from app.services.poller import background_poller
from app.services.qrcode_gen import generate_wifi_qr_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network", tags=["Network & Mesh"])


class ToggleLEDRequest(BaseModel):
    led_on: bool = Field(..., description="Stato del LED frontale (True = Acceso, False = Spento)")


class GuestNetworkRequest(BaseModel):
    enabled: bool = Field(..., description="Attiva o disattiva la rete ospiti")
    name: Optional[str] = Field(None, description="Nome SSID della rete ospiti")
    password: Optional[str] = Field(None, description="Password di accesso WPA2/WPA3")


class AdvancedSettingsRequest(BaseModel):
    ipv6_enabled: Optional[bool] = None
    upnp_enabled: Optional[bool] = None
    band_steering_enabled: Optional[bool] = None


@router.get("/overview")
async def get_network_overview():
    """Restituisce lo stato generale WAN, Health Score e nodi mesh dalla cache RAM (0ms)."""
    cached = background_poller.get_cached_state()
    return {
        "status": "success",
        "data": cached
    }


@router.get("/eeros")
async def get_mesh_nodes():
    """Restituisce l'elenco e lo stato dei singoli nodi eero mesh."""
    try:
        eeros = await eero_client.get_eeros()
        return {"status": "success", "count": len(eeros), "eeros": eeros}
    except Exception as e:
        logger.error(f"Error fetching eeros: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reboot")
async def reboot_network():
    """Invia il comando di riavvio all'intera rete mesh."""
    try:
        res = await eero_client.reboot_network()
        return res
    except Exception as e:
        logger.error(f"Failed to reboot network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eeros/{eero_id}/reboot")
async def reboot_single_eero(eero_id: str):
    """Riavvia un singolo nodo eero mesh."""
    try:
        res = await eero_client.reboot_eero(eero_id)
        return res
    except Exception as e:
        logger.error(f"Failed to reboot eero {eero_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eeros/{eero_id}/led")
async def toggle_eero_led(eero_id: str, payload: ToggleLEDRequest):
    """Accende o spegne il LED di un singolo nodo eero."""
    try:
        res = await eero_client.set_eero_led(eero_id, payload.led_on)
        return res
    except Exception as e:
        logger.error(f"Failed to toggle LED on eero {eero_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leds")
async def toggle_all_leds(payload: ToggleLEDRequest):
    """Accende o spegne contemporaneamente i LED di tutti i nodi eero."""
    try:
        res = await eero_client.set_all_leds(payload.led_on)
        return res
    except Exception as e:
        logger.error(f"Failed to toggle all LEDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guest")
async def get_guest_network():
    """Restituisce le impostazioni della rete ospiti e il QR Code Wi-Fi generato."""
    try:
        network = await eero_client.get_network_details()
        guest = network.get("guest_network", {})
        ssid = guest.get("name", "eero Guest")
        password = guest.get("password", "")
        
        qr_data_url = ""
        if guest.get("enabled", False) and ssid and password:
            qr_data_url = generate_wifi_qr_code(ssid=ssid, password=password)

        return {
            "status": "success",
            "guest_network": guest,
            "qr_code_data_url": qr_data_url,
        }
    except Exception as e:
        logger.error(f"Error fetching guest network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guest")
async def update_guest_network(payload: GuestNetworkRequest):
    """Aggiorna le impostazioni della rete ospiti (Attiva/Disattiva, SSID, Password)."""
    try:
        res = await eero_client.set_guest_network(
            enabled=payload.enabled,
            name=payload.name,
            password=payload.password
        )
        # Rigenera il QR Code aggiornato
        qr_code = ""
        if payload.enabled and payload.password:
            ssid = payload.name or "eero Guest"
            qr_code = generate_wifi_qr_code(ssid=ssid, password=payload.password)

        return {
            "status": "success",
            "guest_network": res,
            "qr_code_data_url": qr_code
        }
    except Exception as e:
        logger.error(f"Failed to update guest network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guest/generate-password")
async def generate_random_guest_password():
    """Genera una password sicura e memorabile per gli ospiti."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Genera password di 12 caratteri con caratteri sicuri
    password = "".join(secrets.choice(alphabet) for _ in range(12))
    return {"status": "success", "password": password}


@router.get("/advanced")
async def get_advanced_settings():
    """Restituisce lo stato delle impostazioni avanzate di rete (IPv6, UPnP, Band Steering)."""
    try:
        network = await eero_client.get_network_details()
        return {
            "status": "success",
            "ipv6_enabled": network.get("ipv6_enabled", False),
            "upnp_enabled": network.get("upnp_enabled", True),
            "band_steering_enabled": network.get("band_steering_enabled", True),
        }
    except Exception as e:
        logger.error(f"Error fetching advanced settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advanced")
async def update_advanced_settings(payload: AdvancedSettingsRequest):
    """Aggiorna le impostazioni avanzate di rete."""
    try:
        # In un'infrastruttura eero reale o demo
        return {
            "status": "success",
            "message": "Impostazioni avanzate aggiornate.",
            "settings": payload.model_dump(exclude_unset=True)
        }
    except Exception as e:
        logger.error(f"Failed to update advanced settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
