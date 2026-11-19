"""
Network overview, WAN/LAN settings, guest network, speedtest, port forwards, and DHCP reservations.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging
import random
import re
import time
from app.config import settings
from app.i18n import log_event, tr
from app.services.eero.const import EERO_API_BASE

logger = logging.getLogger(__name__)


class EeroNetworkMixin:
    """Metodi per dettagli rete, WAN, SpeedTest, Rete Ospiti, Port Forwarding e Prenotazioni IP."""

    def _normalize_network_details(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(raw)
        
        # IP Pubblico / WAN IP (Issue #56: nessun placeholder fittizio 0.0.0.0 né fallback a gateway_ip LAN)
        pub_ip = (
            data.get("public_ip") or 
            data.get("wan_ip") or 
            (data.get("ip_settings") or {}).get("public_ip") or 
            None
        )
        if pub_ip:
            pub_ip_str = str(pub_ip).strip()
            data["public_ip"] = pub_ip_str if pub_ip_str not in ("0.0.0.0", "None", "") else None
        else:
            data["public_ip"] = None

        # Gateway IP & Gateway Network Metadata (Issue #56: nessun default 192.168.4.1 hardcoded)
        gw_ip = (
            data.get("gateway_ip") or 
            (data.get("ip_settings") or {}).get("ip") or 
            None
        )
        if gw_ip:
            gw_ip_str = str(gw_ip).strip()
            data["gateway_ip"] = gw_ip_str if gw_ip_str not in ("None", "") else None
        else:
            data["gateway_ip"] = None

        gw_raw = raw.get("gateway")
        gw_id = ""
        gw_url = ""
        gw_name = raw.get("gateway_name") or ""
        
        if isinstance(gw_raw, dict):
            gw_url = str(gw_raw.get("url") or "")
            gw_id = str(gw_raw.get("id") or (gw_url.split("/")[-1] if "/" in gw_url else ""))
            gw_name = gw_name or gw_raw.get("name") or gw_raw.get("location") or ""
        elif isinstance(gw_raw, str):
            gw_str = gw_raw.strip()
            if "/" in gw_str:
                gw_url = gw_str
                gw_id = gw_str.split("/")[-1]
            elif gw_str.isdigit() or len(gw_str) >= 6:
                gw_id = gw_str
            elif gw_str and not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw_str):
                gw_name = gw_name or gw_str
        
        if gw_id:
            data["gateway_eero_id"] = gw_id
            self.current_gateway_id = str(gw_id)
        if gw_url:
            data["gateway_eero_url"] = gw_url
            self.current_gateway_url = str(gw_url)
        if gw_name:
            data["gateway_name"] = gw_name
            self.current_gateway_name = str(gw_name)
        if data.get("gateway_ip"):
            self.current_gateway_ip = str(data.get("gateway_ip"))

        # Netmask / Subnet LAN (Issue #72)
        netmask = (
            (data.get("ip_settings") or {}).get("netmask") or 
            (data.get("ip_settings") or {}).get("mask") or
            (data.get("dhcp") or {}).get("netmask") or 
            (data.get("dhcp") or {}).get("mask") or
            None
        )
        if netmask:
            self.current_gateway_netmask = str(netmask).strip()
            data["gateway_netmask"] = self.current_gateway_netmask

        # ISP
        data["isp"] = (
            data.get("isp") or 
            data.get("isp_name") or 
            (data.get("speed") or {}).get("isp") or 
            (data.get("geo_ip") or {}).get("isp") or 
            ""
        )

        # Stato Connessione WAN: SEMPRE online quando la rete risponde
        data["status"] = "online"

        # DNS Servers (Supporta array, dizionario {'ips': [...]}, {'custom': {'nameservers': [...]}}, stringhe e liste annidate - Issue #30)
        dns_candidates = []
        for candidate in [
            data.get("dns"),
            data.get("dns_servers"),
            data.get("dns_nameservers"),
            data.get("wan_dns"),
            (data.get("dhcp") or {}).get("dns") if isinstance(data.get("dhcp"), dict) else None,
        ]:
            if candidate:
                dns_candidates.append(candidate)

        extracted_ips = []

        def _collect_ips(val):
            if not val:
                return
            if isinstance(val, str):
                found_ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", val)
                if found_ips:
                    extracted_ips.extend(found_ips)
                else:
                    val_strip = val.strip()
                    if val_strip and not val_strip.startswith(("{", "[")):
                        extracted_ips.append(val_strip)
            elif isinstance(val, list):
                for item in val:
                    _collect_ips(item)
            elif isinstance(val, dict):
                # Priorità a configurazioni custom e nameservers esplicite
                for k in ["custom", "nameservers", "ips", "servers", "primary", "secondary", "dns"]:
                    if k in val and val[k]:
                        _collect_ips(val[k])
                # Se ancora nulla, ispeziona ricorsivamente gli altri campi escludendo flag non-IP
                if not any(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", str(x).strip()) for x in extracted_ips):
                    for k, v in val.items():
                        if k not in ["parental", "zscaler", "caching", "mode", "policy", "block_malware"]:
                            _collect_ips(v)

        for raw in dns_candidates:
            _collect_ips(raw)

        clean_dns = []
        for ip_str in extracted_ips:
            ip_clean = str(ip_str).strip().strip("'\"")
            if ip_clean and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_clean):
                try:
                    octets = [int(o) for o in ip_clean.split(".")]
                    if len(octets) == 4 and all(0 <= o <= 255 for o in octets):
                        if ip_clean not in clean_dns:
                            clean_dns.append(ip_clean)
                except Exception:
                    pass

        if not clean_dns:
            gw_fallback = data.get("gateway_ip")
            if gw_fallback:
                clean_dns = [gw_fallback]

        data["dns_servers"] = clean_dns

        # Speed test
        if "speed" in data and isinstance(data["speed"], dict):
            sp = data["speed"]
            # Nessun valore predefinito: senza misura eero (es. speed test mai eseguito) i valori restano 0
            # (un ping non fornito da eero vale quindi 0 ms, come gli altri campi assenti)
            down = (sp.get("down") or {}).get("value") if isinstance(sp.get("down"), dict) else sp.get("down_mbps")
            up = (sp.get("up") or {}).get("value") if isinstance(sp.get("up"), dict) else sp.get("up_mbps")
            ping = sp.get("ping_ms") or sp.get("latency")
            data["speedtest"] = {
                "download_mbps": round(float(down or 0), 1),
                "upload_mbps": round(float(up or 0), 1),
                "ping_ms": round(float(ping or 0), 1),
                # None se eero non ha una data: un orario inventato (now) farebbe credere a speedtest_service che il test sia finito
                "timestamp": sp.get("date") or sp.get("timestamp")
            }
        return data


    async def get_network_details(self) -> Dict[str, Any]:
        """Recupera lo stato WAN, IP pubblico, DNS, ISP, SpeedTest e impostazioni rete."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_network_details()

        if not self.current_network_id:
            await self.fetch_account_info()

        if not self.current_network_id:
            return self._last_network_details or {}

        async with self._client_session() as client:
            resp = await client.get(f"{EERO_API_BASE}/networks/{self.current_network_id}", headers=self._get_headers())
            if resp.status_code != 200:
                log_event(logger, logging.ERROR, "log_eero.network_details_fetch_failed", status=resp.status_code, response=resp.text)
                return self._last_network_details or {}
            norm = self._normalize_network_details(resp.json().get("data", {}))
            self._last_network_details = norm
            return norm


    async def get_network_updates(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Recupera lo stato di aggiornamento firmware della rete (/2.2/networks/{id}/updates)."""
        target_id = network_id or self.current_network_id
        if settings.demo_mode or not self.is_authenticated or (self.user_token and self.user_token.startswith("demo_")):
            return {
                "has_update": True,
                "can_update_now": False,
                "target_firmware": "v7.16.0-9483",
                "update_status": "rolling_release"
            }

        if not target_id:
            await self.fetch_account_info()
            target_id = self.current_network_id

        if not target_id:
            return {}

        try:
            async with self._client_session() as client:
                resp = await client.get(f"{EERO_API_BASE}/networks/{target_id}/updates", headers=self._get_headers())
                if resp.status_code == 200:
                    return resp.json().get("data", {})
                else:
                    logger.debug(f"Updates endpoint returned {resp.status_code}: {resp.text}")
                    return {}
        except Exception as e:
            logger.debug(f"Error querying network updates: {e}")
            return {}


    async def reboot_network(self) -> Dict[str, Any]:
        """Invia il comando di riavvio all'intera rete eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            log_event(logger, logging.INFO, "log_eero.demo_network_reboot")
            return {"status": "success", "message": tr("eero.network_reboot_demo")}

        async with self._client_session() as client:
            resp = await client.post(f"{EERO_API_BASE}/networks/{self.current_network_id}/reboot", headers=self._get_headers())
            if resp.status_code not in (200, 202):
                raise RuntimeError(tr("eero.network_reboot_error", error=resp.text))
            return {"status": "success", "message": tr("eero.network_reboot_sent")}


    async def set_guest_network(
        self,
        enabled: bool,
        name: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Attiva/disattiva la rete ospiti e aggiorna nome SSID / password."""
        payload: Dict[str, Any] = {"enabled": enabled}
        if name:
            payload["name"] = name
        if password:
            payload["password"] = password

        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["guest_network"]["enabled"] = enabled
            if name:
                self._demo_state["guest_network"]["name"] = name
            if password:
                self._demo_state["guest_network"]["password"] = password
            return {"status": "success", "guest_network": self._demo_state["guest_network"]}

        async with self._client_session() as client:
            resp = await client.put(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/guestnetwork",
                json=payload,
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(tr("eero.guest_network_error", error=resp.text))
            return resp.json().get("data", payload)

    # =========================================================================
    # SPEEDTEST API TRIGGER
    # =========================================================================
    async def trigger_eero_speedtest(self) -> Dict[str, Any]:
        """Avvia uno speedtest nativo sul gateway eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            # Genera risultato simulato coerente
            dl = round(random.uniform(850.0, 940.0), 2)
            ul = round(random.uniform(280.0, 315.0), 2)
            ping = round(random.uniform(7.0, 14.0), 1)
            jitter = round(random.uniform(0.5, 2.1), 1)
            self._demo_state["speedtest"] = {
                "download_mbps": dl,
                "upload_mbps": ul,
                "ping_ms": ping,
                "jitter": jitter,
                "date": datetime.now(timezone.utc).isoformat(),
            }
            return {"status": "success", "result": self._demo_state["speedtest"]}

        async with self._client_session() as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/speedtest",
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 202):
                raise RuntimeError(tr("eero.speedtest_start_error", error=resp.text))
            return resp.json().get("data", {})

    # =========================================================================
    # PRENOTAZIONI DHCP & PORT FORWARDING
    # =========================================================================
    def _extract_raw_list(self, data: Any, key_name: str) -> List[Dict[str, Any]]:
        """Estrae una lista di dizionari da risposte eero API eterogenee (liste, dizionari nidificati o dict indicizzati per ID)."""
        if not data:
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            # 1. Chiave specifica presente
            if key_name in data:
                val = data[key_name]
                if isinstance(val, list):
                    return [item for item in val if isinstance(item, dict)]
                if isinstance(val, dict):
                    if "data" in val and isinstance(val["data"], list):
                        return [item for item in val["data"] if isinstance(item, dict)]
                    return [v for v in val.values() if isinstance(v, dict)]
            # 2. Struttura {"data": [...]} o {"data": {"key": [...]}}
            if "data" in data:
                val = data["data"]
                if isinstance(val, list):
                    return [item for item in val if isinstance(item, dict)]
                if isinstance(val, dict):
                    if key_name in val:
                        sub = val[key_name]
                        if isinstance(sub, list):
                            return [item for item in sub if isinstance(item, dict)]
                        if isinstance(sub, dict) and "data" in sub and isinstance(sub["data"], list):
                            return [item for item in sub["data"] if isinstance(item, dict)]
                    return [v for v in val.values() if isinstance(v, dict)]
            # 3. Dizionario indicizzato per ID (es. {"res_1": {...}, "res_2": {...}})
            dict_items = [v for v in data.values() if isinstance(v, dict)]
            if dict_items:
                return dict_items
        return []

    def _normalize_reservation(self, r: Dict[str, Any], cached_devices: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Normalizza una regola di prenotazione DHCP statica garantendo la compatibilità con tutti i firmware ed estrazione ricorsiva di device."""
        res = dict(r)
        raw_url = str(res.get("url") or "")
        r_id = str(res.get("id") or (raw_url.split("/")[-1] if raw_url else "") or "")
        
        # Estrazione device object se presente come dict
        device_obj = res.get("device") if isinstance(res.get("device"), dict) else {}
        
        mac_val = (
            res.get("mac") 
            or res.get("mac_address") 
            or device_obj.get("mac") 
            or device_obj.get("mac_address") 
            or ""
        ).lower().strip()
        
        ip_val = str(
            res.get("ip") 
            or res.get("ip_address") 
            or device_obj.get("ip") 
            or device_obj.get("ip_address") 
            or ""
        ).strip()
        
        desc = str(
            res.get("description") 
            or res.get("name") 
            or res.get("nickname") 
            or device_obj.get("nickname") 
            or device_obj.get("custom_name") 
            or device_obj.get("name") 
            or device_obj.get("hostname") 
            or "Device"
        ).strip()
        
        # Gestione device identifier o URL
        device_raw = res.get("device")
        dev_url = ""
        dev_id = ""
        if isinstance(device_raw, dict):
            dev_url = str(device_raw.get("url") or "")
            dev_id = str(device_raw.get("id") or (dev_url.split("/")[-1] if dev_url else ""))
        elif isinstance(device_raw, str):
            dev_url = device_raw
            dev_id = device_raw.split("/")[-1] if "/" in device_raw else device_raw
        
        device_id = str(res.get("device_id") or dev_id or "")

        # Se il MAC è ancora vuoto, correlazione automatica con i dispositivi noti nella rete (per URL, device_id o IP)
        if not mac_val and cached_devices:
            for d in cached_devices:
                if not isinstance(d, dict):
                    continue
                d_mac = (d.get("mac") or d.get("mac_address") or "").lower().strip()
                d_url = str(d.get("url") or "")
                d_id = str(d.get("id") or "")
                d_ip = str(d.get("ip") or "").strip()
                if (dev_url and dev_url == d_url) or (device_id and device_id == d_id) or (ip_val and ip_val == d_ip):
                    mac_val = d_mac
                    if desc == "Device":
                        desc = str(d.get("custom_name") or d.get("nickname") or d.get("hostname") or "Device").strip()
                    break

        url_val = raw_url or (f"/2.2/networks/{self.current_network_id}/reservations/{r_id}" if r_id else "")

        return {
            "id": r_id,
            "url": url_val,
            "mac": mac_val,
            "mac_address": mac_val,
            "ip": ip_val,
            "ip_address": ip_val,
            "description": desc,
            "name": desc,
            "device": dev_url or device_id,
            "device_id": device_id,
        }

    def _normalize_forward(
        self, 
        fwd: Dict[str, Any], 
        res_map: Optional[Dict[str, Any]] = None,
        dev_map: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Normalizza una regola di inoltro porte garantendo la coesistenza di nomi porta eero (gateway/client) e dashboard (from/to)."""
        f = dict(fwd)
        raw_url = str(f.get("url") or "")
        f_id = str(f.get("id") or (raw_url.split("/")[-1] if raw_url else "") or "")
        ip_val = str(
            f.get("ip") 
            or f.get("ip_address") 
            or f.get("internal_ip") 
            or f.get("client_ip") 
            or f.get("host") 
            or f.get("target_ip") 
            or f.get("lan_ip") 
            or ""
        ).strip()
        desc = str(f.get("description") or f.get("name") or f.get("service") or "Custom Rule").strip()
        proto = str(f.get("protocol") or "tcp").lower().strip()

        # Porte: supporta gateway_port/client_port (Cloud eero nativo), port_from/port_to (Dashboard) o port singola
        port_ext = (
            f.get("port_from") 
            or f.get("gateway_port") 
            or f.get("external_port") 
            or f.get("wan_port") 
            or f.get("port") 
            or 0
        )
        port_int = (
            f.get("port_to") 
            or f.get("client_port") 
            or f.get("internal_port") 
            or f.get("lan_port") 
            or f.get("port") 
            or port_ext 
            or 0
        )

        try:
            port_ext = int(port_ext)
        except Exception:
            port_ext = 0
        try:
            port_int = int(port_int)
        except Exception:
            port_int = port_ext

        # Estrazione riferimento reservation (dict o stringa)
        raw_res = f.get("reservation") or f.get("reservation_id") or ""
        res_url = ""
        res_id = ""
        if isinstance(raw_res, dict):
            res_url = str(raw_res.get("url") or "")
            res_id = str(raw_res.get("id") or (res_url.split("/")[-1] if res_url else ""))
        elif isinstance(raw_res, str):
            res_url = raw_res
            res_id = raw_res.split("/")[-1] if "/" in raw_res else raw_res

        # Estrazione riferimento device (dict o stringa)
        raw_dev = f.get("device") or f.get("device_id") or ""
        dev_url = ""
        dev_id = ""
        mac_val = (f.get("mac") or f.get("mac_address") or "").lower().strip()
        if isinstance(raw_dev, dict):
            dev_url = str(raw_dev.get("url") or "")
            dev_id = str(raw_dev.get("id") or (dev_url.split("/")[-1] if dev_url else ""))
            if not mac_val:
                mac_val = (raw_dev.get("mac") or raw_dev.get("mac_address") or "").lower().strip()
            if not ip_val:
                ip_val = str(raw_dev.get("ip") or raw_dev.get("ip_address") or "").strip()
        elif isinstance(raw_dev, str):
            dev_url = raw_dev
            dev_id = raw_dev.split("/")[-1] if "/" in raw_dev else raw_dev

        # Se abbiamo dev_map, correlazione e arricchimento IP / MAC tramite device ID o URL
        if dev_map:
            matched_d = dev_map.get(dev_url) or dev_map.get(dev_id) or (dev_map.get(mac_val) if mac_val else None)
            if matched_d:
                if not ip_val:
                    ip_val = str(matched_d.get("ip") or "").strip()
                if not mac_val:
                    mac_val = (matched_d.get("mac") or "").lower().strip()

        # Se manca l'IP o MAC ma abbiamo la reservation correlata, arricchimento da res_map
        if res_map and (res_url or res_id):
            matched_r = res_map.get(res_url) or res_map.get(res_id)
            if matched_r:
                if not ip_val:
                    ip_val = str(matched_r.get("ip") or "").strip()
                if not mac_val:
                    mac_val = (matched_r.get("mac") or "").lower().strip()

        url_val = raw_url if isinstance(raw_url, str) and raw_url.startswith("/") else (f"/2.2/networks/{self.current_network_id}/forwards/{f_id}" if f_id else "")

        return {
            "id": f_id,
            "url": url_val,
            "ip": ip_val,
            "internal_ip": ip_val,
            "mac": mac_val,
            "mac_address": mac_val,
            "device": dev_url or dev_id,
            "device_id": dev_id,
            "port_from": port_ext,
            "port_to": port_int,
            "gateway_port": port_ext,
            "client_port": port_int,
            "external_port": port_ext,
            "internal_port": port_int,
            "protocol": proto,
            "description": desc,
            "name": desc,
            "reservation": res_url or res_id,
            "reservation_id": res_id,
            "enabled": bool(f.get("enabled", True)),
        }

    async def get_forwards_and_reservations(self) -> Dict[str, Any]:
        """Recupera le regole di inoltro porte e prenotazioni IP statico con normalizzazione universale."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                log_event(logger, logging.WARNING, "log_eero.forwards_network_id_unresolved", error=str(e))

        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            raw_res = self._demo_state.get("reservations", [])
            raw_fwd = self._demo_state.get("forwards", [])
            return {
                "reservations": [self._normalize_reservation(r) for r in raw_res if isinstance(r, dict)],
                "forwards": [self._normalize_forward(f) for f in raw_fwd if isinstance(f, dict)],
            }

        # Nessuna rete risolta: evita richieste verso /networks/None/...
        if not self.current_network_id:
            return {"reservations": [], "forwards": []}

        async with self._client_session() as client:
            raw_res_payload = None
            raw_fwd_payload = None

            try:
                res_reservations = await client.get(
                    f"{EERO_API_BASE}/networks/{self.current_network_id}/reservations",
                    headers=self._get_headers()
                )
                if res_reservations.status_code == 200:
                    raw_res_payload = res_reservations.json()
                else:
                    log_event(logger, logging.WARNING, "log_eero.reservations_response_status", status=res_reservations.status_code, response=res_reservations.text)
            except Exception as e:
                log_event(logger, logging.WARNING, "log_eero.reservations_fetch_failed", error=str(e))

            try:
                res_forwards = await client.get(
                    f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards",
                    headers=self._get_headers()
                )
                if res_forwards.status_code == 200:
                    raw_fwd_payload = res_forwards.json()
                else:
                    # Fallback su /port_forwards in caso di 404 o altro codice HTTP su /forwards
                    try:
                        res_pf = await client.get(
                            f"{EERO_API_BASE}/networks/{self.current_network_id}/port_forwards",
                            headers=self._get_headers()
                        )
                        if res_pf.status_code == 200:
                            raw_fwd_payload = res_pf.json()
                    except Exception:
                        pass
            except Exception as e:
                log_event(logger, logging.WARNING, "log_eero.forwards_fetch_failed", error=str(e))

            raw_res_data = raw_res_payload.get("data", raw_res_payload) if isinstance(raw_res_payload, dict) else (raw_res_payload or [])
            raw_fwd_data = raw_fwd_payload.get("data", raw_fwd_payload) if isinstance(raw_fwd_payload, dict) else (raw_fwd_payload or [])

            res_list = self._extract_raw_list(raw_res_data, "reservations")
            fwd_list = self._extract_raw_list(raw_fwd_data, "forwards")

            if not fwd_list:
                try:
                    res_net = await client.get(
                        f"{EERO_API_BASE}/networks/{self.current_network_id}",
                        headers=self._get_headers()
                    )
                    if res_net.status_code == 200:
                        net_data = res_net.json().get("data", {})
                        net_fwds = net_data.get("forwards") or net_data.get("port_forwards") or []
                        if isinstance(net_fwds, list):
                            fwd_list.extend(net_fwds)
                        elif isinstance(net_fwds, dict):
                            fwd_list.extend(net_fwds.values())
                except Exception:
                    pass

            cached_devices = []
            try:
                from app.services.poller import background_poller
                cached_devices = background_poller.get_cached_state().get("devices", [])
            except Exception:
                pass

            dev_map = {}
            for d in cached_devices:
                if isinstance(d, dict):
                    d_id = str(d.get("id") or "")
                    d_url = str(d.get("url") or "")
                    d_mac = (d.get("mac") or d.get("mac_address") or "").lower().strip()
                    d_ip = str(d.get("ip") or "").strip()
                    entry = {"id": d_id, "url": d_url, "mac": d_mac, "ip": d_ip}
                    if d_id:
                        dev_map[d_id] = entry
                    if d_url:
                        dev_map[d_url] = entry
                    if d_mac:
                        dev_map[d_mac] = entry
                    if d_ip:
                        dev_map[d_ip] = entry

            normalized_reservations = [self._normalize_reservation(r, cached_devices=cached_devices) for r in res_list]

            # Mappa per correlazione reservation -> port forwarding
            res_map = {}
            for r in normalized_reservations:
                if r.get("url"):
                    res_map[r["url"]] = r
                if r.get("id"):
                    res_map[r["id"]] = r
                if r.get("ip"):
                    res_map[r["ip"]] = r

            # Estrazione regole di port forwarding annidate direttamente dentro le prenotazioni
            for r_raw, r_norm in zip(res_list, normalized_reservations):
                nested_fwds = []
                if isinstance(r_raw, dict):
                    nested = (
                        r_raw.get("forwards") 
                        or r_raw.get("port_forwards") 
                        or r_raw.get("ports")
                        or r_raw.get("port_forward_rules")
                        or r_raw.get("rules")
                    )
                    if isinstance(nested, list):
                        nested_fwds = [f for f in nested if isinstance(f, dict)]
                    elif isinstance(nested, dict):
                        nested_fwds = [f for f in nested.values() if isinstance(f, dict)]
                
                for nf in nested_fwds:
                    enriched = dict(nf)
                    if not enriched.get("ip") and r_norm.get("ip"):
                        enriched["ip"] = r_norm["ip"]
                    if not enriched.get("mac") and r_norm.get("mac"):
                        enriched["mac"] = r_norm["mac"]
                    if not enriched.get("reservation") and r_norm.get("url"):
                        enriched["reservation"] = r_norm["url"]
                    fwd_list.append(enriched)

            # Normalizza e deduplica tutte le regole di port forward
            normalized_forwards = []
            seen_fwd_keys = set()
            for f in fwd_list:
                norm_f = self._normalize_forward(f, res_map=res_map, dev_map=dev_map)
                f_key = norm_f.get("id") or f"{norm_f.get('ip')}_{norm_f.get('port_from')}_{norm_f.get('port_to')}_{norm_f.get('protocol')}"
                if f_key not in seen_fwd_keys:
                    seen_fwd_keys.add(f_key)
                    normalized_forwards.append(norm_f)

            return {
                "reservations": normalized_reservations,
                "forwards": normalized_forwards,
            }

    async def add_reservation(
        self,
        ip: str,
        mac: str,
        description: Optional[str] = "Device"
    ) -> Dict[str, Any]:
        """Crea o aggiorna una prenotazione IP statico (DHCP Reservation) nel Cloud eero."""
        reservation = {
            "id": f"res_{mac.replace(':', '')}",
            "ip": ip,
            "mac": mac.lower(),
            "description": description or "Device"
        }
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["reservations"] = [
                r for r in self._demo_state.get("reservations", [])
                if (r.get("mac") or "").lower() != mac.lower() and r.get("ip") != ip
            ]
            self._demo_state["reservations"].append(reservation)
            return {"status": "success", "reservation": self._normalize_reservation(reservation)}

        async with self._client_session() as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/reservations",
                json={"ip": ip, "mac": mac.lower(), "description": description or "Device"},
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 201):
                resp_put = await client.put(
                    f"{EERO_API_BASE}/networks/{self.current_network_id}/reservations",
                    json={"ip": ip, "mac": mac.lower(), "description": description or "Device"},
                    headers=self._get_headers()
                )
                if resp_put.status_code not in (200, 201, 204):
                    raise RuntimeError(tr("eero.reservation_add_error", error=resp.text))
                data_out = resp_put.json().get("data", reservation)
                return {"status": "success", "reservation": self._normalize_reservation(data_out if isinstance(data_out, dict) else reservation)}
            data_out = resp.json().get("data", reservation)
            return {"status": "success", "reservation": self._normalize_reservation(data_out if isinstance(data_out, dict) else reservation)}

    async def delete_reservation(self, reservation_id: str) -> Dict[str, Any]:
        """Elimina una prenotazione IP statico dal Cloud eero."""
        clean_id = str(reservation_id).split("/")[-1].strip()
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["reservations"] = [
                r for r in self._demo_state.get("reservations", [])
                if r.get("id") != clean_id and (r.get("mac") or "").lower() != clean_id.lower() and r.get("ip") != clean_id
            ]
            return {"status": "success", "deleted": clean_id}

        async with self._client_session() as client:
            resp = await client.delete(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/reservations/{clean_id}",
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(tr("eero.reservation_delete_error", error=resp.text))
            return {"status": "success", "deleted": clean_id}

    async def add_port_forward(
        self,
        ip: str,
        port_from: int,
        port_to: int,
        protocol: str = "tcp",
        description: str = "Custom Rule"
    ) -> Dict[str, Any]:
        """Aggiunge una regola di inoltro porte supportando sia la sintassi Cloud eero nativa sia i campi estesi."""
        rule_payload = {
            "ip": ip,
            "port_from": port_from,
            "port_to": port_to,
            "gateway_port": port_from,
            "client_port": port_to,
            "protocol": protocol.lower(),
            "description": description,
            "name": description,
        }
        rule_demo = {
            "id": f"fwd_{int(time.time())}",
            **rule_payload
        }
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["forwards"].append(rule_demo)
            return {"status": "success", "forward": self._normalize_forward(rule_demo)}

        async with self._client_session() as client:
            # 1. Prova prima con il payload compatibile Cloud eero standard (gateway_port / client_port)
            eero_payload = {
                "ip": ip,
                "gateway_port": port_from,
                "client_port": port_to,
                "protocol": protocol.lower(),
                "description": description,
            }
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards",
                json=eero_payload,
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 201):
                # Fallback con port_from / port_to
                resp_fallback = await client.post(
                    f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards",
                    json=rule_payload,
                    headers=self._get_headers()
                )
                if resp_fallback.status_code not in (200, 201):
                    raise RuntimeError(tr("eero.port_forward_add_error", error=resp.text))
                data_out = resp_fallback.json().get("data", rule_demo)
                return {"status": "success", "forward": self._normalize_forward(data_out if isinstance(data_out, dict) else rule_demo)}

            data_out = resp.json().get("data", rule_demo)
            return {"status": "success", "forward": self._normalize_forward(data_out if isinstance(data_out, dict) else rule_demo)}

    async def delete_port_forward(self, forward_id: str) -> Dict[str, Any]:
        """Elimina una regola di inoltro porte."""
        clean_id = str(forward_id).split("/")[-1].strip()
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["forwards"] = [f for f in self._demo_state["forwards"] if f.get("id") != clean_id]
            return {"status": "success", "deleted": clean_id}

        async with self._client_session() as client:
            resp = await client.delete(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards/{clean_id}",
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(tr("eero.port_forward_delete_error", error=resp.text))
            return {"status": "success", "deleted": clean_id}

    # =========================================================================
    # GESTIONE PROFILI UTENTE CLOUD (FAMILY PROFILES / USERS)
    # =========================================================================
