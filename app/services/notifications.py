import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app import i18n
from app.i18n import tr
from app.config import settings
from app.services.db import db_service

logger = logging.getLogger(__name__)


class NotificationService:
    """Dispatches event alerts and reports via Telegram Bot, custom Webhook, Discord and Pushover."""

    def __init__(self):
        self._demo_settings: Dict[str, Any] = {
            "telegram_enabled": True,
            "telegram_bot_token": "123456789:AAFakeDemoTelegramBotToken_Example",
            "telegram_chat_id": "-1001234567890",
            "webhook_enabled": True,
            "webhook_url": "https://demo-webhook.lan/events",
            "discord_enabled": True,
            "discord_webhook_url": "https://discord.com/api/webhooks/demo/fake",
            "pushover_enabled": True,
            "pushover_user_key": "uFakeDemoPushoverUserKey",
            "pushover_api_token": "aFakeDemoPushoverToken",
            "system_language": settings.dashboard_lang,
        }

    async def get_language(self, override_lang: Optional[str] = None) -> str:
        """Determines the active notification language ('en' or 'it')."""
        if override_lang and override_lang.lower() in ("it", "en"):
            return override_lang.lower()
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode and "system_language" in self._demo_settings:
            demo_lang = self._demo_settings.get("system_language")
            if demo_lang and demo_lang.lower() in ("it", "en"):
                i18n.set_system_language(demo_lang)
                return demo_lang.lower()
        lang = await db_service.get_setting("system_language", settings.dashboard_lang)
        resolved = lang.lower() if lang and lang.lower() in ("it", "en") else "en"
        i18n.set_system_language(resolved)
        return resolved

    async def set_language(self, lang: str):
        """Sets the active system language."""
        lang = lang.lower().strip()
        if lang in ("it", "en"):
            self._demo_settings["system_language"] = lang
            await db_service.set_setting("system_language", lang)
            i18n.set_system_language(lang)

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
            "discord_enabled": all_s.get("discord_alerts_enabled", "true" if settings.discord_webhook_url else "false").lower() == "true",
            "discord_webhook_url": all_s.get("discord_webhook_url", settings.discord_webhook_url),
            "pushover_enabled": all_s.get("pushover_alerts_enabled", "true" if settings.pushover_user_key else "false").lower() == "true",
            "pushover_user_key": all_s.get("pushover_user_key", settings.pushover_user_key),
            "pushover_api_token": all_s.get("pushover_api_token", settings.pushover_api_token),
            "system_language": all_s.get("system_language", settings.dashboard_lang),
        }

    async def save_settings(
        self,
        telegram_enabled: bool,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        webhook_enabled: bool = False,
        webhook_url: Optional[str] = None,
        discord_enabled: bool = False,
        discord_webhook_url: Optional[str] = None,
        pushover_enabled: bool = False,
        pushover_user_key: Optional[str] = None,
        pushover_api_token: Optional[str] = None,
        language: Optional[str] = None
    ) -> None:
        """Salva le impostazioni di notifica per tutti i canali."""
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
            self._demo_settings["discord_enabled"] = discord_enabled
            if discord_webhook_url is not None:
                self._demo_settings["discord_webhook_url"] = discord_webhook_url.strip()
            self._demo_settings["pushover_enabled"] = pushover_enabled
            if pushover_user_key is not None:
                self._demo_settings["pushover_user_key"] = pushover_user_key.strip()
            if pushover_api_token is not None:
                self._demo_settings["pushover_api_token"] = pushover_api_token.strip()
            if language is not None and language.lower().strip() in ("it", "en"):
                self._demo_settings["system_language"] = language.lower().strip()
                i18n.set_system_language(language)
            return

        await db_service.set_setting("telegram_alerts_enabled", "true" if telegram_enabled else "false")
        if telegram_bot_token is not None:
            await db_service.set_setting("telegram_bot_token", telegram_bot_token.strip())
        if telegram_chat_id is not None:
            await db_service.set_setting("telegram_chat_id", telegram_chat_id.strip())
        await db_service.set_setting("webhook_alerts_enabled", "true" if webhook_enabled else "false")
        if webhook_url is not None:
            await db_service.set_setting("webhook_url", webhook_url.strip())
        await db_service.set_setting("discord_alerts_enabled", "true" if discord_enabled else "false")
        if discord_webhook_url is not None:
            await db_service.set_setting("discord_webhook_url", discord_webhook_url.strip())
        await db_service.set_setting("pushover_alerts_enabled", "true" if pushover_enabled else "false")
        if pushover_user_key is not None:
            await db_service.set_setting("pushover_user_key", pushover_user_key.strip())
        if pushover_api_token is not None:
            await db_service.set_setting("pushover_api_token", pushover_api_token.strip())
        if language is not None and language.lower().strip() in ("it", "en"):
            await db_service.set_setting("system_language", language.lower().strip())
            i18n.set_system_language(language)

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

    async def send_webhook(self, event_type: str, data: Dict[str, Any], ignore_enabled: bool = False) -> bool:
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            if not ignore_enabled and not self._demo_settings.get("webhook_enabled", True):
                logger.debug(f"[Demo Mode] Webhook disabilitato nelle impostazioni demo ({event_type}).")
                return False
            logger.info(f"[Demo Mode] Simulazione invio notifica Webhook riuscita (evento: {event_type})")
            return True

        if not ignore_enabled:
            enabled = await db_service.get_setting("webhook_alerts_enabled", "true" if settings.webhook_url else "false")
            if enabled.lower() != "true":
                return False

        webhook_url = await db_service.get_setting("webhook_url", settings.webhook_url)
        if not webhook_url:
            return False

        payload = {
            "event": event_type,
            "timestamp": data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
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

    async def send_discord_message(
        self,
        title: str,
        description: str,
        color: int = 0x38bdf8,
        fields: Optional[List[Dict[str, Any]]] = None,
        ignore_enabled: bool = False
    ) -> bool:
        """Invia un alert formattato tramite Webhook Discord con embed card."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            if not ignore_enabled and not self._demo_settings.get("discord_enabled", True):
                return False
            logger.info(f"[Demo Mode] Simulazione invio notifica Discord riuscita (titolo: {title})")
            return True

        if not ignore_enabled:
            enabled = await db_service.get_setting("discord_alerts_enabled", "true" if settings.discord_webhook_url else "false")
            if enabled.lower() != "true":
                return False

        webhook_url = await db_service.get_setting("discord_webhook_url", settings.discord_webhook_url)
        if not webhook_url:
            return False

        clean_desc = description.replace("<b>", "**").replace("</b>", "**").replace("<code>", "`").replace("</code>", "`")
        payload = {
            "username": "eero Dashboard Alert",
            "embeds": [
                {
                    "title": title,
                    "description": clean_desc,
                    "color": color,
                    "fields": fields or [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {"text": "eero Management Suite"}
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Discord notification error: {e}")
            return False

    async def send_pushover_message(
        self,
        title: str,
        message: str,
        priority: int = 0,
        ignore_enabled: bool = False
    ) -> bool:
        """Invia una notifica push tramite l'API di Pushover."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            if not ignore_enabled and not self._demo_settings.get("pushover_enabled", True):
                return False
            logger.info(f"[Demo Mode] Simulazione invio notifica Pushover riuscita (titolo: {title})")
            return True

        if not ignore_enabled:
            enabled = await db_service.get_setting("pushover_alerts_enabled", "true" if settings.pushover_user_key else "false")
            if enabled.lower() != "true":
                return False

        user_key = await db_service.get_setting("pushover_user_key", settings.pushover_user_key)
        api_token = await db_service.get_setting("pushover_api_token", settings.pushover_api_token)
        if not user_key or not api_token:
            return False

        clean_msg = message.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
        payload = {
            "token": api_token,
            "user": user_key,
            "title": title,
            "message": clean_msg,
            "priority": priority,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://api.pushover.net/1/messages.json", data=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Pushover notification error: {e}")
            return False

    async def _dispatch_all_channels(self, event_type: str, title: str, text: str, db_msg: str, data: Dict[str, Any], color: int = 0x38bdf8):
        """Helper to dispatch across SQLite alerts, Telegram, Webhook, Discord and Pushover."""
        await db_service.save_alert(
            alert_type=event_type,
            title=title,
            message=db_msg
        )
        await self.send_telegram_message(text)
        await self.send_webhook(event_type, data)
        await self.send_discord_message(title=title, description=text, color=color)
        await self.send_pushover_message(title=title, message=db_msg)

    async def notify_new_device(self, device: Dict[str, Any], lang: Optional[str] = None):
        active_lang = await self.get_language(lang)

        title = tr("notifications.new_device_title", lang=active_lang)
        not_available = tr("notifications.not_available", lang=active_lang)
        hostname = device.get("hostname") or device.get("nickname") or tr("notifications.unknown", lang=active_lang)
        mac = device.get("mac") or device.get("mac_address") or not_available
        ip = device.get("ip") or not_available
        band = device.get("wireless_band") or device.get("connection_type") or not_available
        eero_node = device.get("connected_eero_name") or "Gateway"

        params = {"title": title, "hostname": hostname, "ip": ip, "mac": mac, "node": eero_node, "band": band}
        text = tr("notifications.new_device_text", lang=active_lang, **params)
        db_msg = tr("notifications.new_device_db", lang=active_lang, **params)

        await self._dispatch_all_channels("new_device", title, text, db_msg, device, color=0x38bdf8)

    async def notify_node_offline(self, eero_node: Dict[str, Any], lang: Optional[str] = None):
        active_lang = await self.get_language(lang)

        title = tr("notifications.node_offline_title", lang=active_lang)
        name = eero_node.get("name", tr("notifications.node_default_name", lang=active_lang))
        ip = eero_node.get("ip", tr("notifications.not_available", lang=active_lang))

        text = tr("notifications.node_offline_text", lang=active_lang, title=title, name=name, ip=ip)
        db_msg = tr("notifications.node_offline_db", lang=active_lang, name=name, ip=ip)

        await self._dispatch_all_channels("node_offline", title, text, db_msg, eero_node, color=0xf59e0b)

    async def notify_cloud_unreachable(self, reason: str = "unreachable", consecutive_failures: int = 3, lang: Optional[str] = None):
        active_lang = await self.get_language(lang)
        is_auth = (reason == "unauthorized")

        if is_auth:
            title = tr("notifications.cloud_expired_title", lang=active_lang)
            body = tr("notifications.cloud_expired_body", lang=active_lang)
            db_msg = tr("notifications.cloud_expired_db", lang=active_lang)
        else:
            title = tr("notifications.cloud_unreachable_title", lang=active_lang)
            body = tr("notifications.cloud_unreachable_body", lang=active_lang, failures=consecutive_failures)
            db_msg = tr("notifications.cloud_unreachable_db", lang=active_lang, failures=consecutive_failures)
        text = tr("notifications.titled_text", lang=active_lang, title=title, body=body)

        await self._dispatch_all_channels("cloud_unreachable", title, text, db_msg, {"reason": reason, "consecutive_failures": consecutive_failures}, color=0xef4444)

    async def notify_cloud_recovered(self, lang: Optional[str] = None):
        active_lang = await self.get_language(lang)

        title = tr("notifications.cloud_recovered_title", lang=active_lang)
        body = tr("notifications.cloud_recovered_body", lang=active_lang)
        text = tr("notifications.titled_text", lang=active_lang, title=title, body=body)
        db_msg = tr("notifications.cloud_recovered_db", lang=active_lang)

        await self._dispatch_all_channels("cloud_recovered", title, text, db_msg, {"status": "connected"}, color=0x10b981)

    async def notify_digest(self, digest_summary: Dict[str, Any], lang: Optional[str] = None):
        active_lang = await self.get_language(lang)

        title = tr("notifications.digest_title", lang=active_lang)
        net_name = digest_summary.get("network_name", tr("notifications.default_network_name", lang=active_lang))
        health = digest_summary.get("health_score", 100)
        isp = digest_summary.get("isp", tr("notifications.not_available", lang=active_lang))
        active = digest_summary.get("active_devices_count", 0)
        c_6g = digest_summary.get("count_6ghz", 0)
        c_5g = digest_summary.get("count_5ghz", 0)
        c_24g = digest_summary.get("count_24ghz", 0)
        c_wired = digest_summary.get("count_wired", 0)
        nodes_on = digest_summary.get("online_nodes", 0)
        nodes_tot = digest_summary.get("total_nodes", 0)
        down = digest_summary.get("wan_down", 0)
        up = digest_summary.get("wan_up", 0)

        bands_detail = []
        if c_6g > 0: bands_detail.append(f"6 GHz: {c_6g}")
        if c_5g > 0: bands_detail.append(f"5 GHz: {c_5g}")
        if c_24g > 0: bands_detail.append(f"2.4 GHz: {c_24g}")
        if c_wired > 0: bands_detail.append(tr("notifications.digest_wired", lang=active_lang, count=c_wired))
        bands_str = " | ".join(bands_detail) if bands_detail else tr("notifications.digest_total", lang=active_lang, count=active)

        text = tr(
            "notifications.digest_text",
            lang=active_lang,
            title=title,
            network=net_name,
            health=health,
            isp=isp,
            nodes_on=nodes_on,
            nodes_tot=nodes_tot,
            active=active,
            bands=bands_str,
            down=down,
            up=up,
        )
        db_msg = tr("notifications.digest_db", lang=active_lang, active=active, nodes_on=nodes_on, nodes_tot=nodes_tot, isp=isp)

        await self._dispatch_all_channels("daily_digest", title, text, db_msg, digest_summary, color=0x6366f1)

    async def notify_bufferbloat_degradation(self, bb_result: Dict[str, Any], lang: Optional[str] = None):
        """Notifica degrado delle prestazioni di latenza sotto carico (Bufferbloat Grade D o F)."""
        active_lang = await self.get_language(lang)

        grade = str(bb_result.get("grade") or "D").upper()
        unloaded = bb_result.get("unloaded_latency_ms", 0)
        dl_lat = bb_result.get("download_latency_ms", 0)
        ul_lat = bb_result.get("upload_latency_ms", 0)

        title = tr("notifications.bufferbloat_title", lang=active_lang, grade=grade)
        text = tr("notifications.bufferbloat_text", lang=active_lang, title=title, grade=grade, unloaded=unloaded, dl=dl_lat, ul=ul_lat)
        db_msg = tr("notifications.bufferbloat_db", lang=active_lang, grade=grade, dl=dl_lat, ul=ul_lat)

        await self._dispatch_all_channels("bufferbloat_warning", title, text, db_msg, bb_result, color=0xf97316)

    async def notify_mesh_quality_warning(self, node_name: str, issue: str, lang: Optional[str] = None):
        """Notifica calo di qualità o interferenze su un nodo mesh."""
        active_lang = await self.get_language(lang)

        title = tr("notifications.mesh_warning_title", lang=active_lang, node=node_name)
        text = tr("notifications.mesh_warning_text", lang=active_lang, title=title, node=node_name, issue=issue)
        db_msg = tr("notifications.mesh_warning_db", lang=active_lang, node=node_name, issue=issue)

        await self._dispatch_all_channels("mesh_warning", title, text, db_msg, {"node_name": node_name, "issue": issue}, color=0xf59e0b)

    async def notify_security_auth_alert(self, ip: str, username: str, attempts: int, action: str, lang: Optional[str] = None):
        """Notifica alert di sicurezza su tentativi ripetuti di accesso fallito (Brute-Force)."""
        active_lang = await self.get_language(lang)

        title = tr("notifications.security_title", lang=active_lang)
        params = {"ip": ip, "username": username, "attempts": attempts, "action": action}
        text = tr("notifications.security_text", lang=active_lang, title=title, **params)
        db_msg = tr("notifications.security_db", lang=active_lang, **params)

        await self._dispatch_all_channels("security_auth", title, text, db_msg, {"ip": ip, "username": username, "attempts": attempts, "action": action}, color=0xd97706)

    async def notify_backup_status(self, success: bool, backup_name: str, details: str, lang: Optional[str] = None):
        """Notifica l'esito dell'esecuzione del backup programmato o di emergenza."""
        active_lang = await self.get_language(lang)

        if success:
            title = tr("notifications.backup_success_title", lang=active_lang)
            db_msg = tr("notifications.backup_success_db", lang=active_lang, name=backup_name, details=details)
            status_text = tr("notifications.backup_status_success", lang=active_lang)
            color = 0x10b981
        else:
            title = tr("notifications.backup_failed_title", lang=active_lang)
            db_msg = tr("notifications.backup_failed_db", lang=active_lang, name=backup_name, details=details)
            status_text = tr("notifications.backup_status_failed", lang=active_lang)
            color = 0xef4444

        text = tr("notifications.backup_text", lang=active_lang, title=title, name=backup_name, status=status_text, details=details)

        await self._dispatch_all_channels("backup_status", title, text, db_msg, {"success": success, "backup_name": backup_name, "details": details}, color=color)


notification_service = NotificationService()
