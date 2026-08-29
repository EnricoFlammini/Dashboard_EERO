from fastapi import APIRouter, HTTPException, Query
from app.services.updater import updater_service

router = APIRouter(prefix="/api/system", tags=["System & Updates"])


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
