"""
In-Memory DNS Resolver Cache for Python / Docker environments
=============================================================
Provides a lightweight, thread-safe TTL cache around `socket.getaddrinfo`.
Prevents repetitive outbound DNS queries (UDP port 53) in containerized
environments that lack a local DNS caching daemon (e.g. nscd, systemd-resolved),
resolving Issue #24 (excessive DNS queries to api-user.e2ro.com).
"""

import socket
import threading
import time
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

_orig_getaddrinfo = socket.getaddrinfo
_dns_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
_dns_lock = threading.Lock()
_dns_cache_enabled = False
_dns_cache_ttl = 300  # 5 minutes default TTL
_stats = {"hits": 0, "misses": 0}


def _cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Pass-through if host is None or already numeric IP
    if not host or not _dns_cache_enabled:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)

    cache_key = (host, port, family, type, proto, flags)
    now = time.monotonic()

    with _dns_lock:
        if cache_key in _dns_cache:
            expiry, result = _dns_cache[cache_key]
            if now < expiry:
                _stats["hits"] += 1
                return result
            else:
                del _dns_cache[cache_key]

    # Cache miss: perform genuine socket resolution
    result = _orig_getaddrinfo(host, port, family, type, proto, flags)

    with _dns_lock:
        _stats["misses"] += 1
        _dns_cache[cache_key] = (now + _dns_cache_ttl, result)

    return result


def enable_dns_cache(ttl_seconds: int = 300) -> None:
    """Enables transparent in-memory DNS caching for socket.getaddrinfo."""
    global _dns_cache_enabled, _dns_cache_ttl
    _dns_cache_ttl = max(30, ttl_seconds)
    if not _dns_cache_enabled:
        socket.getaddrinfo = _cached_getaddrinfo
        _dns_cache_enabled = True
        logger.info(f"In-memory DNS caching enabled (TTL: {_dns_cache_ttl}s).")


def disable_dns_cache() -> None:
    """Disables DNS caching and restores default socket.getaddrinfo."""
    global _dns_cache_enabled
    if _dns_cache_enabled:
        socket.getaddrinfo = _orig_getaddrinfo
        _dns_cache_enabled = False
        with _dns_lock:
            _dns_cache.clear()
        logger.info("In-memory DNS caching disabled.")


def clear_dns_cache() -> None:
    """Clears all cached DNS entries."""
    with _dns_lock:
        _dns_cache.clear()


def get_dns_cache_stats() -> Dict[str, Any]:
    """Returns telemetry statistics for DNS cache hits, misses, and entries."""
    with _dns_lock:
        return {
            "enabled": _dns_cache_enabled,
            "ttl_seconds": _dns_cache_ttl,
            "entries_count": len(_dns_cache),
            "hits": _stats["hits"],
            "misses": _stats["misses"],
        }
