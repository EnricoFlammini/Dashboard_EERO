# syntax=docker/dockerfile:1

# ==============================================================================
# STAGE 1: Builder (Compilazione dipendenze e isolamento virtualenv)
# ==============================================================================
FROM python:3.12-alpine AS builder

WORKDIR /app

# Installa pacchetti di build necessari per compilare eventuali wheel native su musl
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    zlib-dev \
    jpeg-dev

# Crea ambiente virtuale pulito in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Installa le dipendenze Python con tooling aggiornato
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade "pip>=26.2.0" "setuptools>=83.0.0" wheel && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# STAGE 2: Runner (Immagine finale ultra-leggera, hardened e utente non-root)
# ==============================================================================
FROM python:3.12-alpine AS runner

# Build arguments per versionamento e build number (iniettati in CI/CD)
ARG APP_VERSION="1.6.2"
ARG BUILD_NUMBER="1"
# Source branch/commit shown on the Updates page (.git is not copied into the image)
ARG GIT_BRANCH=""
ARG GIT_COMMIT=""

# Imposta variabili d'ambiente per Python, metadati di release e path virtualenv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    APP_VERSION=${APP_VERSION} \
    BUILD_NUMBER=${BUILD_NUMBER} \
    GIT_BRANCH=${GIT_BRANCH} \
    GIT_COMMIT=${GIT_COMMIT} \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Installa solo i pacchetti e le librerie runtime essenziali (curl per healthcheck, tzdata, ca-certificates, su-exec)
RUN apk add --no-cache \
    curl \
    tzdata \
    ca-certificates \
    libjpeg-turbo \
    zlib \
    su-exec

# Crea utente e gruppo di sistema non-root dedicati (Principio del Least Privilege)
RUN addgroup -g 10001 -S appgroup && \
    adduser -u 10001 -S appuser -G appgroup

# Copia l'ambiente virtuale completo precompilato dallo stage builder
COPY --from=builder /opt/venv /opt/venv

# Copia il codice sorgente, documentazione e script di avvio entrypoint
COPY app/ /app/app/
COPY changelog.md /app/changelog.md
COPY README.md /app/README.md
COPY entrypoint.sh /app/entrypoint.sh

# Prepara la directory dati per la persistenza e assegna i permessi necessari
RUN mkdir -p /app/data && \
    chown -R appuser:appgroup /app/data /app && \
    chmod +x /app/entrypoint.sh

# Espone la porta del container
EXPOSE 8000

# Docker / Container Manager native healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Entrypoint trasparente: self-healing permessi volume host ed esecuzione sicura come utente non-root appuser
ENTRYPOINT ["/app/entrypoint.sh"]

# Comando predefinito di avvio del server FastAPI con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]

