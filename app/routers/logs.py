"""
Router API REST per Gestione Log di Sistema & Diagnostica (v1.6.0 Modulo 4)

Fornisce gli endpoint per:
- Consultazione configurazione e metriche storage (/api/system/logs/config)
- Riconfigurazione a caldo livello e retention (/api/system/logs/config)
- Query paginata con filtri e ricerca testuale (/api/system/logs)
- Svuotamento rapido registri ed emissione audit log (/api/system/logs/clear)
- Download ed esportazione archivio in formato .log o .json (/api/system/logs/download)
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.dependencies import require_admin, require_permission
from app.services.db import db_service
from app.services.log_service import VALID_LOG_LEVELS, log_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/logs", tags=["System Logs & Diagnostics"])


class LogConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = Field(None, description="Abilita o disabilita il logging a runtime")
    level: Optional[str] = Field(None, description="Livello di dettaglio: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    retention_days: Optional[int] = Field(None, ge=0, description="Giorni di conservazione dei log (0 = illimitato)")


@router.get("/config")
async def get_logs_config(
    user: Optional[Dict[str, Any]] = Depends(require_permission("view_logs"))
):
    """
    Restituisce la configurazione attuale del logging di sistema:
    - Stato attivo/disattivato
    - Livello di dettaglio (profondità di analisi)
    - Politica di retention temporale in giorni
    - Statistiche aggregate su righe totali e dimensioni fisiche
    """
    cfg = await db_service.get_logging_config()
    stats = await db_service.get_system_logs_stats()

    return {
        "status": "success",
        "enabled": cfg.get("enabled", True),
        "level": cfg.get("level", "INFO"),
        "retention_days": cfg.get("retention_days", 7),
        "stats": stats,
    }


@router.post("/config")
async def update_logs_config(
    payload: LogConfigUpdateRequest,
    user: Optional[Dict[str, Any]] = Depends(require_permission("action_manage_rules")),
):
    """
    Aggiorna a caldo le impostazioni di diagnostica e riconfigura immediatamente
    il logger di Python senza richiedere il riavvio dell'applicazione.
    """
    actor = user.get("username", "admin") if user else "admin"
    changes = []

    # 1. Modifica livello a caldo
    if payload.level is not None:
        lvl_clean = payload.level.upper().strip()
        if lvl_clean not in VALID_LOG_LEVELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Livello log '{payload.level}' non valido. Valori ammessi: {list(VALID_LOG_LEVELS.keys())}"
            )
        await log_service.set_level(lvl_clean)
        changes.append(f"livello: {lvl_clean}")

    # 2. Toggle Abilitazione a caldo
    if payload.enabled is not None:
        await log_service.set_enabled(payload.enabled)
        changes.append(f"stato: {'ATTIVO' if payload.enabled else 'DISATTIVATO'}")

    # 3. Aggiornamento giorni di retention
    if payload.retention_days is not None:
        await log_service.set_retention_days(payload.retention_days)
        changes.append(f"retention: {payload.retention_days} giorni")

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nessun parametro valido fornito per l'aggiornamento della configurazione."
        )

    # Registrazione allarme di audit per tracciabilità
    await db_service.save_alert(
        alert_type="system_logs_config_updated",
        title="⚙️ Configurazione Log Aggiornata",
        message=f"Impostazioni di diagnostica modificate da '{actor}': {', '.join(changes)}."
    )

    cfg = await db_service.get_logging_config()
    stats = await db_service.get_system_logs_stats()

    return {
        "status": "success",
        "message": f"Configurazione log aggiornata con successo ({', '.join(changes)}).",
        "enabled": cfg.get("enabled", True),
        "level": cfg.get("level", "INFO"),
        "retention_days": cfg.get("retention_days", 7),
        "stats": stats,
    }


@router.get("")
async def get_system_logs(
    limit: int = Query(100, ge=1, le=2000, description="Numero massimo di record da restituire"),
    offset: int = Query(0, ge=0, description="Offset di paginazione"),
    level: Optional[str] = Query(None, description="Filtro per livello (DEBUG, INFO, WARNING, ERROR, CRITICAL o ALL)"),
    q: Optional[str] = Query(None, description="Termine di ricerca nel messaggio o nome logger"),
    start_time: Optional[str] = Query(None, description="Filtro temporale iniziale"),
    end_time: Optional[str] = Query(None, description="Filtro temporale finale"),
    user: Optional[Dict[str, Any]] = Depends(require_permission("view_logs")),
):
    """
    Interroga i registri di sistema indicizzati con ordinamento decrescente (più recenti prima).
    Supporta filtri combinati per livello, ricerca libera sul testo e range temporale.
    """
    # Svuota buffer in memoria su SQLite per garantire la visualizzazione immediata dell'evento più recente
    await log_service.sqlite_handler.flush_to_db()

    norm_level = level.upper().strip() if level and level.upper().strip() != "ALL" else None

    logs = await db_service.get_system_logs(
        limit=limit,
        offset=offset,
        level=norm_level,
        search=q,
        start_time=start_time,
        end_time=end_time,
    )
    total_count = await db_service.get_system_logs_count(
        level=norm_level,
        search=q,
        start_time=start_time,
        end_time=end_time,
    )

    return {
        "status": "success",
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "logs": logs,
    }


@router.post("/clear")
async def clear_system_logs(
    user: Optional[Dict[str, Any]] = Depends(require_permission("action_manage_rules")),
):
    """
    Svuota istantaneamente tutti i log sia dal database SQLite che dal file fisico system.log.
    Genera un evento di audit per certificare l'avvenuta cancellazione.
    """
    actor = user.get("username", "admin") if user else "admin"

    res = await log_service.clear_logs()

    # Emissione allarme di sicurezza / audit
    await db_service.save_alert(
        alert_type="system_logs_cleared",
        title="🗑️ Registro Log di Sistema Svuotato",
        message=f"I log di sistema sono stati azzerati dall'utente '{actor}' (rimossi {res.get('deleted_records', 0)} eventi)."
    )

    return {
        "status": "success",
        "message": f"Registro eventi azzerato con successo ({res.get('deleted_records', 0)} record rimossi).",
        "deleted_records": res.get("deleted_records", 0),
        "timestamp": res.get("timestamp"),
    }


@router.get("/download")
async def download_system_logs(
    format: str = Query("log", regex="^(log|json|txt)$", description="Formato file ('log', 'txt' o 'json')"),
    user: Optional[Dict[str, Any]] = Depends(require_permission("view_logs")),
):
    """
    Scarica l'intero registro dei log di sistema come allegato (.log o .json).
    Include Content-Disposition per il salvataggio immediato sul computer dell'utente.
    """
    # Assicura il flush dei buffer in-memory
    await log_service.sqlite_handler.flush_to_db()
    if log_service.file_handler:
        log_service.file_handler.flush()

    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    fmt = format.lower().strip()

    if fmt == "json":
        filename = f"eero_system_{now_tag}.json"
        all_logs = await db_service.get_system_logs(limit=10000)
        export_payload = {
            "application": settings.app_name,
            "version": settings.app_version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(all_logs),
            "logs": all_logs,
        }
        json_bytes = json.dumps(export_payload, indent=2, ensure_ascii=False).encode("utf-8")
        return Response(
            content=json_bytes,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    # Formato standard .log o .txt
    filename = f"eero_system_{now_tag}.log"
    log_file = log_service.log_file_path

    if log_file.exists() and log_file.stat().st_size > 0:
        return FileResponse(
            path=str(log_file),
            media_type="text/plain; charset=utf-8",
            filename=filename,
        )

    # Fallback se il file su disco non è ancora stato scritto: estrazione diretta da SQLite
    all_logs = await db_service.get_system_logs(limit=5000)
    lines = [
        f"{l['timestamp']} [{l['level']}] {l['logger_name']}: {l['message']}"
        for l in reversed(all_logs)
    ]
    log_text = "\n".join(lines) if lines else f"# {settings.app_name} System Log - {datetime.now(timezone.utc).isoformat()}\n# Nessun log registrato."
    return Response(
        content=log_text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
