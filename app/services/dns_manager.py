import asyncio
import ipaddress
import json
import logging
import re
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import urllib.parse
import httpx

from app.services.db import db_service
from app.services.eero_client import get_adguard_tags
from app.i18n import log_event, tr

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


def is_safe_dns_url(url: str) -> Tuple[bool, str]:
    """
    Verifica che l'URL dell'istanza DNS sia sicuro e non punti a indirizzi riservati o cloud metadata (anti-SSRF).
    Blocca tassativamente:
      - 169.254.0.0/16 (IPv4 link-local / Cloud Instance Metadata Services come AWS/GCP/Azure)
      - fe80::/10 (IPv6 link-local)
      - Host cloud metadata riservati
    """
    if not url:
        return False, "URL vuoto o non specificato"
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            return False, "Hostname mancante o non valido"

        # Controlla se hostname è un indirizzo IP numerico
        try:
            ip_obj = ipaddress.ip_address(hostname.strip("[]"))
            if ip_obj.is_link_local:
                return False, f"Indirizzo link-local / metadata riservato non consentito ({ip_obj})"
            if ip_obj.is_multicast:
                return False, f"Indirizzo multicast non consentito ({ip_obj})"
            if ip_obj.is_unspecified:
                return False, f"Indirizzo non specificato non consentito ({ip_obj})"
        except ValueError:
            # È un hostname/dominio
            lower_host = hostname.lower()
            if lower_host in ("metadata.google.internal", "instance-data", "metadata"):
                return False, f"Host cloud metadata riservato non consentito ({hostname})"

        return True, ""
    except Exception as e:
        return False, f"URL non analizzabile: {e}"


def sanitize_dns_hostname(name: str, fallback: str = "device") -> str:
    """Sanitizza un nome apparato in un hostname RFC 1123 valido per DNS (lettere a-z, numeri, trattini).

    Rimuove parentesi, caratteri speciali, spazi e simboli che causano il fallimento di Pi-hole v6
    e Technitium, garantendo che le etichette DNS non inizino né finiscano con trattini.
    """
    clean = (name or "").lower().strip()
    clean = clean.replace(" ", "-").replace("_", "-")
    clean = re.sub(r"[^a-z0-9-]", "", clean)
    clean = re.sub(r"-+", "-", clean).strip("-")
    clean = clean[:63].rstrip("-")
    if not clean:
        fb_clean = re.sub(r"[^a-z0-9-]", "", fallback.lower().replace(" ", "-").replace("_", "-")).strip("-")
        clean = fb_clean[:63].rstrip("-") or "device"
    return clean


def _same_registered_instance(saved: Dict[str, Any], engine: str, normalized_url: str, username: str) -> bool:
    """True solo se la richiesta di test punta ESATTAMENTE all'istanza già registrata.

    Serve a non riutilizzare mai un segreto salvato (password AdGuard, token Pi-hole/Technitium)
    quando l'URL, il motore o l'account della richiesta differiscono da quelli memorizzati: così chi
    chiama non può far recapitare il segreto a una destinazione che ha scelto lui.
    """
    if normalize_dns_url(saved.get("url", "")) != normalized_url:
        return False
    if str(saved.get("engine") or "adguard").strip().lower() != engine:
        return False
    # AdGuard invia l'username nella Basic auth: un username diverso non deve riutilizzare la password salvata
    if engine == "adguard" and str(saved.get("username") or "").strip() != str(username or "").strip():
        return False
    return True


