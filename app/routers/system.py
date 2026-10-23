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
from app.services.runtime_info import get_runtime_info
from app.services.updater import updater_service
from app.i18n import log_event, tr

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
        raise HTTPException(status_code=400, detail=tr("system.language_unsupported"))
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


@router.get("/update/changelog")
async def get_update_changelog(version: Optional[str] = Query(None, description="Versione specifica o ultima")):
    """Restituisce le note di rilascio e il changelog ridotto per una versione o per l'aggiornamento disponibile."""
    try:
        from app.services.updater import extract_condensed_changelog, extract_release_notes_from_changelog
        info = await updater_service.check_for_updates(force=False)
        target_version = version or info.get("latest_version") or settings.app_version
        raw_notes = extract_release_notes_from_changelog(target_version)
        if not raw_notes and target_version == info.get("latest_version"):
            raw_notes = info.get("release_notes", "")
        condensed = extract_condensed_changelog(target_version, raw_notes=raw_notes)
        return {
            "status": "success",
            "version": target_version,
            "release_notes": raw_notes,
            "condensed_changelog": condensed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runtime", dependencies=[Depends(require_permission("view_logs"))])
async def get_runtime():
    """Reports where this instance runs (local, Docker, Kubernetes) and its source branch/commit."""
    return {"status": "success", **get_runtime_info()}


@router.post("/update/trigger", dependencies=[Depends(require_permission("action_manage_rules"))])
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
        raise HTTPException(status_code=500, detail=tr("system.news_fetch_failed", error=str(e)))


@router.post("/eero-news/refresh", dependencies=[Depends(require_permission("view_topology"))])
async def refresh_eero_news():
    """Forza il controllo e re-scraping immediato delle release notes eeroOS da Zendesk API."""
    try:
        summary = await eero_news_service.get_news_summary(force=True)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=tr("system.news_refresh_failed", error=str(e)))


# =========================================================================
# DISASTER RECOVERY: BACKUP & ATOMIC RESTORE (v1.6.0 Modulo 1)
# =========================================================================

@router.get("/backup", dependencies=[Depends(require_admin)])
@router.get("/backup/export", dependencies=[Depends(require_admin)])
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
        log_event(logger, logging.ERROR, "log_system.backup_export_failed", error=e)
        raise HTTPException(status_code=500, detail=tr("system.backup_export_failed", error=str(e)))


@router.post("/restore", dependencies=[Depends(require_admin)])
@router.post("/backup/restore", dependencies=[Depends(require_admin)])
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
        log_event(logger, logging.ERROR, "log_system.backup_restore_failed", error=e)
        raise HTTPException(status_code=500, detail=tr("system.backup_restore_failed", error=str(e)))


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
        raise HTTPException(status_code=500, detail=tr("system.db_stats_failed", error=str(e)))


@router.post("/database/compact", dependencies=[Depends(require_admin)])
async def trigger_database_compaction(force: bool = False, vacuum: bool = True):
    """
    Esegue manualmente e on-demand un ciclo completo di compattazione e tiering multi-livello.
    Richiede privilegi di amministratore.
    """
    try:
        from app.services.retention_worker import retention_worker
        summary = await retention_worker.run_compaction_cycle(vacuum=vacuum, force=force)
        return summary
    except Exception as e:
        log_event(logger, logging.ERROR, "log_system.db_compact_failed", error=e)
        raise HTTPException(status_code=500, detail=tr("system.db_compact_failed", error=str(e)))


@router.get("/database/integrity", dependencies=[Depends(require_admin)])
async def check_database_integrity(quick: bool = True):
    """
    Esegue un controllo di integrità del database SQLite (PRAGMA quick_check o integrity_check).
    Richiede privilegi di amministratore.
    """
    try:
        res = await db_service.check_database_integrity(quick=quick)
        return res
    except Exception as e:
        log_event(logger, logging.ERROR, "log_system.db_integrity_failed", error=e)
        raise HTTPException(status_code=500, detail=tr("system.db_integrity_failed", error=str(e)))


@router.post("/database/backup", dependencies=[Depends(require_admin)])
async def create_database_backup():
    """
    Crea un backup coerente, atomico e deframmentato del database SQLite a caldo via VACUUM INTO.
    Richiede privilegi di amministratore.
    """
    try:
        res = await db_service.backup_database_file()
        return res
    except Exception as e:
        log_event(logger, logging.ERROR, "log_system.db_backup_failed", error=e)
        raise HTTPException(status_code=500, detail=tr("system.db_backup_failed", error=str(e)))



