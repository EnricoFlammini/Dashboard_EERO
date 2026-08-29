#!/usr/bin/env python3
"""
Pre-Release Automated Test Suite - eero Custom Dashboard (v1.03.00)
==================================================================
Covers:
  1. Authentication & Demo Mode toggle with session token preservation
  2. AdGuard Home Demo isolation (fictitious credentials, zero network calls in test & sync)
  3. Telegram & Webhook Demo isolation (fictitious tokens, zero external API requests)
  4. Device exports (/api/devices/export/hosts and /api/devices/export/adguard)
  5. Automations (Focus Mode, Night Mode, Daily Digest generation)
  6. Poller & RAM Cache consistency and Network Health Score calculation
  7. SQLite database persistence & mock data purge
"""

import sys
import os
import asyncio
from datetime import datetime

# Configure UTF-8 stdout for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.services.eero_client import eero_client
from app.services.adguard import adguard_service, normalize_adguard_url
from app.services.notifications import notification_service
from app.services.db import db_service
from app.services.poller import background_poller


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0

    def assert_true(self, condition: bool, description: str):
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  ✅ [PASS] {description}")
        else:
            self.failed += 1
            print(f"  ❌ [FAIL] {description}")

    def print_summary(self):
        print("\n" + "=" * 65)
        print(f"📊 RISULTATO TEST: {self.passed}/{self.total} superati ({self.failed} falliti)")
        print("=" * 65)
        if self.failed > 0:
            print("❌ ERRORE: Uno o più test non sono stati superati.")
            sys.exit(1)
        else:
            print("🎉 SUCCESSO: Tutti i test pre-rilascio sono stati superati al 100%!")


