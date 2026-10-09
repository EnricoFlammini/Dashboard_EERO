import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
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
                return demo_lang.lower()
        lang = await db_service.get_setting("system_language", settings.dashboard_lang)
        return lang.lower() if lang and lang.lower() in ("it", "en") else "en"

    async def set_language(self, lang: str):
        """Sets the active system language."""
        lang = lang.lower().strip()
        if lang in ("it", "en"):
            self._demo_settings["system_language"] = lang
            await db_service.set_setting("system_language", lang)

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
        is_it = (active_lang == "it")

        title = "🚨 Nuovo Dispositivo Rilevato nella Rete eero!" if is_it else "🚨 New Device Detected on eero Network!"
        hostname = device.get("hostname") or device.get("nickname") or ("Sconosciuto" if is_it else "Unknown")
        mac = device.get("mac") or device.get("mac_address") or ("N/D" if is_it else "N/A")
        ip = device.get("ip") or ("N/D" if is_it else "N/A")
        band = device.get("wireless_band") or device.get("connection_type") or ("N/D" if is_it else "N/A")
        eero_node = device.get("connected_eero_name") or "Gateway"

        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"• <b>Host:</b> <code>{hostname}</code>\n"
                f"• <b>IP:</b> <code>{ip}</code>\n"
                f"• <b>MAC:</b> <code>{mac}</code>\n"
                f"• <b>Collegato a:</b> {eero_node} ({band})\n"
            )
            db_msg = f"Dispositivo '{hostname}' (IP: {ip}, MAC: {mac}) collegato al nodo {eero_node}."
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"• <b>Host:</b> <code>{hostname}</code>\n"
                f"• <b>IP:</b> <code>{ip}</code>\n"
                f"• <b>MAC:</b> <code>{mac}</code>\n"
                f"• <b>Connected to:</b> {eero_node} ({band})\n"
            )
            db_msg = f"Device '{hostname}' (IP: {ip}, MAC: {mac}) connected to node {eero_node}."

        await self._dispatch_all_channels("new_device", title, text, db_msg, device, color=0x38bdf8)

    async def notify_node_offline(self, eero_node: Dict[str, Any], lang: Optional[str] = None):
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        title = "⚠️ Nodo eero Mesh Offline!" if is_it else "⚠️ eero Mesh Node Offline!"
        name = eero_node.get("name", "Nodo Mesh" if is_it else "Mesh Node")
        ip = eero_node.get("ip", "N/D" if is_it else "N/A")
        
        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"Il nodo mesh <b>{name}</b> (IP: <code>{ip}</code>) risulta non raggiungibile o offline."
            )
            db_msg = f"Il nodo mesh {name} ({ip}) risulta offline."
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"The mesh node <b>{name}</b> (IP: <code>{ip}</code>) is unreachable or offline."
            )
            db_msg = f"Mesh node {name} ({ip}) is offline."

        await self._dispatch_all_channels("node_offline", title, text, db_msg, eero_node, color=0xf59e0b)

    async def notify_cloud_unreachable(self, reason: str = "unreachable", consecutive_failures: int = 3, lang: Optional[str] = None):
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")
        is_auth = (reason == "unauthorized")

        if is_auth:
            title = "🔐 Sessione Cloud eero Scaduta!" if is_it else "🔐 eero Cloud Session Expired!"
            text = (
                f"<b>{title}</b>\n\n"
                f"{'La sessione con il cloud eero è scaduta o non è più valida (HTTP 401). È necessario eseguire nuovamente l\'accesso per ripristinare il monitoraggio.' if is_it else 'The session with eero cloud has expired or is no longer valid (HTTP 401). Re-login is required to restore monitoring.'}"
            )
            db_msg = "Sessione cloud eero scaduta (HTTP 401). Re-login richiesto." if is_it else "eero cloud session expired (HTTP 401). Re-login required."
        else:
            title = "⚠️ Cloud eero Non Raggiungibile!" if is_it else "⚠️ eero Cloud Unreachable!"
            text = (
                f"<b>{title}</b>\n\n"
                f"{f'Il cloud eero non risponde dopo {consecutive_failures} tentativi consecutivi. I dati in dashboard potrebbero non essere aggiornati (modalità cache attiva).' if is_it else f'eero cloud is unreachable after {consecutive_failures} consecutive poll attempts. Dashboard data may be stale (serving cached state).'}"
            )
            db_msg = f"Cloud eero non raggiungibile ({consecutive_failures} tentativi falliti)." if is_it else f"eero cloud unreachable ({consecutive_failures} failed attempts)."

        await self._dispatch_all_channels("cloud_unreachable", title, text, db_msg, {"reason": reason, "consecutive_failures": consecutive_failures}, color=0xef4444)

    async def notify_cloud_recovered(self, lang: Optional[str] = None):
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        title = "✅ Connessione Cloud eero Ripristinata!" if is_it else "✅ eero Cloud Connection Restored!"
        text = (
            f"<b>{title}</b>\n\n"
            f"{'La connessione con i server cloud eero è tornata operativa. Il monitoraggio e la sincronizzazione telemetria sono ripresi regolarmente.' if is_it else 'Connection to eero cloud servers has been restored. Monitoring and telemetry sync have resumed normally.'}"
        )
        db_msg = "Connessione cloud eero ripristinata con successo." if is_it else "eero cloud connection restored successfully."

        await self._dispatch_all_channels("cloud_recovered", title, text, db_msg, {"status": "connected"}, color=0x10b981)

    async def notify_digest(self, digest_summary: Dict[str, Any], lang: Optional[str] = None):
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        title = "📊 Riepilogo Giornaliero eero Mesh" if is_it else "📊 eero Mesh Daily Digest"
        net_name = digest_summary.get("network_name", "Rete eero" if is_it else "eero Network")
        health = digest_summary.get("health_score", 100)
        isp = digest_summary.get("isp", "N/D" if is_it else "N/A")
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
        if c_wired > 0: bands_detail.append(f"Cablati: {c_wired}" if is_it else f"Wired: {c_wired}")
        bands_str = " | ".join(bands_detail) if bands_detail else (f"{active} totali" if is_it else f"{active} total")

        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"🏠 <b>Rete:</b> {net_name} (Health Score: <b>{health}/100</b>)\n"
                f"🌐 <b>Provider Internet (ISP):</b> {isp}\n"
                f"📡 <b>Nodi Mesh Operativi:</b> {nodes_on}/{nodes_tot}\n"
                f"📱 <b>Client Attivi:</b> {active}\n"
                f"📶 <b>Frequenze Wi-Fi:</b> {bands_str}\n"
                f"⚡ <b>Speed Test Gateway:</b> ↓ {down} Mbps / ↑ {up} Mbps\n"
            )
            db_msg = f"Report giornaliero inviato: {active} client connessi, {nodes_on}/{nodes_tot} nodi mesh attivi, ISP: {isp}."
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"🏠 <b>Network:</b> {net_name} (Health Score: <b>{health}/100</b>)\n"
                f"🌐 <b>Internet Provider (ISP):</b> {isp}\n"
                f"📡 <b>Operational Mesh Nodes:</b> {nodes_on}/{nodes_tot}\n"
                f"📱 <b>Active Clients:</b> {active}\n"
                f"📶 <b>Wi-Fi Frequencies:</b> {bands_str}\n"
                f"⚡ <b>Gateway Speed Test:</b> ↓ {down} Mbps / ↑ {up} Mbps\n"
            )
            db_msg = f"Daily digest report sent: {active} connected clients, {nodes_on}/{nodes_tot} active mesh nodes, ISP: {isp}."

        await self._dispatch_all_channels("daily_digest", title, text, db_msg, digest_summary, color=0x6366f1)

    async def notify_bufferbloat_degradation(self, bb_result: Dict[str, Any], lang: Optional[str] = None):
        """Notifica degrado delle prestazioni di latenza sotto carico (Bufferbloat Grade D o F)."""
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        grade = str(bb_result.get("grade") or "D").upper()
        unloaded = bb_result.get("unloaded_latency_ms", 0)
        dl_lat = bb_result.get("download_latency_ms", 0)
        ul_lat = bb_result.get("upload_latency_ms", 0)

        title = f"🐌 Degrado Bufferbloat Rilevato (Voto: {grade})!" if is_it else f"🐌 Bufferbloat Degradation Detected (Grade: {grade})!"
        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"La latenza di rete subisce forti ritardi sotto carico:\n"
                f"• <b>Voto Bufferbloat:</b> <code>{grade}</code>\n"
                f"• <b>Latenza a Riposo:</b> {unloaded} ms\n"
                f"• <b>Latenza in Download:</b> +{dl_lat} ms\n"
                f"• <b>Latenza in Upload:</b> +{ul_lat} ms\n\n"
                f"<i>Consiglio: verifica la funzione SQM (Smart Queue Management) su eero o riduci il traffico concorrente.</i>"
            )
            db_msg = f"Bufferbloat degradato: Voto {grade}, latenza download +{dl_lat}ms, upload +{ul_lat}ms."
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"Network latency experiences significant delays under load:\n"
                f"• <b>Bufferbloat Grade:</b> <code>{grade}</code>\n"
                f"• <b>Unloaded Latency:</b> {unloaded} ms\n"
                f"• <b>Download Latency:</b> +{dl_lat} ms\n"
                f"• <b>Upload Latency:</b> +{ul_lat} ms\n\n"
                f"<i>Tip: Check SQM (Smart Queue Management) in the eero app or prioritize bandwidth hogs.</i>"
            )
            db_msg = f"Bufferbloat degradation: Grade {grade}, dl latency +{dl_lat}ms, ul latency +{ul_lat}ms."

        await self._dispatch_all_channels("bufferbloat_warning", title, text, db_msg, bb_result, color=0xf97316)

    async def notify_mesh_quality_warning(self, node_name: str, issue: str, lang: Optional[str] = None):
        """Notifica calo di qualità o interferenze su un nodo mesh."""
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        title = f"📡 Qualità Segnale Nodo Mesh '{node_name}' Degradata" if is_it else f"📡 Mesh Node '{node_name}' Signal Quality Warning"
        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"Il nodo mesh <b>{node_name}</b> segnala problemi di backhaul o interferenze:\n"
                f"• <b>Dettagli:</b> {issue}\n"
            )
            db_msg = f"Allarme qualità mesh su {node_name}: {issue}."
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"Mesh node <b>{node_name}</b> reports backhaul degradation or wireless interference:\n"
                f"• <b>Details:</b> {issue}\n"
            )
            db_msg = f"Mesh quality alert on {node_name}: {issue}."

        await self._dispatch_all_channels("mesh_warning", title, text, db_msg, {"node_name": node_name, "issue": issue}, color=0xf59e0b)

    async def notify_security_auth_alert(self, ip: str, username: str, attempts: int, action: str, lang: Optional[str] = None):
        """Notifica alert di sicurezza su tentativi ripetuti di accesso fallito (Brute-Force)."""
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        title = "🛡️ Allarme Sicurezza: Tentativi di Login Falliti!" if is_it else "🛡️ Security Alert: Repeated Failed Login Attempts!"
        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"Rilevata attività sospetta di autenticazione locale:\n"
                f"• <b>Indirizzo IP:</b> <code>{ip}</code>\n"
                f"• <b>Nome Utente:</b> <code>{username}</code>\n"
                f"• <b>Tentativi consecutivi:</b> {attempts}\n"
                f"• <b>Azione intrapresa:</b> {action}\n"
            )
            db_msg = f"Sicurezza: {attempts} tentativi di accesso falliti da IP {ip} per l'utente '{username}'. Azione: {action}."
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"Suspicious local authentication activity detected:\n"
                f"• <b>IP Address:</b> <code>{ip}</code>\n"
                f"• <b>Username:</b> <code>{username}</code>\n"
                f"• <b>Failed Attempts:</b> {attempts}\n"
                f"• <b>Action taken:</b> {action}\n"
            )
            db_msg = f"Security: {attempts} failed login attempts from IP {ip} for user '{username}'. Action: {action}."

        await self._dispatch_all_channels("security_auth", title, text, db_msg, {"ip": ip, "username": username, "attempts": attempts, "action": action}, color=0xd97706)

    async def notify_backup_status(self, success: bool, backup_name: str, details: str, lang: Optional[str] = None):
        """Notifica l'esito dell'esecuzione del backup programmato o di emergenza."""
        active_lang = await self.get_language(lang)
        is_it = (active_lang == "it")

        if success:
            title = "💾 Backup Automatico Completato con Successo" if is_it else "💾 Automated Backup Completed Successfully"
            db_msg = f"Backup '{backup_name}' generato correttamente ({details})."
            color = 0x10b981
        else:
            title = "❌ Errore durante il Backup Automatico!" if is_it else "❌ Error during Automated Backup!"
            db_msg = f"Fallimento backup '{backup_name}': {details}."
            color = 0xef4444

        if is_it:
            text = (
                f"<b>{title}</b>\n\n"
                f"• <b>Archivio:</b> <code>{backup_name}</code>\n"
                f"• <b>Stato:</b> {'Completato ✅' if success else 'Fallito ❌'}\n"
                f"• <b>Dettagli:</b> {details}\n"
            )
        else:
            text = (
                f"<b>{title}</b>\n\n"
                f"• <b>Archive:</b> <code>{backup_name}</code>\n"
                f"• <b>Status:</b> {'Success ✅' if success else 'Failed ❌'}\n"
                f"• <b>Details:</b> {details}\n"
            )

        await self._dispatch_all_channels("backup_status", title, text, db_msg, {"success": success, "backup_name": backup_name, "details": details}, color=color)


notification_service = NotificationService()
