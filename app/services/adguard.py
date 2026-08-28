import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from app.services.db import db_service

logger = logging.getLogger(__name__)


def normalize_adguard_url(url: str) -> str:
    """Pulisce e normalizza l'URL di AdGuard Home rimuovendo frammenti (#), trailing slash e aggiungendo http:// se omesso."""
    if not url:
        return ""
    clean = url.strip()
    # Rimuove frammenti hash del browser (es. /# o #)
    if "#" in clean:
        clean = clean.split("#")[0]
    clean = clean.rstrip("/")
    if not clean.startswith("http://") and not clean.startswith("https://"):
        clean = f"http://{clean}"
    return clean


class AdGuardService:
    """Service to handle communication and client synchronization with AdGuard Home."""

    async def get_settings(self) -> Dict[str, Any]:
        """Recupera le impostazioni correnti di AdGuard Home salvate nel database."""
        all_s = await db_service.get_all_settings()
        return {
            "enabled": all_s.get("adguard_sync_enabled", "false").lower() == "true",
            "url": all_s.get("adguard_url", ""),
            "username": all_s.get("adguard_username", ""),
            "has_password": bool(all_s.get("adguard_password", "")),
            "last_sync_time": all_s.get("adguard_last_sync_time", ""),
            "last_sync_count": int(all_s.get("adguard_last_sync_count", "0") or 0),
            "last_sync_status": all_s.get("adguard_last_sync_status", ""),
        }

    async def save_settings(
        self,
        enabled: bool,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """Salva le impostazioni di AdGuard Home nel database SQLite."""
        clean_url = normalize_adguard_url(url)
        await db_service.set_setting("adguard_sync_enabled", "true" if enabled else "false")
        await db_service.set_setting("adguard_url", clean_url)
        if username is not None:
            await db_service.set_setting("adguard_username", username.strip())
        if password is not None and password != "":
            await db_service.set_setting("adguard_password", password.strip())

    async def test_connection(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Testa la connessione e l'autenticazione verso un'istanza AdGuard Home."""
        settings = await self.get_settings()
        raw_url = url if url is not None and url.strip() != "" else settings.get("url", "")
        target_url = normalize_adguard_url(raw_url)
        target_user = username if username is not None else settings.get("username", "")
        
        # Se password non passata esplicitamente, recupera dal DB
        target_pass = password
        if target_pass is None or target_pass == "":
            target_pass = await db_service.get_setting("adguard_password", "")

        if not target_url:
            return {"success": False, "message": "URL di AdGuard Home mancante o non configurato."}

        auth = (target_user, target_pass) if target_user and target_pass else None

        # Tentativo primario con URL fornito + fallback automatico https -> http se fallisce
        urls_to_try = [target_url]
        if target_url.startswith("https://"):
            urls_to_try.append(target_url.replace("https://", "http://", 1))

        last_error_msg = ""
        for try_url in urls_to_try:
            try:
                # verify=False per supportare certificati self-signed su IP locali (es. 192.168.x.x)
                async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                    resp = await client.get(f"{try_url}/control/clients", auth=auth)
                    if resp.status_code == 200:
                        data = resp.json() if isinstance(resp.json(), dict) else {}
                        clients = data.get("clients") or []
                        auto_clients = data.get("auto_clients") or []
                        return {
                            "success": True,
                            "status_code": 200,
                            "normalized_url": try_url,
                            "message": f"Connessione riuscita! Trovati {len(clients)} client manuali ({len(auto_clients)} scoperti automaticamente) su AdGuard Home.",
                            "existing_clients_count": len(clients),
                        }
                    elif resp.status_code in (401, 403):
                        return {
                            "success": False,
                            "status_code": resp.status_code,
                            "message": "Autenticazione fallita (401/403). Verifica che Username e Password siano corretti.",
                        }
                    else:
                        last_error_msg = f"AdGuard Home ha risposto con codice HTTP {resp.status_code}: {resp.text[:120]}"
            except httpx.ConnectError:
                last_error_msg = f"Impossibile raggiungere il server AdGuard Home all'indirizzo '{try_url}'. Verifica che l'IP e la porta siano corretti e che il protocollo sia http (non https)."
            except httpx.TimeoutException:
                last_error_msg = f"Timeout connessione verso AdGuard Home all'indirizzo '{try_url}' (oltre 8 secondi)."
            except Exception as e:
                logger.error(f"Errore durante il test di connessione AdGuard su {try_url}: {e}")
                last_error_msg = f"Errore di connessione: {str(e)}"

        return {"success": False, "message": last_error_msg}

    async def sync_devices(
        self,
        devices: List[Dict[str, Any]],
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sincronizza l'elenco dei dispositivi verso AdGuard Home (/control/clients)."""
        settings = await self.get_settings()
        raw_url = url if url is not None and url.strip() != "" else settings.get("url", "")
        target_url = normalize_adguard_url(raw_url)
        target_user = username if username is not None else settings.get("username", "")
        
        target_pass = password
        if target_pass is None or target_pass == "":
            target_pass = await db_service.get_setting("adguard_password", "")

        if not target_url:
            return {"success": False, "message": "URL di AdGuard Home non impostato."}

        auth = (target_user, target_pass) if target_user and target_pass else None

        # 1. Recupero client esistenti su AdGuard per distinguere ADD da UPDATE
        existing_clients_map: Dict[str, Dict[str, Any]] = {}
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                resp = await client.get(f"{target_url}/control/clients", auth=auth)
                if resp.status_code == 200:
                    resp_data = resp.json() if isinstance(resp.json(), dict) else {}
                    for c in (resp_data.get("clients") or []):
                        if isinstance(c, dict) and c.get("name"):
                            existing_clients_map[c["name"]] = c
                elif resp.status_code in (401, 403):
                    return {"success": False, "message": "Autenticazione AdGuard non valida (401/403). Verifica le credenziali."}
        except Exception as e:
            logger.warning(f"Impossibile recuperare i client esistenti da AdGuard ({e}), si tenterà l'inserimento diretto.")

        # 2. Preparazione client da sincronizzare
        added_count = 0
        updated_count = 0
        failed_count = 0

        async with httpx.AsyncClient(timeout=6.0, verify=False, follow_redirects=True) as client:
            for dev in devices:
                ip = dev.get("ip")
                mac = dev.get("mac")
                if not ip and not mac:
                    continue

                ids = []
                if ip and not ip.startswith("169.254."):
                    ids.append(ip)
                if mac:
                    ids.append(mac.upper())

                if not ids:
                    continue

                name = dev.get("nickname") or dev.get("hostname") or dev.get("device_name") or f"eero-{ip or mac}"

                tags = ["eero-mesh"]
                if dev.get("connection_type") == "wired":
                    tags.append("wired")
                elif dev.get("wireless_band"):
                    tags.append(f"wifi-{dev.get('wireless_band')}".lower().replace(" ", "").replace(".", ""))

                payload = {
                    "name": name,
                    "ids": ids,
                    "tags": tags,
                    "use_global_settings": True,
                    "filtering_enabled": True,
                    "parental_enabled": False,
                    "safebrowsing_enabled": True
                }

                is_update = name in existing_clients_map
                endpoint = f"{target_url}/control/clients/update" if is_update else f"{target_url}/control/clients/add"
                body_data = {"name": name, "data": payload} if is_update else payload

                try:
                    r = await client.post(endpoint, json=body_data, auth=auth)
                    if r.status_code in (200, 201, 204):
                        if is_update:
                            updated_count += 1
                        else:
                            added_count += 1
                    else:
                        # Se fallisce update, prova add di fallback
                        if is_update:
                            r_fallback = await client.post(f"{target_url}/control/clients/add", json=payload, auth=auth)
                            if r_fallback.status_code in (200, 201, 204):
                                added_count += 1
                                continue
                        logger.warning(f"Errore sincronizzazione client '{name}' su AdGuard: {r.status_code} - {r.text[:80]}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Eccezione durante la sincronizzazione di '{name}' su AdGuard: {e}")
                    failed_count += 1

        total_synced = added_count + updated_count
        now_iso = datetime.now(timezone.utc).isoformat()
        status_text = f"Completato: {total_synced} sincronizzati ({added_count} aggiunti, {updated_count} aggiornati)"
        if failed_count > 0:
            status_text += f", {failed_count} falliti"

        # Aggiorna statistiche ultimo sync su SQLite
        await db_service.set_setting("adguard_last_sync_time", now_iso)
        await db_service.set_setting("adguard_last_sync_count", str(total_synced))
        await db_service.set_setting("adguard_last_sync_status", status_text)

        logger.info(f"AdGuard Sync completato: {status_text}")
        return {
            "success": True,
            "total_synced": total_synced,
            "added_count": added_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "message": status_text,
            "last_sync_time": now_iso,
        }

    async def auto_sync_if_enabled(self, devices: List[Dict[str, Any]]) -> None:
        """Esegue la sincronizzazione silenziosa se il toggle adguard_sync_enabled è attivo."""
        try:
            settings = await self.get_settings()
            if not settings.get("enabled"):
                return
            if not settings.get("url"):
                return

            logger.info("AdGuard Home Auto-Sync in esecuzione per i dispositivi correnti...")
            await self.sync_devices(devices)
        except Exception as e:
            logger.error(f"Errore durante l'auto-sync silenzioso con AdGuard Home: {e}")


adguard_service = AdGuardService()
