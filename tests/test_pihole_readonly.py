import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.services.dns_manager import dns_manager

class TestPiholeReadonly(unittest.IsolatedAsyncioTestCase):
    @patch("httpx.AsyncClient.patch")
    @patch("httpx.AsyncClient.get")
    async def test_pihole_v6_test_detects_readonly(self, mock_get, mock_patch):
        # GET /api/config/dns/hosts succeeds with 200
        mock_get_resp = MagicMock(spec=httpx.Response)
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"config": {"dns": {"hosts": ["192.168.1.10 router.lan"]}}}
        mock_get.return_value = mock_get_resp

        # PATCH /api/config probe fails with 403 read-only
        mock_patch_resp = MagicMock(spec=httpx.Response)
        mock_patch_resp.status_code = 403
        mock_patch_resp.text = '{"error":{"key":"forbidden","message":"Unable to change configuration (read-only)","hint":"The current app session is not allowed to modify Pi-hole configuration."}}'
        mock_patch.return_value = mock_patch_resp

        res = await dns_manager._test_pihole("http://192.168.1.5", "app_token_123")
        self.assertFalse(res["success"])
        self.assertEqual(res["status_code"], 403)
        self.assertIn("read-only", res["message"].lower())

    @patch("httpx.AsyncClient.patch")
    @patch("httpx.AsyncClient.get")
    async def test_pihole_v6_test_succeeds_when_writable(self, mock_get, mock_patch):
        mock_get_resp = MagicMock(spec=httpx.Response)
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"config": {"dns": {"hosts": ["192.168.1.10 router.lan"]}}}
        mock_get.return_value = mock_get_resp

        # PATCH probe succeeds
        mock_patch_resp = MagicMock(spec=httpx.Response)
        mock_patch_resp.status_code = 200
        mock_patch_resp.text = '{}'
        mock_patch.return_value = mock_patch_resp

        res = await dns_manager._test_pihole("http://192.168.1.5", "admin_pass_123")
        self.assertTrue(res["success"])
        self.assertEqual(res["status_code"], 200)

    @patch("httpx.AsyncClient.patch")
    @patch("httpx.AsyncClient.get")
    async def test_pihole_v6_sync_handles_readonly(self, mock_get, mock_patch):
        # Initial probe
        mock_get_resp = MagicMock(spec=httpx.Response)
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"config": {"dns": {"hosts": []}}}
        mock_get.return_value = mock_get_resp

        # PATCH fails with 403 read-only
        mock_patch_resp = MagicMock(spec=httpx.Response)
        mock_patch_resp.status_code = 403
        mock_patch_resp.text = '{"error":{"key":"forbidden","message":"Unable to change configuration (read-only)"}}'
        mock_patch.return_value = mock_patch_resp

        inst = {
            "id": "inst-1",
            "url": "http://192.168.1.5",
            "engine": "pihole",
            "token": "app_token_123",
            "insecure_tls": False
        }
        clients = [{"ip": "192.168.1.50", "hostname": "my-pc"}]
        res = await dns_manager._sync_single_pihole(inst, clients)
        self.assertFalse(res["success"])
        self.assertEqual(res["failed"], 1)
        self.assertIn("read-only", res["message"].lower())

if __name__ == "__main__":
    unittest.main()
