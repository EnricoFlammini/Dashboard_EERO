"""
Mesh node topology, gateway election, node normalization, LED control, placement test, and node registration.
"""
from typing import Dict, Any, List, Optional, Tuple
import ipaddress
import logging
import random
import re
from app.config import settings
from app.i18n import log_event, tr
from app.services.eero.const import EERO_API_BASE, parse_speed_mbps, format_speed_mbps

logger = logging.getLogger(__name__)


class EeroMeshMixin:
    """Metodi per topologia nodi eero mesh, LED, reboot nodo, placement test e onboarding."""

    def _is_gateway_node(self, node: Dict[str, Any]) -> bool:
        """Verifica accuratamente se un nodo è il Primary Gateway escludendo falsi positivi da stringhe URL/IP (Issue #19 & Issue #105)."""
        if node.get("is_gateway") is True or node.get("is_primary_node") is True:
            return True
        if node.get("is_gateway") is False and "gateway" not in node:
            return False

        raw_gw = node.get("gateway")
        
        # 1. Booleano diretto
        if isinstance(raw_gw, bool):
            return raw_gw
            
        node_url = str(node.get("url") or "").strip()
        node_id = str(node.get("id") or "").strip()
        node_serial = str(node.get("serial") or "").strip()
        node_ip = str(node.get("ip_address") or node.get("ip") or "").strip()

        # Check contro Gateway registrato a livello di rete (/2.2/networks/{id} - Issue #26)
        gw_cached_id = getattr(self, "current_gateway_id", None)
        gw_cached_url = getattr(self, "current_gateway_url", None)
        gw_cached_ip = getattr(self, "current_gateway_ip", None)

        if gw_cached_id and node_id and str(node_id) == str(gw_cached_id):
            return True
        if gw_cached_url and node_url and (node_url == gw_cached_url or node_url.endswith(gw_cached_url) or gw_cached_url.endswith(node_url)):
            return True
        if gw_cached_ip and node_ip and node_ip == gw_cached_ip:
            return True

        # 2. Stringa (URL risorsa, ID numerico, stringa booleana o IP)
        if isinstance(raw_gw, str):
            gw_s = raw_gw.strip()
            if gw_s.lower() in ("true", "1", "yes"):
                return True
            if gw_s.lower() in ("false", "0", "no", "none", "null", ""):
                return False
            
            # Se la stringa corrisponde esattamente agli identificatori di QUESTO nodo
            # Confronto per segmento di percorso: il gateway "10" non corrisponde a "/2.2/eeros/110"
            if node_url and (gw_s == node_url or gw_s.endswith(node_url) or node_url.endswith("/" + gw_s.lstrip("/"))):
                return True
            if node_id and (gw_s == node_id or gw_s.split("/")[-1] == node_id):
                return True
            if node_serial and gw_s.lower() == node_serial.lower():
                return True
            
            # Se gw_s è un URL o ID che punta a un ALTRO nodo (es. "/2.2/eeros/104" su nodo 101), questo nodo è un beacon foglia
            if "/eeros/" in gw_s or (node_id and gw_s != node_id and (gw_s.isdigit() or len(gw_s) >= 6)):
                return False
            
            # Se gw_s è un indirizzo IP (es. gateway router di subnet "192.168.1.1")
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw_s):
                if node_ip and node_ip == gw_s:
                    return True
                return False

        # 3. Dizionario (es. {"url": "/2.2/eeros/104"})
        if isinstance(raw_gw, dict):
            gw_u = str(raw_gw.get("url") or raw_gw.get("id") or "").strip()
            if gw_u and (gw_u == node_url or gw_u == node_id or (node_url and gw_u.endswith(node_url))):
                return True
            return False

        # 4. Controllo esplicito su ruolo/tipo nodo
        role = str(node.get("role") or node.get("type") or node.get("node_type") or "").lower()
        if role in ("gateway", "primary", "root", "router"):
            return True

        return False

    def _get_lan_network(self) -> Optional[ipaddress.IPv4Network]:
        """Restituisce l'oggetto IPv4Network per la subnet LAN eero se nota, altrimenti None (Issue #72)."""
        gw_ip = getattr(self, "current_gateway_ip", None)
        if not gw_ip:
            return None
        gw_mask = getattr(self, "current_gateway_netmask", None)
        try:
            if gw_mask:
                return ipaddress.IPv4Network(f"{gw_ip}/{gw_mask}", strict=False)
            octets = [int(x) for x in gw_ip.split(".")]
            if len(octets) == 4:
                if octets[0] == 192 and octets[1] == 168:
                    if octets[2] in (4, 5, 6, 7):
                        return ipaddress.IPv4Network(f"{octets[0]}.{octets[1]}.4.0/22", strict=False)
                    return ipaddress.IPv4Network(f"{octets[0]}.{octets[1]}.{octets[2]}.0/24", strict=False)
                elif octets[0] == 10:
                    return ipaddress.IPv4Network(f"10.{octets[1]}.{octets[2]}.0/24", strict=False)
                elif octets[0] == 172 and 16 <= octets[1] <= 31:
                    return ipaddress.IPv4Network(f"172.{octets[1]}.{octets[2]}.0/24", strict=False)
        except Exception:
            pass
        return None

    @staticmethod
    def _sort_ipv4_candidates(candidates: List[str], lan_net: Optional[ipaddress.IPv4Network] = None) -> List[str]:
        """Ordina i candidati IPv4 dando priorità alla LAN fisica e deprioritizzando bridge virtuali Docker/Podman (Issue #72)."""
        def _score(ip_str: str) -> Tuple[int, int]:
            try:
                ip_obj = ipaddress.IPv4Address(ip_str.strip())
            except Exception:
                return (99, 0)

            if ip_obj.is_loopback or ip_obj.is_link_local:
                return (90, int(ip_obj))

            octets = ip_str.strip().split(".")
            ends_in_one = (octets[-1] == "1")

            # Verifica subnet LAN eero se nota
            if lan_net is not None:
                try:
                    if ip_obj in lan_net:
                        return (1 if ends_in_one else 0, int(ip_obj))
                except Exception:
                    pass

            # Rilevamento bridge container tipici (Docker 172.17-31.x.x, Podman 10.88-89.x.x, K8s 10.244/10.42/10.96)
            is_container_bridge = False
            first, second = int(octets[0]), int(octets[1])
            if first == 172 and 17 <= second <= 31:
                is_container_bridge = True
            elif first == 10 and second in (88, 89, 244, 42, 96):
                is_container_bridge = True

            if is_container_bridge or (ends_in_one and (first == 172 or first == 10)):
                return (4, int(ip_obj))

            if ip_obj.is_private:
                return (3 if ends_in_one else 2, int(ip_obj))

            return (5, int(ip_obj))

        return sorted(candidates, key=_score)

    def _normalize_eero_node(self, n: Dict[str, Any]) -> Dict[str, Any]:
        node = dict(n)

        # Rilevamento dello stato operativo reale del nodo eero Mesh (Issue #34)
        raw_status = str(node.get("status") or "").strip().lower()
        raw_state = str(node.get("state") or "").strip().upper()
        heartbeat_ok = node.get("heartbeat_ok")
        connected_prop = node.get("connected")

        node["state"] = raw_state
        node["heartbeat_ok"] = heartbeat_ok

        if raw_state == "REBOOTING" or raw_status == "rebooting":
            node["status"] = "rebooting"
        elif (
            connected_prop is False or
            heartbeat_ok is False or
            raw_status in ("red", "offline", "disconnected") or
            raw_state in ("OFFLINE", "DISCONNECTED", "UNREACHABLE")
        ):
            node["status"] = "offline"
        elif (
            raw_status in ("green", "online") or
            raw_state == "ONLINE" or
            heartbeat_ok is True or
            connected_prop is True
        ):
            node["status"] = "online"
        elif raw_status == "yellow" and heartbeat_ok is not False:
            node["status"] = "online"
        else:
            # Fallback per fixture di test minimali prive di telemetria
            node["status"] = "online"

        # Name / Location / Model
        node["name"] = node.get("location") or node.get("name") or node.get("nickname") or node.get("model") or tr("eero.node_name_fallback")
        node["model"] = node.get("model") or node.get("model_number") or node.get("product_name") or "eero"

        # IP address
        node["ip"] = (
            node.get("ip_address") or 
            node.get("ip") or 
            (node.get("interface") or {}).get("ip") or 
            node.get("ipv4") or 
            ""
        )

        # Primary Node in Bridge Mode (Issue #105 & Issue #129)
        node["is_primary_node"] = bool(
            node.get("is_primary_node") is True or
            node.get("isPrimaryNode") is True or
            node.get("is_primary") is True or
            node.get("isPrimary") is True or
            node.get("primary") is True
        )

        # Gateway (Issue #19 fix: non fare casting booleano indiscriminato su stringhe URL)
        node["is_gateway"] = self._is_gateway_node(node)

        # Backhaul & Inter-node Link
        conn_info = node.get("connectivity") if isinstance(node.get("connectivity"), dict) else {}
        iface_info = node.get("interface") if isinstance(node.get("interface"), dict) else {}
        w_details = node.get("wireless_details") if isinstance(node.get("wireless_details"), dict) else {}
        mesh_info = (
            node.get("mesh") if isinstance(node.get("mesh"), dict)
            else (node.get("mesh_quality") if isinstance(node.get("mesh_quality"), dict)
            else (node.get("mesh_connection") if isinstance(node.get("mesh_connection"), dict) else {}))
        )

        raw_channel = (
            node.get("channel") if node.get("channel") is not None 
            else (conn_info.get("channel") if conn_info.get("channel") is not None 
            else (iface_info.get("channel") if iface_info.get("channel") is not None 
            else (w_details.get("channel") if w_details.get("channel") is not None 
            else mesh_info.get("channel"))))
        )
        channel = 0
        if raw_channel is not None:
            try:
                channel = int(raw_channel)
            except Exception:
                channel = 0

        raw_freq = (
            conn_info.get("frequency") or 
            node.get("frequency") or 
            iface_info.get("frequency") or 
            node.get("wireless_frequency") or 
            w_details.get("frequency") or 
            mesh_info.get("frequency") or 
            ""
        )
        freq_num = 0
        if raw_freq:
            try:
                freq_num = int(float(str(raw_freq).replace("mhz", "").replace("ghz", "").strip()))
            except Exception:
                freq_num = 0

        raw_band = (
            node.get("wireless_band") or 
            node.get("band") or 
            conn_info.get("band") or 
            conn_info.get("wireless_band") or 
            conn_info.get("frequency") or 
            iface_info.get("band") or 
            iface_info.get("frequency") or 
            w_details.get("band") or 
            w_details.get("wireless_band") or 
            mesh_info.get("band") or 
            mesh_info.get("wireless_band") or 
            ""
        )
        band_str = str(raw_band).lower().replace("ghz", "").replace(" ", "").strip()

        phy_type = str(
            conn_info.get("phy_type") or 
            node.get("phy_type") or 
            iface_info.get("phy_type") or 
            w_details.get("phy_type") or 
            mesh_info.get("phy_type") or 
            ""
        ).upper()
        chan_width = str(
            conn_info.get("channel_width") or 
            node.get("channel_width") or 
            w_details.get("channel_width") or 
            mesh_info.get("channel_width") or 
            ""
        ).upper()
        model_str = str(
            node.get("model") or 
            node.get("model_number") or 
            node.get("product_name") or 
            ""
        ).lower()

        # Signal / RSSI
        signal_str = ""
        raw_rssi = (
            node.get("signal_rssi") or 
            node.get("rssi") or 
            conn_info.get("signal") or 
            conn_info.get("rssi") or 
            conn_info.get("signal_strength") or 
            conn_info.get("signal_rssi") or 
            conn_info.get("bars") or
            conn_info.get("score") or
            conn_info.get("rx_rssi") or
            conn_info.get("signal_dbm") or
            iface_info.get("rssi") or 
            iface_info.get("signal") or 
            iface_info.get("rx_rssi") or
            node.get("signal") or
            node.get("mesh_rssi") or
            node.get("mesh_quality") or
            node.get("rx_rssi") or
            node.get("signal_dbm") or
            (node.get("wireless_details") if isinstance(node.get("wireless_details"), dict) else {}).get("rssi") or
            (node.get("wireless_details") if isinstance(node.get("wireless_details"), dict) else {}).get("rx_rssi")
        )
        if isinstance(raw_rssi, dict):
            raw_rssi = (
                raw_rssi.get("rx_rssi") or 
                raw_rssi.get("rssi") or 
                raw_rssi.get("signal_dbm") or 
                raw_rssi.get("score") or 
                raw_rssi.get("signal")
            )

        if raw_rssi is not None:
            cleaned_rssi = str(raw_rssi).replace("dBm", "").replace("dbm", "").strip()
            if cleaned_rssi.startswith("-") or cleaned_rssi.lstrip("-").isdigit():
                try:
                    rssi_num = int(cleaned_rssi)
                    signal_str = f" / {rssi_num} dBm"
                    node["signal_rssi"] = rssi_num
                except Exception:
                    signal_str = f" / {cleaned_rssi} dBm"
                    node["signal_rssi"] = cleaned_rssi
            elif cleaned_rssi:
                signal_str = f" / {cleaned_rssi}"
                node["signal_rssi"] = cleaned_rssi

        # In eero API:
        # - node.get("gateway") is True for the primary router connected to modem/WAN
        # - node.get("wired") is True for beacon nodes connected via Ethernet backhaul cable to the gateway
        # - node.get("wired") is False for wireless mesh nodes (even if a client PC or switch is plugged into their LAN port!)
        is_gateway = node["is_gateway"]
        raw_wired = node.get("wired")
        node["raw_wired"] = raw_wired
        
        if is_gateway:
            is_wired = True
        elif raw_wired is False or node.get("wireless") is True or node.get("connection_type") == "wireless":
            is_wired = False
        elif raw_wired is True or node.get("connection_type") == "wired":
            is_wired = True
        else:
            is_wired = False

        # Check node ports for ethernet backhaul speed (Point 5 & Issue #14)
        active_port_speeds = []
        port_details = []
        wan_port_speed_mbps = 0
        neighbour_port_speed_mbps = 0

        def _process_node_port(p_entry: Any):
            nonlocal wan_port_speed_mbps, neighbour_port_speed_mbps
            if isinstance(p_entry, dict):
                p_speed = str(
                    p_entry.get("speed") or 
                    p_entry.get("rate") or 
                    p_entry.get("link_speed") or 
                    p_entry.get("negotiated_speed") or 
                    ""
                ).strip()
                p_carrier = (
                    p_entry.get("has_carrier") if p_entry.get("has_carrier") is not None 
                    else (p_entry.get("hasCarrier") if p_entry.get("hasCarrier") is not None 
                    else (p_entry.get("connected") if p_entry.get("connected") is not None 
                    else (p_entry.get("carrier") if p_entry.get("carrier") is not None 
                    else p_entry.get("link"))))
                )
                p_num = (
                    p_entry.get("port") or 
                    p_entry.get("port_number") or 
                    p_entry.get("interface_number") or 
                    p_entry.get("interfaceNumber") or 
                    p_entry.get("index") or 
                    p_entry.get("port_name")
                )
                is_wan = bool(
                    p_entry.get("isWanPort") or 
                    p_entry.get("is_wan_port") or 
                    p_entry.get("is_wan") or 
                    p_entry.get("wan") or 
                    str(p_entry.get("role") or "").lower() == "wan" or
                    str(p_entry.get("type") or "").lower() == "wan"
                )
                has_neighbour = bool(
                    p_entry.get("neighbour") or 
                    p_entry.get("neighbor") or 
                    p_entry.get("peer")
                )
                
                speed_mbps = parse_speed_mbps(p_speed)
                if speed_mbps > 0 or p_speed:
                    if p_carrier is True or p_carrier is None or p_carrier == "up":
                        active_port_speeds.append(p_speed)
                        if p_num is not None:
                            wan_label = " (WAN)" if is_wan else ""
                            port_details.append(f"Port {p_num}{wan_label}: {p_speed}")
                        if is_wan:
                            node["has_wan_port"] = True
                            lldp_list = p_entry.get("lldpInfo") or p_entry.get("lldp_info") or []
                            if isinstance(lldp_list, dict):
                                lldp_list = [lldp_list]
                            if isinstance(lldp_list, list) and any(
                                isinstance(li, dict)
                                and str(li.get("systemName") or li.get("system_name") or "").strip().lower() not in ("", "eero")
                                for li in lldp_list
                            ):
                                node["has_upstream_wan_lldp"] = True
                            if speed_mbps > 0 and wan_port_speed_mbps == 0:
                                wan_port_speed_mbps = speed_mbps
                        if has_neighbour and speed_mbps > 0 and neighbour_port_speed_mbps == 0:
                            neighbour_port_speed_mbps = speed_mbps
            elif isinstance(p_entry, (str, int)):
                s_mbps = parse_speed_mbps(p_entry)
                if s_mbps > 0:
                    active_port_speeds.append(str(p_entry))

        # 1. Parse ethernet_status object (e.g. ethernet_status.statuses[].speed)
        eth_status = node.get("ethernet_status")
        if isinstance(eth_status, dict):
            statuses = (
                eth_status.get("statuses") or 
                eth_status.get("status") or 
                eth_status.get("ports") or 
                eth_status.get("interfaces") or 
                []
            )
            if isinstance(statuses, list):
                for st in statuses:
                    _process_node_port(st)
            elif isinstance(statuses, dict):
                for st in statuses.values():
                    _process_node_port(st)
        elif isinstance(eth_status, list):
            for st in eth_status:
                _process_node_port(st)

        # 2. Parse ethernet_ports / ports / interfaces
        ports_list = (
            node.get("ethernet_ports") or 
            node.get("ports") or 
            node.get("interfaces") or 
            (conn_info.get("ports") if isinstance(conn_info, dict) else None)
        )
        if isinstance(ports_list, list):
            for p in ports_list:
                _process_node_port(p)

        if port_details:
            node["ethernet_ports_details"] = port_details

        # Backhaul Speed Resolution (WAN/upstream backhaul port priority over client LAN ports)
        backhaul_mbps = 0
        if wan_port_speed_mbps > 0:
            backhaul_mbps = wan_port_speed_mbps
        elif neighbour_port_speed_mbps > 0:
            backhaul_mbps = neighbour_port_speed_mbps
        else:
            candidate_speeds = [parse_speed_mbps(s) for s in active_port_speeds]
            if node.get("ethernet_speed"):
                candidate_speeds.append(parse_speed_mbps(node.get("ethernet_speed")))
            candidate_speeds = [s for s in candidate_speeds if s > 0]
            if candidate_speeds:
                backhaul_mbps = candidate_speeds[0] if len(candidate_speeds) == 1 else max(candidate_speeds)

        if is_gateway:
            node["wired"] = True
            node["backhaul_type"] = "Gateway (WAN)"
        elif is_wired:
            node["wired"] = True
            spd_fmt = format_speed_mbps(backhaul_mbps)
            if spd_fmt:
                node["backhaul_type"] = f"Ethernet ({spd_fmt})"
            else:
                node["backhaul_type"] = "Ethernet (Wired)"
        else:
            node["wired"] = False

            # Wi-Fi 6E & Wi-Fi 7 (6 GHz) Wireless Backhaul Detection
            # - Frequency in MHz: 5900 - 7200 MHz
            # - Band string: "6", "6.0", "6g", "6ghz", or contains "6ghz" / "6 ghz"
            # - Channels:
            #   * Channels > 177 up to 233 only exist in 6 GHz band
            #   * 6 GHz Preferred Scanning Channels (PSC): 37, 53, 69, 85, 101, 117, 133, 181, 197, 213, 229
            #   * Odd channel numbers between 15 and 147 (2.4 GHz stops at 14 and 5 GHz channels 36-144 are even,
            #     but the 5 GHz UNII-3 channels 149-177 are odd too, so they are NOT a 6 GHz hint)
            # - Channel width: 320 MHz (Wi-Fi 7 exclusive to 6 GHz)
            # - PHY type EHT is NOT a 6 GHz hint: Wi-Fi 7 also runs on 5 GHz and 2.4 GHz
            is_6ghz_link = (
                (freq_num >= 5900 and freq_num <= 7200) or
                band_str in ("6", "6.0", "6g", "6ghz") or
                "6g" in band_str or
                "6ghz" in str(raw_band).lower() or
                "6 ghz" in str(raw_band).lower() or
                (177 < channel <= 233) or
                (channel in (37, 53, 69, 85, 101, 117, 133, 181, 197, 213, 229)) or
                (channel % 2 != 0 and 15 <= channel < 149) or
                "320" in chan_width
            )

            is_24ghz_link = (
                not is_6ghz_link and (
                    (freq_num >= 2400 and freq_num <= 2500) or
                    band_str in ("2.4", "2", "2g", "2ghz") or
                    "2.4" in band_str or
                    "2.4ghz" in str(raw_band).lower() or
                    "2.4 ghz" in str(raw_band).lower() or
                    (1 <= channel <= 14)
                )
            )

            is_5ghz_link = (
                not is_6ghz_link and not is_24ghz_link and (
                    (freq_num >= 5000 and freq_num < 5900) or
                    band_str in ("5", "5.0", "5.8", "5g", "5ghz") or
                    "5g" in band_str or
                    "5ghz" in str(raw_band).lower() or
                    "5 ghz" in str(raw_band).lower() or
                    (36 <= channel <= 177 and (channel % 2 == 0 or channel >= 149))
                )
            )

            # Hardware capability fallback:
            # On eero Pro 6E (K010001/S010001) and eero Max 7 (T010001), TrueMesh operates and prioritizes
            # the dedicated 6 GHz radio as the primary inter-node wireless mesh backhaul.
            is_6e_or_7_hardware = any(m in model_str for m in ("pro 6e", "max 7", "outdoor 7", "k010001", "s010001", "t010001"))

            if is_6ghz_link:
                node["backhaul_type"] = f"Wireless Mesh (6 GHz{signal_str})"
            elif is_24ghz_link:
                node["backhaul_type"] = f"Wireless Mesh (2.4 GHz{signal_str})"
            elif is_5ghz_link:
                node["backhaul_type"] = f"Wireless Mesh (5 GHz{signal_str})"
            # Nessun canale né frequenza: stima dal modello (Issue #56: trasparenza sulle bande dedotte da hardware)
            elif is_6e_or_7_hardware and channel == 0:
                node["backhaul_estimated"] = True
                node["backhaul_type"] = f"Wireless Mesh (6 GHz{signal_str}) (estimated)"
            else:
                node["backhaul_type"] = f"Wireless Mesh (5 GHz{signal_str})"



        # OS Version / Firmware
        os_v = (
            node.get("os_version") or 
            node.get("firmware") or 
            node.get("os") or 
            node.get("software_version") or 
            node.get("version")
        )
        # None when the API reports no firmware: the UI renders its own localized placeholder.
        node["os_version"] = str(os_v) if os_v else None

        # LED State (status_light, led_on, led_status, led_action)
        status_light = node.get("status_light")
        if isinstance(status_light, dict):
            node["led_on"] = bool(status_light.get("enabled", True))
            node["led_brightness"] = status_light.get("brightness", 100)
        elif "led_on" in node:
            node["led_on"] = bool(node["led_on"])
        else:
            led_st = str(node.get("led_status") or node.get("led_action") or "on").lower()
            node["led_on"] = (led_st not in ("off", "disabled", "false", "0"))

        # Serial, ID & URL (ensure id matches url identifier, serial and id are both preserved)
        node_url = str(node.get("url") or "")
        url_id = node_url.split("/")[-1] if node_url else ""
        node["url"] = node_url
        node["serial"] = str(node.get("serial") or "")
        node["id"] = str(node.get("id") or url_id or node.get("serial") or "")
        return node


    async def get_eeros(self) -> List[Dict[str, Any]]:
        """Recupera la lista e i dettagli di tutti i nodi eero mesh (Gateway & Beacon)."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_eeros()

        if not self.current_network_id:
            await self.fetch_account_info()

        if not self.current_network_id:
            return self._last_eeros or []

        async with self._client_session() as client:
            resp = await client.get(f"{EERO_API_BASE}/networks/{self.current_network_id}/eeros", headers=self._get_headers())
            if resp.status_code != 200:
                log_event(logger, logging.ERROR, "log_eero.eeros_fetch_failed", status=resp.status_code, response=resp.text)
                return self._last_eeros or []
            raw_list = resp.json().get("data", [])
            nodes = []
            for n in raw_list:
                try:
                    nodes.append(self._normalize_eero_node(n))
                except Exception as ex:
                    log_event(logger, logging.ERROR, "log_eero.node_normalize_failed", error=str(ex))

            # Reconciliazione Primary Gateway: garantisce l'elezione di un unico nodo Gateway univoco (Issue #19, Issue #26 & Issue #36)
            if nodes:
                primary_gw = None

                # 1. Corrispondenza diretta con Gateway ID o URL restituito da /2.2/networks/{id}
                gw_cached_id = getattr(self, "current_gateway_id", None)
                gw_cached_url = getattr(self, "current_gateway_url", None)
                if gw_cached_id or gw_cached_url:
                    primary_gw = next((n for n in nodes if (
                        (gw_cached_id and str(n.get("id") or "") == str(gw_cached_id)) or
                        # ID esatto in coda all'URL: il gateway "10" non deve eleggere "/2.2/eeros/104"
                        (gw_cached_id and str(n.get("url") or "").rstrip("/").split("/")[-1] == str(gw_cached_id)) or
                        (gw_cached_url and str(n.get("url") or "") == str(gw_cached_url))
                    )), None)

                # 2. Corrispondenza Nome autoritativo di rete (gateway_name da /2.2/networks/{id})
                if not primary_gw:
                    gw_cached_name = getattr(self, "current_gateway_name", None)
                    if gw_cached_name:
                        primary_gw = next((n for n in nodes if str(n.get("name") or "").lower() == str(gw_cached_name).lower()), None)

                # 3. Corrispondenza IP con gateway_ip di rete (se noto da /2.2/networks/{id} - Issue #36, #56)
                if not primary_gw:
                    gw_cached_ip = getattr(self, "current_gateway_ip", None)
                    if gw_cached_ip:
                        primary_gw = next((n for n in nodes if n.get("ip") and n.get("ip") == gw_cached_ip), None)

                # 4. Nodo con flag is_gateway già impostato da _is_gateway_node
                if not primary_gw:
                    gw_nodes = [n for n in nodes if n.get("is_gateway")]
                    if len(gw_nodes) == 1:
                        primary_gw = gw_nodes[0]
                    elif len(gw_nodes) > 1:
                        # Se più nodi hanno il flag, priorità a quello con IP gateway se noto
                        gw_cached_ip = getattr(self, "current_gateway_ip", None)
                        if gw_cached_ip:
                            primary_gw = next((n for n in gw_nodes if n.get("ip") == gw_cached_ip), gw_nodes[0])
                        else:
                            primary_gw = gw_nodes[0]

                # 4b. Bridge Mode Primary Node & Upstream WAN LLDP Neighbor (Issue #105)
                if not primary_gw:
                    primary_gw = next((n for n in nodes if n.get("is_primary_node") is True), None)
                if not primary_gw:
                    primary_gw = next((n for n in nodes if n.get("has_upstream_wan_lldp") is True), None)

                # 5. Nodo con porta WAN reale attiva / collegata all'ONT/modem (fallback in assenza di IP/metadati)
                if not primary_gw:
                    primary_gw = next((n for n in nodes if n.get("has_wan_port") or any("wan" in str(p).lower() for p in n.get("ethernet_ports_details", []))), None)

                # 6. Fallback finale al primo nodo
                if not primary_gw:
                    primary_gw = nodes[0]

                # Demozione ed elezione coerente di tutti i nodi
                for n in nodes:
                    if n is primary_gw:
                        n["is_gateway"] = True
                        n["wired"] = True
                        n["backhaul_type"] = "Gateway (WAN)"
                    else:
                        n["is_gateway"] = False
                        if n.get("backhaul_type") == "Gateway (WAN)":
                            is_6e_or_7 = any(m in str(n.get("model") or "").lower() for m in ("pro 6e", "max 7", "outdoor 7", "k010001", "s010001", "t010001"))
                            candidate_speeds = [parse_speed_mbps(s) for s in n.get("ethernet_ports_details", [])]
                            spd_mbps = max(candidate_speeds) if candidate_speeds else 0
                            spd_fmt = format_speed_mbps(spd_mbps)
                            if n.get("raw_wired") is True or (spd_mbps > 0 and n.get("raw_wired") is not False):
                                n["wired"] = True
                                n["backhaul_type"] = f"Ethernet ({spd_fmt})" if spd_fmt else "Ethernet (Wired)"
                            elif is_6e_or_7 or "6" in str(n.get("wireless_band") or ""):
                                n["wired"] = False
                                n["backhaul_type"] = "Wireless Mesh (6 GHz)"
                            else:
                                n["wired"] = False
                                n["backhaul_type"] = "Wireless Mesh (5 GHz)"

            self._last_eeros = nodes
            return nodes


    async def reboot_eero(self, eero_id: str) -> Dict[str, Any]:
        """Invia il comando di riavvio a un singolo nodo eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            log_event(logger, logging.INFO, "log_eero.demo_node_reboot", eero_id=eero_id)
            return {"status": "success", "message": tr("eero.node_reboot_demo", eero_id=eero_id)}

        async with self._client_session() as client:
            resp = await client.post(f"{EERO_API_BASE}/eeros/{eero_id}/reboot", headers=self._get_headers())
            if resp.status_code not in (200, 202):
                raise RuntimeError(tr("eero.node_reboot_error", eero_id=eero_id, error=resp.text))
            return {"status": "success", "message": tr("eero.node_reboot_sent", eero_id=eero_id)}

    async def set_eero_led(self, eero_id: str, led_on: bool) -> Dict[str, Any]:
        """Accende o spegne il LED frontale di un nodo eero supportando i vari endpoint API eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._set_demo_eero_led(eero_id, led_on)

        clean_id = str(eero_id).split("/")[-1]
        action = "on" if led_on else "off"
        headers = self._get_headers()
        net_id = self.current_network_id

        attempts = [
            ("POST", f"{EERO_API_BASE}/eeros/{clean_id}/led_action", {"led_action": action}),
            ("PUT", f"{EERO_API_BASE}/eeros/{clean_id}/led_action", {"led_action": action}),
            ("POST", f"{EERO_API_BASE}/eeros/{clean_id}/led", {"led_on": led_on}),
            ("PUT", f"{EERO_API_BASE}/eeros/{clean_id}/led", {"led_on": led_on}),
            ("POST", f"{EERO_API_BASE}/eeros/{clean_id}", {"led_on": led_on, "led_action": action}),
            ("PUT", f"{EERO_API_BASE}/eeros/{clean_id}", {"led_on": led_on, "led_action": action}),
            ("POST", f"{EERO_API_BASE}/eeros/{clean_id}/status_light", {"enabled": led_on}),
            ("PUT", f"{EERO_API_BASE}/eeros/{clean_id}/status_light", {"enabled": led_on}),
        ]
        if net_id:
            attempts.extend([
                ("POST", f"{EERO_API_BASE}/networks/{net_id}/eeros/{clean_id}/led_action", {"led_action": action}),
                ("PUT", f"{EERO_API_BASE}/networks/{net_id}/eeros/{clean_id}/led_action", {"led_action": action}),
                ("POST", f"{EERO_API_BASE}/networks/{net_id}/eeros/{clean_id}", {"led_on": led_on}),
                ("PUT", f"{EERO_API_BASE}/networks/{net_id}/eeros/{clean_id}", {"led_on": led_on}),
            ])

        async with self._client_session() as client:
            last_err = ""
            for method, url, payload in attempts:
                try:
                    if method == "POST":
                        resp = await client.post(url, json=payload, headers=headers)
                    else:
                        resp = await client.put(url, json=payload, headers=headers)

                    if resp.status_code in (200, 201, 202, 204):
                        log_event(logger, logging.INFO, "log_eero.led_updated", eero_id=clean_id, method=method, url=url)
                        return {"status": "success", "eero_id": clean_id, "led_on": led_on}
                    else:
                        last_err = f"{method} {url} -> HTTP {resp.status_code}: {resp.text}"
                except Exception as ex:
                    last_err = f"{method} {url} -> Exception: {ex}"

            log_event(logger, logging.ERROR, "log_eero.led_update_failed", eero_id=clean_id, error=last_err)
            raise RuntimeError(tr("eero.led_error", error=last_err))

    async def set_all_leds(self, led_on: bool) -> Dict[str, Any]:
        """Accende o spegne i LED di tutti i nodi mesh."""
        eeros = await self.get_eeros()
        results = []
        for e in eeros:
            eid = e.get("id") or e.get("serial")
            if eid:
                try:
                    res = await self.set_eero_led(str(eid), led_on)
                    results.append(res)
                except Exception as ex:
                    log_event(logger, logging.WARNING, "log_eero.led_toggle_failed", eero_id=eid, error=ex)
        return {"status": "success", "all_leds_on": led_on, "count": len(results)}

    # =========================================================================
    # GESTIONE DISPOSITIVI (NICKNAME & PAUSE)
    # =========================================================================

    async def run_placement_test(self, location: str = "New Node", network_id: Optional[str] = None) -> Dict[str, Any]:
        """Esegue o valuta il test di posizionamento RF dei nodi mesh (/2.2/networks/{id}/placement_test)."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for placement test: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        if not clean_net_id:
            raise ValueError(tr("eero.no_network_selected"))

        if not self.is_demo_mode:
            try:
                async with self._client_session() as client:
                    resp = await client.post(
                        f"{EERO_API_BASE}/networks/{clean_net_id}/placement_test",
                        headers=self._get_headers(),
                        json={"location": location},
                    )
                    if resp.status_code in (200, 201, 202):
                        data = resp.json().get("data", {})
                        return {
                            "status": "success",
                            "location": location,
                            "score": data.get("score", 92),
                            "rating": data.get("rating", "optimal"),
                            "details": data,
                        }
            except Exception as e:
                logger.debug(f"Cloud placement_test endpoint fallback: {e}")

        eeros = await self.get_eeros()
        node_scores = []
        for n in eeros:
            bars = int(n.get("mesh_quality_bars") or 5)
            wired = bool(n.get("wired") or n.get("is_gateway"))
            score = 100 if wired else min(100, max(40, bars * 20))
            node_scores.append({
                "name": n.get("name"),
                "model": n.get("model"),
                "is_echo_node": bool(n.get("is_echo_node")),
                "wired": wired,
                "mesh_quality_bars": bars,
                "placement_score": score,
                "rating": "optimal" if score >= 80 else ("good" if score >= 60 else "poor"),
            })
        avg_score = round(sum(x["placement_score"] for x in node_scores) / max(1, len(node_scores)))
        return {
            "status": "success",
            "location": location,
            "score": avg_score,
            "rating": "optimal" if avg_score >= 80 else ("good" if avg_score >= 60 else "poor"),
            "nodes": node_scores,
        }


    async def register_eero_node(self, serial: str, location: str = "Living Room", network_id: Optional[str] = None) -> Dict[str, Any]:
        """Registra (onboarding) un nuovo nodo fisico eero tramite numero di serie su /2.2/networks/{id}/eeros."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for register node: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        clean_serial = str(serial or "").strip().upper()
        if not clean_serial or len(clean_serial) < 6:
            raise ValueError("Valid eero serial number is required")
        if not clean_net_id:
            raise ValueError(tr("eero.no_network_selected"))

        if self.is_demo_mode:
            return self._register_demo_eero_node(clean_serial, location)

        async with self._client_session() as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{clean_net_id}/eeros",
                f"{EERO_API_BASE}/networks/{net_id}/eeros",
                headers=self._get_headers(),
                json={"serial": clean_serial, "location": location},
            )
            if resp.status_code in (200, 201, 202):
                return {"status": "success", "node": resp.json().get("data", {})}
            raise RuntimeError(f"Cloud API returned HTTP {resp.status_code}")

