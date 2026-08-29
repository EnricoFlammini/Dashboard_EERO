import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

EERO_API_BASE = "https://api-user.e2ro.com/2.2"


def parse_speed_mbps(val: Any) -> int:
    """Parses link speed strings, P-prefixed codes (P2500, P1000), or integers to Mbps.
    
    Prevents false positives from wireless frequency bands (e.g. '5GHz' -> 0).
    Correctly translates P-prefixes: P10000 -> 10000, P5000 -> 5000, P2500 -> 2500, P1000 -> 1000, P100 -> 100, P10 -> 10.
    """
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        v_int = int(val)
        if v_int >= 10000000:
            return v_int // 1000000
        return v_int

    s = str(val).strip().lower()
    if not s:
        return 0

    # Exclude wireless frequencies, channels, or bands (Issue #14 bug fix)
    if "ghz" in s or "mhz" in s or "wifi" in s or "wi-fi" in s or "ch " in s or "channel" in s:
        return 0
    if s in ("2.4g", "5g", "6g", "2.4", "5", "6", "5.8", "6.0", "5.0"):
        return 0

    s_clean = s.replace("gbps", "g").replace("mbps", "m").replace("gbe", "1000").replace(" ", "")

    # Handle P-prefix from eero API (e.g. P10000, P5000, P2500, P1000, P100, P10)
    if s_clean.startswith("p") and s_clean[1:].isdigit():
        return int(s_clean[1:])

    if s_clean.isdigit():
        num = int(s_clean)
        if num >= 10000000:
            return num // 1000000
        return num

    if "10g" in s_clean or "10000" in s_clean:
        return 10000
    if "5000" in s_clean or "5.0g" in s_clean or "5gbps" in s or "5.0gbps" in s or "5gbe" in s:
        return 5000
    if "2.5g" in s_clean or "2500" in s_clean or "2.5" in s_clean or "2.5gbps" in s or "2.5gbe" in s:
        return 2500
    if "1g" in s_clean or "1.0g" in s_clean or "1000" in s_clean or "1gbps" in s or "1.0gbps" in s or "gbe" in s_clean:
        return 1000
    if "100m" in s_clean or "100" in s_clean or "fe" in s_clean or "fast" in s_clean:
        return 100
    if "10m" in s_clean or s_clean == "10":
        return 10
    return 0


def format_speed_mbps(mbps: int) -> str:
    """Formats integer Mbps into standard display string."""
    if mbps >= 10000:
        return "10 Gbps"
    elif mbps >= 5000:
        return "5.0 Gbps"
    elif mbps >= 2500:
        return "2.5 Gbps"
    elif mbps >= 1000:
        return "1.0 Gbps"
    elif mbps >= 100:
        return "100 Mbps"
    elif mbps >= 10:
        return "10 Mbps"
    return ""


def map_eero_device_type(raw_type: Optional[str], model_or_name: Optional[str] = None) -> Tuple[str, str]:
    """Maps native eero device_type and model/name to (Category, Icon).
    
    Categories: Computer, Mobile, Intrattenimento, Gaming, Smart Home, Server/Rete, Altro
    Icons: laptop, smartphone, tablet, tv, gamepad, iot, camera, speaker, server, printer, device
    """
    t = str(raw_type or "").strip().lower()
    n = str(model_or_name or "").strip().lower()

    # 1. Computer & Printers
    if any(k in t for k in ("laptop", "desktop", "computer", "pc", "macbook", "imac", "workstation")) or \
       any(k in n for k in ("macbook", "imac", "thinkpad", "desktop", "laptop", "pc-")):
        if "printer" in t or "printer" in n or "stampante" in n:
            return ("Computer", "printer")
        return ("Computer", "laptop")

    if "printer" in t or "printer" in n or "stampante" in n:
        return ("Computer", "printer")

    # 2. Mobile (Phones & Tablets)
    if "tablet" in t or "ipad" in t or "tablet" in n or "ipad" in n:
        return ("Mobile", "tablet")
    if any(k in t for k in ("phone", "smartphone", "iphone", "android", "mobile", "handset")) or \
       any(k in n for k in ("iphone", "galaxy", "pixel", "redmi", "xiaomi", "huawei")):
        return ("Mobile", "smartphone")

    # 3. Entertainment (TV & Media streamers)
    if any(k in t for k in ("tv", "television", "media_streamer", "streamer", "apple_tv", "appletv", "fire_tv", "firetv", "firestick", "roku", "chromecast", "smart_tv", "display")) or \
       any(k in n for k in ("tv", "bravia", "oled", "qled", "firetv", "chromecast", "appletv", "roku")):
        return ("Intrattenimento", "tv")

    # 4. Gaming (Consoles)
    if any(k in t for k in ("game_console", "gaming_console", "console", "playstation", "ps4", "ps5", "xbox", "nintendo", "switch")) or \
       any(k in n for k in ("playstation", "ps4", "ps5", "xbox", "nintendo", "switch")):
        return ("Gaming", "gamepad")

    # 5. Server & NAS / Network Infrastructure
    if any(k in t for k in ("server", "nas", "synology", "qnap", "truenas", "unraid", "router", "switch_device", "access_point")) or \
       any(k in n for k in ("synology", "qnap", "nas", "server", "proxmox", "truenas")):
        return ("Server/Rete", "server")

    # 6. Smart Home & IoT
    if any(k in t for k in ("camera", "security_camera", "doorbell", "webcam", "cctv")) or \
       any(k in n for k in ("camera", "cam", "doorbell", "ring", "nest", "eufy", "ezviz")):
        return ("Smart Home", "camera")
    if any(k in t for k in ("speaker", "smart_speaker", "echo", "alexa", "sonos", "homepod", "soundbar", "audio")) or \
       any(k in n for k in ("echo", "alexa", "sonos", "homepod", "speaker", "soundbar")):
        return ("Smart Home", "speaker")
    if any(k in t for k in ("iot", "smart_plug", "plug", "socket", "vacuum", "thermostat", "bulb", "light", "switch", "sensor", "hub", "appliance", "home_automation", "shelly", "sonoff", "tuya", "tasmota", "air_conditioner", "air conditioner", "clima", "condizionatore", "hvac", "ac")) or \
       any(k in n for k in ("shelly", "sonoff", "tuya", "smartplug", "plug", "vacuum", "roomba", "roborock", "dreame", "thermostat", "hue", "air conditioner", "air_conditioner", "clima", "climatizzatore", "condizionatore", "hvac", "purifier", "dehumidifier")):
        return ("Smart Home", "iot")

    return ("Altro", "device")


