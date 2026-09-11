import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import urllib.parse
import httpx

from app.services.db import db_service
from app.services.eero_client import get_adguard_tags

logger = logging.getLogger(__name__)


def normalize_dns_url(url: str) -> str:
    """Pulisce e normalizza l'URL di un'istanza DNS rimuovendo frammenti (#), trailing slash e aggiungendo http:// se omesso."""
    if not url:
        return ""
    clean = url.strip()
    if "#" in clean:
        clean = clean.split("#")[0]
    clean = clean.rstrip("/")
    if not clean.startswith("http://") and not clean.startswith("https://"):
        clean = f"http://{clean}"
    return clean


class DNSManager:
    """
    Gestore unificato Multi-Engine DNS per eero Dashboard.
    Supporta la sincronizzazione simultanea di molteplici istanze indipendenti
    con motori differenti:
      - AdGuard Home (Clients API, basic auth, rules preservation, tagging)
      - Pi-hole (v5 Custom DNS API & v6 REST API)
      - Technitium DNS Server (Forward A/AAAA + Reverse PTR Zones)
    """

    def __init__(self):
        self._demo_settings: Dict[str, Any] = {
            "enabled": True,
            "instances": [
                {
                    "id": "inst-adguard-1",
                    "name": "AdGuard Primario",
                    "engine": "adguard",
                    "url": "http://192.168.1.50:80",
                    "username": "demo_admin",
                    "password": "demo_password",
                    "token": "",
                    "zone": "lan",
                    "has_password": True,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "Completato: 18 client sincronizzati [Simulazione Demo]",
                    "last_sync_count": 18
                },
                {
                    "id": "inst-adguard-2",
                    "name": "AdGuard Secondario",
                    "engine": "adguard",
                    "url": "http://192.168.1.51:80",
                    "username": "demo_admin",
                    "password": "demo_password",
                    "token": "",
                    "zone": "lan",
                    "has_password": True,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "Completato: 18 client sincronizzati [Simulazione Demo]",
                    "last_sync_count": 18
                },
                {
                    "id": "inst-pihole-1",
                    "name": "Pi-hole IoT & Backup",
                    "engine": "pihole",
                    "url": "http://192.168.1.52:80",
                    "username": "",
                    "password": "",
                    "token": "demo_pihole_token_123",
                    "zone": "lan",
                    "has_password": True,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "Completato: 18 record Local DNS sincronizzati [Simulazione Demo]",
                    "last_sync_count": 18
                }
            ]
        }

    # =========================================================================
    # SETTINGS PERSISTENCE & RETRIEVAL
    # =========================================================================

    async def get_settings(self) -> Dict[str, Any]:
        """Recupera la lista delle istanze DNS e lo stato di sincronizzazione globale."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            return {
                "enabled": bool(self._demo_settings.get("enabled", True)),
                "instances": [dict(inst) for inst in self._demo_settings.get("instances", [])]
            }

        all_s = await db_service.get_all_settings()
        enabled = all_s.get("dns_sync_enabled", all_s.get("adguard_sync_enabled", "false")).lower() == "true"
        instances_json = all_s.get("dns_instances", "")

        instances: List[Dict[str, Any]] = []
        if instances_json:
            try:
                instances = json.loads(instances_json)
            except Exception as e:
                logger.warning(f"Errore caricamento dns_instances da SQLite: {e}")

        # Se non ci sono istanze strutturate, controlla la configurazione legacy AdGuard
        if not instances:
            legacy_url = all_s.get("adguard_url", "")
            if legacy_url:
                legacy_user = all_s.get("adguard_username", "")
                has_pwd = bool(all_s.get("adguard_password", ""))
                instances.append({
                    "id": "inst-legacy-adguard",
                    "name": "AdGuard Home",
                    "engine": "adguard",
                    "url": legacy_url,
                    "username": legacy_user,
                    "password": "",
                    "token": "",
                    "zone": "lan",
                    "has_password": has_pwd,
                    "enabled": True,
                    "last_sync_time": all_s.get("adguard_last_sync_time", ""),
                    "last_sync_count": int(all_s.get("adguard_last_sync_count", "0") or 0),
                    "last_sync_status": all_s.get("adguard_last_sync_status", "")
                })

        # Maschera le password nella risposta
        sanitized_instances = []
        for inst in instances:
            inst_copy = dict(inst)
            inst_copy["has_password"] = bool(inst_copy.get("password") or inst_copy.get("has_password"))
            inst_copy.pop("password", None)
            sanitized_instances.append(inst_copy)

        return {
            "enabled": enabled,
            "instances": sanitized_instances
        }

    async def save_settings(self, enabled: bool, instances: List[Dict[str, Any]]) -> None:
        """Salva la lista delle istanze DNS nel database SQLite (o in memoria in Demo Mode)."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            self._demo_settings["enabled"] = enabled
            demo_existing_map = {x.get("id"): x for x in self._demo_settings.get("instances", []) if x.get("id")}
            new_demo_instances = []
            for inst in instances:
                inst_id = inst.get("id") or f"inst-{len(new_demo_instances) + 1}"
                old_demo = demo_existing_map.get(inst_id, {})
                d_copy = dict(inst)
                d_copy["id"] = inst_id
                if not d_copy.get("password") and old_demo.get("password"):
                    d_copy["password"] = old_demo["password"]
                if not d_copy.get("token") and old_demo.get("token"):
                    d_copy["token"] = old_demo["token"]
                d_copy["has_password"] = bool(d_copy.get("password") or d_copy.get("token") or old_demo.get("has_password"))
                new_demo_instances.append(d_copy)
            self._demo_settings["instances"] = new_demo_instances
            return

        # Recupera le istanze salvate per preservare le password non modificate
        all_s = await db_service.get_all_settings()
        existing_instances = []
        try:
            existing_instances = json.loads(all_s.get("dns_instances", "[]"))
        except Exception:
            pass
        existing_map = {inst.get("id"): inst for inst in existing_instances if inst.get("id")}

        processed_instances: List[Dict[str, Any]] = []
        for inst in instances:
            inst_id = inst.get("id") or f"inst-{len(processed_instances) + 1}"
            old_inst = existing_map.get(inst_id, {})

            clean_url = normalize_dns_url(inst.get("url", ""))
            pwd = inst.get("password")
            if not pwd and old_inst.get("password"):
                pwd = old_inst["password"]

            tok = inst.get("token")
            if not tok and old_inst.get("token"):
                tok = old_inst["token"]

            processed_instances.append({
                "id": inst_id,
                "name": str(inst.get("name") or "DNS Server").strip(),
                "engine": str(inst.get("engine") or "adguard").strip().lower(),
                "url": clean_url,
                "username": str(inst.get("username") or "").strip(),
                "password": pwd or "",
                "token": tok or "",
                "zone": str(inst.get("zone") if inst.get("zone") is not None else "lan").strip().lower().lstrip("."),
                "has_password": bool(pwd or tok),
                "enabled": bool(inst.get("enabled", True)),
                "last_sync_time": old_inst.get("last_sync_time", ""),
                "last_sync_status": old_inst.get("last_sync_status", ""),
                "last_sync_count": int(old_inst.get("last_sync_count", 0) or 0)
            })

        await db_service.set_setting("dns_sync_enabled", "true" if enabled else "false")
        await db_service.set_setting("dns_instances", json.dumps(processed_instances))

        # Mantieni sincronizzati i valori legacy del primo AdGuard per retrocompatibilità
        first_adguard = next((i for i in processed_instances if i["engine"] == "adguard"), None)
        if first_adguard:
            await db_service.set_setting("adguard_sync_enabled", "true" if (enabled and first_adguard["enabled"]) else "false")
            await db_service.set_setting("adguard_url", first_adguard["url"])
            await db_service.set_setting("adguard_username", first_adguard["username"])
            if first_adguard["password"]:
                await db_service.set_setting("adguard_password", first_adguard["password"])

    # =========================================================================
    # INSTANCE TESTING
    # =========================================================================

    async def test_instance(self, instance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Testa la connessione e le credenziali verso una specifica istanza DNS."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            engine = instance_data.get("engine", "adguard")
            engine_name = "AdGuard Home" if engine == "adguard" else ("Pi-hole" if engine == "pihole" else "Technitium DNS")
            return {
                "status": "success",
                "success": True,
                "status_code": 200,
                "engine": engine,
                "normalized_url": normalize_dns_url(instance_data.get("url", "")),
                "message": f"Connessione a {engine_name} riuscita! (Ambiente Demo Simulato - 18 client rilevati)",
                "existing_clients_count": 18
            }

        engine = str(instance_data.get("engine") or "adguard").strip().lower()
        url = normalize_dns_url(instance_data.get("url", ""))
        if not url:
            return {"success": False, "message": "URL mancante o non specificato."}

        # Se la password o token non sono passati, cercali nei setting salvati
        inst_id = instance_data.get("id")
        password = instance_data.get("password")
        token = instance_data.get("token")
        if (not password or not token) and inst_id:
            all_s = await db_service.get_all_settings()
            try:
                saved = json.loads(all_s.get("dns_instances", "[]"))
                target = next((x for x in saved if x.get("id") == inst_id), None)
                if target:
                    if not password:
                        password = target.get("password")
                    if not token:
                        token = target.get("token")
            except Exception:
                pass

        if engine == "adguard":
            return await self._test_adguard(url, instance_data.get("username", ""), password or "")
        elif engine == "pihole":
            return await self._test_pihole(url, token or password or "")
        elif engine == "technitium":
            return await self._test_technitium(url, token or password or "", instance_data.get("username", ""))
        else:
            return {"success": False, "message": f"Motore DNS '{engine}' non riconosciuto."}

    async def _test_adguard(self, url: str, username: str, password: str) -> Dict[str, Any]:
        auth = (username.strip(), password.strip()) if username and password else None
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                resp = await client.get(f"{url}/control/clients", auth=auth)
                if resp.status_code == 200:
                    data = resp.json() if isinstance(resp.json(), dict) else {}
                    clients = data.get("clients") or []
                    auto_clients = data.get("auto_clients") or []
                    return {
                        "success": True,
                        "status_code": 200,
                        "normalized_url": url,
                        "message": f"Connessione AdGuard Home riuscita! Trovati {len(clients)} client manuali ({len(auto_clients)} scoperti automaticamente).",
                        "existing_clients_count": len(clients)
                    }
                elif resp.status_code in (401, 403):
                    return {"success": False, "status_code": resp.status_code, "message": "Autenticazione fallita (401/403). Verifica Username e Password."}
                else:
                    return {"success": False, "status_code": resp.status_code, "message": f"AdGuard Home ha risposto con codice HTTP {resp.status_code}."}
        except httpx.ConnectError:
            return {"success": False, "message": f"Impossibile connettersi a '{url}'. Verifica IP, porta e protocollo (http/https)."}
        except httpx.TimeoutException:
            return {"success": False, "message": f"Timeout connessione verso '{url}' (oltre 8 secondi)."}
        except Exception as e:
            return {"success": False, "message": f"Errore di connessione AdGuard: {str(e)}"}

    async def _test_pihole(self, url: str, token: str) -> Dict[str, Any]:
        # Prova prima Pi-hole v6 (/api/) poi v5 (admin/api.php)
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                # 1. Pi-hole v6 REST API check
                v6_headers = {}
                clean_token = token.strip()
                if clean_token:
                    v6_headers = {"sid": clean_token}

                resp_v6 = await client.get(f"{url}/api/config/dns/hosts", headers=v6_headers)

                # Se 401/403 e token fornito, prova autenticazione come password per creare sessione (SID)
                if resp_v6.status_code in (401, 403) and clean_token:
                    try:
                        auth_res = await client.post(f"{url}/api/auth", json={"password": clean_token})
                        if auth_res.status_code == 200:
                            auth_data = auth_res.json() if isinstance(auth_res.json(), dict) else {}
                            sid = auth_data.get("session", {}).get("sid")
                            if sid:
                                v6_headers = {"sid": sid}
                                resp_v6 = await client.get(f"{url}/api/config/dns/hosts", headers=v6_headers)
                    except Exception:
                        pass

                if resp_v6.status_code == 200:
                    data = resp_v6.json() if isinstance(resp_v6.json(), dict) else {}
                    existing = []
                    if "config" in data and isinstance(data["config"], dict) and "dns" in data["config"]:
                        existing = data["config"]["dns"].get("hosts") or []
                    elif "hosts" in data and isinstance(data.get("hosts"), list):
                        existing = data.get("hosts") or []
                    return {
                        "success": True,
                        "status_code": 200,
                        "normalized_url": url,
                        "message": f"Connessione Pi-hole (v6 REST API) riuscita! Trovati {len(existing)} host configurati.",
                        "existing_clients_count": len(existing)
                    }
                elif resp_v6.status_code in (401, 403):
                    return {"success": False, "status_code": resp_v6.status_code, "message": "Autenticazione Pi-hole v6 fallita (401/403). Verifica Password o API Token."}

                # 2. Pi-hole v5 check (legacy admin/api.php)
                v5_url = f"{url}/admin/api.php?customdns&action=get&auth={clean_token}"
                resp = await client.get(v5_url)
                if resp.status_code == 200:
                    text = resp.text.strip()
                    if text and not text.startswith("[]") and "data" in resp.json() if resp.headers.get("content-type", "").startswith("application/json") else True:
                        return {
                            "success": True,
                            "status_code": 200,
                            "normalized_url": url,
                            "message": "Connessione Pi-hole (v5 API) riuscita! Record Local DNS accessibili.",
                            "existing_clients_count": 0
                        }

                return {
                    "success": True,
                    "status_code": 200,
                    "normalized_url": url,
                    "message": "Connessione a Pi-hole stabilita con successo!",
                    "existing_clients_count": 0
                }
        except httpx.ConnectError:
            return {"success": False, "message": f"Impossibile raggiungere Pi-hole su '{url}'."}
        except httpx.TimeoutException:
            return {"success": False, "message": f"Timeout connessione Pi-hole verso '{url}'."}
        except Exception as e:
            return {"success": False, "message": f"Errore di connessione Pi-hole: {str(e)}"}

    async def _test_technitium(self, url: str, token_or_pass: str, username: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                # Prova prima con il token diretto se presente
                token = token_or_pass.strip()
                if username and token_or_pass and not token.isalnum():
                    # Prova login di sessione
                    login_resp = await client.post(f"{url}/api/user/login", params={"user": username.strip(), "pass": token_or_pass.strip()})
                    if login_resp.status_code == 200 and login_resp.json().get("status") == "ok":
                        token = login_resp.json().get("token", "")

                resp = await client.get(f"{url}/api/zones/list", params={"token": token} if token else {})
                if resp.status_code == 200:
                    data = resp.json() if isinstance(resp.json(), dict) else {}
                    if data.get("status") == "ok":
                        zones = data.get("response", {}).get("zones", [])
                        return {
                            "success": True,
                            "status_code": 200,
                            "normalized_url": url,
                            "message": f"Connessione Technitium DNS riuscita! Trovate {len(zones)} zone configurate.",
                            "existing_clients_count": len(zones)
                        }
                    else:
                        err = data.get("errorMessage", "Errore API Technitium")
                        return {"success": False, "message": f"Technitium DNS: {err}"}
                elif resp.status_code in (401, 403):
                    return {"success": False, "message": "Autenticazione Technitium DNS fallita (Token o Credenziali non valide)."}
                return {"success": False, "message": f"Technitium DNS ha risposto con codice HTTP {resp.status_code}."}
        except httpx.ConnectError:
            return {"success": False, "message": f"Impossibile raggiungere Technitium DNS su '{url}'."}
        except Exception as e:
            return {"success": False, "message": f"Errore connessione Technitium DNS: {str(e)}"}

    async def test_all_instances(self) -> Dict[str, Any]:
        """Testa contemporaneamente tutte le istanze DNS configurate."""
        settings = await self.get_settings()
        instances = settings.get("instances", [])
        if not instances:
            return {"success": False, "message": "Nessuna istanza DNS configurata da testare.", "results": []}

        results = []
        all_ok = True
        for inst in instances:
            if not inst.get("enabled", True):
                continue
            res = await self.test_instance(inst)
            results.append({
                "id": inst.get("id"),
                "name": inst.get("name"),
                "engine": inst.get("engine"),
                **res
            })
            if not res.get("success"):
                all_ok = False

        return {
            "status": "success" if all_ok else "error",
            "success": all_ok,
            "total_tested": len(results),
            "results": results
        }

    # =========================================================================
    # MULTI-INSTANCE CLIENT SYNCHRONIZATION
    # =========================================================================

    def _prepare_clients_payload(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Estrae e normalizza IP, MAC, hostname e tag per ciascun apparato eero."""
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
        prepared: List[Dict[str, Any]] = []

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
                    if not v6_clean.endswith("::1") and ip_counts.get(v6_clean.lower(), 0) == 1:
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

            prepared.append({
                "name": unique_name,
                "hostname": base_name.lower().replace(" ", "-").replace("_", "-"),
                "ip": ip if (ip and "." in ip and not ip.startswith("169.254.")) else None,
                "mac": mac.upper() if mac else None,
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

        return prepared

    def _merge_adguard_client_data(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """Preserva al 100% tutte le regole personalizzate, filtri, upstreams e blacklist di AdGuard Home (Issue #21)."""
        merged = dict(existing)
        merged["name"] = incoming.get("name") or existing.get("name")

        existing_ids = [str(x).strip() for x in (existing.get("ids") or []) if str(x).strip()]
        incoming_ids = [str(x).strip() for x in (incoming.get("ids") or []) if str(x).strip()]
        merged_ids = list(existing_ids)
        existing_ids_lower = {x.lower() for x in existing_ids}
        for i_id in incoming_ids:
            if i_id.lower() not in existing_ids_lower:
                merged_ids.append(i_id)
                existing_ids_lower.add(i_id.lower())
        merged["ids"] = merged_ids

        if not existing.get("tags") and incoming.get("tags"):
            merged["tags"] = incoming["tags"]

        return merged

    async def _sync_single_adguard(self, inst: Dict[str, Any], prepared_clients: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = normalize_dns_url(inst.get("url", ""))
        username = inst.get("username", "")
        password = inst.get("password", "")
        auth = (username.strip(), password.strip()) if username and password else None

        existing_by_name: Dict[str, Dict[str, Any]] = {}
        existing_by_id: Dict[str, Dict[str, Any]] = {}

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                resp = await client.get(f"{url}/control/clients", auth=auth)
                if resp.status_code == 200:
                    resp_data = resp.json() if isinstance(resp.json(), dict) else {}
                    for c in (resp_data.get("clients") or []):
                        if isinstance(c, dict):
                            if c.get("name"):
                                existing_by_name[c["name"].lower()] = c
                            for cid in (c.get("ids") or []):
                                if cid:
                                    existing_by_id[str(cid).strip().lower()] = c
                elif resp.status_code in (401, 403):
                    return {"success": False, "message": f"Autenticazione fallita su AdGuard ({url})."}

                added = 0
                updated = 0
                failed = 0
                for payload in prepared_clients:
                    name = payload["name"]
                    ids = payload["ids"]

                    existing_client = existing_by_name.get(name.lower())
                    if not existing_client:
                        for cid in ids:
                            found = existing_by_id.get(cid.lower())
                            if found:
                                existing_client = found
                                break

                    if existing_client:
                        merged = self._merge_adguard_client_data(existing_client, payload)
                        update_payload = {"name": existing_client.get("name", name), "data": merged}
                        res = await client.post(f"{url}/control/clients/update", auth=auth, json=update_payload)
                        if res.status_code == 200:
                            updated += 1
                        else:
                            failed += 1
                    else:
                        res = await client.post(f"{url}/control/clients/add", auth=auth, json=payload)
                        if res.status_code == 200:
                            added += 1
                        else:
                            failed += 1

                return {
                    "success": failed == 0,
                    "added": added,
                    "updated": updated,
                    "failed": failed,
                    "message": f"AdGuard: {added} aggiunti, {updated} aggiornati, {failed} falliti."
                }
        except Exception as e:
            return {"success": False, "message": f"Errore durante la sincronizzazione AdGuard: {str(e)}"}

    async def _sync_single_pihole(self, inst: Dict[str, Any], prepared_clients: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = normalize_dns_url(inst.get("url", ""))
        token = (inst.get("token") or inst.get("password") or "").strip()
        raw_zone = str(inst.get("zone") if inst.get("zone") is not None else "").strip().lstrip(".")

        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
                # -------------------------------------------------------------
                # 1. RILEVAZIONE PI-HOLE v6 REST API (/api/config/dns/hosts)
                # -------------------------------------------------------------
                v6_headers = {}
                if token:
                    v6_headers = {"sid": token}

                is_v6 = False
                resp_v6 = await client.get(f"{url}/api/config/dns/hosts", headers=v6_headers)
                if resp_v6.status_code == 200:
                    is_v6 = True
                elif resp_v6.status_code in (401, 403) and token:
                    try:
                        auth_res = await client.post(f"{url}/api/auth", json={"password": token})
                        if auth_res.status_code == 200:
                            auth_data = auth_res.json() if isinstance(auth_res.json(), dict) else {}
                            sid = auth_data.get("session", {}).get("sid")
                            if sid:
                                v6_headers = {"sid": sid}
                                recheck = await client.get(f"{url}/api/config/dns/hosts", headers=v6_headers)
                                if recheck.status_code == 200:
                                    is_v6 = True
                                    resp_v6 = recheck
                    except Exception:
                        pass

                # -------------------------------------------------------------
                # 2. ESECUZIONE SINCRONIZZAZIONE PI-HOLE v6 REST API
                # -------------------------------------------------------------
                if is_v6:
                    data = resp_v6.json() if isinstance(resp_v6.json(), dict) else {}
                    existing_hosts: List[str] = []
                    if "config" in data and isinstance(data["config"], dict) and "dns" in data["config"]:
                        existing_hosts = data["config"]["dns"].get("hosts") or []
                    elif "hosts" in data and isinstance(data.get("hosts"), list):
                        existing_hosts = data.get("hosts") or []

                    # Mappatura host esistenti: IP -> hostname
                    host_map: Dict[str, str] = {}
                    for entry in existing_hosts:
                        if isinstance(entry, str) and " " in entry.strip():
                            parts = entry.strip().split(None, 1)
                            if len(parts) == 2:
                                host_map[parts[0].lower()] = parts[1].strip()

                    synced = 0
                    for client_item in prepared_clients:
                        ip = client_item.get("ip")
                        hostname = client_item.get("hostname")
                        if not ip or not hostname:
                            continue
                        target_name = f"{hostname}.{raw_zone}" if raw_zone else hostname
                        host_map[ip.lower().strip()] = target_name
                        synced += 1

                    new_hosts_list = [f"{ip_addr} {h_name}" for ip_addr, h_name in host_map.items()]

                    # Tenta prima PATCH atomica (un'unica richiesta veloce senza restart multipli)
                    patch_payload = {
                        "config": {
                            "dns": {
                                "hosts": new_hosts_list
                            }
                        }
                    }
                    patch_res = await client.patch(f"{url}/api/config", json=patch_payload, headers=v6_headers)
                    zone_label = f" in zona .{raw_zone}" if raw_zone else " (hostname diretti)"

                    if patch_res.status_code in (200, 204):
                        return {
                            "success": True,
                            "added": synced,
                            "updated": 0,
                            "failed": 0,
                            "message": f"Pi-hole v6: {synced} record DNS sincronizzati con successo{zone_label}."
                        }

                    # Fallback Pi-hole v6: PUT record per record su /api/config/dns/hosts/{value}
                    put_synced = 0
                    put_failed = 0
                    for client_item in prepared_clients:
                        ip = client_item.get("ip")
                        hostname = client_item.get("hostname")
                        if not ip or not hostname:
                            continue
                        target_name = f"{hostname}.{raw_zone}" if raw_zone else hostname
                        val_quoted = urllib.parse.quote(f"{ip} {target_name}")
                        put_res = await client.put(f"{url}/api/config/dns/hosts/{val_quoted}", headers=v6_headers)
                        if put_res.status_code in (200, 201, 204) or (put_res.status_code == 400 and "already present" in put_res.text.lower()):
                            put_synced += 1
                        else:
                            put_failed += 1

                    return {
                        "success": put_failed == 0,
                        "added": put_synced,
                        "updated": 0,
                        "failed": put_failed,
                        "message": f"Pi-hole v6: {put_synced} record sincronizzati{zone_label} ({put_failed} falliti)."
                    }

                # -------------------------------------------------------------
                # 3. ESECUZIONE SINCRONIZZAZIONE PI-HOLE v5 (LEGACY admin/api.php)
                # -------------------------------------------------------------
                synced = 0
                failed = 0
                for client_item in prepared_clients:
                    ip = client_item.get("ip")
                    hostname = client_item.get("hostname")
                    if not ip or not hostname:
                        continue
                    target_name = f"{hostname}.{raw_zone}" if raw_zone else hostname

                    v5_url = f"{url}/admin/api.php?customdns&action=add&ip={ip}&domain={target_name}&auth={token}"
                    res = await client.get(v5_url)
                    if res.status_code == 200:
                        synced += 1
                    else:
                        failed += 1

                zone_label = f" in zona .{raw_zone}" if raw_zone else " (hostname diretti)"
                return {
                    "success": failed == 0,
                    "added": synced,
                    "updated": 0,
                    "failed": failed,
                    "message": f"Pi-hole v5: {synced} record DNS sincronizzati{zone_label} ({failed} falliti)."
                }
        except Exception as e:
            return {"success": False, "message": f"Errore durante sincronizzazione Pi-hole: {str(e)}"}

    async def _sync_single_technitium(self, inst: Dict[str, Any], prepared_clients: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = normalize_dns_url(inst.get("url", ""))
        token = inst.get("token") or inst.get("password") or ""
        zone = inst.get("zone", "lan").lstrip(".")

        synced = 0
        failed = 0
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                for client_item in prepared_clients:
                    ip = client_item.get("ip")
                    hostname = client_item.get("hostname")
                    if not ip or not hostname:
                        continue
                    fqdn = f"{hostname}.{zone}"

                    params = {
                        "token": token.strip(),
                        "domain": fqdn,
                        "zone": zone,
                        "type": "A",
                        "ipAddress": ip,
                        "ptr": "true",
                        "overwrite": "true"
                    }
                    res = await client.post(f"{url}/api/zones/records/add", params=params)
                    if res.status_code == 200 and res.json().get("status") == "ok":
                        synced += 1
                    else:
                        failed += 1

                return {
                    "success": failed == 0,
                    "added": synced,
                    "updated": 0,
                    "failed": failed,
                    "message": f"Technitium: {synced} record A + PTR sincronizzati nella zona {zone}."
                }
        except Exception as e:
            return {"success": False, "message": f"Errore durante sincronizzazione Technitium DNS: {str(e)}"}

    async def sync_devices(
        self,
        devices: List[Dict[str, Any]],
        instance_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sincronizza l'elenco dei dispositivi verso tutte le istanze DNS abilitate,
        oppure verso una specifica istanza se `instance_id` è indicato.
        """
        from app.services.eero_client import eero_client
        prepared_clients = self._prepare_clients_payload(devices)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Simulazione istantanea e sicura in Demo Mode
        if eero_client.is_demo_mode:
            simulated_results = []
            for inst in self._demo_settings.get("instances", []):
                if instance_id and inst.get("id") != instance_id:
                    continue
                inst["last_sync_time"] = now_iso
                inst["last_sync_count"] = len(prepared_clients) or 18
                inst["last_sync_status"] = f"Completato: {inst['last_sync_count']} client sincronizzati [Simulazione Demo]"
                simulated_results.append({
                    "id": inst.get("id"),
                    "name": inst.get("name"),
                    "engine": inst.get("engine"),
                    "success": True,
                    "synced_count": inst["last_sync_count"],
                    "message": inst["last_sync_status"]
                })
            count = len(prepared_clients) or 18
            return {
                "status": "success",
                "success": True,
                "synced_instances": len(simulated_results),
                "total_devices": count,
                "total_synced": count,
                "results": simulated_results,
                "message": f"Sincronizzazione completata con successo su {len(simulated_results)} istanze DNS [Demo]."
            }

        # Carica le istanze da SQLite
        all_s = await db_service.get_all_settings()
        instances: List[Dict[str, Any]] = []
        try:
            instances = json.loads(all_s.get("dns_instances", "[]"))
        except Exception:
            pass

        # Fallback adguard legacy se non ci sono istanze
        if not instances and all_s.get("adguard_url"):
            instances.append({
                "id": "inst-legacy-adguard",
                "name": "AdGuard Home",
                "engine": "adguard",
                "url": all_s.get("adguard_url"),
                "username": all_s.get("adguard_username", ""),
                "password": all_s.get("adguard_password", ""),
                "enabled": True
            })

        if not instances:
            return {"success": False, "message": "Nessuna istanza DNS configurata.", "results": []}

        results = []
        all_success = True

        for inst in instances:
            inst_id = inst.get("id")
            if instance_id and inst_id != instance_id:
                continue
            if not inst.get("enabled", True) and not instance_id:
                continue

            engine = inst.get("engine", "adguard").lower()
            if engine == "adguard":
                res = await self._sync_single_adguard(inst, prepared_clients)
            elif engine == "pihole":
                res = await self._sync_single_pihole(inst, prepared_clients)
            elif engine == "technitium":
                res = await self._sync_single_technitium(inst, prepared_clients)
            else:
                res = {"success": False, "message": f"Motore sconosciuto '{engine}'"}

            status_msg = res.get("message", "Sync completato")
            inst["last_sync_time"] = now_iso
            inst["last_sync_status"] = status_msg
            inst["last_sync_count"] = (res.get("added", 0) + res.get("updated", 0))

            results.append({
                "id": inst_id,
                "name": inst.get("name"),
                "engine": engine,
                **res
            })
            if not res.get("success"):
                all_success = False

        # Salva lo stato di sincronizzazione aggiornato nelle istanze
        await db_service.set_setting("dns_instances", json.dumps(instances))

        # Se presente un'istanza AdGuard, aggiorna anche le chiavi legacy
        first_adg = next((i for i in instances if i.get("engine") == "adguard"), None)
        if first_adg:
            await db_service.set_setting("adguard_last_sync_time", now_iso)
            await db_service.set_setting("adguard_last_sync_count", str(first_adg.get("last_sync_count", 0)))
            await db_service.set_setting("adguard_last_sync_status", first_adg.get("last_sync_status", ""))

        return {
            "status": "success" if all_success else "error",
            "success": all_success,
            "synced_instances": len(results),
            "total_devices": len(prepared_clients),
            "total_synced": len(prepared_clients),
            "results": results,
            "message": f"Sincronizzazione completata su {len(results)} istanze DNS."
        }

    async def auto_sync_if_enabled(self, devices: List[Dict[str, Any]]) -> None:
        """Esegue la sincronizzazione background se il toggle globale è attivo."""
        settings = await self.get_settings()
        if not settings.get("enabled"):
            return
        try:
            logger.info("Avvio sincronizzazione automatica Multi-DNS background...")
            res = await self.sync_devices(devices)
            logger.info(f"Esito sync Multi-DNS: {res.get('message')}")
        except Exception as e:
            logger.error(f"Errore durante l'auto-sync Multi-DNS: {e}")


# Istanza singleton esportata
dns_manager = DNSManager()
dns_service = dns_manager
