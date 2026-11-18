import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.services.dns_manager import dns_manager

class TestIssue134PiholeUnmanaged(unittest.IsolatedAsyncioTestCase):
    @patch("httpx.AsyncClient.patch")
    @patch("httpx.AsyncClient.get")
    async def test_pihole_v6_sync_preserves_unmanaged_custom_records_on_same_ip(self, mock_get, mock_patch):
        # Pi-hole v6 returns existing hosts including unmanaged aliases pointing to 192.168.1.100
        mock_get_resp = MagicMock(spec=httpx.Response)
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "config": {
                "dns": {
                    "hosts": [
                        "192.168.1.100 eero-server.lan",
                        "192.168.1.100 plex.home",
                        "192.168.1.100 vault.home",
                        "192.168.1.50 old-ip-device.lan"
                    ]
                }
            }
        }
        mock_get.return_value = mock_get_resp

        mock_patch_resp = MagicMock(spec=httpx.Response)
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = "{}"
        mock_patch.return_value = mock_patch_resp

        inst = {
            "id": "inst-pihole-v6",
            "url": "http://192.168.1.5",
            "engine": "pihole",
            "token": "token123",
            "zone": "lan",
            "prune_stale_ips": True,
            "insecure_tls": False
        }
        clients = [
            {"ip": "192.168.1.100", "hostname": "eero-server"},
            {"ip": "192.168.1.51", "hostname": "old-ip-device"}  # IP changed from .50 to .51
        ]

        res = await dns_manager._sync_single_pihole(inst, clients)
        self.assertTrue(res["success"])
        self.assertEqual(res["added"], 2)

        # Inspect PATCH payload sent to /api/config
        self.assertTrue(mock_patch.called)
        call_kwargs = mock_patch.call_args[1]
        sent_hosts = call_kwargs["json"]["config"]["dns"]["hosts"]

        # 1. Custom unmanaged records on 192.168.1.100 MUST be preserved
        self.assertIn("192.168.1.100 plex.home", sent_hosts)
        self.assertIn("192.168.1.100 vault.home", sent_hosts)

        # 2. Managed records must be present with current IPs
        self.assertIn("192.168.1.100 eero-server.lan", sent_hosts)
        self.assertIn("192.168.1.51 old-ip-device.lan", sent_hosts)

        # 3. Old stale IP for managed device must be pruned
        self.assertNotIn("192.168.1.50 old-ip-device.lan", sent_hosts)

    @patch("httpx.AsyncClient.get")
    async def test_pihole_v5_sync_does_not_delete_custom_records_on_same_ip(self, mock_get):
        # Simulate Pi-hole v5
        deleted_urls = []

        async def fake_get(url, *args, **kwargs):
            url_str = str(url)
            resp = MagicMock(spec=httpx.Response)
            if "/api/config/dns/hosts" in url_str:
                # Return 404 to trigger fallback to v5
                resp.status_code = 404
                return resp
            elif "action=get" in url_str:
                resp.status_code = 200
                resp.json.return_value = {
                    "data": [
                        ["192.168.1.100", "plex.home"],
                        ["192.168.1.100", "vault.home"],
                        ["192.168.1.50", "managed-pc.lan"]
                    ]
                }
                return resp
            elif "action=delete" in url_str:
                deleted_urls.append(url_str)
                resp.status_code = 200
                return resp
            elif "action=add" in url_str:
                resp.status_code = 200
                return resp
            resp.status_code = 200
            return resp

        mock_get.side_effect = fake_get

        inst = {
            "id": "inst-pihole-v5",
            "url": "http://192.168.1.5",
            "engine": "pihole",
            "token": "token123",
            "zone": "lan",
            "prune_stale_ips": True,
            "insecure_tls": False
        }
        clients = [
            {"ip": "192.168.1.100", "hostname": "eero-server"},
            {"ip": "192.168.1.51", "hostname": "managed-pc"}  # IP changed from .50 to .51
        ]

        res = await dns_manager._sync_single_pihole(inst, clients)
        self.assertTrue(res["success"])

        # Check delete calls: only managed-pc.lan with old IP .50 should be deleted
        self.assertTrue(any("domain=managed-pc.lan" in u and "ip=192.168.1.50" in u for u in deleted_urls))

        # plex.home and vault.home must NEVER be deleted
        self.assertFalse(any("domain=plex.home" in u for u in deleted_urls))
        self.assertFalse(any("domain=vault.home" in u for u in deleted_urls))

if __name__ == "__main__":
    unittest.main()
