"""
Public WAN IP resolution & double-NAT detection (Issue #115).

When the eero gateway sits behind an ISP modem/router (or in Bridge Mode), the eero
Cloud API reports the upstream router's private address as the WAN IP. In that case,
and only then, the true public IP is looked up over HTTPS and cached, so external
dashboards can read it from GET /api/network/public-ip.
"""
import ipaddress
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger("eero_dashboard.public_ip")

# Plain-text or JSON IPv4 echo services, tried in order.
LOOKUP_URLS = (
    "https://api.ipify.org?format=json",
    "https://ipv4.icanhazip.com",
    "https://checkip.amazonaws.com",
)
CACHE_TTL = timedelta(minutes=30)
MIN_FORCE_INTERVAL = timedelta(minutes=1)
FAILURE_RETRY = timedelta(minutes=5)
LOOKUP_TIMEOUT_SECONDS = 5.0

_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def classify_ip(value: Optional[str]) -> Optional[str]:
    """'public', 'private' (RFC 1918 / ULA / link-local), 'cgnat' (RFC 6598) or None when not an IP."""
    try:
        ip = ipaddress.ip_address(str(value or "").strip())
    except ValueError:
        return None
    if ip.version == 4 and ip in _CGNAT:
        return "cgnat"
    if ip.is_global:
        return "public"
    return "private"


def _parse_lookup_response(text: str) -> Optional[str]:
    text = text.strip()
    if text.startswith("{"):
        try:
            text = str(json.loads(text).get("ip", ""))
        except ValueError:
            return None
    return text if classify_ip(text) == "public" else None


class PublicIPService:
    def __init__(self) -> None:
        self._ip: Optional[str] = None
        self._checked_at: Optional[datetime] = None
        self._next_attempt: Optional[datetime] = None

    def reset(self) -> None:
        self._ip = None
        self._checked_at = None
        self._next_attempt = None

    async def _lookup(self) -> Optional[str]:
        async with httpx.AsyncClient(timeout=LOOKUP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            for url in LOOKUP_URLS:
                try:
                    res = await client.get(url, headers={"Accept": "application/json, text/plain"})
                    if res.status_code == 200:
                        ip = _parse_lookup_response(res.text)
                        if ip:
                            return ip
                except httpx.HTTPError as e:
                    logger.debug(f"Public IP lookup via {url} failed: {e}")
        return None

    async def get_external_ip(self, force: bool = False) -> Optional[str]:
        """The cached external IP, refreshed every 30 minutes (5 after a failed attempt)."""
        now = datetime.now(timezone.utc)
        if force and self._checked_at and now - self._checked_at < MIN_FORCE_INTERVAL:
            force = False  # keep manual refreshes from hammering the lookup services
        if not force and self._next_attempt and now < self._next_attempt:
            return self._ip
        ip = await self._lookup()
        if ip:
            self._ip = ip
            self._checked_at = now
            self._next_attempt = now + CACHE_TTL
        else:
            logger.warning("Public IP lookup failed on every service; keeping the last known value.")
            self._next_attempt = now + FAILURE_RETRY
        return self._ip

    async def resolve(self, eero_wan_ip: Optional[str], force: bool = False) -> Dict[str, Any]:
        """Combines the WAN IP reported by eero with an external lookup when that IP is not public."""
        wan_type = classify_ip(eero_wan_ip)
        result: Dict[str, Any] = {
            "public_ip": None,
            "source": None,
            "eero_wan_ip": eero_wan_ip or None,
            "eero_wan_ip_type": wan_type,
            "double_nat": wan_type == "private",
            "cgnat": wan_type == "cgnat",
            "lookup_enabled": settings.public_ip_lookup,
            "checked_at": None,
        }
        if wan_type == "public":
            result["public_ip"] = eero_wan_ip
            result["source"] = "eero"
            return result
        if not settings.public_ip_lookup:
            return result
        ip = await self.get_external_ip(force=force)
        if ip:
            result["public_ip"] = ip
            result["source"] = "lookup"
            result["checked_at"] = self._checked_at.isoformat() if self._checked_at else None
        return result


public_ip_service = PublicIPService()
