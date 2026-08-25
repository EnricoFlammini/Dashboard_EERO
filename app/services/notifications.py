import logging
from typing import Any, Dict, Optional
import httpx
from app.config import settings
from app.services.db import db_service

logger = logging.getLogger(__name__)


class NotificationService:
    """Dispatches event alerts and reports via Telegram Bot and custom Webhook."""

    async def send_telegram_message(self, message: str) -> bool:
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
        text = (
            f"<b>{title}</b>\n\n"
            f"• <b>Traffico Totale WAN:</b> {digest_summary.get('total_gb', 0)} GB\n"
            f"• <b>Top Consumer:</b> {digest_summary.get('top_device', 'N/D')} ({digest_summary.get('top_device_gb', 0)} GB)\n"
            f"• <b>Velocità Media:</b> ↓ {digest_summary.get('avg_down_mbps', 0)} Mbps / ↑ {digest_summary.get('avg_up_mbps', 0)} Mbps\n"
            f"• <b>Ping Medio:</b> {digest_summary.get('avg_ping_ms', 0)} ms\n"
            f"• <b>Dispositivi Attivi:</b> {digest_summary.get('active_devices_count', 0)}\n"
        )
        await db_service.save_alert(
            alert_type="daily_digest",
            title=title,
            message=f"Consumo giornaliero {digest_summary.get('total_gb', 0)} GB. Top host: {digest_summary.get('top_device', 'N/D')}."
        )
        await self.send_telegram_message(text)
        await self.send_webhook("daily_digest", digest_summary)


notification_service = NotificationService()
