"""A stale session_token cookie must not blank the dashboard when local login is optional.

Plain fetch() calls carried only the cookie. Once that cookie's session was gone,
every data endpoint answered 401 while /me (sent with the Bearer header) still
reported the user as logged in, so the Devices page showed no devices at all.
"""
import unittest
from pathlib import Path

import httpx

from app.config import settings
from app.main import app
from app.services.db import db_service


GUARDED_GET = "/api/devices"  # require_permission("view_devices")


class TestStaleSessionCookie(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await db_service.init_db()
        self._require = settings.require_local_auth
        settings.require_local_auth = False
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        settings.require_local_auth = self._require
        await self.client.aclose()

    async def test_stale_cookie_is_ignored_and_cleared_when_login_optional(self):
        self.client.cookies.set("session_token", "stale-cookie-token-0000")
        res = await self.client.get(GUARDED_GET)
        self.assertEqual(res.status_code, 200, res.text)
        set_cookie = res.headers.get("set-cookie", "")
        self.assertIn("session_token=", set_cookie)
        self.assertTrue("Max-Age=0" in set_cookie or "expires=" in set_cookie.lower(), set_cookie)

    async def test_stale_cookie_still_401_when_login_required(self):
        settings.require_local_auth = True
        self.client.cookies.set("session_token", "stale-cookie-token-0000")
        res = await self.client.get(GUARDED_GET)
        self.assertEqual(res.status_code, 401)

    async def test_invalid_bearer_header_still_401(self):
        # The frontend relies on this 401 to notice an expired login.
        res = await self.client.get(GUARDED_GET, headers={"Authorization": "Bearer FakeInvalidToken12345"})
        self.assertEqual(res.status_code, 401)

    async def test_invalid_header_wins_over_cookie(self):
        self.client.cookies.set("session_token", "stale-cookie-token-0000")
        res = await self.client.get(GUARDED_GET, headers={"Authorization": "Bearer FakeInvalidToken12345"})
        self.assertEqual(res.status_code, 401)


class TestFetchWrapperSendsToken(unittest.TestCase):
    def test_wrapper_attaches_stored_token(self):
        src = Path("app/static/js/app.js").read_text(encoding="utf-8")
        wrapper = src[: src.index("document.addEventListener('alpine:init'")]
        self.assertIn("eero_local_auth_token", wrapper)
        self.assertIn("headers.set('Authorization'", wrapper)


if __name__ == "__main__":
    unittest.main()