def parse_insecure_tls(value: Any) -> bool:
    """Interpreta in modo rigoroso l'opzione 'insecure_tls' di un'istanza DNS.

    Solo True (o le stringhe "true"/"1"/"yes"/"on") disattiva la verifica del certificato TLS:
    una stringa come "false" o "0" resta False (bool("false") sarebbe True), None e valori ignoti pure.
    """
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def apply_legacy_tls_default(inst: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibilità per le istanze salvate prima dell'opzione 'insecure_tls'.

    Fino alla v1.6.0 ogni istanza veniva contattata con verify=False. Un'istanza salvata senza
    l'opzione e con URL https:// mantiene quindi la verifica disattivata, così un server con certificato
    autofirmato continua a funzionare: l'opzione risulta spuntata nell'interfaccia e l'utente può toglierla.
    Le istanze http:// non cambiano (nessun TLS); quelle con l'opzione esplicita vengono solo normalizzate.
    """
    if inst.get("insecure_tls") is None:
        inst["insecure_tls"] = normalize_dns_url(inst.get("url", "")).lower().startswith("https://")
    else:
        inst["insecure_tls"] = parse_insecure_tls(inst["insecure_tls"])
    return inst


def _is_tls_verification_error(exc: Optional[BaseException]) -> bool:
    """True se l'errore (o una delle sue cause) è un certificato TLS non verificabile."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, ssl.SSLCertVerificationError):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return False


def _tls_error_result(url: str, exc: Optional[BaseException] = None, engine: Optional[str] = None) -> Dict[str, Any]:
    reason = None
    curr = exc
    seen = set()
    while curr is not None and id(curr) not in seen:
        if isinstance(curr, ssl.SSLCertVerificationError):
            reason = str(curr)
            break
        seen.add(id(curr))
        curr = curr.__cause__ or curr.__context__

    if not reason and exc:
        reason = str(exc)

    engine_label = f"[{engine}] " if engine else ""
    log_detail = f": {reason}" if reason else ""
    logger.warning(f"TLS certificate verification failed for {engine_label}{url}{log_detail}")

    return {
        "success": False,
        "tls_error": True,
        "message": tr("dns.tls_unverified", url=url),
    }


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
                    "insecure_tls": False,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "",
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
                    "insecure_tls": False,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "",
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
                    "insecure_tls": False,
                    "enabled": True,
                    "last_sync_time": "2026-08-29T10:00:00Z",
                    "last_sync_status": "",
                    "last_sync_count": 18
                }
            ]
        }
        # Stato di sync delle istanze demo come (chiave catalogo, parametri): tradotto a ogni lettura nella lingua della richiesta
        self._demo_status_keys: Dict[str, Tuple[str, Dict[str, Any]]] = {
            "inst-adguard-1": ("dns.demo_status_clients", {"count": 18}),
            "inst-adguard-2": ("dns.demo_status_clients", {"count": 18}),
            "inst-pihole-1": ("dns.demo_status_records", {"count": 18}),
        }

    def _demo_instances_view(self) -> List[Dict[str, Any]]:
        instances = []
        for inst in self._demo_settings.get("instances", []):
            inst_copy = dict(inst)
            status = self._demo_status_keys.get(inst_copy.get("id"))
            if status:
                inst_copy["last_sync_status"] = tr(status[0], **status[1])
            instances.append(inst_copy)
        return instances

    # =========================================================================
    # SETTINGS PERSISTENCE & RETRIEVAL
    # =========================================================================

    async def get_settings(self) -> Dict[str, Any]:
        """Recupera la lista delle istanze DNS e lo stato di sincronizzazione globale."""
        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            return {
                "enabled": bool(self._demo_settings.get("enabled", True)),
                "instances": self._demo_instances_view()
            }

        all_s = await db_service.get_all_settings()
        enabled = all_s.get("dns_sync_enabled", all_s.get("adguard_sync_enabled", "false")).lower() == "true"
        instances_json = all_s.get("dns_instances", "")

        instances: List[Dict[str, Any]] = []
        if instances_json:
            try:
                instances = json.loads(instances_json)
            except Exception as e:
                logger.warning(f"Failed to load dns_instances from SQLite: {e}")

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
                    "insecure_tls": all_s.get("adguard_insecure_tls"),
                    "enabled": True,
                    "last_sync_time": all_s.get("adguard_last_sync_time", ""),
                    "last_sync_count": int(all_s.get("adguard_last_sync_count", "0") or 0),
                    "last_sync_status": all_s.get("adguard_last_sync_status", "")
                })

        # Maschera i segreti nella risposta (espone solo has_password/has_token) e rende esplicita l'opzione TLS (vedi apply_legacy_tls_default)
        sanitized_instances = []
        for inst in instances:
            inst_copy = apply_legacy_tls_default(dict(inst))
            inst_copy["has_password"] = bool(inst_copy.get("password") or inst_copy.get("has_password"))
            inst_copy["has_token"] = bool(inst_copy.get("token"))
            inst_copy.pop("password", None)
            inst_copy.pop("token", None)
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
                insecure = d_copy.get("insecure_tls")
                if insecure is None:
                    same_demo = bool(inst.get("id")) and normalize_dns_url(old_demo.get("url", "")) == normalize_dns_url(d_copy.get("url", ""))
                    insecure = old_demo.get("insecure_tls", False) if same_demo else False
                d_copy["insecure_tls"] = parse_insecure_tls(insecure)
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
        existing_map = {inst.get("id"): apply_legacy_tls_default(inst) for inst in existing_instances if inst.get("id")}
        if not existing_instances and all_s.get("adguard_url"):
            # Configurazione legacy a istanza singola (vedi get_settings): conserva la sua opzione TLS al primo salvataggio
            existing_map["inst-legacy-adguard"] = apply_legacy_tls_default({
                "url": all_s.get("adguard_url", ""),
                "insecure_tls": all_s.get("adguard_insecure_tls"),
            })

        processed_instances: List[Dict[str, Any]] = []
        for inst in instances:
            inst_id = inst.get("id") or f"inst-{len(processed_instances) + 1}"
            old_inst = existing_map.get(inst_id, {})

            clean_url = normalize_dns_url(inst.get("url", ""))
            # Il segreto salvato si conserva solo se l'istanza punta ancora allo stesso server (URL, motore, account):
            # cambiare l'URL senza ridigitare password/token non deve portare il segreto verso il nuovo indirizzo.
            keep_secret = bool(old_inst) and _same_registered_instance(
                old_inst, str(inst.get("engine") or "adguard").strip().lower(), clean_url, inst.get("username", ""))
            pwd = inst.get("password")
            if not pwd and keep_secret and old_inst.get("password"):
                pwd = old_inst["password"]

            tok = inst.get("token")
            if not tok and keep_secret and old_inst.get("token"):
                tok = old_inst["token"]

            # Opzione TLS: valore esplicito della richiesta, altrimenti quello già salvato per lo stesso id fornito
            # e lo stesso server (istanza nuova, senza id o con un altro URL: verifica attiva)
            insecure = inst.get("insecure_tls")
            if insecure is None:
                same_instance = bool(inst.get("id")) and normalize_dns_url(old_inst.get("url", "")) == clean_url
                insecure = old_inst.get("insecure_tls", False) if same_instance else False

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
                "insecure_tls": parse_insecure_tls(insecure),
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
            # Copia legacy della password: azzerata se l'URL cambia senza nuova password (stessa regola delle istanze)
            if first_adguard["password"] or normalize_dns_url(all_s.get("adguard_url", "")) != first_adguard["url"]:
                await db_service.set_setting("adguard_password", first_adguard["password"])
            await db_service.set_setting("adguard_url", first_adguard["url"])
            await db_service.set_setting("adguard_username", first_adguard["username"])
            await db_service.set_setting("adguard_insecure_tls", "true" if first_adguard["insecure_tls"] else "false")

    # =========================================================================
    # INSTANCE TESTING
    # =========================================================================

    async def test_instance(self, instance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Testa la connessione e le credenziali verso una specifica istanza DNS."""
        url = normalize_dns_url(instance_data.get("url", ""))
        if not url:
            return {"success": False, "message": tr("dns.url_missing")}

        is_safe, error_reason = is_safe_dns_url(url)
        if not is_safe:
            return {"success": False, "message": f"URL non consentito (Anti-SSRF): {error_reason}"}

        from app.services.eero_client import eero_client
        if eero_client.is_demo_mode:
            engine = instance_data.get("engine", "adguard")
            engine_name = "AdGuard Home" if engine == "adguard" else ("Pi-hole" if engine == "pihole" else "Technitium DNS")
            return {
                "status": "success",
                "success": True,
                "status_code": 200,
                "engine": engine,
                "normalized_url": url,
                "message": tr("dns.demo_test_success", engine=engine_name, count=18),
                "existing_clients_count": 18
            }

        engine = str(instance_data.get("engine") or "adguard").strip().lower()

        # Se la password o il token non sono passati, cercali nei setting salvati, ma SOLO se la richiesta
        # punta alla stessa istanza registrata (stesso id, URL, motore e account): un URL o un account
        # diversi non devono mai riutilizzare il segreto salvato e recapitarlo a una destinazione scelta da chi chiama.
        inst_id = instance_data.get("id")
        password = instance_data.get("password")
        token = instance_data.get("token")
        if (not password or not token) and inst_id:
            all_s = await db_service.get_all_settings()
            try:
                saved = json.loads(all_s.get("dns_instances", "[]"))
                target = next((x for x in saved if x.get("id") == inst_id), None)
                if target and _same_registered_instance(target, engine, url, instance_data.get("username", "")):
                    if not password:
                        password = target.get("password")
                    if not token:
                        token = target.get("token")
            except Exception:
                pass

        # Opzione TLS non passata: quella dell'istanza salvata con lo stesso id e lo stesso server
        # (configurazione legacy inclusa), altrimenti verifica attiva
        insecure = instance_data.get("insecure_tls")
        if insecure is None and inst_id:
            saved_instances = (await self.get_settings()).get("instances", [])
            saved_target = next((x for x in saved_instances if x.get("id") == inst_id), None)
            if saved_target and normalize_dns_url(saved_target.get("url", "")) == url:
                insecure = saved_target.get("insecure_tls")
        insecure_tls = parse_insecure_tls(insecure)

        if engine == "adguard":
            return await self._test_adguard(url, instance_data.get("username", ""), password or "", insecure_tls=insecure_tls)
        elif engine == "pihole":
            return await self._test_pihole(url, token or password or "", insecure_tls=insecure_tls)
        elif engine == "technitium":
            return await self._test_technitium(url, token or password or "", instance_data.get("username", ""), insecure_tls=insecure_tls)
        else:
            return {"success": False, "message": tr("dns.unknown_engine", engine=engine)}

    async def _test_adguard(self, url: str, username: str, password: str, insecure_tls: bool = False) -> Dict[str, Any]:
        auth = (username.strip(), password.strip()) if username and password else None
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=not insecure_tls, follow_redirects=True) as client:
                resp = await client.get(f"{url}/control/clients", auth=auth)
                if resp.status_code == 200:
                    data = resp.json() if isinstance(resp.json(), dict) else {}
                    clients = data.get("clients") or []
                    auto_clients = data.get("auto_clients") or []
                    return {
                        "success": True,
                        "status_code": 200,
                        "normalized_url": url,
                        "message": tr("dns.adguard_test_success", clients=len(clients), auto_clients=len(auto_clients)),
                        "existing_clients_count": len(clients)
                    }
                elif resp.status_code in (401, 403):
                    return {"success": False, "status_code": resp.status_code, "message": tr("dns.adguard_auth_failed")}
                else:
                    return {"success": False, "status_code": resp.status_code, "message": tr("dns.adguard_http_error", code=resp.status_code)}
        except httpx.ConnectError as e:
            if _is_tls_verification_error(e):
                return _tls_error_result(url, exc=e, engine="AdGuard")
            return {"success": False, "message": tr("dns.adguard_connect_failed", url=url)}
        except httpx.TimeoutException:
            return {"success": False, "message": tr("dns.adguard_timeout", url=url)}
        except Exception as e:
            return {"success": False, "message": tr("dns.adguard_connection_error", error=str(e))}

    async def _test_pihole(self, url: str, token: str, insecure_tls: bool = False) -> Dict[str, Any]:
        # Prova prima Pi-hole v6 (/api/) poi v5 (admin/api.php)
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=not insecure_tls, follow_redirects=True) as client:
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
                    except Exception as e:
                        if _is_tls_verification_error(e):
                            raise

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
                        "message": tr("dns.pihole_v6_success", count=len(existing)),
                        "existing_clients_count": len(existing)
                    }
                elif resp_v6.status_code in (401, 403):
                    return {"success": False, "status_code": resp_v6.status_code, "message": tr("dns.pihole_v6_auth_failed")}

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
                            "message": tr("dns.pihole_v5_success"),
                            "existing_clients_count": 0
                        }

                return {
                    "success": True,
                    "status_code": 200,
                    "normalized_url": url,
                    "message": tr("dns.pihole_connected"),
                    "existing_clients_count": 0
                }
        except httpx.ConnectError as e:
            if _is_tls_verification_error(e):
                return _tls_error_result(url, exc=e, engine="Pi-hole")
            return {"success": False, "message": tr("dns.pihole_unreachable", url=url)}
        except httpx.TimeoutException:
            return {"success": False, "message": tr("dns.pihole_timeout", url=url)}
        except Exception as e:
            return {"success": False, "message": tr("dns.pihole_connection_error", error=str(e))}

    async def _test_technitium(self, url: str, token_or_pass: str, username: str, insecure_tls: bool = False) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=not insecure_tls, follow_redirects=True) as client:
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
                            "message": tr("dns.technitium_success", count=len(zones)),
                            "existing_clients_count": len(zones)
                        }
                    else:
                        err = data.get("errorMessage") or tr("dns.technitium_api_error")
                        return {"success": False, "message": f"Technitium DNS: {err}"}
                elif resp.status_code in (401, 403):
                    return {"success": False, "message": tr("dns.technitium_auth_failed")}
                return {"success": False, "message": tr("dns.technitium_http_error", code=resp.status_code)}
        except httpx.ConnectError as e:
            if _is_tls_verification_error(e):
                return _tls_error_result(url, exc=e, engine="Technitium")
            return {"success": False, "message": tr("dns.technitium_unreachable", url=url)}
        except Exception as e:
            return {"success": False, "message": tr("dns.technitium_connection_error", error=str(e))}

    async def test_all_instances(self) -> Dict[str, Any]:
        """Testa contemporaneamente tutte le istanze DNS configurate."""
        settings = await self.get_settings()
        instances = settings.get("instances", [])
        if not instances:
            return {"success": False, "message": tr("dns.no_instances_to_test"), "results": []}

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

    def _prepare_clients_payload(self, devices: List[Dict[str, Any]], drop_ipv6: bool = False) -> List[Dict[str, Any]]:
        """Estrae e normalizza IP, MAC, hostname e tag per ciascun apparato eero, con filtro IPv6 opzionale."""
        ip_counts: Dict[str, int] = {}
        for dev in devices:
            if dev.get("dns_sync_excluded"):
                continue
            raw_ips = []
            if dev.get("ip"):
                raw_ips.append(str(dev["ip"]).strip())
            if not drop_ipv6:
                for v6 in (dev.get("ipv6_addresses") or []):
                    if isinstance(v6, str):
                        raw_ips.append(v6.strip())
            for single_ip in set(raw_ips):
                if single_ip:
                    ip_counts[single_ip.lower()] = ip_counts.get(single_ip.lower(), 0) + 1

        used_names: Dict[str, int] = {}
        prepared: List[Dict[str, Any]] = []

        for dev in devices:
            if dev.get("dns_sync_excluded"):
                continue
            ip = dev.get("ip")
            mac = dev.get("mac")
            if not ip and not mac:
                continue

            ids: List[str] = []
            if ip and isinstance(ip, str) and "." in ip and not ip.startswith("169.254."):
                ip_clean = ip.strip()
                if ip_counts.get(ip_clean.lower(), 0) == 1:
                    ids.append(ip_clean)

            if not drop_ipv6:
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

            mac_suffix = mac[-5:].replace(":", "").lower() if mac else "node"
            ip_suffix = ip.split(".")[-1] if (ip and "." in ip) else mac_suffix
            fallback_host = f"eero-{ip_suffix}"
            clean_host = sanitize_dns_hostname(base_name, fallback=fallback_host)

            prepared.append({
                "name": unique_name,
                "hostname": clean_host,
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

    @staticmethod
    def _is_ipv4(val: str) -> bool:
        try:
            return ipaddress.ip_address(val).version == 4
        except ValueError:
            return False

    @staticmethod
    def _is_ipv6(val: str) -> bool:
        try:
            return ipaddress.ip_address(val).version == 6
        except ValueError:
            return False

    def _merge_adguard_client_data(
        self,
        existing: Dict[str, Any],
        incoming: Dict[str, Any],
        prune_stale_ips: bool = True,
        drop_ipv6: bool = False
    ) -> Dict[str, Any]:
        """Preserva regole, filtri, upstreams e pota indirizzi SLAAC obsoleti e IP scaduti (Issue #21 & #31)."""
        merged = dict(existing)
        merged["name"] = incoming.get("name") or existing.get("name")

        existing_ids = [str(x).strip() for x in (existing.get("ids") or []) if str(x).strip()]
        incoming_ids = [str(x).strip() for x in (incoming.get("ids") or []) if str(x).strip()]

        if drop_ipv6:
            # Filtra via gli indirizzi IPv6
            existing_ids = [x for x in existing_ids if not self._is_ipv6(x)]
            incoming_ids = [x for x in incoming_ids if not self._is_ipv6(x)]

        if prune_stale_ips:
            # 1. Preserva sempre gli identificatori MAC address e custom host aliases / CIDR
            preserved_macs = []
            special_ids = []
            valid_existing_ipv4 = []

            for cid in existing_ids:
                is_mac = (":" in cid and len(cid) == 17) or ("-" in cid and len(cid) == 17) or (len(cid) == 12 and all(c in "0123456789abcdefABCDEF" for c in cid))
                if is_mac:
                    preserved_macs.append(cid.upper())
                    continue

                if self._is_ipv4(cid):
                    valid_existing_ipv4.append(cid)
                elif self._is_ipv6(cid):
                    # Gli IPv6 vecchi non vengono preservati qui: se sono ancora validi saranno in incoming_ids
                    pass
                else:
                    # Non è un IP puro (es. CIDR come 192.168.1.0/24, host alias come custom-alias.lan, o tag) -> Preserva sempre!
                    special_ids.append(cid)

            # 2. Gestione indirizzi IPv4:
            incoming_has_ipv4 = any(self._is_ipv4(x) for x in incoming_ids)
            preserved_ipv4 = []
            for cid in valid_existing_ipv4:
                if cid in incoming_ids or not incoming_has_ipv4:
                    if cid not in preserved_ipv4:
                        preserved_ipv4.append(cid)

            # 3. Costruzione unione ordinata e pulita
            final_ids = []
            # MACs prima
            for m in (preserved_macs + [x for x in incoming_ids if (":" in x and len(x) == 17) or ("-" in x and len(x) == 17)]):
                if m.upper() not in [k.upper() for k in final_ids]:
                    final_ids.append(m.upper())

            # IPv4 dopo
            for ipv4 in (preserved_ipv4 + [x for x in incoming_ids if self._is_ipv4(x)]):
                if ipv4.lower() not in [k.lower() for k in final_ids]:
                    final_ids.append(ipv4)

            # IPv6 solo freschi da incoming (gli SLAAC vecchi vengono potati!)
            if not drop_ipv6:
                for x in incoming_ids:
                    if self._is_ipv6(x):
                        if x.lower() not in [k.lower() for k in final_ids]:
                            final_ids.append(x)

            # Special IDs manuali (CIDR / host aliases come custom-alias.lan)
            for s in special_ids:
                if s not in final_ids:
                    final_ids.append(s)

            merged["ids"] = final_ids
        else:
            # Comportamento di unione standard senza potatura
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
        
        prune_stale = bool(inst.get("prune_stale_ips", True))
        drop_v6 = bool(inst.get("drop_ipv6", False))
        insecure_tls = parse_insecure_tls(inst.get("insecure_tls", False))

        existing_by_name: Dict[str, Dict[str, Any]] = {}
        existing_by_id: Dict[str, Dict[str, Any]] = {}

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=not insecure_tls, follow_redirects=True) as client:
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
                    return {"success": False, "message": tr("dns.adguard_sync_auth_failed", url=url)}

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
                        merged = self._merge_adguard_client_data(existing_client, payload, prune_stale_ips=prune_stale, drop_ipv6=drop_v6)
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
                    "message": tr("dns.adguard_sync_result", added=added, updated=updated, failed=failed)
                }
        except Exception as e:
            if _is_tls_verification_error(e):
                return _tls_error_result(url, exc=e, engine="AdGuard")
            return {"success": False, "message": tr("dns.adguard_sync_error", error=str(e))}

    async def _sync_single_pihole(self, inst: Dict[str, Any], prepared_clients: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = normalize_dns_url(inst.get("url", ""))
        token = (inst.get("token") or inst.get("password") or "").strip()
        raw_zone = str(inst.get("zone") if inst.get("zone") is not None else "").strip().lstrip(".")
        insecure_tls = parse_insecure_tls(inst.get("insecure_tls", False))
        prune_stale = bool(inst.get("prune_stale_ips", True))

        # Mappatura dei target attivi che la dashboard sta sincronizzando: hostname.lower() -> active IP
        managed_active_targets: Dict[str, str] = {}
        for client_item in prepared_clients:
            ip = client_item.get("ip")
            hostname = client_item.get("hostname")
            if not ip or not hostname:
                continue
            target_name = f"{hostname}.{raw_zone}" if raw_zone else hostname
            managed_active_targets[target_name.lower().strip()] = ip.strip()

        try:
            async with httpx.AsyncClient(timeout=10.0, verify=not insecure_tls, follow_redirects=True) as client:
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
                    except Exception as e:
                        if _is_tls_verification_error(e):
                            raise

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

                    retained_entries: List[Tuple[str, str]] = []
                    stale_records: List[str] = []
                    seen_pairs: Set[Tuple[str, str]] = set()

                    for entry in existing_hosts:
                        if not (isinstance(entry, str) and " " in entry.strip()):
                            continue
                        parts = entry.strip().split(None, 1)
                        if len(parts) != 2:
                            continue
                        e_ip = parts[0].strip()
                        e_host = parts[1].strip()
                        e_host_lower = e_host.lower()

                        if e_host_lower in managed_active_targets:
                            active_ip = managed_active_targets[e_host_lower]
                            if e_ip.lower() == active_ip.lower():
                                pair_key = (e_ip.lower(), e_host_lower)
                                if pair_key not in seen_pairs:
                                    seen_pairs.add(pair_key)
                                    retained_entries.append((e_ip, e_host))
                            else:
                                if prune_stale:
                                    stale_records.append(f"{e_ip} {e_host}")
                                else:
                                    pair_key = (e_ip.lower(), e_host_lower)
                                    if pair_key not in seen_pairs:
                                        seen_pairs.add(pair_key)
                                        retained_entries.append((e_ip, e_host))
                        else:
                            # Record personalizzato non gestito: preserva integralmente
                            pair_key = (e_ip.lower(), e_host_lower)
                            if pair_key not in seen_pairs:
                                seen_pairs.add(pair_key)
                                retained_entries.append((e_ip, e_host))

                    # Aggiunta/aggiornamento dei target attivi
                    synced = 0
                    for client_item in prepared_clients:
                        ip = client_item.get("ip")
                        hostname = client_item.get("hostname")
                        if not ip or not hostname:
                            continue
                        safe_host = sanitize_dns_hostname(hostname, fallback=f"device-{ip.split('.')[-1] if '.' in ip else 'client'}")
                        target_name = f"{safe_host}.{raw_zone}" if raw_zone else safe_host
                        pair_key = (ip.lower().strip(), target_name.lower().strip())
                        if pair_key not in seen_pairs:
                            seen_pairs.add(pair_key)
                            retained_entries.append((ip.strip(), target_name))
                        synced += 1

                    new_hosts_list = [f"{ip_val} {host_val}" for ip_val, host_val in retained_entries]

                    # Tenta prima PATCH atomica (un'unica richiesta veloce senza restart multipli)
                    patch_payload = {
                        "config": {
                            "dns": {
                                "hosts": new_hosts_list
                            }
                        }
                    }
                    patch_res = await client.patch(f"{url}/api/config", json=patch_payload, headers=v6_headers)
                    zone_label = tr("dns.zone_label_zone", zone=raw_zone) if raw_zone else tr("dns.zone_label_direct")

                    if patch_res.status_code in (200, 204):
                        return {
                            "success": True,
                            "added": synced,
                            "updated": 0,
                            "failed": 0,
                            "message": tr("dns.pihole_v6_sync_ok", count=synced, zone_label=zone_label)
                        }

                    logger.warning(
                        f"Pi-hole v6 PATCH /api/config returned HTTP {patch_res.status_code}: {patch_res.text[:200]}"
                    )

                    # Fallback Pi-hole v6: PUT record per record su /api/config/dns/hosts/{value}
                    # ed eventuale DELETE dei record obsoleti identificati se prune_stale
                    if prune_stale:
                        for stale_item in stale_records:
                            try:
                                stale_quoted = urllib.parse.quote(stale_item)
                                await client.delete(f"{url}/api/config/dns/hosts/{stale_quoted}", headers=v6_headers)
                            except Exception:
                                pass

                    put_synced = 0
                    put_failed = 0
                    for client_item in prepared_clients:
                        ip = client_item.get("ip")
                        hostname = client_item.get("hostname")
                        if not ip or not hostname:
                            continue
                        safe_host = sanitize_dns_hostname(hostname, fallback=f"device-{ip.split('.')[-1] if '.' in ip else 'client'}")
                        target_name = f"{safe_host}.{raw_zone}" if raw_zone else safe_host
                        val_quoted = urllib.parse.quote(f"{ip} {target_name}")
                        put_res = await client.put(f"{url}/api/config/dns/hosts/{val_quoted}", headers=v6_headers)
                        if put_res.status_code in (200, 201, 204) or (put_res.status_code == 400 and "already present" in put_res.text.lower()):
                            put_synced += 1
                        else:
                            logger.warning(
                                f"Pi-hole v6 PUT host '{ip} {target_name}' failed ({put_res.status_code}): {put_res.text[:150]}"
                            )
                            put_failed += 1

                    return {
                        "success": put_failed == 0,
                        "added": put_synced,
                        "updated": 0,
                        "failed": put_failed,
                        "message": tr("dns.pihole_v6_sync_partial", count=put_synced, zone_label=zone_label, failed=put_failed)
                    }

                # -------------------------------------------------------------
                # 3. ESECUZIONE SINCRONIZZAZIONE PI-HOLE v5 (LEGACY admin/api.php)
                # -------------------------------------------------------------
                if prune_stale:
                    try:
                        v5_get_url = f"{url}/admin/api.php?customdns&action=get&auth={token}"
                        v5_get_res = await client.get(v5_get_url)
                        if v5_get_res.status_code == 200:
                            v5_data = v5_get_res.json()
                            raw_v5_entries = v5_data.get("data") if isinstance(v5_data, dict) else (v5_data if isinstance(v5_data, list) else [])
                            for entry in raw_v5_entries:
                                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                                    first_val, second_val = str(entry[0]).strip(), str(entry[1]).strip()
                                    if self._is_ipv4(first_val) or self._is_ipv6(first_val):
                                        e_ip, e_domain = first_val, second_val
                                    else:
                                        e_domain, e_ip = first_val, second_val
                                    
                                    if e_domain.lower() in managed_active_targets:
                                        active_ip = managed_active_targets[e_domain.lower()]
                                        if e_ip.lower() != active_ip.lower():
                                            v5_del_url = f"{url}/admin/api.php?customdns&action=delete&ip={e_ip}&domain={e_domain}&auth={token}"
                                            await client.get(v5_del_url)
                    except Exception as e:
                        logger.warning(f"Pi-hole v5: customdns pruning check failed: {e}")

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

                zone_label = tr("dns.zone_label_zone", zone=raw_zone) if raw_zone else tr("dns.zone_label_direct")
                return {
                    "success": failed == 0,
                    "added": synced,
                    "updated": 0,
                    "failed": failed,
                    "message": tr("dns.pihole_v5_sync", count=synced, zone_label=zone_label, failed=failed)
                }
        except Exception as e:
            if _is_tls_verification_error(e):
                return _tls_error_result(url, exc=e, engine="Pi-hole")
            return {"success": False, "message": tr("dns.pihole_sync_error", error=str(e))}

    async def _sync_single_technitium(self, inst: Dict[str, Any], prepared_clients: List[Dict[str, Any]]) -> Dict[str, Any]:
        url = normalize_dns_url(inst.get("url", ""))
        token = inst.get("token") or inst.get("password") or ""
        zone = inst.get("zone", "lan").lstrip(".")
        insecure_tls = parse_insecure_tls(inst.get("insecure_tls", False))

        synced = 0
        failed = 0
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=not insecure_tls, follow_redirects=True) as client:
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
                    "message": tr("dns.technitium_sync_result", count=synced, zone=zone)
                }
        except Exception as e:
            if _is_tls_verification_error(e):
                return _tls_error_result(url, exc=e, engine="Technitium")
            return {"success": False, "message": tr("dns.technitium_sync_error", error=str(e))}

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
                self._demo_status_keys[inst.get("id")] = ("dns.demo_status_clients", {"count": inst["last_sync_count"]})
                inst["last_sync_status"] = tr("dns.demo_status_clients", count=inst["last_sync_count"])
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
                "message": tr("dns.demo_sync_completed", count=len(simulated_results))
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
                "insecure_tls": all_s.get("adguard_insecure_tls"),
                "enabled": True
            })

        if not instances:
            return {"success": False, "message": tr("dns.no_instances"), "results": []}

        # Rende esplicita l'opzione TLS delle istanze salvate prima della sua introduzione
        # (salvata con lo stato di sincronizzazione più sotto)
        for inst in instances:
            apply_legacy_tls_default(inst)

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
                res = {"success": False, "message": tr("dns.unknown_engine_sync", engine=engine)}

            status_msg = res.get("message") or tr("dns.sync_done_default")
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
            "message": tr("dns.sync_completed", count=len(results))
        }

    async def auto_sync_if_enabled(self, devices: List[Dict[str, Any]]) -> None:
        """Esegue la sincronizzazione background se il toggle globale è attivo."""
        settings = await self.get_settings()
        if not settings.get("enabled"):
            return
        try:
            # 1. Reverse NDP Enrichment scan per recuperare client orfani ULA prima del push (Issue #57)
            try:
                from app.services.enrichment_service import enrichment_service
                await enrichment_service.scan_all_adguard_instances()
            except Exception as e_scan:
                logger.debug(f"Pre-sync AdGuard NDP scan skipped/failed: {e_scan}")

            # 2. Sincronizzazione regolare verso tutti i server DNS
            log_event(logger, logging.INFO, "log_ops.dns_autosync_started")
            res = await self.sync_devices(devices)
            log_event(logger, logging.INFO, "log_ops.dns_autosync_result", result=res.get('message'))
        except Exception as e:
            log_event(logger, logging.ERROR, "log_ops.dns_autosync_failed", error=str(e))


# Istanza singleton esportata
dns_manager = DNSManager()
dns_service = dns_manager
