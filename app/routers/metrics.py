import logging
from typing import Optional
from fastapi import APIRouter, Query

from app.services.db import db_service
from app.services.poller import background_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["Metrics & Bandwidth Historian"])


@router.get("/realtime")
async def get_realtime_metrics():
    """Restituisce il throughput istantaneo aggregato e i dati live."""
    cached = background_poller.get_cached_state()
    devices = cached.get("devices", [])
    
    total_dl = sum(d.get("download_rate_mbps", 0) for d in devices if d.get("connected"))
    total_ul = sum(d.get("upload_rate_mbps", 0) for d in devices if d.get("connected"))
    total_rx = sum(d.get("rx_bytes", 0) for d in devices)
    total_tx = sum(d.get("tx_bytes", 0) for d in devices)

    return {
        "status": "success",
        "current_download_mbps": round(total_dl, 2),
        "current_upload_mbps": round(total_ul, 2),
        "total_rx_gb": round(total_rx / (1024 ** 3), 2),
        "total_tx_gb": round(total_tx / (1024 ** 3), 2),
        "connected_clients_count": len([d for d in devices if d.get("connected")]),
        "health_score": cached.get("health_score", 100),
    }


@router.get("/wan")
async def get_wan_metrics_history(
    hours: int = Query(24, ge=1, le=720),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """Restituisce la cronologia temporale del traffico WAN per generare i grafici."""
    history = await db_service.get_wan_metrics_history(
        hours=hours,
        start_time=start_time,
        end_time=end_time
    )

    # Calcolo totale scambiato nel periodo selezionato
    total_bytes = 0
    if history and len(history) > 1:
        rx_delta = max(0, history[-1].get("rx_bytes", 0) - history[0].get("rx_bytes", 0))
        tx_delta = max(0, history[-1].get("tx_bytes", 0) - history[0].get("tx_bytes", 0))
        total_bytes = rx_delta + tx_delta

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
    """Restituisce la classifica dei dispositivi con il maggior consumo di dati nel periodo."""
    hogs = await db_service.get_top_bandwidth_hogs(hours=hours, limit=limit)
    
    # Formattazione per la UI
    formatted = []
    for item in hogs:
        tot_b = item.get("total_bytes", 0)
        formatted.append({
            "mac_address": item.get("mac_address"),
            "display_name": item.get("display_name"),
            "custom_icon": item.get("custom_icon", "device"),
            "category": item.get("category", "Altro"),
            "total_bytes": tot_b,
            "total_gb": round(tot_b / (1024 ** 3), 2),
            "total_mb": round(tot_b / (1024 ** 2), 1),
            "rx_gb": round(item.get("total_rx_bytes", 0) / (1024 ** 3), 2),
            "tx_gb": round(item.get("total_tx_bytes", 0) / (1024 ** 3), 2),
            "avg_download_rate": round(item.get("avg_download_rate", 0), 2),
            "avg_upload_rate": round(item.get("avg_upload_rate", 0), 2),
        })

    return {
        "status": "success",
        "hours": hours,
        "count": len(formatted),
        "hogs": formatted
    }
