# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

# Imposta variabili d'ambiente per Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Crea directory applicativa
WORKDIR /app

# Installa pacchetti di sistema essenziali e pulisci la cache apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente e la documentazione
COPY app/ /app/app/
COPY changelog.md /app/changelog.md
COPY README.md /app/README.md

# Crea la directory dati per la persistenza di database e sessione
RUN mkdir -p /app/data

# Espone la porta del container
EXPOSE 8000

# Comando di avvio del server FastAPI con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
