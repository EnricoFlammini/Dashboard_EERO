import asyncio
import json
import unittest
from pathlib import Path
from unittest import mock

import httpx

from app import main
from app.i18n import SUPPORTED_LANGUAGES
from app.main import app
from app.services.db import db_service
from app.services.maintenance import (
    STAGE_DB_REPAIR,
    STAGE_STARTING,
    STAGE_STARTUP_FAILED,
    MaintenanceState,
    maintenance_state,
)


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _reset_state():
    maintenance_state._stages.clear()
    maintenance_state._since = None


class TestMaintenanceState(unittest.TestCase):
    def test_stages_nest_and_fall_back(self):
        state = MaintenanceState()
        self.assertFalse(state.active)
        with state.stage_scope(STAGE_STARTING):
            self.assertEqual(state.stage, STAGE_STARTING)
            since = state.snapshot()["since"]
            with state.stage_scope(STAGE_DB_REPAIR):
                self.assertEqual(state.stage, STAGE_DB_REPAIR)
                # The clock keeps counting from the first stage.
                self.assertEqual(state.snapshot()["since"], since)
            self.assertEqual(state.stage, STAGE_STARTING)
        self.assertFalse(state.active)
        self.assertEqual(state.snapshot(), {"stage": None, "since": None})

    def test_scope_ends_on_error(self):
        state = MaintenanceState()
        with self.assertRaises(RuntimeError):
            with state.stage_scope(STAGE_DB_REPAIR):
                raise RuntimeError("boom")
        self.assertFalse(state.active)


class TestMaintenanceGate(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _reset_state()

    def tearDown(self):
        _reset_state()

    async def test_health_reports_maintenance_with_http_200(self):
        maintenance_state.begin(STAGE_DB_REPAIR)
        async with _client() as client:
            res = await client.get("/api/health")
        self.assertEqual(res.status_code, 200)  # the Docker healthcheck must not restart a repair
        body = res.json()
        self.assertEqual(body["status"], "maintenance")
        self.assertEqual(body["maintenance"]["stage"], STAGE_DB_REPAIR)
        self.assertIsNotNone(body["maintenance"]["since"])

    async def test_api_is_gated_while_maintenance_runs(self):
        maintenance_state.begin(STAGE_STARTING)
        async with _client() as client:
            res = await client.get("/api/auth/local/status", headers={"X-Dashboard-Lang": "it"})
            metrics = await client.get("/metrics")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.headers["X-Dashboard-Maintenance"], STAGE_STARTING)
        self.assertEqual(res.headers["Retry-After"], "2")
        self.assertEqual(res.json()["status"], "maintenance")
        self.assertIn("manutenzione", res.json()["detail"])
        self.assertEqual(metrics.status_code, 503)

    async def test_pages_and_static_files_are_served_during_maintenance(self):
        maintenance_state.begin(STAGE_STARTING)
        async with _client() as client:
            page = await client.get("/devices")
            locale = await client.get("/static/locales/en.json")
        self.assertEqual(page.status_code, 200)
        self.assertIn("maintenance-title", page.text)
        self.assertEqual(locale.status_code, 200)

    async def test_failed_startup_turns_health_unhealthy(self):
        maintenance_state.begin(STAGE_STARTUP_FAILED)
        async with _client() as client:
            res = await client.get("/api/health")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["status"], "error")

    async def test_healthy_when_idle(self):
        async with _client() as client:
            res = await client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")
        self.assertNotIn("maintenance", res.json())

    async def test_db_repair_reports_its_stage(self):
        seen = []

        async def fake_repair(error):
            seen.append(maintenance_state.stage)
            return True

        with mock.patch.object(db_service, "_repair_malformed", side_effect=fake_repair):
            self.assertTrue(await db_service.repair_if_malformed(Exception("malformed")))
        self.assertEqual(seen, [STAGE_DB_REPAIR])
        self.assertFalse(maintenance_state.active)


class TestBackgroundStartup(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _reset_state()

    def tearDown(self):
        _reset_state()

    async def test_slow_startup_serves_maintenance_then_becomes_healthy(self):
        release = asyncio.Event()

        async def slow_start():
            await release.wait()

        with mock.patch.object(main, "_start_services", side_effect=slow_start), \
                mock.patch.object(main, "STARTUP_GRACE_SECONDS", 0.05):
            async with app.router.lifespan_context(app):
                async with _client() as client:
                    during = (await client.get("/api/health")).json()
                    release.set()
                    await asyncio.sleep(0.05)
                    after = (await client.get("/api/health")).json()
        self.assertEqual(during["status"], "maintenance")
        self.assertEqual(during["maintenance"]["stage"], STAGE_STARTING)
        self.assertEqual(after["status"], "healthy")

    async def test_fast_startup_failure_still_aborts(self):
        async def failing_start():
            raise RuntimeError("bad config")

        with mock.patch.object(main, "_start_services", side_effect=failing_start):
            with self.assertRaises(RuntimeError):
                async with app.router.lifespan_context(app):
                    pass
        self.assertFalse(maintenance_state.active)

    async def test_late_startup_failure_keeps_api_gated(self):
        release = asyncio.Event()

        async def slow_failing_start():
            await release.wait()
            raise RuntimeError("migration failed")

        with mock.patch.object(main, "_start_services", side_effect=slow_failing_start), \
                mock.patch.object(main, "STARTUP_GRACE_SECONDS", 0.05):
            async with app.router.lifespan_context(app):
                release.set()
                await asyncio.sleep(0.05)
                self.assertEqual(maintenance_state.stage, STAGE_STARTUP_FAILED)


class TestMaintenanceTranslations(unittest.TestCase):
    def test_all_languages_have_maintenance_strings(self):
        for lang in SUPPORTED_LANGUAGES:
            ui = json.loads(Path(f"app/static/locales/{lang}.json").read_text(encoding="utf-8"))["maintenance"]
            for key in ("title", "stage_starting", "stage_db_repair", "stage_startup_failed", "auto_reload", "elapsed"):
                self.assertTrue(ui.get(key), f"{lang}: maintenance.{key}")
            self.assertIn("{seconds}", ui["elapsed"], lang)
            backend = json.loads(Path(f"app/i18n_locales/{lang}/common.json").read_text(encoding="utf-8"))
            self.assertTrue(backend.get("maintenance_in_progress"), lang)


if __name__ == "__main__":
    unittest.main()
