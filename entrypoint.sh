#!/bin/sh
set -e

# ==============================================================================
# eero Dashboard - Container Entrypoint
# Gestione trasparente e retrocompatibile dei permessi della directory dati.
# Se il container è avviato come root (default di Docker), adegua la proprietà
# di /app/data a appuser (UID 10001) e cede i privilegi tramite su-exec.
# ==============================================================================

if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data
    chown -R appuser:appgroup /app/data 2>/dev/null || true
    chmod -R 775 /app/data 2>/dev/null || true
    exec su-exec appuser "$@"
fi

# Se avviato già con utente non-root (es. docker run --user 10001)
exec "$@"
