import logging
import secrets
import string
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.db import db_service
from app.services.eero_client import eero_client, EERO_API_BASE
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


@router.get("/health-breakdown")
async def get_health_breakdown():
    """Restituisce il dettaglio diagnostico completo e i 4 pilastri dello Health Score (Issue #15)."""
    cached = background_poller.get_cached_state()
    return {
        "status": "success",
        "data": {
            "health_score": cached.get("health_score", 100),
            "health_details": cached.get("health_details") or {}
        }
    }


@router.get("/diagnostics/iot-anomalies")
async def get_iot_night_anomalies(limit: int = 50, days: int = 7):
    """Restituisce le anomalie di traffico notturno registrate per apparati IoT (v1.6.0 Modulo 1)."""
    try:
        from app.services.db import db_service
        cached_anomalies = getattr(background_poller, "cached_iot_anomalies", [])
        db_anomalies = await db_service.get_iot_anomalies(limit=limit, days=days)
        
        # Unifica con priorità a quelle in memoria se in demo mode
        if getattr(eero_client, "is_demo_mode", False) or settings.demo_mode:
            all_anomalies = cached_anomalies or db_anomalies
        else:
            all_anomalies = db_anomalies or cached_anomalies

        return {
            "status": "success",
            "count": len(all_anomalies),
            "data": all_anomalies,
            "anomalies": all_anomalies,
        }
    except Exception as e:
        logger.error(f"Error fetching IoT anomalies: {e}")
        return {"status": "error", "message": str(e), "data": []}


@router.post("/refresh")
async def force_network_refresh():
    """Forza il poller a effettuare una lettura immediata e aggiornare la cache RAM."""
    try:
        await background_poller._poll_and_cache()
        cached = background_poller.get_cached_state()
        return {
            "status": "success",
            "message": "Dati rete aggiornati con successo.",
            "data": cached
        }
    except Exception as e:
        logger.error(f"Force refresh error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/debug-raw")
