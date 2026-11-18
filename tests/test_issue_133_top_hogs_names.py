import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, AsyncMock
from app.services.db import DBService
from app.routers.network import get_top_bandwidth_hogs
from app.services.poller import background_poller

class TestIssue133TopHogsNames(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_hogs.db")
        self.test_db = DBService(db_path=self.db_path)
        await self.test_db.init_db()

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_db_get_top_bandwidth_hogs_enriches_with_device_metadata(self):
        # 1. Insert device usage history with raw MAC as hostname
        mac = "b2:88:eb:11:22:33"
        await self.test_db.record_device_usage_samples(
            samples=[{
                "mac": mac,
                "hostname": mac,
                "rx_bytes": 1000000.0,
                "tx_bytes": 500000.0,
                "download_rate_mbps": 10.0,
                "upload_rate_mbps": 5.0,
            }],
            network_id="net_test_1"
        )

        # 2. Add custom name in device_metadata
        await self.test_db.upsert_device_metadata(
            mac_address=mac,
            custom_name="iPhone di Enrico",
            category="Smartphone"
        )

        # 3. Call get_top_bandwidth_hogs on DB
        hogs = await self.test_db.get_top_bandwidth_hogs(network_id="net_test_1", limit=5, period="daily")
        self.assertEqual(len(hogs), 1)
        self.assertEqual(hogs[0]["mac"], mac)
        self.assertEqual(hogs[0]["hostname"], "iPhone di Enrico")
        self.assertEqual(hogs[0]["nickname"], "iPhone di Enrico")
        self.assertEqual(hogs[0]["display_name"], "iPhone di Enrico")
        self.assertEqual(hogs[0]["category"], "Smartphone")

    async def test_db_get_top_bandwidth_hogs_supports_hours_kwarg(self):
        # Verify hours argument works without raising TypeError
        hogs = await self.test_db.get_top_bandwidth_hogs(hours=48, limit=5)
        self.assertIsInstance(hogs, list)

    @patch("app.routers.network.eero_client")
    @patch("app.routers.network.db_service")
    async def test_router_get_top_bandwidth_hogs_enriches_from_cache(self, mock_db_service, mock_eero_client):
        mock_eero_client.current_network_id = "net_test_1"
        mock_eero_client.is_demo_mode = False

        mac = "b2:88:eb:44:55:66"
        # Database returned raw MAC as hostname
        mock_db_service.get_top_bandwidth_hogs = AsyncMock(return_value=[{
            "mac": mac,
            "hostname": mac,
            "rx_bytes": 5000000,
            "tx_bytes": 2000000,
            "total_bytes": 7000000,
            "avg_down_mbps": 12.5,
            "avg_up_mbps": 3.2,
        }])
        mock_db_service.get_all_device_metadata = AsyncMock(return_value={})

        # Cached devices in background poller has live nickname
        cached_devices = [{
            "mac": mac,
            "nickname": "iPad di Jon",
            "hostname": "Jon-iPad",
            "category": "Tablet",
            "custom_icon": "tablet",
            "ip": "192.168.1.150"
        }]

        with patch.object(background_poller, "cached_devices", cached_devices):
            res = await get_top_bandwidth_hogs(limit=5, period="daily")
            self.assertEqual(res["status"], "success")
            self.assertEqual(len(res["top_hogs"]), 1)
            hog = res["top_hogs"][0]
            self.assertEqual(hog["nickname"], "iPad di Jon")
            self.assertEqual(hog["hostname"], "iPad di Jon")
            self.assertEqual(hog["display_name"], "iPad di Jon")
            self.assertEqual(hog["category"], "Tablet")
            self.assertEqual(hog["custom_icon"], "tablet")

if __name__ == "__main__":
    unittest.main()
