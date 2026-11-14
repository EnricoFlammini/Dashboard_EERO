"""
In-Memory DNS Resolver Cache for Python / Docker environments
=============================================================
Provides a lightweight, thread-safe TTL cache around `socket.getaddrinfo`.
Prevents repetitive outbound DNS queries (UDP port 53) in containerized
environments that lack a local DNS caching daemon (e.g. nscd, systemd-resolved),
resolving Issue #24 (excessive DNS queries to api-user.e2ro.com).
"""

import ipaddress
import logging
import os
import random
import socket
import struct
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.i18n import log_event

logger = logging.getLogger(__name__)

_orig_getaddrinfo = socket.getaddrinfo
_dns_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
_dns_lock = threading.Lock()
_dns_cache_enabled = False
_dns_cache_ttl = 300  # 5 minutes default TTL
_stats = {"hits": 0, "misses": 0, "custom_hits": 0}
_custom_servers: List[Tuple[str, int]] = []
_domain_rules: List[Tuple[str, List[Tuple[str, int]]]] = []


def _parse_dns_server(entry: str) -> Optional[Tuple[str, int]]:
    """Parses 'IP' or 'IP:PORT' (including '[IPv6]:PORT') into (ip, port)."""
    raw = (entry or "").strip()
    if not raw:
        return None
    host = raw
    port = 53
    if raw.startswith("[") and "]" in raw:
        end = raw.index("]")
        host = raw[1:end]
        rest = raw[end + 1:].strip()
        if rest.startswith(":") and rest[1:].isdigit():
            port = int(rest[1:])
    elif raw.count(":") == 1:
        maybe_host, maybe_port = raw.split(":", 1)
        if maybe_port.isdigit():
            host, port = maybe_host.strip(), int(maybe_port)
    try:
        ipaddress.ip_address(host)
        return (host, port)
    except ValueError:
        logger.warning("Ignoring invalid custom DNS server IP: %s", entry)
        return None


def _parse_server_list(servers_str: str) -> List[Tuple[str, int]]:
    result: List[Tuple[str, int]] = []
    for part in (servers_str or "").replace(";", ",").split(","):
        parsed = _parse_dns_server(part)
        if parsed:
            result.append(parsed)
    return result


def configure_custom_dns(servers: str = "", domains: str = "") -> None:
    """Configures custom and split-DNS servers/domains and resets the cache."""
    global _custom_servers, _domain_rules
    parsed_servers = _parse_server_list(servers)
    parsed_rules: List[Tuple[str, List[Tuple[str, int]]]] = []

    for token in (domains or "").replace(";", ",").split(","):
        item = token.strip().lower()
        if not item:
            continue
        if "=" in item:
            pattern, srv_spec = item.split("=", 1)
            rule_servers = _parse_server_list(srv_spec) or parsed_servers
            pattern = pattern.strip().rstrip(".")
        else:
            pattern = item.rstrip(".")
            rule_servers = parsed_servers
        if pattern and rule_servers:
            parsed_rules.append((pattern, rule_servers))

    with _dns_lock:
        _custom_servers = parsed_servers
        _domain_rules = parsed_rules
        _dns_cache.clear()


def _match_domain_pattern(hostname: str, pattern: str) -> bool:
    host = hostname.strip().lower().rstrip(".")
    pat = pattern.strip().lower().rstrip(".")
    if not host or not pat:
        return False
    if pat.startswith("*."):
        suffix = pat[2:]
        return host == suffix or host.endswith("." + suffix)
    if pat.startswith("."):
        suffix = pat[1:]
        return host == suffix or host.endswith("." + suffix)
    return host == pat or host.endswith("." + pat)


def _select_custom_servers(host: str) -> List[Tuple[str, int]]:
    if not isinstance(host, str) or not host:
        return []
    try:
        ipaddress.ip_address(host)
        return []
    except ValueError:
        pass
    lowered = host.strip().lower().rstrip(".")
    if not lowered or lowered == "localhost":
        return []

    for pattern, servers in _domain_rules:
        if _match_domain_pattern(lowered, pattern):
            return servers

    # If no explicit domain rules are set, apply global custom servers to FQDNs
    if not _domain_rules and _custom_servers and "." in lowered:
        return _custom_servers
    return []


def _encode_dns_name(hostname: str) -> bytes:
    labels = [lbl.encode("idna") for lbl in hostname.rstrip(".").split(".") if lbl]
    return b"".join(bytes([len(lbl)]) + lbl for lbl in labels) + b"\x00"


def _skip_dns_name(data: bytes, offset: int) -> int:
    length = len(data)
    while offset < length:
        byte = data[offset]
        if byte == 0:
            return offset + 1
        if (byte & 0xC0) == 0xC0:
            return offset + 2
        offset += 1 + byte
    return length


def _build_dns_query(hostname: str, qtype: int, txid: int) -> bytes:
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    question = _encode_dns_name(hostname) + struct.pack("!HH", qtype, 1)
    return header + question


