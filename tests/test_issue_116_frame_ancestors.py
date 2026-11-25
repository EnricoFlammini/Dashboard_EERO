"""Issue #116: FRAME_ANCESTORS lets homelab dashboards (Homarr, Dashy, Glance...) embed the dashboard."""
import unittest
from unittest import mock

import httpx

import app.main as main_module
from app.main import build_frame_ancestors_policy


class TestBuildFrameAncestorsPolicy(unittest.TestCase):
    def test_empty_keeps_same_origin_default(self):
        for raw in ("", "   ", ",, ,"):
            self.assertEqual(build_frame_ancestors_policy(raw), (None, []))

    def test_origins_are_added_after_self(self):
        policy, rejected = build_frame_ancestors_policy(
            "https://homarr.home.lan, http://192.168.1.10:7575 http://localhost:3000/"
        )
        self.assertEqual(
            policy,
            "frame-ancestors 'self' https://homarr.home.lan http://192.168.1.10:7575 http://localhost:3000",
        )
        self.assertEqual(rejected, [])

    def test_wildcards_schemes_and_ports(self):
        policy, rejected = build_frame_ancestors_policy("https://*.home.lan,https:,http://dash.lan:*,*")
        self.assertEqual(policy, "frame-ancestors 'self' https://*.home.lan https: http://dash.lan:* *")
        self.assertEqual(rejected, [])

    def test_duplicates_and_explicit_self_are_collapsed(self):
        policy, _ = build_frame_ancestors_policy("'self',https://a.lan,HTTPS://A.LAN")
        self.assertEqual(policy, "frame-ancestors 'self' https://a.lan")

    def test_invalid_entries_are_rejected_and_cannot_inject_directives(self):
        policy, rejected = build_frame_ancestors_policy(
            "https://ok.lan;script-src,'unsafe-inline',ftp://x.lan,https://a.lan/path,'none'"
        )
        self.assertIsNone(policy)
        self.assertEqual(
            rejected,
            ["https://ok.lan;script-src", "'unsafe-inline'", "ftp://x.lan", "https://a.lan/path", "'none'"],
        )

    def test_valid_entries_survive_next_to_invalid_ones(self):
        policy, rejected = build_frame_ancestors_policy("https://homarr.lan,javascript:alert(1)")
        self.assertEqual(policy, "frame-ancestors 'self' https://homarr.lan")
        self.assertEqual(rejected, ["javascript:alert(1)"])


class TestSecurityHeaders(unittest.IsolatedAsyncioTestCase):
    async def _headers(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main_module.app), base_url="http://test") as client:
            res = await client.get("/api/health")
        return res.headers

    async def test_default_sends_x_frame_options_sameorigin(self):
        with mock.patch.object(main_module, "FRAME_ANCESTORS_POLICY", None):
            headers = await self._headers()
        self.assertEqual(headers.get("x-frame-options"), "SAMEORIGIN")
        self.assertNotIn("content-security-policy", headers)
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")

    async def test_configured_origins_send_csp_frame_ancestors(self):
        policy = "frame-ancestors 'self' https://homarr.home.lan"
        with mock.patch.object(main_module, "FRAME_ANCESTORS_POLICY", policy):
            headers = await self._headers()
        self.assertEqual(headers.get("content-security-policy"), policy)
        self.assertNotIn("x-frame-options", headers)
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")


if __name__ == "__main__":
    unittest.main()
