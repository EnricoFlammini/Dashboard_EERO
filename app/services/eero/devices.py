"""
Device management, device normalization, profiles, aliases, pause/resume, and bandwidth data usage.
"""
from typing import Dict, Any, List, Optional, Tuple
import ipaddress
import logging
import re
import time
from app.config import settings
from app.i18n import log_event, tr, tr_all
from app.services.eero.const import (
    EERO_API_BASE,
    IPV6_ULA_NET,
    _IPV6_ULA_NET,
    parse_speed_mbps,
    format_speed_mbps,
    map_eero_device_type,
)

logger = logging.getLogger(__name__)


class EeroDevicesMixin:
    """Metodi per dispositivi connessi, normalizzazione telemetria, profili famiglia e consumo dati."""

    def _normalize_device(self, d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            dev = dict(d)
            
            # MAC Address
            mac_val = dev.get("mac") or dev.get("mac_address")
            if not mac_val and isinstance(dev.get("interface"), dict):
                mac_val = dev["interface"].get("mac")
            dev["mac"] = str(mac_val).strip() if mac_val else ""
            dev["mac_address"] = dev["mac"]

            # ID & URL
            dev_id = str(dev.get("id") or (dev.get("url", "").split("/")[-1] if dev.get("url") else "") or dev.get("mac") or "")
            dev["id"] = dev_id
            dev["url"] = dev.get("url") or (f"/2.2/devices/{dev_id}" if dev_id else "")
            
            # Keep the name the device itself reports before the display name overwrites it
            dev["reported_hostname"] = dev.get("hostname") or ""

            # Hostname & Display Name
            dev["hostname"] = dev.get("nickname") or dev.get("hostname") or dev.get("display_name") or dev.get("device_name") or dev.get("name") or dev.get("mac") or tr("eero.device_name_fallback")

            # Helper to extract clean IP string from str or dict (eero can return dicts like {'address': 'fe80::...', 'scope': 'link'})
            def _clean_ip(item: Any) -> Optional[str]:
                if not item:
                    return None
                if isinstance(item, str):
                    s = item.strip()
                    if "/" in s:
                        s = s.split("/")[0].strip()
                    if "%" in s:
                        s = s.split("%")[0].strip()
                    return s if s else None
                if isinstance(item, dict):
                    addr = item.get("address") or item.get("ip") or item.get("ipv6") or item.get("ipv4")
                    if addr and isinstance(addr, str):
                        s = addr.strip()
                        if "/" in s:
                            s = s.split("/")[0].strip()
                        if "%" in s:
                            s = s.split("%")[0].strip()
                        return s if s else None
                return None

            # IP Address Extraction (IPv4 and IPv6)
            all_ips_raw = []
            if isinstance(dev.get("ips"), list):
                all_ips_raw.extend(dev["ips"])
            if isinstance(dev.get("ip_addresses"), list):
                all_ips_raw.extend(dev["ip_addresses"])
            if isinstance(dev.get("ipv6_addresses"), list):
                all_ips_raw.extend(dev["ipv6_addresses"])
            if isinstance(dev.get("ipv6_link_local"), list):
                all_ips_raw.extend(dev["ipv6_link_local"])
            if isinstance(dev.get("ipv6_all"), list):
                all_ips_raw.extend(dev["ipv6_all"])
            if isinstance(dev.get("interface"), dict):
                iface_ips = dev["interface"].get("ips") or []
                if isinstance(iface_ips, list):
                    all_ips_raw.extend(iface_ips)
                if dev["interface"].get("ip"):
                    all_ips_raw.append(dev["interface"]["ip"])
                if dev["interface"].get("ipv6"):
                    all_ips_raw.append(dev["interface"]["ipv6"])

            if dev.get("ip"):
                all_ips_raw.append(dev["ip"])
            if dev.get("ipv4"):
                all_ips_raw.append(dev["ipv4"])
            if dev.get("ipv6"):
                all_ips_raw.append(dev["ipv6"])

            ipv4_candidates = []
            ipv6_gua = []
            ipv6_ula = []
            ipv6_link_local = []
            ipv6_details = []

            for raw_item in all_ips_raw:
                ip_str = _clean_ip(raw_item)
                if not ip_str:
                    continue
                # IPv4 check (must contain dot, no colon, exclude 169.254.x.x link-local APIPA)
                if "." in ip_str and ":" not in ip_str and not ip_str.startswith("169.254."):
                    if ip_str not in ipv4_candidates:
                        ipv4_candidates.append(ip_str)
                # IPv6 check (must contain colon, exclude loopback ::1 or unspecified ::)
                elif ":" in ip_str and ip_str.strip() not in ("::", "::1", "0:0:0:0:0:0:0:1"):
                    # Classificazione RFC 4291 / RFC 4193 (Issue #57)
                    addr_type = "GUA"
                    addr_scope = "global"
                    is_ll = False
                    is_ula = False

                    try:
                        v6_obj = ipaddress.IPv6Address(ip_str)
                        if v6_obj.is_loopback or v6_obj.is_unspecified:
                            continue
                        if v6_obj.is_link_local:
                            is_ll = True
                        elif v6_obj in _IPV6_ULA_NET:
                            is_ula = True
                    except ValueError:
                        # Fallback parsing stringa se indirizzo non normalizzato
                        lower_v6 = ip_str.lower()
                        if lower_v6.startswith(("fe80:", "fe90:", "fea0:", "feb0:")):
                            is_ll = True
                        elif lower_v6.startswith(("fc", "fd")):
                            is_ula = True

                    if is_ll:
                        addr_type = "Link-Local"
                        addr_scope = "link"
                        if ip_str not in ipv6_link_local:
                            ipv6_link_local.append(ip_str)
                    elif is_ula:
                        addr_type = "ULA"
                        addr_scope = "local"
                        if ip_str not in ipv6_ula:
                            ipv6_ula.append(ip_str)
                    else:
                        addr_type = "GUA"
                        addr_scope = "global"
                        if ip_str not in ipv6_gua:
                            ipv6_gua.append(ip_str)

                    detail_entry = {"address": ip_str, "type": addr_type, "scope": addr_scope}
                    if not any(d["address"] == ip_str for d in ipv6_details):
                        ipv6_details.append(detail_entry)

            # Prioritizzazione intelligente candidati IPv4 (Issue #72)
            lan_net = self._get_lan_network()
            sorted_v4 = self._sort_ipv4_candidates(ipv4_candidates, lan_net)

            # Se il dispositivo ha una prenotazione o static IP configurato, prioritizzalo se presente
            static_pref = dev.get("static_ip") or (dev.get("reservation") or {}).get("ip")
            if static_pref and str(static_pref).strip() in sorted_v4:
                pref_clean = str(static_pref).strip()
                sorted_v4.remove(pref_clean)
                sorted_v4.insert(0, pref_clean)

            dev["ipv4_candidates"] = sorted_v4
            raw_ip = sorted_v4[0] if sorted_v4 else (dev.get("ip") if isinstance(dev.get("ip"), str) else None)
            dev["ip"] = str(raw_ip).strip() if raw_ip else None

            # Struttura completa IPv6 (Issue #57)
            dev["ipv6_gua"] = ipv6_gua
            dev["ipv6_ula"] = ipv6_ula
            dev["ipv6_link_local"] = ipv6_link_local
            dev["ipv6_details"] = ipv6_details

            # Indirizzi routabili (GUA + ULA) per propagazione verso AdGuard Home e DNS locale
            routable_v6 = ipv6_gua + ipv6_ula
            dev["ipv6_addresses"] = routable_v6
            dev["ipv6_all"] = routable_v6 + ipv6_link_local

            # Indirizzo IPv6 primario (priorità GUA > ULA > Link-Local)
            if ipv6_gua:
                dev["ipv6"] = ipv6_gua[0]
            elif ipv6_ula:
                dev["ipv6"] = ipv6_ula[0]
            elif ipv6_link_local:
                dev["ipv6"] = ipv6_link_local[0]
            else:
                dev["ipv6"] = None

            # Connection Status (Online / Offline / Paused)
            conn_val = dev.get("connected")
            if conn_val is None and isinstance(dev.get("connectivity"), dict):
                conn_val = dev["connectivity"].get("connected")
            if conn_val is None:
                conn_val = (dev.get("status") == "connected")
            dev["connected"] = bool(conn_val)

            # Channel & Frequency Band extraction (Wi-Fi 6E/7 6 GHz, 5 GHz, 2.4 GHz, Ethernet)
            conn_dict = dev.get("connectivity") if isinstance(dev.get("connectivity"), dict) else {}
            iface_dict = dev.get("interface") if isinstance(dev.get("interface"), dict) else {}

            raw_channel = (
                dev.get("channel") if dev.get("channel") is not None 
                else (conn_dict.get("channel") if conn_dict.get("channel") is not None 
                else iface_dict.get("channel"))
            )
            channel = 0
            if raw_channel is not None:
                try:
                    channel = int(raw_channel)
                except Exception:
                    channel = 0

            raw_freq = (
                conn_dict.get("frequency") or 
                dev.get("frequency") or 
                iface_dict.get("frequency") or 
                dev.get("wireless_frequency") or 
                ""
            )
            freq_num = 0
            if raw_freq is not None:
                try:
                    freq_num = int(float(str(raw_freq).replace("mhz", "").replace("ghz", "").strip()))
                except Exception:
                    freq_num = 0

            raw_band = (
                dev.get("band") or 
                dev.get("wireless_band") or 
                conn_dict.get("band") or 
                conn_dict.get("frequency") or 
                iface_dict.get("band") or 
                iface_dict.get("frequency") or 
                ""
            )
            band_str = str(raw_band).lower().replace("ghz", "").replace(" ", "").strip()
            phy_type = str(conn_dict.get("phy_type") or dev.get("phy_type") or iface_dict.get("phy_type") or "").upper()
            chan_width = str(conn_dict.get("channel_width") or dev.get("channel_width") or "").upper()
            dev["phy_type"] = phy_type or None
            dev["channel_width"] = chan_width or None

            # Check for wired ethernet status in connectivity / interface (Issue #14)
            eth_status = conn_dict.get("ethernet_status") or dev.get("ethernet_status") or iface_dict.get("ethernet_status")
            eth_speed_cand = []
            eth_carrier_detected = False

            if isinstance(eth_status, dict):
                carrier = (
                    eth_status.get("has_carrier") if eth_status.get("has_carrier") is not None 
                    else (eth_status.get("hasCarrier") if eth_status.get("hasCarrier") is not None 
                    else (eth_status.get("connected") if eth_status.get("connected") is not None 
                    else eth_status.get("carrier")))
                )
                if carrier is True:
                    eth_carrier_detected = True
                sp = (
                    eth_status.get("speed") or 
                    eth_status.get("rate") or 
                    eth_status.get("link_speed") or 
                    eth_status.get("negotiated_speed")
                )
                if sp and carrier is not False and parse_speed_mbps(sp) > 0:
                    eth_speed_cand.append(sp)
            elif isinstance(eth_status, list):
                for st in eth_status:
                    if isinstance(st, dict):
                        carrier = (
                            st.get("has_carrier") if st.get("has_carrier") is not None 
                            else (st.get("hasCarrier") if st.get("hasCarrier") is not None 
                            else (st.get("connected") if st.get("connected") is not None 
                            else st.get("carrier")))
                        )
                        if carrier is True:
                            eth_carrier_detected = True
                        sp = st.get("speed") or st.get("rate") or st.get("link_speed")
                        if sp and carrier is not False and parse_speed_mbps(sp) > 0:
                            eth_speed_cand.append(sp)

            is_wired = (
                eth_carrier_detected or 
                len(eth_speed_cand) > 0 or 
                dev.get("connection_type") == "wired" or 
                dev.get("wired") is True or 
                dev.get("wireless") is False
            )
            if is_wired:
                dev["wireless"] = False
                dev["connection_type"] = "wired"
                dev["frequency_band"] = "Ethernet"
                dev["wireless_band"] = "Ethernet"
            else:
                dev["wireless"] = True
                dev["connection_type"] = "wireless"
                
                # 1. 6 GHz Wi-Fi 6E / Wi-Fi 7 (Frequency 5900-7200 MHz, explicit 6GHz, 320MHz width,
                #    or an odd channel 15-147 that only exists in 6 GHz). EHT alone is not a 6 GHz hint:
                #    Wi-Fi 7 clients also connect on 5 GHz and 2.4 GHz.
                if (
                    (freq_num >= 5900 and freq_num <= 7200) or 
                    band_str in ("6", "6.0", "6g", "6ghz") or 
                    "6g" in band_str or 
                    "320" in chan_width or 
                    (channel % 2 != 0 and 15 <= channel < 149)
                ):
                    dev["frequency_band"] = "6 GHz"
                    dev["wireless_band"] = "6GHz"
                # 2. 2.4 GHz
                elif (
                    (freq_num >= 2400 and freq_num <= 2500) or 
                    band_str in ("2.4", "2", "2g", "2.4g") or 
                    (channel >= 1 and channel <= 14 and freq_num == 0 and band_str == "")
                ):
                    dev["frequency_band"] = "2.4 GHz"
                    dev["wireless_band"] = "2.4GHz"
                # 3. 5 GHz
                elif (
                    (freq_num >= 5000 and freq_num < 5900) or 
                    band_str in ("5", "5.0", "5g", "5ghz", "5.8") or 
                    (channel >= 32 and channel <= 177)
                ):
                    dev["frequency_band"] = "5 GHz"
                    dev["wireless_band"] = "5GHz"
                else:
                    if channel > 0 and channel <= 14:
                        dev["frequency_band"] = "2.4 GHz"
                        dev["wireless_band"] = "2.4GHz"
                    elif channel >= 32 and channel <= 177:
                        dev["frequency_band"] = "5 GHz"
                        dev["wireless_band"] = "5GHz"
                    elif channel > 177:
                        dev["frequency_band"] = "6 GHz"
                        dev["wireless_band"] = "6GHz"
                    else:
                        dev["frequency_band"] = "5 GHz"
                        dev["wireless_band"] = "5GHz"

            dev["channel"] = channel if channel > 0 else (raw_channel if raw_channel else None)

            # Signal RSSI (Issue #110: normalizzazione robusta di stringhe "-78 dBm", float, dict e signal_avg)
            def _parse_rssi_dbm(val: Any) -> Optional[int]:
                if val is None or isinstance(val, bool):
                    return None
                if isinstance(val, (int, float)):
                    iv = int(round(float(val)))
                    return iv if -120 <= iv < 0 else None
                if isinstance(val, dict):
                    for k in ("rx_rssi", "rssi", "signal_dbm", "signal_avg", "signal", "signal_strength", "dbm", "rx_rate_info", "tx_rate_info"):
                        parsed = _parse_rssi_dbm(val.get(k))
                        if parsed is not None:
                            return parsed
                    return None
                s_val = str(val).replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
                m = re.search(r"-\s*(\d+(?:\.\d+)?)", s_val)
                if m:
                    try:
                        iv = -int(round(float(m.group(1))))
                        return iv if -120 <= iv < 0 else None
                    except Exception:
                        return None
                return None

            rssi_parsed: Optional[int] = None
            for rssi_cand in (
                dev.get("signal_rssi"),
                dev.get("rssi"),
                dev.get("rx_rssi"),
                dev.get("signal_dbm"),
                dev.get("signal"),
                dev.get("signal_avg"),
                dev.get("signal_strength"),
                conn_dict.get("signal"),
                conn_dict.get("signal_avg"),
                conn_dict.get("signal_strength"),
                conn_dict.get("rx_rssi"),
                conn_dict.get("rssi"),
                conn_dict.get("signal_dbm"),
                conn_dict.get("rx_rate_info"),
                conn_dict.get("tx_rate_info"),
                iface_dict.get("signal"),
                iface_dict.get("rssi"),
                iface_dict.get("rx_rssi"),
                dev.get("wireless_details"),
            ):
                rssi_parsed = _parse_rssi_dbm(rssi_cand)
                if rssi_parsed is not None:
                    break
            # Nessun valore inventato: senza segnale dal cloud resta None (nessun campione nello storico RSSI)
            dev["signal_rssi"] = rssi_parsed

            # Ethernet Speed extraction (Point 3 & Issue #14)
            eth_speed_str = ""
            raw_speed_cand = eth_speed_cand + [
                dev.get("ethernet_speed"),
                dev.get("negotiated_speed"),
                dev.get("speed"),
                iface_dict.get("speed"),
                iface_dict.get("negotiated_speed"),
                conn_dict.get("speed"),
                conn_dict.get("negotiated_speed"),
                conn_dict.get("rate"),
                conn_dict.get("bitrate"),
                conn_dict.get("rx_bitrate"),
                dev.get("bitrate")
            ]
            for s in raw_speed_cand:
                if s is not None:
                    mbps = parse_speed_mbps(s)
                    if mbps > 0:
                        eth_speed_str = format_speed_mbps(mbps)
                        break

            dev["ethernet_speed"] = eth_speed_str if eth_speed_str else ""

            # Wireless PHY Link Rate extraction (Point 6)
            phy_rate = dev.get("rx_bitrate") or dev.get("tx_bitrate") or dev.get("bitrate") or conn_dict.get("rx_bitrate") or conn_dict.get("tx_bitrate") or conn_dict.get("bitrate") or conn_dict.get("rate") or iface_dict.get("bitrate")
            if phy_rate:
                phy_str = str(phy_rate).strip()
                if phy_str.isdigit():
                    num = int(phy_str)
                    if num > 1000000:
                        dev["phy_rate"] = f"{num // 1000000} Mbps"
                    elif num > 1000:
                        dev["phy_rate"] = f"{num // 1000} Mbps"
                    else:
                        dev["phy_rate"] = f"{num} Mbps"
                else:
                    dev["phy_rate"] = phy_str
            else:
                dev["phy_rate"] = None

            # Device Type, Category & Default Icon mapping (Issue #13)
            raw_dev_type = (
                dev.get("device_type") or 
                dev.get("device_type_custom") or 
                dev.get("custom_device_type") or 
                dev.get("type") or 
                dev.get("category") or 
                dev.get("device_category") or 
                dev.get("icon") or 
                (conn_dict.get("device_type") if isinstance(conn_dict, dict) else None) or
                ""
            )
            def_cat, def_icon = map_eero_device_type(raw_dev_type, dev.get("model") or dev.get("model_name") or dev.get("hostname") or dev.get("nickname"))
            dev["device_type"] = raw_dev_type
            dev["default_category"] = def_cat
            dev["default_icon"] = def_icon
            dev["category"] = def_cat
            dev["custom_icon"] = def_icon

            # Source / Connected eero (Robust multi-source resolution across all eero models and firmware versions)
            c_id = ""
            c_name = ""
            c_url = ""
            c_is_proxied = False

            def _extract_source_candidate(src: Any):
                nonlocal c_id, c_name, c_url, c_is_proxied
                if isinstance(src, dict):
                    u = str(src.get("url") or "")
                    if u:
                        c_url = u
                        c_id = u.split("/")[-1]
                    if not c_id:
                        c_id = str(src.get("id") or src.get("serial") or "")
                    c_name = str(src.get("location") or src.get("name") or src.get("nickname") or "")
                    if src.get("is_proxied_node") or src.get("isProxiedNode"):
                        c_is_proxied = True
                elif isinstance(src, str) and src:
                    if "/" in src:
                        c_url = src
                        c_id = src.split("/")[-1]
                    else:
                        c_id = src

            for src_cand in [
                dev.get("source"),
                dev.get("eero"),
                dev.get("parent"),
                (dev.get("connectivity") or {}).get("source") if isinstance(dev.get("connectivity"), dict) else None,
                (dev.get("connectivity") or {}).get("eero") if isinstance(dev.get("connectivity"), dict) else None,
                (dev.get("connectivity") or {}).get("parent") if isinstance(dev.get("connectivity"), dict) else None,
                (dev.get("interface") or {}).get("source") if isinstance(dev.get("interface"), dict) else None,
            ]:
                if src_cand:
                    _extract_source_candidate(src_cand)
                    if c_id or c_name:
                        break

            dev["connected_eero_id"] = c_id
            dev["connected_eero_name"] = c_name
            dev["connected_eero_url"] = c_url
            dev["connected_to_proxied_node"] = c_is_proxied
            dev["is_proxied_node"] = bool(
                dev.get("is_proxied_node")
                or dev.get("isProxiedNode")
                or dev.get("is_proxy_node")
                or dev.get("isProxyNode")
            )

            # Se il dispositivo è un Echo o nodo extender Built-in con telemetria Wi-Fi attiva,
            # assicura lo stato 'connected' anche se il cloud eero segnala connected: false nel payload (Issue #135)
            if not dev.get("connected"):
                is_echo_or_proxied = (
                    dev.get("is_proxied_node")
                    or dev.get("connected_to_proxied_node")
                    or "echo" in str(dev.get("model") or "").lower()
                    or "echo" in str(dev.get("nickname") or dev.get("hostname") or dev.get("name") or "").lower()
                )
                if is_echo_or_proxied and (
                    (dev.get("signal_rssi") is not None and dev.get("connected_eero_name"))
                    or (dev.get("channel") and dev.get("connected_eero_name"))
                ):
                    dev["connected"] = True

            # Usage / Throughput rates (STRICT REAL DATA ONLY)
            usage = dev.get("usage")
            down_rate = float(dev.get("download_rate_mbps") or dev.get("down_mbps") or dev.get("down_rate") or 0.0)
            up_rate = float(dev.get("upload_rate_mbps") or dev.get("up_mbps") or dev.get("up_rate") or 0.0)
            rx_b = float(dev.get("rx_bytes") or dev.get("bytes_received") or 0.0)
            tx_b = float(dev.get("tx_bytes") or dev.get("bytes_transmitted") or 0.0)

            # Controllo su dizionari annidati (connectivity, interface, ethernet_status)
            if rx_b == 0.0:
                rx_b = float(
                    conn_dict.get("rx_bytes") or 
                    conn_dict.get("bytes_received") or 
                    iface_dict.get("rx_bytes") or 
                    iface_dict.get("bytes_received") or 
                    (eth_status.get("rx_bytes") if isinstance(eth_status, dict) else 0.0) or
                    0.0
                )
            if tx_b == 0.0:
                tx_b = float(
                    conn_dict.get("tx_bytes") or 
                    conn_dict.get("bytes_transmitted") or 
                    iface_dict.get("tx_bytes") or 
                    iface_dict.get("bytes_transmitted") or 
                    (eth_status.get("tx_bytes") if isinstance(eth_status, dict) else 0.0) or
                    0.0
                )

            if isinstance(usage, dict):
                try:
                    if usage.get("down_mbps") is not None:
                        down_rate = float(usage["down_mbps"])
                    elif usage.get("download_mbps") is not None:
                        down_rate = float(usage["download_mbps"])
                    elif usage.get("down_kbps") is not None:
                        down_rate = float(usage["down_kbps"]) / 1000.0
                    elif usage.get("down") is not None:
                        d_val = float(usage["down"])
                        if d_val > 10000:
                            down_rate = (d_val * 8.0) / 1_000_000.0
                        elif d_val > 100:
                            down_rate = (d_val * 8.0) / 1000.0
                        else:
                            down_rate = d_val
                except Exception:
                    pass

                try:
                    if usage.get("up_mbps") is not None:
                        up_rate = float(usage["up_mbps"])
                    elif usage.get("upload_mbps") is not None:
                        up_rate = float(usage["upload_mbps"])
                    elif usage.get("up_kbps") is not None:
                        up_rate = float(usage["up_kbps"]) / 1000.0
                    elif usage.get("up") is not None:
                        u_val = float(usage["up"])
                        if u_val > 10000:
                            up_rate = (u_val * 8.0) / 1_000_000.0
                        elif u_val > 100:
                            up_rate = (u_val * 8.0) / 1000.0
                        else:
                            up_rate = u_val
                except Exception:
                    pass

                try:
                    rx_u = float(usage.get("rx_bytes") or usage.get("bytes_received") or 0.0)
                    if rx_u > 0.0:
                        rx_b = rx_u
                except Exception:
                    pass

                try:
                    tx_u = float(usage.get("tx_bytes") or usage.get("bytes_transmitted") or 0.0)
                    if tx_u > 0.0:
                        tx_b = tx_u
                except Exception:
                    pass
            elif isinstance(usage, (int, float)):
                if float(usage) > 0.0:
                    rx_b = float(usage)
            
            # Packet Stats & Real Hardware Cumulative Counters (Uncensored by eero Cloud)
            conn_info = dev.get("connectivity") or {}
            pkt_stats = conn_info.get("packet_stats") or (dev.get("interface") or {}).get("packet_stats") or {}
            rx_pkts = int(pkt_stats.get("rx_packets") or 0)
            tx_pkts = int(pkt_stats.get("tx_packets") or 0)
            total_pkts = int(pkt_stats.get("total_packets") or (rx_pkts + tx_pkts))

            dev["rx_packets"] = rx_pkts
            dev["tx_packets"] = tx_pkts
            dev["total_packets"] = total_pkts

            dev["download_rate_mbps"] = round(float(down_rate), 2)
            dev["upload_rate_mbps"] = round(float(up_rate), 2)
            dev["rx_rate"] = dev["download_rate_mbps"]
            dev["tx_rate"] = dev["upload_rate_mbps"]
            dev["rx_bytes"] = rx_b
            dev["tx_bytes"] = tx_b

            is_paused_val = bool(
                dev.get("paused") is True or
                dev.get("is_paused") is True or
                dev.get("blacklisted") is True or
                str(dev.get("status", "")).lower() == "paused" or
                (isinstance(dev.get("profile"), dict) and dev["profile"].get("paused") is True)
            )
            dev["paused"] = is_paused_val
            dev["is_paused"] = is_paused_val
            return dev
        except Exception as ex:
            log_event(logger, logging.ERROR, "log_eero.device_normalize_failed", error=str(ex))
            return dict(d)

    # =========================================================================
    # RECUPERO DATI RETE & MESH
    # =========================================================================

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Recupera l'elenco dei dispositivi connessi/noti e il loro stato di banda."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_devices()

        if not self.current_network_id:
            await self.fetch_account_info()

        # Sessione reale senza rete risolta: mai dispositivi demo (finirebbero in notifiche, storico e sync DNS)
        if not self.current_network_id:
            return []

        raw_list = []
        async with self._client_session() as client:
            try:
                resp = await client.get(f"{EERO_API_BASE}/networks/{self.current_network_id}/devices", headers=self._get_headers())
                if resp.status_code == 200:
                    json_data = resp.json()
                    data = json_data.get("data", json_data) if isinstance(json_data, dict) else json_data
                    if isinstance(data, list):
                        raw_list = data
                    elif isinstance(data, dict):
                        if isinstance(data.get("devices"), list):
                            raw_list = data["devices"]
                        elif isinstance(data.get("clients"), list):
                            raw_list = data["clients"]
            except Exception as e:
                log_event(logger, logging.WARNING, "log_eero.devices_endpoint_failed", error=str(e))

            # Fallback 1: recupero dispositivi dai dettagli completi della rete se /devices era vuoto o assente
            if not raw_list:
                try:
                    resp_net = await client.get(f"{EERO_API_BASE}/networks/{self.current_network_id}", headers=self._get_headers())
                    if resp_net.status_code == 200:
                        net_data = resp_net.json().get("data", {})
                        if isinstance(net_data, dict):
                            if isinstance(net_data.get("devices"), list) and net_data["devices"]:
                                raw_list = net_data["devices"]
                            elif isinstance(net_data.get("clients"), list) and net_data["clients"]:
                                raw_list = net_data["clients"]
                except Exception as e:
                    log_event(logger, logging.WARNING, "log_eero.devices_fallback_failed", error=str(e))

        # Se non ci sono dispositivi connessi/noti sulla rete reale, ritorna lista vuota dinamica
        if not raw_list:
            return []

        # Arricchimento opzionale con telemetria data_usage (se la rete supporta eero Plus)
        data_usage_map = {}
        if self._data_usage_endpoint_available and self.current_network_id:
            now_ts = time.time()
            if now_ts - self._last_data_usage_check > 300.0:
                self._last_data_usage_check = now_ts
                try:
                    async with self._client_session(timeout=5.0) as client:
                        resp_du = await client.get(
                            f"{EERO_API_BASE}/networks/{self.current_network_id}/data_usage/devices",
                            headers=self._get_headers()
                        )
                        if resp_du.status_code == 200:
                            du_json = resp_du.json()
                            du_data = du_json.get("data", du_json) if isinstance(du_json, dict) else du_json
                            du_items = du_data if isinstance(du_data, list) else (du_data.get("devices") or [])
                            for it in du_items:
                                if isinstance(it, dict):
                                    m = (it.get("mac") or it.get("mac_address") or "").lower().strip()
                                    if m:
                                        self._cached_cloud_data_usage[m] = it
                        elif resp_du.status_code in (401, 403, 404):
                            self._data_usage_endpoint_available = False
                except Exception:
                    pass
            data_usage_map = self._cached_cloud_data_usage

        devices_list = []
        for d in raw_list:
            if not isinstance(d, dict):
                continue
            try:
                d_mac = (d.get("mac") or d.get("mac_address") or "").lower().strip()
                if d_mac and d_mac in data_usage_map:
                    du = data_usage_map[d_mac]
                    if not d.get("rx_bytes"):
                        d["rx_bytes"] = du.get("rx_bytes") or du.get("download") or du.get("bytes_received")
                    if not d.get("tx_bytes"):
                        d["tx_bytes"] = du.get("tx_bytes") or du.get("upload") or du.get("bytes_transmitted")
                devices_list.append(self._normalize_device(d))
            except Exception as ex:
                log_event(logger, logging.ERROR, "log_eero.device_item_normalize_failed", error=str(ex))
                devices_list.append(dict(d))
        return devices_list

    # =========================================================================
    # CONTROLLI E AZIONI SU RETE E NODI
    # =========================================================================

    async def update_device(
        self,
        device_id: str,
        nickname: Optional[str] = None,
        paused: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Aggiorna il nome o lo stato di pausa internet di un dispositivo sul cloud eero."""
        payload: Dict[str, Any] = {}
        if nickname is not None:
            payload["nickname"] = nickname
        if paused is not None:
            payload["paused"] = paused

        # Aggiorna lo stato in memoria se presente nel poller
        try:
            from app.services.poller import background_poller
            cached_state = background_poller.get_cached_state()
            found_dev = None
            for dev in cached_state.get("devices", []):
                if str(dev.get("id")) == str(device_id) or (dev.get("mac") or "").lower() == str(device_id).lower():
                    found_dev = dev
                    if nickname is not None:
                        dev["nickname"] = nickname
                        dev["custom_name"] = nickname
                    if paused is not None:
                        dev["paused"] = bool(paused)
                        dev["is_paused"] = bool(paused)
                    break
        except Exception:
            found_dev = None

        if settings.demo_mode or not self.is_authenticated or (self.user_token and self.user_token.startswith("demo_")):
            return self._update_demo_device(device_id, nickname=nickname, paused=paused, payload=payload)

        # Raccolta URL candidati da testare in sequenza con massima priorità all'URL nativo del dispositivo
        urls_to_try = []

        # 1. URL canonico eero del dispositivo dal cloud (massima priorità)
        if found_dev and found_dev.get("url"):
            dev_u = str(found_dev["url"]).lstrip("/")
            urls_to_try.append(f"https://api-user.e2ro.com/{dev_u}" if dev_u.startswith("2.2/") else f"{EERO_API_BASE}/{dev_u}")

        # 2. Se device_id è già un URL completo eero
        if device_id.startswith("/2.2/") or device_id.startswith("2.2/"):
            urls_to_try.append(f"https://api-user.e2ro.com/{device_id.lstrip('/')}")
        elif "/" in device_id and ":" not in device_id:
            urls_to_try.append(f"{EERO_API_BASE}/{device_id.lstrip('/')}")

        # 3. ID autentico (non-MAC)
        if found_dev and found_dev.get("id"):
            fid = str(found_dev["id"]).split("/")[-1]
            if ":" not in fid:
                if self.current_network_id:
                    urls_to_try.append(f"{EERO_API_BASE}/networks/{self.current_network_id}/devices/{fid}")
                urls_to_try.append(f"{EERO_API_BASE}/devices/{fid}")

        # 4. Fallback su network/devices
        if self.current_network_id:
            urls_to_try.append(f"{EERO_API_BASE}/networks/{self.current_network_id}/devices/{device_id}")
        urls_to_try.append(f"{EERO_API_BASE}/devices/{device_id}")

        base_urls = [u for u in dict.fromkeys(urls_to_try) if u]

        # Priorità assoluta agli endpoint di azione specifici per pause/blacklist
        action_calls = []
        if paused is True:
            for u in base_urls:
                action_calls.append((f"{u}/pause", "POST"))
                action_calls.append((f"{u}/blacklist", "POST"))
                action_calls.append((f"{u}/pause", "PUT"))
                action_calls.append((f"{u}/blacklist", "PUT"))
        elif paused is False:
            for u in base_urls:
                action_calls.append((f"{u}/unpause", "POST"))
                action_calls.append((f"{u}/unblacklist", "POST"))
                action_calls.append((f"{u}/unpause", "PUT"))
                action_calls.append((f"{u}/unblacklist", "PUT"))

        # Aggiunta degli endpoint base
        for u in base_urls:
            action_calls.append((u, "PUT"))
            action_calls.append((u, "POST"))
            action_calls.append((u, "PATCH"))

        composite_payload = dict(payload)
        if paused is not None:
            composite_payload["paused"] = paused
            composite_payload["is_paused"] = paused
            composite_payload["blacklisted"] = paused
            composite_payload["blocked"] = paused

        payload_variants = [composite_payload, {"paused": paused} if paused is not None else payload, {"blacklisted": paused} if paused is not None else payload, {}]

        last_error = ""
        success = False

        async with self._client_session() as client:
            for url, method in action_calls:
                for p_var in payload_variants:
                    try:
                        if method == "PUT":
                            resp = await client.put(url, json=p_var, headers=self._get_headers(), cookies=self._get_cookies())
                        elif method == "POST":
                            resp = await client.post(url, json=p_var, headers=self._get_headers(), cookies=self._get_cookies())
                        elif method == "PATCH":
                            resp = await client.patch(url, json=p_var, headers=self._get_headers(), cookies=self._get_cookies())

                        if resp.status_code in (200, 201, 204):
                            log_event(logger, logging.INFO, "log_eero.device_updated", device_id=device_id, method=method, url=url, payload=p_var)
                            return {
                                "status": "success",
                                "device_id": device_id,
                                "url_used": url,
                                "method_used": method,
                                "payload_used": p_var,
                                "cloud_synced": True
                            }
                        else:
                            last_error = tr("eero.device_update_http_error", method=method, status=resp.status_code, body=resp.text[:80], url=url)
                    except Exception as e:
                        last_error = f"{method} {url}: {e}"

        log_event(logger, logging.WARNING, "log_eero.device_update_failed", device_id=device_id, error=last_error)
        return {
            "status": "warning",
            "device_id": device_id,
            "payload": payload,
            "last_error": last_error,
            "cloud_synced": False
        }

    # =========================================================================
    # RETE OSPITI (GUEST WI-FI)
    # =========================================================================

    def _normalize_profile(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizza un profilo utente del Cloud eero."""
        profile = dict(p)
        prof_id = str(profile.get("id") or profile.get("url", "").split("/")[-1])
        profile["id"] = prof_id
        if not profile.get("name"):
            # Profiles are cached by the poller and rendered later: keep ``name`` English and ship
            # ``name_i18n`` so the UI can pick the viewer's language via localized(p, 'name').
            profile["name_i18n"] = tr_all("profiles.default_name")
            profile["name"] = profile["name_i18n"]["en"]
        profile["paused"] = bool(profile.get("paused", False))
        
        # Normalizzazione lista dispositivi associati
        raw_devices = profile.get("devices") or []
        normalized_devs = []
        if isinstance(raw_devices, list):
            for d in raw_devices:
                if isinstance(d, dict):
                    d_id = str(d.get("id") or d.get("url", "").split("/")[-1])
                    d_mac = (d.get("mac") or d.get("mac_address") or "").lower()
                    normalized_devs.append({
                        "id": d_id,
                        "url": d.get("url") or f"/2.2/devices/{d_id}",
                        "mac": d_mac,
                        "nickname": d.get("nickname") or d.get("hostname") or d.get("display_name") or d_mac,
                        "hostname": d.get("hostname") or "",
                        "ip": d.get("ip") or d.get("ipv4") or "",
                        "connected": bool(d.get("connected", False)),
                        "paused": bool(d.get("paused", False)),
                    })
                elif isinstance(d, str):
                    d_id = d.split("/")[-1]
                    normalized_devs.append({
                        "id": d_id,
                        "url": d if "/" in d else f"/2.2/devices/{d_id}",
                        "mac": "",
                        "nickname": d_id,
                        "connected": True,
                    })
        profile["devices"] = normalized_devs
        profile["device_count"] = len(normalized_devs)
        return profile

    async def get_profiles(self) -> List[Dict[str, Any]]:
        """Recupera l'elenco dei profili utente configurati nel Cloud eero e sincronizzati con il DB locale."""
        if settings.demo_mode or not self.is_authenticated or (self.user_token and self.user_token.startswith("demo_")):
            profiles = self._get_demo_profiles()
        else:
            if not self.current_network_id:
                await self.fetch_account_info()

            if not self.current_network_id:
                profiles = []
            else:
                raw_list = []
                async with self._client_session() as client:
                    for endpoint in [
                        f"{EERO_API_BASE}/networks/{self.current_network_id}/profiles",
                        f"https://api-user.e2ro.com/2.2/networks/{self.current_network_id}/profiles",
                        f"{EERO_API_BASE}/profiles",
                        f"https://api-user.e2ro.com/2.2/profiles"
                    ]:
                        try:
                            resp = await client.get(endpoint, headers=self._get_headers(), cookies=self._get_cookies())
                            if resp.status_code == 200:
                                res_json = resp.json()
                                raw_list = res_json.get("data", res_json) if isinstance(res_json, dict) else res_json
                                if isinstance(raw_list, list) and raw_list:
                                    break
                            else:
                                log_event(logger, logging.WARNING, "log_eero.profiles_endpoint_status", endpoint=endpoint, status=resp.status_code, response=resp.text)
                        except Exception as e:
                            log_event(logger, logging.WARNING, "log_eero.profiles_endpoint_failed", endpoint=endpoint, error=str(e))

                profiles = []
                if isinstance(raw_list, list):
                    for p in raw_list:
                        try:
                            if isinstance(p, dict):
                                profiles.append(self._normalize_profile(p))
                        except Exception as ex:
                            log_event(logger, logging.ERROR, "log_eero.profile_item_normalize_failed", error=str(ex))

        all_devs = []
        try:
            all_devs = await self.get_devices()
            dev_lookup = {}
            for d in all_devs:
                if d.get("id"):
                    dev_lookup[str(d["id"])] = d
                if d.get("mac"):
                    dev_lookup[d["mac"].lower()] = d
                if d.get("url"):
                    dev_lookup[d["url"]] = d

            for prof in profiles:
                enriched_pdevs = []
                for pdev in prof.get("devices", []):
                    p_id = str(pdev.get("id") or "")
                    p_mac = (pdev.get("mac") or "").lower()
                    p_url = pdev.get("url") or ""
                    match = dev_lookup.get(p_id) or dev_lookup.get(p_mac) or dev_lookup.get(p_url)
                    if match:
                        merged = dict(pdev)
                        merged.update({k: v for k, v in match.items() if v})
                        enriched_pdevs.append(merged)
                    else:
                        enriched_pdevs.append(pdev)
                prof["devices"] = enriched_pdevs
        except Exception as enrich_ex:
            log_event(logger, logging.WARNING, "log_eero.profile_enrichment_warning", error=str(enrich_ex))

        # Sincronizzazione e override con il Database Locale (SQLite)
        try:
            from app.services.db import db_service
            metadata_map = await db_service.get_all_device_metadata()

            for prof in profiles:
                prof_id = prof.get("id")
                filtered_devs = []
                for pd in prof.get("devices", []):
                    pd_mac = (pd.get("mac") or "").lower()
                    pd_id = str(pd.get("id") or "")
                    pd_url = pd.get("url") or ""
                    meta = metadata_map.get(pd_mac) or metadata_map.get(pd_id) or metadata_map.get(pd_url) or {}
                    override_pid = meta.get("profile_id")
                    if override_pid == "NONE":
                        continue
                    elif override_pid and override_pid != prof_id:
                        continue
                    filtered_devs.append(pd)
                prof["devices"] = filtered_devs

            for d in all_devs:
                d_mac = (d.get("mac") or "").lower()
                d_id = str(d.get("id") or "")
                d_url = d.get("url") or ""
                meta = metadata_map.get(d_mac) or metadata_map.get(d_id) or metadata_map.get(d_url) or {}
                override_pid = meta.get("profile_id")
                if override_pid and override_pid != "NONE":
                    target_p = next((p for p in profiles if p.get("id") == override_pid or p.get("url", "").endswith(override_pid)), None)
                    if target_p:
                        already_in = any((x.get("mac") or "").lower() == d_mac or str(x.get("id") or "") == d_id for x in target_p.get("devices", []))
                        if not already_in:
                            target_p["devices"].append(d)

            for prof in profiles:
                prof["device_count"] = len(prof.get("devices", []))
        except Exception as db_ex:
            log_event(logger, logging.WARNING, "log_eero.profile_overrides_sync_failed", error=str(db_ex))

        return profiles

    async def create_profile(self, name: str, device_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Crea un nuovo profilo utente nel Cloud eero."""
        if not name or not name.strip():
            raise ValueError(tr("eero.profile_name_empty"))
        
        name = name.strip()
        device_ids = device_ids or []

        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            new_id = f"prof_{int(time.time())}"
            assigned_devs = []
            for d in self._demo_state.get("devices", []):
                d_id = str(d.get("id"))
                d_mac = (d.get("mac") or "").lower()
                if d_id in device_ids or d_mac in [x.lower() for x in device_ids]:
                    assigned_devs.append({
                        "id": d_id,
                        "url": f"/2.2/devices/{d_id}",
                        "mac": d_mac,
                        "nickname": d.get("nickname") or d.get("hostname"),
                        "hostname": d.get("hostname") or "",
                        "ip": d.get("ip") or "",
                        "connected": bool(d.get("connected", False)),
                        "paused": bool(d.get("paused", False)),
                    })
                    # Rimuovi da eventuali altri profili demo
                    for p in self._demo_state.get("profiles", []):
                        p["devices"] = [x for x in p.get("devices", []) if str(x.get("id")) != d_id and (x.get("mac") or "").lower() != d_mac]

            new_profile = {
                "id": new_id,
                "url": f"/2.2/profiles/{new_id}",
                "name": name,
                "paused": False,
                "devices": assigned_devs,
                "device_count": len(assigned_devs)
            }
            if "profiles" not in self._demo_state:
                self._demo_state["profiles"] = []
            self._demo_state["profiles"].append(new_profile)
            return {"status": "success", "profile": new_profile}

        formatted_devices = [f"/2.2/devices/{d}" if not d.startswith("/2.2/") else d for d in device_ids]
        payload = {"name": name, "devices": formatted_devices}

        async with self._client_session() as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/profiles",
                json=payload,
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(tr("eero.profile_create_error", error=resp.text))
            created = resp.json().get("data", payload)
            return {"status": "success", "profile": self._normalize_profile(created)}

    async def update_profile(
        self,
        profile_id: str,
        name: Optional[str] = None,
        paused: Optional[bool] = None,
        device_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Aggiorna le informazioni o i dispositivi associati a un profilo eero."""
        clean_id = str(profile_id).split("/")[-1]

        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            for p in self._demo_state.get("profiles", []):
                if p["id"] == clean_id or p.get("url", "").endswith(clean_id):
                    if name is not None:
                        p["name"] = name.strip()
                    if paused is not None:
                        p["paused"] = paused
                    if device_ids is not None:
                        assigned_devs = []
                        for d in self._demo_state.get("devices", []):
                            d_id = str(d.get("id"))
                            d_mac = (d.get("mac") or "").lower()
                            if d_id in device_ids or d_mac in [x.lower() for x in device_ids] or any(x.endswith(f"/{d_id}") for x in device_ids):
                                assigned_devs.append({
                                    "id": d_id,
                                    "url": f"/2.2/devices/{d_id}",
                                    "mac": d_mac,
                                    "nickname": d.get("nickname") or d.get("hostname"),
                                    "hostname": d.get("hostname") or "",
                                    "ip": d.get("ip") or "",
                                    "connected": bool(d.get("connected", False)),
                                    "paused": bool(d.get("paused", False)),
                                })
                        p["devices"] = assigned_devs
                        p["device_count"] = len(assigned_devs)
                    return {"status": "success", "profile": p}
            raise ValueError(tr("eero.demo_profile_not_found", profile_id=clean_id))

        if not self.current_network_id:
            await self.fetch_account_info()

        formatted_urls = []
        clean_ids = []
        if device_ids is not None:
            for d in device_ids:
                d_str = str(d).strip()
                if not d_str:
                    continue
                c_id = d_str.split("/")[-1]
                clean_ids.append(c_id)
                if d_str.startswith("/2.2/"):
                    formatted_urls.append(d_str)
                elif d_str.startswith("/"):
                    formatted_urls.append(f"/2.2{d_str}")
                else:
                    formatted_urls.append(f"/2.2/devices/{d_str}")

        payloads = []
        base_p: Dict[str, Any] = {}
        if name is not None:
            base_p["name"] = name.strip()
        if paused is not None:
            base_p["paused"] = paused

        if device_ids is not None:
            p1 = dict(base_p)
            p1["devices"] = formatted_urls
            payloads.append(p1)

            p2 = dict(base_p)
            p2["devices"] = clean_ids
            payloads.append(p2)

            payloads.append({"devices": formatted_urls})
            payloads.append({"devices": clean_ids})
        else:
            payloads.append(base_p)

        headers = self._get_headers()
        endpoints = []
        if str(profile_id).startswith("/2.2/"):
            endpoints.append(f"https://api-user.e2ro.com{profile_id}")

        if self.current_network_id:
            endpoints.append(f"{EERO_API_BASE}/networks/{self.current_network_id}/profiles/{clean_id}")
            endpoints.append(f"{EERO_API_BASE}/networks/{self.current_network_id}/profile/{clean_id}")

        endpoints.append(f"{EERO_API_BASE}/profiles/{clean_id}")

        methods = ["PUT", "POST", "PATCH"]

        async with self._client_session() as client:
            last_err = ""
            for url in endpoints:
                for method in methods:
                    for payload in payloads:
                        try:
                            log_event(logger, logging.INFO, "log_eero.profile_update_attempt", method=method, url=url, payload=payload)
                            if method == "PUT":
                                resp = await client.put(url, json=payload, headers=headers)
                            elif method == "POST":
                                resp = await client.post(url, json=payload, headers=headers)
                            else:
                                resp = await client.patch(url, json=payload, headers=headers)

                            if resp.status_code in (200, 201, 204):
                                data = resp.json().get("data", payload) if (resp.status_code in (200, 201) and resp.text) else payload
                                log_event(logger, logging.INFO, "log_eero.profile_updated", profile_id=clean_id, status=resp.status_code, method=method, url=url)
                                return {"status": "success", "profile": self._normalize_profile(data)}
                            last_err = f"{resp.status_code}: {resp.text}"
                        except Exception as ex:
                            last_err = str(ex)
            raise RuntimeError(tr("eero.profile_update_error", error=last_err))

    async def delete_profile(self, profile_id: str) -> Dict[str, Any]:
        """Elimina un profilo utente da eero Cloud."""
        clean_id = str(profile_id).split("/")[-1]

        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["profiles"] = [
                p for p in self._demo_state.get("profiles", [])
                if p["id"] != clean_id and not p.get("url", "").endswith(clean_id)
            ]
            return {"status": "success", "deleted": clean_id}

        if not self.current_network_id:
            await self.fetch_account_info()

        headers = self._get_headers()
        endpoints = []
        if str(profile_id).startswith("/2.2/"):
            endpoints.append(f"https://api-user.e2ro.com{profile_id}")
        if self.current_network_id:
            endpoints.append(f"{EERO_API_BASE}/networks/{self.current_network_id}/profiles/{clean_id}")
        endpoints.append(f"{EERO_API_BASE}/profiles/{clean_id}")

        async with self._client_session() as client:
            last_err = ""
            for url in endpoints:
                try:
                    resp = await client.delete(url, headers=headers)
                    if resp.status_code in (200, 204):
                        return {"status": "success", "deleted": clean_id}
                    last_err = f"{resp.status_code}: {resp.text}"
                except Exception as ex:
                    last_err = str(ex)
            raise RuntimeError(tr("eero.profile_delete_error", error=last_err))

    async def set_profile_paused(self, profile_id: str, paused: bool) -> Dict[str, Any]:
        """Mette in pausa o riattiva la connessione di tutti i dispositivi del profilo."""
        clean_id = str(profile_id).split("/")[-1]

        target_prof = None
        # 1. Prova aggiornamento a livello profilo Cloud
        try:
            res = await self.update_profile(profile_id=profile_id, paused=paused)
            target_prof = res.get("profile")
        except Exception as ex:
            log_event(logger, logging.WARNING, "log_eero.profile_pause_cloud_warning", profile_id=clean_id, error=ex)

        # 2. Pausa/riattiva tutti i singoli dispositivi associati al profilo (garantito su Cloud eero)
        try:
            profiles = await self.get_profiles()
            target = next((p for p in profiles if p["id"] == clean_id or p.get("url", "").endswith(clean_id)), None)
            if target:
                target_prof = target
                for dev in target.get("devices", []):
                    d_id = str(dev.get("id") or dev.get("url", "").split("/")[-1] or dev.get("mac"))
                    if d_id:
                        try:
                            await self.update_device(device_id=d_id, paused=paused)
                        except Exception as d_ex:
                            log_event(logger, logging.WARNING, "log_eero.profile_device_pause_failed", device_id=d_id, error=str(d_ex))
        except Exception as ex:
            log_event(logger, logging.WARNING, "log_eero.profile_pause_devices_failed", profile_id=clean_id, error=ex)

        if not target_prof:
            target_prof = {"id": clean_id, "paused": paused}
        else:
            target_prof["paused"] = paused

        return {"status": "success", "profile": target_prof, "paused": paused}

    async def assign_device_to_profile(self, device_id_or_mac: str, profile_id: Optional[str]) -> Dict[str, Any]:
        """
        Assegna, sposta o rimuove un dispositivo da un profilo utente.
        Se profile_id è None o stringa vuota, il dispositivo viene rimosso dal profilo attuale.
        """
        if not device_id_or_mac:
            raise ValueError(tr("eero.device_id_missing"))

        dev_key = str(device_id_or_mac).strip()
        clean_target_pid = str(profile_id).split("/")[-1] if profile_id else None

        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            target_dev = None
            for d in self._demo_state.get("devices", []):
                if str(d.get("id")) == dev_key or (d.get("mac") or "").lower() == dev_key.lower():
                    target_dev = d
                    break
            
            if not target_dev:
                target_dev = {"id": dev_key, "mac": dev_key if ":" in dev_key else "", "nickname": dev_key}

            dev_id = str(target_dev.get("id"))
            dev_mac = (target_dev.get("mac") or "").lower()

            # 1. Rimuovi il dispositivo da tutti i profili esistenti
            for p in self._demo_state.get("profiles", []):
                p["devices"] = [
                    x for x in p.get("devices", [])
                    if str(x.get("id")) != dev_id and (x.get("mac") or "").lower() != dev_mac
                ]
                p["device_count"] = len(p["devices"])

            # 2. Se è specificato un profilo di destinazione, aggiungilo
            if clean_target_pid:
                assigned = False
                for p in self._demo_state.get("profiles", []):
                    if p["id"] == clean_target_pid or p.get("url", "").endswith(clean_target_pid):
                        p["devices"].append({
                            "id": dev_id,
                            "url": f"/2.2/devices/{dev_id}",
                            "mac": dev_mac,
                            "nickname": target_dev.get("nickname") or target_dev.get("hostname") or dev_key,
                            "hostname": target_dev.get("hostname") or "",
                            "ip": target_dev.get("ip") or "",
                            "connected": bool(target_dev.get("connected", False)),
                            "paused": bool(target_dev.get("paused", False)),
                        })
                        p["device_count"] = len(p["devices"])
                        assigned = True
                        break
                if not assigned:
                    raise ValueError(tr("eero.target_profile_not_found", profile_id=clean_target_pid))

            return {"status": "success", "device": dev_key, "assigned_profile_id": clean_target_pid}

        # -------------------------------------------------------------
        # MODALITÀ CLOUD REALE EERO
        # -------------------------------------------------------------
        if not self.current_network_id:
            await self.fetch_account_info()

        all_network_devices = await self.get_devices()

        # Risoluzione univoca del dispositivo (trova ID eero, MAC e URL risorsa)
        matched_net_dev = None
        for d in all_network_devices:
            d_mac = (d.get("mac") or "").lower()
            d_id = str(d.get("id") or "")
            d_url = d.get("url") or ""
            d_nick = (d.get("nickname") or d.get("hostname") or "").lower()
            if (dev_key.lower() == d_mac) or (dev_key == d_id) or (d_url.endswith(f"/{dev_key}")) or (dev_key.lower() == d_nick):
                matched_net_dev = d
                break

        target_mac = (matched_net_dev.get("mac") or "").lower() if matched_net_dev else (dev_key.lower() if ":" in dev_key or "-" in dev_key else "")
        target_id = str(matched_net_dev.get("id") or "") if matched_net_dev else dev_key
        target_url = matched_net_dev.get("url") if matched_net_dev else (f"/2.2/devices/{target_id}" if not target_id.startswith("/2.2/") else target_id)
        if not target_url.startswith("/2.2/devices/"):
            target_url = f"/2.2/devices/{target_id}"

        clean_dev_id = target_id.split("/")[-1] if "/" in target_id else target_id

        log_event(
            logger, logging.INFO, "log_eero.device_profile_assign_resolved",
            dev_key=dev_key, target_mac=target_mac, device_id=clean_dev_id, url=target_url, profile_id=clean_target_pid,
        )

        # 1. Salva la modifica nel Database Locale per garantire persistenza ed effetto immediato
        try:
            from app.services.db import db_service
            keys_to_save = set()
            if target_mac:
                keys_to_save.add(target_mac.lower())
            if clean_dev_id:
                keys_to_save.add(clean_dev_id)
            if dev_key:
                keys_to_save.add(dev_key.lower())

            for k in keys_to_save:
                await db_service.upsert_device_metadata(
                    mac_address=k,
                    profile_id=clean_target_pid if clean_target_pid else "NONE"
                )
            log_event(logger, logging.INFO, "log_eero.device_profile_mapping_persisted", keys=keys_to_save, profile_id=clean_target_pid or "NONE")
        except Exception as db_err:
            log_event(logger, logging.ERROR, "log_eero.device_profile_mapping_persist_failed", error=str(db_err))

        # 2. Tenta la sincronizzazione diretta su eero Cloud (best effort)
        try:
            headers = self._get_headers()
            async with self._client_session() as client:
                if not clean_target_pid:
                    unassign_endpoints = [
                        (f"{EERO_API_BASE}/networks/{self.current_network_id}/devices/{clean_dev_id}/profile", "DELETE", None),
                        (f"{EERO_API_BASE}/devices/{clean_dev_id}/profile", "DELETE", None),
                    ]
                    for url, method, payload in unassign_endpoints:
                        try:
                            if method == "DELETE":
                                await client.delete(url, headers=headers)
                        except Exception:
                            pass
                elif clean_target_pid:
                    assign_endpoints = [
                        (f"{EERO_API_BASE}/networks/{self.current_network_id}/profiles/{clean_target_pid}/devices", "POST", {"devices": [target_url]}),
                        (f"{EERO_API_BASE}/networks/{self.current_network_id}/devices/{clean_dev_id}/profile", "POST", {"profile_id": clean_target_pid}),
                    ]
                    for url, method, payload in assign_endpoints:
                        try:
                            await client.post(url, json=payload, headers=headers)
                        except Exception:
                            pass
        except Exception as cloud_ex:
            logger.debug(f"Direct cloud profile sync attempt finished: {cloud_ex}")

        return {"status": "success", "device": dev_key, "assigned_profile_id": clean_target_pid}

    # =========================================================================
    # SIMULATORE DEMO MODE (FALLBACK & TESTING REALISTICO)
    # =========================================================================
    # =========================================================================
    # SIMULATORE DEMO MODE (Fornito da DemoFixturesMixin in demo_fixtures.py)
    # =========================================================================

    async def get_device_data_usage(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Recupera l'utilizzo dati aggregato dei dispositivi per la rete attiva (Fase 3 - Insights Suite)."""
        net_id = network_id or self.current_network_id
        if not net_id:
            return {"status": "error", "message": tr("eero.no_network_selected"), "devices": []}

        if self.is_demo_mode:
            demo_devices = self._get_demo_devices()
            results = []
            for d in demo_devices:
                rx_b = float(d.get("rx_bytes") or 0)
                tx_b = float(d.get("tx_bytes") or 0)
                results.append({
                    "mac": d.get("mac"),
                    "hostname": d.get("hostname"),
                    "nickname": d.get("nickname"),
                    "rx_bytes": rx_b,
                    "tx_bytes": tx_b,
                    "total_bytes": rx_b + tx_b,
                    "download_rate_mbps": d.get("download_rate_mbps", 0.0),
                    "upload_rate_mbps": d.get("upload_rate_mbps", 0.0),
                })
            return {"status": "success", "network_id": net_id, "devices": results}

        try:
            async with self._client_session() as client:
                resp = await client.get(
                    f"{EERO_API_BASE}/networks/{net_id}/data_usage/devices",
                    headers=self._get_headers()
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {"status": "success", "network_id": net_id, "data": data}
        except Exception as e:
            logger.debug(f"Endpoint /data_usage/devices unavailable or failed ({e}); falling back to live telemetry.")

        devices = await self.get_devices()
        results = []
        for d in devices:
            rx_b = float(d.get("rx_bytes") or 0)
            tx_b = float(d.get("tx_bytes") or 0)
            results.append({
                "mac": d.get("mac"),
                "hostname": d.get("hostname"),
                "nickname": d.get("nickname"),
                "rx_bytes": rx_b,
                "tx_bytes": tx_b,
                "total_bytes": rx_b + tx_b,
                "download_rate_mbps": d.get("download_rate_mbps", 0.0),
                "upload_rate_mbps": d.get("upload_rate_mbps", 0.0),
            })
        return {"status": "success", "network_id": net_id, "devices": results}

    # =====================================================================
    # v1.7.0 — IPv6 FIREWALL RULES, PLACEMENT TEST, GUARDIAN VPN & AMAZON OAUTH
    # =====================================================================

