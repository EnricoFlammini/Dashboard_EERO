import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from app.services.db import db_service
from app.services.eero_client import get_adguard_tags

logger = logging.getLogger(__name__)


def normalize_adguard_url(url: str) -> str:
    """Pulisce e normalizza l'URL di AdGuard Home rimuovendo frammenti (#), trailing slash e aggiungendo http:// se omesso."""
    if not url:
        return ""
    clean = url.strip()
    if "#" in clean:
        clean = clean.split("#")[0]
    clean = clean.rstrip("/")
    if not clean.startswith("http://") and not clean.startswith("https://"):
        clean = f"http://{clean}"
    return clean


class AdGuardService:
    """Service to handle communication and client synchronization with one or multiple AdGuard Home instances."""

    def __init__(self):
        self._demo_settings: Dict[str, Any] = {
            "enabled": True,
            "instances": [
                {
                    "id": "inst-1",
                    "name": "DNS Primario",
                    "url": "http://192.168.1.50:80",
                    "username": "demo_admin",
                    "password": "demo_password",
                    "has_password": True,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "Completato: 18 sincronizzati [Simulazione Demo]"
                },
                {
                    "id": "inst-2",
                    "name": "DNS Secondario",
                    "url": "http://192.168.1.51:80",
                    "username": "demo_admin",
                    "password": "demo_password",
                    "has_password": True,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "Completato: 18 sincronizzati [Simulazione Demo]"
                }
            ],
            "url": "http://192.168.1.50:80",
            "username": "demo_admin",
            "password": "demo_password",
            "has_password": True,
            "last_sync_time": "2026-08-29T10:00:00Z",
            "last_sync_count": 18,
            "last_sync_status": "Completato: 18 sincronizzati su 2 istanze [Simulazione Demo]",
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
                "last_sync_status": self._demo_settings.get("last_sync_status", "Completato: 18 sincronizzati [Simulazione Demo]"),
            }

        all_s = await db_service.get_all_settings()
        url = all_s.get("adguard_url", "")
        username = all_s.get("adguard_username", "")
        has_pwd = bool(all_s.get("adguard_password", ""))

        return {
            "enabled": all_s.get("adguard_sync_enabled", "false").lower() == "true",
            "url": url,
            "username": username,
            "has_password": has_pwd,
            "last_sync_time": all_s.get("adguard_last_sync_time", ""),
            "last_sync_count": int(all_s.get("adguard_last_sync_count", "0") or 0),
            "last_sync_status": all_s.get("adguard_last_sync_status", ""),
        }

    async def save_settings(
        self,
        enabled: bool,
        instances: Optional[List[Dict[str, Any]]] = None,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """Salva le impostazioni di AdGuard Home nel database SQLite (o in memoria in Demo Mode)."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            self._demo_settings["enabled"] = enabled
            if url is not None:
                self._demo_settings["url"] = normalize_adguard_url(url)
            if username is not None:
                self._demo_settings["username"] = username.strip()
            if password is not None and password != "":
                self._demo_settings["password"] = password.strip()
                self._demo_settings["has_password"] = True
            return

        await db_service.set_setting("adguard_sync_enabled", "true" if enabled else "false")
        if url is not None:
            clean_url = normalize_adguard_url(url)
            await db_service.set_setting("adguard_url", clean_url)
        if username is not None:
            await db_service.set_setting("adguard_username", username.strip())
        if password is not None and password != "":
            await db_service.set_setting("adguard_password", password.strip())

    async def test_single_instance(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Testa la connessione verso una singola istanza AdGuard Home."""
        target_url = normalize_adguard_url(url)
        if not target_url:
            return {"success": False, "message": "URL mancante o non specificato."}

        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            return {
                "success": True,
                "status_code": 200,
                "normalized_url": target_url,
                "message": "Connessione riuscita! (Ambiente Demo Simulato - 18 client rilevati)",
                "existing_clients_count": 18,
            }

        auth = (username.strip(), password.strip()) if username and password else None
        urls_to_try = [target_url]
        if target_url.startswith("https://"):
            urls_to_try.append(target_url.replace("https://", "http://", 1))

        last_error_msg = ""
        for try_url in urls_to_try:
            try:
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
                            "message": f"Connessione riuscita! Trovati {len(clients)} client manuali ({len(auto_clients)} scoperti automaticamente).",
                            "existing_clients_count": len(clients),
                        }
                    elif resp.status_code in (401, 403):
                        return {
                            "success": False,
                            "status_code": resp.status_code,
                            "message": "Autenticazione fallita (401/403). Verifica che Username e Password siano corretti.",
                        }
                    else:
                        last_error_msg = f"AdGuard Home ha risposto con codice HTTP {resp.status_code}: {resp.text[:100]}"
            except httpx.ConnectError:
                last_error_msg = f"Impossibile raggiungere '{try_url}'. Verifica IP, porta e protocollo (http/https)."
            except httpx.TimeoutException:
                last_error_msg = f"Timeout connessione verso '{try_url}' (oltre 8 secondi)."
            except Exception as e:
                last_error_msg = f"Errore di connessione: {str(e)}"

        return {"success": False, "message": last_error_msg}

    async def test_connection(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        instances: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Testa la connessione verso l'istanza AdGuard Home."""
        from app.services.eero_client import eero_client
        cur = await self.get_settings()
        target_url = url or cur.get("url")
        target_user = username if username is not None else cur.get("username")
        target_pass = password
        if (target_pass is None or target_pass == "") and cur.get("has_password"):
            target_pass = (await db_service.get_setting("adguard_password", "")) or (self._demo_settings.get("password") if eero_client.is_demo_mode else "")

        return await self.test_single_instance(target_url or "", target_user or "", target_pass or "")

    def _prepare_clients(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepara e disambigua l'elenco dei client per il payload AdGuard Home."""
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

        used_names: Dict[str, int] = {}
        prepared_clients: List[Dict[str, Any]] = []

        for dev in devices:
            ip = dev.get("ip")
            mac = dev.get("mac")
            if not ip and not mac:
                continue

            ids: List[str] = []
            if ip and isinstance(ip, str) and "." in ip and not ip.startswith("169.254."):
                ip_clean = ip.strip()
                if ip_counts.get(ip_clean.lower(), 0) == 1:
                    ids.append(ip_clean)

            for v6 in (dev.get("ipv6_addresses") or []):
                if isinstance(v6, str) and ":" in v6 and not v6.lower().startswith("fe80:"):
                    v6_clean = v6.strip()
                    if v6_clean.endswith("::1"):
                        continue
                    if ip_counts.get(v6_clean.lower(), 0) == 1:
                        if v6_clean not in ids:
                            ids.append(v6_clean)

            if mac and isinstance(mac, str) and len(mac) >= 12:
                mac_clean = mac.strip().upper()
                if mac_clean not in ids:
                    ids.append(mac_clean)

            if not ids:
                continue

            base_name = str(dev.get("nickname") or dev.get("hostname") or dev.get("device_name") or f"eero-{ip or mac}").strip()
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
                "tags": get_adguard_tags(dev.get("category"), dev.get("custom_icon")),
                "upstreams": [],
                "blocked_services": [],
                "use_global_blocked_services": True,
                "use_global_settings": True,
                "filtering_enabled": True,
                "parental_enabled": False,
                "safebrowsing_enabled": True,
                "safesearch_enabled": False,
            })

        return prepared_clients

    def _merge_adguard_client_data(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """Preserva al 100% tutte le regole personalizzate, filtri, upstreams e blacklist di AdGuard Home (Issue #21)."""
        merged = dict(existing)

        # 1. Aggiorna nome con quello formattato da eero
        merged["name"] = incoming.get("name") or existing.get("name")

        # 2. Merge degli identificatori (IP, IPv6, MAC) preservando ID custom aggiunti dall'utente in AdGuard
        existing_ids = [str(x).strip() for x in (existing.get("ids") or []) if str(x).strip()]
        incoming_ids = [str(x).strip() for x in (incoming.get("ids") or []) if str(x).strip()]
        
        merged_ids = list(existing_ids)
        existing_ids_lower = {x.lower() for x in existing_ids}
        for i_id in incoming_ids:
            if i_id.lower() not in existing_ids_lower:
                merged_ids.append(i_id)
                existing_ids_lower.add(i_id.lower())
        merged["ids"] = merged_ids

        # 3. Tags: se l'utente ha già impostato tag custom su AdGuard, li preserva; altrimenti applica quelli di eero
        if not existing.get("tags") and incoming.get("tags"):
            merged["tags"] = incoming["tags"]

        # 4. Tutti i campi di regole e configurazione (upstreams, blocked_services, filtering_enabled,
        # parental_enabled, safebrowsing_enabled, safesearch_enabled, use_global_settings, ecc.)
        # vengono ereditati e preservati integralmente dall'oggetto existing.
        return merged

    async def _sync_single_target(
        self,
        target_url: str,
        auth: Optional[tuple],
        prepared_clients: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sincronizza i client verso una singola istanza AdGuard Home preservando le regole esistenti."""
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
                logger.warning(f"Impossibile recuperare client da {target_url} ({e})")
            return True

        added_count = 0
        updated_count = 0
        failed_count = 0
        error_details: List[str] = []

        async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
            auth_ok = await _fetch_adguard_clients(client)
            if not auth_ok:
                return {
                    "success": False,
                    "added": 0,
                    "updated": 0,
                    "failed": len(prepared_clients),
                    "message": f"Autenticazione fallita su {target_url} (401/403)."
                }

            for payload in prepared_clients:
                name = payload["name"]
                ids = payload["ids"]

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
                    update_data = self._merge_adguard_client_data(matched_client, payload)
                    body_data = {"name": orig_name, "data": update_data}
                    is_update = True
                    client_record = update_data
                else:
                    endpoint = f"{target_url}/control/clients/add"
                    body_data = payload
                    is_update = False
                    client_record = payload

                try:
                    r = await client.post(endpoint, json=body_data, auth=auth)
                    if r.status_code in (200, 201, 204):
                        if is_update:
                            updated_count += 1
                        else:
                            added_count += 1
                        existing_clients_by_name[name.lower()] = client_record
                        for cid in client_record.get("ids", ids):
                            existing_clients_by_id[str(cid).lower()] = client_record
                    else:
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
                                upd_data = self._merge_adguard_client_data(rematched, payload)
                                r_upd = await client.post(
                                    f"{target_url}/control/clients/update",
                                    json={"name": target_orig, "data": upd_data},
                                    auth=auth
                                )
                                if r_upd.status_code in (200, 201, 204):
                                    updated_count += 1
                                    existing_clients_by_name[name.lower()] = upd_data
                                    for cid in upd_data.get("ids", ids):
                                        existing_clients_by_id[str(cid).lower()] = upd_data
                                    continue

                        err_text = r.text.strip()[:90]
                        error_details.append(f"{name} (HTTP {r.status_code})")
                        failed_count += 1
                except Exception as e:
                    error_details.append(f"{name}: {str(e)}")
                    failed_count += 1

        total_synced = added_count + updated_count
        return {
            "success": total_synced > 0 or failed_count == 0,
            "added": added_count,
            "updated": updated_count,
            "failed": failed_count,
            "total_synced": total_synced,
            "errors": error_details
        }

    async def sync_devices(
        self,
        devices: List[Dict[str, Any]],
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        instances: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Sincronizza l'elenco dei dispositivi verso tutte le istanze AdGuard Home configurate."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            total_count = len(devices)
            now_iso = datetime.now(timezone.utc).isoformat()
            status_text = f"Completato: {total_count} sincronizzati ({total_count} aggiunti, 0 aggiornati) [Simulazione Demo]"
            self._demo_settings["last_sync_time"] = now_iso
            self._demo_settings["last_sync_count"] = total_count
            self._demo_settings["last_sync_status"] = status_text
            return {
                "success": True,
                "total_synced": total_count,
                "added_count": total_count,
                "updated_count": 0,
                "failed_count": 0,
                "message": status_text,
                "last_sync_time": now_iso,
            }

        cur = await self.get_settings()
        target_url = normalize_adguard_url(url or cur.get("url", ""))
        target_user = username if username is not None else cur.get("username", "")
        target_pass = password
        if (target_pass is None or target_pass == "") and cur.get("has_password"):
            target_pass = await db_service.get_setting("adguard_password", "")

        if not target_url:
            return {"success": False, "message": "Nessun URL AdGuard Home configurato."}

        prepared_clients = self._prepare_clients(devices)
        if not prepared_clients:
            return {"success": False, "message": "Nessun client valido trovato da sincronizzare."}

        auth = (target_user.strip(), target_pass.strip()) if target_user and target_pass else None
        res = await self._sync_single_target(target_url, auth, prepared_clients)

        now_iso = datetime.now(timezone.utc).isoformat()
        status_text = f"Completato: {res.get('total_synced', 0)} client ({res.get('added', 0)} aggiunti, {res.get('updated', 0)} aggiornati)"
        if res.get("failed", 0) > 0:
            status_text += f", {res.get('failed')} falliti"

        await db_service.set_setting("adguard_last_sync_time", now_iso)
        await db_service.set_setting("adguard_last_sync_count", str(res.get("total_synced", 0)))
        await db_service.set_setting("adguard_last_sync_status", status_text)

        return {
            "success": res.get("success", False),
            "total_synced": res.get("total_synced", 0),
            "added_count": res.get("added", 0),
            "updated_count": res.get("updated", 0),
            "failed_count": res.get("failed", 0),
            "message": status_text,
            "last_sync_time": now_iso,
            "errors": res.get("errors", [])
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
            if not settings.get("instances") and not settings.get("url"):
                return

            logger.info("AdGuard Home Auto-Sync in esecuzione per i dispositivi correnti...")
            await self.sync_devices(devices)
        except Exception as e:
            logger.error(f"Errore durante l'auto-sync silenzioso con AdGuard Home: {e}")


adguard_service = AdGuardService()