def _parse_dns_response(data: bytes, txid: int, qtype: int) -> List[str]:
    if len(data) < 12:
        return []
    resp_id, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", data[:12])
    if resp_id != txid or (flags & 0x000F) != 0:
        return []

    offset = 12
    for _ in range(qdcount):
        offset = _skip_dns_name(data, offset)
        offset += 4

    ips: List[str] = []
    for _ in range(ancount):
        if offset >= len(data):
            break
        offset = _skip_dns_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, _, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlength]
        offset += rdlength
        if rclass != 1 or rtype != qtype:
            continue
        if qtype == 1 and len(rdata) == 4:
            ips.append(socket.inet_ntop(socket.AF_INET, rdata))
        elif qtype == 28 and len(rdata) == 16:
            ips.append(socket.inet_ntop(socket.AF_INET6, rdata))
    return ips


def _query_udp_dns(hostname: str, qtype: int, server: Tuple[str, int], timeout: float = 2.0) -> List[str]:
    txid = random.randint(1, 65534)
    packet = _build_dns_query(hostname, qtype, txid)
    srv_ip, srv_port = server
    af = socket.AF_INET6 if ":" in srv_ip else socket.AF_INET
    with socket.socket(af, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (srv_ip, srv_port))
        resp, _ = sock.recvfrom(4096)
    return _parse_dns_response(resp, txid, qtype)


def _normalize_port(port: Any) -> int:
    if port is None or port == "":
        return 0
    if isinstance(port, int):
        return port
    try:
        return int(port)
    except (TypeError, ValueError):
        return socket.getservbyname(str(port))


def _resolve_via_custom_dns(
    host: str,
    port: Any,
    family: int,
    socktype: int,
    proto: int,
    servers: List[Tuple[str, int]],
) -> List[Any]:
    try:
        port_int = _normalize_port(port)
    except OSError:
        port_int = 0

    eff_type = socktype or socket.SOCK_STREAM
    eff_proto = proto or (socket.IPPROTO_TCP if eff_type == socket.SOCK_STREAM else socket.IPPROTO_UDP if eff_type == socket.SOCK_DGRAM else 0)

    qtypes: List[Tuple[int, int]] = []
    if family in (0, socket.AF_INET):
        qtypes.append((1, socket.AF_INET))
    if family in (0, socket.AF_INET6):
        qtypes.append((28, socket.AF_INET6))

    results: List[Any] = []
    for srv in servers:
        for qtype, res_family in qtypes:
            try:
                ips = _query_udp_dns(host, qtype, srv)
            except OSError:
                continue
            for ip in ips:
                sockaddr = (ip, port_int) if res_family == socket.AF_INET else (ip, port_int, 0, 0)
                results.append((res_family, eff_type, eff_proto, "", sockaddr))
        if results:
            break
    return results


def _cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Pass-through if host is None or cache is disabled
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

    result = None
    custom_servers = _select_custom_servers(host)
    if custom_servers:
        result = _resolve_via_custom_dns(host, port, family, type, proto, custom_servers)
        if result:
            with _dns_lock:
                _stats["custom_hits"] += 1

    # Cache miss or custom DNS fallback: perform genuine socket resolution
    # (prefer IPv4 over IPv6 when family=AF_UNSPEC - Issue #98)
    if not result:
        result = _orig_getaddrinfo(host, port, family, type, proto, flags)

    if isinstance(result, list) and len(result) > 1 and family == 0:
        result = sorted(result, key=lambda item: 0 if item[0] == socket.AF_INET else 1)

    with _dns_lock:
        _stats["misses"] += 1
        _dns_cache[cache_key] = (now + _dns_cache_ttl, result)

    return result


def enable_dns_cache(ttl_seconds: int = 300, custom_servers: str = "", custom_domains: str = "") -> None:
    """Enables transparent in-memory DNS caching (and optional custom/split DNS) for socket.getaddrinfo."""
    global _dns_cache_enabled, _dns_cache_ttl
    _dns_cache_ttl = max(30, ttl_seconds)
    env_servers = custom_servers if custom_servers else os.getenv("CUSTOM_DNS_SERVERS", "")
    env_domains = custom_domains if custom_domains else os.getenv("CUSTOM_DNS_DOMAINS", "")
    configure_custom_dns(env_servers, env_domains)
    if not _dns_cache_enabled:
        socket.getaddrinfo = _cached_getaddrinfo
        _dns_cache_enabled = True
        log_event(logger, logging.INFO, "log_system.dns_cache_enabled", ttl=_dns_cache_ttl)


def disable_dns_cache() -> None:
    """Disables DNS caching and restores default socket.getaddrinfo."""
    global _dns_cache_enabled
    if _dns_cache_enabled:
        socket.getaddrinfo = _orig_getaddrinfo
        _dns_cache_enabled = False
        with _dns_lock:
            _dns_cache.clear()
        log_event(logger, logging.INFO, "log_system.dns_cache_disabled")


def clear_dns_cache() -> None:
    """Clears all cached DNS entries."""
    with _dns_lock:
        _dns_cache.clear()


def get_dns_cache_stats() -> Dict[str, Any]:
    """Returns telemetry statistics for DNS cache hits, misses, and custom DNS rules."""
    with _dns_lock:
        return {
            "enabled": _dns_cache_enabled,
            "ttl_seconds": _dns_cache_ttl,
            "entries_count": len(_dns_cache),
            "hits": _stats["hits"],
            "misses": _stats["misses"],
            "custom_hits": _stats["custom_hits"],
            "custom_servers_count": len(_custom_servers),
            "custom_domain_rules_count": len(_domain_rules),
        }
