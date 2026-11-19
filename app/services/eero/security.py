"""
Security settings, IPv6 pinhole firewall rules, and eero Plus Guardian VPN status.
"""
from typing import Dict, Any, List, Optional
import logging
import time
from app.config import settings
from app.i18n import tr
from app.services.eero.const import EERO_API_BASE

logger = logging.getLogger(__name__)


class EeroSecurityMixin:
    """Metodi per regole firewall IPv6 (pinholes) e Guardian VPN eero Plus."""

    async def get_ipv6_firewall_rules(self, network_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera le regole del firewall IPv6 (pinhole) con risoluzione automatica e fallback endpoint (Issue #90)."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for IPv6 rules: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        if not clean_net_id:
            return []

        if self.is_demo_mode:
            return self._get_demo_ipv6_firewall_rules()

        candidate_endpoints = [
            f"{EERO_API_BASE}/networks/{clean_net_id}/firewall_rules",
            f"{EERO_API_BASE}/networks/{clean_net_id}/ipv6/firewall_rules",
            f"{EERO_API_BASE}/networks/{clean_net_id}/pinholes",
        ]

        try:
            async with self._client_session() as client:
                for endpoint in candidate_endpoints:
                    try:
                        resp = await client.get(endpoint, headers=self._get_headers())
                        if resp.status_code == 200:
                            raw_data = resp.json().get("data", [])
                            rules = raw_data.get("rules", []) if isinstance(raw_data, dict) else (raw_data if isinstance(raw_data, list) else [])
                            normalized = []
                            for idx, r in enumerate(rules):
                                if not isinstance(r, dict):
                                    continue
                                r_url = str(r.get("url") or "")
                                r_id = str(r.get("id") or (r_url.rstrip("/").split("/")[-1] if r_url else f"rule_{idx}"))
                                normalized.append({
                                    "id": r_id,
                                    "url": r_url,
                                    "device_name": r.get("device_name") or r.get("nickname") or r.get("hostname") or r.get("mac") or "Device",
                                    "mac": r.get("mac") or r.get("device_mac") or "",
                                    "protocol": str(r.get("protocol") or "tcp").lower(),
                                    "ports": str(r.get("ports") or r.get("port_range") or r.get("port") or ""),
                                    "enabled": bool(r.get("enabled", True)),
                                })
                            return normalized
                    except Exception as sub_err:
                        logger.debug(f"Candidate endpoint {endpoint} error: {sub_err}")

                # Fallback: check network details for embedded firewall/pinhole rules
                try:
                    resp_net = await client.get(f"{EERO_API_BASE}/networks/{clean_net_id}", headers=self._get_headers())
                    if resp_net.status_code == 200:
                        net_data = resp_net.json().get("data", {})
                        embedded_rules = net_data.get("firewall_rules") or net_data.get("ipv6_firewall_rules") or net_data.get("pinholes") or []
                        if isinstance(embedded_rules, list) and embedded_rules:
                            normalized = []
                            for idx, r in enumerate(embedded_rules):
                                if not isinstance(r, dict):
                                    continue
                                r_url = str(r.get("url") or "")
                                r_id = str(r.get("id") or (r_url.rstrip("/").split("/")[-1] if r_url else f"rule_{idx}"))
                                normalized.append({
                                    "id": r_id,
                                    "url": r_url,
                                    "device_name": r.get("device_name") or r.get("nickname") or r.get("hostname") or r.get("mac") or "Device",
                                    "mac": r.get("mac") or r.get("device_mac") or "",
                                    "protocol": str(r.get("protocol") or "tcp").lower(),
                                    "ports": str(r.get("ports") or r.get("port_range") or r.get("port") or ""),
                                    "enabled": bool(r.get("enabled", True)),
                                })
                            return normalized
                except Exception as net_err:
                    logger.debug(f"Fallback network details error: {net_err}")

        except Exception as e:
            logger.debug(f"IPv6 firewall rules fetch error: {e}")
        return []

    async def add_ipv6_firewall_rule(self, rule: Dict[str, Any], network_id: Optional[str] = None) -> Dict[str, Any]:
        """Crea una nuova regola pinhole nel firewall IPv6 (Issue #90)."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for IPv6 rules: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        if not clean_net_id:
            raise ValueError(tr("eero.no_network_selected"))
        mac = str(rule.get("mac") or "").strip()
        ports = str(rule.get("ports") or "").strip()
        protocol = str(rule.get("protocol") or "tcp").strip().lower()
        device_name = str(rule.get("device_name") or mac or "Device").strip()
        if not ports:
            raise ValueError("Port or port range is required")

        if self.is_demo_mode:
            return self._add_demo_ipv6_firewall_rule(device_name, mac, protocol, ports)

        payload = {
            "mac": mac,
            "protocol": protocol,
            "ports": ports,
            "enabled": True,
        }
        candidate_endpoints = [
            f"{EERO_API_BASE}/networks/{clean_net_id}/firewall_rules",
            f"{EERO_API_BASE}/networks/{clean_net_id}/ipv6/firewall_rules",
            f"{EERO_API_BASE}/networks/{clean_net_id}/pinholes",
        ]
        last_status = 0
        async with self._client_session() as client:
            for endpoint in candidate_endpoints:
                try:
                    resp = await client.post(endpoint, headers=self._get_headers(), json=payload)
                    if resp.status_code in (200, 201, 204):
                        data = resp.json().get("data", payload) if resp.text else payload
                        return {"status": "success", "rule": data}
                    last_status = resp.status_code
                except Exception as sub_err:
                    logger.debug(f"Candidate endpoint {endpoint} error: {sub_err}")

            if last_status == 404:
                raise RuntimeError(
                    "eero Cloud API returned HTTP 404. IPv6 firewall rules (pinholes) are unavailable or disabled by eero on this network (e.g. Bridge Mode or IPv6 inactive)."
                )
            raise RuntimeError(f"Cloud API returned HTTP {last_status or 500}")

    async def delete_ipv6_firewall_rule(self, rule_id: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Elimina una regola dal firewall IPv6 (Issue #90)."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for IPv6 rules: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        if not clean_net_id:
            raise ValueError(tr("eero.no_network_selected"))
        if self.is_demo_mode:
            return self._delete_demo_ipv6_firewall_rule(rule_id)

        clean_rule_id = str(rule_id or "").strip().rstrip("/").split("/")[-1]
        candidate_endpoints = [
            f"{EERO_API_BASE}/networks/{clean_net_id}/firewall_rules/{clean_rule_id}",
            f"{EERO_API_BASE}/networks/{clean_net_id}/ipv6/firewall_rules/{clean_rule_id}",
            f"{EERO_API_BASE}/networks/{clean_net_id}/pinholes/{clean_rule_id}",
        ]
        last_status = 0
        async with self._client_session() as client:
            for endpoint in candidate_endpoints:
                try:
                    resp = await client.delete(endpoint, headers=self._get_headers())
                    if resp.status_code in (200, 202, 204):
                        return {"status": "success", "deleted_id": clean_rule_id}
                    last_status = resp.status_code
                except Exception as sub_err:
                    logger.debug(f"Candidate endpoint {endpoint} error: {sub_err}")

            if last_status in (200, 202, 204):
                return {"status": "success", "deleted_id": clean_rule_id}
            raise RuntimeError(f"Cloud API returned HTTP {last_status or 500}")


    async def get_guardian_vpn_status(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Restituisce lo stato di eero Plus Guardian VPN (/2.2/networks/{id}/guardian_vpn)."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for Guardian VPN: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        if self.is_demo_mode:
            return self._get_demo_guardian_vpn_status()
        if not clean_net_id:
            return {"status": "error", "supported": False, "enabled": False}
        try:
            async with self._client_session() as client:
                resp = await client.get(
                    f"{EERO_API_BASE}/networks/{clean_net_id}/guardian_vpn",
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {
                        "status": "success",
                        "supported": True,
                        "enabled": bool(data.get("enabled") or data.get("vpn_enabled")),
                        "provider": "Guardian (eero Plus)",
                        "details": data,
                    }
        except Exception as e:
            logger.debug(f"Guardian VPN status check fallback: {e}")
        return {
            "status": "success",
            "supported": False,
            "enabled": False,
            "provider": "Guardian (eero Plus)",
        }

    async def set_guardian_vpn_status(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Attiva o disattiva eero Plus Guardian VPN se supportato dall'account."""
        if not self.current_network_id and not settings.demo_mode:
            try:
                await self.fetch_account_info()
            except Exception as e:
                logger.debug(f"Account info fetch error for Guardian VPN toggle: {e}")

        raw_id = network_id or self.current_network_id
        clean_net_id = str(raw_id or "").strip().rstrip("/").split("/")[-1]
        if self.is_demo_mode:
            return self._set_demo_guardian_vpn_status(enabled)
        if not clean_net_id:
            raise ValueError(tr("eero.no_network_selected"))
        async with self._client_session() as client:
            resp = await client.put(
                f"{EERO_API_BASE}/networks/{clean_net_id}/guardian_vpn",
                headers=self._get_headers(),
                json={"enabled": bool(enabled)},
            )
            if resp.status_code in (200, 201, 204):
                return {"status": "success", "enabled": bool(enabled)}
            raise RuntimeError(f"Cloud API returned HTTP {resp.status_code}")

