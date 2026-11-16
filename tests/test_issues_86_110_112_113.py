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

        d4 = eero_client._normalize_device({
            "mac": "AA:BB:CC:00:11:04",
            "connected": True,
            "wireless": True,
            "ethernet_status": {"speed": "NONE", "has_carrier": False},
            "connectivity": {"signal": "−79 dBm"},
        })
        self.assertTrue(d4["wireless"])
        self.assertEqual(d4["signal_rssi"], -79)

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

                # Simulate corrupted SQLite file ("database disk image is malformed")
                Path(db_service.db_path).write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
                overview_after_corrupt = await db_service.get_signal_overview(
                    is_demo=0,
                    active_macs={"10:20:30:40:50:01", "10:20:30:40:50:02"},
                    live_devices=live_devs,
                )
                self.assertEqual(overview_after_corrupt["total_wireless_devices"], 2)
                self.assertEqual(overview_after_corrupt["weak_count"], 1)

                # Verify that auto-repair restored a working SQLite database
                inserted = await db_service.record_device_signal_samples(live_devs, is_demo=0)
                self.assertEqual(inserted, 2)
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

    def test_issue_129_bridge_mode_primary_node_normalization_and_election(self):
        """Issue #129: Bridge mode with multiple wired nodes must elect the node with is_primary_node as Gateway."""
        raw_nodes = [
            {
                "url": "/2.2/eeros/101",
                "id": "101",
                "location": "Garage",
                "gateway": False,
                "is_primary_node": False,
                "ethernet_ports": [{"port": 1, "isWanPort": True, "speed": "1000 Mbps"}],
            },
            {
                "url": "/2.2/eeros/102",
                "id": "102",
                "location": "Garden",
                "gateway": False,
                "is_primary_node": False,
                "ethernet_ports": [{"port": 1, "isWanPort": True, "speed": "1000 Mbps"}],
            },
            {
                "url": "/2.2/eeros/103",
                "id": "103",
                "location": "Living (Pro 7)",
                "gateway": False,
                "isPrimaryNode": True,  # camelCase variant
                "ethernet_ports": [{"port": 1, "isWanPort": True, "speed": "2500 Mbps"}],
            },
        ]

        normalized = [eero_client._normalize_eero_node(n) for n in raw_nodes]
        self.assertTrue(normalized[2]["is_primary_node"])
        self.assertTrue(normalized[2]["is_gateway"])
        self.assertFalse(normalized[0]["is_primary_node"])
        self.assertFalse(normalized[1]["is_primary_node"])

    def test_issue_96_echo_builtin_extender_reconciliation(self):
        """Issue #96: Reconcile Echo Built-in virtual nodes from connected devices, proxied flags, and persistence."""
        base_eeros = [
            {"id": "gw_1", "name": "Studio (Gateway)", "is_gateway": True, "wired": True, "status": "online"}
        ]
        devices = [
            {
                "id": "client_phone",
                "hostname": "John Phone",
                "connected": True,
                "connected_eero_name": "Bedroom Echo Spot",
                "connected_to_proxied_node": True,
            },
            {
                "id": "echo_harmony",
                "hostname": "Harmony Echo Dot",
                "model": "Echo Dot (5th Gen)",
                "manufacturer": "Amazon Technologies Inc.",
                "mac": "aa:bb:cc:dd:ee:ff",
                "ip": "192.168.4.88",
                "connected": False,  # eero cloud reports connected: False on the station record
            },
            {
                "id": "echo_miami",
                "hostname": "Miami Echo",
                "model": "Echo",
                "manufacturer": "Amazon",
                "mac": "aa:bb:cc:dd:ee:11",
                "ip": "192.168.4.89",
                "connected": False,
                "connected_eero_name": "Studio (Gateway)",
            }
        ]

        known_specs = {}
        result = BackgroundPoller.reconcile_echo_extender_nodes(base_eeros, devices, known_specs=known_specs)
        result_names = [n["name"] for n in result]

        self.assertIn("Bedroom Echo Spot", result_names)
        self.assertIn("Harmony Echo Dot", result_names)
        self.assertIn("Miami Echo", result_names)

        echo_node = next(n for n in result if n["name"] == "Bedroom Echo Spot")
        self.assertTrue(echo_node["is_echo_node"])
        self.assertEqual(echo_node["backhaul_type"], "eero Built-in (Wi-Fi)")
        self.assertEqual(echo_node["status"], "online")

        # Miami and Harmony are online because they are active on LAN with assigned IP
        harmony_node = next(n for n in result if n["name"] == "Harmony Echo Dot")
        self.assertEqual(harmony_node["status"], "online")
        miami_node = next(n for n in result if n["name"] == "Miami Echo")
        self.assertEqual(miami_node["status"], "online")

        # Test persistence: on the next poll, even if client_phone disconnects, Bedroom Echo Spot persists
        devices_next = [
            {
                "id": "echo_harmony",
                "hostname": "Harmony Echo Dot",
                "model": "Echo Dot",
                "ip": "192.168.4.88",
            }
        ]
        result_next = BackgroundPoller.reconcile_echo_extender_nodes(base_eeros, devices_next, known_specs=known_specs)
        next_names = [n["name"] for n in result_next]
        self.assertIn("Bedroom Echo Spot", next_names)

    async def test_issue_128_mqtt_gone_away_device_purge(self):
        """Issue #128: Devices that disappear from eero cloud are purged from Home Assistant MQTT after 2 cycles."""
        from app.services.mqtt_client import MQTTService

        service = MQTTService()
        service._discovery_enabled = True
        service._published_tracker_configs = {
            "aabbccddeeff": "My Laptop",
            "112233445566": "Old Gone Away Device",
        }
        service._tracker_last_state = {
            "aabbccddeeff": "home",
            "112233445566": "not_home",
        }

        published_messages = []
        async def mock_publish(client, topic, payload, retain=False):
            published_messages.append((topic, payload, retain))

        service._publish_message = mock_publish

        telemetry_cycle_1 = {
            "devices": [
                {"mac": "aa:bb:cc:dd:ee:ff", "hostname": "My Laptop", "connected": True}
                # "112233445566" is missing from eero cloud
            ],
            "eeros": [],
            "health_score": 95,
        }

        # Cycle 1: Device is missing for the first time -> marked not_home
        await service.publish_telemetry(None, telemetry_cycle_1)
        self.assertEqual(service._stale_device_counter.get("112233445566"), 1)
        self.assertIn("112233445566", service._published_tracker_configs)

        # Cycle 2: Device is missing for the second consecutive time -> purged from Home Assistant!
        await service.publish_telemetry(None, telemetry_cycle_1)
        self.assertNotIn("112233445566", service._published_tracker_configs)
        self.assertNotIn("112233445566", service._tracker_last_state)
        self.assertNotIn("112233445566", service._stale_device_counter)

        # Check that empty payload with retain=True was sent to discovery config topic
        purge_topic = f"{service._ha_prefix}/device_tracker/{service._base_topic}_112233445566/config"
        purge_msg = next((msg for msg in published_messages if msg[0] == purge_topic and msg[1] == "" and msg[2] is True), None)
        self.assertIsNotNone(purge_msg, "Expected empty retained MQTT message on discovery config topic to purge entity")


if __name__ == "__main__":
    unittest.main()
