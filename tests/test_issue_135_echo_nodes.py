"""
Unit test for Issue #135: Eero Node Network - Amazon Echos
Verifies that:
1. Only Echo devices explicitly enabled as eero Built-in (via proxied_nodes, is_proxied_node, or active client connection)
   are promoted to virtual mesh extender nodes.
2. Regular Echo smart speakers on the LAN (not enabled as Built-in nodes) remain normal client devices and are NOT added to the mesh.
3. Enabled Echo Built-in nodes are matched against LAN client devices using multi-criteria lookup (MAC, ID, exact/clean/token name),
   accurately inheriting their real LAN IP and maintaining Online status (green indicator).
"""
import unittest
from app.services.poller import BackgroundPoller


class TestIssue135EchoNodes(unittest.TestCase):
    def test_issue_135_selective_echo_mesh_nodes_and_online_status(self):
        # 1. 3 nodi fisici eero Pro 7 (come nello screenshot di markharrison)
        base_eeros = [
            {"id": "gw_studio", "name": "Studio", "is_gateway": True, "ip": "192.168.4.1", "status": "online", "model": "eero Pro 7"},
            {"id": "node_ironworks", "name": "Ironworks", "is_gateway": False, "ip": "192.168.4.15", "status": "online", "model": "eero Pro 7"},
            {"id": "node_office", "name": "Office", "is_gateway": False, "ip": "192.168.4.21", "status": "online", "model": "eero Pro 7"},
        ]

        # 2. Solo 3 Echo abilitati come eero Built-in nel cloud eero (dettagli di rete proxied_nodes)
        network_details = {
            "proxied_nodes": [
                {
                    "name": "Oasis Echo Spot",
                    "id": "echo_oasis_id",
                    "mac": "11:22:33:44:55:01",
                    "status": "active",
                    "connected": False,  # eero cloud proxied record can be connected: False
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
                    "connected": False,
                },
            ]
        }

        # 3. Dispositivi sulla LAN: 6 Echo totali presenti in casa
        # - 3 abilitati come Built-in
        # - 3 normali smart speaker Alexa NON abilitati come nodi eero (Office Echo, Spectre Echo, Echo 4th Gen)
        devices = [
            # Echo 1 (abilitato): Oasis - notare il nome parziale nel DHCP/nickname ("Oasis")
            {
                "id": "dev_oasis",
                "mac": "11:22:33:44:55:01",
                "hostname": "Oasis",
                "ip": "192.168.4.50",
                "connected": True,
                "model": "Echo Spot",
                "manufacturer": "Amazon Technologies Inc.",
            },
            # Echo 2 (abilitato): Miami - match per MAC e nome
            {
                "id": "dev_miami",
                "mac": "11:22:33:44:55:02",
                "hostname": "Miami Echo",
                "ip": "192.168.4.51",
                "connected": True,
                "model": "Echo",
                "manufacturer": "Amazon",
            },
            # Echo 3 (abilitato): Harmony
            {
                "id": "dev_harmony",
                "mac": "11:22:33:44:55:03",
                "hostname": "Harmony Echo Dot",
                "ip": "192.168.4.52",
                "connected": True,
                "model": "Echo Dot (5th Gen)",
                "manufacturer": "Amazon",
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

        # Verifica 4: I 3 nodi Built-in devono essere ONLINE e avere il loro IP LAN reale
        oasis_node = next(n for n in result if n["name"] == "Oasis Echo Spot")
        self.assertEqual(oasis_node["status"], "online")
        self.assertEqual(oasis_node["ip"], "192.168.4.50")
        self.assertEqual(oasis_node["mac_address"], "11:22:33:44:55:01")

        miami_node = next(n for n in result if n["name"] == "Miami Echo")
        self.assertEqual(miami_node["status"], "online")
        self.assertEqual(miami_node["ip"], "192.168.4.51")

        harmony_node = next(n for n in result if n["name"] == "Harmony Echo Dot")
        self.assertEqual(harmony_node["status"], "online")
        self.assertEqual(harmony_node["ip"], "192.168.4.52")


if __name__ == "__main__":
    unittest.main()
