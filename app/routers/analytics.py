import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.poller import background_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _resolve_vendor_from_mac_and_name(mac: str, hostname: str) -> str:
    """Riconosce il produttore hardware da prefisso OUI del MAC o stringa hostname."""
    mac_clean = (mac or "").lower().replace(":", "").replace("-", "")[:6]
    h_lower = (hostname or "").lower()

    # Heuristic su hostname
    if any(k in h_lower for k in ("iphone", "ipad", "macbook", "imac", "apple", "airpods", "homepod")):
        return "Apple"
    if any(k in h_lower for k in ("galaxy", "samsung")):
        return "Samsung"
    if any(k in h_lower for k in ("echo", "kindle", "fire tv", "firetv", "firestick", "ring", "eero")):
        return "Amazon"
    if any(k in h_lower for k in ("pixel", "nest", "chromecast", "google")):
        return "Google"
    if any(k in h_lower for k in ("playstation", "ps5", "ps4", "bravia", "sony")):
        return "Sony"
    if any(k in h_lower for k in ("raspberry", "rpi", "raspi")):
        return "Raspberry Pi"
    if "shelly" in h_lower:
        return "Shelly"
    if any(k in h_lower for k in ("esp_", "espressif", "tasmota", "tuya", "sonoff")):
        return "Espressif / IoT"
    if any(k in h_lower for k in ("surface", "xbox", "windows")):
        return "Microsoft"
    if any(k in h_lower for k in ("nuc", "intel")):
        return "Intel"

    # OUI Prefix Database (OUI a 6 caratteri esadecimali)
    apple_ouis = {
        "000393", "000502", "000a27", "000a95", "000c29", "000d93", "0010fa", "001124", "001451",
        "0016cb", "0017f2", "0019e3", "001b63", "001cb3", "001d4f", "001e52", "001ec2", "0021e9",
        "002241", "002312", "002332", "00236c", "0023df", "002436", "002500", "00254b", "0025bc",
        "002608", "00264a", "0026b0", "0026bb", "040cce", "041552", "041e64", "042665", "044bed",
        "045453", "04db56", "04e536", "080007", "086698", "087045", "08e689", "0c1539", "0c3021",
        "0cbc9f", "101c0c", "1040f3", "1093e9", "1094bb", "109add", "14109f", "14205e", "147dda",
        "1499e2", "14c213", "182032", "183451", "186590", "18af61", "18e7f4", "1c1ac0", "20768f",
        "20ab37", "24a074", "24a2e1", "280b5c", "285aeb", "286aba", "28cfe9", "2cb43a", "30074d",
        "305714", "3090ab", "3408bc", "34159e", "34363b", "34ab37", "34c059", "380f4a", "38484c",
        "3871de", "38b54d", "38f9d3", "3c0754", "3c15c2", "3c22fb", "3cab8e", "406c8f", "409c28",
        "440010", "48605f", "48746e", "4c3275", "50bc96", "542696", "5855ca", "5cadcf", "600308",
        "64200c", "68a86d", "6c4008", "701124", "70708b", "748d08", "784f43", "7c04d0", "80e650",
        "84fcac", "88665a", "8c8590", "907240", "94e979", "9801a7", "9c207b", "a483e7", "a8667f",
        "acde48", "b03495", "b418d1", "b8098a", "bcd074", "c0847d", "c4b301", "c86f1d", "cc08e0",
        "d0034b", "d4dccd", "d83062", "dc2b2a", "e0338e", "e498d6", "e8b2ac", "ec3586", "f01898",
        "f40f24", "f8ffc2", "fc257f", "3c2ef9", "787b8a", "48437c", "60f445", "a4c361"
    }
    if mac_clean in apple_ouis:
        return "Apple"

    samsung_ouis = {
        "0007ab", "000919", "001247", "001377", "001599", "001632", "0017c9", "001a8a", "001d25",
        "001ee1", "001fcc", "002119", "002339", "002454", "0024e9", "002637", "08373d", "1449e0",
        "244b03", "3423ba", "400e85", "4c6641", "508569", "58c38b", "606bbd", "6c8336", "78471d",
        "8425db", "946372", "9810e8", "a0821f", "a80600", "b0c4e7", "b85a73", "c4731e", "d059e4",
        "e47cf9", "f47b5e"
    }
    if mac_clean in samsung_ouis:
        return "Samsung"

    amazon_ouis = {
        "007147", "0c47c9", "10ae60", "18742e", "38f73d", "40b4cd", "440049", "44650d", "50dce7",
        "6837e9", "68545a", "747548", "74c246", "84d6d0", "ac63be", "b009da", "cc9e00", "f08173",
        "fc65de"
    }
    if mac_clean in amazon_ouis:
        return "Amazon"

    google_ouis = {
        "001a11", "089e08", "1c5cf2", "20dfb9", "30fd38", "3c5a37", "44070b", "48d705", "546009",
        "641666", "703acb", "88366c", "94eb2c", "a47733", "b4f7a1", "d86c63", "e4f042", "f4f5e8",
        "f80f41"
    }
    if mac_clean in google_ouis:
        return "Google"

    sony_ouis = {
        "00014a", "00041f", "001315", "0015c1", "0019c5", "001a80", "001d0d", "00248d", "0498f3",
        "080046", "0cfe45", "1048b1", "280dfc", "303926", "40b034", "4cb9ea", "709e29", "80c3ba",
        "9003b7", "a8e3ee", "bc60a7", "c863f1", "d8d43c", "f8461c"
    }
    if mac_clean in sony_ouis:
        return "Sony"

    rpi_ouis = {"b827eb", "dca632", "e45f01", "28cdc1"}
    if mac_clean in rpi_ouis:
        return "Raspberry Pi"

    shelly_ouis = {"3ce90e", "409151", "485519", "4c7525", "600194", "68c63a", "84f3eb", "a4cf12", "b4e62d", "c44f33", "e8db84"}
    if mac_clean in shelly_ouis:
        return "Shelly"

    espressif_ouis = {
        "18fe34", "240ac4", "246f28", "24b2de", "2c3ae8", "30aea4", "4c11ae", "5ccf7f", "840d8e",
        "98cdac", "a020a6", "a47b9d", "acd074", "c82b96", "d8a01d", "ecfabc"
    }
    if mac_clean in espressif_ouis:
        return "Espressif / IoT"

    intel_ouis = {
        "0002b3", "000347", "000423", "0007e9", "000e0c", "001111", "001302", "0013e8", "001500",
        "001517", "0016ea", "0018de", "0019d1", "001b21", "001cc0", "001de0", "001e64", "00215c",
        "0022fb", "002314", "0024d7", "0026c6", "00270e", "04ed33", "081196", "083e8e", "08d23e",
        "0c8bfd", "1002b5", "144f8a", "185e0f", "1c697a", "247703", "3413e8", "38baf8", "3cfdfe",
        "4851b7", "4c796e", "5891cf", "644bf0", "6805ca", "6c2995", "707781", "74d435", "782bcb",
        "7c5758", "8086f2", "84fdd1", "887556", "8cdcd4", "94659c", "a036bc", "a402b9", "ac74b1",
        "b49691", "b8b81e", "c403a8", "c82158", "cc96e5", "d43b04", "d8fc93", "e4e749", "ecaaa0"
    }
    if mac_clean in intel_ouis:
        return "Intel"

    return "Other"


