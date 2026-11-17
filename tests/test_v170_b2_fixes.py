import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.eero_client import EeroClient
from app.routers.automations import _NOTIFICATION_SECRET_FIELDS


class TestV170Build2Fixes(unittest.IsolatedAsyncioTestCase):
    def test_ntfy_token_in_secret_fields(self):
        """Verifica che ntfy_token sia incluso tra i campi segreti da mascherare."""
        self.assertIn("ntfy_token", _NOTIFICATION_SECRET_FIELDS)

    async def test_ipv6_firewall_rules_auto_fetches_account_info_and_sanitizes_id(self):
        """Verifica che get_ipv6_firewall_rules chiami fetch_account_info se network_id è vuoto e rimuova slash."""
        client = EeroClient()
        client._is_demo_active = False
        client.user_token = "live_test_token_123456"
        client.current_network_id = None

        mock_resp_account = {
            "networks": [{"id": "net_test_123", "name": "Main Mesh", "url": "/2.2/networks/net_test_123"}]
        }

        async def mock_fetch():
            client.current_network_id = "net_test_123/"
            return mock_resp_account

        client.fetch_account_info = mock_fetch

        mock_resp_fw = MagicMock()
        mock_resp_fw.status_code = 200
        mock_resp_fw.json.return_value = {
            "data": [
                {
                    "id": "rule_99",
                    "device_name": "TestServer",
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "protocol": "TCP",
                    "ports": "8080",
                    "enabled": True,
                }
            ]
        }

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_resp_fw
        client._client_session = MagicMock(return_value=mock_http)
        mock_http.__aenter__.return_value = mock_http

        rules = await client.get_ipv6_firewall_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "rule_99")
        self.assertEqual(rules[0]["ports"], "8080")

        # Verifica che l'URL chiamato non abbia doppio slash
        called_url = mock_http.get.call_args[0][0]
        self.assertIn("/networks/net_test_123/firewall_rules", called_url)
        self.assertNotIn("//firewall_rules", called_url)

    async def test_ipv6_firewall_rules_fallback_endpoints(self):
        """Verifica che se /firewall_rules restituisce 404, venga tentato /ipv6/firewall_rules."""
        client = EeroClient()
        client._is_demo_active = False
        client.user_token = "live_test_token_123456"
        client.current_network_id = "net_fallback_456"

        mock_404 = MagicMock()
        mock_404.status_code = 404

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {
            "data": [
                {
                    "url": "/2.2/networks/net_fallback_456/ipv6/firewall_rules/pin_1",
                    "device_name": "Storage",
                    "ports": "22",
                }
            ]
        }

        mock_http = AsyncMock()
        mock_http.get.side_effect = [mock_404, mock_200]
        client._client_session = MagicMock(return_value=mock_http)
        mock_http.__aenter__.return_value = mock_http

        rules = await client.get_ipv6_firewall_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "pin_1")
        self.assertEqual(rules[0]["ports"], "22")
        self.assertEqual(mock_http.get.call_count, 2)

    async def test_add_ipv6_firewall_rule_informative_404_error(self):
        """Verifica che un 404 cloud sollevi un errore esplicativo su bridge mode/IPv6 inattivo."""
        client = EeroClient()
        client._is_demo_active = False
        client.user_token = "live_test_token_123456"
        client.current_network_id = "net_bridge_789"

        mock_404 = MagicMock()
        mock_404.status_code = 404

        mock_http = AsyncMock()
        mock_http.post.return_value = mock_404
        client._client_session = MagicMock(return_value=mock_http)
        mock_http.__aenter__.return_value = mock_http

        with self.assertRaises(RuntimeError) as ctx:
            await client.add_ipv6_firewall_rule({"mac": "11:22:33:44:55:66", "ports": "80"})
        self.assertIn("Bridge Mode or IPv6 inactive", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
