import json
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

import httpx

from app.config import settings
from app.i18n import SUPPORTED_LANGUAGES
from app.services import public_ip as public_ip_module
from app.services.public_ip import PublicIPService, _parse_lookup_response, classify_ip


class TestClassifyIp(unittest.TestCase):
    def test_public(self):
        self.assertEqual(classify_ip("93.42.178.105"), "public")
        self.assertEqual(classify_ip("2a01:4f8::1"), "public")

    def test_private_ranges(self):
        for ip in ("192.168.1.1", "10.0.0.1", "172.16.5.4", "169.254.1.1", "fd00::1"):
            self.assertEqual(classify_ip(ip), "private", ip)

    def test_cgnat(self):
        self.assertEqual(classify_ip("100.64.0.1"), "cgnat")
        self.assertEqual(classify_ip("100.127.255.254"), "cgnat")

    def test_not_an_ip(self):
        for value in (None, "", "0.0.0.0x", "router.local"):
            self.assertIsNone(classify_ip(value), value)

    def test_lookup_parsing(self):
        self.assertEqual(_parse_lookup_response('{"ip":"81.2.69.142"}'), "81.2.69.142")
        self.assertEqual(_parse_lookup_response("81.2.69.142\n"), "81.2.69.142")
        # A lookup must never report a private address as the public one.
        self.assertIsNone(_parse_lookup_response("192.168.1.1"))
        self.assertIsNone(_parse_lookup_response("<html>blocked</html>"))


def _responder(*bodies):
    """Fake lookup services answering in order; None means a connection error."""
    calls = []

    def handler(request):
        calls.append(str(request.url))
        body = bodies[len(calls) - 1] if len(calls) <= len(bodies) else None
        if body is None:
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(200, text=body)

    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    return mock.patch.object(public_ip_module.httpx, "AsyncClient", side_effect=factory), calls


class TestResolve(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = PublicIPService()
        self._lookup_setting = settings.public_ip_lookup
        settings.public_ip_lookup = True

    def tearDown(self):
        settings.public_ip_lookup = self._lookup_setting

    async def test_public_wan_ip_needs_no_lookup(self):
        patcher, calls = _responder()
        with patcher:
            data = await self.service.resolve("93.42.178.105")
        self.assertEqual(calls, [])
        self.assertEqual(data["public_ip"], "93.42.178.105")
        self.assertEqual(data["source"], "eero")
        self.assertFalse(data["double_nat"])
        self.assertFalse(data["cgnat"])

    async def test_private_wan_ip_is_double_nat_and_looked_up(self):
        patcher, calls = _responder('{"ip":"81.2.69.142"}')
        with patcher:
            data = await self.service.resolve("192.168.1.1")
        self.assertEqual(len(calls), 1)
        self.assertTrue(data["double_nat"])
        self.assertEqual(data["eero_wan_ip_type"], "private")
        self.assertEqual(data["public_ip"], "81.2.69.142")
        self.assertEqual(data["source"], "lookup")
        self.assertIsNotNone(data["checked_at"])

    async def test_cgnat_detected(self):
        patcher, _ = _responder("81.2.69.142")
        with patcher:
            data = await self.service.resolve("100.72.10.3")
        self.assertTrue(data["cgnat"])
        self.assertFalse(data["double_nat"])
        self.assertEqual(data["public_ip"], "81.2.69.142")

    async def test_falls_back_to_next_service(self):
        patcher, calls = _responder(None, "garbage", "81.2.69.142\n")
        with patcher:
            data = await self.service.resolve("10.0.0.2")
        self.assertEqual(len(calls), 3)
        self.assertEqual(data["public_ip"], "81.2.69.142")

    async def test_result_is_cached(self):
        patcher, calls = _responder("81.2.69.142", "81.2.69.200")
        with patcher:
            await self.service.resolve("192.168.1.1")
            data = await self.service.resolve("192.168.1.1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(data["public_ip"], "81.2.69.142")

    async def test_forced_refresh_is_rate_limited(self):
        patcher, calls = _responder("81.2.69.142", "81.2.69.200")
        with patcher:
            await self.service.resolve("192.168.1.1")
            await self.service.resolve("192.168.1.1", force=True)  # within a minute: served from cache
            self.assertEqual(len(calls), 1)
            self.service._checked_at -= timedelta(minutes=2)
            data = await self.service.resolve("192.168.1.1", force=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(data["public_ip"], "81.2.69.200")

    async def test_all_services_failing_keeps_last_known_ip(self):
        patcher, _ = _responder("81.2.69.142")
        with patcher:
            await self.service.resolve("192.168.1.1")
        self.service._next_attempt = None  # cache expired
        patcher, calls = _responder(None, None, None)
        with patcher:
            data = await self.service.resolve("192.168.1.1")
        self.assertEqual(len(calls), 3)
        self.assertEqual(data["public_ip"], "81.2.69.142")

    async def test_lookup_disabled_never_calls_out(self):
        settings.public_ip_lookup = False
        patcher, calls = _responder("81.2.69.142")
        with patcher:
            data = await self.service.resolve("192.168.1.1")
        self.assertEqual(calls, [])
        self.assertTrue(data["double_nat"])
        self.assertIsNone(data["public_ip"])
        self.assertFalse(data["lookup_enabled"])


class TestPublicIpEndpoint(unittest.IsolatedAsyncioTestCase):
    async def test_endpoint_uses_cached_network_wan_ip(self):
        from app.main import app
        from app.services.poller import background_poller

        state = {"network": {"public_ip": "93.42.178.105"}}
        with mock.patch.object(background_poller, "get_cached_state", return_value=state):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get("/api/network/public-ip")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["public_ip"], "93.42.178.105")
        self.assertEqual(data["source"], "eero")


class TestPublicIpTranslations(unittest.TestCase):
    def test_all_languages_have_strings(self):
        for lang in SUPPORTED_LANGUAGES:
            dash = json.loads(Path(f"app/static/locales/{lang}.json").read_text(encoding="utf-8"))["dashboard"]
            for key in ("public_ip_label", "public_ip_unknown", "double_nat", "double_nat_tooltip", "cgnat_tooltip"):
                self.assertTrue(dash.get(key), f"{lang}: dashboard.{key}")


if __name__ == "__main__":
    unittest.main()