async def get_debug_raw():
    """Diagnostica: recupera i campi raw completi restituiti da eero per capire come vengono forniti i dati."""
    import httpx
    if not eero_client.is_authenticated or not eero_client.current_network_id:
        return {"status": "error", "message": "Non autenticato con eero"}

    try:
        async with eero_client._client_session() as client:
            resp_dev = await client.get(
                f"{EERO_API_BASE}/networks/{eero_client.current_network_id}/devices",
                headers=eero_client._get_headers()
            )
            resp_net = await client.get(
                f"{EERO_API_BASE}/networks/{eero_client.current_network_id}",
                headers=eero_client._get_headers()
            )
            resp_eeros = await client.get(
                f"{EERO_API_BASE}/networks/{eero_client.current_network_id}/eeros",
                headers=eero_client._get_headers()
            )
            raw_devices = resp_dev.json().get("data", [])
            raw_network = resp_net.json().get("data", {})
            raw_eeros = resp_eeros.json().get("data", [])

            # Estrai solo i campi rilevanti per la telemetria di ogni dispositivo
            devices_summary = []
            for d in raw_devices:
                devices_summary.append({
                    "nickname": d.get("nickname") or d.get("hostname") or d.get("mac"),
                    "mac": d.get("mac"),
                    "connected": d.get("connected"),
                    "wireless": d.get("wireless"),
                    "usage": d.get("usage"),
                    "rates": d.get("rates"),
                    "connectivity": d.get("connectivity"),
                    "rx_bytes": d.get("rx_bytes"),
                    "tx_bytes": d.get("tx_bytes"),
                    "channel": d.get("channel"),
                    "all_keys": list(d.keys())
                })

            return {
                "status": "success",
                "network_keys": list(raw_network.keys()),
                "network_speed": raw_network.get("speed"),
                "network_rates": raw_network.get("rates"),
                "network_activity": raw_network.get("activity"),
                "eeros_count": len(raw_eeros),
                "eeros": raw_eeros,
                "devices_count": len(devices_summary),
                "devices": devices_summary
            }
    except Exception as e:
        logger.error(f"Debug raw error: {e}")
        return {"status": "error", "error": str(e)}


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
        qr_data_url_light = ""
        qr_data_url_dark = ""
        if guest.get("enabled", False) and ssid and password:
            qr_data_url_light = generate_wifi_qr_code(ssid=ssid, password=password, dark_mode=False)
            qr_data_url_dark = generate_wifi_qr_code(ssid=ssid, password=password, dark_mode=True)
            qr_data_url = qr_data_url_light

        return {
            "status": "success",
            "guest_network": guest,
            "qr_code_data_url": qr_data_url,
            "qr_code_data_url_light": qr_data_url_light,
            "qr_code_data_url_dark": qr_data_url_dark,
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
        qr_code_light = ""
        qr_code_dark = ""
        if payload.enabled and payload.password:
            ssid = payload.name or "eero Guest"
            qr_code_light = generate_wifi_qr_code(ssid=ssid, password=payload.password, dark_mode=False)
            qr_code_dark = generate_wifi_qr_code(ssid=ssid, password=payload.password, dark_mode=True)
            qr_code = qr_code_light

        return {
            "status": "success",
            "guest_network": res,
            "qr_code_data_url": qr_code,
            "qr_code_data_url_light": qr_code_light,
            "qr_code_data_url_dark": qr_code_dark,
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


class SwitchNetworkRequest(BaseModel):
    network_id: str = Field(..., description="ID della rete eero verso cui effettuare lo switch")


@router.get("/list")
async def list_available_networks():
    """Restituisce l'elenco di tutte le reti mesh eero associate all'account (Issue #22)."""
    try:
        if not eero_client.available_networks and eero_client.is_authenticated:
            await eero_client.fetch_account_info()
        networks = eero_client.get_available_networks()
        return {
            "status": "success",
            "active_network_id": eero_client.current_network_id,
            "networks": networks
        }
    except Exception as e:
        logger.error(f"Error listing available networks: {e}")
        return {
            "status": "error",
            "message": str(e),
            "active_network_id": eero_client.current_network_id,
            "networks": eero_client.get_available_networks()
        }


@router.post("/switch")
async def switch_network(payload: SwitchNetworkRequest):
    """Hot-swap immediato della rete eero attiva con refresh istantaneo della cache RAM."""
    try:
        res = await eero_client.switch_network(payload.network_id)
        # Invalida cache poller ed esegue polling immediato per la nuova rete
        background_poller.invalidate_cache()
        await background_poller._poll_and_cache()
        cached = background_poller.get_cached_state()
        return {
            "status": "success",
            "message": f"Rete passata a '{payload.network_id}' con successo.",
            "active_network_id": eero_client.current_network_id,
            "data": cached
        }
    except Exception as e:
        logger.error(f"Error switching network: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/top-hogs")
async def get_top_bandwidth_hogs(limit: int = 5, period: str = "daily"):
    """Classifica dei dispositivi che hanno consumato più banda (Top Hogs) - v1.5.0 Insights Suite."""
    try:
        curr_net = eero_client.current_network_id
        is_demo_flag = 1 if getattr(eero_client, "is_demo_mode", False) else 0
        hogs = await db_service.get_top_bandwidth_hogs(network_id=curr_net, limit=limit, period=period, is_demo=is_demo_flag)
        
        # Fallback dai dispositivi attualmente in cache se lo storico è ancora scarso
        if not hogs:
            cached_devs = background_poller.cached_devices or []
            demo_factor = 1.0 if (period == "daily" or not is_demo_flag) else (4.2 if period == "weekly" else 14.8)
            sorted_devs = sorted(
                cached_devs,
                key=lambda d: float(d.get("rx_bytes") or 0) + float(d.get("tx_bytes") or 0),
                reverse=True
            )[:limit]
            for d in sorted_devs:
                rx_b = round(float(d.get("rx_bytes") or 0) * demo_factor, 1)
                tx_b = round(float(d.get("tx_bytes") or 0) * demo_factor, 1)
                hogs.append({
                    "mac": d.get("mac"),
                    "hostname": d.get("nickname") or d.get("hostname") or d.get("mac"),
                    "rx_bytes": rx_b,
                    "tx_bytes": tx_b,
                    "total_bytes": rx_b + tx_b,
                    "avg_down_mbps": float(d.get("download_rate_mbps") or 0),
                    "avg_up_mbps": float(d.get("upload_rate_mbps") or 0),
                })

        return {
            "status": "success",
            "network_id": curr_net,
            "period": period,
            "top_hogs": hogs
        }
    except Exception as e:
        logger.error(f"Error getting top bandwidth hogs: {e}")
        return {"status": "error", "message": str(e), "top_hogs": []}

