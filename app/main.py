import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers import analytics, auth, automations, devices, manual, metrics, network, profiles, speedtest, system
from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.poller import background_poller
from app.services.dns_cache import enable_dns_cache, disable_dns_cache

# Configurazione Logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eero_dashboard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione ciclo di vita dell'applicazione: avvio database e poller in background."""
    logger.info("=" * 60)
    logger.info(f"Avvio {settings.app_name} v{settings.app_version}")
    logger.info(f"Data directory: {settings.data_path.resolve()}")
    logger.info("=" * 60)

    # 0. Attivazione In-Memory DNS Caching (Issue #24)
    enable_dns_cache(ttl_seconds=300)

    # 1. Inizializzazione Database SQLite
    await db_service.init_db()

    # 2. Caricamento Sessione eero
    eero_client.load_session()

    # 3. Avvio Poller Asincrono in Background
    await background_poller.start()

    yield

    # Chiusura pulita dei processi in background
    logger.info("Chiusura in corso dei servizi in background...")
    await background_poller.stop()
    await eero_client.close()
    disable_dns_cache()
    logger.info("Applicazione terminata correttamente.")


# Inizializzazione FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Self-Hosted Management Suite, Bandwidth Historian & Built-in User Manual for Amazon eero",
    lifespan=lifespan,
    # Swagger UI / ReDoc / schema OpenAPI solo con API_DOCS=true: le API non hanno autenticazione
    docs_url="/docs" if settings.api_docs else None,
    redoc_url="/redoc" if settings.api_docs else None,
    openapi_url="/openapi.json" if settings.api_docs else None,
)

# Configurazione Middleware CORS
# La SPA è servita dalla stessa origine delle API: il CORS serve solo per origini esterne elencate in
# CORS_ORIGINS (es. "http://homeassistant.local:8123"). Con allow_origins=["*"] qualsiasi sito aperto
# nel browser poteva leggere e modificare le API della dashboard. "*" resta possibile ma sconsigliato.
cors_origins = [origin.strip().rstrip("/").lower() for origin in settings.cors_origins.split(",") if origin.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _is_cross_origin_write(request: Request) -> bool:
    """True se una richiesta di modifica arriva da una pagina di un'altra origine (CSRF).

    Stessa logica di CrossOriginProtection di Go: Sec-Fetch-Site quando il browser lo invia (solo HTTPS e
    localhost), altrimenti confronto tra Origin e Host. Le richieste senza Origin (curl, Home Assistant REST,
    script) non provengono da una pagina web e restano consentite.
    """
    origin = request.headers.get("origin")
    if origin and ("*" in cors_origins or origin.rstrip("/").lower() in cors_origins):
        return False
    sec_fetch_site = request.headers.get("sec-fetch-site")
    if sec_fetch_site is not None:
        return sec_fetch_site not in ("same-origin", "none")
    if origin is None:
        return False
    if origin == "null":
        return True
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return urlsplit(origin).netloc.lower() != host.split(",")[0].strip().lower()


@app.middleware("http")
async def block_cross_origin_writes(request: Request, call_next):
    """Rifiuta POST/PUT/PATCH/DELETE inviati da pagine di altri siti: le POST senza body non passano dal preflight CORS."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and _is_cross_origin_write(request):
        return JSONResponse(status_code=403, content={"detail": "Cross-origin request blocked"})
    return await call_next(request)


# Definizione Percorsi Static e Template
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Registrazione Router API
app.include_router(auth.router)
app.include_router(network.router)
app.include_router(devices.router)
app.include_router(profiles.router)
app.include_router(metrics.router)
app.include_router(speedtest.router)
app.include_router(automations.router)
app.include_router(manual.router)
app.include_router(system.router)
app.include_router(analytics.router)


@app.get("/api/health")
async def healthcheck():
    """Endpoint di controllo salute per Docker Healthcheck."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_authenticated": eero_client.is_authenticated,
        "demo_mode": settings.demo_mode or (bool(eero_client.user_token) and eero_client.user_token.startswith("demo_")),
    }


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Serve la Single Page Application (SPA) della Dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.app_name, "app_version": settings.app_version}
    )
