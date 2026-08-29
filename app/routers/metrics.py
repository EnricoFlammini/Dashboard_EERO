import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Query

from app.services.db import db_service
from app.services.poller import background_poller
from app.services.eero_client import eero_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["Metrics & Bandwidth Historian"])


@router.get("/realtime")
async def get_realtime_metrics():
    """Restituisce il throughput istantaneo aggregato e i dati live reali."""
    cached = background_poller.get_cached_state()
    devices = cached.get("devices", [])
    
    connected_devs = [d for d in devices if d.get("connected")]
    total_dl = sum(float(d.get("download_rate_mbps", 0)) for d in connected_devs)
    total_ul = sum(float(d.get("upload_rate_mbps", 0)) for d in connected_devs)
    total_rx = sum(float(d.get("rx_bytes", 0)) for d in devices)
    total_tx = sum(float(d.get("tx_bytes", 0)) for d in devices)

    return {
        "status": "success",
        "current_download_mbps": round(total_dl, 2),
        "current_upload_mbps": round(total_ul, 2),
        "total_rx_gb": round(total_rx / (1024 ** 3), 2),
        "total_tx_gb": round(total_tx / (1024 ** 3), 2),
        "connected_clients_count": len(connected_devs),
        "health_score": cached.get("health_score", 100),
    }


