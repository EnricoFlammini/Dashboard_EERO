import logging
from fastapi import APIRouter, HTTPException, Query
from app.services.db import db_service
from app.services.speedtest_service import speedtest_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speedtest", tags=["Speed Test & Diagnostics"])


@router.get("/status")
async def get_speedtest_status():
    """Restituisce se uno speedtest è attualmente in esecuzione e l'ultimo risultato noto."""
    return {
        "is_running": speedtest_service.is_running,
        "last_run_time": speedtest_service.last_run_time,
        "last_result": speedtest_service.last_result,
    }


@router.post("/run")
async def trigger_manual_speedtest():
    """Avvia manualmente una sessione di Speed Test."""
    if speedtest_service.is_running:
        raise HTTPException(status_code=409, detail="Uno Speed Test è già in corso. Attendi il completamento.")

    try:
        result = await speedtest_service.run_speedtest()
        return {
            "status": "success",
            "message": "Speed Test completato con successo.",
            "result": result
        }
    except Exception as e:
        logger.error(f"Manual speedtest execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_speedtest_history(limit: int = Query(50, ge=1, le=200)):
    """Restituisce lo storico di tutti i test di velocità eseguiti."""
    tests = await db_service.get_speedtests(limit=limit)
    return {
        "status": "success",
        "count": len(tests),
        "tests": tests
    }


@router.get("/stats")
async def get_speedtest_statistics():
    """Restituisce le statistiche aggregate di prestazione (medie, picchi e latenza)."""
    stats = await db_service.get_speedtest_stats()
    return {
        "status": "success",
        "stats": stats
    }
