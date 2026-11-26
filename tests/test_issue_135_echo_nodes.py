"""
Unit test for Issue #135: Eero Node Network - Amazon Echos
Verifies that:
1. Only Echo devices explicitly enabled as eero Built-in (via proxied_nodes, is_proxied_node, or active client connection)
   are promoted to virtual mesh extender nodes.
2. Regular Echo smart speakers on the LAN (not enabled as Built-in nodes) remain normal client devices and are NOT added to the mesh.
3. Enabled Echo Built-in nodes are matched against LAN client devices using multi-criteria lookup (MAC, ID, exact/clean/token name),
   accurately inheriting their real LAN IP and maintaining Online status (green indicator), even when eero cloud reports
   connected: False on the Echo station record or when 0 clients are currently connected.
4. Extenders reporting enabled: False (or standby) in proxied_nodes are not dropped.
5. Normalizer and poller alignment mark Echo extender stations as connected=True in enriched_devices.
"""
import unittest
from app.services.poller import BackgroundPoller
from app.services.eero_client import EeroClient


class TestIssue135EchoNodes(unittest.TestCase):
    def test_issue_135_selective_echo_mesh_nodes_and_online_status(self):
        # 1. 3 nodi fisici eero Pro 7 (come nello screenshot di markharrison)
        base_eeros = [
            {"id": "gw_studio", "name": "Studio", "is_gateway": True, "ip": "192.168.4.1", "status": "online", "model": "eero Pro 7"},
            {"id": "node_ironworks", "name": "Ironworks", "is_gateway": False, "ip": "192.168.4.15", "status": "online", "model": "eero Pro 7"},
            {"id": "node_office", "name": "Office", "is_gateway": False, "ip": "192.168.4.21", "status": "online", "model": "eero Pro 7"},
        ]

        # 2. Solo 3 Echo abilitati come eero Built-in nel cloud eero:
        # - Oasis Echo Spot: 1 client connesso
        # - Miami Echo: 0 client connessi, connected: False
        # - Harmony Echo Dot: enabled: False (standby / low-power), connected: False
        network_details = {
            "proxied_nodes": [
                {
                    "name": "Oasis Echo Spot",
                    "id": "echo_oasis_id",
                    "mac": "11:22:33:44:55:01",
                    "status": "active",
                    "connected": False,
                },
                {
                    "name": "Miami Echo",
                    "id": "echo_miami_id",
                    "mac": "11:22:33:44:55:02",
                    "status": "ready",
                    "connected": False,
                },
                {
                    "name": "Harmony Echo Dot",
                    "id": "echo_harmony_id",
                    "mac": "11:22:33:44:55:03",
                    "status": "online",
                    "enabled": False,  # Standby / low-power in cloud API
                    "connected": False,
                },
            ]
        }

        # 3. Dispositivi sulla LAN:
        # - 3 Echo Built-in (con telemetria Wi-Fi verso i nodi fisici, anche se connected: False dal cloud)
        # - 3 normali smart speaker Alexa NON abilitati come nodi eero (Office Echo, Spectre Echo, Echo 4th Gen)
        # - 1 client connesso a Oasis Echo Spot
        devices = [
            # Client connesso a Oasis
            {
                "id": "client_phone",
                "mac": "99:88:77:66:55:44",
                "hostname": "Mark iPhone",
                "ip": "192.168.4.99",
                "connected": True,
                "connected_eero_name": "Oasis Echo Spot",
                "connected_eero_id": "echo_oasis_id",
            },
            # Echo 1 (abilitato): Oasis - notare il nome parziale nel DHCP/nickname ("Oasis")
            {
                "id": "dev_oasis",
                "mac": "11:22:33:44:55:01",
                "hostname": "Oasis",
                "ip": "192.168.4.50",
                "connected": True,
                "model": "Echo Spot",
                "manufacturer": "Amazon Technologies Inc.",
                "signal_rssi": -55,
                "connected_eero_name": "Studio",
            },
            # Echo 2 (abilitato): Miami - 0 client connessi, connected: False da API eero
            {
                "id": "dev_miami",
                "mac": "11:22:33:44:55:02",
                "hostname": "Miami Echo",
                "ip": "192.168.4.51",
                "connected": False,  # Simula payload eero con connected: False
                "model": "Echo",
                "manufacturer": "Amazon",
                "signal_rssi": -65,
                "connected_eero_name": "Ironworks",
                "channel": 36,
            },
            # Echo 3 (abilitato): Harmony - enabled: False in proxied_nodes, connected: False in devices, IP assente
            {
                "id": "dev_harmony",
                "mac": "11:22:33:44:55:03",
                "hostname": "Harmony Echo Dot",
                "ip": None,
                "connected": False,
                "model": "Echo Dot (5th Gen)",
                "manufacturer": "Amazon Technologies Inc.",
                "signal_rssi": -73,
                "connected_eero_name": "Ironworks",
                "channel": 40,
                "wireless": True,
            },
            # Echo 4 (NON abilitato): Spectre Echo
            {
                "id": "dev_spectre",
                "mac": "aa:bb:cc:dd:ee:04",
                "hostname": "Spectre Echo",
                "ip": "192.168.4.63",
                "connected": True,
                "model": "Echo",
                "manufacturer": "Amazon",
            },
            # Echo 5 (NON abilitato): Office Echo
            {
                "id": "dev_office_echo",
                "mac": "aa:bb:cc:dd:ee:05",
                "hostname": "Office Echo",
                "ip": "192.168.4.40",
                "connected": True,
                "model": "Echo",
                "manufacturer": "Amazon",
            },
            # Echo 6 (NON abilitato): Echo (4th Gen) 2
            {
                "id": "dev_echo4",
                "mac": "aa:bb:cc:dd:ee:06",
                "hostname": "Echo (4th Gen) 2",
                "ip": "192.168.4.67",
                "connected": True,
                "model": "Echo (4th Gen)",
                "manufacturer": "Amazon",
            },
        ]

        known_specs = {}
        result = BackgroundPoller.reconcile_echo_extender_nodes(
            base_eeros, devices, network_details=network_details, known_specs=known_specs
        )

        result_names = [n["name"] for n in result]

        # Verifica 1: DEVONO esserci ESATTAMENTE 6 nodi (3 fisici + 3 Built-in)
        self.assertEqual(len(result), 6, f"Expected 6 nodes, got {len(result)}: {result_names}")

        # Verifica 2: I 3 Echo abilitati DEVONO essere presenti
        self.assertIn("Oasis Echo Spot", result_names)
        self.assertIn("Miami Echo", result_names)
        self.assertIn("Harmony Echo Dot", result_names)

        # Verifica 3: Gli Echo NON abilitati NON devono comparire tra i nodi mesh
        self.assertNotIn("Spectre Echo", result_names)
        self.assertNotIn("Office Echo", result_names)
        self.assertNotIn("Echo (4th Gen) 2", result_names)

        # Verifica 4: Tutti e 3 i nodi Built-in DEVONO essere ONLINE (green indicator)
        oasis_node = next(n for n in result if n["name"] == "Oasis Echo Spot")
        self.assertEqual(oasis_node["status"], "online")
        self.assertEqual(oasis_node["ip"], "192.168.4.50")
        self.assertEqual(oasis_node["mac_address"], "11:22:33:44:55:01")
        self.assertEqual(oasis_node["connected_clients_count"], 1)

        miami_node = next(n for n in result if n["name"] == "Miami Echo")
        self.assertEqual(miami_node["status"], "online")
        self.assertEqual(miami_node["ip"], "192.168.4.51")
        self.assertEqual(miami_node["connected_clients_count"], 0)

        harmony_node = next(n for n in result if n["name"] == "Harmony Echo Dot")
        self.assertEqual(harmony_node["status"], "online")
        self.assertEqual(harmony_node["mac_address"], "11:22:33:44:55:03")

    def test_device_normalizer_echo_wifi_connected_fallback(self):
        """Verifica che _normalize_device imposti connected=True per Echo con telemetria Wi-Fi attiva."""
        raw_dev = {
            "id": "dev_echo_test",
            "nickname": "Harmony Echo Dot",
            "mac": "40:d7:2e:01:02:03",
            "model": "Echo Dot (5th Gen)",
            "connected": False,  # eero cloud invia False
            "status": "disconnected",
            "connectivity": {
                "signal": "-73 dBm",
                "rx_bitrate": "6 Mbps",
                "tx_bitrate": "6 Mbps",
                "frequency": "5 GHz",
                "channel": 40,
            },
            "source": {
                "location": "Ironworks",
            },
        }
        client = EeroClient()
        norm = client._normalize_device(raw_dev)
        self.assertTrue(norm["connected"], "Echo device with live Wi-Fi signal and source node should be marked connected")
        self.assertEqual(norm["connected_eero_name"], "Ironworks")
        self.assertEqual(norm["signal_rssi"], -73)

    def test_echo_builtin_user_configured_metadata_with_zero_clients(self):
        """Verifica che un Echo marcato is_echo_builtin compaia come nodo mesh anche senza proxied_nodes e con 0 client."""
        base_eeros = [
            {"id": "eero_01", "name": "Studio", "is_gateway": True, "status": "online"},
            {"id": "eero_02", "name": "Ironworks", "is_gateway": False, "status": "online"},
        ]
        devices = [
            {
                "id": "dev_echo_harmony",
                "hostname": "Harmony Echo Dot",
                "mac": "fc:e9:d8:e6:71:ac",
                "ip": "192.168.4.52",
                "model": "Echo Dot (5th Gen)",
                "connected": True,
                "connected_eero_name": "Studio",
                "is_echo_builtin": True,  # Abilitato manualmente o persistito
            },
            {
                "id": "dev_echo_speaker",
                "hostname": "Normal Living Room Echo",
                "mac": "11:22:33:44:55:99",
                "ip": "192.168.4.99",
                "model": "Echo (4th Gen)",
                "connected": True,
                "connected_eero_name": "Studio",
                "is_echo_builtin": False,  # Non abilitato
            }
        ]
        # Nessun proxied_nodes nei dettagli di rete, 0 client connessi ad Harmony Echo Dot
        result = BackgroundPoller.reconcile_echo_extender_nodes(
            base_eeros, devices, network_details={}, known_specs={}
        )
        result_names = [n["name"] for n in result]

        self.assertIn("Harmony Echo Dot", result_names, "Harmony Echo Dot con is_echo_builtin deve comparire tra i nodi")
        self.assertNotIn("Normal Living Room Echo", result_names, "Echo non abilitato non deve comparire tra i nodi")

        harmony_node = next(n for n in result if n["name"] == "Harmony Echo Dot")
        self.assertEqual(harmony_node["status"], "online")
        self.assertEqual(harmony_node["connected_clients_count"], 0)
        self.assertEqual(harmony_node["ip"], "192.168.4.52")
        self.assertEqual(harmony_node["mac_address"], "fc:e9:d8:e6:71:ac")
        self.assertTrue(harmony_node["is_echo_node"])



class TestIssue135FrontendMethodCalls(unittest.TestCase):
    """Saving device details with the eero Built-in toggle showed
    "Save Error: this.fetchMeshNodes is not a function": the save handler
    called a method that was never defined. Guard the whole component,
    which on 1.8.0 is app.js plus the modules merged into it."""

    def test_every_this_method_call_is_defined(self):
        import re
        from pathlib import Path

        files = [Path("app/static/js/app.js")] + sorted(Path("app/static/js/modules").glob("*.js"))
        js = "".join(f.read_text(encoding="utf-8") for f in files)
        defined = set(re.findall(r"^\s*(?:async\s+)?(?:get\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", js, re.M))
        defined |= set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*:", js, re.M))
        called = set(re.findall(r"this\.([A-Za-z_$][\w$]*)\s*\(", js))
        alpine_magics = {"$nextTick", "$watch", "$dispatch"}
        self.assertEqual(sorted(called - defined - alpine_magics), [])


if __name__ == "__main__":
    unittest.main()
