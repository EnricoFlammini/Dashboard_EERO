import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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
                    suggested_node = alt_nodes[0].get("name") or alt_nodes[0].get("location") or "Nodo Secondario"

            severity = "critical" if rssi <= -82 else "warning"

            advisor_data = {
                "mac": mac,
                "name": dev_name,
                "hostname": d.get("hostname") or dev_name,
                "current_rssi": rssi,
                "connected_eero_id": d.get("connected_eero_id"),
                "connected_eero_name": curr_node_name,
                "suggested_eero_name": suggested_node or "Nodo Mesh Vicino",
                "estimated_delta_dbm": delta_est,
                "severity": severity,
                "advice_it": (
                    f"Il dispositivo portatile '{dev_name}' è agganciato al nodo '{curr_node_name}' con segnale critico "
                    f"({rssi} dBm). Si consiglia di disattivare e riattivare il Wi-Fi sul dispositivo per forzare il roaming "
                    f"TrueMesh 802.11k/v verso '{suggested_node}'."
                ),
                "advice_en": (
                    f"Mobile device '{dev_name}' is stuck on node '{curr_node_name}' with weak signal "
                    f"({rssi} dBm). Toggle Wi-Fi on the device to trigger 802.11k/v TrueMesh roaming "
                    f"towards '{suggested_node}'."
                ),
            }

            # Assegna il badge direttamente all'oggetto device
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
            overview_it = (
                "La rete mesh eero opera con stabilità ed efficienza eccellenti. Tutti i principali parametri "
                "di sincronizzazione TrueMesh, la qualità del segnale client e la latenza WAN verso l'ISP "
                "risultano ottimali."
            )
            overview_en = (
                "The eero mesh network is operating with excellent stability and efficiency. All primary "
                "TrueMesh synchronization parameters, client signal quality, and WAN latency to your ISP "
                "are optimal."
            )
        elif score >= 70:
            overview_it = (
                "La rete eero è pienamente operativa, ma presenta alcune inefficienze localizzate che impediscono "
                "di raggiungere il massimo rendimento. Sono stati identificati fattori minori di attenuazione "
                "o sbilanciamento delle frequenze."
            )
            overview_en = (
                "The eero network is fully functional, but exhibits localized inefficiencies preventing peak "
                "throughput. Minor signal attenuation or band balance factors were detected."
            )
        else:
            overview_it = (
                "La rete evidenzia criticità significative che impattano la qualità dell'esperienza utente. "
                "Si raccomanda di intervenire sui nodi o collegamenti segnalati per ripristinare la piena "
                "stabilità della copertura mesh."
            )
            overview_en = (
                "The network exhibits significant criticalities impacting user experience quality. Immediate "
                "action on reported nodes or links is recommended to restore full mesh coverage stability."
            )

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
            names_str = ", ".join(aff) if aff else "uno o più nodi"
            narrative_it_parts.append(
                f"⚠️ **Nodi Disconnessi:** I nodi mesh ({names_str}) risultano irraggiungibili o spenti, "
                f"riducendo il raggio di copertura complessivo dell'abitazione."
            )
            narrative_en_parts.append(
                f"⚠️ **Disconnected Nodes:** Mesh node(s) ({names_str}) are offline or unreachable, "
                f"reducing overall wireless coverage."
            )
            checklist.append({
                "id": "fix_offline_nodes",
                "priority": "critical",
                "category": "mesh",
                "title_it": f"Ripristina connettività nodi ({names_str})",
                "title_en": f"Restore connectivity for nodes ({names_str})",
                "description_it": "Controlla l'alimentatore, la presa di corrente e l'eventuale cavo Ethernet a monte.",
                "description_en": "Check power adapter, electrical outlet, and upstream Ethernet cabling.",
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
            narrative_it_parts.append(
                f"🔌 **Backhaul Degradato:** Si riscontra un collegamento sottodimensionato su: {items_str}. "
                f"Se la velocità è limitata a 100 Mbps, uno switch di rete o un cavo Cat5/Cat6 difettoso sta strozzando la banda Gigabit."
            )
            narrative_en_parts.append(
                f"🔌 **Degraded Backhaul:** Sub-optimal backhaul link detected on: {items_str}. "
                f"If link negotiates at 100 Mbps, a legacy switch or faulty Cat5/Cat6 cable is throttling Gigabit throughput."
            )
            checklist.append({
                "id": "fix_degraded_backhaul",
                "priority": "high",
                "category": "cabling",
                "title_it": "Sostituisci cavi Ethernet o riposiziona beacon",
                "title_en": "Replace Ethernet cabling or reposition beacons",
                "description_it": "Verifica che i cavi LAN siano almeno Cat 5e/Cat 6 a 8 poli e che le porte degli switch supportino 1 Gbps / 2.5 Gbps.",
                "description_en": "Verify that LAN cables are Cat 5e/Cat 6 with all 8 pins active and switch ports support 1 Gbps / 2.5 Gbps.",
                "icon": "cable",
            })

        # Analisi Segnale Client Debole
        client_pen = next((p for p in penalties if p.get("id") == "weak_client_signal"), None)
        if client_pen:
            aff = client_pen.get("affected_items") or []
            cnt = len(aff)
            narrative_it_parts.append(
                f"📶 **Client con Segnale Debole:** {cnt} dispositivo/i presentano un segnale RSSI inferiore a -75 dBm "
                f"({', '.join(aff[:3])}{'...' if len(aff) > 3 else ''}), con potenziale aumento di latenza e ritrasmissione pacchetti."
            )
            narrative_en_parts.append(
                f"📶 **Weak Client Signal:** {cnt} device(s) have RSSI below -75 dBm "
                f"({', '.join(aff[:3])}{'...' if len(aff) > 3 else ''}), increasing retransmission rate and latency."
            )
            checklist.append({
                "id": "fix_weak_clients",
                "priority": "medium",
                "category": "clients",
                "title_it": "Ottimizza la posizione degli apparati periferici",
                "title_en": "Optimize peripheral devices positioning",
                "description_it": "Avvicina i client con segnale critico o valuta l'aggiunta di un nodo mesh per coprire eventuali zone d'ombra.",
                "description_en": "Relocate critical clients closer or consider adding a mesh node to bridge dead zones.",
                "icon": "signal",
            })

        # Analisi Affollamento 2.4 GHz
        band_pen = next((p for p in penalties if p.get("id") == "band_24_crowding"), None)
        if band_pen:
            narrative_it_parts.append(
                "📡 **Affollamento Spettro 2.4 GHz:** Oltre il 70% dei dispositivi wireless è attestato sulla frequenza 2.4 GHz, "
                "più soggetta a interferenze e con ampiezza di canale ridotta rispetto a 5 GHz e 6 GHz."
            )
            narrative_en_parts.append(
                "📡 **2.4 GHz Band Crowding:** Over 70% of wireless clients are operating on the 2.4 GHz band, "
                "which is prone to interference and offers lower spectral efficiency than 5 GHz and 6 GHz."
            )
            checklist.append({
                "id": "enable_band_steering",
                "priority": "low",
                "category": "spectrum",
                "title_it": "Attiva Band Steering / Client Steering",
                "title_en": "Enable Band Steering / Client Steering",
                "description_it": "Consente a eero TrueMesh di instradare automaticamente i dispositivi dual-band compatibili sulle frequenze più veloci a 5 GHz e 6 GHz.",
                "description_en": "Allows eero TrueMesh to steer capable dual-band clients towards faster 5 GHz and 6 GHz frequencies.",
                "icon": "radio",
            })

        # Analisi Roaming Advisor
        if roaming_info and roaming_info.get("sticky_count", 0) > 0:
            stk_cnt = roaming_info["sticky_count"]
            stk_devs = roaming_info.get("devices", [])
            dev_names = ", ".join(d.get("name") for d in stk_devs[:3])
            narrative_it_parts.append(
                f"🔄 **Roaming Advisor (Sticky Clients):** Rilevati {stk_cnt} dispositivi mobili ({dev_names}) "
                f"agganciati a nodi distanti con segnale debole pur disponendo di nodi alternativi più vicini."
            )
            narrative_en_parts.append(
                f"🔄 **Roaming Advisor (Sticky Clients):** Detected {stk_cnt} mobile device(s) ({dev_names}) "
                f"clinging to distant nodes with poor signal despite closer mesh nodes being available."
            )
            checklist.append({
                "id": "resolve_sticky_clients",
                "priority": "medium",
                "category": "clients",
                "title_it": f"Forza riassociazione Wi-Fi per {stk_cnt} client",
                "title_en": f"Force Wi-Fi re-association for {stk_cnt} client(s)",
                "description_it": "Spegni e riaccendi il Wi-Fi sui dispositivi mobili segnalati per agganciarli al nodo con segnale ottimale.",
                "description_en": "Toggle Wi-Fi on the flagged mobile devices to trigger 802.11k/v roaming to the closest node.",
                "icon": "refresh-cw",
            })

        # Analisi Anomalie Traffico Notturno IoT
        if recent_anomalies:
            crit_anom = [a for a in recent_anomalies if a.get("severity") in ("critical", "warning")]
            if crit_anom:
                anom_names = ", ".join(a.get("hostname") or a.get("mac_address") for a in crit_anom[:2])
                narrative_it_parts.append(
                    f"🌙 **Traffico Notturno IoT Anomalo:** Rilevato volume dati anomalo nelle ore notturne (01:00 - 06:00) "
                    f"su: {anom_names}. Verificare lo stato del firmware o eventuali streaming/backup non previsti."
                )
                narrative_en_parts.append(
                    f"🌙 **Unusual Night IoT Traffic:** Abnormal data volume recorded during night hours (01:00 - 06:00) "
                    f"on: {anom_names}. Check device firmware or unintended cloud uploads/streaming."
                )
                checklist.append({
                    "id": "investigate_iot_anomaly",
                    "priority": "high",
                    "category": "security",
                    "title_it": f"Ispeziona traffico notturno per {anom_names}",
                    "title_en": f"Inspect night traffic for {anom_names}",
                    "description_it": "Verifica le impostazioni di registrazione cloud o la sicurezza degli apparati domotici coinvolti.",
                    "description_en": "Verify cloud recording settings and firmware integrity of the involved smart devices.",
                    "icon": "alert-triangle",
                })

        # Se non ci sono penalità, aggiungi checklist ottimale
        if not checklist:
            checklist.append({
                "id": "network_optimal",
                "priority": "low",
                "category": "mesh",
                "title_it": "Nessuna azione correttiva necessaria",
                "title_en": "No corrective action needed",
                "description_it": "La flotta eero opera al massimo dell'efficienza. Tutti i collegamenti mesh sono conformi agli standard di eccellenza.",
                "description_en": "The eero fleet is performing at peak efficiency. All mesh links adhere to optimal performance standards.",
                "icon": "check-circle",
            })

        narrative_it = " ".join(narrative_it_parts) if narrative_it_parts else "Nessuna anomalia o fattore di penalità riscontrato."
        narrative_en = " ".join(narrative_en_parts) if narrative_en_parts else "No anomalies or penalty factors detected."

        return {
            "score": score,
            "status": status,
            "overview_it": overview_it,
            "overview_en": overview_en,
            "narrative_it": narrative_it,
            "narrative_en": narrative_en,
            "checklist": checklist,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

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
            return [
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
                    "description_it": "Upload notturno anomalo di 1.42 GB tra le 02:00 e le 05:30 (la media notturna tipica è di soli 15 MB).",
                    "description_en": "Abnormal night upload of 1.42 GB between 02:00 and 05:30 (typical baseline is 15 MB).",
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
                    "description_it": "Traffico notturno anomalo di 340 MB su attuatore domotico (baseline abituale 2.5 MB).",
                    "description_en": "Unusual night traffic of 340 MB on smart relay switch (typical baseline 2.5 MB).",
                    "timestamp": now,
                    "is_demo": 1,
                }
            ]

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
                anom = {
                    "mac_address": mac,
                    "hostname": h_name,
                    "device_category": cat,
                    "anomaly_type": "excessive_upload" if "cam" in h_name.lower() else "unexpected_activity",
                    "megabytes_transferred": round(delta_vol, 1),
                    "baseline_megabytes": 10.0,
                    "severity": sev,
                    "description_it": (
                        f"Rilevato traffico notturno anomalo di {delta_vol:.1f} MB (soglia di allerta: {threshold:.0f} MB) "
                        f"tra le 01:00 e le 06:00 su '{h_name}'."
                    ),
                    "description_en": (
                        f"Abnormal night traffic of {delta_vol:.1f} MB detected (warning threshold: {threshold:.0f} MB) "
                        f"between 01:00 and 06:00 on '{h_name}'."
                    ),
                    "timestamp": now_str,
                    "is_demo": 0,
                }
                anomalies.append(anom)

        return anomalies


# Istanza singleton del servizio
diagnostics_service = DiagnosticsService()
