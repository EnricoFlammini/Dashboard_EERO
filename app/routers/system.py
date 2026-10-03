import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from app.config import settings
from app.routers.dependencies import require_admin, require_permission
from app.services.db import db_service
from app.services.eero_news_service import eero_news_service
from app.services.notifications import notification_service
from app.services.updater import updater_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System & Updates"])


class LanguageRequest(BaseModel):
    language: str


@router.get("/language")
async def get_system_language():
    """Restituisce la lingua attualmente configurata per la dashboard e le notifiche."""
    lang = await notification_service.get_language()
    return {"status": "success", "language": lang}


@router.post("/language")
async def set_system_language(payload: LanguageRequest):
    """Aggiorna e persiste la lingua preferita per la dashboard e le notifiche."""
    lang = payload.language.lower().strip()
    if lang not in ("it", "en"):
        raise HTTPException(status_code=400, detail="Lingua non supportata. Valori validi: 'en', 'it'")
    await notification_service.set_language(lang)
    return {"status": "success", "language": lang}


@router.get("/update/check")
async def check_for_updates(force: bool = Query(False, description="Forza il controllo remoto senza usare la cache")):
    """Controlla se è disponibile una nuova versione su Docker Hub e GitHub Releases."""
    try:
        info = await updater_service.check_for_updates(force=force)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update/trigger")
async def trigger_update():
    """Avvia l'aggiornamento automatico del container Docker tramite Docker Socket o Watchtower."""
    try:
        res = await updater_service.trigger_update()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eero-news")
async def get_eero_news(force: bool = Query(False, description="Forza il ricalcolo e recupero da Zendesk")):
    """Restituisce l'elenco cronologico delle note di rilascio eeroOS, la versione del firmware

    installata sui nodi mesh dell'utente, lo stato di allineamento e i feedback della community.
    """
    try:
        summary = await eero_news_service.get_news_summary(force=force)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero delle notizie eero: {str(e)}")


@router.post("/eero-news/refresh")
async def refresh_eero_news():
    """Forza il controllo e re-scraping immediato delle release notes eeroOS da Zendesk API."""
    try:
        summary = await eero_news_service.get_news_summary(force=True)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel refresh delle notizie eero: {str(e)}")


# =========================================================================
# DISASTER RECOVERY: BACKUP & ATOMIC RESTORE (v1.6.0 Modulo 1)
# =========================================================================

@router.get("/backup", dependencies=[Depends(require_admin)])
async def export_system_backup_endpoint():
    """
    Esporta un backup atomico completo dello stato di configurazione della dashboard:
    metadati dispositivi, impostazioni globali, regole di parental scheduling e account utenti.
    """
    try:
        backup_data = await db_service.export_system_backup()
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="eero_dashboard_backup_{now_str}.json"'
            }
        )
    except Exception as e:
        logger.error(f"Error generating system backup: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante l'esportazione del backup: {str(e)}")


@router.post("/restore", dependencies=[Depends(require_admin)])
async def import_system_restore_endpoint(payload: Dict[str, Any]):
    """
    Esegue il ripristino atomico dei dati da un payload di backup valido.
    Operazione riservata esclusivamente agli amministratori di sistema.
    """
    try:
        data_to_restore = payload.get("backup") if (isinstance(payload, dict) and "backup" in payload and isinstance(payload["backup"], dict)) else payload
        result = await db_service.import_system_restore(data_to_restore)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during system restore: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante il ripristino del backup: {str(e)}")


# =========================================================================
# DATABASE METRICS & DATA RETENTION ENGINE (v1.6.0 Modulo 2)
# =========================================================================

@router.get("/database/stats")
async def get_database_statistics():
    """
    Restituisce le statistiche su dimensioni fisiche (MB), conteggio righe per tier e stato compattazione.
    """
    try:
        from app.services.retention_worker import retention_worker
        stats = await db_service.get_database_stats()
        stats["last_retention_summary"] = retention_worker.last_summary
        stats["last_retention_run"] = retention_worker.last_run.strftime("%Y-%m-%dT%H:%M:%SZ") if retention_worker.last_run else None
        return stats
    except Exception as e:
        logger.error(f"Error fetching database stats: {e}")
        raise HTTPException(status_code=500, detail=f"Errore recupero statistiche database: {str(e)}")


@router.post("/database/compact", dependencies=[Depends(require_admin)])
async def trigger_database_compaction():
    """
    Esegue manualmente e on-demand un ciclo completo di compattazione e tiering multi-livello.
    Richiede privilegi di amministratore.
    """
    try:
        from app.services.retention_worker import retention_worker
        summary = await retention_worker.run_compaction_cycle()
        return summary
    except Exception as e:
        logger.error(f"Error during manual database compaction: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante la compattazione del database: {str(e)}")