@router.get("/distribution")
async def get_network_distribution() -> Dict[str, Any]:
    """
    Restituisce le statistiche aggregate di distribuzione del carico di rete:
    - Frequenze Wi-Fi & Cablato (2.4 GHz, 5 GHz, 6 GHz, Ethernet)
    - Carico per singolo nodo eero mesh
    - Categorie dei dispositivi connessi
    - Top Vendor hardware (OUI & Heuristic)
    """
    try:
        # Prendi dispositivi e nodi dalla cache in memoria del poller (0 ms)
        devices = background_poller.cached_devices or []
        eeros = background_poller.cached_eeros or []

        if not devices and hasattr(eero_client, "get_devices"):
            devices = await eero_client.get_devices()
        if not eeros and hasattr(eero_client, "get_eeros"):
            eeros = await eero_client.get_eeros()

        total_devices = len(devices)
        active_devices = [d for d in devices if d.get("connected")]
        active_count = len(active_devices)

        def _get_device_display_name(dev: Dict[str, Any]) -> str:
            return str(dev.get("custom_name") or dev.get("nickname") or dev.get("hostname") or dev.get("ip") or dev.get("mac") or "Dispositivo").strip()

        # 1. Distribuzione Frequenze (su client attivi)
        freq_map: Dict[str, List[str]] = {"6 GHz": [], "5 GHz": [], "2.4 GHz": [], "Ethernet": []}
        for d in active_devices:
            d_name = _get_device_display_name(d)
            band = str(d.get("wireless_band") or d.get("frequency_band") or "").strip()
            if "6" in band:
                freq_map["6 GHz"].append(d_name)
            elif "5" in band:
                freq_map["5 GHz"].append(d_name)
            elif "2.4" in band or "2" in band:
                freq_map["2.4 GHz"].append(d_name)
            else:
                freq_map["Ethernet"].append(d_name)

        freq_list = []
        for f_name, f_devs in freq_map.items():
            f_cnt = len(f_devs)
            pct = round((f_cnt / active_count * 100.0), 1) if active_count > 0 else 0.0
            freq_list.append({"band": f_name, "count": f_cnt, "percentage": pct, "devices": f_devs})

        # 2. Carico per Nodo Mesh (su client attivi)
        node_map: Dict[str, Dict[str, Any]] = {}
        node_keys_map: Dict[str, set] = {}
        for e in eeros:
            e_name = e.get("name") or e.get("location") or "Nodo eero"
            e_id = str(e.get("id") or "").strip()
            e_serial = str(e.get("serial") or "").strip()
            e_url = str(e.get("url") or "").strip()
            e_url_tail = e_url.split("/")[-1] if e_url else ""

            node_map[e_name] = {
                "id": e_id,
                "name": e_name,
                "is_gateway": bool(e.get("is_gateway")),
                "model": e.get("model") or "eero",
                "client_count": 0,
                "percentage": 0.0,
                "devices": []
            }
            node_keys_map[e_name] = {k for k in [e_id, e_serial, e_name.lower(), e_url, e_url_tail] if k}

        unassigned_devices: List[str] = []
        for d in active_devices:
            d_name = _get_device_display_name(d)
            src_name = (d.get("connected_eero_name") or d.get("source_name") or "").strip().lower()
            src_id = str(d.get("connected_eero_id") or "").strip()
            src_url = str(d.get("connected_eero_url") or "").strip()
            src_url_tail = src_url.split("/")[-1] if src_url else ""

            matched = False
            # Matching esatto per ID, serial, URL o nome esatto (evita collisioni di sottostringa es. Bedroom vs Issac Bedroom)
            for n_name, n_info in node_map.items():
                ident_keys = node_keys_map[n_name]
                if (src_id and src_id in ident_keys) or \
                   (src_url and (src_url in ident_keys or src_url_tail in ident_keys)) or \
                   (src_name and src_name == n_name.lower()):
                    n_info["devices"].append(d_name)
                    matched = True
                    break

            if not matched and (not d.get("wireless") or d.get("connection_type") == "wired"):
                gw_node = next((n for n in node_map.values() if n["is_gateway"]), None)
                if gw_node:
                    gw_node["devices"].append(d_name)
                    matched = True

            if not matched:
                unassigned_devices.append(d_name)

        if unassigned_devices and node_map:
            first_node = next((n for n in node_map.values() if n["is_gateway"]), list(node_map.values())[0])
            first_node["devices"].extend(unassigned_devices)

        node_list = []
        for n in node_map.values():
            n["client_count"] = len(n["devices"])
            n["percentage"] = round((n["client_count"] / active_count * 100.0), 1) if active_count > 0 else 0.0
            node_list.append(n)
        node_list.sort(key=lambda x: x["client_count"], reverse=True)

        # 3. Categorie Dispositivi (su tutti i dispositivi noti)
        cat_map: Dict[str, List[str]] = {}
        for d in devices:
            d_name = _get_device_display_name(d)
            raw_cat = str(d.get("category") or d.get("device_category") or "Other").strip()
            cat = "Other" if raw_cat in ("Altro", "Other", "") else raw_cat
            if cat not in cat_map:
                cat_map[cat] = []
            cat_map[cat].append(d_name)

        cat_list = []
        for c_name, c_devs in sorted(cat_map.items(), key=lambda x: len(x[1]), reverse=True):
            c_cnt = len(c_devs)
            pct = round((c_cnt / total_devices * 100.0), 1) if total_devices > 0 else 0.0
            cat_list.append({"category": c_name, "count": c_cnt, "percentage": pct, "devices": c_devs})

        # 4. Top Vendor Hardware
        vendor_map: Dict[str, List[str]] = {}
        for d in devices:
            d_name = _get_device_display_name(d)
            raw_v = _resolve_vendor_from_mac_and_name(
                str(d.get("mac") or d.get("mac_address") or ""),
                str(d.get("hostname") or d.get("nickname") or "")
            )
            v = "Other" if raw_v in ("Altro", "Other") else raw_v
            if v not in vendor_map:
                vendor_map[v] = []
            vendor_map[v].append(d_name)

        vendor_list = []
        for v_name, v_devs in sorted(vendor_map.items(), key=lambda x: len(x[1]), reverse=True):
            v_cnt = len(v_devs)
            pct = round((v_cnt / total_devices * 100.0), 1) if total_devices > 0 else 0.0
            vendor_list.append({"vendor": v_name, "count": v_cnt, "percentage": pct, "devices": v_devs})

        return {
            "status": "success",
            "total_devices": total_devices,
            "active_devices": active_count,
            "frequencies": freq_list,
            "node_load": node_list,
            "categories": cat_list,
            "vendors": vendor_list
        }
    except Exception as e:
        logger.error(f"Errore generazione distribuzione analytics: {e}")
        return {
            "status": "error",
            "message": str(e),
            "total_devices": 0,
            "active_devices": 0,
            "frequencies": [],
            "node_load": [],
            "categories": [],
            "vendors": []
        }


