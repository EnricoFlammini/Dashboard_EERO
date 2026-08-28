import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.adguard import adguard_service
from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.notifications import notification_service
from app.services.poller import background_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/automations", tags=["Automations & Controls"])


class FocusModeRequest(BaseModel):
    active: bool = Field(..., description="Attiva (True) o Disattiva (False) la Gaming/Focus Low-Latency Mode")


class NightModeSettingsRequest(BaseModel):
    enabled: bool
    start_time: str = Field("23:00", description="Orario di inizio (HH:MM)")
    end_time: str = Field("07:00", description="Orario di fine (HH:MM)")


class NotificationSettingsRequest(BaseModel):
    telegram_enabled: bool
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_enabled: bool
    webhook_url: Optional[str] = None


class AdGuardSettingsRequest(BaseModel):
    enabled: bool
    url: str = Field(..., description="URL di base dell'istanza AdGuard Home (es. http://192.168.4.2:80)")
    username: Optional[str] = None
    password: Optional[str] = None


class AdGuardTestRequest(BaseModel):
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


@router.get("/focus-mode")
async def get_focus_mode_status():
    """Restituisce lo stato corrente della modalità Gaming / Focus Mode."""
    active_str = await db_service.get_setting("focus_mode_active", "false")
    paused_macs_json = await db_service.get_setting("focus_mode_paused_macs", "[]")
    
    try:
        paused_macs = json.loads(paused_macs_json)
    except Exception:
        paused_macs = []

    # Recupera tutti i dispositivi configurati per la prioritizzazione
    all_metadata = await db_service.get_all_device_metadata()
    target_devices = [m for m in all_metadata.values() if m.get("is_low_latency_target")]

    return {
        "status": "success",
        "active": active_str.lower() == "true",
        "target_devices_count": len(target_devices),
        "paused_macs": paused_macs,
    }


@router.post("/focus-mode")
async def toggle_focus_mode(payload: FocusModeRequest):
    """
    Attiva o disattiva con 1 clic la Gaming / Focus Mode.
    Quando attiva, mette in pausa automaticamente gli apparati secondari / IoT
    selezionati per azzerare la latenza e riservare la banda alle console e PC gaming.
    """
    cached = background_poller.get_cached_state()
    devices = cached.get("devices", [])
    all_metadata = await db_service.get_all_device_metadata()
    
    # Identifica apparati da mettere in pausa (quelli contrassegnati come target a bassa priorità o categoria IoT/Streaming)
    targets_to_pause = []
    for d in devices:
        mac = (d.get("mac") or d.get("mac_address") or "").upper()
        meta = all_metadata.get(mac, {})
        # Se esplicitamente marcato per la pausa o IoT non prioritario
        if meta.get("is_low_latency_target") or meta.get("category") in ("Smart Home", "Intrattenimento"):
            targets_to_pause.append(d)

    if payload.active:
        paused_list = []
        for dev in targets_to_pause:
            dev_id = dev.get("id") or dev.get("mac")
            try:
                await eero_client.update_device(device_id=str(dev_id), paused=True)
                paused_list.append(dev.get("mac"))
            except Exception as ex:
                logger.warning(f"Failed to pause device {dev_id} for focus mode: {ex}")

        await db_service.set_setting("focus_mode_active", "true")
        await db_service.set_setting("focus_mode_paused_macs", json.dumps(paused_list))
        
        await db_service.save_alert(
            alert_type="focus_mode",
            title="🎮 Gaming / Focus Mode Attivata",
            message=f"Focus Mode attivata. {len(paused_list)} dispositivi secondari messi in pausa."
        )

        return {
            "status": "success",
            "active": True,
            "message": f"Gaming Mode attivata! {len(paused_list)} dispositivi secondari messi in pausa.",
            "paused_macs": paused_list,
        }
    else:
        # Ripristina i dispositivi precedentemente messi in pausa
        paused_macs_json = await db_service.get_setting("focus_mode_paused_macs", "[]")
        try:
            paused_macs = json.loads(paused_macs_json)
        except Exception:
            paused_macs = []

        unpaused_count = 0
        for dev in devices:
            if dev.get("mac") in paused_macs:
                dev_id = dev.get("id") or dev.get("mac")
                try:
                    await eero_client.update_device(device_id=str(dev_id), paused=False)
                    unpaused_count += 1
                except Exception as ex:
                    logger.warning(f"Failed to unpause device {dev_id}: {ex}")

        await db_service.set_setting("focus_mode_active", "false")
        await db_service.set_setting("focus_mode_paused_macs", "[]")

        await db_service.save_alert(
            alert_type="focus_mode",
            title="🎮 Gaming / Focus Mode Disattivata",
            message=f"Focus Mode disattivata. Riconnessione consentita per tutti gli apparati."
        )

        return {
            "status": "success",
            "active": False,
            "message": "Gaming Mode disattivata. Traffico ripristinato su tutta la rete.",
            "unpaused_count": unpaused_count,
        }


@router.get("/night-mode")
async def get_night_mode_settings():
    """Restituisce le impostazioni della Modalità Notte automatica per i LED."""
    enabled = (await db_service.get_setting("night_mode_enabled", "false")).lower() == "true"
    start_time = await db_service.get_setting("night_mode_start", "23:00")
    end_time = await db_service.get_setting("night_mode_end", "07:00")

    return {
        "status": "success",
        "enabled": enabled,
        "start_time": start_time,
        "end_time": end_time,
    }