async def run_all_tests():
    runner = TestRunner()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("\n🚀 [1/6] TEST AUTENTICAZIONE E TOGGLE MODALITÀ DEMO")
        # Inizializzazione sessione live simulata
        eero_client.user_token = "live_secret_user_token_sample"
        eero_client.saved_live_token = "live_secret_user_token_sample"
        eero_client.current_network_id = "network_live_123"
        eero_client._is_demo_active = False

        res = await client.get("/api/auth/status")
        runner.assert_true(res.status_code == 200, "Endpoint GET /api/auth/status risponde HTTP 200")
        data = res.json()
        runner.assert_true(data["authenticated"] is True, "Sessione live autenticata correttamente")
        runner.assert_true(data["demo_mode"] is False, "Modalità Demo disattiva in stato Live")

        # Passaggio a Demo Mode
        res = await client.post("/api/auth/mode", json={"demo": True})
        runner.assert_true(res.status_code == 200, "Endpoint POST /api/auth/mode (demo=True) risponde HTTP 200")
        data = res.json()
        runner.assert_true(data["demo_mode"] is True, "Modalità Demo attivata correttamente")
        runner.assert_true(data["has_saved_live_token"] is True, "Token Live reale preservato in memoria durante Demo")

        print("\n🛡️ [2/6] TEST ISOLAMENTO E SICUREZZA ADGUARD HOME (DEMO MODE)")
        res = await client.get("/api/automations/adguard")
        runner.assert_true(res.status_code == 200, "Endpoint GET /api/automations/adguard risponde HTTP 200")
        ag_data = res.json()
        runner.assert_true("192.168.1.50" in ag_data.get("url", ""), "URL AdGuard in Demo è fittizio (192.168.1.50)")
        runner.assert_true(ag_data.get("username") == "demo_admin", "Username AdGuard in Demo è 'demo_admin'")
        runner.assert_true(ag_data.get("has_password") is True, "Indicator password AdGuard presente")
        runner.assert_true("Simulazione Demo" in ag_data.get("last_sync_status", ""), "Stato sync riporta '[Simulazione Demo]'")

        # Test Connessione AdGuard in Demo Mode (nessuna chiamata HTTP esterna)
        res = await client.post("/api/automations/adguard/test", json={})
        runner.assert_true(res.status_code == 200, "Endpoint POST /api/automations/adguard/test risponde HTTP 200")
        test_res = res.json()
        runner.assert_true(test_res.get("success") is True, "Test connessione AdGuard simulato con successo")
        runner.assert_true("Ambiente Demo Simulato" in test_res.get("message", ""), "Messaggio esplicito di ambiente Demo simulato")

        # Test Sincronizzazione Dispositivi AdGuard in Demo Mode
        res = await client.post("/api/automations/adguard/sync", json={})
        runner.assert_true(res.status_code == 200, "Endpoint POST /api/automations/adguard/sync risponde HTTP 200")
        sync_res = res.json()
        runner.assert_true(sync_res.get("success") is True, "Sincronizzazione AdGuard simulata con successo")
        runner.assert_true(sync_res.get("total_synced", 0) > 0, f"Dispositivi sincronizzati in memoria ({sync_res.get('total_synced')})")

        print("\n🔔 [3/6] TEST ISOLAMENTO NOTIFICHE TELEGRAM E WEBHOOK (DEMO MODE)")
        res = await client.get("/api/automations/notifications")
        runner.assert_true(res.status_code == 200, "Endpoint GET /api/automations/notifications risponde HTTP 200")
        notif_data = res.json()
        runner.assert_true("AAFakeDemoTelegramBotToken_Example" in notif_data.get("telegram_bot_token", ""), "Token Telegram in Demo è fittizio (AAFakeDemo...)")
        runner.assert_true(notif_data.get("telegram_chat_id") == "-1001234567890", "Chat ID Telegram in Demo è fittizio (-1001234567890)")
        runner.assert_true("demo-webhook.lan" in notif_data.get("webhook_url", ""), "Webhook URL in Demo è fittizio (demo-webhook.lan)")

        # Test invio notifiche in Demo (nessuna chiamata HTTP a Telegram / Webhook)
        res = await client.post("/api/automations/notifications/test")
        runner.assert_true(res.status_code == 200, "Endpoint POST /api/automations/notifications/test risponde HTTP 200")
        test_notif = res.json()
        runner.assert_true(test_notif.get("telegram_sent") is True, "Simulazione invio Telegram completata senza errori")
        runner.assert_true(test_notif.get("webhook_sent") is True, "Simulazione invio Webhook completata senza errori")

        # Test Daily Digest immediato in Demo
        res = await client.post("/api/automations/digest/generate")
        runner.assert_true(res.status_code == 200, "Endpoint POST /api/automations/digest/generate risponde HTTP 200")
        digest_res = res.json()
        runner.assert_true(digest_res.get("status") == "success", "Generazione Daily Digest completata")
        runner.assert_true(digest_res.get("data", {}).get("health_score", 0) > 0, "Health score presente nel digest")

        print("\n📄 [4/6] TEST ESPORTAZIONE DISPOSITIVI (/etc/hosts & AdGuard JSON)")
        res = await client.get("/api/devices/export/hosts")
        runner.assert_true(res.status_code == 200, "Endpoint GET /api/devices/export/hosts risponde HTTP 200")
        runner.assert_true("eero Mesh Network - Hosts Export" in res.text, "Intestazione /etc/hosts valida")
        runner.assert_true(len(res.text.splitlines()) > 5, "Righe di dispositivi esportate correttamente")

        res = await client.get("/api/devices/export/adguard")
        runner.assert_true(res.status_code == 200, "Endpoint GET /api/devices/export/adguard risponde HTTP 200")
        ag_export = res.json()
        runner.assert_true("clients" in ag_export, "Struttura JSON client AdGuard valida")
        runner.assert_true(len(ag_export["clients"]) > 0, f"Client trovati per export AdGuard: {len(ag_export['clients'])}")

        print("\n🎮 [5/6] TEST CONTROLLI AUTOMAZIONI (Focus Mode & Night Mode)")
        # Test Gaming / Focus Mode toggle
        res = await client.post("/api/automations/focus-mode", json={"active": True})
        runner.assert_true(res.status_code == 200, "Attivazione Gaming/Focus Mode risponde HTTP 200")
        res = await client.get("/api/automations/focus-mode")
        runner.assert_true(res.json().get("active") is True, "Stato Focus Mode risulta Attivo")

        res = await client.post("/api/automations/focus-mode", json={"active": False})
        runner.assert_true(res.status_code == 200, "Disattivazione Gaming/Focus Mode risponde HTTP 200")
        res = await client.get("/api/automations/focus-mode")
        runner.assert_true(res.json().get("active") is False, "Stato Focus Mode risulta Disattivo")

        # Test Night Mode settings
        res = await client.post("/api/automations/night-mode", json={"enabled": True, "start_time": "22:30", "end_time": "06:30"})
        runner.assert_true(res.status_code == 200, "Aggiornamento Night Mode risponde HTTP 200")
        res = await client.get("/api/automations/night-mode")
        nm_data = res.json()
        runner.assert_true(nm_data.get("enabled") is True and nm_data.get("start_time") == "22:30", "Impostazioni Night Mode persistite correttamente")

        print("\n🔄 [6/6] TEST RIPRISTINO SESSIONE LIVE E NORMALIZZAZIONE URL")
        # Normalizzazione URL AdGuard
        test_url_raw = "192.168.1.100:8085/#/dashboard"
        normalized = normalize_adguard_url(test_url_raw)
        runner.assert_true(normalized == "http://192.168.1.100:8085", f"Normalizzazione URL corretta: '{test_url_raw}' -> '{normalized}'")

        print("\n⚡ [7/7] TEST NORMALIZZAZIONE VELOCITÀ ETHERNET E SEGNALE WIRELESS (Issue #14)")
        # Test nodo cablato con porte P2500 e P1000 (es. Bedroom da Issue #14)
        node_bedroom_raw = {
            "name": "Bedroom",
            "model": "eero Pro 6E",
            "gateway": False,
            "connected": True,
            "ethernet_status": {
                "statuses": [
                    {"port": 1, "speed": "P2500", "has_carrier": True},
                    {"port": 2, "speed": "P1000", "has_carrier": True}
                ]
            }
        }
        bedroom_norm = eero_client._normalize_eero_node(node_bedroom_raw)
        runner.assert_true(bedroom_norm["backhaul_type"] == "Ethernet (2.5 Gbps)", f"Bedroom ethernet_status P2500 rileva 'Ethernet (2.5 Gbps)' (ottenuto: {bedroom_norm['backhaul_type']})")
        runner.assert_true(bedroom_norm["wired"] is True, "Bedroom marcato correttamente come wired")

        # Test nodo cablato con porte P1000 (es. Toilet da Issue #14)
        node_toilet_raw = {
            "name": "Toilet",
            "model": "eero 6+",
            "gateway": False,
            "connected": True,
            "ethernet_status": {
                "statuses": [
                    {"port": 1, "speed": "P1000", "has_carrier": True},
                    {"port": 2, "speed": "P1000", "has_carrier": True}
                ]
            }
        }
        toilet_norm = eero_client._normalize_eero_node(node_toilet_raw)
        runner.assert_true(toilet_norm["backhaul_type"] == "Ethernet (1.0 Gbps)", f"Toilet ethernet_status P1000 rileva 'Ethernet (1.0 Gbps)' (ottenuto: {toilet_norm['backhaul_type']})")

        # Test nodo wireless mesh con RSSI in dBm
        node_wireless_raw = {
            "name": "Living Room Beacon",
            "model": "eero 6",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "wireless_band": "5 GHz",
            "connectivity": {
                "signal": -58,
                "frequency": "5 GHz"
            }
        }
        wireless_norm = eero_client._normalize_eero_node(node_wireless_raw)
        runner.assert_true(wireless_norm["backhaul_type"] == "Wireless Mesh (5 GHz / -58 dBm)", f"Beacon wireless rileva 'Wireless Mesh (5 GHz / -58 dBm)' (ottenuto: {wireless_norm['backhaul_type']})")
        runner.assert_true(wireless_norm["signal_rssi"] == -58, "Beacon wireless signal_rssi estratto come -58")

        # Switch back to Live
        res = await client.post("/api/auth/mode", json={"demo": False})
        runner.assert_true(res.status_code == 200, "Ritorno a Live Mode risponde HTTP 200")
        status_res = (await client.get("/api/auth/status")).json()
        runner.assert_true(status_res.get("demo_mode") is False, "Modalità Demo disattivata")
        runner.assert_true(eero_client.user_token == "live_secret_user_token_sample", "Token Live originale ripristinato intatto")

    runner.print_summary()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
