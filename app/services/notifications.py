import logging
from typing import Any, Dict, Optional
import httpx
from app.config import settings
from app.services.db import db_service

logger = logging.getLogger(__name__)


class NotificationService:
    """Dispatches event alerts and reports via Telegram Bot and custom Webhook."""

    def __init__(self):
        self._demo_settings: Dict[str, Any] = {
            "telegram_enabled": True,
            "telegram_bot_token": "123456789:AAFakeDemoTelegramBotToken_Example",
            "telegram_chat_id": "-1001234567890",
            "webhook_enabled": True,
            "webhook_url": "https://demo-webhook.lan/events",
        }

    async def get_settings(self) -> Dict[str, Any]:
        """Recupera le impostazioni correnti di notifica salvate nel database o fittizie in ambiente demo."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            return dict(self._demo_settings)

        all_s = await db_service.get_all_settings()
        return {
            "telegram_enabled": all_s.get("telegram_alerts_enabled", "true" if settings.telegram_bot_token else "false").lower() == "true",
            "telegram_bot_token": all_s.get("telegram_bot_token", settings.telegram_bot_token),
            "telegram_chat_id": all_s.get("telegram_chat_id", settings.telegram_chat_id),
            "webhook_enabled": all_s.get("webhook_alerts_enabled", "true" if settings.webhook_url else "false").lower() == "true",
            "webhook_url": all_s.get("webhook_url", settings.webhook_url),
        }

    async def save_settings(
        self,
        telegram_enabled: bool,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        webhook_enabled: bool = False,
        webhook_url: Optional[str] = None
    ) -> None:
        """Salva le impostazioni di notifica (in memoria in Demo Mode, su SQLite in Live Mode)."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            self._demo_settings["telegram_enabled"] = telegram_enabled
            if telegram_bot_token is not None:
                self._demo_settings["telegram_bot_token"] = telegram_bot_token.strip()
            if telegram_chat_id is not None:
                self._demo_settings["telegram_chat_id"] = telegram_chat_id.strip()
            self._demo_settings["webhook_enabled"] = webhook_enabled
            if webhook_url is not None:
                self._demo_settings["webhook_url"] = webhook_url.strip()
            return

        await db_service.set_setting("telegram_alerts_enabled", "true" if telegram_enabled else "false")
        if telegram_bot_token is not None:
            await db_service.set_setting("telegram_bot_token", telegram_bot_token.strip())
        if telegram_chat_id is not None:
            await db_service.set_setting("telegram_chat_id", telegram_chat_id.strip())
        await db_service.set_setting("webhook_alerts_enabled", "true" if webhook_enabled else "false")
        if webhook_url is not None:
            await db_service.set_setting("webhook_url", webhook_url.strip())

    async def send_telegram_message(self, message: str, ignore_enabled: bool = False) -> bool:
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            if not ignore_enabled and not self._demo_settings.get("telegram_enabled", True):
                logger.debug("[Demo Mode] Notifiche Telegram disabilitate nelle impostazioni demo.")
                return False
            logger.info(f"[Demo Mode] Simulazione invio notifica Telegram riuscita (messaggio: {message[:80]}...)")
            return True

        if not ignore_enabled:
            enabled = await db_service.get_setting("telegram_alerts_enabled", "true" if settings.telegram_bot_token else "false")
            if enabled.lower() != "true":
                logger.debug("Telegram alerts are disabled in settings.")
                return False

        token = await db_service.get_setting("telegram_bot_token", settings.telegram_bot_token)
        chat_id = await db_service.get_setting("telegram_chat_id", settings.telegram_chat_id)
        
        if not token or not chat_id:
            logger.debug("Telegram credentials not configured. Skipping Telegram notification.")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram notification sent successfully.")
                    return True
                else:
                    logger.error(f"Telegram send failed ({resp.status_code}): {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return False

    async def send_webhook(self, event_type: str, data: Dict[str, Any]) -> bool:
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            if not self._demo_settings.get("webhook_enabled", True):
                logger.debug(f"[Demo Mode] Webhook disabilitato nelle impostazioni demo ({event_type}).")
                return False
            logger.info(f"[Demo Mode] Simulazione invio notifica Webhook riuscita (evento: {event_type})")
            return True

        webhook_url = await db_service.get_setting("webhook_url", settings.webhook_url)
        if not webhook_url:
            return False

        payload = {
            "event": event_type,
            "timestamp": data.get("timestamp"),
            "data": data,
            "source": "eero_custom_dashboard"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code in (200, 201, 202, 204)
        except Exception as e:
            logger.error(f"Webhook notification error: {e}")
            return False

    async def notify_new_device(self, device: Dict[str, Any]):
        title = "🚨 Nuovo Dispositivo Rilevato nella Rete eero!"
        hostname = device.get("hostname") or device.get("nickname") or "Sconosciuto"
        mac = device.get("mac") or device.get("mac_address") or "N/D"
        ip = device.get("ip") or "N/D"
        band = device.get("wireless_band") or device.get("connection_type") or "N/D"
        eero_node = device.get("connected_eero_name") or "Gateway"

        text = (
            f"<b>{title}</b>\n\n"
            f"• <b>Host:</b> <code>{hostname}</code>\n"
            f"• <b>IP:</b> <code>{ip}</code>\n"
            f"• <b>MAC:</b> <code>{mac}</code>\n"
            f"• <b>Collegato a:</b> {eero_node} ({band})\n"
        )
        
        # Registra su database
        await db_service.save_alert(
            alert_type="new_device",
            title=title,
            message=f"Dispositivo '{hostname}' (IP: {ip}, MAC: {mac}) collegato al nodo {eero_node}."
        )

        # Invia canali esterni se attivi
        await self.send_telegram_message(text)
        await self.send_webhook("new_device", device)

    async def notify_node_offline(self, eero_node: Dict[str, Any]):
        title = "⚠️ Nodo eero Mesh Offline!"
        name = eero_node.get("name", "Nodo Mesh")
        ip = eero_node.get("ip", "N/D")
        
        text = (
            f"<b>{title}</b>\n\n"
            f"Il nodo mesh <b>{name}</b> (IP: <code>{ip}</code>) risulta non raggiungibile o offline."
        )
        await db_service.save_alert(
            alert_type="node_offline",
            title=title,
            message=f"Il nodo mesh {name} ({ip}) risulta offline."
        )
        await self.send_telegram_message(text)
        await self.send_webhook("node_offline", eero_node)

    async def notify_digest(self, digest_summary: Dict[str, Any]):
        title = "📊 Riepilogo Giornaliero eero Mesh"
        net_name = digest_summary.get("network_name", "Rete eero")
        health = digest_summary.get("health_score", 100)
        isp = digest_summary.get("isp", "N/D")
        active = digest_summary.get("active_devices_count", 0)
        c_6g = digest_summary.get("count_6ghz", 0)
        c_5g = digest_summary.get("count_5ghz", 0)
        c_24g = digest_summary.get("count_24ghz", 0)
        c_wired = digest_summary.get("count_wired", 0)
        nodes_on = digest_summary.get("online_nodes", 0)
        nodes_tot = digest_summary.get("total_nodes", 0)
        down = digest_summary.get("wan_down", 0)
        up = digest_summary.get("wan_up", 0)
        ping = digest_summary.get("wan_ping", 0)

        # Formattazione dettagliata delle frequenze
        bands_detail = []
        if c_6g > 0: bands_detail.append(f"6 GHz: {c_6g}")
        if c_5g > 0: bands_detail.append(f"5 GHz: {c_5g}")
        if c_24g > 0: bands_detail.append(f"2.4 GHz: {c_24g}")
        if c_wired > 0: bands_detail.append(f"Cablati: {c_wired}")
        bands_str = " | ".join(bands_detail) if bands_detail else f"{active} totali"

        text = (
            f"<b>{title}</b>\n\n"
            f"🏠 <b>Rete:</b> {net_name} (Health Score: <b>{health}/100</b>)\n"
            f"🌐 <b>Provider Internet (ISP):</b> {isp}\n"
            f"📡 <b>Nodi Mesh Operativi:</b> {nodes_on}/{nodes_tot}\n"
            f"📱 <b>Client Attivi:</b> {active}\n"
            f"📶 <b>Frequenze Wi-Fi:</b> {bands_str}\n"
            f"⚡ <b>Speed Test Gateway:</b> ↓ {down} Mbps / ↑ {up} Mbps\n"
            f"⏱️ <b>Latenza Ping:</b> {ping} ms\n"
        )
        await db_service.save_alert(
            alert_type="daily_digest",
            title=title,
            message=f"Report giornaliero inviato: {active} client connessi, {nodes_on}/{nodes_tot} nodi mesh attivi, ISP: {isp}."
        )
        await self.send_telegram_message(text)
        await self.send_webhook("daily_digest", digest_summary)


notification_service = NotificationService()
