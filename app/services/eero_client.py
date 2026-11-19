"""
Asynchronous Python Client for eero REST API (v2.2).
Provides EeroClient assembled from domain mixins (Auth, Network, Mesh, Devices, Security, Demo).
Full backward compatibility for all existing imports and API routes.
"""
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import httpx
import logging

from app.config import settings
from app.services.demo_fixtures import DemoFixturesMixin
from app.services.eero.const import (
    EERO_API_BASE,
    IPV6_ULA_NET,
    parse_speed_mbps,
    format_speed_mbps,
    map_eero_device_type,
    get_adguard_tags,
)
from app.services.eero.base import EeroBaseMixin
from app.services.eero.auth import EeroAuthMixin
from app.services.eero.network import EeroNetworkMixin
from app.services.eero.mesh import EeroMeshMixin
from app.services.eero.devices import EeroDevicesMixin
from app.services.eero.security import EeroSecurityMixin

logger = logging.getLogger(__name__)


class EeroClient(
    DemoFixturesMixin,
    EeroBaseMixin,
    EeroAuthMixin,
    EeroNetworkMixin,
    EeroMeshMixin,
    EeroDevicesMixin,
    EeroSecurityMixin,
):
    """Async Client for eero REST API 2.2 with local persistence and Demo Mode simulator."""

    def __init__(self, session_path: Optional[Path] = None):
        self.session_path = session_path or settings.session_file_path
        self.user_token: Optional[str] = None
        self.account_info: Optional[Dict[str, Any]] = None
        self.current_network_id: Optional[str] = None
        self.available_networks: List[Dict[str, Any]] = []
        self.saved_live_token: Optional[str] = None
        self.saved_live_network_id: Optional[str] = None
        self.saved_live_networks: List[Dict[str, Any]] = []
        self.saved_live_account_info: Optional[Dict[str, Any]] = None
        self.current_gateway_id: Optional[str] = None
        self.current_gateway_url: Optional[str] = None
        self.current_gateway_name: Optional[str] = None
        self.current_gateway_ip: Optional[str] = None
        self._last_network_details: Optional[Dict[str, Any]] = None
        self._last_eeros: Optional[List[Dict[str, Any]]] = None
        self._is_demo_active: bool = False
        self._http_client: Optional[httpx.AsyncClient] = None
        self._demo_networks_store: Dict[str, Dict[str, Any]] = {}
        self._data_usage_endpoint_available: bool = True
        self._last_data_usage_check: float = 0.0
        self._cached_cloud_data_usage: Dict[str, Dict[str, Any]] = {}
        self.load_session()

        # Simulated Demo State
        self._demo_state = self._init_demo_state()
        # Tassi base immutabili dei dispositivi demo (id -> (download, upload) in Mbps)
        self._demo_base_rates: Dict[str, Tuple[float, float]] = {}


# Istanza singleton client eero
eero_client = EeroClient()

__all__ = [
    "EeroClient",
    "eero_client",
    "EERO_API_BASE",
    "IPV6_ULA_NET",
    "parse_speed_mbps",
    "format_speed_mbps",
    "map_eero_device_type",
    "get_adguard_tags",
]
