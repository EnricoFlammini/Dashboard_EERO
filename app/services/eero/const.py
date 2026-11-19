"""
Constants and static mapping utilities for eero Client.
Includes speed parsing, formatters, device category / icon mappings, and AdGuard Home tag helpers.
"""
from typing import Any, Optional, Tuple, List
import logging
import ipaddress

logger = logging.getLogger(__name__)

EERO_API_BASE = "https://api-user.e2ro.com/2.2"
IPV6_ULA_NET = ipaddress.IPv6Network("fc00::/7")
_IPV6_ULA_NET = IPV6_ULA_NET


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

    The category strings are stable identifiers, not display text: they are stored in
    device_metadata.category (user choice) and matched by filters, analytics and the
    automations router, and the frontend maps them to t('devices.cat_*') labels. Do not
    rename them; add a new language by translating the devices.cat_* keys instead.
    Icons: laptop, smartphone, tablet, tv, gamepad, iot, camera, speaker, server, printer, device
    """
    t = str(raw_type or "").strip().lower()
    n = str(model_or_name or "").strip().lower()

    # 1. Computer & Printers
    if "printer" in t or "printer" in n or "stampante" in n:
        return ("Computer", "printer")

    if any(k in t for k in ("laptop", "notebook", "macbook")) or \
       any(k in n for k in ("macbook", "thinkpad", "laptop", "notebook")):
        return ("Computer", "laptop")

    if any(k in t for k in ("desktop", "computer", "pc", "imac", "workstation", "tower", "mac_mini", "macmini", "mac_studio", "macstudio", "mac_pro", "macpro")) or \
       any(k in n for k in ("imac", "desktop", "pc-", "-pc", "pc_", "_pc", "workstation", "tower", "mac mini", "macmini", "mac studio", "mac pro")):
        return ("Computer", "pc")

    if t in ("computer", "pc") or "computer" in n or "pc" in n:
        return ("Computer", "pc")

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

    if icon_lower in ("pc", "desktop"):
        return ["device_pc"]
    if icon_lower in ("laptop", "macbook"):
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