@router.get("/wan")
async def get_wan_metrics_history(
    hours: int = Query(24, ge=1, le=720),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """Restituisce la cronologia temporale del traffico WAN reale per generare i grafici."""
    history = await db_service.get_wan_metrics_history(
        hours=hours,
        start_time=start_time,
        end_time=end_time
    )

    total_bytes = 0.0
    if history and len(history) > 1:
        rx_first = float(history[0].get("rx_bytes", 0))
        rx_last = float(history[-1].get("rx_bytes", 0))
        tx_first = float(history[0].get("tx_bytes", 0))
        tx_last = float(history[-1].get("tx_bytes", 0))
        delta_bytes = max(0.0, (rx_last - rx_first) + (tx_last - tx_first))
        
        if delta_bytes > 0:
            total_bytes = delta_bytes
        else:
            for i in range(1, len(history)):
                try:
                    t_str_prev = history[i-1]["timestamp"].replace("Z", "").split(".")[0]
                    t_str_curr = history[i]["timestamp"].replace("Z", "").split(".")[0]
                    t_prev = datetime.fromisoformat(t_str_prev)
                    t_curr = datetime.fromisoformat(t_str_curr)
                    dt_sec = max(1.0, min(300.0, (t_curr - t_prev).total_seconds()))
                except Exception:
                    dt_sec = 30.0
                
                avg_mbps = float(history[i].get("download_speed_mbps", 0)) + float(history[i].get("upload_speed_mbps", 0))
                total_bytes += (avg_mbps * 1_000_000.0 / 8.0) * dt_sec

    return {
        "status": "success",
        "hours": hours,
        "points_count": len(history),
        "total_gb_transferred": round(total_bytes / (1024 ** 3), 2),
        "history": history
    }


@router.get("/top-hogs")
async def get_top_bandwidth_hogs(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(10, ge=1, le=50)
):
    """Restituisce la classifica rigorosa dei dispositivi con consumo reale di dati nel periodo."""
    hogs = await db_service.get_top_bandwidth_hogs(hours=hours, limit=limit)
    
    demo_blacklist = {
        'home nas & media server', 'macbook pro lavoro', 'smart tv oled 65"',
        'iphone personale', 'ps5 pro console', 'shelly domotica quadro',
        'termostato soggiorno', 'ipad cucina / ricette', 'home assistant server',
        'sonos speaker salone'
    }

    formatted = []
    seen_macs = set()
    for item in hogs:
        d_name = str(item.get("display_name", "")).strip()
        mac = str(item.get("mac_address", "")).upper()
        if d_name.lower() in demo_blacklist or not mac or mac in seen_macs:
            continue

        tot_b = float(item.get("total_bytes", 0))
        rx_b = float(item.get("total_rx_bytes", 0))
        tx_b = float(item.get("total_tx_bytes", 0))
        avg_dl = float(item.get("avg_download_rate", 0))
        avg_ul = float(item.get("avg_upload_rate", 0))

        # Se non ci sono byte o traffico reale registrato (meno di 1 KB totale e 0 rate), non mostrare
        if tot_b < 1024 and avg_dl <= 0 and avg_ul <= 0:
            continue

        seen_macs.add(mac)

        tot_gb = tot_b / (1024 ** 3)
        tot_mb = tot_b / (1024 ** 2)
        rx_gb = rx_b / (1024 ** 3)
        rx_mb = rx_b / (1024 ** 2)
        tx_gb = tx_b / (1024 ** 3)
        tx_mb = tx_b / (1024 ** 2)

        # Formattazione intelligente per visualizzare unità corrette
        if tot_gb >= 0.1:
            disp_tot = f"{tot_gb:.2f} GB"
        else:
            disp_tot = f"{tot_mb:.1f} MB"

        if rx_gb >= 0.1:
            disp_rx = f"{rx_gb:.2f}GB"
        else:
            disp_rx = f"{rx_mb:.1f}MB"

        if tx_gb >= 0.1:
            disp_tx = f"{tx_gb:.2f}GB"
        else:
            disp_tx = f"{tx_mb:.1f}MB"

        formatted.append({
            "mac_address": mac,
            "display_name": d_name,
            "custom_icon": item.get("custom_icon", "device"),
            "category": item.get("category", "Altro"),
            "total_bytes": tot_b,
            "total_gb": round(tot_gb, 2) if tot_gb >= 0.01 else round(tot_mb / 1024.0, 4),
            "display_consumption": disp_tot,
            "rx_display": disp_rx,
            "tx_display": disp_tx,
            "total_mb": round(tot_mb, 1),
            "rx_gb": round(rx_gb, 2),
            "tx_gb": round(tx_gb, 2),
            "avg_download_rate": round(avg_dl, 2),
            "avg_upload_rate": round(avg_ul, 2),
        })

    formatted.sort(key=lambda x: x["total_bytes"], reverse=True)

    return {
        "status": "success",
        "hours": hours,
        "count": len(formatted),
        "hogs": formatted[:limit]
    }


# =========================================================================
# SIGNAL QUALITY & MESH COVERAGE HISTORIAN (v1.04.00)
# =========================================================================

@router.get("/signal/overview")
async def get_signal_overview():
    """Restituisce le statistiche aggregate di copertura mesh e qualità del segnale RSSI."""
    try:
        is_demo = getattr(eero_client, "is_demo_mode", False)
        if is_demo:
            devs = [
                {"mac_address": "3C:22:FB:99:88:77", "hostname": "iPhone Demo", "signal_rssi": -45, "frequency_band": "6 GHz", "channel": 69, "connected_eero_name": "Studio"},
                {"mac_address": "E0:4F:43:AA:BB:CC", "hostname": "iPad Cucina", "signal_rssi": -55, "frequency_band": "5 GHz", "channel": 36, "connected_eero_name": "Gateway Soggiorno"},
                {"mac_address": "70:EE:50:66:77:88", "hostname": "Sonos Salone", "signal_rssi": -58, "frequency_band": "5 GHz", "channel": 40, "connected_eero_name": "Gateway Soggiorno"},
                {"mac_address": "18:B4:30:11:22:33", "hostname": "Termostato Soggiorno", "signal_rssi": -68, "frequency_band": "2.4 GHz", "channel": 11, "connected_eero_name": "Gateway Soggiorno"},
                {"mac_address": "DC:A6:32:88:77:66", "hostname": "Telecamera Giardino", "signal_rssi": -78, "frequency_band": "2.4 GHz", "channel": 6, "connected_eero_name": "Camera da Letto"}
            ]
            total = len(devs)
            total_rssi = sum(d["signal_rssi"] for d in devs)
            avg_rssi = round(total_rssi / total, 1)
            excellent = [d for d in devs if d["signal_rssi"] >= -50]
            good = [d for d in devs if -65 <= d["signal_rssi"] < -50]
            fair = [d for d in devs if -75 <= d["signal_rssi"] < -65]
            weak = [d for d in devs if d["signal_rssi"] < -75]
            return {
                "status": "success",
                "overview": {
                    "total_wireless_devices": total,
                    "average_rssi": avg_rssi,
                    "excellent_count": len(excellent),
                    "good_count": len(good),
                    "fair_count": len(fair),
                    "weak_count": len(weak),
                    "excellent_pct": round((len(excellent) / total) * 100, 1),
                    "good_pct": round((len(good) / total) * 100, 1),
                    "fair_pct": round((len(fair) / total) * 100, 1),
                    "weak_pct": round((len(weak) / total) * 100, 1),
                    "weak_devices": weak,
                    "devices": devs
                }
            }

        overview = await db_service.get_signal_overview(is_demo=0)
        return {
            "status": "success",
            "overview": overview
        }
    except Exception as e:
        logger.error(f"Errore recupero signal overview: {e}")
        return {
            "status": "error",
            "message": str(e),
            "overview": {
                "total_wireless_devices": 0,
                "average_rssi": 0,
                "excellent_count": 0,
                "good_count": 0,
                "fair_count": 0,
                "weak_count": 0,
                "excellent_pct": 0,
                "good_pct": 0,
                "fair_pct": 0,
                "weak_pct": 0,
                "weak_devices": [],
                "devices": []
            }
        }


@router.get("/signal/history")
async def get_device_signal_history(
    mac: str = Query(..., description="Indirizzo MAC del dispositivo da interrogare"),
    hours: int = Query(24, ge=1, le=336, description="Intervallo orario storico (es. 24h, 168h = 7d)")
):
    """Restituisce la serie temporale dei campioni RSSI per il dispositivo specificato."""
    try:
        is_demo = getattr(eero_client, "is_demo_mode", False)
        if is_demo:
            now = datetime.now(timezone.utc)
            base_rssi = -45 if "3C" in mac.upper() else (-55 if "E0" in mac.upper() else (-78 if "DC" in mac.upper() else -62))
            history = []
            steps = min(hours * 3, 36)
            interval_mins = max(5, int((hours * 60) / max(steps, 1)))
            for i in range(steps, -1, -1):
                pt_time = (now - timedelta(minutes=i * interval_mins)).strftime("%Y-%m-%dT%H:%M:%SZ")
                fluct = random.choice([-1, 0, 1, 0, -2, 1])
                history.append({
                    "timestamp": pt_time,
                    "mac_address": mac.upper(),
                    "hostname": "Demo Device",
                    "signal_rssi": base_rssi + fluct,
                    "frequency_band": "5 GHz",
                    "channel": 36,
                    "connected_eero_name": "Gateway Soggiorno"
                })
            return {
                "status": "success",
                "mac_address": mac.upper(),
                "hours": hours,
                "points_count": len(history),
                "history": history
            }

        history = await db_service.get_device_signal_history(mac_address=mac, range_hours=hours, is_demo=0)
        return {
            "status": "success",
            "mac_address": mac.upper(),
            "hours": hours,
            "points_count": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(f"Errore recupero signal history per {mac}: {e}")
        return {
            "status": "error",
            "message": str(e),
            "mac_address": mac.upper(),
            "hours": hours,
            "points_count": 0,
            "history": []
        }