@router.post("/night-mode")
async def update_night_mode_settings(payload: NightModeSettingsRequest):
    """Aggiorna gli orari dello scheduler per spegnere i LED durante la notte."""
    await db_service.set_setting("night_mode_enabled", "true" if payload.enabled else "false")
    await db_service.set_setting("night_mode_start", payload.start_time)
    await db_service.set_setting("night_mode_end", payload.end_time)

    return {
        "status": "success",
        "message": "Impostazioni Modalità Notte salvate con successo.",
        "settings": payload.model_dump()
    }


@router.get("/notifications")
async def get_notification_settings():
    """Restituisce la configurazione dei canali di allarme (Telegram & Webhook)."""
    settings_dict = await db_service.get_all_settings()
    return {
        "status": "success",
        "telegram_enabled": settings_dict.get("telegram_alerts_enabled", "false").lower() == "true",
        "telegram_bot_token": settings_dict.get("telegram_bot_token", ""),
        "telegram_chat_id": settings_dict.get("telegram_chat_id", ""),
        "webhook_enabled": settings_dict.get("webhook_alerts_enabled", "false").lower() == "true",
        "webhook_url": settings_dict.get("webhook_url", ""),
    }


@router.post("/notifications")
async def update_notification_settings(payload: NotificationSettingsRequest):
    """Salva le credenziali e i toggle per Telegram e Webhook."""
    await db_service.set_setting("telegram_alerts_enabled", "true" if payload.telegram_enabled else "false")
    if payload.telegram_bot_token is not None:
        await db_service.set_setting("telegram_bot_token", payload.telegram_bot_token.strip())
    if payload.telegram_chat_id is not None:
        await db_service.set_setting("telegram_chat_id", payload.telegram_chat_id.strip())

    await db_service.set_setting("webhook_alerts_enabled", "true" if payload.webhook_enabled else "false")
    if payload.webhook_url is not None:
        await db_service.set_setting("webhook_url", payload.webhook_url.strip())

    return {"status": "success", "message": "Impostazioni di notifica salvate."}


@router.post("/notifications/test")
async def test_notification_channels():
    """Invia un messaggio di prova per verificare che Telegram e Webhook funzionino."""
    msg = "🔔 <b>Test Notifiche eero Dashboard</b>\n\nConnessione con il server completata con successo!"
    tg_res = await notification_service.send_telegram_message(msg, ignore_enabled=True)
    wh_res = await notification_service.send_webhook("test_ping", {"test": True, "message": "Ping test da eero Dashboard"})
    
    return {
        "status": "success",
        "telegram_sent": tg_res,
        "webhook_sent": wh_res,
    }


@router.get("/alerts")
async def get_recent_alerts():
    """Restituisce il log degli ultimi allarmi e notifiche della dashboard."""
    alerts = await db_service.get_alerts(limit=50)
    return {"status": "success", "count": len(alerts), "alerts": alerts}


@router.post("/alerts/read")
async def mark_all_alerts_read():
    """Segna tutti gli allarmi come letti."""
    await db_service.mark_alerts_read()
    return {"status": "success", "message": "Tutti gli allarmi sono stati contrassegnati come letti."}


@router.post("/digest/generate")
async def generate_immediate_digest():
    """Genera e invia immediatamente il report di riepilogo della rete."""
    try:
        data = await background_poller._send_daily_digest()
        return {"status": "success", "message": "Report Digest generato e inviato con successo sui canali attivi.", "data": data}
    except Exception as e:
        logger.error(f"Errore generazione digest: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante l'invio del report: {str(e)}")


# =========================================================================
# ADGUARD HOME DNS INTEGRATION
# =========================================================================

@router.get("/adguard")
async def get_adguard_settings():
    """Restituisce la configurazione corrente dell'integrazione AdGuard Home."""
    settings = await adguard_service.get_settings()
    return {
        "status": "success",
        **settings
    }


@router.post("/adguard")
async def update_adguard_settings(payload: AdGuardSettingsRequest):
    """Salva le impostazioni di connessione verso AdGuard Home."""
    await adguard_service.save_settings(
        enabled=payload.enabled,
        url=payload.url,
        username=payload.username,
        password=payload.password
    )
    return {"status": "success", "message": "Impostazioni AdGuard Home salvate con successo."}


@router.post("/adguard/test")
async def test_adguard_connection(payload: Optional[AdGuardTestRequest] = None):
    """Verifica la connessione e l'autenticazione con l'istanza AdGuard Home."""
    url = payload.url if payload else None
    username = payload.username if payload else None
    password = payload.password if payload else None
    res = await adguard_service.test_connection(url=url, username=username, password=password)
    return res


@router.post("/adguard/sync")
async def sync_adguard_devices():
    """Forza la sincronizzazione immediata di tutti i dispositivi correnti verso AdGuard Home."""
    cached = background_poller.get_cached_state()
    devices = cached.get("devices", [])
    if not devices:
        raise HTTPException(status_code=400, detail="Nessun dispositivo disponibile nella cache per la sincronizzazione.")
    
    res = await adguard_service.sync_devices(devices)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Sincronizzazione fallita."))
        
    return {
        "status": "success",
        **res
    }
