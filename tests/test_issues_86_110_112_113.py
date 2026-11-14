import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.eero_client import eero_client
from app.services.db import db_service
from app.services.poller import BackgroundPoller
from app.services.notifications import notification_service


class TestIssues86_110_112_113(unittest.IsolatedAsyncioTestCase):
    def test_issue_110_normalize_device_parses_string_and_dict_rssi(self):
        """Issue #110: _normalize_device must normalize string/float/dict/signal_avg RSSI to int dBm."""
        d1 = eero_client._normalize_device({
            "mac": "AA:BB:CC:00:11:01",
            "connected": True,
            "wireless": True,
            "rssi": "-78 dBm",
        })
        self.assertEqual(d1["signal_rssi"], -78)

        d2 = eero_client._normalize_device({
            "mac": "AA:BB:CC:00:11:02",
            "connected": True,
            "wireless": True,
            "connectivity": {"signal": {"rx_rssi": "-81 dBm", "score": 2}},
        })
        self.assertEqual(d2["signal_rssi"], -81)

        d3 = eero_client._normalize_device({
            "mac": "AA:BB:CC:00:11:03",
            "connected": True,
            "wireless": True,
            "connectivity": {"signal_avg": "-76.4 dBm"},
        })
        self.assertEqual(d3["signal_rssi"], -76)

    async def test_issue_110_signal_overview_merges_live_cached_devices(self):
        """Issue #110: get_signal_overview must include live wireless devices (< -75 dBm) even if DB history is empty."""
        orig_db_path = db_service.db_path
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                db_service.db_path = Path(tmpdir) / "test_sig_110.db"
                await db_service.init_db()

                live_devs = [
                    {
                        "mac": "10:20:30:40:50:01",
                        "custom_name": "Garage Camera",
                        "hostname": "cam-garage",
                        "connected": True,
                        "wireless": True,
                        "signal_rssi": "-79 dBm",
                        "frequency_band": "2.4 GHz",
                        "channel": 6,
                        "connected_eero_name": "Living Room",
                    },
                    {
                        "mac": "10:20:30:40:50:02",
                        "custom_name": "MacBook Pro",
                        "hostname": "mbp",
                        "connected": True,
                        "wireless": True,
                        "signal_rssi": -52,
                        "frequency_band": "6 GHz",
                        "channel": 37,
                        "connected_eero_name": "Office",
                    },
                ]
                overview = await db_service.get_signal_overview(
                    is_demo=0,
                    active_macs={"10:20:30:40:50:01", "10:20:30:40:50:02"},
                    live_devices=live_devs,
                )
                self.assertEqual(overview["total_wireless_devices"], 2)
                self.assertEqual(overview["weak_count"], 1)
                self.assertEqual(len(overview["weak_devices"]), 1)
                self.assertEqual(overview["weak_devices"][0]["hostname"], "Garage Camera")
                self.assertEqual(overview["weak_devices"][0]["signal_rssi"], -79)
            finally:
                db_service.db_path = orig_db_path

    async def test_issue_112_fresh_install_no_alert_burst_after_unauthenticated_demo_poll(self):
        """Issue #112: A pre-login Demo poll must not flip initial discovery and trigger alerts on first real login."""
        orig_db_path = db_service.db_path
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                db_service.db_path = Path(tmpdir) / "test_issue_112.db"
                await db_service.init_db()

                poller = BackgroundPoller()
                notify_mock = AsyncMock()

                demo_net = {"id": "network_demo_mesh_01", "name": "Demo Mesh"}
                demo_devs = [
                    {
                        "id": "dev_demo_1",
                        "mac": "00:1a:2b:3c:4d:01",
                        "hostname": "Demo Phone",
                        "connected": True,
                        "wireless": True,
                    }
                ]

                real_net = {"id": "net_real_999", "name": "Home Mesh"}
                real_devs_initial = [
                    {
                        "id": "real_1",
                        "mac": "a1:b2:c3:d4:e5:01",
                        "hostname": "Real iPhone",
                        "connected": True,
                        "wireless": True,
                        "signal_rssi": -60,
                    },
                    {
                        "id": "real_2",
                        "mac": "a1:b2:c3:d4:e5:02",
                        "hostname": "Real TV",
                        "connected": True,
                        "wireless": True,
                        "signal_rssi": -78,
                    },
                ]

                with patch.object(notification_service, "notify_new_device", notify_mock), \
                     patch.object(eero_client, "get_eeros", AsyncMock(return_value=[])), \
                     patch.object(eero_client, "get_profiles", AsyncMock(return_value=[])), \
                     patch.object(eero_client, "get_forwards_and_reservations", AsyncMock(return_value={"reservations": []})):

                    # Step 1: Container boots unauthenticated -> poller gets Demo dataset
                    with patch.object(eero_client, "get_network_details", AsyncMock(return_value=demo_net)), \
                         patch.object(eero_client, "get_devices", AsyncMock(return_value=demo_devs)):
                        await poller._poll_and_cache()

                    self.assertEqual(notify_mock.call_count, 0)
                    self.assertEqual(len(poller._known_macs), 0)

                    # Step 2: User completes first login -> poller gets real devices for the first time
                    with patch.object(eero_client, "get_network_details", AsyncMock(return_value=real_net)), \
                         patch.object(eero_client, "get_devices", AsyncMock(return_value=real_devs_initial)):
                        await poller._poll_and_cache()

                    # Zero alerts must be sent for existing devices on first login!
                    self.assertEqual(notify_mock.call_count, 0)
                    self.assertEqual(poller._known_macs, {"a1:b2:c3:d4:e5:01", "a1:b2:c3:d4:e5:02"})
                    self.assertTrue(all(not d.get("is_new") for d in poller.cached_devices))

                    # Step 3: A genuinely new device joins on the next poll -> exactly 1 alert
                    real_devs_next = real_devs_initial + [
                        {
                            "id": "real_3",
                            "mac": "a1:b2:c3:d4:e5:03",
                            "hostname": "New Guest iPad",
                            "connected": True,
                            "wireless": True,
                            "signal_rssi": -55,
                        }
                    ]
                    with patch.object(eero_client, "get_network_details", AsyncMock(return_value=real_net)), \
                         patch.object(eero_client, "get_devices", AsyncMock(return_value=real_devs_next)):
                        await poller._poll_and_cache()

                    self.assertEqual(notify_mock.call_count, 1)
                    alerted_dev = notify_mock.call_args[0][0]
                    self.assertEqual(alerted_dev["mac"], "a1:b2:c3:d4:e5:03")
            finally:
                db_service.db_path = orig_db_path

    def test_issues_86_and_113_template_bindings(self):
        """Issue #86 & #113: index.html must include color-scheme meta and :selected bindings on x-for <select> options."""
        html = Path("app/templates/index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="color-scheme" content="light dark">', html)
        self.assertIn(':selected="(h - 1) === Number(digestSettings.hour)"', html)
        self.assertIn(':selected="d.mac_address === selectedSignalDeviceMac"', html)


if __name__ == "__main__":
    unittest.main()