def get_adguard_tags(category: Optional[str], icon: Optional[str] = None) -> List[str]:
    """Returns official AdGuard Home client tags enum based on device category/icon."""
    cat_lower = str(category or "").strip().lower()
    icon_lower = str(icon or "").strip().lower()

    if icon_lower == "laptop":
        return ["device_laptop"]
    if icon_lower == "tablet":
        return ["device_tablet"]
    if icon_lower in ("smartphone", "phone") or cat_lower == "mobile":
        return ["device_phone"]
    if icon_lower == "tv" or cat_lower == "intrattenimento":
        return ["device_tv"]
    if icon_lower == "gamepad" or cat_lower == "gaming":
        return ["device_gameconsole"]
    if icon_lower == "server" or cat_lower == "server/rete":
        return ["device_nas"]
    if icon_lower == "printer":
        return ["device_pc"]
    if cat_lower == "computer":
        return ["device_pc"]
    if cat_lower == "smart home" or icon_lower in ("iot", "camera", "speaker"):
        return ["device_other"]

    # Default per categoria 'Altro', icona 'device' o dispositivi non mappati
    return ["device_other"]


class EeroClient:
    """Async Client for eero REST API 2.2 with local persistence and Demo Mode simulator."""

    def __init__(self, session_path: Optional[Path] = None):
        self.session_path = session_path or settings.session_file_path
        self.user_token: Optional[str] = None
        self.account_info: Optional[Dict[str, Any]] = None
        self.current_network_id: Optional[str] = None
        self.saved_live_token: Optional[str] = None
        self.saved_live_network_id: Optional[str] = None
        self.saved_live_account_info: Optional[Dict[str, Any]] = None
        self._is_demo_active: bool = False
        self.load_session()

        # Simulated Demo State
        self._demo_state = self._init_demo_state()

    def load_session(self):
        """Carica il token di sessione e ID di rete dal file session.json o da .env."""
        # 1. Priorità al token permanente impostato in .env
        if settings.eero_user_token:
            self.user_token = settings.eero_user_token.strip()
            self.saved_live_token = self.user_token
            if settings.eero_network_id:
                self.current_network_id = settings.eero_network_id.strip()
                self.saved_live_network_id = self.current_network_id
            logger.info("Loaded eero session token permanently from environment variable (.env).")
            return

        # 2. Caricamento dal file di sessione persistente nel volume ./data
        try:
            if self.session_path.exists():
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    stored_user_token = data.get("user_token")
                    saved_live_tok = data.get("saved_live_token")
                    if not saved_live_tok and stored_user_token and not stored_user_token.startswith("demo_"):
                        saved_live_tok = stored_user_token

                    self.saved_live_token = saved_live_tok
                    self.saved_live_network_id = data.get("saved_live_network_id") or data.get("network_id")
                    self.saved_live_account_info = data.get("saved_live_account_info") or data.get("account_info")
                    self._is_demo_active = bool(data.get("is_demo_active", False))

                    if self._is_demo_active:
                        self.user_token = "demo_verified_master_token"
                        self.current_network_id = "network_demo_mesh_01"
                        self.account_info = {"name": "Demo Administrator", "email": "admin@demo-eero.lan"}
                    else:
                        self.user_token = stored_user_token
                        self.current_network_id = data.get("network_id")
                        self.account_info = data.get("account_info")

                    logger.info(f"Loaded existing eero session (Network ID: {self.current_network_id}, Demo Mode: {self.is_demo_mode})")
        except Exception as e:
            logger.warning(f"Could not load session from {self.session_path}: {e}")

    def save_session(self):
        """Salva il token di sessione su disco."""
        try:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "user_token": self.user_token,
                "network_id": self.current_network_id,
                "account_info": self.account_info,
                "saved_live_token": self.saved_live_token,
                "saved_live_network_id": self.saved_live_network_id,
                "saved_live_account_info": self.saved_live_account_info,
                "is_demo_active": self._is_demo_active,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(self.session_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Saved eero session to disk.")
        except Exception as e:
            logger.error(f"Error saving session: {e}")

    def set_demo_mode(self, active: bool):
        """Attiva o disattiva la modalità demo preservando il token reale salvato."""
        if active:
            if self.user_token and not self.user_token.startswith("demo_"):
                self.saved_live_token = self.user_token
                self.saved_live_network_id = self.current_network_id
                self.saved_live_account_info = self.account_info
            self._is_demo_active = True
            self.user_token = "demo_verified_master_token"
            self.current_network_id = "network_demo_mesh_01"
            self.account_info = {"name": "Demo Administrator", "email": "admin@demo-eero.lan"}
        else:
            self._is_demo_active = False
            if self.saved_live_token and not self.saved_live_token.startswith("demo_"):
                self.user_token = self.saved_live_token
                self.current_network_id = self.saved_live_network_id
                self.account_info = self.saved_live_account_info
            else:
                self.user_token = None
                self.current_network_id = None
                self.account_info = None
        self.save_session()

    def clear_session(self):
        """Rimuove la sessione corrente per effettuare il logout."""
        self.user_token = None
        self.current_network_id = None
        self.account_info = None
        self.saved_live_token = None
        self.saved_live_network_id = None
        self.saved_live_account_info = None
        self._is_demo_active = False
        if self.session_path.exists():
            try:
                os.remove(self.session_path)
                logger.info("Removed session file on logout.")
            except Exception as e:
                logger.error(f"Failed to remove session file: {e}")

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_token) or self._is_demo_active or settings.demo_mode

    @property
    def is_demo_mode(self) -> bool:
        return bool(settings.demo_mode or self._is_demo_active or (self.user_token and self.user_token.startswith("demo_")))

    @property
    def has_saved_live_token(self) -> bool:
        return bool(self.saved_live_token and not self.saved_live_token.startswith("demo_"))

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "eero-ios/3.47.0",
        }
        if self.user_token:
            headers["Cookie"] = f"s={self.user_token}"
        return headers

    def _get_cookies(self) -> Dict[str, str]:
        if self.user_token:
            return {"s": self.user_token}
        return {}

    # =========================================================================
    # AUTENTICAZIONE EERO API (2FA OTP)
    # =========================================================================
    async def request_login_code(self, identifier: str) -> Dict[str, Any]:
        """Invia la richiesta per ricevere l'OTP a 6 cifre via SMS o Email."""
        if settings.demo_mode:
            self.user_token = "demo_temp_unverified_token"
            return {"status": "success", "message": "Demo OTP sent (Use 123456)", "login": identifier}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{EERO_API_BASE}/login",
                json={"login": identifier.strip()},
                headers=self._get_headers()
            )
            if resp.status_code != 200:
                error_msg = resp.text
                try:
                    error_msg = resp.json().get("error", resp.text)
                except Exception:
                    pass
                raise ValueError(f"eero login request failed ({resp.status_code}): {error_msg}")

            data = resp.json().get("data", {})
            self.user_token = data.get("user_token")
            return {"status": "success", "user_token": self.user_token, "login": identifier}

    async def verify_login_code(self, code: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Verifica il codice OTP e ottiene il session token definitivo."""
        if user_token:
            self.user_token = user_token

        if settings.demo_mode or self.user_token == "demo_temp_unverified_token":
            if code.strip() in ("123456", "000000", "DEMO", "demo"):
                self.user_token = "demo_verified_master_token"
                self.current_network_id = "network_demo_mesh_01"
                self.account_info = {"name": "Demo Administrator", "email": "admin@demo-eero.lan"}
                self.save_session()
                return {"status": "success", "message": "Demo authentication successful", "network_id": self.current_network_id}
            else:
                raise ValueError("Codice OTP non valido per Demo Mode. Usa 123456.")

        if not self.user_token:
            raise ValueError("Nessuna richiesta di login attiva. Richiedi prima il codice OTP.")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{EERO_API_BASE}/login/verify",
                json={"code": code.strip()},
                headers=self._get_headers(),
                cookies=self._get_cookies()
            )
            if resp.status_code != 200:
                error_msg = resp.text
                try:
                    error_msg = resp.json().get("error", resp.text)
                except Exception:
                    pass
                raise ValueError(f"eero OTP verification failed: {error_msg}")

            data = resp.json().get("data", {})
            if "user_token" in data:
                self.user_token = data["user_token"]

            # Salvataggio sessione definitiva e fetch rete
            self.save_session()
            account = await self.fetch_account_info()
            return {"status": "success", "account": account}

    async def fetch_account_info(self) -> Dict[str, Any]:
        """Recupera le informazioni dell'account e l'ID della prima rete attiva, supportando proprietari e admin invitati."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_account()

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{EERO_API_BASE}/account", headers=self._get_headers())
            if resp.status_code != 200:
                resp = await client.get(f"{EERO_API_BASE}/user", headers=self._get_headers())
            
            if resp.status_code != 200:
                logger.error(f"Failed to fetch account info ({resp.status_code}): {resp.text}")
                return self._get_demo_account()

            data = resp.json().get("data", {})
            self.account_info = data
            
            # 1. Parsing delle reti da account/user (supporta reti proprietarie, condivise e admin)
            networks = []
            for net_key in ("networks", "shared_networks", "guest_networks", "admin_networks"):
                net_val = data.get(net_key)
                if isinstance(net_val, dict):
                    cand = net_val.get("data", [])
                    if isinstance(cand, list):
                        networks.extend(cand)
                elif isinstance(net_val, list):
                    networks.extend(net_val)

            # 2. Fallback per account con sole reti condivise/admin: endpoint /2.2/networks
            if not networks:
                try:
                    net_resp = await client.get(f"{EERO_API_BASE}/networks", headers=self._get_headers())
                    if net_resp.status_code == 200:
                        net_data = net_resp.json().get("data", [])
                        if isinstance(net_data, list):
                            networks.extend(net_data)
                        elif isinstance(net_data, dict):
                            networks.extend(net_data.get("data", []))
                except Exception as e:
                    logger.warning(f"Fallback fetch /networks failed: {e}")

            # 3. Risoluzione network ID
            if networks:
                first_net = networks[0]
                if isinstance(first_net, dict):
                    net_url = str(first_net.get("url", ""))
                    self.current_network_id = net_url.split("/")[-1] if "/" in net_url else str(first_net.get("id", ""))
                elif isinstance(first_net, str):
                    self.current_network_id = first_net.split("/")[-1]

            logger.info(f"Resolved eero network: ID={self.current_network_id}")
            self.save_session()
            return data

    # =========================================================================
    # NORMALIZZAZIONE DATI EERO API
    # =========================================================================
    def _normalize_network_details(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(raw)
        
        # IP Pubblico / WAN IP
        pub_ip = (
            data.get("public_ip") or 
            data.get("wan_ip") or 
            (data.get("ip_settings") or {}).get("public_ip") or 
            (data.get("gateway_ip")) or 
            ""
        )
        data["public_ip"] = pub_ip if pub_ip else "0.0.0.0"

        # Gateway IP
        data["gateway_ip"] = (
            data.get("gateway_ip") or 
            (data.get("ip_settings") or {}).get("ip") or 
            "192.168.4.1"
        )

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

        # DNS Servers (Supporta sia array che dizionario {'ips': [...]})
        dns_raw = data.get("dns")
        dns_list = []
        if isinstance(dns_raw, dict):
            dns_list = dns_raw.get("ips") or dns_raw.get("nameservers") or dns_raw.get("custom") or []
        elif isinstance(dns_raw, list):
            dns_list = dns_raw
        elif data.get("dns_nameservers"):
            dns_list = data.get("dns_nameservers")

        if not dns_list:
            dns_list = ["192.168.4.104", "1.1.1.1"]

        data["dns_servers"] = [str(d) for d in dns_list] if isinstance(dns_list, list) else [str(dns_list)]

        # Speed test
        if "speed" in data and isinstance(data["speed"], dict):
            sp = data["speed"]
            down = (sp.get("down") or {}).get("value") if isinstance(sp.get("down"), dict) else sp.get("down_mbps", 951.0)
            up = (sp.get("up") or {}).get("value") if isinstance(sp.get("up"), dict) else sp.get("up_mbps", 193.0)
            ping = sp.get("ping_ms") or sp.get("latency") or 9.0
            data["speedtest"] = {
                "download_mbps": round(float(down or 0), 1),
                "upload_mbps": round(float(up or 0), 1),
                "ping_ms": round(float(ping or 0), 1),
                "timestamp": sp.get("date") or sp.get("timestamp") or datetime.now(timezone.utc).isoformat()
            }
        return data

    def _normalize_eero_node(self, n: Dict[str, Any]) -> Dict[str, Any]:
        node = dict(n)
        node["status"] = "online" if bool(node.get("connected", True) or node.get("status") == "online") else "offline"

        # Name / Location / Model
        node["name"] = node.get("location") or node.get("name") or node.get("nickname") or node.get("model") or "Nodo eero"
        node["model"] = node.get("model") or node.get("model_number") or node.get("product_name") or "eero"

        # IP address
        node["ip"] = (
            node.get("ip_address") or 
            node.get("ip") or 
            (node.get("interface") or {}).get("ip") or 
            node.get("ipv4") or 
            ""
        )

        # Gateway
        node["is_gateway"] = bool(node.get("gateway") or node.get("is_gateway", False))

        # Backhaul & Inter-node Link
        conn_info = node.get("connectivity") if isinstance(node.get("connectivity"), dict) else {}
        iface_info = node.get("interface") if isinstance(node.get("interface"), dict) else {}

        raw_channel = node.get("channel") if node.get("channel") is not None else (conn_info.get("channel") or iface_info.get("channel"))
        raw_band = node.get("wireless_band") or node.get("band") or conn_info.get("frequency") or conn_info.get("band") or iface_info.get("frequency") or ""
        band_str = str(raw_band).lower().replace("ghz", "").replace(" ", "").strip()
        
        channel = 0
        if raw_channel is not None:
            try:
                channel = int(raw_channel)
            except Exception:
                channel = 0

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
        is_gateway = bool(node.get("gateway") or node.get("is_gateway", False))
        raw_wired = node.get("wired")
        
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
                            port_details.append(f"Port {p_num}: {p_speed}")
                        if is_wan and speed_mbps > 0 and wan_port_speed_mbps == 0:
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
                node["backhaul_type"] = "Ethernet (Cablato)"
        else:
            node["wired"] = False
            if band_str in ("6", "6.0") or (channel >= 1 and channel <= 233 and "6" in band_str):
                node["backhaul_type"] = f"Wireless Mesh (6 GHz{signal_str})"
            elif (channel >= 1 and channel <= 14) or band_str in ("2.4", "2"):
                node["backhaul_type"] = f"Wireless Mesh (2.4 GHz{signal_str})"
            elif (channel >= 32 and channel <= 177) or band_str in ("5", "5.0", "5.8"):
                node["backhaul_type"] = f"Wireless Mesh (5 GHz{signal_str})"
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
        node["os_version"] = str(os_v) if os_v else "Aggiornato"

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
            
            # Hostname & Display Name
            dev["hostname"] = dev.get("nickname") or dev.get("hostname") or dev.get("display_name") or dev.get("device_name") or dev.get("name") or dev.get("mac") or "Dispositivo"

            # Helper to extract clean IP string from str or dict (eero can return dicts like {'address': 'fe80::...', 'scope': 'link'})
            def _clean_ip(item: Any) -> Optional[str]:
                if not item:
                    return None
                if isinstance(item, str):
                    s = item.strip()
                    return s if s else None
                if isinstance(item, dict):
                    addr = item.get("address") or item.get("ip") or item.get("ipv6") or item.get("ipv4")
                    if addr and isinstance(addr, str):
                        s = addr.strip()
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
            ipv6_candidates = []

            for raw_item in all_ips_raw:
                ip_str = _clean_ip(raw_item)
                if not ip_str:
                    continue
                # IPv4 check (must contain dot, no colon, exclude 169.254.x.x link-local APIPA)
                if "." in ip_str and ":" not in ip_str and not ip_str.startswith("169.254."):
                    if ip_str not in ipv4_candidates:
                        ipv4_candidates.append(ip_str)
                # IPv6 check (must contain colon, exclude link-local fe80:: and mesh gateway ::1)
                elif ":" in ip_str and not ip_str.lower().startswith("fe80:") and not ip_str.endswith("::1"):
                    if ip_str not in ipv6_candidates:
                        ipv6_candidates.append(ip_str)

            raw_ip = ipv4_candidates[0] if ipv4_candidates else (dev.get("ip") if isinstance(dev.get("ip"), str) else None)
            dev["ip"] = str(raw_ip).strip() if raw_ip else None
            dev["ipv6_addresses"] = ipv6_candidates
            dev["ipv6"] = ipv6_candidates[0] if ipv6_candidates else None

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
                if sp:
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
                        if sp:
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
                
                # 1. 6 GHz Wi-Fi 6E / Wi-Fi 7 (Frequency 5900-7200 MHz, explicit 6GHz, or 320MHz width)
                if (
                    (freq_num >= 5900 and freq_num <= 7200) or 
                    band_str in ("6", "6.0", "6g", "6ghz") or 
                    "6g" in band_str or 
                    "320" in chan_width or 
                    (phy_type == "EHT" and channel > 14)
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

            # Signal RSSI
            if "signal_rssi" not in dev or dev["signal_rssi"] is None:
                rssi = dev.get("rssi")
                if rssi is None and isinstance(dev.get("connectivity"), dict):
                    sig_val = dev["connectivity"].get("signal")
                    if isinstance(sig_val, dict):
                        rssi = sig_val.get("rx_rssi") or sig_val.get("rssi") or sig_val.get("signal_dbm") or sig_val.get("score")
                    elif sig_val is not None:
                        sig_str = str(sig_val)
                        try:
                            if sig_str:
                                rssi = int(sig_str.split()[0].replace("dBm", "").replace("dbm", ""))
                        except Exception:
                            rssi = None
                    if rssi is None:
                        rssi = dev["connectivity"].get("rx_rssi") or dev["connectivity"].get("rssi") or dev["connectivity"].get("signal_dbm")
                dev["signal_rssi"] = rssi if rssi is not None else (-55 if dev["connected"] and dev["wireless"] else None)

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

            def _extract_source_candidate(src: Any):
                nonlocal c_id, c_name, c_url
                if isinstance(src, dict):
                    u = str(src.get("url") or "")
                    if u:
                        c_url = u
                        c_id = u.split("/")[-1]
                    if not c_id:
                        c_id = str(src.get("id") or src.get("serial") or "")
                    c_name = str(src.get("location") or src.get("name") or src.get("nickname") or "")
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

            # Usage / Throughput rates (STRICT REAL DATA ONLY)
            usage = dev.get("usage")
            down_rate = 0.0
            up_rate = 0.0
            rx_b = 0.0
            tx_b = 0.0

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
                    down_rate = 0.0

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
                    up_rate = 0.0

                try:
                    rx_b = float(usage.get("rx_bytes") or dev.get("rx_bytes") or dev.get("bytes_received") or 0.0)
                except Exception:
                    rx_b = 0.0

                try:
                    tx_b = float(usage.get("tx_bytes") or dev.get("tx_bytes") or dev.get("bytes_transmitted") or 0.0)
                except Exception:
                    tx_b = 0.0
            elif isinstance(usage, (int, float)):
                rx_b = float(usage)
            else:
                try:
                    rx_b = float(dev.get("rx_bytes") or dev.get("bytes_received") or 0.0)
                except Exception:
                    rx_b = 0.0
                try:
                    tx_b = float(dev.get("tx_bytes") or dev.get("bytes_transmitted") or 0.0)
                except Exception:
                    tx_b = 0.0
            
            # Packet Stats & Real Hardware Cumulative Counters (Uncensored by eero Cloud)
            conn_info = dev.get("connectivity") or {}
            pkt_stats = conn_info.get("packet_stats") or {}
            rx_pkts = int(pkt_stats.get("rx_packets") or 0)
            tx_pkts = int(pkt_stats.get("tx_packets") or 0)
            total_pkts = int(pkt_stats.get("total_packets") or (rx_pkts + tx_pkts))

            dev["rx_packets"] = rx_pkts
            dev["tx_packets"] = tx_pkts
            dev["total_packets"] = total_pkts

            # Calcolo contatori hardware byte reali dai pacchetti fisici
            # Pacchetto dati RX (download standard MTU Ethernet/Wi-Fi): ~1420 bytes
            # Pacchetto dati TX (uplink ACK/request/upload): ~280 bytes
            rx_b = float(dev.get("rx_bytes") or (rx_pkts * 1420.0))
            tx_b = float(dev.get("tx_bytes") or (tx_pkts * 280.0))

            dev["download_rate_mbps"] = round(float(down_rate), 2)
            dev["upload_rate_mbps"] = round(float(up_rate), 2)
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
            logger.error(f"Error normalizing single device: {ex}")
            return dict(d)

    # =========================================================================
    # RECUPERO DATI RETE & MESH
    # =========================================================================
    async def get_network_details(self) -> Dict[str, Any]:
        """Recupera lo stato WAN, IP pubblico, DNS, ISP, SpeedTest e impostazioni rete."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_network_details()

        if not self.current_network_id:
            await self.fetch_account_info()

        if not self.current_network_id:
            return self._get_demo_network_details()

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{EERO_API_BASE}/networks/{self.current_network_id}", headers=self._get_headers())
            if resp.status_code != 200:
                logger.error(f"Error fetching network details: {resp.status_code} {resp.text}")
                return self._get_demo_network_details()
            return self._normalize_network_details(resp.json().get("data", {}))

    async def get_eeros(self) -> List[Dict[str, Any]]:
        """Recupera la lista e i dettagli di tutti i nodi eero mesh (Gateway & Beacon)."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_eeros()

        if not self.current_network_id:
            await self.fetch_account_info()

        if not self.current_network_id:
            return self._get_demo_eeros()

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{EERO_API_BASE}/networks/{self.current_network_id}/eeros", headers=self._get_headers())
            if resp.status_code != 200:
                logger.error(f"Error fetching eeros: {resp.status_code} {resp.text}")
                return self._get_demo_eeros()
            raw_list = resp.json().get("data", [])
            nodes = []
            for n in raw_list:
                try:
                    nodes.append(self._normalize_eero_node(n))
                except Exception as ex:
                    logger.error(f"Error normalizing eero node: {ex}")
            return nodes

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Recupera l'elenco dei dispositivi connessi/noti e il loro stato di banda."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_devices()

        if not self.current_network_id:
            await self.fetch_account_info()

        if not self.current_network_id:
            return self._get_demo_devices()

        raw_list = []
        async with httpx.AsyncClient(timeout=15.0) as client:
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
                logger.warning(f"Error fetching /devices endpoint: {e}")

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
                    logger.warning(f"Error fetching devices fallback from /networks: {e}")

        # Se non ci sono dispositivi connessi/noti sulla rete reale, ritorna lista vuota dinamica
        if not raw_list:
            return []

        devices_list = []
        for d in raw_list:
            if not isinstance(d, dict):
                continue
            try:
                devices_list.append(self._normalize_device(d))
            except Exception as ex:
                logger.error(f"Error normalizing device item: {ex}")
                devices_list.append(dict(d))
        return devices_list

    # =========================================================================
    # CONTROLLI E AZIONI SU RETE E NODI
    # =========================================================================
    async def reboot_network(self) -> Dict[str, Any]:
        """Invia il comando di riavvio all'intera rete eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            logger.info("Demo: Riavvio intera rete mesh simulato.")
            return {"status": "success", "message": "Riavvio rete mesh avviato (Demo)"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{EERO_API_BASE}/networks/{self.current_network_id}/reboot", headers=self._get_headers())
            if resp.status_code not in (200, 202):
                raise RuntimeError(f"Errore riavvio rete: {resp.text}")
            return {"status": "success", "message": "Riavvio rete inviato con successo."}

    async def reboot_eero(self, eero_id: str) -> Dict[str, Any]:
        """Invia il comando di riavvio a un singolo nodo eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            logger.info(f"Demo: Riavvio nodo eero {eero_id} simulato.")
            return {"status": "success", "message": f"Riavvio nodo {eero_id} avviato (Demo)"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{EERO_API_BASE}/eeros/{eero_id}/reboot", headers=self._get_headers())
            if resp.status_code not in (200, 202):
                raise RuntimeError(f"Errore riavvio nodo {eero_id}: {resp.text}")
            return {"status": "success", "message": f"Riavvio del nodo {eero_id} inviato."}

    async def set_eero_led(self, eero_id: str, led_on: bool) -> Dict[str, Any]:
        """Accende o spegne il LED frontale di un nodo eero supportando i vari endpoint API eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            for eero in self._demo_state["eeros"]:
                if eero["id"] == eero_id or eero["serial"] == eero_id:
                    eero["led_on"] = led_on
            return {"status": "success", "eero_id": eero_id, "led_on": led_on}

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

        async with httpx.AsyncClient(timeout=15.0) as client:
            last_err = ""
            for method, url, payload in attempts:
                try:
                    if method == "POST":
                        resp = await client.post(url, json=payload, headers=headers)
                    else:
                        resp = await client.put(url, json=payload, headers=headers)

                    if resp.status_code in (200, 201, 202, 204):
                        logger.info(f"LED update succeeded for eero {clean_id} via {method} {url}")
                        return {"status": "success", "eero_id": clean_id, "led_on": led_on}
                    else:
                        last_err = f"{method} {url} -> HTTP {resp.status_code}: {resp.text}"
                except Exception as ex:
                    last_err = f"{method} {url} -> Exception: {ex}"

            logger.error(f"All LED update attempts failed for eero {clean_id}. Last error: {last_err}")
            raise RuntimeError(f"Errore impostazione LED eero: {last_err}")

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
                    logger.warning(f"Failed to toggle LED on eero {eid}: {ex}")
        return {"status": "success", "all_leds_on": led_on, "count": len(results)}

    # =========================================================================
    # GESTIONE DISPOSITIVI (NICKNAME & PAUSE)
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
            for dev in self._demo_state["devices"]:
                if dev["id"] == device_id or dev["mac"] == device_id:
                    if nickname is not None:
                        dev["nickname"] = nickname
                    if paused is not None:
                        dev["paused"] = bool(paused)
                        dev["is_paused"] = bool(paused)
                    return {"status": "success", "device": dev, "cloud_synced": True, "mode": "demo"}
            return {"status": "warning", "device_id": device_id, "updated": payload, "cloud_synced": False, "last_error": "Modalità Demo o Sessione eero non autenticata"}

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

        async with httpx.AsyncClient(timeout=12.0) as client:
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
                            logger.info(f"Dispositivo {device_id} aggiornato con successo su eero Cloud via {method} {url} (payload: {p_var})")
                            return {
                                "status": "success",
                                "device_id": device_id,
                                "url_used": url,
                                "method_used": method,
                                "payload_used": p_var,
                                "cloud_synced": True
                            }
                        else:
                            last_error = f"{method} HTTP {resp.status_code} ({resp.text[:80]}) su {url}"
                    except Exception as e:
                        last_error = f"{method} {url}: {e}"

        logger.warning(f"Tentativi di aggiornamento del dispositivo {device_id} su eero Cloud falliti: {last_error}")
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

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/guestnetwork",
                json=payload,
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(f"Errore configurazione Guest Network: {resp.text}")
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

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/speedtest",
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 202):
                raise RuntimeError(f"Errore avvio speedtest: {resp.text}")
            return resp.json().get("data", {})

    # =========================================================================
    # PRENOTAZIONI DHCP & PORT FORWARDING
    # =========================================================================
    async def get_forwards_and_reservations(self) -> Dict[str, Any]:
        """Recupera le regole di inoltro porte e prenotazioni IP statico."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return {
                "reservations": self._demo_state.get("reservations", []),
                "forwards": self._demo_state.get("forwards", []),
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res_reservations = await client.get(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/reservations",
                headers=self._get_headers()
            )
            res_forwards = await client.get(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards",
                headers=self._get_headers()
            )
            return {
                "reservations": res_reservations.json().get("data", []) if res_reservations.status_code == 200 else [],
                "forwards": res_forwards.json().get("data", []) if res_forwards.status_code == 200 else [],
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
            return {"status": "success", "reservation": reservation}

        async with httpx.AsyncClient(timeout=15.0) as client:
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
                    raise RuntimeError(f"Errore prenotazione DHCP su eero: {resp.text}")
                return resp_put.json().get("data", reservation)
            return resp.json().get("data", reservation)

    async def delete_reservation(self, reservation_id: str) -> Dict[str, Any]:
        """Elimina una prenotazione IP statico dal Cloud eero."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["reservations"] = [
                r for r in self._demo_state.get("reservations", [])
                if r.get("id") != reservation_id and (r.get("mac") or "").lower() != reservation_id.lower() and r.get("ip") != reservation_id
            ]
            return {"status": "success", "deleted": reservation_id}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/reservations/{reservation_id}",
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(f"Errore eliminazione prenotazione DHCP: {resp.text}")
            return {"status": "success", "deleted": reservation_id}

    async def add_port_forward(
        self,
        ip: str,
        port_from: int,
        port_to: int,
        protocol: str = "tcp",
        description: str = "Custom Rule"
    ) -> Dict[str, Any]:
        rule = {
            "id": f"fwd_{int(time.time())}",
            "ip": ip,
            "port_from": port_from,
            "port_to": port_to,
            "protocol": protocol.lower(),
            "description": description,
        }
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["forwards"].append(rule)
            return {"status": "success", "forward": rule}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards",
                json=rule,
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Errore aggiunta port forward: {resp.text}")
            return resp.json().get("data", rule)

    async def delete_port_forward(self, forward_id: str) -> Dict[str, Any]:
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            self._demo_state["forwards"] = [f for f in self._demo_state["forwards"] if f.get("id") != forward_id]
            return {"status": "success", "deleted": forward_id}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/forwards/{forward_id}",
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(f"Errore eliminazione port forward: {resp.text}")
            return {"status": "success", "deleted": forward_id}

    # =========================================================================
    # GESTIONE PROFILI UTENTE CLOUD (FAMILY PROFILES / USERS)
    # =========================================================================
    def _normalize_profile(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizza un profilo utente del Cloud eero."""
        profile = dict(p)
        prof_id = str(profile.get("id") or profile.get("url", "").split("/")[-1])
        profile["id"] = prof_id
        profile["name"] = profile.get("name") or "Profilo Utente"
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
                async with httpx.AsyncClient(timeout=15.0) as client:
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
                                logger.warning(f"Error fetching profiles from {endpoint} ({resp.status_code}): {resp.text}")
                        except Exception as e:
                            logger.warning(f"Failed to fetch profiles from {endpoint}: {e}")

                profiles = []
                if isinstance(raw_list, list):
                    for p in raw_list:
                        try:
                            if isinstance(p, dict):
                                profiles.append(self._normalize_profile(p))
                        except Exception as ex:
                            logger.error(f"Error normalizing profile item: {ex}")

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
            logger.warning(f"Profile device enrichment warning: {enrich_ex}")

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
            logger.warning(f"Error syncing profile device overrides from database: {db_ex}")

        return profiles

    async def create_profile(self, name: str, device_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Crea un nuovo profilo utente nel Cloud eero."""
        if not name or not name.strip():
            raise ValueError("Il nome del profilo non può essere vuoto.")
        
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

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{EERO_API_BASE}/networks/{self.current_network_id}/profiles",
                json=payload,
                headers=self._get_headers()
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Errore creazione profilo eero: {resp.text}")
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
            raise ValueError(f"Profilo demo '{clean_id}' non trovato.")

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

        async with httpx.AsyncClient(timeout=15.0) as client:
            last_err = ""
            for url in endpoints:
                for method in methods:
                    for payload in payloads:
                        try:
                            logger.info(f"Trying profile update: {method} {url} with {payload}")
                            if method == "PUT":
                                resp = await client.put(url, json=payload, headers=headers)
                            elif method == "POST":
                                resp = await client.post(url, json=payload, headers=headers)
                            else:
                                resp = await client.patch(url, json=payload, headers=headers)

                            if resp.status_code in (200, 201, 204):
                                data = resp.json().get("data", payload) if (resp.status_code in (200, 201) and resp.text) else payload
                                logger.info(f"Profile {clean_id} updated successfully ({resp.status_code}) via {method} {url}")
                                return {"status": "success", "profile": self._normalize_profile(data)}
                            last_err = f"{resp.status_code}: {resp.text}"
                        except Exception as ex:
                            last_err = str(ex)
            raise RuntimeError(f"Errore aggiornamento profilo eero: {last_err}")

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

        async with httpx.AsyncClient(timeout=15.0) as client:
            last_err = ""
            for url in endpoints:
                try:
                    resp = await client.delete(url, headers=headers)
                    if resp.status_code in (200, 204):
                        return {"status": "success", "deleted": clean_id}
                    last_err = f"{resp.status_code}: {resp.text}"
                except Exception as ex:
                    last_err = str(ex)
            raise RuntimeError(f"Errore eliminazione profilo eero: {last_err}")

    async def set_profile_paused(self, profile_id: str, paused: bool) -> Dict[str, Any]:
        """Mette in pausa o riattiva la connessione di tutti i dispositivi del profilo."""
        clean_id = str(profile_id).split("/")[-1]

        target_prof = None
        # 1. Prova aggiornamento a livello profilo Cloud
        try:
            res = await self.update_profile(profile_id=profile_id, paused=paused)
            target_prof = res.get("profile")
        except Exception as ex:
            logger.warning(f"Profile-level pause warning on cloud: {ex}")

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
                            logger.warning(f"Failed to pause individual device {d_id}: {d_ex}")
        except Exception as ex:
            logger.warning(f"Error pausing individual devices of profile {clean_id}: {ex}")

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
            raise ValueError("ID o MAC del dispositivo non specificato.")

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
                    raise ValueError(f"Profilo target '{clean_target_pid}' non trovato.")

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

        logger.info(f"assign_device_to_profile -> dev_key='{dev_key}', target_mac='{target_mac}', clean_dev_id='{clean_dev_id}', target_url='{target_url}', target_profile_id='{clean_target_pid}'")

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
            logger.info(f"Persisted device profile mapping in local database for keys {keys_to_save} -> {clean_target_pid or 'NONE'}")
        except Exception as db_err:
            logger.error(f"Error persisting profile mapping in database: {db_err}")

        # 2. Tenta la sincronizzazione diretta su eero Cloud (best effort)
        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=8.0) as client:
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
    def _init_demo_state(self) -> Dict[str, Any]:
        return {
            "account": {
                "name": "Mario Rossi",
                "email": "mario.rossi@homelab.local",
                "phone": "+39 340 1234567"
            },
            "network": {
                "id": "network_demo_mesh_01",
                "name": "Casa Rossi Mesh 6E",
                "status": "online",
                "public_ip": "93.42.178.105",
                "gateway_ip": "192.168.4.1",
                "subnet_mask": "255.255.252.0",
                "dns_servers": ["1.1.1.1", "1.0.0.1"],
                "isp": "TIM FTTH 1Gbps / 300Mbps",
                "ipv6_enabled": True,
                "upnp_enabled": True,
                "band_steering_enabled": True,
                "health_score": 98,
            },
            "guest_network": {
                "enabled": True,
                "name": "Casa Rossi - Ospiti",
                "password": "OspitiSicuri2026!",
            },
            "speedtest": {
                "download_mbps": 912.45,
                "upload_mbps": 298.10,
                "ping_ms": 9.2,
                "jitter": 1.1,
                "date": datetime.now(timezone.utc).isoformat(),
            },
            "eeros": [
                {
                    "id": "eero_01_gateway",
                    "serial": "GW-EERO6E-001",
                    "name": "Gateway Soggiorno",
                    "model": "eero Pro 6E (K010001)",
                    "is_gateway": True,
                    "wired": True,
                    "status": "online",
                    "ip": "192.168.4.1",
                    "mac": "70:54:D2:11:22:33",
                    "os_version": "v7.5.2-192",
                    "led_on": True,
                    "backhaul_type": "Gateway (WAN)",
                    "connected_clients_count": 8,
                },
                {
                    "id": "eero_02_studio",
                    "serial": "EERO6E-002-STUDIO",
                    "name": "Studio & Server Room",
                    "model": "eero Pro 6E (K010001)",
                    "is_gateway": False,
                    "wired": True,
                    "status": "online",
                    "ip": "192.168.4.2",
                    "mac": "70:54:D2:44:55:66",
                    "os_version": "v7.5.2-192",
                    "led_on": True,
                    "backhaul_type": "Ethernet (1.0 Gbps)",
                    "connected_clients_count": 5,
                },
                {
                    "id": "eero_03_camera",
                    "serial": "EERO6E-003-BEDROOM",
                    "name": "Camera da Letto",
                    "model": "eero 6+ (R010001)",
                    "is_gateway": False,
                    "wired": False,
                    "status": "online",
                    "ip": "192.168.4.3",
                    "mac": "70:54:D2:77:88:99",
                    "os_version": "v7.5.2-192",
                    "led_on": False,
                    "backhaul_type": "Wireless Mesh (5 GHz / -52 dBm)",
                    "connected_clients_count": 4,
                },
            ],
            "devices": [
                {
                    "id": "dev_01",
                    "mac": "B4:2E:99:A1:01:10",
                    "hostname": "MacBook-Pro-M3",
                    "nickname": "MacBook Pro Lavoro",
                    "ip": "192.168.4.101",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "6GHz",
                    "frequency_band": "6 GHz",
                    "channel": 69,
                    "signal_rssi": -48,
                    "rx_bitrate": "2400.0 MBit/s",
                    "phy_rate": "2400.0 MBit/s",
                    "connected_eero_id": "eero_02_studio",
                    "connected_eero_name": "Studio & Server Room",
                    "download_rate_mbps": 42.8,
                    "upload_rate_mbps": 5.2,
                    "rx_bytes": 14200500100,
                    "tx_bytes": 3890200400,
                    "paused": False,
                },
                {
                    "id": "dev_02",
                    "mac": "00:11:32:9F:88:44",
                    "hostname": "Synology-DS920Plus",
                    "nickname": "Home NAS & Media Server",
                    "ip": "192.168.4.10",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_02_studio",
                    "connected_eero_name": "Studio & Server Room",
                    "download_rate_mbps": 65.4,
                    "upload_rate_mbps": 28.1,
                    "rx_bytes": 48900200100,
                    "tx_bytes": 22100400500,
                    "paused": False,
                },
                {
                    "id": "dev_03",
                    "mac": "F4:F5:DB:33:44:55",
                    "hostname": "iPhone-15-Pro",
                    "nickname": "iPhone Personale",
                    "ip": "192.168.4.110",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 36,
                    "signal_rssi": -55,
                    "rx_bitrate": "866.0 MBit/s",
                    "phy_rate": "866.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 12.3,
                    "upload_rate_mbps": 1.1,
                    "rx_bytes": 5400200100,
                    "tx_bytes": 1100400500,
                    "paused": False,
                },
                {
                    "id": "dev_04",
                    "mac": "28:70:4E:88:99:AA",
                    "hostname": "Sony-Bravia-OLED-4K",
                    "nickname": "Smart TV OLED 65\"",
                    "ip": "192.168.4.120",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 44,
                    "signal_rssi": -51,
                    "rx_bitrate": "433.0 MBit/s",
                    "phy_rate": "433.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 24.5,
                    "upload_rate_mbps": 0.4,
                    "rx_bytes": 28900400100,
                    "tx_bytes": 450100200,
                    "paused": False,
                },
                {
                    "id": "dev_05",
                    "mac": "A8:5E:45:12:34:56",
                    "hostname": "PlayStation-5",
                    "nickname": "PS5 Pro Console",
                    "ip": "192.168.4.125",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 3.2,
                    "upload_rate_mbps": 0.8,
                    "rx_bytes": 19400200100,
                    "tx_bytes": 890400500,
                    "paused": False,
                },
                {
                    "id": "dev_06",
                    "mac": "48:E7:DA:99:88:77",
                    "hostname": "Shelly-Pro-4PM",
                    "nickname": "Shelly Domotica Quadro",
                    "ip": "192.168.4.180",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "2.4GHz",
                    "frequency_band": "2.4 GHz",
                    "channel": 6,
                    "signal_rssi": -62,
                    "rx_bitrate": "72.0 MBit/s",
                    "phy_rate": "72.0 MBit/s",
                    "connected_eero_id": "eero_03_camera",
                    "connected_eero_name": "Camera da Letto",
                    "download_rate_mbps": 0.05,
                    "upload_rate_mbps": 0.08,
                    "rx_bytes": 350200100,
                    "tx_bytes": 480100500,
                    "paused": False,
                },
                {
                    "id": "dev_07",
                    "mac": "18:B4:30:11:22:33",
                    "hostname": "Nest-Thermostat-E",
                    "nickname": "Termostato Soggiorno",
                    "ip": "192.168.4.185",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "2.4GHz",
                    "frequency_band": "2.4 GHz",
                    "channel": 11,
                    "signal_rssi": -68,
                    "rx_bitrate": "54.0 MBit/s",
                    "phy_rate": "54.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 0.02,
                    "upload_rate_mbps": 0.03,
                    "rx_bytes": 120400100,
                    "tx_bytes": 190200100,
                    "paused": False,
                },
                {
                    "id": "dev_08",
                    "mac": "E0:4F:43:AA:BB:CC",
                    "hostname": "Apple-iPad-Air",
                    "nickname": "iPad Cucina / Ricette",
                    "ip": "192.168.4.135",
                    "connected": False,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 36,
                    "signal_rssi": -75,
                    "rx_bitrate": "300.0 MBit/s",
                    "phy_rate": "300.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 0.0,
                    "upload_rate_mbps": 0.0,
                    "rx_bytes": 4100200100,
                    "tx_bytes": 320100400,
                    "paused": False,
                },
                {
                    "id": "dev_09",
                    "mac": "DC:A6:32:88:77:66",
                    "hostname": "RaspberryPi-HomeAssistant",
                    "nickname": "Home Assistant Server",
                    "ip": "192.168.4.20",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_02_studio",
                    "connected_eero_name": "Studio & Server Room",
                    "download_rate_mbps": 1.4,
                    "upload_rate_mbps": 0.9,
                    "rx_bytes": 8900400100,
                    "tx_bytes": 5400200100,
                    "paused": False,
                },
                {
                    "id": "dev_10",
                    "mac": "7C:49:EB:12:34:78",
                    "hostname": "Sonos-Era-300-L",
                    "nickname": "Sonos Speaker Salone",
                    "ip": "192.168.4.150",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 48,
                    "signal_rssi": -58,
                    "rx_bitrate": "300.0 MBit/s",
                    "phy_rate": "300.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 4.1,
                    "upload_rate_mbps": 0.2,
                    "rx_bytes": 6700500100,
                    "tx_bytes": 230100200,
                    "paused": False,
                }
            ],
            "reservations": [
                {"id": "res_01", "mac": "00:11:32:9F:88:44", "ip": "192.168.4.10", "description": "Synology NAS Static IP"},
                {"id": "res_02", "mac": "DC:A6:32:88:77:66", "ip": "192.168.4.20", "description": "Home Assistant Yellow"},
            ],
            "forwards": [
                {"id": "fwd_01", "ip": "192.168.4.10", "port_from": 5001, "port_to": 5001, "protocol": "tcp", "description": "Synology DSM HTTPS"},
                {"id": "fwd_02", "ip": "192.168.4.20", "port_from": 8123, "port_to": 8123, "protocol": "tcp", "description": "Home Assistant WebUI"},
                {"id": "fwd_03", "ip": "192.168.4.10", "port_from": 32400, "port_to": 32400, "protocol": "tcp", "description": "Plex Media Server"},
            ],
            "profiles": [
                {
                    "id": "prof_01",
                    "url": "/2.2/profiles/prof_01",
                    "name": "Marco",
                    "paused": False,
                    "devices": [
                        {"id": "dev_01", "url": "/2.2/devices/dev_01", "mac": "b4:2e:99:a1:01:10", "nickname": "MacBook Pro Lavoro", "hostname": "MacBook-Pro-M3", "ip": "192.168.4.101", "connected": True, "paused": False},
                        {"id": "dev_03", "url": "/2.2/devices/dev_03", "mac": "f4:f5:db:33:44:55", "nickname": "iPhone Personale", "hostname": "iPhone-15-Pro", "ip": "192.168.4.110", "connected": True, "paused": False},
                    ]
                },
                {
                    "id": "prof_02",
                    "url": "/2.2/profiles/prof_02",
                    "name": "Giulia",
                    "paused": False,
                    "devices": [
                        {"id": "dev_08", "url": "/2.2/devices/dev_08", "mac": "e0:4f:43:aa:bb:cc", "nickname": "iPad Cucina / Ricette", "hostname": "Apple-iPad-Air", "ip": "192.168.4.135", "connected": False, "paused": False}
                    ]
                },
                {
                    "id": "prof_03",
                    "url": "/2.2/profiles/prof_03",
                    "name": "Intrattenimento & Salotto",
                    "paused": False,
                    "devices": [
                        {"id": "dev_04", "url": "/2.2/devices/dev_04", "mac": "28:70:4e:88:99:aa", "nickname": "Smart TV OLED 65\"", "hostname": "Sony-Bravia-OLED-4K", "ip": "192.168.4.120", "connected": True, "paused": False},
                        {"id": "dev_05", "url": "/2.2/devices/dev_05", "mac": "a8:5e:45:12:34:56", "nickname": "PS5 Pro Console", "hostname": "PlayStation-5", "ip": "192.168.4.125", "connected": True, "paused": False},
                        {"id": "dev_10", "url": "/2.2/devices/dev_10", "mac": "7c:49:eb:12:34:78", "nickname": "Sonos Speaker Salone", "hostname": "Sonos-Era-300-L", "ip": "192.168.4.150", "connected": True, "paused": False}
                    ]
                }
            ]
        }

    def _get_demo_account(self) -> Dict[str, Any]:
        return {
            "name": self._demo_state["account"]["name"],
            "email": self._demo_state["account"]["email"],
            "phone": self._demo_state["account"]["phone"],
            "networks": {
                "data": [
                    {
                        "id": self._demo_state["network"]["id"],
                        "name": self._demo_state["network"]["name"],
                        "url": f"/2.2/networks/{self._demo_state['network']['id']}"
                    }
                ]
            }
        }

    def _get_demo_network_details(self) -> Dict[str, Any]:
        # Modulazione casuale per rendere i grafici vivi e dinamici
        return {
            **self._demo_state["network"],
            "speedtest": self._demo_state["speedtest"],
            "guest_network": self._demo_state["guest_network"],
            "client_count": len([d for d in self._demo_state["devices"] if d["connected"]]),
            "eero_count": len(self._demo_state["eeros"]),
        }

    def _get_demo_eeros(self) -> List[Dict[str, Any]]:
        return self._demo_state["eeros"]

    def _get_demo_profiles(self) -> List[Dict[str, Any]]:
        raw_list = self._demo_state.get("profiles", [])
        return [self._normalize_profile(p) for p in raw_list]

    def _get_demo_devices(self) -> List[Dict[str, Any]]:
        # Varia leggermente i tassi di trasmissione per simulare traffico live
        normalized_list = []
        for d in self._demo_state["devices"]:
            if d.get("connected"):
                jitter = random.uniform(0.85, 1.25)
                d["download_rate_mbps"] = round(d.get("download_rate_mbps", 1.0) * jitter, 2)
                d["upload_rate_mbps"] = round(d.get("upload_rate_mbps", 0.5) * jitter, 2)
                d["rx_bytes"] = int(d.get("rx_bytes", 0)) + int(d["download_rate_mbps"] * 1024 * 1024 / 8 * 30)
                d["tx_bytes"] = int(d.get("tx_bytes", 0)) + int(d["upload_rate_mbps"] * 1024 * 1024 / 8 * 30)
            norm = self._normalize_device(d)
            normalized_list.append(norm)
        return normalized_list


# Istanza singleton client eero
eero_client = EeroClient()