@router.get("/isp-sla")
async def get_isp_sla_trend(days: int = Query(30, ge=1, le=365)) -> Dict[str, Any]:
    """Restituisce le metriche storiche SLA e l'indice di affidabilità del Provider Internet (ISP)."""
    try:
        is_demo = int(getattr(eero_client, "is_demo_mode", False) or False)
        sla_data = await db_service.get_isp_sla_analytics(days=days, is_demo=is_demo)
        return {
            "status": "success",
            "sla": sla_data
        }
    except Exception as e:
        logger.error(f"Errore recupero SLA trend: {e}")
        return {
            "status": "error",
            "message": str(e),
            "sla": {
                "total_tests": 0,
                "period_days": days,
                "avg_download_mbps": 0,
                "max_download_mbps": 0,
                "avg_upload_mbps": 0,
                "max_upload_mbps": 0,
                "avg_ping_ms": 0,
                "reliability_score": 100,
                "history_points": []
            }
        }


@router.get("/export/{data_type}")
async def export_network_data(
    data_type: str,
    format: str = Query("csv", regex="^(csv|json)$"),
    limit: int = Query(5000, ge=1, le=50000)
):
    """
    Esporta i dataset di rete in formato standard CSV (RFC 4180) o JSON aperto.
    Tipi supportati: 'devices', 'speedtest', 'signal', 'usage'.
    """
    valid_types = ("devices", "speedtest", "signal", "usage")
    if data_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo di dato non valido. Scegli tra: {', '.join(valid_types)}")

    is_demo = int(getattr(eero_client, "is_demo_mode", False) or False)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"eero_{data_type}_{date_str}.{format}"

    # 1. Dataset Dispositivi
    if data_type == "devices":
        raw_devices = background_poller.cached_devices or []
        if not raw_devices and hasattr(eero_client, "get_devices"):
            raw_devices = await eero_client.get_devices()

        export_items = []
        for d in raw_devices:
            export_items.append({
                "hostname": d.get("hostname") or d.get("nickname") or "Dispositivo",
                "ip": d.get("ip") or "",
                "mac_address": d.get("mac") or d.get("mac_address") or "",
                "status": "Online" if d.get("connected") else "Offline",
                "connection_type": d.get("connection_type") or ("Wireless" if d.get("wireless") else "Wired"),
                "frequency_band": d.get("wireless_band") or d.get("frequency_band") or "",
                "channel": d.get("channel") or "",
                "signal_rssi_dbm": d.get("signal_rssi") or "",
                "connected_eero_node": d.get("source_name") or d.get("connected_eero_name") or "",
                "category": d.get("category") or "",
                "rx_bytes": d.get("rx_bytes") or 0,
                "tx_bytes": d.get("tx_bytes") or 0,
                "download_speed_mbps": d.get("download_rate_mbps") or 0,
                "upload_speed_mbps": d.get("upload_rate_mbps") or 0,
                "is_guest": "Si" if d.get("is_guest") else "No",
                "is_static_ip": "Si" if d.get("is_static") else "No"
            })

    # 2. Dataset Speedtest
    elif data_type == "speedtest":
        export_items = await db_service.get_speedtests_for_export(limit=limit, is_demo=is_demo)

    # 3. Dataset Segnale Radio Wi-Fi RSSI
    elif data_type == "signal":
        export_items = await db_service.get_signal_samples_for_export(limit=limit, is_demo=is_demo)

    # 4. Dataset Storico Consumo Dati
    elif data_type == "usage":
        export_items = await db_service.get_usage_samples_for_export(limit=limit, is_demo=is_demo)
        # Converti byte in MB / GB per facilità di lettura nel CSV
        for item in export_items:
            item["rx_mb"] = round(float(item.get("rx_bytes") or 0) / (1024 * 1024), 2)
            item["tx_mb"] = round(float(item.get("tx_bytes") or 0) / (1024 * 1024), 2)
            item["total_mb"] = round(item["rx_mb"] + item["tx_mb"], 2)

    # Formato JSON
    if format == "json":
        json_content = json.dumps({
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_type": data_type,
            "total_records": len(export_items),
            "data": export_items
        }, indent=2, ensure_ascii=False)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache"
            }
        )

    # Formato CSV
    output = io.StringIO()
    if export_items:
        fieldnames = list(export_items[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(export_items)
    else:
        output.write("nessun_dato_disponibile\n")

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )
