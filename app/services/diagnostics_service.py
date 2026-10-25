import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.i18n import SUPPORTED_LANGUAGES, tr

logger = logging.getLogger(__name__)


def _it_en(key: str, **params: Any) -> Tuple[str, str]:
    """Returns the (Italian, English) catalog texts for the paired *_it / *_en payload fields."""
    return tr(key, lang="it", **params), tr(key, lang="en", **params)


def with_i18n_maps(obj: Any) -> Any:
    """Adds a ``<field>_i18n`` map next to every legacy ``<field>_it`` / ``<field>_en`` pair.

    Walks dicts and lists in place. The frontend reads the map through
    ``localized(obj, field)`` and keeps working for any language in
    SUPPORTED_LANGUAGES, while the legacy pair stays for older clients.
    """
    if isinstance(obj, list):
        for item in obj:
            with_i18n_maps(item)
    elif isinstance(obj, dict):
        for key in list(obj.keys()):
            if key.endswith("_en") and f"{key[:-3]}_it" in obj and f"{key[:-3]}_i18n" not in obj:
                base = key[:-3]
                obj[f"{base}_i18n"] = {lang: obj[f"{base}_{lang}"] for lang in SUPPORTED_LANGUAGES if f"{base}_{lang}" in obj}
        for value in obj.values():
            if isinstance(value, (dict, list)):
                with_i18n_maps(value)
    return obj

# Pattern per identificare apparati wireless tipicamente mobili (smartphone, tablet, laptop, smartwatch)
MOBILE_DEVICE_PATTERNS = [
    r"iphone",
    r"android",
    r"galaxy",
    r"pixel",
    r"phone",
    r"smartphone",
    r"mobile",
    r"ipad",
    r"tablet",
    r"tab",
    r"macbook",
    r"laptop",
    r"notebook",
    r"thinkpad",
    r"surface",
    r"watch",
]

# Pattern per apparati fissi o IoT da escludere tassativamente dal Roaming Advisor
STATIC_DEVICE_PATTERNS = [
    r"tv",
    r"apple\s*tv",
    r"bravia",
    r"oled",
    r"firetv",
    r"chromecast",
    r"printer",
    r"stampante",
    r"plug",
    r"presa",
    r"switch",
    r"relay",
    r"shelly",
    r"sonoff",
    r"sensor",
    r"sensore",
    r"thermostat",
    r"termostato",
    r"camera",
    r"telecamera",
    r"cam",
    r"doorbell",
    r"speaker",
    r"echo",
    r"alexa",
    r"homepod",
    r"sonos",
    r"nas",
    r"synology",
    r"qnap",
    r"server",
    r"desktop",
    r"pc-fisso",
    r"workstation",
    r"console",
    r"playstation",
    r"ps[45]",
    r"xbox",
]

# Pattern per identificare categorie IoT / Smart Home per il monitoraggio notturno
IOT_DEVICE_PATTERNS = [
    r"shelly",
    r"sonoff",
    r"tapo",
    r"tuya",
    r"hue",
    r"camera",
    r"telecamera",
    r"cam",
    r"thermostat",
    r"termostato",
    r"sensor",
    r"sensore",
    r"plug",
    r"presa",
    r"switch",
    r"bulb",
    r"lampadina",
    r"vacuum",
    r"roborock",
    r"roomba",
    r"ring",
    r"nest",
    r"doorbell",
    r"esp[_-]?",
    r"esp32",
    r"esp8266",
    r"homeassistant",
    r"wled",
    r"zigbee",
    r"aqara",
]


def is_mobile_client(device: Any, hostname: Optional[str] = None) -> bool:
    """Verifica se il dispositivo è un apparato wireless portatile soggetto a roaming fisico."""
    if isinstance(device, str):
        device = {"custom_name": device, "hostname": hostname or "", "wireless": True}
    elif not isinstance(device, dict):
        return False

    if not device.get("wireless", True):
        return False

    dev_type = str(device.get("device_type") or device.get("category") or "").lower()
    if dev_type in ("phone", "smartphone", "tablet", "laptop", "wearable", "watch"):
        return True

    name_str = " ".join([
        str(device.get("custom_name") or ""),
        str(device.get("nickname") or ""),
        str(device.get("hostname") or ""),
        str(device.get("manufacturer") or ""),
        str(device.get("model") or ""),
    ]).lower()

    # Se corrisponde a pattern statico, scartare
    for p in STATIC_DEVICE_PATTERNS:
        if re.search(r"\b" + p + r"\b", name_str):
            return False

    # Verifica corrispondenza con pattern mobile
    for p in MOBILE_DEVICE_PATTERNS:
        if re.search(r"\b" + p + r"\b", name_str):
            return True

    return False


def is_iot_client(device: Any, hostname: Optional[str] = None) -> bool:
    """Verifica se il dispositivo appartiene all'ecosistema Smart Home / IoT / Domotica / Cam."""
    if isinstance(device, str):
        device = {"custom_name": device, "hostname": hostname or ""}
    elif not isinstance(device, dict):
        return False

    category = str(device.get("device_type") or device.get("category") or "").lower()
    if category in ("smart_home", "iot", "camera", "sensor", "plug", "appliance"):
        return True

    name_str = " ".join([
        str(device.get("custom_name") or ""),
        str(device.get("nickname") or ""),
        str(device.get("hostname") or ""),
        str(device.get("manufacturer") or ""),
    ]).lower()

    for p in IOT_DEVICE_PATTERNS:
        if re.search(r"\b" + p + r"\b", name_str):
            return True
    return False


class DiagnosticsService:
    """Servizio per l'analisi intelligente della rete eeroOS, la diagnosi discorsiva in linguaggio

    naturale, il rilevamento degli Sticky Clients (Roaming Advisor) e delle anomalie IoT.
    """

    def analyze_roaming_advisor(
        self,
        devices: List[Dict[str, Any]],
        eeros: List[Dict[str, Any]],
        historic_affinity: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Identifica i client mobili agganciati a nodi mesh distanti con RSSI debole (<= -75 dBm)

        quando sono disponibili nodi mesh alternativi migliori (Issue #43).
        """
        # Se c'è solo 1 nodo o nessun nodo alternativo, il roaming non si applica
        online_eeros = [
            e for e in eeros
            if str(e.get("status", "online")).lower() in ("online", "green", "connected") and (e.get("name") or e.get("location"))
        ]
        if len(online_eeros) < 2:
            return {"sticky_count": 0, "devices": []}

        sticky_devices: List[Dict[str, Any]] = []

        for d in devices:
            if not d.get("connected") or not d.get("wireless"):
                continue

            rssi = d.get("signal_rssi")
            if rssi is None or not isinstance(rssi, (int, float)):
                continue

            # Rileviamo solo dispositivi mobili con segnale degradato (<= -75 dBm)
            if rssi > -75 or not is_mobile_client(d):
                continue

            curr_node_name = str(d.get("connected_eero_name") or "").strip()
            mac = str(d.get("mac") or d.get("mac_address") or "").lower().strip()
            dev_name = d.get("custom_name") or d.get("nickname") or d.get("hostname") or mac

            # Cerchiamo un nodo alternativo consigliato
            suggested_node = None
            delta_est = 20

            # 1. Controllo affinità storica dal database
            if historic_affinity and mac in historic_affinity:
                hist = historic_affinity[mac]
                hist_node = hist.get("best_node")
                hist_rssi = hist.get("avg_rssi", -60)
                if hist_node and hist_node.lower() != curr_node_name.lower():
                    suggested_node = hist_node
                    delta_est = max(15, int(abs(hist_rssi - rssi)))

            # 2. Se non abbiamo dati storici, suggeriamo il nodo mesh attivo non sovraccarico
            if not suggested_node:
                alt_nodes = [
                    e for e in online_eeros
                    if str(e.get("name") or e.get("location") or "").lower() != curr_node_name.lower()
                ]
                if alt_nodes:
                    # Preferisci un nodo con backhaul cablato o con minor carico client
                    alt_nodes.sort(key=lambda x: x.get("connected_clients_count", 0))
                    suggested_node = alt_nodes[0].get("name") or alt_nodes[0].get("location") or tr("diagnostics.fallback_secondary_node")

            severity = "critical" if rssi <= -82 else "warning"
            advice_it, advice_en = (
                tr(
                    "diagnostics.advice_sticky",
                    lang=lang,
                    device=dev_name,
                    node=curr_node_name,
                    rssi=rssi,
                    suggested=suggested_node or tr("diagnostics.fallback_nearby_node", lang=lang),
                )
                for lang in SUPPORTED_LANGUAGES
            )

            suggested_i18n = {
                lang: suggested_node or tr("diagnostics.fallback_nearby_node", lang=lang)
                for lang in SUPPORTED_LANGUAGES
            }

            advisor_data = {
                "mac": mac,
                "name": dev_name,
                "hostname": d.get("hostname") or dev_name,
                "current_rssi": rssi,
                "connected_eero_id": d.get("connected_eero_id"),
                "connected_eero_name": curr_node_name,
                "suggested_eero_name": suggested_node or tr("diagnostics.fallback_nearby_node"),
                "suggested_eero_name_i18n": suggested_i18n,
                "estimated_delta_dbm": delta_est,
                "severity": severity,
                "advice_it": advice_it,
                "advice_en": advice_en,
            }

            # Assegna il badge direttamente all'oggetto device
            with_i18n_maps(advisor_data)
            d["roaming_advisor"] = advisor_data
            sticky_devices.append(advisor_data)

        return {
            "sticky_count": len(sticky_devices),
            "devices": sticky_devices,
        }

    def generate_health_summary(
        self,
        health_details: Dict[str, Any],
        network_details: Dict[str, Any],
        eeros: List[Dict[str, Any]],
        devices: List[Dict[str, Any]],
        roaming_info: Optional[Dict[str, Any]] = None,
        recent_anomalies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Genera una diagnosi discorsiva contestuale in linguaggio naturale (Italiano e Inglese)

        e una Actionable Remediation Checklist ordinata per priorità.
        """
        score = health_details.get("score", 100)
        status = health_details.get("status", "optimal")
        penalties = health_details.get("penalties") or []

        # 1. Overview Narrative
        if score >= 90:
            overview_it, overview_en = _it_en("diagnostics.overview_excellent")
        elif score >= 70:
            overview_it, overview_en = _it_en("diagnostics.overview_good")
        else:
            overview_it, overview_en = _it_en("diagnostics.overview_critical")

        # 2. Penalty Explanations Narrative
        narrative_it_parts: List[str] = []
        narrative_en_parts: List[str] = []
        checklist: List[Dict[str, Any]] = []

        # Analisi Nodi Offline
        offline_pen = next((
            p for p in penalties
            if p.get("id") == "offline_nodes" or "offline" in str(p.get("id") or "").lower() or "offline" in str(p.get("factor") or "").lower()
        ), None)
        if offline_pen:
            aff = offline_pen.get("affected_items") or []
            names_it, names_en = (", ".join(aff) if aff else tr("diagnostics.fallback_some_nodes", lang=lang) for lang in ("it", "en"))
            narrative_it_parts.append(tr("diagnostics.narrative_offline_nodes", lang="it", names=names_it))
            narrative_en_parts.append(tr("diagnostics.narrative_offline_nodes", lang="en", names=names_en))
            checklist.append({
                "id": "fix_offline_nodes",
                "priority": "critical",
                "category": "mesh",
                "title_it": tr("diagnostics.check_offline_nodes_title", lang="it", names=names_it),
                "title_en": tr("diagnostics.check_offline_nodes_title", lang="en", names=names_en),
                "description_it": tr("diagnostics.check_offline_nodes_desc", lang="it"),
                "description_en": tr("diagnostics.check_offline_nodes_desc", lang="en"),
                "icon": "wifi-off",
            })

        # Analisi Backhaul Degradato o Cavi 100 Mbps
        backhaul_pen = next((
            p for p in penalties
            if p.get("id") == "degraded_backhaul" or "backhaul" in str(p.get("id") or "").lower()
            or "100" in str(p.get("factor") or "") or "100" in str(p.get("description") or "")
        ), None)
        if backhaul_pen:
            aff = backhaul_pen.get("affected_items") or []
            items_str = "; ".join(aff)
            narrative_it, narrative_en = _it_en("diagnostics.narrative_degraded_backhaul", items=items_str)
            narrative_it_parts.append(narrative_it)
            narrative_en_parts.append(narrative_en)
            title_it, title_en = _it_en("diagnostics.check_degraded_backhaul_title")
            description_it, description_en = _it_en("diagnostics.check_degraded_backhaul_desc")
            checklist.append({
                "id": "fix_degraded_backhaul",
                "priority": "high",
                "category": "cabling",
                "title_it": title_it,
                "title_en": title_en,
                "description_it": description_it,
                "description_en": description_en,
                "icon": "cable",
            })

        # Analisi Segnale Client Debole
        client_pen = next((p for p in penalties if p.get("id") == "weak_client_signal"), None)
        if client_pen:
            aff = client_pen.get("affected_items") or []
            cnt = len(aff)
            devices_str = f"{', '.join(aff[:3])}{'...' if len(aff) > 3 else ''}"
            narrative_it, narrative_en = _it_en("diagnostics.narrative_weak_clients", count=cnt, devices=devices_str)
            narrative_it_parts.append(narrative_it)
            narrative_en_parts.append(narrative_en)
            title_it, title_en = _it_en("diagnostics.check_weak_clients_title")
            description_it, description_en = _it_en("diagnostics.check_weak_clients_desc")
            checklist.append({
                "id": "fix_weak_clients",
                "priority": "medium",
                "category": "clients",
                "title_it": title_it,
                "title_en": title_en,
                "description_it": description_it,
                "description_en": description_en,
                "icon": "signal",
            })

        # Analisi Affollamento 2.4 GHz
        band_pen = next((p for p in penalties if p.get("id") == "band_24_crowding"), None)
        if band_pen:
            narrative_it, narrative_en = _it_en("diagnostics.narrative_band_24")
            narrative_it_parts.append(narrative_it)
            narrative_en_parts.append(narrative_en)
            title_it, title_en = _it_en("diagnostics.check_band_steering_title")
            description_it, description_en = _it_en("diagnostics.check_band_steering_desc")
            checklist.append({
                "id": "enable_band_steering",
                "priority": "low",
                "category": "spectrum",
                "title_it": title_it,
                "title_en": title_en,
                "description_it": description_it,
                "description_en": description_en,
                "icon": "radio",
            })

        # Analisi Roaming Advisor
        if roaming_info and roaming_info.get("sticky_count", 0) > 0:
            stk_cnt = roaming_info["sticky_count"]
            stk_devs = roaming_info.get("devices", [])
            dev_names = ", ".join(d.get("name") for d in stk_devs[:3])
            narrative_it, narrative_en = _it_en("diagnostics.narrative_sticky_clients", count=stk_cnt, devices=dev_names)
            narrative_it_parts.append(narrative_it)
            narrative_en_parts.append(narrative_en)
            title_it, title_en = _it_en("diagnostics.check_sticky_clients_title", count=stk_cnt)
            description_it, description_en = _it_en("diagnostics.check_sticky_clients_desc")
            checklist.append({
                "id": "resolve_sticky_clients",
                "priority": "medium",
                "category": "clients",
                "title_it": title_it,
                "title_en": title_en,
                "description_it": description_it,
                "description_en": description_en,
                "icon": "refresh-cw",
            })

        # Analisi Anomalie Traffico Notturno IoT
        if recent_anomalies:
            crit_anom = [a for a in recent_anomalies if a.get("severity") in ("critical", "warning")]
            if crit_anom:
                anom_names = ", ".join(a.get("hostname") or a.get("mac_address") for a in crit_anom[:2])
                narrative_it, narrative_en = _it_en("diagnostics.narrative_iot_anomaly", devices=anom_names)
                narrative_it_parts.append(narrative_it)
                narrative_en_parts.append(narrative_en)
                title_it, title_en = _it_en("diagnostics.check_iot_anomaly_title", devices=anom_names)
                description_it, description_en = _it_en("diagnostics.check_iot_anomaly_desc")
                checklist.append({
                    "id": "investigate_iot_anomaly",
                    "priority": "high",
                    "category": "security",
                    "title_it": title_it,
                    "title_en": title_en,
                    "description_it": description_it,
                    "description_en": description_en,
                    "icon": "alert-triangle",
                })

        # Se non ci sono penalità, aggiungi checklist ottimale
        if not checklist:
            title_it, title_en = _it_en("diagnostics.check_optimal_title")
            description_it, description_en = _it_en("diagnostics.check_optimal_desc")
            checklist.append({
                "id": "network_optimal",
                "priority": "low",
                "category": "mesh",
                "title_it": title_it,
                "title_en": title_en,
                "description_it": description_it,
                "description_en": description_en,
                "icon": "check-circle",
            })

        narrative_it = " ".join(narrative_it_parts) if narrative_it_parts else tr("diagnostics.narrative_none", lang="it")
        narrative_en = " ".join(narrative_en_parts) if narrative_en_parts else tr("diagnostics.narrative_none", lang="en")

        return with_i18n_maps({
            "score": score,
            "status": status,
            "overview_it": overview_it,
            "overview_en": overview_en,
            "narrative_it": narrative_it,
            "narrative_en": narrative_en,
            "checklist": checklist,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def detect_iot_night_anomalies(
        self,
        devices: List[Dict[str, Any]],
        usage_history_rows: Optional[List[Dict[str, Any]]] = None,
        is_demo: bool = False,
        demo_mode: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Analizza il traffico dati notturno (01:00 - 06:00) per rilevare outlier statistici

        e picchi anomali su apparati IoT, sensori domotici e telecamere.
        """
        if demo_mode is not None:
            is_demo = demo_mode
        if usage_history_rows is None:
            usage_history_rows = []

        anomalies: List[Dict[str, Any]] = []

        if is_demo:
            # In modalità demo, restituisce 2 anomalie realistiche per dimostrare la feature
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT03:45:00Z")
            return with_i18n_maps([
                {
                    "mac_address": "dc:a6:32:88:77:66",
                    "hostname": "Telecamera Giardino Esterno",
                    "device_name": "Telecamera Giardino Esterno",
                    "device_category": "camera",
                    "anomaly_type": "excessive_upload",
                    "megabytes_transferred": 1420.5,
                    "observed_mb": 1420.5,
                    "baseline_megabytes": 15.0,
                    "baseline_mb": 15.0,
                    "severity": "critical",
                    "description_it": tr("diagnostics.demo_anomaly_camera", lang="it"),
                    "description_en": tr("diagnostics.demo_anomaly_camera", lang="en"),
                    "timestamp": now,
                    "is_demo": 1,
                },
                {
                    "mac_address": "48:e7:da:99:88:77",
                    "hostname": "Shelly Domotica Quadro",
                    "device_name": "Shelly Domotica Quadro",
                    "device_category": "smart_home",
                    "anomaly_type": "unexpected_activity",
                    "megabytes_transferred": 340.2,
                    "observed_mb": 340.2,
                    "baseline_megabytes": 2.5,
                    "baseline_mb": 2.5,
                    "severity": "warning",
                    "description_it": tr("diagnostics.demo_anomaly_relay", lang="it"),
                    "description_en": tr("diagnostics.demo_anomaly_relay", lang="en"),
                    "timestamp": now,
                    "is_demo": 1,
                }
            ])

        # Analisi live su righe storiche
        if not usage_history_rows:
            return anomalies

        # Mappa MAC -> device info
        dev_map = {
            str(d.get("mac") or d.get("mac_address") or "").lower().strip(): d
            for d in devices
        }

        # Raggruppa campioni notturni per MAC
        night_samples_by_mac: Dict[str, List[float]] = {}
        for row in usage_history_rows:
            ts_str = str(row.get("timestamp") or "")
            try:
                # Estrai ora: formato atteso 'YYYY-MM-DD HH:MM:SS' o ISO
                if "T" in ts_str:
                    hour = int(ts_str.split("T")[1].split(":")[0])
                elif " " in ts_str:
                    hour = int(ts_str.split(" ")[1].split(":")[0])
                else:
                    continue
            except Exception:
                continue

            # Fascia notturna: 01:00 - 05:59
            if 1 <= hour < 6:
                mac = str(row.get("mac_address") or "").lower().strip()
                if mac not in dev_map:
                    continue
                # Controlla se è un apparato IoT
                if not is_iot_client(dev_map[mac]):
                    continue

                rx_mb = float(row.get("rx_bytes") or 0.0) / (1024 * 1024)
                tx_mb = float(row.get("tx_bytes") or 0.0) / (1024 * 1024)
                tot_mb = rx_mb + tx_mb
                night_samples_by_mac.setdefault(mac, []).append(tot_mb)

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for mac, volumes in night_samples_by_mac.items():
            if not volumes:
                continue
            max_vol = max(volumes)
            min_vol = min(volumes)
            delta_vol = max(0.0, max_vol - min_vol)
            dev = dev_map.get(mac, {})
            h_name = dev.get("custom_name") or dev.get("nickname") or dev.get("hostname") or mac
            cat = str(dev.get("category") or dev.get("device_type") or "iot")

            # Soglia anomalia: > 150 MB per sensori/domotica, o > 1.2 GB per telecamere
            threshold = 1200.0 if "cam" in h_name.lower() or cat == "camera" else 150.0

            if delta_vol > threshold:
                sev = "critical" if delta_vol > (threshold * 2) else "warning"
                description_it, description_en = _it_en(
                    "diagnostics.anomaly_night_traffic",
                    observed=f"{delta_vol:.1f}",
                    threshold=f"{threshold:.0f}",
                    device=h_name,
                )
                anom = {
                    "mac_address": mac,
                    "hostname": h_name,
                    "device_category": cat,
                    "anomaly_type": "excessive_upload" if "cam" in h_name.lower() else "unexpected_activity",
                    "megabytes_transferred": round(delta_vol, 1),
                    "baseline_megabytes": 10.0,
                    "severity": sev,
                    "description_it": description_it,
                    "description_en": description_en,
                    "timestamp": now_str,
                    "is_demo": 0,
                }
                anomalies.append(anom)

        return with_i18n_maps(anomalies)


# Istanza singleton del servizio
diagnostics_service = DiagnosticsService()
