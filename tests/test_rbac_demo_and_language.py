import json
import unittest
from pathlib import Path
import httpx

from app.main import app
from app.services.auth_service import (
    ACTION_SCOPES,
    ALL_ACTION_PERMISSION_KEYS,
    ALL_PERMISSION_KEYS,
    UI_PERMISSION_KEYS,
    auth_service,
)
from app.services.db import db_service
from app.i18n import SUPPORTED_LANGUAGES


class TestRBACDemoAndLanguage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await db_service.init_db()

    def test_permission_catalog_includes_new_scopes(self):
        """Verifica che action_toggle_demo e action_change_language siano registrati in ACTION_SCOPES e catalog."""
        action_keys = [s["key"] for s in ACTION_SCOPES]
        self.assertIn("action_toggle_demo", action_keys)
        self.assertIn("action_change_language", action_keys)
        self.assertIn("action_toggle_demo", ALL_ACTION_PERMISSION_KEYS)
        self.assertIn("action_change_language", ALL_ACTION_PERMISSION_KEYS)
        self.assertIn("action_toggle_demo", ALL_PERMISSION_KEYS)
        self.assertIn("action_change_language", ALL_PERMISSION_KEYS)
        self.assertIn("action_toggle_demo", UI_PERMISSION_KEYS)
        self.assertIn("action_change_language", UI_PERMISSION_KEYS)

        catalog = auth_service.get_permissions_catalog()
        self.assertIn("action_toggle_demo", catalog["all_keys"])
        self.assertIn("action_change_language", catalog["all_keys"])

    def test_translations_in_all_supported_languages(self):
        """Verifica che tutte e 9 le lingue abbiano etichette e descrizioni complete per i 2 nuovi permessi."""
        base_dir = Path("app/i18n_locales")
        for lang in SUPPORTED_LANGUAGES:
            perm_file = base_dir / lang / "permissions.json"
            self.assertTrue(perm_file.exists(), f"File non trovato: {perm_file}")
            with open(perm_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("action_toggle_demo_label", data, f"Manca action_toggle_demo_label in {lang}")
            self.assertIn("action_toggle_demo_desc", data, f"Manca action_toggle_demo_desc in {lang}")
            self.assertIn("action_change_language_label", data, f"Manca action_change_language_label in {lang}")
            self.assertIn("action_change_language_desc", data, f"Manca action_change_language_desc in {lang}")
            self.assertTrue(bool(data["action_toggle_demo_label"].strip()))
            self.assertTrue(bool(data["action_toggle_demo_desc"].strip()))
            self.assertTrue(bool(data["action_change_language_label"].strip()))
            self.assertTrue(bool(data["action_change_language_desc"].strip()))

    async def test_rbac_endpoints_enforcement(self):
        """Verifica che /api/auth/mode e /api/system/language siano protetti da RBAC:
        - Admin: autorizzato sempre di default
        - Utente con permesso: autorizzato (200)
        - Utente senza permesso: bloccato con HTTP 403 Forbidden
        """
        # Creiamo 3 utenti di test:
        # 1. admin_rbac (is_admin=True)
        # 2. op_demo_only (permissions=['action_toggle_demo'])
        # 3. op_lang_only (permissions=['action_change_language'])
        # 4. op_neither (permissions=['view_topology'])

        pwd = "TestPassword123!"
        h, s = auth_service.hash_password(pwd)

        async def _ensure_user(username, is_admin, perms):
            u = await db_service.get_local_user_by_username(username)
            if u:
                await db_service.update_local_user(u["id"], is_admin=is_admin, permissions=perms)
                return u["id"]
            return await db_service.create_local_user(
                username=username,
                password_hash=h,
                salt=s,
                display_name=username,
                role="admin" if is_admin else "operator",
                is_admin=is_admin,
                permissions=perms
            )

        await _ensure_user("admin_rbac_test", True, ALL_PERMISSION_KEYS)
        await _ensure_user("op_demo_only", False, ["action_toggle_demo"])
        await _ensure_user("op_lang_only", False, ["action_change_language"])
        await _ensure_user("op_neither", False, ["view_topology"])

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Login helper
            async def _login(username):
                res = await client.post("/api/auth/local/login", json={"username": username, "password": pwd})
                self.assertEqual(res.status_code, 200, f"Login fallito per {username}: {res.text}")
                token = res.json()["token"]
                return {"Authorization": f"Bearer {token}"}

            admin_headers = await _login("admin_rbac_test")
            demo_headers = await _login("op_demo_only")
            lang_headers = await _login("op_lang_only")
            neither_headers = await _login("op_neither")

            # 1. Test POST /api/auth/mode
            # Admin: OK
            res = await client.post("/api/auth/mode", json={"demo": True}, headers=admin_headers)
            self.assertEqual(res.status_code, 200)

            # Op with action_toggle_demo: OK
            res = await client.post("/api/auth/mode", json={"demo": True}, headers=demo_headers)
            self.assertEqual(res.status_code, 200)

            # Op without action_toggle_demo (lang only): 403 Forbidden
            res = await client.post("/api/auth/mode", json={"demo": True}, headers=lang_headers)
            self.assertEqual(res.status_code, 403)

            # Op without action_toggle_demo (neither): 403 Forbidden
            res = await client.post("/api/auth/mode", json={"demo": True}, headers=neither_headers)
            self.assertEqual(res.status_code, 403)

            # 2. Test POST /api/system/language
            # Admin: OK
            res = await client.post("/api/system/language", json={"language": "it"}, headers=admin_headers)
            self.assertEqual(res.status_code, 200)

            # Op with action_change_language: OK
            res = await client.post("/api/system/language", json={"language": "en"}, headers=lang_headers)
            self.assertEqual(res.status_code, 200)

            # Op without action_change_language (demo only): 403 Forbidden
            res = await client.post("/api/system/language", json={"language": "it"}, headers=demo_headers)
            self.assertEqual(res.status_code, 403)

            # Op without action_change_language (neither): 403 Forbidden
            res = await client.post("/api/system/language", json={"language": "it"}, headers=neither_headers)
            self.assertEqual(res.status_code, 403)
