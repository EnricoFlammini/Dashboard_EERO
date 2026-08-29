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
            insts = self._demo_settings.get("instances", [])
            primary = insts[0] if insts else {}
            return {
                "enabled": bool(self._demo_settings.get("enabled", True)),
                "instances": insts,
                "url": primary.get("url", "http://192.168.1.50:80"),
                "username": primary.get("username", "demo_admin"),
                "has_password": bool(primary.get("has_password", True)),
                "last_sync_time": self._demo_settings.get("last_sync_time", "2026-08-29T10:00:00Z"),
                "last_sync_count": int(self._demo_settings.get("last_sync_count", 18)),
                "last_sync_status": self._demo_settings.get("last_sync_status", "Completato: 18 sincronizzati [Simulazione Demo]"),
            }

        all_s = await db_service.get_all_settings()
        inst_json = all_s.get("adguard_instances_json", "")
        instances = []
        if inst_json:
            try:
                instances = json.loads(inst_json)
            except Exception:
                instances = []

        # Se non ci sono istanze salvate in JSON, migra/usa i vecchi campi adguard_url
        if not instances:
            legacy_url = all_s.get("adguard_url", "")
            if legacy_url:
                instances = [{
                    "id": "inst-1",
                    "name": "DNS Primario",
                    "url": legacy_url,
                    "username": all_s.get("adguard_username", ""),
                    "has_password": bool(all_s.get("adguard_password", "")),
                    "enabled": True,
                    "last_sync_time": all_s.get("adguard_last_sync_time", ""),
                    "last_sync_status": all_s.get("adguard_last_sync_status", "")
                }]
            else:
                instances = [{
                    "id": "inst-1",
                    "name": "DNS Primario",
                    "url": "",
                    "username": "",
                    "has_password": False,
                    "enabled": True,
                    "last_sync_time": "",
                    "last_sync_status": ""
                }]

        primary = instances[0] if instances else {}
        return {
            "enabled": all_s.get("adguard_sync_enabled", "false").lower() == "true",
            "instances": instances,
            "url": primary.get("url", ""),
            "username": primary.get("username", ""),
            "has_password": bool(primary.get("has_password", False)),
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
            if instances is not None:
                self._demo_settings["instances"] = instances
            elif url is not None:
                self._demo_settings["url"] = normalize_adguard_url(url)
            return

        await db_service.set_setting("adguard_sync_enabled", "true" if enabled else "false")

        if instances is not None:
            # Recupera istanze correnti per preservare password invariate
            current_settings = await self.get_settings()
            current_map = {inst.get("id", str(i)): inst for i, inst in enumerate(current_settings.get("instances", []))}

            cleaned_instances = []
            for i, inst in enumerate(instances):
                inst_id = inst.get("id") or f"inst-{i+1}"
                old_inst = current_map.get(inst_id, {})
                c_url = normalize_adguard_url(inst.get("url", ""))
                c_user = (inst.get("username") or "").strip()
                new_pass = inst.get("password")

                if new_pass and str(new_pass).strip() != "":
                    final_pass = str(new_pass).strip()
                    has_pwd = True
                else:
                    final_pass = old_inst.get("password", "")
                    has_pwd = bool(final_pass) or bool(old_inst.get("has_password", False))

                cleaned_instances.append({
                    "id": inst_id,
                    "name": (inst.get("name") or f"DNS {i+1}").strip(),
                    "url": c_url,
                    "username": c_user,
                    "password": final_pass,
                    "has_password": has_pwd,
                    "enabled": bool(inst.get("enabled", True)),
                    "last_sync_time": inst.get("last_sync_time") or old_inst.get("last_sync_time", ""),
                    "last_sync_status": inst.get("last_sync_status") or old_inst.get("last_sync_status", "")
                })

            await db_service.set_setting("adguard_instances_json", json.dumps(cleaned_instances))

            # Sincronizza anche campi legacy per retrocompatibilità
            if cleaned_instances:
                primary = cleaned_instances[0]
                await db_service.set_setting("adguard_url", primary.get("url", ""))
                await db_service.set_setting("adguard_username", primary.get("username", ""))
                if primary.get("password"):
                    await db_service.set_setting("adguard_password", primary.get("password"))
        elif url is not None:
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
        """Testa una o tutte le istanze AdGuard Home configurate."""
        if instances:
            from app.services.eero_client import eero_client
            results = []
            all_ok = True
            for inst in instances:
                i_url = inst.get("url", "")
                i_user = inst.get("username", "")
                i_pass = inst.get("password")
                if (i_pass is None or i_pass == "") and inst.get("has_password"):
                    # Recupera password salvata
                    cur_settings = await self.get_settings()
                    match = next((x for x in cur_settings.get("instances", []) if x.get("id") == inst.get("id")), None)
                    if match:
                        i_pass = match.get("password")

                res = await self.test_single_instance(i_url, i_user, i_pass)
                results.append({
                    "name": inst.get("name") or i_url,
                    "url": i_url,
                    "success": res.get("success", False),
                    "message": res.get("message", "")
                })
                if not res.get("success"):
                    all_ok = False

            succ_count = sum(1 for r in results if r["success"])
            demo_suffix = " (Ambiente Demo Simulato)" if eero_client.is_demo_mode else ""
            return {
                "success": all_ok,
                "message": f"Test completato: {succ_count}/{len(results)} istanze raggiungibili.{demo_suffix}",
                "results": results
            }

        # Test singola istanza (fallback)
        if not url:
            cur = await self.get_settings()
            inst_list = cur.get("instances", [])
            if inst_list:
                return await self.test_connection(instances=inst_list)

        return await self.test_single_instance(url or "", username or "", password or "")

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

    async def _sync_single_target(
        self,
        target_url: str,
        auth: Optional[tuple],
        prepared_clients: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sincronizza i client verso una singola istanza AdGuard Home."""
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
                        existing_clients_by_name[name.lower()] = payload
                        for cid in ids:
                            existing_clients_by_id[str(cid).lower()] = payload
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

        # Risolvi elenco target istanze
        target_instances = []
        if instances:
            target_instances = [inst for inst in instances if inst.get("enabled", True) and inst.get("url")]
        else:
            cur = await self.get_settings()
            target_instances = [inst for inst in cur.get("instances", []) if inst.get("enabled", True) and inst.get("url")]
            if not target_instances and (url or cur.get("url")):
                target_instances = [{
                    "id": "inst-1",
                    "name": "DNS Primario",
                    "url": url or cur.get("url"),
                    "username": username if username is not None else cur.get("username", ""),
                    "password": password,
                    "has_password": cur.get("has_password", False),
                    "enabled": True
                }]

        if not target_instances:
            return {"success": False, "message": "Nessuna istanza AdGuard Home configurata o abilitata."}

        prepared_clients = self._prepare_clients(devices)
        if not prepared_clients:
            return {"success": False, "message": "Nessun client valido trovato da sincronizzare."}

        instance_results = []
        total_added = 0
        total_updated = 0
        total_failed = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for inst in target_instances:
            t_url = normalize_adguard_url(inst.get("url", ""))
            t_user = inst.get("username", "")
            t_pass = inst.get("password")
            if (t_pass is None or t_pass == "") and inst.get("has_password"):
                cur_settings = await self.get_settings()
                match = next((x for x in cur_settings.get("instances", []) if x.get("id") == inst.get("id")), None)
                if match:
                    t_pass = match.get("password")

            auth = (t_user.strip(), t_pass.strip()) if t_user and t_pass else None
            res = await self._sync_single_target(t_url, auth, prepared_clients)
            
            inst_status = f"{res.get('total_synced', 0)} sincronizzati ({res.get('added', 0)} agg, {res.get('updated', 0)} mod)"
            if res.get("failed", 0) > 0:
                inst_status += f", {res.get('failed')} falliti"

            inst["last_sync_status"] = inst_status
            inst["last_sync_time"] = now_iso

            total_added += res.get("added", 0)
            total_updated += res.get("updated", 0)
            total_failed += res.get("failed", 0)

            instance_results.append({
                "name": inst.get("name") or t_url,
                "url": t_url,
                "success": res.get("success", False),
                "added": res.get("added", 0),
                "updated": res.get("updated", 0),
                "failed": res.get("failed", 0),
                "message": inst_status
            })

        overall_synced = len(prepared_clients)
        summary_status = f"Completato: {overall_synced} dispositivi sincronizzati su {len(target_instances)} istanze AdGuard"
        if total_failed > 0:
            summary_status += f" ({total_failed} errori totali)"

        # Aggiorna statistiche globali su SQLite
        await db_service.set_setting("adguard_last_sync_time", now_iso)
        await db_service.set_setting("adguard_last_sync_count", str(overall_synced))
        await db_service.set_setting("adguard_last_sync_status", summary_status)

        # Salva stato aggiornato istanze se presenti
        cur_all = await self.get_settings()
        saved_insts = cur_all.get("instances", [])
        if saved_insts:
            for s_inst in saved_insts:
                matching = next((x for x in target_instances if x.get("id") == s_inst.get("id")), None)
                if matching:
                    s_inst["last_sync_status"] = matching.get("last_sync_status", "")
                    s_inst["last_sync_time"] = now_iso
            await db_service.set_setting("adguard_instances_json", json.dumps(saved_insts))

        return {
            "success": any(r["success"] for r in instance_results),
            "total_synced": overall_synced,
            "added_count": total_added,
            "updated_count": total_updated,
            "failed_count": total_failed,
            "message": summary_status,
            "results": instance_results,
            "last_sync_time": now_iso
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

