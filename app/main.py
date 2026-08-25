import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers import auth, automations, devices, manual, metrics, network, speedtest
from app.services.db import db_service
from app.services.eero_client import eero_client
from app.services.poller import background_poller

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
    logger.info("Applicazione terminata correttamente.")


# Inizializzazione FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Self-Hosted Management Suite, Bandwidth Historian & Built-in User Manual for Amazon eero",
    lifespan=lifespan,
)

# Configurazione Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(metrics.router)
app.include_router(speedtest.router)
app.include_router(automations.router)
app.include_router(manual.router)


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
    return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.app_name})
