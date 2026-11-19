"""
eero client domain mixins package.
"""
from app.services.eero.const import (
    EERO_API_BASE,
    IPV6_ULA_NET,
    _IPV6_ULA_NET,
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

__all__ = [
    "EERO_API_BASE",
    "IPV6_ULA_NET",
    "parse_speed_mbps",
    "format_speed_mbps",
    "map_eero_device_type",
    "get_adguard_tags",
    "EeroBaseMixin",
    "EeroAuthMixin",
    "EeroNetworkMixin",
    "EeroMeshMixin",
    "EeroDevicesMixin",
    "EeroSecurityMixin",
]
