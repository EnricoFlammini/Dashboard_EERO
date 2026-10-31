"""
Rate Limiter in-memory per protezione da attacchi brute-force e throttling delle API.
==================================================================================
Implementa una finestra temporale a scorrimento (sliding window) con blocco temporaneo,
completamente thread-safe e a zero dipendenze esterne.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple


class InMemoryRateLimiter:
    """Rate limiter in-memory con sliding window e blocco temporaneo."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, block_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._lock = threading.Lock()
        # key -> list of float timestamps
        self._attempts: Dict[str, List[float]] = {}
        # key -> float timestamp of unblock time
        self._blocked_until: Dict[str, float] = {}

    def _cleanup_unlocked(self, now: float) -> None:
        """Rimuove record obsoleti per prevenire memory leak (deve essere invocato sotto _lock)."""
        cutoff = now - max(self.window_seconds, self.block_seconds)
        expired_keys = []
        for key, timestamps in self._attempts.items():
            valid_ts = [t for t in timestamps if t > cutoff]
            if valid_ts:
                self._attempts[key] = valid_ts
            else:
                expired_keys.append(key)

        for k in expired_keys:
            self._attempts.pop(k, None)

        # Pulizia blocchi scaduti
        expired_blocks = [k for k, unblock in self._blocked_until.items() if unblock <= now]
        for k in expired_blocks:
            self._blocked_until.pop(k, None)

    def is_limited(self, key: str) -> Tuple[bool, int]:
        """
        Verifica se la chiave è attualmente bloccata o ha superato la soglia.
        Restituisce (True, secondi_rimanenti) se limitata, altrimenti (False, 0).
        """
        now = time.monotonic()
        with self._lock:
            # 1. Controlla blocco esplicito
            unblock_time = self._blocked_until.get(key, 0.0)
            if now < unblock_time:
                return True, int(unblock_time - now) + 1

            # 2. Controlla tentativi nella finestra temporale
            timestamps = self._attempts.get(key, [])
            recent = [t for t in timestamps if t > (now - self.window_seconds)]
            if len(recent) >= self.max_attempts:
                # Applica il blocco
                self._blocked_until[key] = now + self.block_seconds
                return True, self.block_seconds

            return False, 0

    def record_failure(self, key: str) -> Tuple[bool, int]:
        """
        Registra un tentativo fallito.
        Restituisce (True, secondi_rimanenti) se la chiave è entrata in stato di blocco.
        """
        now = time.monotonic()
        with self._lock:
            self._cleanup_unlocked(now)
            timestamps = self._attempts.setdefault(key, [])
            timestamps.append(now)

            recent = [t for t in timestamps if t > (now - self.window_seconds)]
            self._attempts[key] = recent

            if len(recent) >= self.max_attempts:
                self._blocked_until[key] = now + self.block_seconds
                return True, self.block_seconds

            return False, 0

    def record_hit(self, key: str) -> Tuple[bool, int]:
        """
        Registra un hit incondizionato (es. per rate limit su richieste OTP o invocazioni API).
        Restituisce (True, retry_after) se il limite è stato superato, altrimenti (False, 0).
        """
        now = time.monotonic()
        with self._lock:
            self._cleanup_unlocked(now)

            # Verifica se già bloccato
            unblock_time = self._blocked_until.get(key, 0.0)
            if now < unblock_time:
                return True, int(unblock_time - now) + 1

            timestamps = self._attempts.setdefault(key, [])
            timestamps.append(now)
            recent = [t for t in timestamps if t > (now - self.window_seconds)]
            self._attempts[key] = recent

            if len(recent) > self.max_attempts:
                self._blocked_until[key] = now + self.block_seconds
                return True, self.block_seconds

            return False, 0

    def reset(self, key: str) -> None:
        """Resetta i tentativi e l'eventuale blocco per la chiave specificata (es. su login riuscito)."""
        with self._lock:
            self._attempts.pop(key, None)
            self._blocked_until.pop(key, None)


def get_client_ip(request) -> str:
    """Estrae l'indirizzo IP del client rispettando gli header del reverse proxy se presenti."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    return request.client.host if request.client else "unknown"


# Istanze preconfigurate per l'applicazione
auth_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60, block_seconds=300)
cloud_auth_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60, block_seconds=180)
