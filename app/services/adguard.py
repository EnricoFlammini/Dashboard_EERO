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

    def __init__(self):
        self._demo_settings: Dict[str, Any] = {
            "enabled": True,
            "url": "http://192.168.1.50:80",
            "username": "demo_admin",
            "password": "demo_password",
            "has_password": True,
            "last_sync_time": "2026-08-29T10:00:00Z",
            "last_sync_count": 18,
            "last_sync_status": "Completato: 18 sincronizzati (18 aggiunti, 0 aggiornati) [Simulazione Demo]",
        }

    async def get_settings(self) -> Dict[str, Any]:
        """Recupera le impostazioni correnti di AdGuard Home salvate nel database o fittizie in ambiente demo."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            return {
                "enabled": bool(self._demo_settings.get("enabled", True)),
                "url": self._demo_settings.get("url", "http://192.168.1.50:80"),
                "username": self._demo_settings.get("username", "demo_admin"),
                "has_password": bool(self._demo_settings.get("has_password", True)),
                "last_sync_time": self._demo_settings.get("last_sync_time", "2026-08-29T10:00:00Z"),
                "last_sync_count": int(self._demo_settings.get("last_sync_count", 18)),
                "last_sync_status": self._demo_settings.get("last_sync_status", "Completato: 18 sincronizzati (18 aggiunti, 0 aggiornati) [Simulazione Demo]"),
            }

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
        """Salva le impostazioni di AdGuard Home nel database SQLite (o in memoria in Demo Mode)."""
        clean_url = normalize_adguard_url(url)
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            self._demo_settings["enabled"] = enabled
            self._demo_settings["url"] = clean_url
            if username is not None:
                self._demo_settings["username"] = username.strip()
            if password is not None and password != "":
                self._demo_settings["password"] = password.strip()
                self._demo_settings["has_password"] = True
            return

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
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            target_url = normalize_adguard_url(url if url is not None and url.strip() != "" else self._demo_settings.get("url", "http://192.168.1.50:80"))
            return {
                "success": True,
                "status_code": 200,
                "normalized_url": target_url,
                "message": "Connessione riuscita! (Ambiente Demo Simulato - 18 client rilevati su AdGuard Home)",
                "existing_clients_count": 18,
            }

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
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            total_count = len(devices)
            now_iso = datetime.now(timezone.utc).isoformat()
            status_text = f"Completato: {total_count} sincronizzati ({total_count} aggiunti, 0 aggiornati) [Simulazione Demo]"
            self._demo_settings["last_sync_time"] = now_iso
            self._demo_settings["last_sync_count"] = total_count
            self._demo_settings["last_sync_status"] = status_text
            if url:
                self._demo_settings["url"] = normalize_adguard_url(url)
            if username:
                self._demo_settings["username"] = username.strip()
            return {
                "success": True,
                "total_synced": total_count,
                "added_count": total_count,
                "updated_count": 0,
                "failed_count": 0,
                "message": status_text,
                "last_sync_time": now_iso,
            }
        settings = await self.get_settings()
        raw_url = url if url is not None and url.strip() != "" else settings.get("url", "")
        target_url = normalize_adguard_url(raw_url)
        target_user = username if username is not None else settings.get("username", "")
        
        target_pass = password
        if target_pass is not None and target_pass != "":
            await db_service.set_setting("adguard_password", target_pass.strip())
        else:
            target_pass = await db_service.get_setting("adguard_password", "")

        if raw_url:
            await db_service.set_setting("adguard_url", target_url)
        if username is not None:
            await db_service.set_setting("adguard_username", target_user.strip())

        if not target_url:
            return {"success": False, "message": "URL di AdGuard Home non impostato."}

        auth = (target_user, target_pass) if target_user and target_pass else None

        existing_clients_by_name: Dict[str, Dict[str, Any]] = {}
        existing_clients_by_id: Dict[str, Dict[str, Any]] = {}

        async def _fetch_adguard_clients(http_client: httpx.AsyncClient) -> bool:
            try:
                resp = await http_client.get(f"{target_url}/control/clients", auth=auth)
                if resp.status_code == 200:
                    existing_clients_by_name.clear()
                    existing_clients_by_id.clear()
                    resp_data = resp.json() if isinstance(resp.json(), dict) else {}
                    for c in (resp_data.get("clients") or []):
                        if isinstance(c, dict):
                            c_name = c.get("name")
                            if c_name:
                                existing_clients_by_name[c_name.lower()] = c
                            for cid in (c.get("ids") or []):
                                if cid:
                                    existing_clients_by_id[str(cid).strip().lower()] = c
                    return True
                elif resp.status_code in (401, 403):
                    return False
            except Exception as e:
                logger.warning(f"Impossibile recuperare i client esistenti da AdGuard ({e})")
            return True

        # Calcola occorrenze di ciascun IP per escludere indirizzi gateway o broadcast condivisi
        ip_counts: Dict[str, int] = {}
        for dev in devices:
            raw_ips = []
            if dev.get("ip"):
                raw_ips.append(str(dev["ip"]).strip())
            for v6 in (dev.get("ipv6_addresses") or []):
                if isinstance(v6, str):
                    raw_ips.append(v6.strip())
            for single_ip in set(raw_ips):
                if single_ip:
                    ip_counts[single_ip.lower()] = ip_counts.get(single_ip.lower(), 0) + 1

        # Preparazione e disambiguazione dei dispositivi da sincronizzare
        used_names: Dict[str, int] = {}
        prepared_clients: List[Dict[str, Any]] = []

        for dev in devices:
            ip = dev.get("ip")
            mac = dev.get("mac")
            if not ip and not mac:
                continue

            ids: List[str] = []
            # 1. IPv4 pulito (solo se non condiviso tra più apparati)
            if ip and isinstance(ip, str) and "." in ip and not ip.startswith("169.254."):
                ip_clean = ip.strip()
                if ip_counts.get(ip_clean.lower(), 0) == 1:
                    ids.append(ip_clean)

            # 2. IPv6 globale/SLAAC instradabile (esclude link-local fe80:, gateway ::1 e IP condivisi)
            for v6 in (dev.get("ipv6_addresses") or []):
                if isinstance(v6, str) and ":" in v6 and not v6.lower().startswith("fe80:"):
                    v6_clean = v6.strip()
                    if v6_clean.endswith("::1"):
                        continue  # Gateway / Thread router loopback
                    if ip_counts.get(v6_clean.lower(), 0) == 1:
                        if v6_clean not in ids:
                            ids.append(v6_clean)

            # 3. MAC address pulito (univoco per scheda di rete)
            if mac and isinstance(mac, str) and len(mac) >= 12:
                mac_clean = mac.strip().upper()
                if mac_clean not in ids:
                    ids.append(mac_clean)

            if not ids:
                continue

            base_name = str(dev.get("nickname") or dev.get("hostname") or dev.get("device_name") or f"eero-{ip or mac}").strip()
            
            # Se esistono più dispositivi con lo stesso identico nome, disambigua con suffisso IP/MAC
            if base_name in used_names:
                used_names[base_name] += 1
                suffix = ip.split(".")[-1] if (ip and "." in ip) else (mac[-5:].replace(":", "") if mac else str(used_names[base_name]))
                unique_name = f"{base_name} ({suffix})"
            else:
                used_names[base_name] = 1
                unique_name = base_name

            prepared_clients.append({
                "name": unique_name,
                "ids": ids,
                "tags": [],
                "upstreams": [],
                "blocked_services": [],
                "use_global_blocked_services": True,
                "use_global_settings": True,
                "filtering_enabled": True,
                "parental_enabled": False,
                "safebrowsing_enabled": True,
                "safesearch_enabled": False,
            })

        added_count = 0
        updated_count = 0
        failed_count = 0
        error_details: List[str] = []

        async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
            # 1. Recupero iniziale client su AdGuard
            auth_ok = await _fetch_adguard_clients(client)
            if not auth_ok:
                return {"success": False, "message": "Autenticazione AdGuard non valida (401/403). Verifica Username e Password."}

            for payload in prepared_clients:
                name = payload["name"]
                ids = payload["ids"]

                # Cerca corrispondenza: prima per ID (MAC o IP), poi per Nome
                matched_client = None
                for cid in ids:
                    matched_client = existing_clients_by_id.get(str(cid).lower())
                    if matched_client:
                        break

                if not matched_client:
                    matched_client = existing_clients_by_name.get(name.lower())

                if matched_client:
                    orig_name = matched_client.get("name") or name
                    endpoint = f"{target_url}/control/clients/update"
                    body_data = {"name": orig_name, "data": payload}
                    is_update = True
                else:
                    endpoint = f"{target_url}/control/clients/add"
                    body_data = payload
                    is_update = False

                try:
                    r = await client.post(endpoint, json=body_data, auth=auth)
                    if r.status_code in (200, 201, 204):
                        if is_update:
                            updated_count += 1
                        else:
                            added_count += 1
                        # Aggiorna mappe in memoria
                        existing_clients_by_name[name.lower()] = payload
                        for cid in ids:
                            existing_clients_by_id[str(cid).lower()] = payload
                    else:
                        # Se l'add fallisce perché esiste già un conflitto su AdGuard, ricarica e tenta l'update
                        if not is_update:
                            await _fetch_adguard_clients(client)
                            rematched = None
                            for cid in ids:
                                rematched = existing_clients_by_id.get(str(cid).lower())
                                if rematched:
                                    break
                            if not rematched:
                                rematched = existing_clients_by_name.get(name.lower())

                            if rematched:
                                target_orig = rematched.get("name") or name
                                r_upd = await client.post(
                                    f"{target_url}/control/clients/update",
                                    json={"name": target_orig, "data": payload},
                                    auth=auth
                                )
                                if r_upd.status_code in (200, 201, 204):
                                    updated_count += 1
                                    existing_clients_by_name[name.lower()] = payload
                                    for cid in ids:
                                        existing_clients_by_id[str(cid).lower()] = payload
                                    continue

                        err_text = r.text.strip()[:90]
                        err_entry = f"{name} (HTTP {r.status_code}: {err_text})"
                        error_details.append(err_entry)
                        logger.warning(f"Errore sync AdGuard per '{name}': {err_text}")
                        failed_count += 1
                except Exception as e:
                    error_details.append(f"{name}: {str(e)}")
                    logger.error(f"Eccezione sync AdGuard per '{name}': {e}")
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
        if total_synced == 0 and failed_count > 0:
            return {
                "success": False,
                "total_synced": 0,
                "failed_count": failed_count,
                "message": f"Sincronizzazione fallita per tutti i {failed_count} client. Errori: {'; '.join(error_details[:2])}",
                "last_sync_time": now_iso,
            }

        return {
            "success": True,
            "total_synced": total_synced,
            "added_count": added_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "message": status_text if failed_count == 0 else f"{status_text} ({'; '.join(error_details[:2])})",
            "last_sync_time": now_iso,
        }

    async def auto_sync_if_enabled(self, devices: List[Dict[str, Any]]) -> None:
        """Esegue la sincronizzazione silenziosa se il toggle adguard_sync_enabled è attivo."""
        try:
            from app.services.eero_client import eero_client
            if eero_client.is_demo_mode:
                if self._demo_settings.get("enabled"):
                    await self.sync_devices(devices)
                return

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
