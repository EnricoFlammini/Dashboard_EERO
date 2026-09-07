import logging
from typing import Any, Dict, List, Optional

from app.services.dns_manager import dns_manager, normalize_dns_url

logger = logging.getLogger(__name__)


def normalize_adguard_url(url: str) -> str:
    """Funzione helper retrocompatibile per normalizzare l'URL."""
    return normalize_dns_url(url)


class AdGuardService:
    """
    Wrapper di retrocompatibilità verso DNSManager per AdGuard Home.
    Mantiene identica l'interfaccia pubblica per non rompere test esistenti
    o integrazioni esterne, inoltrando le operazioni al DNSManager unificato.
    """

    def __init__(self):
        self._demo_settings = dns_manager._demo_settings

    async def get_settings(self) -> Dict[str, Any]:
        """Restituisce la configurazione AdGuard."""
        all_dns = await dns_manager.get_settings()
        instances = all_dns.get("instances", [])
        first_adguard = next((i for i in instances if i.get("engine") == "adguard"), None)
        if not first_adguard and instances:
            first_adguard = instances[0]

        return {
            "enabled": all_dns.get("enabled", False) and (first_adguard.get("enabled", True) if first_adguard else True),
            "url": first_adguard.get("url", "") if first_adguard else "",
            "username": first_adguard.get("username", "") if first_adguard else "",
            "has_password": first_adguard.get("has_password", False) if first_adguard else False,
            "last_sync_time": first_adguard.get("last_sync_time", "") if first_adguard else "",
            "last_sync_count": first_adguard.get("last_sync_count", 0) if first_adguard else 0,
            "last_sync_status": first_adguard.get("last_sync_status", "") if first_adguard else "",
            "instances": instances
        }

    async def save_settings(
        self,
        enabled: bool,
        instances: Optional[List[Dict[str, Any]]] = None,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """Salva le impostazioni AdGuard."""
        if instances is not None and len(instances) > 0:
            formatted_instances = []
            for inst in instances:
                i_copy = dict(inst)
                if "engine" not in i_copy:
                    i_copy["engine"] = "adguard"
                formatted_instances.append(i_copy)
            await dns_manager.save_settings(enabled=enabled, instances=formatted_instances)
        else:
            # Compatibilità singola istanza
            inst_list = [{
                "id": "inst-adguard-1",
                "name": "AdGuard Home",
                "engine": "adguard",
                "url": url or "",
                "username": username or "",
                "password": password or "",
                "enabled": True
            }]
            await dns_manager.save_settings(enabled=enabled, instances=inst_list)

    def _merge_adguard_client_data(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """Inoltra il merge delle regole client a dns_manager."""
        return dns_manager._merge_adguard_client_data(existing, incoming)

    def _prepare_clients(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Inoltra la preparazione dei client a dns_manager."""
        return dns_manager._prepare_clients_payload(devices)

    async def test_single_instance(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Testa una singola istanza AdGuard Home."""
        inst_payload = {
            "engine": "adguard",
            "url": url,
            "username": username or "",
            "password": password or ""
        }
        return await dns_manager.test_instance(inst_payload)

    async def test_connection(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        instances: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Testa la connessione verso AdGuard."""
        if instances and len(instances) > 0:
            return await dns_manager.test_all_instances()
        cur = await self.get_settings()
        target_url = url or cur.get("url", "")
        target_user = username if username is not None else cur.get("username", "")
        target_pass = password
        return await self.test_single_instance(target_url, target_user, target_pass)

    async def sync_devices(
        self,
        devices: List[Dict[str, Any]],
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        instances: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Sincronizza i dispositivi verso AdGuard."""
        return await dns_manager.sync_devices(devices)

    async def auto_sync_if_enabled(self, devices: List[Dict[str, Any]]) -> None:
        """Inoltra il sync automatico a dns_manager."""
        await dns_manager.auto_sync_if_enabled(devices)


# Istanza singleton esportata per retrocompatibilità
adguard_service = AdGuardService()
