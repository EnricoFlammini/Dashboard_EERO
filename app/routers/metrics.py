import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query

from app.services.db import db_service
from app.services.poller import background_poller

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

        # Se non ci sono byte o traffico reale registrato (meno di 100 KB totali e 0 rate), non mostrare
        if tot_b < 100_000 and avg_dl <= 0 and avg_ul <= 0:
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

