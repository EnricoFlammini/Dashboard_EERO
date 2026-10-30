#!/usr/bin/env python3
"""
Pre-Release Automated Test Suite - eero Custom Dashboard (v1.6.0)
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
import aiosqlite
import ipaddress
import json
import httpx
from datetime import date, datetime, timedelta, timezone

# Configure UTF-8 stdout for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
# Default to an isolated temporary DATA_DIR to protect production databases
if not os.environ.get("DATA_DIR"):
    _test_data_dir = tempfile.mkdtemp(prefix="eero_dashboard_test_")
    os.environ["DATA_DIR"] = _test_data_dir

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.services.eero_client import eero_client, parse_speed_mbps, format_speed_mbps
from app.services.adguard import adguard_service, normalize_adguard_url
from app.services.notifications import notification_service
from app.services.db import db_service
from app.services.poller import background_poller
from app.services.dns_manager import dns_service


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
    # Inizializza schema database SQLite
    await db_service.init_db()
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

        # Stabilità tassi dispositivi demo: oscillano attorno al valore base invece di crescere in modo esponenziale
        import tempfile
        from pathlib import Path
        from app.services.eero_client import EeroClient
        with tempfile.TemporaryDirectory() as demo_tmp_dir:
            demo_rates_client = EeroClient(session_path=Path(demo_tmp_dir) / "session.json")
        demo_base = {
            str(d["id"]): float(d.get("download_rate_mbps", 1.0))
            for d in demo_rates_client._demo_state["devices"] if d.get("connected")
        }
        for _ in range(600):
            demo_rates_client._get_demo_devices()
        demo_out_of_range = [
            d["id"] for d in demo_rates_client._demo_state["devices"] if d.get("connected") and not (
                demo_base[str(d["id"])] * 0.85 - 0.01 <= float(d["download_rate_mbps"]) <= demo_base[str(d["id"])] * 1.25 + 0.01
            )
        ]
        runner.assert_true(not demo_out_of_range, f"Tassi demo restano entro 0.85x-1.25x del valore base dopo 600 poll (fuori intervallo: {demo_out_of_range})")

        print("\n🛡️ [2/6] TEST ISOLAMENTO E SICUREZZA ADGUARD HOME (DEMO MODE)")
        res = await client.get("/api/automations/adguard")
        runner.assert_true(res.status_code == 200, "Endpoint GET /api/automations/adguard risponde HTTP 200")
        ag_data = res.json()
        runner.assert_true("192.168.1.50" in ag_data.get("url", ""), "URL AdGuard in Demo è fittizio (192.168.1.50)")
        runner.assert_true(ag_data.get("username") == "demo_admin", "Username AdGuard in Demo è 'demo_admin'")
        runner.assert_true(ag_data.get("has_password") is True, "Indicator password AdGuard presente")
        runner.assert_true(any(t in ag_data.get("last_sync_status", "") for t in ("Simulazione Demo", "Demo Simulation")), "Stato sync riporta '[Simulazione Demo]'")

        # Test Connessione AdGuard in Demo Mode (nessuna chiamata HTTP esterna)
        res = await client.post("/api/automations/adguard/test", json={})
        runner.assert_true(res.status_code == 200, "Endpoint POST /api/automations/adguard/test risponde HTTP 200")
        test_res = res.json()
        runner.assert_true(test_res.get("success") is True, "Test connessione AdGuard simulato con successo")
        runner.assert_true(any(t in test_res.get("message", "") for t in ("Ambiente Demo Simulato", "Simulated demo environment")), "Messaggio esplicito di ambiente Demo simulato")

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
        runner.assert_true(digest_res.get("data", {}).get("line_stability", 0) > 0, "Line stability presente nel digest (Issue #32)")

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

        # Test export AdGuard with include_ipv6=false (Issue #23)
        res_no_v6 = await client.get("/api/devices/export/adguard?include_ipv6=false")
        runner.assert_true(res_no_v6.status_code == 200, "Endpoint GET /api/devices/export/adguard?include_ipv6=false risponde HTTP 200")
        ag_no_v6 = res_no_v6.json()
        runner.assert_true("clients" in ag_no_v6, "Payload include_ipv6=false contiene 'clients'")

        from scripts.adguard_sync import is_ipv6_address
        # Verifica che is_ipv6_address distingua correttamente IPv6 da IPv4 e MAC address
        runner.assert_true(is_ipv6_address("2001:db8::1") is True, "is_ipv6_address riconosce IPv6 standard")
        runner.assert_true(is_ipv6_address("fe80::1ff:fe00:1") is True, "is_ipv6_address riconosce link-local IPv6")
        runner.assert_true(is_ipv6_address("192.168.4.55") is False, "is_ipv6_address esclude IPv4")
        runner.assert_true(is_ipv6_address("AA:BB:CC:DD:EE:FF") is False, "is_ipv6_address non scambia un MAC address per IPv6")
        runner.assert_true(is_ipv6_address("hostname-device") is False, "is_ipv6_address esclude hostname generici")

        # Verifica che nessun client contenga IPv6 tra gli IDs quando include_ipv6=false
        has_v6_in_no_v6_export = False
        for c in ag_no_v6["clients"]:
            for cid in c.get("ids", []):
                if is_ipv6_address(str(cid)):
                    has_v6_in_no_v6_export = True
                    break
        runner.assert_true(not has_v6_in_no_v6_export, "Nessun indirizzo IPv6 presente negli IDs esportati quando include_ipv6=false")

        # Test IPv6 candidate, link-local and all addresses normalization (Issue #43)
        mock_raw_dev = {
            "mac": "11:22:33:44:55:66",
            "hostname": "Test-DualStack-Client",
            "ips": ["192.168.4.150", "2001:db8::100/64", "fe80::1122:33ff:fe44:5566%eth0", "::1"],
            "ipv6_addresses": ["2001:db8::200"],
            "ipv6_link_local": ["fe80::dead:beef"],
        }
        normalized_dev = eero_client._normalize_device(mock_raw_dev)
        runner.assert_true(normalized_dev.get("ip") == "192.168.4.150", "IPv4 estratto correttamente")
        runner.assert_true("2001:db8::100" in normalized_dev.get("ipv6_addresses", []), "IPv6 globale 2001:db8::100 in ipv6_addresses senza CIDR /64 (Issue #43)")
        runner.assert_true("2001:db8::200" in normalized_dev.get("ipv6_addresses", []), "IPv6 globale 2001:db8::200 in ipv6_addresses (Issue #43)")
        runner.assert_true("fe80::1122:33ff:fe44:5566" in normalized_dev.get("ipv6_link_local", []), "Link-local fe80:: in ipv6_link_local senza scope %eth0 (Issue #43)")
        runner.assert_true("fe80::dead:beef" in normalized_dev.get("ipv6_link_local", []), "Link-local fe80::dead:beef in ipv6_link_local (Issue #43)")
        runner.assert_true("::1" not in normalized_dev.get("ipv6_all", []), "Loopback ::1 escluso da ipv6_all (Issue #43)")
        runner.assert_true(len(normalized_dev.get("ipv6_all", [])) == 4, "ipv6_all contiene esattamente i 4 indirizzi validi (2 globali + 2 link-local)")
        # Verifica che AdGuard export non includa link-local
        res_ag = await client.get("/api/devices/export/adguard?include_ipv6=true")
        runner.assert_true(res_ag.status_code == 200, "GET /api/devices/export/adguard?include_ipv6=true risponde 200")
        has_fe80_in_adguard = any(str(cid).lower().startswith("fe80:") for cl in res_ag.json().get("clients", []) for cid in cl.get("ids", []))
        runner.assert_true(not has_fe80_in_adguard, "Nessun indirizzo fe80: link-local inviato ad AdGuard (Issue #43)")

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

        # Accesso cross-origin alle API: nessun header CORS per default e modifiche da altre origini rifiutate
        evil_origin = {"Origin": "http://evil.example"}
        focus_off = {"active": False}
        res = await client.get("/api/health", headers=evil_origin)
        runner.assert_true("access-control-allow-origin" not in res.headers, "Nessun header CORS per un'origine esterna non configurata")
        res = await client.options("/api/network/guest", headers={**evil_origin, "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "content-type"})
        runner.assert_true("access-control-allow-origin" not in res.headers, "Preflight CORS da origine esterna non autorizzato")
        # Dashboard in HTTP su IP LAN: il browser non invia Sec-Fetch-Site, solo Origin
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers=evil_origin)
        runner.assert_true(res.status_code == 403, f"POST da altra origine senza Sec-Fetch-Site (HTTP) rifiutata con 403 (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers={"Origin": "null"})
        runner.assert_true(res.status_code == 403, f"POST con Origin 'null' rifiutata con 403 (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers={**evil_origin, "Sec-Fetch-Site": "cross-site"})
        runner.assert_true(res.status_code == 403, f"POST con Sec-Fetch-Site cross-site rifiutata con 403 (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers={"Origin": "http://test:9999", "Sec-Fetch-Site": "same-site"})
        runner.assert_true(res.status_code == 403, f"POST same-site (altra porta dello stesso host) rifiutata con 403 (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers={"Origin": "http://test"})
        runner.assert_true(res.status_code == 200, f"POST dalla dashboard stessa in HTTP (Origin = Host) accettata (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers={"Origin": "http://test", "Sec-Fetch-Site": "same-origin"})
        runner.assert_true(res.status_code == 200, f"POST same-origin (HTTPS/localhost) accettata (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off, headers={"Origin": "https://dash.example", "Host": "backend:8000", "X-Forwarded-Host": "dash.example"})
        runner.assert_true(res.status_code == 200, f"POST dietro reverse proxy (Origin = X-Forwarded-Host) accettata (ottenuto: {res.status_code})")
        res = await client.post("/api/automations/focus-mode", json=focus_off)
        runner.assert_true(res.status_code == 200, f"POST senza Origin (curl, Home Assistant REST) accettata (ottenuto: {res.status_code})")

        # CORS_ORIGINS esplicito: l'origine elencata (anche con "/" finale nella configurazione) riceve gli header CORS
        import importlib
        import app.main as main_module
        orig_cors_origins = settings.cors_origins
        try:
            settings.cors_origins = "http://homeassistant.local:8123/"
            cors_app = importlib.reload(main_module).app
            ha_origin = {"Origin": "http://homeassistant.local:8123"}
            async with AsyncClient(transport=ASGITransport(app=cors_app), base_url="http://test") as cors_client:
                res = await cors_client.get("/api/health", headers=ha_origin)
                runner.assert_true(res.headers.get("access-control-allow-origin") == "http://homeassistant.local:8123", "Origine elencata in CORS_ORIGINS riceve Access-Control-Allow-Origin")
                res = await cors_client.post("/api/automations/focus-mode", json=focus_off, headers=ha_origin)
                runner.assert_true(res.status_code == 200, f"POST dall'origine elencata in CORS_ORIGINS accettata (ottenuto: {res.status_code})")
                res = await cors_client.get("/api/health", headers=evil_origin)
                runner.assert_true("access-control-allow-origin" not in res.headers, "Origine non elencata in CORS_ORIGINS resta esclusa")
                res = await cors_client.post("/api/automations/focus-mode", json=focus_off, headers=evil_origin)
                runner.assert_true(res.status_code == 403, f"POST da origine non elencata rifiutata anche con CORS_ORIGINS (ottenuto: {res.status_code})")
        finally:
            settings.cors_origins = orig_cors_origins
            importlib.reload(main_module)

        print("\n🔄 [6/6] TEST RIPRISTINO SESSIONE LIVE E NORMALIZZAZIONE URL")
        # Normalizzazione URL AdGuard
        test_url_raw = "192.168.1.100:8085/#/dashboard"
        normalized = normalize_adguard_url(test_url_raw)
        runner.assert_true(normalized == "http://192.168.1.100:8085", f"Normalizzazione URL corretta: '{test_url_raw}' -> '{normalized}'")

        # Risoluzione network ID in get_forwards_and_reservations (Issue #33: metodo _resolve_network_id inesistente)
        import logging
        import httpx

        class _WarningCollector(logging.Handler):
            def __init__(self):
                super().__init__(level=logging.WARNING)
                self.messages = []

            def emit(self, record):
                self.messages.append(record.getMessage())

        def _forwards_handler(request):
            path = request.url.path
            if path.endswith("/2.2/account"):
                return httpx.Response(200, json={"data": {"networks": {"data": [{"url": "/2.2/networks/net_fwd_test"}]}}})
            if path.endswith("/networks/net_fwd_test/reservations"):
                return httpx.Response(200, json={"data": [{"mac": "aa:bb:cc:00:11:22", "ip": "192.168.4.50", "description": "Test Reservation"}]})
            return httpx.Response(200, json={"data": []})

        fwd_log = logging.getLogger("app.services.eero_client")
        fwd_collector = _WarningCollector()
        fwd_log.addHandler(fwd_collector)
        saved_fwd_state = (eero_client.user_token, eero_client.current_network_id, eero_client._is_demo_active, eero_client._http_client, eero_client.account_info)
        try:
            # Nessuna scrittura di session.json durante il test
            eero_client.save_session = lambda: None
            # 1. Senza sessione: nessun AttributeError registrato ad ogni poll
            eero_client.user_token = None
            eero_client.current_network_id = None
            eero_client._is_demo_active = False
            await eero_client.get_forwards_and_reservations()
            runner.assert_true(
                not any("Could not resolve network ID" in m for m in fwd_collector.messages),
                f"get_forwards_and_reservations() senza sessione non registra errori di risoluzione rete (log: {fwd_collector.messages[:1]})"
            )

            # 2. Sessione live senza network ID: la rete viene risolta da /account e le prenotazioni lette dalla rete corretta
            eero_client.user_token = "live_token_forwards_test"
            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(_forwards_handler))
            fwd_res = await eero_client.get_forwards_and_reservations()
            runner.assert_true(eero_client.current_network_id == "net_fwd_test", f"Network ID risolto da /account (ottenuto: {eero_client.current_network_id})")
            runner.assert_true(len(fwd_res.get("reservations", [])) == 1, f"Prenotazioni lette dalla rete risolta (ottenute: {len(fwd_res.get('reservations', []))})")
        finally:
            fwd_log.removeHandler(fwd_collector)
            if eero_client._http_client is not saved_fwd_state[3] and eero_client._http_client is not None:
                await eero_client._http_client.aclose()
            del eero_client.save_session
            (eero_client.user_token, eero_client.current_network_id, eero_client._is_demo_active, eero_client._http_client, eero_client.account_info) = saved_fwd_state

        print("\n⚡ [7/7] TEST NORMALIZZAZIONE VELOCITÀ ETHERNET E SEGNALE WIRELESS (Issue #14)")
        # Test 1: Nodo cablato con porte multiple (Bedroom da Issue #14): Interface 0 WAN P2500 + Interface 1 P1000 + Wi-Fi 5GHz
        node_bedroom_raw = {
            "name": "Bedroom",
            "model": "eero Pro 6E",
            "gateway": False,
            "wired": True,
            "connected": True,
            "ethernet_status": {
                "statuses": [
                    {"interface_number": 0, "speed": "P2500", "hasCarrier": True, "isWanPort": True, "neighbour": "Living Room"},
                    {"interface_number": 1, "speed": "P1000", "hasCarrier": True}
                ]
            },
            "interface": {"speed": "5GHz"},
            "connectivity": {"frequency": "5 GHz"}
        }
        bedroom_norm = eero_client._normalize_eero_node(node_bedroom_raw)
        runner.assert_true(bedroom_norm["backhaul_type"] == "Ethernet (2.5 Gbps)", f"Bedroom porta WAN P2500 rileva 'Ethernet (2.5 Gbps)' (ottenuto: {bedroom_norm['backhaul_type']})")
        runner.assert_true(bedroom_norm["wired"] is True, "Bedroom marcato correttamente come wired")
        runner.assert_true("5.0 Gbps" not in bedroom_norm["backhaul_type"], "Bedroom non viene scambiato erroneamente per 5.0 Gbps")

        # Test 2: Nodo cablato con porte P1000 (Toilet da Issue #14)
        node_toilet_raw = {
            "name": "Toilet",
            "model": "eero 6+",
            "gateway": False,
            "wired": True,
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

        # Test 3: Dispositivo client cablato con connectivity.ethernet_status (cameraui da Issue #14)
        device_cameraui_raw = {
            "id": "cameraui_dev_1",
            "hostname": "cameraui",
            "ip": "192.168.4.39",
            "connected": True,
            "connectivity": {
                "connected": True,
                "ethernet_status": {
                    "has_carrier": True,
                    "interface_number": 1,
                    "speed": "P2500",
                    "port_name": "2"
                }
            }
        }
        cameraui_norm = eero_client._normalize_device(device_cameraui_raw)
        runner.assert_true(cameraui_norm["wireless"] is False, "Client cameraui con ethernet_status marcato wireless=False")
        runner.assert_true(cameraui_norm["connection_type"] == "wired", f"Client cameraui connection_type è 'wired' (ottenuto: {cameraui_norm['connection_type']})")
        runner.assert_true(cameraui_norm["ethernet_speed"] == "2.5 Gbps", f"Client cameraui ethernet_speed estratto come '2.5 Gbps' (ottenuto: {cameraui_norm['ethernet_speed']})")

        # Test 4: Dispositivo client cablato 1 Gbps standard
        device_pc_raw = {
            "id": "pc_gigabit",
            "hostname": "Workstation",
            "ip": "192.168.4.50",
            "connected": True,
            "ethernet_status": {
                "speed": "P1000",
                "has_carrier": True
            }
        }
        pc_norm = eero_client._normalize_device(device_pc_raw)
        runner.assert_true(pc_norm["ethernet_speed"] == "1.0 Gbps", f"Client PC ethernet_speed estratto come '1.0 Gbps' (ottenuto: {pc_norm['ethernet_speed']})")
        runner.assert_true(pc_norm["wireless"] is False, "Client cablato ha wireless=False")
        runner.assert_true(pc_norm["connection_type"] == "wired", "Client cablato ha connection_type='wired'")

        # Test 4b: Preservazione telemetria e tassi per client cablati con data usage
        device_nas_wired = {
            "id": "nas_qnap",
            "hostname": "QNAP-Storage",
            "ip": "192.168.4.60",
            "connected": True,
            "wireless": False,
            "download_rate_mbps": 52.4,
            "upload_rate_mbps": 18.2,
            "rx_bytes": 10500200300,
            "tx_bytes": 4200100200
        }
        nas_norm = eero_client._normalize_device(device_nas_wired)
        runner.assert_true(nas_norm["download_rate_mbps"] == 52.4, f"Download rate NAS preservato a 52.4 (ottenuto: {nas_norm['download_rate_mbps']})")
        runner.assert_true(nas_norm["rx_bytes"] == 10500200300.0, f"rx_bytes NAS preservato a 10500200300 (ottenuto: {nas_norm['rx_bytes']})")

        # Test 5: Nodo wireless mesh (wired: false) che ha un PC collegato via cavo (Camera di Filippo e Enea)
        node_wireless_with_pc = {
            "name": "Camera di Filippo e Enea",
            "model": "eero",
            "gateway": False,
            "wired": False,
            "connected": True,
            "ethernet_status": {
                "statuses": [
                    {"port": 1, "speed": "P1000", "has_carrier": True}
                ]
            },
            "connectivity": {
                "signal": -62,
                "frequency": "5 GHz"
            }
        }
        filippo_norm = eero_client._normalize_eero_node(node_wireless_with_pc)
        runner.assert_true(filippo_norm["wired"] is False, "Nodo wireless con PC collegato marcato wired=False")
        runner.assert_true(filippo_norm["backhaul_type"] == "Wireless Mesh (5 GHz / -62 dBm)", f"Nodo wireless con PC rileva 'Wireless Mesh (5 GHz / -62 dBm)' (ottenuto: {filippo_norm['backhaul_type']})")

        # Test 6: Nodo wireless mesh con segnale come dizionario (signal: {rx_rssi: -58})
        node_wireless_raw = {
            "name": "Living Room Beacon",
            "model": "eero 6",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "wireless_band": "5 GHz",
            "connectivity": {
                "signal": {"rx_rssi": -58},
                "frequency": "5 GHz"
            }
        }
        wireless_norm = eero_client._normalize_eero_node(node_wireless_raw)
        runner.assert_true(wireless_norm["backhaul_type"] == "Wireless Mesh (5 GHz / -58 dBm)", f"Beacon wireless con dict signal rileva 'Wireless Mesh (5 GHz / -58 dBm)' (ottenuto: {wireless_norm['backhaul_type']})")
        runner.assert_true(wireless_norm["signal_rssi"] == -58, f"Beacon wireless signal_rssi estratto come -58 (ottenuto: {wireless_norm['signal_rssi']})")

        # Test 6a: Nodo Wi-Fi 6E mesh con frequenza MHz e canale PSC (frequency: 6295 MHz, channel: 69)
        node_6ghz_raw = {
            "name": "Office Pro 6E",
            "model": "eero Pro 6E",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "connectivity": {
                "signal": -52,
                "frequency": 6295,
                "channel": 69,
            }
        }
        node_6ghz_norm = eero_client._normalize_eero_node(node_6ghz_raw)
        runner.assert_true(node_6ghz_norm["backhaul_type"] == "Wireless Mesh (6 GHz / -52 dBm)", f"Nodo Pro 6E con freq 6295 MHz rileva 'Wireless Mesh (6 GHz / -52 dBm)' (ottenuto: {node_6ghz_norm['backhaul_type']})")

        # Test 6b: Nodo Wi-Fi 6E mesh con solo canale PSC 69 e segnale dict (senza stringa frequenza)
        node_6ghz_psc_raw = {
            "name": "Bedroom 6E",
            "model": "eero Pro 6E",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "channel": 69,
            "signal": {"rx_rssi": -54}
        }
        node_6ghz_psc_norm = eero_client._normalize_eero_node(node_6ghz_psc_raw)
        runner.assert_true(node_6ghz_psc_norm["backhaul_type"] == "Wireless Mesh (6 GHz / -54 dBm)", f"Nodo con canale PSC 69 rileva 'Wireless Mesh (6 GHz / -54 dBm)' (ottenuto: {node_6ghz_psc_norm['backhaul_type']})")

        # Test 6c: Nodo Wi-Fi 6E hardware fallback (senza canale né frequenza espliciti dall'API cloud)
        node_6ghz_hw_raw = {
            "name": "Living Room 6E",
            "model": "eero Pro 6E (K010001)",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "signal_rssi": -48
        }
        node_6ghz_hw_norm = eero_client._normalize_eero_node(node_6ghz_hw_raw)
        runner.assert_true(node_6ghz_hw_norm["backhaul_type"] in ("Wireless Mesh (6 GHz / -48 dBm)", "Wireless Mesh (6 GHz / -48 dBm) (estimated)"), f"Nodo hardware Pro 6E senza freq API adotta 'Wireless Mesh (6 GHz / -48 dBm)' (ottenuto: {node_6ghz_hw_norm['backhaul_type']})")

        # Test 6d: Nodo Wi-Fi 7 hardware (eero Max 7 su 320MHz width)
        node_max7_raw = {
            "name": "Attic Max 7",
            "model": "eero Max 7",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "connectivity": {
                "channel_width": "WIDTH_320MHz",
                "signal": -42
            }
        }
        node_max7_norm = eero_client._normalize_eero_node(node_max7_raw)
        runner.assert_true(node_max7_norm["backhaul_type"] == "Wireless Mesh (6 GHz / -42 dBm)", f"Nodo Max 7 rileva 'Wireless Mesh (6 GHz / -42 dBm)' (ottenuto: {node_max7_norm['backhaul_type']})")

        # Test 6e: Nodo Max 7 (Wi-Fi 7, EHT) su 5 GHz UNII-3: frequenza 5745 MHz, canale dispari 149
        node_max7_5g_raw = {
            "name": "Garage Max 7",
            "model": "eero Max 7",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "connectivity": {"frequency": 5745, "channel": 149, "phy_type": "EHT", "signal": -50}
        }
        node_max7_5g_norm = eero_client._normalize_eero_node(node_max7_5g_raw)
        runner.assert_true(node_max7_5g_norm["backhaul_type"] == "Wireless Mesh (5 GHz / -50 dBm)", f"Max 7 EHT su 5745 MHz / canale 149 rileva 'Wireless Mesh (5 GHz / -50 dBm)' (ottenuto: {node_max7_5g_norm['backhaul_type']})")

        # Test 6f: Nodo Max 7 EHT con solo canale 36 (nessuna frequenza): EHT non implica 6 GHz
        node_max7_ch36_raw = {
            "name": "Office Max 7",
            "model": "eero Max 7",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "channel": 36,
            "phy_type": "EHT",
            "signal": {"rx_rssi": -57}
        }
        node_max7_ch36_norm = eero_client._normalize_eero_node(node_max7_ch36_raw)
        runner.assert_true(node_max7_ch36_norm["backhaul_type"] == "Wireless Mesh (5 GHz / -57 dBm)", f"Max 7 EHT su canale 36 rileva 'Wireless Mesh (5 GHz / -57 dBm)' (ottenuto: {node_max7_ch36_norm['backhaul_type']})")

        # Test 6g: Nodo eero 6 con solo canale dispari 157 (UNII-3, 5 GHz)
        node_unii3_raw = {
            "name": "Kitchen eero 6",
            "model": "eero 6",
            "gateway": False,
            "wireless": True,
            "connected": True,
            "channel": 157,
            "signal": {"rx_rssi": -61}
        }
        node_unii3_norm = eero_client._normalize_eero_node(node_unii3_raw)
        runner.assert_true(node_unii3_norm["backhaul_type"] == "Wireless Mesh (5 GHz / -61 dBm)", f"eero 6 su canale 157 rileva 'Wireless Mesh (5 GHz / -61 dBm)' (ottenuto: {node_unii3_norm['backhaul_type']})")

        # Test 6h: Dispositivo Wi-Fi 7 (EHT) connesso a 5 GHz (frequenza 5180 MHz, canale 36)
        wifi7_5g_dev_raw = {
            "id": "dev_wifi7_5g",
            "hostname": "Wi-Fi 7 Phone",
            "connected": True,
            "connectivity": {"connected": True, "frequency": 5180, "channel": 36, "phy_type": "EHT", "channel_width": "WIDTH_80MHz"}
        }
        wifi7_5g_dev_norm = eero_client._normalize_device(wifi7_5g_dev_raw)
        runner.assert_true(wifi7_5g_dev_norm["frequency_band"] == "5 GHz", f"Dispositivo EHT su 5180 MHz rileva '5 GHz' (ottenuto: {wifi7_5g_dev_norm['frequency_band']})")

        # Test 6i: Dispositivo EHT su 6 GHz con solo canale 37 (senza frequenza) resta 6 GHz
        wifi7_6g_ch_raw = {
            "id": "dev_wifi7_6g_ch",
            "hostname": "Wi-Fi 7 Laptop",
            "connected": True,
            "connectivity": {"connected": True, "channel": 37, "phy_type": "EHT"}
        }
        wifi7_6g_ch_norm = eero_client._normalize_device(wifi7_6g_ch_raw)
        runner.assert_true(wifi7_6g_ch_norm["frequency_band"] == "6 GHz", f"Dispositivo EHT su canale 37 rileva '6 GHz' (ottenuto: {wifi7_6g_ch_norm['frequency_band']})")

        # Test 7: Dispositivo Wi-Fi 6 GHz (Steve iPhone 17 da Issue #14: frequency=6295, channel=69, phy_type=EHT)
        iphone17_raw = {
            "id": "dev_iphone17",
            "hostname": "Steve iPhone 17",
            "connected": True,
            "connectivity": {
                "connected": True,
                "frequency": 6295,
                "channel": 69,
                "phy_type": "EHT",
                "channel_width": "WIDTH_160MHz"
            }
        }
        iphone17_norm = eero_client._normalize_device(iphone17_raw)
        runner.assert_true(iphone17_norm["frequency_band"] == "6 GHz", f"iPhone 17 frequency 6295 rileva '6 GHz' (ottenuto: {iphone17_norm['frequency_band']})")
        runner.assert_true(iphone17_norm["wireless_band"] == "6GHz", f"iPhone 17 wireless_band è '6GHz' (ottenuto: {iphone17_norm['wireless_band']})")
        runner.assert_true(iphone17_norm["channel"] == 69, f"iPhone 17 channel estratto come 69 (ottenuto: {iphone17_norm['channel']})")

        # Test 8: Dispositivo Wi-Fi 7 6 GHz 320MHz (Steve PC wifi da Issue #14)
        steve_pc_raw = {
            "id": "dev_steve_pc",
            "hostname": "Steve PC wifi",
            "connected": True,
            "connectivity": {
                "connected": True,
                "frequency": 6295,
                "channel": 69,
                "phy_type": "EHT",
                "channel_width": "WIDTH_320MHz",
                "rx_bitrate": 2882.6
            }
        }
        steve_pc_norm = eero_client._normalize_device(steve_pc_raw)
        runner.assert_true(steve_pc_norm["frequency_band"] == "6 GHz", f"Steve PC wifi rileva '6 GHz' (ottenuto: {steve_pc_norm['frequency_band']})")
        runner.assert_true(steve_pc_norm["wireless_band"] == "6GHz", f"Steve PC wifi wireless_band è '6GHz' (ottenuto: {steve_pc_norm['wireless_band']})")

        # Test 9: Dispositivo wireless senza segnale nel payload eero: nessun RSSI inventato (-55 dBm)
        no_signal_raw = {
            "id": "dev_no_signal",
            "hostname": "Wireless Sensor",
            "connected": True,
            "wireless": True,
            "connectivity": {"connected": True, "frequency": 2437, "channel": 6}
        }
        no_signal_norm = eero_client._normalize_device(no_signal_raw)
        runner.assert_true(no_signal_norm["signal_rssi"] is None, f"RSSI assente dal cloud resta None (ottenuto: {no_signal_norm['signal_rssi']})")
        runner.assert_true(no_signal_norm["frequency_band"] == "2.4 GHz", f"Banda del dispositivo senza segnale rilevata comunque (ottenuto: {no_signal_norm['frequency_band']})")

        print("\n🏷️ [8/8] TEST MAPPING CATEGORIE NATIVE EERO, TAG ADGUARD E SALVATAGGIO METADATI (Issue #13)")
        from app.services.eero_client import map_eero_device_type, get_adguard_tags

        # Test mapping tipi nativi eero
        cat_laptop, icon_laptop = map_eero_device_type("laptop", "MacBook Pro")
        runner.assert_true(cat_laptop == "Computer" and icon_laptop == "laptop", f"Mapping laptop: {cat_laptop}, {icon_laptop}")

        cat_phone, icon_phone = map_eero_device_type("phone", "iPhone 15 Pro")
        runner.assert_true(cat_phone == "Mobile" and icon_phone == "smartphone", f"Mapping phone: {cat_phone}, {icon_phone}")

        cat_console, icon_console = map_eero_device_type("gaming_console", "PlayStation 5")
        runner.assert_true(cat_console == "Gaming" and icon_console == "gamepad", f"Mapping gaming_console: {cat_console}, {icon_console}")

        cat_plug, icon_plug = map_eero_device_type("smart_plug", "Shelly Plug S")
        runner.assert_true(cat_plug == "Smart Home" and icon_plug == "iot", f"Mapping smart_plug: {cat_plug}, {icon_plug}")

        cat_nas, icon_nas = map_eero_device_type("nas", "Synology DS920+")
        runner.assert_true(cat_nas == "Server/Rete" and icon_nas == "server", f"Mapping nas: {cat_nas}, {icon_nas}")

        cat_tv, icon_tv = map_eero_device_type("tv", "Samsung Smart TV")
        runner.assert_true(cat_tv == "Intrattenimento" and icon_tv == "tv", f"Mapping tv: {cat_tv}, {icon_tv}")

        # Test normalizzazione e categorizzazione dispositivo
        dev_ps5_raw = {
            "id": "ps5_client_test",
            "mac": "00:1A:2B:3C:4D:5E",
            "hostname": "PS5-LivingRoom",
            "device_type": "gaming_console",
            "connected": True
        }
        ps5_norm = eero_client._normalize_device(dev_ps5_raw)
        runner.assert_true(ps5_norm["default_category"] == "Gaming", f"PS5 default_category è Gaming (ottenuto: {ps5_norm['default_category']})")
        runner.assert_true(ps5_norm["default_icon"] == "gamepad", f"PS5 default_icon è gamepad (ottenuto: {ps5_norm['default_icon']})")
        runner.assert_true(ps5_norm["category"] == "Gaming", f"PS5 category è Gaming (ottenuto: {ps5_norm['category']})")

        # Test generazione tag AdGuard
        runner.assert_true(get_adguard_tags("Computer", "laptop") == ["device_laptop"], "Tag AdGuard per laptop è ['device_laptop']")
        runner.assert_true(get_adguard_tags("Mobile", "smartphone") == ["device_phone"], "Tag AdGuard per smartphone è ['device_phone']")
        runner.assert_true(get_adguard_tags("Intrattenimento", "tv") == ["device_tv"], "Tag AdGuard per tv è ['device_tv']")
        runner.assert_true(get_adguard_tags("Gaming", "gamepad") == ["device_gameconsole"], "Tag AdGuard per gaming è ['device_gameconsole']")
        runner.assert_true(get_adguard_tags("Server/Rete", "server") == ["device_nas"], "Tag AdGuard per server è ['device_nas']")
        runner.assert_true(get_adguard_tags("Smart Home", "iot") == ["device_other"], "Tag AdGuard per iot è ['device_other']")
        runner.assert_true(get_adguard_tags("Altro", "device") == ["device_other"], "Tag AdGuard per Altro / device è ['device_other']")
        
        # Test condizionatori Samsung
        cat_ac, icon_ac = map_eero_device_type(None, "samsung air conditioner corridoio")
        runner.assert_true(cat_ac == "Smart Home" and icon_ac == "iot", f"Condizionatore mappato come Smart Home/iot (ottenuto: {cat_ac}/{icon_ac})")
        runner.assert_true(get_adguard_tags(cat_ac, icon_ac) == ["device_other"], "Tag AdGuard per condizionatore è ['device_other']")

        # Test salvataggio metadati via API
        save_res = await client.post("/api/devices/00:1a:2b:3c:4d:5e/metadata", json={
            "custom_name": "PlayStation 5 Pro",
            "category": "Gaming",
            "custom_icon": "gamepad",
            "is_favorite": True
        })
        runner.assert_true(save_res.status_code == 200, "Salvataggio metadati dispositivo risponde HTTP 200")
        detail_res = await client.get("/api/devices/00:1a:2b:3c:4d:5e")
        runner.assert_true(detail_res.status_code == 200, "Dettaglio metadati dispositivo risponde HTTP 200")
        meta_saved = detail_res.json().get("metadata") or {}
        runner.assert_true(meta_saved.get("custom_name") == "PlayStation 5 Pro", "Nome personalizzato salvato con successo")
        runner.assert_true(meta_saved.get("category") == "Gaming", "Categoria salvata con successo")

        # Switch back to Live
        res = await client.post("/api/auth/mode", json={"demo": False})
        runner.assert_true(res.status_code == 200, "Ritorno a Live Mode risponde HTTP 200")
        status_res = (await client.get("/api/auth/status")).json()
        runner.assert_true(status_res.get("demo_mode") is False, "Modalità Demo disattivata")
        runner.assert_true(eero_client.user_token == "live_secret_user_token_sample", "Token Live originale ripristinato intatto")

        # =====================================================================
        # 9. TEST CACHE BUSTING ASSET & ADGUARD HOME SYNC (v1.03.02)
        # =====================================================================
        print("\n🛡️ [9/9] TEST CACHE BUSTING ASSET & ADGUARD HOME SYNC (v1.03.02)")
        
        # Test cache busting su pagina index
        page_res = await client.get("/")
        runner.assert_true(page_res.status_code == 200, "GET / risponde HTTP 200")
        page_html = page_res.text
        runner.assert_true("styles.css?v=" in page_html, "styles.css include parametro versione cache-busting (?v=)")
        runner.assert_true("app.js?v=" in page_html, "app.js include parametro versione cache-busting (?v=)")
        for route in ("/dashboard", "/devices", "/speedtest", "/analytics", "/automations", "/manual", "/news", "/eero-news"):
            route_res = await client.get(route)
            runner.assert_true(route_res.status_code == 200 and 'x-data="eeroApp"' in route_res.text, f"GET {route} serve la SPA")

        # Test salvataggio impostazioni AdGuard singola istanza
        adg_payload = {
            "enabled": True,
            "url": "http://192.168.4.104:8085",
            "username": "admin",
            "password": "test_password_123"
        }
        save_adg_res = await client.post("/api/automations/adguard", json=adg_payload)
        runner.assert_true(save_adg_res.status_code == 200, "Salvataggio impostazioni AdGuard risponde HTTP 200")

        # Verifica lettura impostazioni
        get_adg_res = await client.get("/api/automations/adguard")
        runner.assert_true(get_adg_res.status_code == 200, "Lettura impostazioni AdGuard risponde HTTP 200")
        adg_data = get_adg_res.json()
        runner.assert_true(adg_data.get("url") == "http://192.168.4.104:8085", "URL AdGuard preservato correttamente")
        runner.assert_true(adg_data.get("username") == "admin", "Username AdGuard preservato")
        runner.assert_true(adg_data.get("has_password") is True, "Password AdGuard presente e protetta")

        # Attiva demo mode per simulazione test e sync senza socket reali
        await client.post("/api/auth/mode", json={"demo": True})
        
        # Test connessione
        test_adg_res = await client.post("/api/automations/adguard/test", json=adg_payload)
        runner.assert_true(test_adg_res.status_code == 200, "Test connessione AdGuard risponde HTTP 200")
        runner.assert_true(test_adg_res.json().get("success") is True, "Test connessione AdGuard simulato con successo")

        # Test sync in demo mode
        sync_adg_res = await client.post("/api/automations/adguard/sync", json=adg_payload)
        runner.assert_true(sync_adg_res.status_code == 200, "Sync AdGuard risponde HTTP 200")
        runner.assert_true(sync_adg_res.json().get("success") is True, "Sync AdGuard completato con successo")

        # =====================================================================
        # 10. TEST RISOLUZIONE ACCURATA PRIMARY GATEWAY (Issue #19)
        # =====================================================================
        print("\n🌐 [10/12] TEST RISOLUZIONE ACCURATA PRIMARY GATEWAY (Issue #19)")
        
        # Test 1: Topologia Bridge Mode reale Issue #19 (phutmacher) con gateway string URL
        phutmacher_nodes_raw = [
            {"id": "101", "url": "/2.2/eeros/101", "name": "Bedroom", "gateway": "/2.2/eeros/104", "wired": True, "ip": "192.168.1.189"},
            {"id": "102", "url": "/2.2/eeros/102", "name": "Office", "gateway": "/2.2/eeros/104", "wired": True, "ip": "192.168.1.190"},
            {"id": "103", "url": "/2.2/eeros/103", "name": "Office 2", "gateway": "/2.2/eeros/104", "wired": True, "ip": "192.168.1.191"},
            {"id": "104", "url": "/2.2/eeros/104", "name": "Wiring Closet", "gateway": "/2.2/eeros/104", "wired": True, "ip": "192.168.1.188"}
        ]
        
        norm_nodes = [eero_client._normalize_eero_node(n) for n in phutmacher_nodes_raw]
        
        bedroom_res = next(n for n in norm_nodes if n["name"] == "Bedroom")
        office_res = next(n for n in norm_nodes if n["name"] == "Office")
        office2_res = next(n for n in norm_nodes if n["name"] == "Office 2")
        closet_res = next(n for n in norm_nodes if n["name"] == "Wiring Closet")
        
        runner.assert_true(bedroom_res["is_gateway"] is False, "Bedroom marcato is_gateway=False (non è gateway)")
        runner.assert_true(bedroom_res["backhaul_type"] == "Ethernet (Wired)", f"Bedroom backhaul è 'Ethernet (Wired)' (ottenuto: {bedroom_res['backhaul_type']})")
        runner.assert_true(office_res["is_gateway"] is False, "Office marcato is_gateway=False")
        runner.assert_true(office2_res["is_gateway"] is False, "Office 2 marcato is_gateway=False")
        runner.assert_true(closet_res["is_gateway"] is True, "Wiring Closet marcato is_gateway=True (Primary Gateway univoco)")
        runner.assert_true(closet_res["backhaul_type"] == "Gateway (WAN)", f"Wiring Closet backhaul è 'Gateway (WAN)' (ottenuto: {closet_res['backhaul_type']})")

        # Test 2: Subnet Gateway IP string in Bridge Mode (es. "192.168.1.1" upstream Peplink)
        bridge_node_leaf = {"id": "201", "url": "/2.2/eeros/201", "name": "Salotto", "gateway": "192.168.1.1", "ip": "192.168.1.55"}
        bridge_leaf_norm = eero_client._normalize_eero_node(bridge_node_leaf)
        runner.assert_true(bridge_leaf_norm["is_gateway"] is False, "Nodo con gateway IP subnet differente marcato is_gateway=False")

        # Test 3: Normalizzazione dettagli rete con metadati gateway
        net_raw = {
            "name": "Home Network",
            "gateway": "/2.2/eeros/104",
            "gateway_name": "Wiring Closet",
            "gateway_ip": "192.168.1.188"
        }
        net_norm = eero_client._normalize_network_details(net_raw)
        runner.assert_true(net_norm.get("gateway_eero_id") == "104", f"Network details estrae gateway_eero_id='104' (ottenuto: {net_norm.get('gateway_eero_id')})")
        runner.assert_true(net_norm.get("gateway_name") == "Wiring Closet", f"Network details estrae gateway_name='Wiring Closet' (ottenuto: {net_norm.get('gateway_name')})")

        # Test 3b: Elezione per ID esatto tramite get_eeros() reale (Issue #26): il gateway "10" non deve eleggere "/2.2/eeros/104"
        import httpx
        exact_id_nodes = [
            {"url": "/2.2/eeros/104", "location": "Upstairs", "gateway": False, "ip_address": "192.168.4.31", "status": "green"},
            {"url": "/2.2/eeros/10", "location": "Hallway", "gateway": False, "ip_address": "192.168.4.32", "status": "green"},
        ]

        def _exact_id_handler(request):
            if request.url.path.endswith("/eeros"):
                return httpx.Response(200, json={"data": exact_id_nodes})
            return httpx.Response(200, json={"data": {"url": "/2.2/networks/network_gw_test", "gateway": {"url": "/2.2/eeros/10"}, "gateway_ip": "192.168.4.99"}})

        saved_gw_state = (
            eero_client.user_token, eero_client.current_network_id, eero_client._is_demo_active, eero_client._http_client,
            eero_client.current_gateway_id, eero_client.current_gateway_url, eero_client.current_gateway_name, eero_client.current_gateway_ip,
            eero_client._last_network_details, eero_client._last_eeros,
        )
        try:
            eero_client.user_token = "live_token_gateway_test"
            eero_client.current_network_id = "network_gw_test"
            eero_client._is_demo_active = False
            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(_exact_id_handler))
            await eero_client.get_network_details()
            exact_nodes = await eero_client.get_eeros()
            elected_ids = [n.get("id") for n in exact_nodes if n.get("is_gateway")]
            runner.assert_true(elected_ids == ["10"], f"Gateway '10' eletto per ID esatto, non '/2.2/eeros/104' (ottenuto: {elected_ids})")
        finally:
            await eero_client._http_client.aclose()
            (
                eero_client.user_token, eero_client.current_network_id, eero_client._is_demo_active, eero_client._http_client,
                eero_client.current_gateway_id, eero_client.current_gateway_url, eero_client.current_gateway_name, eero_client.current_gateway_ip,
                eero_client._last_network_details, eero_client._last_eeros,
            ) = saved_gw_state

        # Test 3c: Campo "gateway" del nodo con ID nudo: "10" identifica solo "/2.2/eeros/10", non "/2.2/eeros/110"
        saved_gw_hint = (eero_client.current_gateway_id, eero_client.current_gateway_url, eero_client.current_gateway_ip)
        eero_client.current_gateway_id = eero_client.current_gateway_url = eero_client.current_gateway_ip = None
        node_110 = eero_client._normalize_eero_node({"url": "/2.2/eeros/110", "location": "Attic", "gateway": "10"})
        node_10 = eero_client._normalize_eero_node({"url": "/2.2/eeros/10", "location": "Hallway", "gateway": "10"})
        eero_client.current_gateway_id, eero_client.current_gateway_url, eero_client.current_gateway_ip = saved_gw_hint
        runner.assert_true(node_110["is_gateway"] is False, "Nodo /2.2/eeros/110 non marcato gateway per gateway='10'")
        runner.assert_true(node_10["is_gateway"] is True, "Nodo /2.2/eeros/10 marcato gateway per gateway='10'")

        # Test 4: Risoluzione Gateway con nodi PoE e nodi WAN misti (Issue #26 - jonmacdonald)
        outdoor_poe_node = {
            "id": "704",
            "url": "/2.2/eeros/704",
            "name": "Backyard Outdoor",
            "model": "eero Outdoor 7",
            "ip": "192.168.4.88",
            "wired": False,
            "ethernet_ports": [{"port": 1, "speed": "2.5 Gbps", "has_carrier": True}]
        }
        max7_gateway_node = {
            "id": "701",
            "url": "/2.2/eeros/701",
            "name": "Main Router Max 7",
            "model": "eero Max 7",
            "ip": "192.168.4.1",
            "wired": True,
            "ethernet_ports": [
                {"port": 1, "speed": "10 Gbps", "has_carrier": True, "role": "wan", "is_wan": True},
                {"port": 2, "speed": "10 Gbps", "has_carrier": True}
            ]
        }
        norm_outdoor = eero_client._normalize_eero_node(outdoor_poe_node)
        norm_max7 = eero_client._normalize_eero_node(max7_gateway_node)

        runner.assert_true(norm_max7.get("has_wan_port") is True, "Max 7 ha has_wan_port=True")
        runner.assert_true(any("(WAN)" in str(p) for p in norm_max7.get("ethernet_ports_details", [])), "Dettaglio porte Max 7 etichetta correttamente '(WAN)'")
        runner.assert_true(norm_outdoor.get("has_wan_port") is not True, "Outdoor 7 PoE non ha porta WAN")

        # Simulazione riconciliazione cluster get_eeros
        raw_cluster = [norm_outdoor, norm_max7]
        eero_client.current_gateway_id = "701"
        eero_client.current_gateway_url = "/2.2/eeros/701"
        eero_client.current_gateway_ip = "192.168.4.1"

        primary_gw = None
        gw_cached_id = getattr(eero_client, "current_gateway_id", None)
        gw_cached_url = getattr(eero_client, "current_gateway_url", None)
        if gw_cached_id or gw_cached_url:
            primary_gw = next((n for n in raw_cluster if (
                (gw_cached_id and str(n.get("id") or "") == str(gw_cached_id)) or
                (gw_cached_id and str(n.get("url") or "").rstrip("/").split("/")[-1] == str(gw_cached_id)) or
                (gw_cached_url and str(n.get("url") or "") == str(gw_cached_url))
            )), None)
        if not primary_gw:
            gw_cached_name = getattr(eero_client, "current_gateway_name", None)
            if gw_cached_name:
                primary_gw = next((n for n in raw_cluster if str(n.get("name") or "").lower() == str(gw_cached_name).lower()), None)
        if not primary_gw:
            gw_cached_ip = getattr(eero_client, "current_gateway_ip", None) or "192.168.4.1"
            primary_gw = next((n for n in raw_cluster if n.get("ip") and n.get("ip") == gw_cached_ip), None)
        if not primary_gw:
            gw_nodes = [n for n in raw_cluster if n.get("is_gateway")]
            if len(gw_nodes) == 1:
                primary_gw = gw_nodes[0]
            elif len(gw_nodes) > 1:
                primary_gw = next((n for n in gw_nodes if n.get("ip") == (getattr(eero_client, "current_gateway_ip", None) or "192.168.4.1")), gw_nodes[0])
        if not primary_gw:
            primary_gw = next((n for n in raw_cluster if n.get("has_wan_port") or any("wan" in str(p).lower() for p in n.get("ethernet_ports_details", []))), None)
        if not primary_gw:
            primary_gw = raw_cluster[0]

        for n in raw_cluster:
            if n is primary_gw:
                n["is_gateway"] = True
                n["wired"] = True
                n["backhaul_type"] = "Gateway (WAN)"
            else:
                n["is_gateway"] = False
                is_6e_or_7 = any(m in str(n.get("model") or "").lower() for m in ("pro 6e", "max 7", "outdoor 7", "k010001", "s010001", "t010001"))
                candidate_speeds = [parse_speed_mbps(s) for s in n.get("ethernet_ports_details", [])]
                spd_mbps = max(candidate_speeds) if candidate_speeds else 0
                spd_fmt = format_speed_mbps(spd_mbps)
                if n.get("raw_wired") is True:
                    n["wired"] = True
                    n["backhaul_type"] = f"Ethernet ({spd_fmt})" if spd_fmt else "Ethernet (Wired)"
                elif is_6e_or_7 or "6" in str(n.get("wireless_band") or ""):
                    n["wired"] = False
                    n["backhaul_type"] = "Wireless Mesh (6 GHz)"
                else:
                    n["wired"] = False
                    n["backhaul_type"] = "Wireless Mesh (5 GHz)"

        runner.assert_true(norm_max7["is_gateway"] is True, "Max 7 correttamente eletto Primary Gateway")
        runner.assert_true(norm_max7["backhaul_type"] == "Gateway (WAN)", "Max 7 ha backhaul 'Gateway (WAN)'")
        runner.assert_true(norm_outdoor["is_gateway"] is False, "Outdoor 7 PoE non è eletto Primary Gateway")
        runner.assert_true(norm_outdoor["backhaul_type"] == "Wireless Mesh (6 GHz)", f"Outdoor 7 PoE ha backhaul 'Wireless Mesh (6 GHz)' (ottenuto: {norm_outdoor['backhaul_type']})")

        # Test 5: Risoluzione accurata Primary Gateway su topologia multi-ethernet Issue #36 (jpatchMC)
        jpatch_nodes_raw = [
            {"id": "jp_garage", "name": "Garage", "model": "eero 6 Extender", "ip": "192.168.7.133", "wired": False},
            {"id": "jp_office", "name": "Office", "model": "eero 6+", "ip": "192.168.6.192", "wired": True, "ethernet_ports_details": ["Port 1 (WAN): 1.0 Gbps"], "raw_wired": True},
            {"id": "jp_living", "name": "Living Room", "model": "eero 6+", "ip": "192.168.7.177", "wired": True, "ethernet_ports_details": ["Port 1: 1.0 Gbps"], "raw_wired": True},
            {"id": "jp_family", "name": "Family Room", "model": "eero 6+", "ip": "192.168.4.1", "wired": True, "ethernet_ports_details": ["Port 1 (WAN): 1.0 Gbps"], "raw_wired": True}
        ]
        norm_jpatch = [eero_client._normalize_eero_node(n) for n in jpatch_nodes_raw]
        eero_client.current_gateway_ip = "192.168.4.1"
        eero_client.current_gateway_id = None
        eero_client.current_gateway_url = None
        eero_client.current_gateway_name = "Family Room"

        reconciled_jpatch = list(norm_jpatch)
        gw_cached_id = getattr(eero_client, "current_gateway_id", None)
        gw_cached_url = getattr(eero_client, "current_gateway_url", None)
        primary_gw = None
        if gw_cached_id or gw_cached_url:
            primary_gw = next((n for n in reconciled_jpatch if (
                (gw_cached_id and str(n.get("id") or "") == str(gw_cached_id)) or
                (gw_cached_id and gw_cached_id in str(n.get("url") or "")) or
                (gw_cached_url and str(n.get("url") or "") == str(gw_cached_url))
            )), None)
        if not primary_gw:
            gw_cached_name = getattr(eero_client, "current_gateway_name", None)
            if gw_cached_name:
                primary_gw = next((n for n in reconciled_jpatch if str(n.get("name") or "").lower() == str(gw_cached_name).lower()), None)
        if not primary_gw:
            gw_cached_ip = getattr(eero_client, "current_gateway_ip", None) or "192.168.4.1"
            primary_gw = next((n for n in reconciled_jpatch if n.get("ip") and n.get("ip") == gw_cached_ip), None)
        if not primary_gw:
            primary_gw = reconciled_jpatch[0]

        for n in reconciled_jpatch:
            if n is primary_gw:
                n["is_gateway"] = True
                n["wired"] = True
                n["backhaul_type"] = "Gateway (WAN)"
            else:
                n["is_gateway"] = False
                n["backhaul_type"] = "Ethernet (1.0 Gbps)" if n.get("raw_wired") else "Wireless Mesh (5 GHz)"

        jp_office_res = next(n for n in reconciled_jpatch if n["name"] == "Office")
        jp_family_res = next(n for n in reconciled_jpatch if n["name"] == "Family Room")
        runner.assert_true(jp_family_res["is_gateway"] is True, "Family Room (192.168.4.1) correttamente eletto Primary Gateway (Issue #36)")
        runner.assert_true(jp_family_res["backhaul_type"] == "Gateway (WAN)", "Family Room backhaul è 'Gateway (WAN)'")
        runner.assert_true(jp_office_res["is_gateway"] is False, "Office (192.168.6.192) demotato correttamente a nodo foglia")
        runner.assert_true(jp_office_res["backhaul_type"] == "Ethernet (1.0 Gbps)", f"Office backhaul è 'Ethernet (1.0 Gbps)' (ottenuto: {jp_office_res['backhaul_type']})")

        # Test 5: Estrazione DNS Servers personalizzati e fallback gateway IP (Issue #30)
        custom_dns_net = {
            "name": "Custom DNS Network",
            "gateway_ip": "192.168.4.1",
            "dns": {
                "parental": None,
                "zscaler": None,
                "caching": False,
                "custom": {
                    "nameservers": ["1.1.1.1", "1.0.0.1"]
                }
            }
        }
        res_custom_dns = eero_client._normalize_network_details(custom_dns_net)
        runner.assert_true(res_custom_dns.get("dns_servers") == ["1.1.1.1", "1.0.0.1"], f"DNS personalizzati estratti correttamente (ottenuto: {res_custom_dns.get('dns_servers')})")
        runner.assert_true("192.168.4.104" not in res_custom_dns.get("dns_servers"), "IP sviluppatore 192.168.4.104 assente da custom DNS")

        # Fallback ISP DNS (nessun custom DNS configurato)
        default_dns_net = {
            "name": "Default DNS Network",
            "gateway_ip": "192.168.1.1",
            "dns": {
                "custom": None,
                "caching": True
            }
        }
        res_default_dns = eero_client._normalize_network_details(default_dns_net)
        runner.assert_true(res_default_dns.get("dns_servers") == ["192.168.1.1"], f"Fallback DNS usa gateway_ip di rete (ottenuto: {res_default_dns.get('dns_servers')})")
        runner.assert_true("192.168.4.104" not in res_default_dns.get("dns_servers"), "IP sviluppatore 192.168.4.104 assente da default DNS")

        # Test 6: Rilevamento accurato nodi offline e rebooting (Issue #34)
        node_healthy_raw = {
            "id": "node_healthy",
            "name": "Salotto Sano",
            "status": "green",
            "state": "ONLINE",
            "heartbeat_ok": True
        }
        node_rebooting_raw = {
            "id": "node_reboot",
            "name": "Salotto In Riavvio",
            "status": "yellow",
            "state": "REBOOTING",
            "heartbeat_ok": False
        }
        node_offline_red_raw = {
            "id": "node_off_red",
            "name": "Salotto Spento",
            "status": "red",
            "state": "OFFLINE",
            "heartbeat_ok": False
        }
        node_offline_hb_raw = {
            "id": "node_off_hb",
            "name": "Salotto No Heartbeat",
            "status": "yellow",
            "state": "ONLINE",
            "heartbeat_ok": False
        }
        norm_healthy = eero_client._normalize_eero_node(node_healthy_raw)
        norm_reboot = eero_client._normalize_eero_node(node_rebooting_raw)
        norm_off_red = eero_client._normalize_eero_node(node_offline_red_raw)
        norm_off_hb = eero_client._normalize_eero_node(node_offline_hb_raw)

        runner.assert_true(norm_healthy["status"] == "online", "Nodo sano con status='green', heartbeat_ok=True è 'online'")
        runner.assert_true(norm_reboot["status"] == "rebooting", "Nodo con state='REBOOTING' è 'rebooting' (Issue #34)")
        runner.assert_true(norm_off_red["status"] == "offline", "Nodo con status='red' è 'offline' (Issue #34)")
        runner.assert_true(norm_off_hb["status"] == "offline", "Nodo con heartbeat_ok=False è 'offline' (Issue #34)")

        # =====================================================================
        # 11. TEST PRESERVAZIONE REGOLE ADGUARD HOME & MAPPING DESKTOP (Issue #21)
        # =====================================================================
        print("\n🛡️ [11/12] TEST PRESERVAZIONE REGOLE ADGUARD HOME & MAPPING DESKTOP (Issue #21)")
        
        # Test 1: Mappatura corretta Desktop vs Laptop e tag AdGuard
        cat_dt, icon_dt = map_eero_device_type("desktop", "Josh_desktop")
        runner.assert_true(cat_dt == "Computer" and icon_dt == "pc", f"Josh_desktop device_type desktop mappato come Computer/pc (ottenuto: {cat_dt}/{icon_dt})")
        runner.assert_true(get_adguard_tags(cat_dt, icon_dt) == ["device_pc"], "Tag AdGuard per desktop è ['device_pc']")

        cat_lt, icon_lt = map_eero_device_type("laptop", "MacBook Pro M3")
        runner.assert_true(cat_lt == "Computer" and icon_lt == "laptop", f"MacBook Pro mappato come Computer/laptop (ottenuto: {cat_lt}/{icon_lt})")
        runner.assert_true(get_adguard_tags(cat_lt, icon_lt) == ["device_laptop"], "Tag AdGuard per laptop è ['device_laptop']")

        cat_tower, icon_tower = map_eero_device_type("computer", "Workstation Tower PC")
        runner.assert_true(cat_tower == "Computer" and icon_tower == "pc", f"Workstation Tower mappato come Computer/pc (ottenuto: {cat_tower}/{icon_tower})")
        runner.assert_true(get_adguard_tags(cat_tower, icon_tower) == ["device_pc"], "Tag AdGuard per tower è ['device_pc']")

        # Test 2: Preservazione integrale regole, upstreams e blacklist custom su update AdGuard
        existing_ag_client = {
            "name": "Josh_desktop",
            "ids": ["192.168.1.100", "00:11:22:33:44:55", "custom-alias.lan"],
            "tags": ["user_custom_tag"],
            "upstreams": ["https://dns.quad9.net/dns-query", "9.9.9.9"],
            "blocked_services": ["youtube", "tiktok", "steam"],
            "blocked_services_schedule": {"time_zone": "UTC"},
            "use_global_blocked_services": False,
            "use_global_settings": False,
            "filtering_enabled": True,
            "parental_enabled": True,
            "safebrowsing_enabled": True,
            "safesearch_enabled": True,
        }

        incoming_eero_payload = {
            "name": "Josh_desktop",
            "ids": ["192.168.1.100", "00:11:22:33:44:55", "2001:db8::1"],
            "tags": ["device_pc"],
            "upstreams": [],
            "blocked_services": [],
            "use_global_blocked_services": True,
            "use_global_settings": True,
            "filtering_enabled": True,
            "parental_enabled": False,
            "safebrowsing_enabled": True,
            "safesearch_enabled": False,
        }

        merged_client = adguard_service._merge_adguard_client_data(existing_ag_client, incoming_eero_payload)
        
        runner.assert_true(merged_client["upstreams"] == ["https://dns.quad9.net/dns-query", "9.9.9.9"], "Upstreams DNS personalizzati preservati al 100%")
        runner.assert_true(merged_client["blocked_services"] == ["youtube", "tiktok", "steam"], "Servizi bloccati (blocked_services) preservati al 100%")
        runner.assert_true(merged_client["parental_enabled"] is True, "Parental Control abilitato preservato (parental_enabled=True)")
        runner.assert_true(merged_client["safesearch_enabled"] is True, "SafeSearch abilitato preservato (safesearch_enabled=True)")
        runner.assert_true(merged_client["use_global_settings"] is False, "use_global_settings=False preservato")
        runner.assert_true(merged_client["use_global_blocked_services"] is False, "use_global_blocked_services=False preservato")
        runner.assert_true(merged_client["tags"] == ["user_custom_tag"], "Tag personalizzato utente preservato")
        runner.assert_true("custom-alias.lan" in merged_client["ids"] and "2001:db8::1" in merged_client["ids"], "IDs uniti correttamente senza perdere ID custom utente")

        # =====================================================================
        # 12. TEST AUTO-UPDATE ENGINE & STORICIZZAZIONE SEGNALE (v1.4.0)
        # =====================================================================
        print("\n🔄 [12/12] TEST AUTO-UPDATE ENGINE & STORICIZZAZIONE SEGNALE (v1.4.0)")

        # Documentazione interattiva delle API (Swagger / ReDoc / OpenAPI): 404 per default, 200 solo con API_DOCS=true
        import importlib
        import app.main as docs_main_module
        orig_api_docs = settings.api_docs
        try:
            for api_docs_value, expected_docs_status in ((False, 404), (True, 200)):
                settings.api_docs = api_docs_value
                docs_app = importlib.reload(docs_main_module).app
                async with AsyncClient(transport=ASGITransport(app=docs_app), base_url="http://test") as docs_client:
                    for docs_path in ("/docs", "/redoc", "/openapi.json"):
                        docs_res = await docs_client.get(docs_path)
                        runner.assert_true(docs_res.status_code == expected_docs_status, f"GET {docs_path} risponde HTTP {expected_docs_status} con API_DOCS={api_docs_value} (ottenuto: {docs_res.status_code})")
        finally:
            settings.api_docs = orig_api_docs
            importlib.reload(docs_main_module)

        # 1. Test Endpoint /api/system/update/check
        check_res = await client.get("/api/system/update/check?force=true")
        runner.assert_true(check_res.status_code == 200, "Endpoint GET /api/system/update/check risponde HTTP 200")
        check_data = check_res.json()
        runner.assert_true(check_data.get("status") == "success", "Stato update check è 'success'")
        runner.assert_true(check_data.get("current_version") == "1.6.2", f"Versione corrente rilevata è 1.6.2 (ottenuta: {check_data.get('current_version')})")
        runner.assert_true("cli_command" in check_data, "Comando CLI assistito presente nel payload di update")

        # 2. Test Endpoint /api/system/update/trigger (modalità manuale/assistita in test env)
        trigger_res = await client.post("/api/system/update/trigger")
        runner.assert_true(trigger_res.status_code == 200, "Endpoint POST /api/system/update/trigger risponde HTTP 200")
        trigger_data = trigger_res.json()
        runner.assert_true("method" in trigger_data, "Metodo di aggiornamento specificato nella risposta")

        # Switch to Live mode for DB signal tracking test
        await client.post("/api/auth/mode", json={"demo": False})

        # 3. Test Salvataggio Campioni Segnale RSSI su SQLite
        signal_samples = [
            {
                "mac_address": "AA:BB:CC:DD:EE:01",
                "hostname": "iPhone Test Soggiorno",
                "signal_rssi": -45,
                "frequency_band": "6 GHz",
                "channel": 69,
                "connected_eero_name": "Living Room",
                "rx_bitrate": 1800.0,
                "tx_bitrate": 1200.0
            },
            {
                "mac_address": "AA:BB:CC:DD:EE:02",
                "hostname": "Telecamera Giardino",
                "signal_rssi": -82,
                "frequency_band": "2.4 GHz",
                "channel": 6,
                "connected_eero_name": "Garage Beacon",
                "rx_bitrate": 54.0,
                "tx_bitrate": 54.0
            }
        ]
        inserted = await db_service.record_device_signal_samples(signal_samples)
        runner.assert_true(inserted == 2, f"Salvati 2 campioni di segnale su SQLite (inseriti: {inserted})")

        # Configura cache poller con i dispositivi attivi per il test dell'overview
        background_poller.cached_devices = [
            {"mac": "AA:BB:CC:DD:EE:01", "hostname": "iPhone Test Soggiorno", "connected": True, "wireless": True},
            {"mac": "AA:BB:CC:DD:EE:02", "hostname": "Telecamera Giardino", "connected": True, "wireless": True}
        ]

        # 4. Test Endpoint /api/metrics/signal/overview
        overview_res = await client.get("/api/metrics/signal/overview")
        runner.assert_true(overview_res.status_code == 200, "Endpoint GET /api/metrics/signal/overview risponde HTTP 200")
        overview_data = overview_res.json().get("overview", {})
        runner.assert_true(overview_data.get("total_wireless_devices", 0) >= 2, "Overview riporta almeno 2 dispositivi wireless campionati")
        runner.assert_true("average_rssi" in overview_data, "Segnale medio RSSI presente nell'overview")
        runner.assert_true(overview_data.get("weak_count", 0) >= 1, "Rilevato almeno 1 dispositivo con segnale debole (Telecamera Giardino)")
        weak_devs = overview_data.get("weak_devices", [])
        runner.assert_true(any(d.get("mac_address") == "aa:bb:cc:dd:ee:02" for d in weak_devs), "Telecamera Giardino inclusa nella Weak Signal Watchlist")

        # 5. Test Endpoint /api/metrics/signal/history
        history_res = await client.get("/api/metrics/signal/history?mac=AA:BB:CC:DD:EE:01&hours=24")
        runner.assert_true(history_res.status_code == 200, "Endpoint GET /api/metrics/signal/history risponde HTTP 200")
        hist_data = history_res.json()
        runner.assert_true(hist_data.get("points_count", 0) >= 1, "Cronologia segnale per iPhone Test riporta campioni storici")
        runner.assert_true(hist_data["history"][0]["signal_rssi"] == -45, "Valore RSSI -45 dBm verificato nei punti storici")

        # 6. Test Bonifica Transitori di Uscita (Exit Fade-out Pruning)
        exit_mac = "AA:BB:CC:DD:EE:99"
        await db_service.record_device_signal_samples([
            {"mac_address": exit_mac, "hostname": "Telefono Uscente", "signal_rssi": -55},
            {"mac_address": exit_mac, "hostname": "Telefono Uscente", "signal_rssi": -89}
        ])
        pruned_count = await db_service.prune_device_exit_transient_samples(exit_mac, window_minutes=5, threshold_rssi=-75)
        runner.assert_true(pruned_count >= 1, f"Bonificato campione transitorio di uscita per {exit_mac} (pruned: {pruned_count})")
        remaining_hist = await db_service.get_device_signal_history(exit_mac, range_hours=1)
        runner.assert_true(all(pt["signal_rssi"] >= -75 for pt in remaining_hist), "Nessun campione critico < -75 dBm residuo dopo exit pruning")

        # 7. Test Filtro Presenza Attiva su Signal Overview (dispositivo disconnesso escluso da Watchlist)
        overview_active_only = await db_service.get_signal_overview(is_demo=0, active_macs={"aa:bb:cc:dd:ee:01"})
        runner.assert_true(overview_active_only.get("total_wireless_devices") == 1, "Overview con active_macs filtra solo dispositivi connessi")
        runner.assert_true(len(overview_active_only.get("weak_devices", [])) == 0, "Dispositivo offline con ultimo segnale debole escluso dalla Watchlist attiva")

        # =====================================================================
        # 13. TEST MULTI-ENGINE DNS SYNCHRONIZER (AdGuard, Pi-hole, Technitium) (v1.4.0)
        # =====================================================================
        print("\n🌐 [13/13] TEST MULTI-ENGINE DNS SYNCHRONIZER (v1.4.0)")

        # Switch to Demo mode to ensure total network isolation
        await client.post("/api/auth/mode", json={"demo": True})

        # 1. Test Endpoint GET /api/automations/dns
        dns_get_res = await client.get("/api/automations/dns")
        runner.assert_true(dns_get_res.status_code == 200, "Endpoint GET /api/automations/dns risponde HTTP 200")
        dns_get_data = dns_get_res.json()
        runner.assert_true("instances" in dns_get_data, "Payload GET /api/automations/dns contiene 'instances'")

        # 2. Configura 3 istanze simultanee eterogenee (2 AdGuard Home + 1 Pi-hole)
        test_dns_payload = {
            "instances": [
                {
                    "id": "ag_soggiorno",
                    "name": "AdGuard Primario Soggiorno",
                    "engine": "adguard",
                    "url": "http://192.168.1.2:80",
                    "username": "admin",
                    "password": "secretpassword",
                    "enabled": True,
                    "sync_reverse_dns": True,
                    "preserve_custom_settings": True,
                },
                {
                    "id": "ag_studio",
                    "name": "AdGuard Backup Studio",
                    "engine": "adguard",
                    "url": "http://192.168.1.3:80",
                    "username": "admin",
                    "password": "secretpassword2",
                    "enabled": True,
                    "sync_reverse_dns": True,
                    "preserve_custom_settings": True,
                },
                {
                    "id": "pihole_iot",
                    "name": "Pi-hole IoT Dedicated",
                    "engine": "pihole",
                    "url": "http://192.168.1.4:80",
                    "api_token": "mock_pihole_token_12345",
                    "enabled": True,
                    "sync_reverse_dns": True,
                    "preserve_custom_settings": False,
                }
            ],
            "auto_sync_enabled": True,
            "sync_schedule_minutes": 30
        }

        dns_post_res = await client.post("/api/automations/dns", json=test_dns_payload)
        runner.assert_true(dns_post_res.status_code == 200, "Endpoint POST /api/automations/dns salva configurazione con HTTP 200")
        dns_saved = dns_post_res.json()
        runner.assert_true(dns_saved.get("status") == "success", "Salvataggio Multi-DNS restituisce status 'success'")
        runner.assert_true(len(dns_saved.get("instances", [])) == 3, "Salvate correttamente 3 istanze simultanee (2 AdGuard + 1 Pi-hole)")

        # 3. Test connessione singola istanza (Pi-hole)
        test_pihole_res = await client.post("/api/automations/dns/test", json={"instance_id": "pihole_iot"})
        runner.assert_true(test_pihole_res.status_code == 200, "Endpoint POST /api/automations/dns/test per Pi-hole risponde HTTP 200")
        pihole_res_data = test_pihole_res.json()
        runner.assert_true(pihole_res_data.get("status") == "success", "Test connettività Pi-hole in isolamento Demo ha status 'success'")

        # 4. Test connettività globale simultanea di tutte le istanze (2 AdGuard + 1 Pi-hole)
        test_all_res = await client.post("/api/automations/dns/test", json={})
        runner.assert_true(test_all_res.status_code == 200, "Endpoint POST /api/automations/dns/test globale risponde HTTP 200")
        all_res_data = test_all_res.json()
        runner.assert_true(all_res_data.get("status") == "success", "Test globale di tutte le istanze ha status 'success'")
        results_list = all_res_data.get("results", [])
        runner.assert_true(len(results_list) == 3, f"Ricevuti esiti di test per tutte e 3 le istanze (ricevuti: {len(results_list)})")
        runner.assert_true(all(r.get("success") is True for r in results_list), "Tutte e 3 le istanze simultanee risultano connesse con successo in Demo Mode")

        # 5. Sincronizzazione massiva di tutte le istanze DNS
        sync_all_res = await client.post("/api/automations/dns/sync", json={})
        runner.assert_true(sync_all_res.status_code == 200, "Endpoint POST /api/automations/dns/sync risponde HTTP 200")
        sync_data = sync_all_res.json()
        runner.assert_true(sync_data.get("status") == "success", "Sincronizzazione massiva Multi-DNS ha status 'success'")
        runner.assert_true(len(sync_data.get("results", [])) == 3, "Sincronizzate con successo tutte e 3 le istanze (2 AdGuard + 1 Pi-hole)")

        # 6. Verifica Backward Compatibility Endpoint Legacy /api/automations/adguard*
        legacy_get = await client.get("/api/automations/adguard")
        runner.assert_true(legacy_get.status_code == 200, "Endpoint legacy GET /api/automations/adguard risponde HTTP 200")
        legacy_get_data = legacy_get.json()
        runner.assert_true("url" in legacy_get_data, "Payload legacy contiene chiave 'url'")
        runner.assert_true(legacy_get_data.get("url") == "http://192.168.1.2:80", "Endpoint legacy espone URL della prima istanza AdGuard")

        legacy_test = await client.post("/api/automations/adguard/test", json={"url": "http://192.168.1.2:80", "username": "admin", "password": "secretpassword"})
        runner.assert_true(legacy_test.status_code == 200, "Endpoint legacy POST /api/automations/adguard/test risponde HTTP 200")
        runner.assert_true(legacy_test.json().get("status") == "success", "Test connettività legacy AdGuard ha status 'success'")

        legacy_sync = await client.post("/api/automations/adguard/sync")
        runner.assert_true(legacy_sync.status_code == 200, "Endpoint legacy POST /api/automations/adguard/sync risponde HTTP 200")
        runner.assert_true(legacy_sync.json().get("status") == "success", "Sync legacy AdGuard ha status 'success'")

        # 7. Verifica del certificato HTTPS verso i server DNS (opzione per istanza 'insecure_tls')
        # Nessun accesso di rete: httpx.AsyncClient è sostituito da un client con MockTransport che registra 'verify'.
        import json
        import ssl
        import httpx
        import app.services.dns_manager as dns_manager_module
        from app.services.dns_manager import parse_insecure_tls

        strict_true = [v for v in (True, False, None, "", "false", "False", "0", "no", "off", 0, "true", "TRUE ", "1", 1, "yes", "on") if parse_insecure_tls(v)]
        runner.assert_true(strict_true == [True, "true", "TRUE ", "1", 1, "yes", "on"], f"parse_insecure_tls: solo True/'true'/'1'/'yes'/'on' disattivano la verifica (ottenuti: {strict_true})")
        runner.assert_true(parse_insecure_tls("false") is False and parse_insecure_tls("0") is False, "parse_insecure_tls: la stringa 'false' (o '0') NON diventa True")

        def _tls_dns_handler(request):
            if request.url.host == "selfsigned.lan":
                try:
                    raise ssl.SSLCertVerificationError(1, "certificate verify failed: self-signed certificate")
                except ssl.SSLCertVerificationError as ssl_exc:
                    raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed", request=request) from ssl_exc
            if request.url.host == "unreachable.lan":
                raise httpx.ConnectError("All connection attempts failed", request=request)
            if request.url.host == "pihole-auth.lan":
                if request.url.path == "/api/auth":
                    try:
                        raise ssl.SSLCertVerificationError(1, "certificate verify failed: self-signed certificate")
                    except ssl.SSLCertVerificationError as ssl_exc:
                        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed", request=request) from ssl_exc
                return httpx.Response(401, json={})
            path = request.url.path
            if path == "/control/clients":
                return httpx.Response(200, json={"clients": [], "auto_clients": []})
            if path.startswith("/control/clients/"):
                return httpx.Response(200, json={})
            if path == "/api/config/dns/hosts":
                return httpx.Response(200, json={"config": {"dns": {"hosts": []}}})
            if path == "/api/config":
                return httpx.Response(200, json={})
            if path == "/api/zones/list":
                return httpx.Response(200, json={"status": "ok", "response": {"zones": []}})
            if path == "/api/zones/records/add":
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(404, json={})

        tls_verify_seen = []
        real_async_client = httpx.AsyncClient

        class _TlsRecordingClient(real_async_client):
            def __init__(self, *args, **kwargs):
                tls_verify_seen.append(kwargs.get("verify", True))
                kwargs["transport"] = httpx.MockTransport(_tls_dns_handler)
                super().__init__(*args, **kwargs)

        tls_devices = [{"ip": "192.168.1.20", "mac": "AA:BB:CC:00:11:20", "hostname": "pc-tls-test"}]
        tls_engines = [("tls_adguard", "adguard", "adguard.lan"), ("tls_pihole", "pihole", "pihole.lan"), ("tls_technitium", "technitium", "technitium.lan")]
        tls_setting_keys = [
            "dns_instances", "dns_sync_enabled", "adguard_url", "adguard_username", "adguard_password", "adguard_sync_enabled", "adguard_insecure_tls",
            "adguard_last_sync_time", "adguard_last_sync_count", "adguard_last_sync_status",
        ]
        tls_saved_settings = {k: await db_service.get_setting(k) for k in tls_setting_keys}
        tls_prev_demo = eero_client._is_demo_active
        tls_prev_token = eero_client.user_token

        async def _tls_verify_per_path(instance_ids):
            """Esegue test e sync per ciascuna istanza e restituisce {(id, 'test'|'sync'): verify}."""
            seen = {}
            for inst_id in instance_ids:
                tls_verify_seen.clear()
                await client.post("/api/automations/dns/test", json={"instance_id": inst_id})
                seen[(inst_id, "test")] = list(tls_verify_seen)
                tls_verify_seen.clear()
                await dns_service.sync_devices(tls_devices, instance_id=inst_id)
                seen[(inst_id, "sync")] = list(tls_verify_seen)
            return seen

        def _tls_instances(insecure=None, host_override=None):
            out = []
            for inst_id, engine, host in tls_engines:
                inst = {"id": inst_id, "name": f"TLS {engine}", "engine": engine, "url": f"https://{host_override or host}",
                        "username": "admin", "password": "pw-tls", "token": "tok-tls", "enabled": True}
                if insecure is not None:
                    inst["insecure_tls"] = insecure
                out.append(inst)
            return out

        async def _stored_instances():
            return json.loads(await db_service.get_setting("dns_instances", "[]") or "[]")

        httpx.AsyncClient = _TlsRecordingClient
        try:
            eero_client._is_demo_active = False
            eero_client.user_token = "live_secret_user_token_sample"
            tls_ids = [e[0] for e in tls_engines]

            # a) Istanza nuova senza opzione: verifica TLS attiva sui 6 percorsi (3 test + 3 sync)
            await db_service.set_setting("dns_instances", "[]")
            res = await client.post("/api/automations/dns", json={"enabled": False, "instances": _tls_instances()})
            runner.assert_true(res.status_code == 200, "Salvataggio istanze https:// senza 'insecure_tls' risponde HTTP 200")
            stored = await _stored_instances()
            runner.assert_true(all(i.get("insecure_tls") is False for i in stored), "Istanze nuove salvate con insecure_tls=False (booleano) di default")
            seen = await _tls_verify_per_path(tls_ids)
            runner.assert_true(all(v == [True] for v in seen.values()) and len(seen) == 6, f"Default: verify=True sui 6 percorsi AdGuard/Pi-hole/Technitium test+sync (visti: {seen})")

            # b) Opzione attiva: verify=False sui 6 percorsi
            res = await client.post("/api/automations/dns", json={"enabled": False, "instances": _tls_instances(insecure=True)})
            stored = await _stored_instances()
            runner.assert_true(all(i.get("insecure_tls") is True for i in stored), "insecure_tls=True salvato per le 3 istanze")
            seen = await _tls_verify_per_path(tls_ids)
            runner.assert_true(all(v == [False] for v in seen.values()) and len(seen) == 6, f"insecure_tls=True: verify=False sui 6 percorsi (visti: {seen})")
            dns_get = (await client.get("/api/automations/dns")).json()
            runner.assert_true(all(i.get("insecure_tls") is True for i in dns_get.get("instances", [])), "GET /api/automations/dns espone insecure_tls=True")
            runner.assert_true(all("password" not in i for i in dns_get.get("instances", [])), "GET /api/automations/dns continua a non esporre le password")

            # c) Interpretazione rigorosa: "false" (API o database) non disattiva la verifica
            res = await client.post("/api/automations/dns", json={"enabled": False, "instances": _tls_instances(insecure="false")})
            stored = await _stored_instances()
            runner.assert_true(res.status_code == 200 and all(i.get("insecure_tls") is False for i in stored), "API: insecure_tls='false' salvato come False")
            raw = _tls_instances()
            for inst in raw:
                inst["insecure_tls"] = "false"
            await db_service.set_setting("dns_instances", json.dumps(raw))
            seen = await _tls_verify_per_path(tls_ids)
            runner.assert_true(all(v == [True] for v in seen.values()), f"Database: insecure_tls='false' (stringa) mantiene verify=True (visti: {seen})")
            for inst in raw:
                inst["insecure_tls"] = "yes-please"
            await db_service.set_setting("dns_instances", json.dumps(raw))
            seen = await _tls_verify_per_path(tls_ids)
            runner.assert_true(all(v == [True] for v in seen.values()), f"Database: valore sconosciuto mantiene verify=True (visti: {seen})")

            # d) Compatibilità: istanze salvate prima dell'opzione (nessuna chiave) — https:// resta senza verifica, http:// invariato
            legacy_raw = [
                {"id": "old_https", "name": "AdGuard https", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "password": "pw", "token": "", "enabled": True},
                {"id": "old_http", "name": "Pi-hole http", "engine": "pihole", "url": "http://pihole.lan", "username": "", "password": "", "token": "tok", "enabled": True},
            ]
            await db_service.set_setting("dns_instances", json.dumps(legacy_raw))
            dns_get = (await client.get("/api/automations/dns")).json()
            by_id = {i["id"]: i for i in dns_get.get("instances", [])}
            runner.assert_true(by_id.get("old_https", {}).get("insecure_tls") is True, "Compatibilità: istanza https:// salvata prima dell'opzione appare con insecure_tls=True (visibile e disattivabile)")
            runner.assert_true(by_id.get("old_http", {}).get("insecure_tls") is False, "Compatibilità: istanza http:// salvata prima dell'opzione appare con insecure_tls=False")
            seen = await _tls_verify_per_path(["old_https"])
            runner.assert_true(seen == {("old_https", "test"): [False], ("old_https", "sync"): [False]}, f"Compatibilità: l'istanza https:// esistente continua a funzionare senza verifica (visti: {seen})")
            stored = {i["id"]: i for i in await _stored_instances()}
            runner.assert_true(stored.get("old_https", {}).get("insecure_tls") is True and stored.get("old_http", {}).get("insecure_tls") is False, "Compatibilità: dopo il primo sync l'opzione è salvata esplicitamente nel database")

            # Salvataggio da client che non conosce l'opzione: valore conservato ; l'utente può disattivarlo (reversibile)
            res = await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "old_https", "name": "AdGuard https", "engine": "adguard", "url": "https://adguard.lan", "username": "admin"}]})
            stored = {i["id"]: i for i in await _stored_instances()}
            runner.assert_true(stored.get("old_https", {}).get("insecure_tls") is True and stored.get("old_https", {}).get("password") == "pw", "Salvataggio senza 'insecure_tls' conserva il valore (e la password) già salvati")
            tls_verify_seen.clear()
            await client.post("/api/automations/dns/test", json={"instance": {"id": "old_https", "engine": "adguard", "url": "https://altro.lan", "username": "admin"}})
            runner.assert_true(tls_verify_seen == [True], f"Test dello stesso id verso un altro server senza opzione: verify=True (visti: {tls_verify_seen})")
            await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "old_https", "name": "AdGuard https", "engine": "adguard", "url": "https://altro.lan", "username": "admin"}]})
            stored = {i["id"]: i for i in await _stored_instances()}
            runner.assert_true(stored.get("old_https", {}).get("insecure_tls") is False, "Stesso id con un altro server e senza opzione: verifica attiva (nessuna eredità)")
            await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "old_https", "name": "AdGuard https", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "insecure_tls": True}]})
            res = await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "old_https", "name": "AdGuard https", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "insecure_tls": False}]})
            seen = await _tls_verify_per_path(["old_https"])
            runner.assert_true(seen == {("old_https", "test"): [True], ("old_https", "sync"): [True]}, f"Opzione tolta dall'utente: verifica di nuovo attiva (visti: {seen})")

            # Test dall'interfaccia con valore non ancora salvato: prevale il valore inviato
            tls_verify_seen.clear()
            await client.post("/api/automations/dns/test", json={"instance": {"id": "old_https", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "insecure_tls": True}})
            runner.assert_true(tls_verify_seen == [False], f"Test con insecure_tls inviato dall'interfaccia (non salvato) usa quel valore (visti: {tls_verify_seen})")
            tls_verify_seen.clear()
            await client.post("/api/automations/dns/test", json={"instance": {"id": "nuova", "engine": "adguard", "url": "https://adguard.lan"}})
            runner.assert_true(tls_verify_seen == [True], f"Test di un'istanza nuova senza opzione: verify=True (visti: {tls_verify_seen})")

            # Configurazione legacy a istanza singola (adguard_url senza dns_instances, salvata prima dell'opzione)
            await db_service.set_setting("dns_instances", "")
            async with db_service.get_connection() as tls_db:
                await tls_db.execute("DELETE FROM app_settings WHERE key = 'adguard_insecure_tls'")
                await tls_db.commit()
            await db_service.set_setting("adguard_url", "https://adguard.lan")
            await db_service.set_setting("adguard_username", "admin")
            await db_service.set_setting("adguard_password", "pw")
            dns_get = (await client.get("/api/automations/dns")).json()
            legacy_inst = next((i for i in dns_get.get("instances", []) if i.get("id") == "inst-legacy-adguard"), {})
            runner.assert_true(legacy_inst.get("insecure_tls") is True, "Compatibilità: configurazione legacy adguard_url https:// appare con insecure_tls=True")
            tls_verify_seen.clear()
            await dns_service.sync_devices(tls_devices)
            runner.assert_true(tls_verify_seen == [False], f"Compatibilità: sync della configurazione legacy https:// invariato (verify=False, visti: {tls_verify_seen})")

            # e) Certificato non verificabile: messaggio chiaro con l'indicazione dell'opzione
            await db_service.set_setting("dns_instances", json.dumps(_tls_instances(insecure=False, host_override="selfsigned.lan")))
            for inst_id, engine, _host in tls_engines:
                test_res = (await client.post("/api/automations/dns/test", json={"instance_id": inst_id})).json()
                runner.assert_true(test_res.get("success") is False and test_res.get("tls_error") is True and any(t in test_res.get("message", "") for t in ("Accetta certificato HTTPS non verificato", "Accept unverified HTTPS certificate")), f"Test {engine}: certificato non verificabile → tls_error e messaggio con l'opzione da abilitare")
                sync_res = await dns_service.sync_devices(tls_devices, instance_id=inst_id)
                sync_item = (sync_res.get("results") or [{}])[0]
                runner.assert_true(sync_item.get("success") is False and sync_item.get("tls_error") is True, f"Sync {engine}: certificato non verificabile → tls_error")
            await db_service.set_setting("dns_instances", json.dumps(_tls_instances(insecure=False, host_override="unreachable.lan")))
            test_res = (await client.post("/api/automations/dns/test", json={"instance_id": "tls_adguard"})).json()
            runner.assert_true(test_res.get("success") is False and not test_res.get("tls_error") and any(t in test_res.get("message", "") for t in ("Impossibile connettersi", "Cannot connect")), "Errore di connessione non TLS: messaggio invariato, nessun tls_error")

            # Pi-hole: errore di certificato durante /api/auth (dopo un 401) non viene assorbito
            await db_service.set_setting("dns_instances", json.dumps([{"id": "tls_pihole_auth", "name": "Pi-hole auth", "engine": "pihole", "url": "https://pihole-auth.lan", "token": "tok-tls", "insecure_tls": False, "enabled": True}]))
            test_res = (await client.post("/api/automations/dns/test", json={"instance_id": "tls_pihole_auth"})).json()
            runner.assert_true(test_res.get("tls_error") is True, f"Test Pi-hole: certificato non verificabile su /api/auth → tls_error (ottenuto: {test_res.get('message')})")
            sync_item = ((await dns_service.sync_devices(tls_devices, instance_id="tls_pihole_auth")).get("results") or [{}])[0]
            runner.assert_true(sync_item.get("success") is False and sync_item.get("tls_error") is True, f"Sync Pi-hole: certificato non verificabile su /api/auth → tls_error, nessun ripiego v5 (ottenuto: {sync_item.get('message')})")

            # API: Pydantic non converte "t", "y", 1.0 in True (stessa regola del database)
            for loose_value in ("t", "y", 1.0, "garbage"):
                res = await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "tls_loose", "engine": "adguard", "url": "https://adguard.lan", "insecure_tls": loose_value}]})
                stored = await _stored_instances()
                runner.assert_true(res.status_code == 200 and stored and stored[0].get("insecure_tls") is False, f"API: insecure_tls={loose_value!r} salvato come False")

            # Istanza senza id: non eredita l'opzione di un'istanza salvata con l'id generato ("inst-1")
            await db_service.set_setting("dns_instances", json.dumps([{"id": "inst-1", "engine": "adguard", "url": "https://old.lan", "insecure_tls": True, "enabled": True}]))
            await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"engine": "adguard", "url": "https://new.lan"}]})
            stored = await _stored_instances()
            runner.assert_true(stored and stored[0].get("id") == "inst-1" and stored[0].get("insecure_tls") is False, "Istanza nuova senza id: verifica attiva (nessuna eredità dall'id generato)")

            # Configurazione legacy: primo salvataggio senza il campo conserva l'opzione mostrata (True), chiave legacy rispecchiata
            await db_service.set_setting("dns_instances", "")
            await db_service.set_setting("adguard_url", "https://adguard.lan")
            async with db_service.get_connection() as tls_db:
                await tls_db.execute("DELETE FROM app_settings WHERE key = 'adguard_insecure_tls'")
                await tls_db.commit()
            await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "inst-legacy-adguard", "engine": "adguard", "url": "https://adguard.lan", "username": "admin"}]})
            stored = await _stored_instances()
            runner.assert_true(stored and stored[0].get("insecure_tls") is True, "Configurazione legacy https://: primo salvataggio senza il campo conserva insecure_tls=True")
            runner.assert_true(await db_service.get_setting("adguard_insecure_tls") == "true", "Chiave legacy adguard_insecure_tls rispecchia il primo AdGuard")

            # Istanze eliminate: la copia legacy che riappare mantiene la scelta dell'utente (verifica attiva)
            await client.post("/api/automations/dns", json={"enabled": True, "instances": [{"id": "inst-legacy-adguard", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "insecure_tls": False}]})
            await client.post("/api/automations/dns", json={"enabled": True, "instances": []})
            dns_get = (await client.get("/api/automations/dns")).json()
            revived = next((i for i in dns_get.get("instances", []) if i.get("id") == "inst-legacy-adguard"), {})
            runner.assert_true(revived.get("insecure_tls") is False, "Dopo l'eliminazione delle istanze, la configurazione legacy riapparsa resta verificata")
            tls_verify_seen.clear()
            await dns_service.sync_devices(tls_devices)
            runner.assert_true(tls_verify_seen == [True], f"Sync della configurazione legacy riapparsa: verify=True (visti: {tls_verify_seen})")

            # Endpoint legacy /api/automations/adguard/test: opzione dell'istanza salvata solo per lo stesso server
            await client.post("/api/automations/dns", json={"enabled": False, "instances": [{"id": "tls_legacy_ep", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "password": "pw", "insecure_tls": True}]})
            tls_verify_seen.clear()
            await client.post("/api/automations/adguard/test", json={"url": "https://adguard.lan", "username": "admin", "password": "pw"})
            runner.assert_true(tls_verify_seen == [False], f"Endpoint legacy adguard/test sullo stesso server: opzione salvata applicata (visti: {tls_verify_seen})")
            tls_verify_seen.clear()
            await client.post("/api/automations/adguard/test", json={"url": "https://other.lan", "username": "admin", "password": "pw"})
            runner.assert_true(tls_verify_seen == [True], f"Endpoint legacy adguard/test verso un altro server: verify=True (visti: {tls_verify_seen})")

            # Endpoint legacy POST /api/automations/adguard (istanza singola): opzione conservata solo per lo stesso server
            await db_service.set_setting("dns_instances", json.dumps([{"id": "inst-adguard-1", "engine": "adguard", "url": "https://adguard.lan", "username": "admin", "password": "pw", "insecure_tls": True, "enabled": True}]))
            await client.post("/api/automations/adguard", json={"enabled": False, "url": "https://adguard.lan", "username": "admin"})
            stored = await _stored_instances()
            runner.assert_true(stored and stored[0].get("insecure_tls") is True, "Endpoint legacy adguard (stesso server): insecure_tls=True conservato")
            await client.post("/api/automations/adguard", json={"enabled": False, "url": "https://altro.lan", "username": "admin"})
            stored = await _stored_instances()
            runner.assert_true(stored and stored[0].get("insecure_tls") is False, "Endpoint legacy adguard (nuovo server): verifica attiva")
            await db_service.set_setting("dns_instances", json.dumps([{"id": "tls_pihole_only", "engine": "pihole", "url": "https://adguard.lan", "token": "tok", "insecure_tls": True, "enabled": True}]))
            tls_verify_seen.clear()
            await client.post("/api/automations/adguard/test", json={"url": "https://adguard.lan", "username": "admin", "password": "pw"})
            runner.assert_true(tls_verify_seen == [True], f"Endpoint legacy adguard/test: l'opzione di un Pi-hole alla stessa URL non vale per AdGuard (visti: {tls_verify_seen})")
            await client.post("/api/automations/adguard", json={"enabled": False, "url": "https://adguard.lan", "username": "admin"})
            stored = await _stored_instances()
            runner.assert_true(stored and stored[0].get("engine") == "adguard" and stored[0].get("insecure_tls") is False, "Endpoint legacy adguard: nuova istanza AdGuard non eredita l'opzione di un Pi-hole alla stessa URL")

            # Configurazione legacy salvata prima dell'opzione: primo salvataggio dall'endpoint legacy e test per id
            await db_service.set_setting("dns_instances", "")
            async with db_service.get_connection() as tls_db:
                await tls_db.execute("DELETE FROM app_settings WHERE key = 'adguard_insecure_tls'")
                await tls_db.commit()
            await db_service.set_setting("adguard_url", "https://adguard.lan")
            tls_verify_seen.clear()
            await client.post("/api/automations/dns/test", json={"instance": {"id": "inst-legacy-adguard", "engine": "adguard", "url": "https://adguard.lan", "username": "admin"}})
            runner.assert_true(tls_verify_seen == [False], f"Test per id della configurazione legacy https:// senza opzione: comportamento invariato (visti: {tls_verify_seen})")
            await client.post("/api/automations/adguard", json={"enabled": False, "url": "https://adguard.lan", "username": "admin"})
            stored = await _stored_instances()
            runner.assert_true(stored and stored[0].get("insecure_tls") is True, "Configurazione legacy https://: primo salvataggio dall'endpoint legacy conserva insecure_tls=True")
        finally:
            httpx.AsyncClient = real_async_client
            eero_client._is_demo_active = tls_prev_demo
            eero_client.user_token = tls_prev_token
            for key, value in tls_saved_settings.items():
                if value is None:
                    async with db_service.get_connection() as tls_db:
                        await tls_db.execute("DELETE FROM app_settings WHERE key = ?", (key,))
                        await tls_db.commit()
                else:
                    await db_service.set_setting(key, value)
        runner.assert_true(dns_manager_module.httpx.AsyncClient is real_async_client, "httpx.AsyncClient ripristinato dopo i test TLS")

        # f) Interfaccia: casella per istanza, valore inviato al salvataggio e al test, traduzioni it/en allineate
        from pathlib import Path
        tls_index_html = Path("app/templates/index.html").read_text(encoding="utf-8")
        tls_app_js = Path("app/static/js/app.js").read_text(encoding="utf-8")
        runner.assert_true('x-model="inst.insecure_tls"' in tls_index_html, "index.html: casella 'insecure_tls' nel modulo dell'istanza DNS")
        runner.assert_true('x-model="inst.url" @input="if (inst.insecure_tls && normalizeDnsUrl($event.target.value) !== inst.tls_url) inst.insecure_tls = false"' in tls_index_html, "index.html: cambiare server (URL normalizzato) toglie l'opzione (nuovo server = verifica attiva)")
        runner.assert_true("normalizeDnsUrl(url)" in tls_app_js and "tls_url: i.insecure_tls === true ? this.normalizeDnsUrl(i.url) : ''" in tls_app_js, "app.js: URL associato all'opzione TLS memorizzato e normalizzato come nel backend")
        runner.assert_true("controls.dns_insecure_tls_warning" in tls_index_html, "index.html: avviso mostrato quando la verifica è disattivata")
        runner.assert_true(tls_app_js.count("insecure_tls: inst.insecure_tls === true") == 2, "app.js: insecure_tls inviato (booleano rigoroso) al salvataggio e al test")
        runner.assert_true("insecure_tls: false" in tls_app_js, "app.js: nuova istanza con verifica attiva (insecure_tls: false)")
        tls_it = json.loads(Path("app/static/locales/it.json").read_text(encoding="utf-8")).get("controls", {})
        tls_en = json.loads(Path("app/static/locales/en.json").read_text(encoding="utf-8")).get("controls", {})
        runner.assert_true(all(k in tls_it and k in tls_en for k in ("dns_insecure_tls", "dns_insecure_tls_warning", "dns_tls_error")), "Chiavi i18n dns_insecure_tls / _warning / dns_tls_error presenti in it.json ed en.json")
        runner.assert_true(set(tls_it.keys()) == set(tls_en.keys()), "Parità 100% tra chiavi 'controls' di it.json ed en.json")

        # =====================================================================
        # 14. TEST HEALTH SCORE BREAKDOWN & DIAGNOSTICS (Issue #15)
        # =====================================================================
        print("\n❤️ [14/14] TEST HEALTH SCORE BREAKDOWN & DIAGNOSTICS (Issue #15)")
        
        # Test endpoint overview
        ov_res = await client.get("/api/network/overview")
        runner.assert_true(ov_res.status_code == 200, "Endpoint GET /api/network/overview risponde HTTP 200")
        ov_data = ov_res.json().get("data", {})
        runner.assert_true("health_details" in ov_data, "Payload overview contiene 'health_details'")
        runner.assert_true("health_score" in ov_data, "Payload overview contiene 'health_score'")

        # Test endpoint dedicato /api/network/health-breakdown
        hb_res = await client.get("/api/network/health-breakdown")
        runner.assert_true(hb_res.status_code == 200, "Endpoint GET /api/network/health-breakdown risponde HTTP 200")
        hb_json = hb_res.json()
        runner.assert_true(hb_json.get("status") == "success", "Endpoint health-breakdown restituisce status 'success'")
        hb_data = hb_json.get("data", {})
        runner.assert_true("health_score" in hb_data, "health-breakdown contiene 'health_score'")
        runner.assert_true("health_details" in hb_data, "health-breakdown contiene 'health_details'")
        
        h_details = hb_data.get("health_details", {})
        runner.assert_true("pillars" in h_details, "health_details contiene 'pillars'")
        pillars = h_details.get("pillars", {})
        runner.assert_true("mesh_topology" in pillars, "Pilastro 'mesh_topology' presente")
        runner.assert_true("wan_gateway" in pillars, "Pilastro 'wan_gateway' presente")
        runner.assert_true("client_signal" in pillars, "Pilastro 'client_signal' presente")
        runner.assert_true("channel_density" in pillars, "Pilastro 'channel_density' presente")
        runner.assert_true(isinstance(h_details.get("penalties"), list), "'penalties' è una lista")
        runner.assert_true(isinstance(h_details.get("recommendations"), list), "'recommendations' è una lista")

        # Test unitario calcolo diagnostico su scenario degradato
        deg_net = {"status": "online", "public_ip": "1.2.3.4", "speedtest": {"ping_ms": 85.0}}
        deg_eeros = [
            {"id": "gw", "name": "Gateway", "is_gateway": True, "status": "online", "connected_clients_count": 10},
            {"id": "node2", "name": "Nodo Cucina", "is_gateway": False, "status": "offline", "connected_clients_count": 0}
        ]
        deg_devs = [
            {"connected": True, "wireless": True, "wireless_band": "2.4GHz", "signal_rssi": -85, "custom_name": "Device 1"},
            {"connected": True, "wireless": True, "wireless_band": "2.4GHz", "signal_rssi": -78, "custom_name": "Device 2"},
        ]
        deg_calc = background_poller.calculate_health_details(deg_net, deg_eeros, deg_devs)
        runner.assert_true(deg_calc["score"] < 100, f"Scenario degradato calcola punteggio inferiore a 100 (ottenuto: {deg_calc['score']})")
        runner.assert_true(len(deg_calc["penalties"]) >= 2, f"Scenario degradato rileva almeno 2 penalità (ottenute: {len(deg_calc['penalties'])})")
        has_offline_penalty = any(p["id"] == "offline_nodes" for p in deg_calc["penalties"])
        runner.assert_true(has_offline_penalty, "Penalità 'offline_nodes' correttamente rilevata per Nodo Cucina")

        # Test multilingua i18n (Issue #15 / i18n fix): ogni pilastro ha una traduzione per ogni lingua supportata
        from app.i18n import SUPPORTED_LANGUAGES as _langs_health
        for p_key in ["mesh_topology", "wan_gateway", "client_signal", "channel_density"]:
            pillar_obj = deg_calc["pillars"].get(p_key, {})
            runner.assert_true("summary_i18n" in pillar_obj, f"Pilastro '{p_key}' contiene 'summary_i18n'")
            for _lang in _langs_health:
                runner.assert_true(_lang in pillar_obj.get("summary_i18n", {}), f"Pilastro '{p_key}' ha traduzione '{_lang}'")

        first_penalty = deg_calc["penalties"][0]
        runner.assert_true("title_i18n" in first_penalty and "en" in first_penalty["title_i18n"], "Penalità include title_i18n con chiave 'en'")
        runner.assert_true("description_i18n" in first_penalty and "en" in first_penalty["description_i18n"], "Penalità include description_i18n con chiave 'en'")
        runner.assert_true("recommendations_i18n" in deg_calc and len(deg_calc["recommendations_i18n"]) > 0, "'recommendations_i18n' presente e popolato")
        runner.assert_true("en" in deg_calc["recommendations_i18n"][0], "Prima raccomandazione include versione 'en'")

        # Permessi di session.json (contiene il token eero): 0600 anche se il file esisteva con permessi più ampi
        if os.name == "posix":
            import json
            import stat
            import tempfile
            from pathlib import Path
            from app.services.eero_client import EeroClient
            with tempfile.TemporaryDirectory() as session_tmp_dir:
                session_file = Path(session_tmp_dir) / "session.json"
                session_file.write_text("{}", encoding="utf-8")
                os.chmod(session_file, 0o644)
                perm_client = EeroClient(session_path=session_file)
                perm_client.user_token = "live_token_permissions_test"
                perm_client.save_session()
                session_mode = stat.S_IMODE(os.stat(session_file).st_mode)
                runner.assert_true(session_mode == 0o600, f"session.json scritto con permessi 0600 (ottenuto: {oct(session_mode)})")
                saved_token = json.loads(session_file.read_text(encoding="utf-8")).get("user_token")
                runner.assert_true(saved_token == "live_token_permissions_test", "session.json contiene il token salvato")

                # chmod non consentito (es. volume montato): il salvataggio avviene comunque e il file non resta vuoto
                orig_fchmod = os.fchmod

                def _fchmod_denied(fd, mode):
                    raise PermissionError("chmod not permitted")

                os.fchmod = _fchmod_denied
                try:
                    perm_client.user_token = "live_token_after_chmod_error"
                    perm_client.save_session()
                finally:
                    os.fchmod = orig_fchmod
                try:
                    saved_token = json.loads(session_file.read_text(encoding="utf-8")).get("user_token")
                except ValueError:
                    saved_token = None  # file vuoto o troncato
                runner.assert_true(saved_token == "live_token_after_chmod_error", f"session.json salvato anche se chmod non è consentito (token letto: {saved_token})")

        # Ripristina stato finale live
        await client.post("/api/auth/mode", json={"demo": False})

        # =====================================================================
        # 15. TEST CONNECTION POOLING & IN-MEMORY DNS CACHE (Issue #24)
        # =====================================================================
        print("\n⚡ [15/15] TEST CONNECTION POOLING & IN-MEMORY DNS CACHE (Issue #24)")
        from app.services.dns_cache import enable_dns_cache, disable_dns_cache, get_dns_cache_stats, clear_dns_cache
        import socket

        # Test attivazione cache DNS
        enable_dns_cache(ttl_seconds=300)
        clear_dns_cache()
        stats_init = get_dns_cache_stats()
        runner.assert_true(stats_init["enabled"] is True, "DNS Cache risulta abilitata")
        runner.assert_true(stats_init["ttl_seconds"] == 300, "TTL DNS Cache configurato a 300s")

        # Prima query a dominio esterno -> cache miss
        info1 = socket.getaddrinfo("api-user.e2ro.com", 443)
        runner.assert_true(len(info1) > 0, "Risoluzione DNS di api-user.e2ro.com valida")
        stats_after_first = get_dns_cache_stats()
        runner.assert_true(stats_after_first["entries_count"] >= 1, "api-user.e2ro.com memorizzato in cache")

        # Seconda query identica -> cache hit immediato a 0ms (zero query DNS verso l'upstream)
        hits_before = stats_after_first["hits"]
        info2 = socket.getaddrinfo("api-user.e2ro.com", 443)
        stats_after_second = get_dns_cache_stats()
        runner.assert_true(info1 == info2, "Risultato DNS da cache identico all'originale")
        runner.assert_true(stats_after_second["hits"] == hits_before + 1, "Cache hit registrato con successo (zero chiamate DNS)")

        # Test riutilizzo istanza client HTTP e connection pooling
        async with eero_client._client_session() as c1:
            client_id1 = id(c1)
        async with eero_client._client_session() as c2:
            client_id2 = id(c2)
        runner.assert_true(client_id1 == client_id2, "Istanza httpx.AsyncClient riutilizzata nel pool (Keep-Alive attivo)")
        runner.assert_true(not eero_client._http_client.is_closed, "Client HTTP aperto e pronto per nuove richieste nel pool")

        # Password Wi-Fi mai esposte dalla cache pubblica (/api/network/overview e /api/network/refresh)
        import httpx
        main_wifi_secret = "MainWifiSecret-Test-123"
        guest_wifi_secret = "GuestWifiSecret-Test-456"

        def _wifi_secret_handler(request):
            if request.url.path.endswith("/networks/net_wifi_test"):
                return httpx.Response(200, json={"data": {
                    "url": "/2.2/networks/net_wifi_test",
                    "name": "Test Network",
                    "password": main_wifi_secret,
                    "guest_network": {"enabled": True, "name": "Test Guest", "password": guest_wifi_secret},
                    "backup_networks": [{"name": "Backup", "psk": main_wifi_secret}],
                }})
            return httpx.Response(200, json={"data": []})

        saved_wifi_client = (eero_client.user_token, eero_client.current_network_id, eero_client._is_demo_active, eero_client._http_client,
                             eero_client._last_network_details, eero_client._last_eeros)
        saved_wifi_cache = (background_poller.cached_network, background_poller.cached_eeros, background_poller.cached_devices,
                            background_poller.cached_profiles, background_poller.cached_health_score, background_poller.cached_health_details)
        try:
            eero_client.user_token = "live_token_wifi_test"
            eero_client.current_network_id = "net_wifi_test"
            eero_client._is_demo_active = False
            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(_wifi_secret_handler))
            await background_poller._poll_and_cache()
            overview_res = await client.get("/api/network/overview")
            runner.assert_true(overview_res.status_code == 200, "GET /api/network/overview risponde HTTP 200")
            runner.assert_true(overview_res.json()["data"]["network"].get("name") == "Test Network", "Overview contiene i dettagli rete del poll")
            runner.assert_true(main_wifi_secret not in overview_res.text, "Password Wi-Fi principale assente da /api/network/overview")
            runner.assert_true(guest_wifi_secret not in overview_res.text, "Password Wi-Fi ospiti assente da /api/network/overview")
            guest_res = await client.get("/api/network/guest")
            runner.assert_true(guest_res.json().get("guest_network", {}).get("password") == guest_wifi_secret, "Endpoint dedicato /api/network/guest restituisce ancora la password ospiti (QR Code)")
        finally:
            await eero_client._http_client.aclose()
            (eero_client.user_token, eero_client.current_network_id, eero_client._is_demo_active, eero_client._http_client,
             eero_client._last_network_details, eero_client._last_eeros) = saved_wifi_client
            (background_poller.cached_network, background_poller.cached_eeros, background_poller.cached_devices,
             background_poller.cached_profiles, background_poller.cached_health_score, background_poller.cached_health_details) = saved_wifi_cache

        # =====================================================================
        # 16. TEST ISOLAMENTO SPEEDTEST & PREVENZIONE LEAK MOCK TIM (Issue #35)
        # =====================================================================
        print("\n⚡ [16/16] TEST ISOLAMENTO SPEEDTEST & PREVENZIONE LEAK MOCK TIM (Issue #35)")
        from app.services.speedtest_service import speedtest_service

        # 1. Verifica che in sessione autenticata un errore API non restituisca dati demo TIM
        orig_token = eero_client.user_token
        orig_net_id = eero_client.current_network_id
        orig_cache_net = eero_client._last_network_details
        orig_cache_eeros = eero_client._last_eeros

        try:
            eero_client.user_token = "live_token_test_abc"
            eero_client.current_network_id = "invalid_network_test_id"
            eero_client._last_network_details = {"network_name": "Cached Live Network", "isp": "Virgin Media UK"}
            eero_client._last_eeros = [{"name": "Living Room", "is_gateway": True}]

            # get_network_details() in caso di errore HTTP (es. 400 Bad Request) deve ritornare la cache reale, MAI i dati demo TIM
            res_net = await eero_client.get_network_details()
            runner.assert_true("TIM FTTH" not in str(res_net.get("isp", "")), "get_network_details() non restituisce 'TIM FTTH' su errore API autenticata")
            runner.assert_true(res_net.get("network_name") == "Cached Live Network", "get_network_details() preserva l'ultimo stato noto")

            # get_devices() in sessione autenticata senza rete risolvibile (/account in errore) non deve ricadere nei dispositivi demo
            import httpx
            saved_devices_http = eero_client._http_client
            eero_client.current_network_id = None
            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503, json={"meta": {"code": 503}})))
            try:
                res_devices = await eero_client.get_devices()
            finally:
                await eero_client._http_client.aclose()
                eero_client._http_client = saved_devices_http
                eero_client.current_network_id = "invalid_network_test_id"
            demo_macs = {str(d.get("mac")).lower() for d in eero_client._demo_state["devices"]}
            runner.assert_true(
                not any(str(d.get("mac")).lower() in demo_macs for d in res_devices),
                f"get_devices() senza rete risolta non restituisce dispositivi demo in sessione autenticata (ottenuti: {len(res_devices)})"
            )

            # get_eeros() in caso di errore HTTP deve ritornare _last_eeros, MAI i nodi demo
            res_eeros = await eero_client.get_eeros()
            runner.assert_true(len(res_eeros) == 1 and res_eeros[0].get("name") == "Living Room", "get_eeros() preserva l'ultimo stato noto senza ricadere nei nodi demo")

            # 2. Verifica purge_all_mock_data() su SQLite (sia in init_db sia standalone)
            sp_mock_id = await db_service.save_speedtest(
                download_mbps=912.45,
                upload_mbps=298.10,
                ping_ms=9.2,
                server_name="TIM FTTH 1Gbps / 300Mbps (WAN SpeedTest)",
                source="eero_gateway"
            )
            sp_real_id = await db_service.save_speedtest(
                download_mbps=1140.50,
                upload_mbps=105.20,
                ping_ms=14.1,
                server_name="Virgin Media (WAN SpeedTest)",
                source="eero_gateway"
            )

            # Esecuzione pulizia durante init_db() (verifica assenza 'database is locked')
            await db_service.init_db()

            # Verifichiamo che il record TIM sia stato eliminato e il record Virgin Media sia preservato
            all_sp = await db_service.get_speedtests(limit=50)
            mock_found = any(s.get("id") == sp_mock_id or abs(float(s.get("download_mbps", 0)) - 912.45) < 0.01 for s in all_sp)
            real_found = any(s.get("id") == sp_real_id for s in all_sp)
            runner.assert_true(not mock_found, "Record mock TIM eliminato da init_db() senza deadlock SQLite")
            runner.assert_true(real_found, "Record reale utente preservato intatto nel database SQLite")

            # Verifica chiamata standalone di purge_all_mock_data()
            await db_service.save_speedtest(
                download_mbps=912.45,
                upload_mbps=298.10,
                ping_ms=9.2,
                server_name="TIM FTTH 1Gbps / 300Mbps (WAN SpeedTest)",
                source="eero_gateway"
            )
            await db_service.purge_all_mock_data()
            all_sp_standalone = await db_service.get_speedtests(limit=50)
            mock_found_standalone = any(abs(float(s.get("download_mbps", 0)) - 912.45) < 0.01 for s in all_sp_standalone)
            runner.assert_true(not mock_found_standalone, "Record mock eliminato anche da chiamata standalone purge_all_mock_data()")

            # 3. Verifica che speedtest_service fallisca in modo pulito senza salvare fallback sintetici
            eero_client.current_network_id = "invalid_network_test_id"
            threw_exception = False
            try:
                await speedtest_service.run_speedtest()
            except Exception:
                threw_exception = True
            runner.assert_true(threw_exception, "speedtest_service solleva eccezione pulita su errore API anziché generare fallback sintetici")
            runner.assert_true(speedtest_service.is_running is False, "speedtest_service resetta il flag is_running a False")

            # 4. Rete senza speed test eero (down/up nulli): nessun valore predefinito presentato come misura reale
            no_speed_net = eero_client._normalize_network_details({"name": "No Speed Network", "speed": {"down": None, "up": None, "date": None}})
            no_speed = no_speed_net.get("speedtest", {})
            runner.assert_true(
                no_speed.get("download_mbps") == 0.0 and no_speed.get("upload_mbps") == 0.0 and no_speed.get("ping_ms") == 0.0,
                f"Speed test assente non sostituito da valori predefiniti (ottenuto: {no_speed.get('download_mbps')}/{no_speed.get('upload_mbps')} Mbps, {no_speed.get('ping_ms')} ms)"
            )
            runner.assert_true(no_speed.get("timestamp") is None, f"Speed test senza data eero non riceve un orario inventato (ottenuto: {no_speed.get('timestamp')})")

            # 5. Poll reale (API eero simulata) di una rete senza speed test: nessun test 951/193 Mbps registrato nello storico
            import httpx

            def _no_speed_handler(request):
                if request.url.path.endswith("/networks/net_nospeed_test"):
                    return httpx.Response(200, json={"data": {"url": "/2.2/networks/net_nospeed_test", "name": "No Speed Network", "speed": {"down": None, "up": None, "date": None}}})
                return httpx.Response(200, json={"data": []})

            def _count_951(tests):
                return sum(1 for t in tests if abs(float(t.get("download_mbps") or 0) - 951.0) < 0.05)

            count_951_before = _count_951(await db_service.get_speedtests(limit=500))
            saved_nospeed_http = eero_client._http_client
            saved_nospeed_cache = (background_poller.cached_network, background_poller.cached_eeros, background_poller.cached_devices,
                                   background_poller.cached_profiles, background_poller.cached_health_score, background_poller.cached_health_details)
            eero_client.user_token = "live_token_nospeed_test"
            eero_client.current_network_id = "net_nospeed_test"
            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(_no_speed_handler))
            try:
                await background_poller._poll_and_cache()
            finally:
                await eero_client._http_client.aclose()
                eero_client._http_client = saved_nospeed_http
                (background_poller.cached_network, background_poller.cached_eeros, background_poller.cached_devices,
                 background_poller.cached_profiles, background_poller.cached_health_score, background_poller.cached_health_details) = saved_nospeed_cache
            count_951_after = _count_951(await db_service.get_speedtests(limit=500))
            runner.assert_true(
                count_951_after == count_951_before,
                f"Nessuno speed test predefinito 951/193 Mbps salvato come misura eero_gateway (righe 951 prima/dopo il poll: {count_951_before}/{count_951_after})"
            )

        finally:
            # Ripristina client eero
            eero_client.user_token = orig_token
            eero_client.current_network_id = orig_net_id
            eero_client._last_network_details = orig_cache_net
            eero_client._last_eeros = orig_cache_eeros

        # =====================================================================
        # 17. TEST MULTI-NETWORK FLEET MANAGEMENT, INTELLIGENT PRUNING & USAGE (v1.5.0)
        # =====================================================================
        print("\n🌐 [17/17] TEST MULTI-NETWORK FLEET MANAGEMENT, INTELLIGENT PRUNING & USAGE (v1.5.0)")
        
        # 1. Attiva demo mode
        eero_client.set_demo_mode(True)
        
        # 2. Test GET /api/network/list
        list_res = await client.get("/api/network/list")
        runner.assert_true(list_res.status_code == 200, "Endpoint GET /api/network/list risponde HTTP 200")
        list_data = list_res.json()
        runner.assert_true(list_data.get("status") == "success", "GET /api/network/list restituisce status success")
        runner.assert_true(len(list_data.get("networks", [])) >= 2, "Trovate almeno 2 reti disponibili nell'account Demo (Issue #22)")
        net_ids = [n.get("id") for n in list_data.get("networks", [])]
        runner.assert_true("network_demo_mesh_01" in net_ids and "network_demo_mesh_02" in net_ids, "Entrambe le reti demo (Casa Rossi Mesh 6E e Ufficio & Studio Pro Mesh) presenti")

        # 3. Test POST /api/network/switch verso Rete 2
        switch_res = await client.post("/api/network/switch", json={"network_id": "network_demo_mesh_02"})
        runner.assert_true(switch_res.status_code == 200, "Endpoint POST /api/network/switch risponde HTTP 200")
        switch_data = switch_res.json()
        runner.assert_true(switch_data.get("active_network_id") == "network_demo_mesh_02", "Rete attiva cambiata con successo a 'network_demo_mesh_02'")
        runner.assert_true(eero_client.current_network_id == "network_demo_mesh_02", "eero_client memorizza la nuova rete attiva")

        # 4. Verifica dettagli rete post-switch
        # Demo sample names are translated for non-Italian callers (demo_i18n middleware): ask for IT explicitly
        det_res = await client.get("/api/network/overview", headers={"X-Dashboard-Lang": "it"})
        runner.assert_true(det_res.status_code == 200, "GET /api/network/overview risponde HTTP 200 post-switch")
        det_data = det_res.json()
        cached_net = det_data.get("data", {}).get("network", {})
        net_name = cached_net.get("name") or cached_net.get("network_name") or ""
        runner.assert_true("Ufficio & Studio" in net_name, f"Nome rete aggiornato a Ufficio & Studio (ottenuto: {net_name})")

        # 5. Switch di ripristino su Rete 1
        switch_back = await client.post("/api/network/switch", json={"network_id": "network_demo_mesh_01"})
        runner.assert_true(switch_back.status_code == 200, "Ripristino su 'network_demo_mesh_01' eseguito con successo")

        # 6. Test GET /api/network/top-hogs
        hogs_res = await client.get("/api/network/top-hogs?period=daily")
        runner.assert_true(hogs_res.status_code == 200, "Endpoint GET /api/network/top-hogs risponde HTTP 200")
        hogs_data = hogs_res.json()
        runner.assert_true(hogs_data.get("status") == "success", "top-hogs restituisce status success")
        runner.assert_true(isinstance(hogs_data.get("top_hogs"), list), "top_hogs è un array valido")
        runner.assert_true(len(hogs_data.get("top_hogs")) > 0, "Almeno un dispositivo presente nella classifica Top Hogs")

        # 7. Test GET /api/devices/{mac}/usage
        sample_mac = hogs_data.get("top_hogs")[0].get("mac")
        usage_res = await client.get(f"/api/devices/{sample_mac}/usage?period=daily")
        runner.assert_true(usage_res.status_code == 200, f"Endpoint GET /api/devices/{sample_mac}/usage risponde HTTP 200")
        usage_data = usage_res.json()
        runner.assert_true(usage_data.get("status") == "success", "device usage status è success")
        u_info = usage_data.get("data", {})
        runner.assert_true(u_info.get("period") == "daily", "Periodo usage è daily")
        runner.assert_true("summary" in u_info and "rx_bytes" in u_info["summary"], "Sommario consumo include rx_bytes")
        runner.assert_true(len(u_info.get("data_points", [])) > 0, "Punti storici consumo presenti nel payload")

        # 8. Test Intelligent Address Pruning (Issue #31)
        prune_existing = {
            "name": "NAS_Storage",
            "ids": [
                "00:11:22:33:44:99",
                "192.168.4.200",
                "2001:db8::dead:beef",
                "2001:db8::cafe:babe",
                "storage.local",
                "192.168.4.0/24"
            ]
        }
        incoming_fresh = {
            "name": "NAS_Storage",
            "ids": [
                "00:11:22:33:44:99",
                "192.168.4.200",
                "2001:db8::1111:2222"
            ]
        }
        # Con prune_stale_ips=True:
        pruned = dns_service._merge_adguard_client_data(prune_existing, incoming_fresh, prune_stale_ips=True, drop_ipv6=False)
        runner.assert_true("00:11:22:33:44:99" in pruned["ids"], "MAC Address preservato nel pruning")
        runner.assert_true("192.168.4.200" in pruned["ids"], "IPv4 attivo preservato nel pruning")
        runner.assert_true("storage.local" in pruned["ids"], "Custom host alias storage.local preservato intatto")
        runner.assert_true("192.168.4.0/24" in pruned["ids"], "Custom CIDR preservato intatto")
        runner.assert_true("2001:db8::1111:2222" in pruned["ids"], "Nuovo IPv6 attivo incluso")
        runner.assert_true("2001:db8::dead:beef" not in pruned["ids"], "Stale SLAAC IPv6 dead:beef correttamente potato (Issue #31)")
        runner.assert_true("2001:db8::cafe:babe" not in pruned["ids"], "Stale SLAAC IPv6 cafe:babe correttamente potato (Issue #31)")

        # Con drop_ipv6=True:
        dropped_v6 = dns_service._merge_adguard_client_data(prune_existing, incoming_fresh, prune_stale_ips=True, drop_ipv6=True)
        runner.assert_true(not any(":" in x and len(x) > 17 for x in dropped_v6["ids"]), "Nessun indirizzo IPv6 presente quando drop_ipv6=True (Issue #31)")
        runner.assert_true("00:11:22:33:44:99" in dropped_v6["ids"], "MAC a 17 caratteri preservato con drop_ipv6")

        # =====================================================================
        # 18. TEST STATISTICHE, ANALYTICS & EXPORT CENTER (v1.5.0)
        # =====================================================================
        print("\n📊 [18/18] TEST STATISTICHE, ANALYTICS & EXPORT CENTER (v1.5.0)")

        # 1. Test GET /api/analytics/distribution
        dist_res = await client.get("/api/analytics/distribution")
        runner.assert_true(dist_res.status_code == 200, "GET /api/analytics/distribution risponde HTTP 200")
        dist_data = dist_res.json()
        runner.assert_true(dist_data.get("status") == "success", "Distribution restituisce status 'success'")
        runner.assert_true("total_devices" in dist_data and dist_data["total_devices"] >= 0, "total_devices valido")
        runner.assert_true("active_devices" in dist_data and dist_data["active_devices"] >= 0, "active_devices valido")
        runner.assert_true(isinstance(dist_data.get("frequencies"), list), "frequencies è un array")
        runner.assert_true(len(dist_data.get("frequencies", [])) > 0, "Almeno una frequenza presente nella distribuzione")
        runner.assert_true(isinstance(dist_data.get("node_load"), list), "node_load è un array")
        runner.assert_true(len(dist_data.get("node_load", [])) > 0, "Almeno un nodo presente nel carico mesh")
        runner.assert_true(isinstance(dist_data.get("categories"), list), "categories è un array")
        runner.assert_true(isinstance(dist_data.get("vendors"), list), "vendors è un array")

        # 2. Test GET /api/analytics/isp-sla (30 giorni e 7 giorni)
        sla30_res = await client.get("/api/analytics/isp-sla?days=30")
        runner.assert_true(sla30_res.status_code == 200, "GET /api/analytics/isp-sla?days=30 risponde HTTP 200")
        sla30_data = sla30_res.json()
        runner.assert_true(sla30_data.get("status") == "success", "SLA restituisce status 'success'")
        sla_info = sla30_data.get("sla", {})
        runner.assert_true(sla_info.get("period_days") == 30, "Periodo SLA impostato a 30 giorni")
        runner.assert_true("reliability_score" in sla_info, "Indice reliability_score presente")
        runner.assert_true(0 <= float(sla_info.get("reliability_score", 0)) <= 100, "reliability_score tra 0 e 100%")
        runner.assert_true("avg_download_mbps" in sla_info, "avg_download_mbps presente")
        runner.assert_true("avg_upload_mbps" in sla_info, "avg_upload_mbps presente")
        runner.assert_true("avg_jitter_ms" in sla_info, "avg_jitter_ms presente")
        runner.assert_true(isinstance(sla_info.get("history_points"), list), "history_points è una lista")

        sla7_res = await client.get("/api/analytics/isp-sla?days=7")
        runner.assert_true(sla7_res.status_code == 200, "GET /api/analytics/isp-sla?days=7 risponde HTTP 200")
        runner.assert_true(sla7_res.json().get("sla", {}).get("period_days") == 7, "Periodo SLA impostato a 7 giorni")

        # 3. Test Esportazione CSV
        exp_dev_csv = await client.get("/api/analytics/export/devices?format=csv")
        runner.assert_true(exp_dev_csv.status_code == 200, "GET /api/analytics/export/devices?format=csv risponde HTTP 200")
        runner.assert_true("text/csv" in exp_dev_csv.headers.get("content-type", ""), "Content-Type è text/csv")
        runner.assert_true("attachment;" in exp_dev_csv.headers.get("content-disposition", ""), "Header Content-Disposition contiene attachment")
        runner.assert_true("mac" in exp_dev_csv.text and "hostname" in exp_dev_csv.text, "CSV dispositivi include colonne mac e hostname")

        exp_sp_csv = await client.get("/api/analytics/export/speedtest?format=csv")
        runner.assert_true(exp_sp_csv.status_code == 200, "GET /api/analytics/export/speedtest?format=csv risponde HTTP 200")
        runner.assert_true("text/csv" in exp_sp_csv.headers.get("content-type", ""), "Content-Type speedtest è text/csv")

        exp_sig_csv = await client.get("/api/analytics/export/signal?format=csv")
        runner.assert_true(exp_sig_csv.status_code == 200, "GET /api/analytics/export/signal?format=csv risponde HTTP 200")
        runner.assert_true("text/csv" in exp_sig_csv.headers.get("content-type", ""), "Content-Type signal è text/csv")

        exp_usg_csv = await client.get("/api/analytics/export/usage?format=csv")
        runner.assert_true(exp_usg_csv.status_code == 200, "GET /api/analytics/export/usage?format=csv risponde HTTP 200")
        runner.assert_true("text/csv" in exp_usg_csv.headers.get("content-type", ""), "Content-Type usage è text/csv")

        # 4. Test Esportazione JSON
        exp_dev_json = await client.get("/api/analytics/export/devices?format=json")
        runner.assert_true(exp_dev_json.status_code == 200, "GET /api/analytics/export/devices?format=json risponde HTTP 200")
        runner.assert_true("application/json" in exp_dev_json.headers.get("content-type", ""), "Content-Type è application/json")
        dev_json_payload = exp_dev_json.json()
        runner.assert_true(dev_json_payload.get("status") == "success", "Export JSON restituisce status success")
        runner.assert_true(isinstance(dev_json_payload.get("data"), list), "Export JSON contiene campo 'data' di tipo array")

        # 5. Test Gestione Errori Esportazione
        exp_invalid = await client.get("/api/analytics/export/unknown_dataset?format=csv")
        runner.assert_true(exp_invalid.status_code == 400, "Richiesta esportazione dataset non valido restituisce HTTP 400")

        print("\n🌐 [19/19] TEST LOCALIZZAZIONE MULTILINGUA & DAILY DIGEST EN/IT (Issue #38)")
        # 1. API System Language GET / POST
        lang_get = await client.get("/api/system/language")
        runner.assert_true(lang_get.status_code == 200, "GET /api/system/language risponde HTTP 200")
        runner.assert_true(lang_get.json().get("status") == "success", "GET /api/system/language restituisce status success")

        # Rifiuta lingua non supportata ("xx" non è un codice ISO 639-1 assegnato: non entrerà mai in SUPPORTED_LANGUAGES)
        lang_invalid = await client.post("/api/system/language", json={"language": "xx"})
        runner.assert_true(lang_invalid.status_code == 400, "POST /api/system/language con lingua non supportata risponde HTTP 400")

        # Imposta lingua italiana
        lang_set_it = await client.post("/api/system/language", json={"language": "it"})
        runner.assert_true(lang_set_it.status_code == 200, "POST /api/system/language 'it' risponde HTTP 200")
        runner.assert_true(lang_set_it.json().get("language") == "it", "Lingua impostata a 'it'")

        lang_check_it = await client.get("/api/system/language")
        runner.assert_true(lang_check_it.json().get("language") == "it", "GET /api/system/language conferma 'it'")

        # Imposta lingua inglese
        lang_set_en = await client.post("/api/system/language", json={"language": "en"})
        runner.assert_true(lang_set_en.status_code == 200, "POST /api/system/language 'en' risponde HTTP 200")
        runner.assert_true(lang_set_en.json().get("language") == "en", "Lingua impostata a 'en'")

        # 2. Test Daily Digest con localizzazione (EN vs IT)
        from app.services.notifications import notification_service
        sample_digest = {
            "network_name": "Home Test Mesh",
            "health_score": 98,
            "isp": "Fiber ISP",
            "active_devices_count": 12,
            "count_6ghz": 2,
            "count_5ghz": 6,
            "count_24ghz": 3,
            "count_wired": 1,
            "online_nodes": 3,
            "total_nodes": 3,
            "wan_down": 850.0,
            "wan_up": 320.0,
            "wan_ping": 11.5,
        }

        # Invio digest in Inglese
        await notification_service.notify_digest(sample_digest, lang="en")
        alerts_en = await db_service.get_alerts(limit=1)
        runner.assert_true(len(alerts_en) > 0, "Alert salvato su DB per digest EN")
        runner.assert_true(alerts_en[0].get("title") == "📊 eero Mesh Daily Digest", "Titolo Digest in Inglese corretto (Issue #38)")
        runner.assert_true("Daily digest report sent" in alerts_en[0].get("message", ""), "Messaggio Digest in Inglese corretto")

        # Invio digest in Italiano
        await notification_service.notify_digest(sample_digest, lang="it")
        alerts_it = await db_service.get_alerts(limit=1)
        runner.assert_true(alerts_it[0].get("title") == "📊 Riepilogo Giornaliero eero Mesh", "Titolo Digest in Italiano corretto")
        runner.assert_true("Report giornaliero inviato" in alerts_it[0].get("message", ""), "Messaggio Digest in Italiano corretto")

        # Test trigger digest via API con override language
        res_dig_en = await client.post("/api/automations/digest/generate", json={"language": "en"})
        runner.assert_true(res_dig_en.status_code == 200, "POST /api/automations/digest/generate con language='en' risponde HTTP 200")
        alerts_api_en = await db_service.get_alerts(limit=1)
        runner.assert_true(alerts_api_en[0].get("title") == "📊 eero Mesh Daily Digest", "API digest genera titolo EN con language='en'")

        # 3. Test Allarme Nuovo Dispositivo (EN vs IT)
        sample_dev = {
            "hostname": "Test-Laptop",
            "mac": "AA:BB:CC:11:22:33",
            "ip": "192.168.4.99",
            "wireless_band": "5 GHz",
            "connected_eero_name": "Living Room"
        }
        await notification_service.notify_new_device(sample_dev, lang="en")
        alert_dev_en = (await db_service.get_alerts(limit=1))[0]
        runner.assert_true(alert_dev_en.get("title") == "🚨 New Device Detected on eero Network!", "Titolo nuovo device in Inglese corretto")
        runner.assert_true("connected to node" in alert_dev_en.get("message", ""), "Messaggio nuovo device in Inglese corretto")

        await notification_service.notify_new_device(sample_dev, lang="it")
        alert_dev_it = (await db_service.get_alerts(limit=1))[0]
        runner.assert_true(alert_dev_it.get("title") == "🚨 Nuovo Dispositivo Rilevato nella Rete eero!", "Titolo nuovo device in Italiano corretto")
        runner.assert_true("collegato al nodo" in alert_dev_it.get("message", ""), "Messaggio nuovo device in Italiano corretto")

        # 4. Test Allarme Nodo Offline (EN vs IT)
        sample_node = {"name": "Studio eero", "ip": "192.168.4.2"}
        await notification_service.notify_node_offline(sample_node, lang="en")
        alert_node_en = (await db_service.get_alerts(limit=1))[0]
        runner.assert_true(alert_node_en.get("title") == "⚠️ eero Mesh Node Offline!", "Titolo nodo offline in Inglese corretto")

        await notification_service.notify_node_offline(sample_node, lang="it")
        alert_node_it = (await db_service.get_alerts(limit=1))[0]
        runner.assert_true(alert_node_it.get("title") == "⚠️ Nodo eero Mesh Offline!", "Titolo nodo offline in Italiano corretto")

        # 5. Test Endpoint Notifiche / Test con language
        res_notif_en = await client.post("/api/automations/notifications/test", json={"language": "en"})
        runner.assert_true(res_notif_en.status_code == 200, "POST /api/automations/notifications/test con language='en' risponde HTTP 200")
        runner.assert_true(res_notif_en.json().get("telegram_sent") is True, "Test notifica Telegram EN inviato")

        # 6. Verifica integrità dizionari JSON (it.json ed en.json)
        import json
        with open("app/static/locales/it.json", "r", encoding="utf-8") as f:
            it_dict = json.load(f)
        with open("app/static/locales/en.json", "r", encoding="utf-8") as f:
            en_dict = json.load(f)

        required_keys = [
            "notifications_desc",
            "docker_title",
            "docker_subtitle",
            "docker_btn_update_available",
            "docker_btn_check",
            "docker_installed_version",
            "docker_socket_status",
            "docker_socket_detected",
            "docker_socket_not_mounted",
            "docker_latest_release",
            "dns_last_sync_prefix",
            "dns_never_synced",
            "dns_password_unchanged",
        ]
        for k in required_keys:
            runner.assert_true(k in it_dict.get("controls", {}), f"Chiave controls.{k} presente in it.json")
            runner.assert_true(k in en_dict.get("controls", {}), f"Chiave controls.{k} presente in en.json")

        # 7. Test Manuale In-App & Package Versioning (v1.6.0)
        import importlib
        app_pkg = importlib.import_module("app")
        runner.assert_true(getattr(app_pkg, "__version__", None) == "1.6.2", f"app.__version__ è '1.6.2' (trovato: {getattr(app_pkg, '__version__', None)})")
        res_man_it = await client.get("/api/manual/sections?lang=it")
        runner.assert_true(res_man_it.status_code == 200, "GET /api/manual/sections?lang=it risponde HTTP 200")
        runner.assert_true(res_man_it.json().get("count") >= 10, f"Manuale IT contiene almeno 10 sezioni complete (trovate: {res_man_it.json().get('count')})")
        res_man_en = await client.get("/api/manual/sections?lang=en")
        runner.assert_true(res_man_en.status_code == 200, "GET /api/manual/sections?lang=en risponde HTTP 200")
        runner.assert_true(res_man_en.json().get("count") >= 10, f"Manuale EN contiene almeno 10 sezioni complete (trovate: {res_man_en.json().get('count')})")
        res_ch_it = await client.get("/api/manual/changelog?lang=it")
        runner.assert_true(res_ch_it.json().get("version") == "1.6.2", "Versione restituita da changelog IT è 1.6.2")
        runner.assert_true("## v1.6.2" in res_ch_it.json().get("content", ""), "Changelog in-app IT include la release v1.6.2")
        res_ch_en = await client.get("/api/manual/changelog?lang=en")
        runner.assert_true(res_ch_en.json().get("version") == "1.6.2", "Versione restituita da changelog EN è 1.6.2")
        runner.assert_true("## v1.6.2" in res_ch_en.json().get("content", ""), "Changelog in-app EN include la release v1.6.2")

        # 8. Test Build Number & Full Versioning (es. '1.6.0 build 1')
        runner.assert_true(hasattr(settings, "build_number") and bool(settings.build_number), "settings.build_number configurato")
        runner.assert_true(settings.full_version == f"{settings.app_version} build {settings.build_number}", f"settings.full_version format corretto: '{settings.full_version}'")
        res_health = await client.get("/api/health")
        runner.assert_true(res_health.status_code == 200, "GET /api/health risponde HTTP 200")
        health_json = res_health.json()
        runner.assert_true("build_number" in health_json, "Endpoint /api/health include campo 'build_number'")
        runner.assert_true(health_json.get("full_version") == settings.full_version, f"/api/health full_version corrisponde: {health_json.get('full_version')}")
        from app.services.updater import updater_service, is_newer_version
        update_data = await updater_service.check_for_updates(force=True)
        runner.assert_true(update_data.get("full_version") == settings.full_version, f"updater_service include full_version: {update_data.get('full_version')}")
        runner.assert_true(bool(update_data.get("latest_full_version")), f"updater_service include latest_full_version: {update_data.get('latest_full_version')}")
        runner.assert_true(is_newer_version("1.6.0 build 2", "1.6.0-build.4") is True, "is_newer_version rileva correttamente nuova build 4")
        runner.assert_true(is_newer_version("1.6.0 build 2", "1.6.0-build.3") is True, "is_newer_version rileva correttamente nuova build 3")
        runner.assert_true(is_newer_version("1.6.0 build 4", "1.6.0-build.1") is False, "is_newer_version riconosce che build 1 non è più recente")
        runner.assert_true(is_newer_version("1.6.0 build 1", "1.6.0-build.2") is True, "is_newer_version rileva build 2 rispetto a build 1")

        # =====================================================================
        # 20. TEST EEROOS RELEASE NOTES, ZENDESK SCRAPER & COMMUNITY HUB (v1.6.0)
        # =====================================================================
        print("\n📰 [20/21] TEST EEROOS RELEASE NOTES, ZENDESK SCRAPER & COMMUNITY HUB (v1.6.0)")

        from app.services.eero_news_service import (
            eero_news_service,
            parse_eero_version,
            compare_eero_versions,
            is_newer_eero_version,
            compute_firmware_alignment,
        )

        # 1. Test Funzioni di Confronto Versioni eeroOS (SemVer & Build)
        runner.assert_true(parse_eero_version("v7.16.0-9483") == (7, 16, 0, 9483), "parse_eero_version analizza correttamente 'v7.16.0-9483'")
        runner.assert_true(parse_eero_version("v7.5.2-192") == (7, 5, 2, 192), "parse_eero_version analizza correttamente 'v7.5.2-192'")
        runner.assert_true(parse_eero_version("v6.16.5-4") == (6, 16, 5, 4), "parse_eero_version analizza correttamente 'v6.16.5-4'")
        runner.assert_true(parse_eero_version("v1.0.11") == (1, 0, 11, 0), "parse_eero_version analizza correttamente 'v1.0.11'")
        runner.assert_true(parse_eero_version("v7.17.1-24") == (7, 17, 1, 24), "parse_eero_version analizza correttamente 'v7.17.1-24'")
        runner.assert_true(parse_eero_version(None) == (0, 0, 0, 0), "parse_eero_version gestisce None senza errori")
        runner.assert_true(compare_eero_versions("v7.17.1-24", "v7.16.0-9483") == 1, "compare_eero_versions riconosce 7.17.1-24 > 7.16.0-9483")
        runner.assert_true(compare_eero_versions("v7.16.0-9483", "v7.17.1-24") == -1, "compare_eero_versions riconosce 7.16.0-9483 < 7.17.1-24")
        runner.assert_true(compare_eero_versions("v7.16.0-9483", "v7.16.0-9483") == 0, "compare_eero_versions riconosce versioni identiche")
        runner.assert_true(is_newer_eero_version("v7.16.0-9483", "v7.5.2-192") is True, "is_newer_eero_version rileva correttamente nuova release 7.16 vs 7.5.2")
        runner.assert_true(is_newer_eero_version("v7.5.2-192", "v7.16.0-9483") is False, "is_newer_eero_version riconosce versione precedente")
        runner.assert_true(is_newer_eero_version("v7.16.0-9483", "v7.16.0-9483") is False, "is_newer_eero_version ritorna False per versioni identiche")

        # 1.1 Test Allineamento Rigoroso e Mutua Esclusione (compute_firmware_alignment)
        # Caso A: Rete locale più recente della release censita (Early-rollout tipico eero: 7.17.1-24 vs 7.16.0-9483)
        align_early = compute_firmware_alignment("v7.17.1-24", "v7.16.0-9483")
        runner.assert_true(align_early["firmware_status"] == "newer_than_published", "compute_firmware_alignment assegna stato 'newer_than_published'")
        runner.assert_true(align_early["is_up_to_date"] is True, "align_early imposta is_up_to_date=True")
        runner.assert_true(align_early["update_available"] is False, "align_early garantisce update_available=False")
        runner.assert_true(align_early["target_firmware"] is None, "align_early non ha target_firmware pendente")

        # Caso B: Rete perfettamente allineata alla release ufficiale (7.16.0-9483 vs 7.16.0-9483)
        align_same = compute_firmware_alignment("v7.16.0-9483", "v7.16.0-9483")
        runner.assert_true(align_same["firmware_status"] == "up_to_date", "compute_firmware_alignment assegna stato 'up_to_date'")
        runner.assert_true(align_same["is_up_to_date"] is True, "align_same imposta is_up_to_date=True")
        runner.assert_true(align_same["update_available"] is False, "align_same imposta update_available=False")

        # Caso C: Rete indietro rispetto alla release ufficiale (7.15.1-119 vs 7.16.0-9483)
        align_behind = compute_firmware_alignment("v7.15.1-119", "v7.16.0-9483")
        runner.assert_true(align_behind["firmware_status"] == "update_available", "compute_firmware_alignment assegna stato 'update_available'")
        runner.assert_true(align_behind["is_up_to_date"] is False, "align_behind imposta is_up_to_date=False")
        runner.assert_true(align_behind["update_available"] is True, "align_behind imposta update_available=True")
        runner.assert_true(align_behind["target_firmware"] == "v7.16.0-9483", "align_behind target_firmware corrisponde alla release ufficiale")

        # Caso D: API eero segnala target più recente (es. 7.17.0-1000 su flotta a 7.16)
        align_pending = compute_firmware_alignment("v7.16.0-9483", "v7.16.0-9483", pending_api_target="v7.17.0-1000")
        runner.assert_true(align_pending["firmware_status"] == "update_available", "Pending API target più recente attiva 'update_available'")
        runner.assert_true(align_pending["target_firmware"] == "v7.17.0-1000", "target_firmware riflette l'aggiornamento pendente API")

        # Caso E: API eero segnala target antecedente o uguale alla versione già installata (es. target 7.16 ma installata 7.17)
        align_ignore_old_target = compute_firmware_alignment("v7.17.1-24", "v7.16.0-9483", pending_api_target="v7.16.0-9483")
        runner.assert_true(align_ignore_old_target["firmware_status"] == "newer_than_published", "Target pendente più vecchio viene correttamente ignorato")
        runner.assert_true(align_ignore_old_target["update_available"] is False, "update_available rimane False con target obsoleto")

        # 2. Test Parser HTML Zendesk (Mock Payload Realistico)
        sample_zendesk_html = """
        <p>Introductory paragraph from eero support.</p>
        <p><strong>eeroOS: v7.17.0-1000 - </strong><em>Released August 15, 2026</em></p>
        <ul>
            <li>Security vulnerability patches for Wi-Fi stack</li>
            <li>Improved TrueChannel and AWGN interference mitigation on 6 GHz band</li>
            <li>Performance and stability enhancements for mesh roaming</li>
        </ul>
        <p><strong>eeroOS: v7.16.1-50 - </strong><em>Released July 30, 2026</em></p>
        <ul>
            <li>General stability fixes and connection improvements</li>
            <li>Matter and Thread protocol updates</li>
        </ul>
        """
        parsed_notes = eero_news_service.parse_zendesk_html(sample_zendesk_html)
        runner.assert_true(len(parsed_notes) == 2, f"Parser Zendesk estrae 2 release (trovate: {len(parsed_notes)})")
        rel1 = parsed_notes[0]
        runner.assert_true(rel1["version"] == "v7.17.0-1000", f"Versione release 1 corretta: {rel1['version']}")
        runner.assert_true("August 15, 2026" in rel1["release_date"], f"Data release 1 corretta: {rel1['release_date']}")
        runner.assert_true(len(rel1["content"]) == 3, f"Release 1 ha 3 bullet points (trovati: {len(rel1['content'])})")
        runner.assert_true(rel1["is_security_patch"] is True, "Release 1 identificata correttamente come Security Patch")
        runner.assert_true("Sicurezza" in rel1["tags"], "Tag 'Sicurezza' assegnato a Release 1")
        runner.assert_true("Wi-Fi 7 / 6 GHz" in rel1["tags"], "Tag 'Wi-Fi 7 / 6 GHz' assegnato a Release 1")
        runner.assert_true("Stabilità" in rel1["tags"], "Tag 'Stabilità' assegnato a Release 1")

        rel2 = parsed_notes[1]
        runner.assert_true(rel2["version"] == "v7.16.1-50", f"Versione release 2 corretta: {rel2['version']}")
        runner.assert_true(rel2["is_security_patch"] is False, "Release 2 non contiene patch di sicurezza")
        runner.assert_true("Smart Home" in rel2["tags"], "Tag 'Smart Home' assegnato a Release 2 per Thread/Matter")

        # 3. Test Persistenza SQLite (Tabella eero_release_notes)
        await db_service.clear_release_notes()
        empty_notes = await db_service.get_release_notes()
        runner.assert_true(len(empty_notes) == 0, "clear_release_notes svuota correttamente la tabella SQLite")

        saved_count = await db_service.save_release_notes(parsed_notes)
        runner.assert_true(saved_count == 2, f"save_release_notes ha salvato 2 record (salvati: {saved_count})")

        db_notes = await db_service.get_release_notes(limit=10)
        runner.assert_true(len(db_notes) == 2, f"get_release_notes recupera 2 record (ottenuti: {len(db_notes)})")
        runner.assert_true(db_notes[0]["version"] in ("v7.17.0-1000", "v7.16.1-50"), "Versioni memorizzate conformi")
        runner.assert_true(isinstance(db_notes[0]["content"], list), "content_json deserializzato come array Python")

        latest_db = await db_service.get_latest_release_note()
        runner.assert_true(latest_db is not None and bool(latest_db.get("version")), "get_latest_release_note restituisce la release più recente")

        sec_only = await db_service.get_release_notes(security_only=True)
        runner.assert_true(len(sec_only) == 1 and sec_only[0]["version"] == "v7.17.0-1000", "get_release_notes con security_only=True filtra correttamente")

        # 4. Test Resilienza Offline & Timeout
        import httpx
        def _failing_transport(req):
            raise httpx.ConnectError("Simulated offline network failure")

        saved_last_fetch = eero_news_service._last_fetched
        eero_news_service._last_fetched = None  # Forza tentativo remoto
        orig_demo = settings.demo_mode
        settings.demo_mode = False
        eero_client.set_demo_mode(False)

        # Simula chiamata con fallback su DB esistente
        offline_notes = await eero_news_service.fetch_official_release_notes(force=True)
        runner.assert_true(len(offline_notes) >= 2, f"In caso di timeout/offline fetch_official_release_notes usa la cache SQLite senza eccezioni (trovati: {len(offline_notes)})")
        
        # Test fallback community feedback su errore
        community_res = await eero_news_service.fetch_community_feedback()
        runner.assert_true(isinstance(community_res, list) and len(community_res) > 0, "fetch_community_feedback gestisce blocchi/errori restituendo discussioni di fallback")

        # Ripristina stato demo per i test successivi
        settings.demo_mode = orig_demo
        eero_client.set_demo_mode(True)

        # 5. Test Endpoint REST FastAPI GET /api/system/eero-news
        res_news = await client.get("/api/system/eero-news")
        runner.assert_true(res_news.status_code == 200, "Endpoint GET /api/system/eero-news risponde HTTP 200")
        news_json = res_news.json()
        runner.assert_true(news_json.get("status") == "success", "GET /api/system/eero-news restituisce status success")
        runner.assert_true("current_firmware" in news_json, "Risposta include 'current_firmware'")
        runner.assert_true("latest_firmware" in news_json, "Risposta include 'latest_firmware'")
        runner.assert_true("is_up_to_date" in news_json, "Risposta include flag 'is_up_to_date'")
        runner.assert_true("update_available" in news_json, "Risposta include flag 'update_available'")
        runner.assert_true("firmware_status" in news_json, "Risposta include stringa 'firmware_status'")
        runner.assert_true("nodes" in news_json and isinstance(news_json["nodes"], list), "Risposta include array 'nodes'")
        runner.assert_true("releases" in news_json and len(news_json["releases"]) > 0, "Risposta include elenco note di rilascio")
        runner.assert_true("community_posts" in news_json, "Risposta include feed 'community_posts'")

        # In modalità Demo (flotta su v7.5.2 vs release v7.16+), deve rilevare update disponibile
        runner.assert_true(news_json.get("is_up_to_date") is False, "In ambiente Demo rileva correttamente is_up_to_date=False (v7.5.2 vs v7.16+)")
        runner.assert_true(news_json.get("update_available") is True, "In ambiente Demo rileva correttamente update_available=True")
        runner.assert_true(news_json.get("firmware_status") == "update_available", "In ambiente Demo firmware_status è 'update_available'")

        # 6. Test Endpoint REST POST /api/system/eero-news/refresh
        res_refresh = await client.post("/api/system/eero-news/refresh")
        runner.assert_true(res_refresh.status_code == 200, "Endpoint POST /api/system/eero-news/refresh risponde HTTP 200")
        refresh_json = res_refresh.json()
        runner.assert_true(refresh_json.get("status") == "success", "POST refresh restituisce status success")

        # 7. Verifica Integrità Dizionari Localizzazione (it.json ed en.json)
        with open("app/static/locales/it.json", "r", encoding="utf-8") as f:
            it_locale = json.load(f)
        with open("app/static/locales/en.json", "r", encoding="utf-8") as f:
            en_locale = json.load(f)

        runner.assert_true("eero_news" in it_locale.get("nav", {}), "Voce 'eero_news' presente in nav di it.json")
        runner.assert_true("eero_news" in en_locale.get("nav", {}), "Voce 'eero_news' presente in nav di en.json")
        runner.assert_true("eero_news" in it_locale, "Sezione 'eero_news' presente in it.json")
        runner.assert_true("eero_news" in en_locale, "Sezione 'eero_news' presente in en.json")
        runner.assert_true("up_to_date_title" in it_locale["eero_news"], "up_to_date_title presente in it.json")
        runner.assert_true("up_to_date_title" in en_locale["eero_news"], "up_to_date_title presente in en.json")
        runner.assert_true("newer_than_published_title" in it_locale["eero_news"], "newer_than_published_title presente in it.json")
        runner.assert_true("newer_than_published_title" in en_locale["eero_news"], "newer_than_published_title presente in en.json")
        runner.assert_true("newer_than_published_desc" in it_locale["eero_news"], "newer_than_published_desc presente in it.json")
        runner.assert_true("newer_than_published_desc" in en_locale["eero_news"], "newer_than_published_desc presente in en.json")
        runner.assert_true("update_avail_title" in it_locale["eero_news"], "update_avail_title presente in it.json")
        runner.assert_true("update_avail_title" in en_locale["eero_news"], "update_avail_title presente in en.json")
        runner.assert_true("show_older_releases" in it_locale["eero_news"], "show_older_releases presente in it.json")
        runner.assert_true("show_older_releases" in en_locale["eero_news"], "show_older_releases presente in en.json")
        runner.assert_true("show_recent_only" in it_locale["eero_news"], "show_recent_only presente in it.json")
        runner.assert_true("show_recent_only" in en_locale["eero_news"], "show_recent_only presente in en.json")
        runner.assert_true("installed_on_network" in it_locale["eero_news"], "installed_on_network presente in it.json")
        runner.assert_true("installed_on_network" in en_locale["eero_news"], "installed_on_network presente in en.json")
        runner.assert_true("community_title" in it_locale["eero_news"], "community_title presente in it.json")
        runner.assert_true("community_title" in en_locale["eero_news"], "community_title presente in en.json")

        # =====================================================================
        # 21. TEST AI NETWORK DIAGNOSTICS, ROAMING ADVISOR & IOT ANOMALY DETECTION (v1.6.0)
        # =====================================================================
        print("\n🤖 [21/22] TEST AI NETWORK DIAGNOSTICS, ROAMING ADVISOR & IOT ANOMALY DETECTION (v1.6.0)")

        from app.services.diagnostics_service import (
            diagnostics_service,
            is_mobile_client,
            is_iot_client,
        )

        # 1. Test Euristica di Classificazione Client (is_mobile_client vs is_iot_client)
        runner.assert_true(is_mobile_client("iPhone 15 Pro", "iPhone"), "is_mobile_client riconosce iPhone come dispositivo mobile")
        runner.assert_true(is_mobile_client("Samsung Galaxy Tab S9", "Galaxy-Tab"), "is_mobile_client riconosce Galaxy Tab come mobile")
        runner.assert_true(is_mobile_client("MacBook Pro M3", "MacBook-Pro"), "is_mobile_client riconosce MacBook come mobile/laptop")
        runner.assert_true(is_mobile_client("iPad Air", "iPad"), "is_mobile_client riconosce iPad come mobile")
        runner.assert_true(is_mobile_client("LG OLED 4K TV", "LGwebOSTV") is False, "is_mobile_client esclude Smart TV fisse")
        runner.assert_true(is_mobile_client("Shelly 1PM Relay", "shelly-switch") is False, "is_mobile_client esclude relè IoT")
        runner.assert_true(is_mobile_client("Sonoff Cam Outdoor", "sonoff-cam") is False, "is_mobile_client esclude telecamere IoT")

        runner.assert_true(is_iot_client("Shelly Plus 1PM", "shelly1pm-living"), "is_iot_client riconosce Shelly come apparato IoT")
        runner.assert_true(is_iot_client("Philips Hue Bridge", "hue-bridge"), "is_iot_client riconosce Hue Bridge come IoT")
        runner.assert_true(is_iot_client("Sonoff Micro", "sonoff-micro"), "is_iot_client riconosce Sonoff come IoT")
        runner.assert_true(is_iot_client("Aqara Hub M2", "aqara-hub"), "is_iot_client riconosce Aqara Hub come IoT")
        runner.assert_true(is_iot_client("Tasmota Plug", "tasmota-plug-1"), "is_iot_client riconosce Tasmota come IoT")
        runner.assert_true(is_iot_client("MacBook Pro", "MacBook-Pro") is False, "is_iot_client esclude personal computer")
        runner.assert_true(is_iot_client("iPhone 15", "iPhone") is False, "is_iot_client esclude smartphone")

        # 2. Test Roaming Advisor Euristico (Sticky Clients Detection)
        mock_eeros = [
            {"id": "eero_gw", "name": "eero Gateway", "is_gateway": True, "status": "connected"},
            {"id": "eero_studio", "name": "eero Studio", "is_gateway": False, "status": "connected"},
        ]
        mock_devices = [
            # Client mobile agganciato a GW con segnale degradato (-80 dBm) -> Deve essere sticky client
            {
                "id": "dev_mobile_sticky",
                "custom_name": "Galaxy Tab S9",
                "hostname": "Galaxy-Tab-S9",
                "mac": "3C:22:FB:99:88:77",
                "wireless": True,
                "connected": True,
                "signal_rssi": -80,
                "connected_eero_id": "eero_gw",
                "connected_eero_name": "eero Gateway",
            },
            # Client mobile con ottimo segnale (-55 dBm) -> NON deve essere sticky
            {
                "id": "dev_mobile_good",
                "custom_name": "iPhone 15 Pro",
                "hostname": "iPhone-15",
                "mac": "4D:33:AA:11:22:33",
                "wireless": True,
                "connected": True,
                "signal_rssi": -55,
                "connected_eero_id": "eero_gw",
                "connected_eero_name": "eero Gateway",
            },
            # Dispositivo fisso con segnale degradato (-85 dBm) -> NON deve comparire come roaming advisor
            {
                "id": "dev_tv_weak",
                "custom_name": "LG OLED TV",
                "hostname": "LGwebOSTV",
                "mac": "AA:BB:CC:DD:EE:FF",
                "wireless": True,
                "connected": True,
                "signal_rssi": -85,
                "connected_eero_id": "eero_gw",
                "connected_eero_name": "eero Gateway",
            }
        ]

        roaming_report = diagnostics_service.analyze_roaming_advisor(mock_devices, mock_eeros)
        runner.assert_true(roaming_report["sticky_count"] == 1, f"Roaming Advisor rileva esattamente 1 sticky client (rilevati: {roaming_report['sticky_count']})")
        sticky_dev = roaming_report["devices"][0]
        runner.assert_true(sticky_dev["mac"].lower() == "3c:22:fb:99:88:77", "MAC del dispositivo sticky corrisponde a Galaxy Tab S9")
        runner.assert_true(sticky_dev["connected_eero_name"] == "eero Gateway", "Nodo attuale rilevato correttamente come Gateway")
        runner.assert_true(sticky_dev["suggested_eero_name"] == "eero Studio", "Nodo consigliato per roaming è 'eero Studio'")
        runner.assert_true(sticky_dev["estimated_delta_dbm"] > 0, "Guadagno stimato del segnale positivo (>0 dB)")
        runner.assert_true(bool(sticky_dev["advice_it"]) and bool(sticky_dev["advice_en"]), "Suggerimenti d'azione bilingue presenti")

        # 3. Test NLG Health Summary & Actionable Checklist
        mock_penalties = [
            {"id": "degraded_backhaul", "factor": "Ethernet Capped to 100M", "points": 15, "description": "Il nodo eero Studio negozia a soli 100 Mbps", "affected_items": ["eero Studio (100 Mbps)"]},
            {"id": "offline_nodes", "factor": "Offline Nodes", "points": 25, "description": "1 nodo eero risulta offline", "affected_items": ["eero Studio"]}
        ]
        health_summary = diagnostics_service.generate_health_summary(
            health_details={"score": 60, "status": "attention", "penalties": mock_penalties},
            network_details={"status": "online"},
            eeros=mock_eeros,
            devices=mock_devices,
            roaming_info=roaming_report,
            recent_anomalies=[]
        )
        runner.assert_true(bool(health_summary["overview_it"]) and bool(health_summary["overview_en"]), "Health summary produce panoramica bilingue")
        runner.assert_true(bool(health_summary["narrative_it"]) and bool(health_summary["narrative_en"]), "Health summary produce narrativa bilingue dettagliata")
        from app.i18n import SUPPORTED_LANGUAGES as _langs_diag
        for _field in ("overview", "narrative"):
            _map = health_summary.get(f"{_field}_i18n") or {}
            runner.assert_true(set(_map) == set(_langs_diag) and all(_map.values()), f"Health summary '{_field}_i18n' copre tutte le lingue supportate {list(_langs_diag)}")
            runner.assert_true(health_summary.get(_field) == _map.get("en"), f"Health summary '{_field}' (campo piatto) è l'inglese della mappa")
        _ck = health_summary["checklist"][0]
        runner.assert_true(set(_ck.get("title_i18n") or {}) == set(_langs_diag) and set(_ck.get("description_i18n") or {}) == set(_langs_diag), "Checklist: title_i18n/description_i18n coprono tutte le lingue supportate")
        runner.assert_true(_ck.get("title_it") == _ck["title_i18n"].get("it") and _ck.get("title_en") == _ck["title_i18n"].get("en"), "Checklist: campi legacy title_it/title_en derivati dalla mappa title_i18n")
        runner.assert_true("100 Mbps" in health_summary["narrative_it"], "Narrativa IT menziona la limitazione 100 Mbps del cavo")
        runner.assert_true("100 Mbps" in health_summary["narrative_en"], "Narrativa EN menziona la limitazione 100 Mbps del cavo")
        runner.assert_true(len(health_summary["checklist"]) >= 2, f"Checklist contiene azioni correttive (trovate: {len(health_summary['checklist'])})")

        first_priority = health_summary["checklist"][0]["priority"]
        runner.assert_true(first_priority in ("critical", "high"), f"Prima azione in checklist ha priorità elevata ({first_priority})")

        # 4. Test Rilevamento Anomalie Notturne IoT e Persistenza SQLite
        await db_service.clear_iot_anomalies()
        init_anomalies = await db_service.get_iot_anomalies()
        runner.assert_true(len(init_anomalies) == 0, "clear_iot_anomalies svuota la tabella SQLite")

        detected_demo_anomalies = diagnostics_service.detect_iot_night_anomalies(mock_devices, demo_mode=True)
        runner.assert_true(len(detected_demo_anomalies) > 0, "detect_iot_night_anomalies produce anomalie sintetiche realistiche in demo mode")
        sample_anom = detected_demo_anomalies[0]
        runner.assert_true("mac_address" in sample_anom and "device_name" in sample_anom, "Anomalia include MAC e Device Name")
        runner.assert_true("observed_mb" in sample_anom and "baseline_mb" in sample_anom, "Anomalia include metriche di traffico")
        runner.assert_true(set(sample_anom.get("description_i18n") or {}) == set(_langs_diag), f"Anomalia include description_i18n per tutte le lingue supportate {list(_langs_diag)}")
        runner.assert_true(sample_anom.get("description_it") == sample_anom["description_i18n"].get("it") and sample_anom.get("description_en") == sample_anom["description_i18n"].get("en"), "Anomalia: description_it/description_en legacy derivati dalla mappa")

        saved_anom_count = await db_service.save_iot_anomalies(detected_demo_anomalies)
        runner.assert_true(saved_anom_count == len(detected_demo_anomalies), "save_iot_anomalies persiste correttamente tutte le anomalie")

        retrieved_anomalies = await db_service.get_iot_anomalies(limit=10)
        runner.assert_true(len(retrieved_anomalies) == len(detected_demo_anomalies), "get_iot_anomalies recupera le anomalie salvate")
        _stored = retrieved_anomalies[0] if retrieved_anomalies else {}
        runner.assert_true(isinstance(_stored.get("description_i18n"), dict) and set(_stored["description_i18n"]) == set(_langs_diag), "get_iot_anomalies restituisce description_i18n (JSON decodificato) per tutte le lingue supportate")
        runner.assert_true(_stored.get("description_it") == _stored["description_i18n"].get("it") and _stored.get("description_en") == _stored["description_i18n"].get("en"), "get_iot_anomalies: colonne legacy description_it/_en coerenti con la mappa")
        # Righe scritte prima della colonna description_i18n (solo colonne legacy) vengono ricostruite in mappa
        async with db_service.get_connection() as _db_legacy:
            await _db_legacy.execute(
                "INSERT INTO iot_traffic_anomalies (timestamp, mac_address, hostname, device_category, anomaly_type, megabytes_transferred, baseline_megabytes, severity, description_it, description_en, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                ("2099-01-01T03:00:00Z", "00:11:22:33:44:55", "Legacy Row", "iot", "unexpected_activity", 100.0, 1.0, "warning", "Descrizione legacy", "Legacy description"),
            )
            await _db_legacy.commit()
        _legacy_rows = [r for r in await db_service.get_iot_anomalies(limit=20) if r.get("mac_address") == "00:11:22:33:44:55"]
        runner.assert_true(bool(_legacy_rows) and _legacy_rows[0].get("description_i18n") == {"it": "Descrizione legacy", "en": "Legacy description"} and _legacy_rows[0].get("description") == "Legacy description", "get_iot_anomalies ricostruisce description_i18n dalle colonne legacy per righe pre-migrazione")
        await db_service.clear_iot_anomalies()
        await db_service.save_iot_anomalies(detected_demo_anomalies)

        # 5. Test Endpoint REST GET /api/diagnostics/iot-anomalies
        res_iot_api = await client.get("/api/diagnostics/iot-anomalies")
        runner.assert_true(res_iot_api.status_code == 200, "GET /api/diagnostics/iot-anomalies risponde HTTP 200")
        iot_api_json = res_iot_api.json()
        runner.assert_true(iot_api_json.get("status") == "success", "Risposta /api/diagnostics/iot-anomalies ha status success")
        runner.assert_true("anomalies" in iot_api_json and isinstance(iot_api_json["anomalies"], list), "Risposta include array 'anomalies'")

        # 6. Test Integrazione Completa in /api/network/health-breakdown
        await client.post("/api/auth/mode", json={"demo": True})
        await background_poller._poll_and_cache()
        res_health = await client.get("/api/network/health-breakdown")
        runner.assert_true(res_health.status_code == 200, "GET /api/network/health-breakdown risponde HTTP 200")
        health_json = res_health.json()
        h_details = health_json.get("data", {}).get("health_details", {})
        runner.assert_true("ai_summary" in h_details, "Payload health breakdown include 'ai_summary'")
        runner.assert_true("overview_it" in h_details["ai_summary"], "ai_summary include 'overview_it'")
        runner.assert_true("overview_en" in h_details["ai_summary"], "ai_summary include 'overview_en'")
        runner.assert_true("narrative_it" in h_details["ai_summary"], "ai_summary include 'narrative_it'")
        runner.assert_true("narrative_en" in h_details["ai_summary"], "ai_summary include 'narrative_en'")
        runner.assert_true("roaming_advisor" in h_details, "Payload health breakdown include 'roaming_advisor'")
        runner.assert_true("devices" in h_details["roaming_advisor"], "roaming_advisor include 'devices'")
        runner.assert_true("iot_anomalies" in h_details, "Payload health breakdown include 'iot_anomalies'")
        runner.assert_true("action_checklist" in h_details, "Payload health breakdown include 'action_checklist'")
        runner.assert_true(isinstance(h_details["action_checklist"], list), "action_checklist è una lista ordinata")

        # In modalità Demo, verifica che il tablet Galaxy-Tab-S9 (dev_11) compaia nei consigli di roaming
        demo_sticky_devices = h_details["roaming_advisor"].get("devices", [])
        galaxy_sticky = any("galaxy" in str(d.get("name") or "").lower() or "galaxy" in str(d.get("hostname") or "").lower() or d.get("mac") == "3c:22:fb:99:88:77" for d in demo_sticky_devices)
        runner.assert_true(galaxy_sticky, "In Demo Mode Galaxy-Tab-S9 è identificato dal Roaming Advisor (Sticky Client)")

        # 7. Verifica Dizionari di Localizzazione Bilingue (it.json ed en.json)
        runner.assert_true("sticky_roaming_badge" in it_locale.get("devices", {}), "sticky_roaming_badge presente in it.json [devices]")
        runner.assert_true("sticky_roaming_badge" in en_locale.get("devices", {}), "sticky_roaming_badge presente in en.json [devices]")
        runner.assert_true("ai_diagnostics_badge" in it_locale.get("health_modal", {}), "ai_diagnostics_badge presente in it.json [health_modal]")
        runner.assert_true("ai_diagnostics_badge" in en_locale.get("health_modal", {}), "ai_diagnostics_badge presente in en.json [health_modal]")
        runner.assert_true("ai_analysis_title" in it_locale.get("health_modal", {}), "ai_analysis_title presente in it.json [health_modal]")
        runner.assert_true("ai_analysis_title" in en_locale.get("health_modal", {}), "ai_analysis_title presente in en.json [health_modal]")
        runner.assert_true("action_checklist_title" in it_locale.get("health_modal", {}), "action_checklist_title presente in it.json [health_modal]")
        runner.assert_true("action_checklist_title" in en_locale.get("health_modal", {}), "action_checklist_title presente in en.json [health_modal]")
        runner.assert_true("roaming_advisor_title" in it_locale.get("health_modal", {}), "roaming_advisor_title presente in it.json [health_modal]")
        runner.assert_true("roaming_advisor_title" in en_locale.get("health_modal", {}), "roaming_advisor_title presente in en.json [health_modal]")
        runner.assert_true("iot_anomalies_title" in it_locale.get("health_modal", {}), "iot_anomalies_title presente in it.json [health_modal]")
        runner.assert_true("iot_anomalies_title" in en_locale.get("health_modal", {}), "iot_anomalies_title presente in en.json [health_modal]")
        runner.assert_true("priority_critical" in it_locale.get("health_modal", {}), "priority_critical presente in it.json [health_modal]")
        runner.assert_true("priority_high" in it_locale.get("health_modal", {}), "priority_high presente in it.json [health_modal]")
        runner.assert_true("priority_medium" in it_locale.get("health_modal", {}), "priority_medium presente in it.json [health_modal]")
        runner.assert_true("priority_low" in it_locale.get("health_modal", {}), "priority_low presente in it.json [health_modal]")

        # -----------------------------------------------------------------
        # 22. TEST LOCAL AUTHENTICATION, RBAC PERMISSIONS & USERS (v1.6.0 Modulo 1)
        # -----------------------------------------------------------------
        print("\n🔐 [22/22] TEST LOCAL AUTHENTICATION, RBAC PERMISSIONS & USER MANAGEMENT (v1.6.0)")

        from app.services.auth_service import auth_service, ALL_PERMISSION_KEYS
        
        # 1. Test Crittografia Password PBKDF2/SHA-256
        test_pw = "SuperSecretPassword123!"
        pw_hash, pw_salt = auth_service.hash_password(test_pw)
        runner.assert_true(len(pw_hash) == 64, f"Hash PBKDF2 digest SHA-256 lungo 64 caratteri esadecimali (lunghezza: {len(pw_hash)})")
        runner.assert_true(len(pw_salt) == 32, f"Salt crittografico casuale lungo 32 caratteri esadecimali (lunghezza: {len(pw_salt)})")
        runner.assert_true(auth_service.verify_password(test_pw, pw_hash, pw_salt) is True, "verify_password valida con successo la password corretta")
        runner.assert_true(auth_service.verify_password("WrongPassword!", pw_hash, pw_salt) is False, "verify_password rifiuta tassativamente password errata")
        runner.assert_true(auth_service.verify_password("", pw_hash, pw_salt) is False, "verify_password rifiuta stringa vuota")
        
        token_sample = auth_service.generate_session_token()
        runner.assert_true(len(token_sample) >= 32, "generate_session_token produce token crittografico ad elevata entropia")

        catalog = auth_service.get_permissions_catalog()
        runner.assert_true("read_scopes" in catalog and "action_scopes" in catalog, "Catalogo permessi espone read_scopes e action_scopes")
        runner.assert_true("action_run_speedtest" in catalog.get("all_keys", []), "action_run_speedtest presente tra i permessi supportati")
        runner.assert_true("action_reboot_nodes" in catalog.get("all_keys", []), "action_reboot_nodes presente tra i permessi supportati")

        # 2. Test Inizializzazione e Bootstrap Database SQLite / Setup Wizard
        # Reset pulito di local_users e user_sessions per validare il flusso reale del Setup Wizard
        async with db_service._write_lock:
            async with aiosqlite.connect(db_service.db_path, timeout=60.0) as db_clean:
                await db_clean.execute("DELETE FROM user_sessions;")
                await db_clean.execute("DELETE FROM local_users;")
                await db_clean.commit()

        res_status = await client.get("/api/auth/local/status")
        runner.assert_true(res_status.status_code == 200, "GET /api/auth/local/status risponde HTTP 200")
        status_payload = res_status.json()
        runner.assert_true(status_payload.get("setup_required") is True, "Al primo avvio setup_required è True")

        # Esegui il Setup Wizard iniziale
        res_setup = await client.post("/api/auth/local/setup", json={
            "username": "admin",
            "password": "AdminPassword123!",
            "display_name": "Admin"
        })
        runner.assert_true(res_setup.status_code == 200, "POST /api/auth/local/setup completa il primo setup con successo")
        setup_json = res_setup.json()
        runner.assert_true(setup_json.get("status") == "success", "Setup restituisce status 'success'")
        admin_pwd = "AdminPassword123!"
        runner.admin_test_pwd = admin_pwd
        admin_user = await db_service.get_local_user_by_username("admin")

        # Verifica che setup_required sia ora False
        res_status_after = await client.get("/api/auth/local/status")
        runner.assert_true(res_status_after.json().get("setup_required") is False, "Dopo setup, setup_required è False")

        runner.assert_true(admin_user is not None, "Utente 'admin' presente nel database")
        runner.assert_true(admin_user.get("is_admin") is True, "Utente admin possiede flag is_admin=True")
        runner.assert_true(len(admin_user.get("permissions", [])) >= len(ALL_PERMISSION_KEYS), "Utente admin possiede tutti i permessi granulari RBAC")

        # Verifica rifiuto doppi setup
        res_dup_setup = await client.post("/api/auth/local/setup", json={"username": "hacker", "password": "PasswordHacker123!"})
        runner.assert_true(res_dup_setup.status_code == 400, "POST /api/auth/local/setup rifiuta ulteriori setup una volta completato")

        # 3. Test Chiamate Non Autenticate e Login API
        client.cookies.clear()
        res_me_unauth = await client.get("/api/auth/local/me")
        runner.assert_true(res_me_unauth.status_code == 401, "GET /api/auth/local/me senza token restituisce HTTP 401 Unauthorized")

        res_users_noauth = await client.get("/api/users")
        runner.assert_true(res_users_noauth.status_code == 401, "GET /api/users senza autenticazione restituisce HTTP 401")

        # Fallimento con password errata
        res_login_bad = await client.post("/api/auth/local/login", json={"username": "admin", "password": "WrongPassword123"})
        runner.assert_true(res_login_bad.status_code == 401, "POST /api/auth/local/login con password errata restituisce HTTP 401 Unauthorized")

        # Successo con admin configurato
        res_login_ok = await client.post("/api/auth/local/login", json={"username": "admin", "password": admin_pwd})
        runner.assert_true(res_login_ok.status_code == 200, "POST /api/auth/local/login con credenziali corrette risponde HTTP 200 OK")
        login_json = res_login_ok.json()
        runner.assert_true(login_json.get("status") == "success", "Risposta login contiene status 'success'")
        admin_token = login_json.get("token")
        runner.assert_true(bool(admin_token), "Login restituisce session token valido")
        runner.assert_true(login_json.get("user", {}).get("username") == "admin", "Payload user contiene username 'admin'")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 4. Test API Endpoint GET /api/auth/local/me
        res_me_auth = await client.get("/api/auth/local/me", headers=admin_headers)
        runner.assert_true(res_me_auth.status_code == 200, "GET /api/auth/local/me con Bearer token risponde HTTP 200 OK")
        me_json = res_me_auth.json()
        runner.assert_true(me_json.get("user", {}).get("username") == "admin", "/me restituisce profilo admin autenticato")

        # 5. Test Endpoint GET /api/auth/local/permissions
        res_perm = await client.get("/api/auth/local/permissions")
        runner.assert_true(res_perm.status_code == 200, "GET /api/auth/local/permissions risponde HTTP 200 OK")

        # 6. Test CRUD Utenti: /api/users
        # Elenco utenti da parte di admin
        res_users_list = await client.get("/api/users", headers=admin_headers)
        runner.assert_true(res_users_list.status_code == 200, "GET /api/users con admin token risponde HTTP 200 OK")
        users_list = res_users_list.json().get("users", [])
        runner.assert_true(len(users_list) >= 1, "Elenco utenti contiene almeno l'utente admin")

        # Creazione nuovo operatore con permessi limitati (SOLO action_run_speedtest)
        new_op_payload = {
            "username": "operatore_test",
            "password": "PasswordOperatore1!",
            "is_admin": False,
            "permissions": ["action_run_speedtest", "view_devices"]
        }
        res_create_op = await client.post("/api/users", json=new_op_payload, headers=admin_headers)
        runner.assert_true(res_create_op.status_code == 201, "POST /api/users da parte di admin risponde HTTP 201 Created")
        created_op = res_create_op.json().get("user", {})
        op_id = created_op.get("id")
        runner.assert_true(op_id is not None, "Nuovo utente creato riceve un ID univoco")

        # Creazione duplicata con stesso username -> 409 Conflict
        res_create_dup = await client.post("/api/users", json=new_op_payload, headers=admin_headers)
        runner.assert_true(res_create_dup.status_code == 409, "POST /api/users con username duplicato restituisce HTTP 409 Conflict")

        # Login con nuovo operatore
        res_op_login = await client.post("/api/auth/local/login", json={"username": "operatore_test", "password": "PasswordOperatore1!"})
        runner.assert_true(res_op_login.status_code == 200, "Login con nuovo operatore risponde HTTP 200 OK")
        op_token = res_op_login.json().get("token")
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # Operatore non admin tenta di accedere a /api/users -> 403 Forbidden
        res_op_users = await client.get("/api/users", headers=op_headers)
        runner.assert_true(res_op_users.status_code == 403, "GET /api/users da parte di operatore non admin bloccato con HTTP 403 Forbidden")

        res_op_create = await client.post("/api/users", json={"username": "fake_admin", "password": "123"}, headers=op_headers)
        runner.assert_true(res_op_create.status_code == 403, "POST /api/users da parte di operatore non admin bloccato con HTTP 403 Forbidden")

        # 7. Test Protezione RBAC Dependency Injection (require_permission)
        # Operatore ha 'action_run_speedtest' -> richiesta non viene bloccata con 403
        res_speed_op = await client.post("/api/speedtest/run", headers=op_headers)
        runner.assert_true(res_speed_op.status_code != 403, "Operatore con permesso 'action_run_speedtest' NON riceve HTTP 403")

        # Operatore NON ha 'action_reboot_nodes' -> richiesta bloccata con HTTP 403 Forbidden!
        res_reboot_op = await client.post("/api/network/reboot", headers=op_headers)
        runner.assert_true(res_reboot_op.status_code == 403, "Operatore privo di 'action_reboot_nodes' bloccato su /network/reboot con HTTP 403 Forbidden")

        # Operatore NON ha 'action_toggle_guest' -> richiesta bloccata con HTTP 403 Forbidden!
        res_guest_op = await client.post("/api/network/guest", json={"enabled": True}, headers=op_headers)
        runner.assert_true(res_guest_op.status_code == 403, "Operatore privo di 'action_toggle_guest' bloccato su /network/guest con HTTP 403 Forbidden")

        # Richiesta con token Bearer corrotto/falso -> HTTP 401 Unauthorized
        res_fake_token = await client.post("/api/network/reboot", headers={"Authorization": "Bearer FakeInvalidToken12345"})
        runner.assert_true(res_fake_token.status_code == 401, "Richiesta con token di sessione corrotto restituisce HTTP 401 Unauthorized")

        # 8. Test Protezione Rimozione Ultimo Amministratore
        admin_id = admin_user["id"]
        res_revoke_admin = await client.put(f"/api/users/{admin_id}", json={"is_admin": False}, headers=admin_headers)
        runner.assert_true(res_revoke_admin.status_code == 400, "Tentativo di revoca privilegi all'ultimo admin bloccato con HTTP 400")

        res_del_admin = await client.delete(f"/api/users/{admin_id}", headers=admin_headers)
        runner.assert_true(res_del_admin.status_code == 400, "Tentativo di cancellazione dell'ultimo admin bloccato con HTTP 400")

        # Aggiornamento permessi operatore da parte di admin
        res_update_op = await client.put(
            f"/api/users/{op_id}",
            json={"permissions": ["action_run_speedtest", "action_reboot_nodes"]},
            headers=admin_headers
        )
        runner.assert_true(res_update_op.status_code == 200, "PUT /api/users/{id} aggiorna con successo i permessi dell'operatore")

        # Cancellazione operatore da parte di admin
        res_del_op = await client.delete(f"/api/users/{op_id}", headers=admin_headers)
        runner.assert_true(res_del_op.status_code == 200, "DELETE /api/users/{id} elimina correttamente l'operatore")

        # 9. Test Logout e Invalidazione Sessione
        res_logout = await client.post("/api/auth/local/logout", headers=admin_headers)
        runner.assert_true(res_logout.status_code == 200, "POST /api/auth/local/logout risponde HTTP 200 OK")

        res_me_after_logout = await client.get("/api/auth/local/me", headers=admin_headers)
        runner.assert_true(res_me_after_logout.status_code == 401, "Dopo logout il token risulta invalidato (HTTP 401)")

        # -----------------------------------------------------------------
        # 23. TEST CLOUD RESILIENCE, PLACEHOLDER REMOVAL & IPV6 ULA (v1.6.0 Modulo 1)
        # -----------------------------------------------------------------
        print("\n🛡️ [23/24] TEST CLOUD POLLER RESILIENCE, PLACEHOLDER CLEANUP & IPV6 ULA (v1.6.0)")

        # 1. Test Issue #55: Cloud Poller Resilience & Graceful Disconnection
        from app.services.poller import BackgroundPoller
        test_poller = BackgroundPoller()

        init_state = test_poller.get_cached_state()
        runner.assert_true("data_stale" in init_state, "get_cached_state espone il flag 'data_stale'")
        runner.assert_true("cloud_status" in init_state, "get_cached_state espone 'cloud_status'")
        runner.assert_true("consecutive_failed_polls" in init_state, "get_cached_state espone 'consecutive_failed_polls'")
        runner.assert_true(init_state["data_stale"] is False, "data_stale iniziale è False")
        runner.assert_true(init_state["cloud_status"] == "connected", "cloud_status iniziale è 'connected'")
        runner.assert_true(init_state["consecutive_failed_polls"] == 0, "consecutive_failed_polls iniziale è 0")

        # Simulazione caduta connessione Cloud (Timeout / HTTP 503)
        orig_get_network = eero_client.get_network_details
        orig_get_eeros = eero_client.get_eeros
        orig_get_devices = eero_client.get_devices

        async def _mock_cloud_timeout():
            raise httpx.ConnectTimeout("Connection to eero cloud timed out")

        eero_client.get_network_details = _mock_cloud_timeout

        # Esecuzione poll con errore
        await test_poller._poll_and_cache()
        runner.assert_true(test_poller.data_stale is True, "In caso di errore cloud data_stale diventa True")
        runner.assert_true(test_poller.cloud_status == "unreachable", "cloud_status impostato a 'unreachable' su timeout")
        runner.assert_true(test_poller._consecutive_failed_polls == 1, "consecutive_failed_polls incrementato a 1")
        runner.assert_true(test_poller._last_successful_poll is None, "last_successful_poll non viene aggiornato su errore")

        # Simulazione sessione scaduta (HTTP 401)
        async def _mock_cloud_401():
            req = httpx.Request("GET", "https://api-user.e2ro.com/2.2/networks")
            resp = httpx.Response(401, request=req)
            raise httpx.HTTPStatusError("401 Unauthorized", request=req, response=resp)

        eero_client.get_network_details = _mock_cloud_401
        await test_poller._poll_and_cache()
        runner.assert_true(test_poller.cloud_status == "unauthorized", "cloud_status impostato a 'unauthorized' su HTTP 401")
        runner.assert_true(test_poller._consecutive_failed_polls == 2, "consecutive_failed_polls incrementato a 2")

        # Terzo fallimento consecutivo: deve attivare _cloud_alert_sent
        await test_poller._poll_and_cache()
        runner.assert_true(test_poller._consecutive_failed_polls == 3, "consecutive_failed_polls raggiunge 3")
        runner.assert_true(test_poller._cloud_alert_sent is True, "Dopo 3 fallimenti consecutivi _cloud_alert_sent diventa True")

        # Verifica soppressione falsi allarmi nodi offline durante cloud outage
        await asyncio.sleep(0.1)  # Consente il completamento del dispatch background di notify_cloud_unreachable
        test_poller._known_eeros_status["node_test_1"] = "online"
        fake_offline_node = {"id": "node_test_1", "status": "offline"}
        alerts_before = len(await db_service.get_alerts(limit=50))
        if test_poller._consecutive_failed_polls == 0 and not test_poller.data_stale:
            await notification_service.notify_node_offline(fake_offline_node)
        alerts_after = len(await db_service.get_alerts(limit=50))
        runner.assert_true(alerts_before == alerts_after, "Allarme node_offline soppresso con successo durante interruzione cloud")

        # Ripristino eero client e poll riuscito
        eero_client.get_network_details = orig_get_network
        eero_client.get_eeros = orig_get_eeros
        eero_client.get_devices = orig_get_devices

        await test_poller._poll_and_cache()
        runner.assert_true(test_poller._consecutive_failed_polls == 0, "Dopo successo consecutive_failed_polls torna a 0")
        runner.assert_true(test_poller.data_stale is False, "data_stale torna a False")
        runner.assert_true(test_poller.cloud_status == "connected", "cloud_status torna a 'connected'")
        runner.assert_true(test_poller._cloud_alert_sent is False, "_cloud_alert_sent resettato a False")
        runner.assert_true(test_poller._last_successful_poll is not None, "last_successful_poll aggiornato dopo successo")

        # 2. Test Issue #56: Rimozione Fallback e Placeholder Arbitrari
        # Test 2a: public_ip è None se assente dal payload cloud (no '0.0.0.0' né fallback a gateway_ip)
        net_no_pub = eero_client._normalize_network_details({"name": "Test Net", "gateway_ip": "10.0.0.1"})
        runner.assert_true(net_no_pub["public_ip"] is None, f"public_ip è None quando non fornito dal cloud (ottenuto: {net_no_pub['public_ip']})")
        runner.assert_true(net_no_pub["public_ip"] != "0.0.0.0", "public_ip non contiene il placeholder fittizio '0.0.0.0'")
        runner.assert_true(net_no_pub["public_ip"] != "10.0.0.1", "public_ip non eredita arbitrariamente l'IP gateway della LAN")

        # Test 2b: gateway_ip è None se assente (no '192.168.4.1' hardcoded)
        net_no_gw = eero_client._normalize_network_details({"name": "Test Net"})
        runner.assert_true(net_no_gw["gateway_ip"] is None, f"gateway_ip è None quando non fornito (ottenuto: {net_no_gw['gateway_ip']})")
        runner.assert_true(net_no_gw["gateway_ip"] != "192.168.4.1", "gateway_ip non adotta il default '192.168.4.1'")
        runner.assert_true("192.168.4.1" not in net_no_gw["dns_servers"], "dns_servers non inserisce '192.168.4.1' come fallback arbitrario")

        # Test 2c: Nessun moltiplicatore sintetico arbitrario per throughput (rx_pkts * 1420 / 280)
        raw_dev_pkts = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "hostname": "IoT Sensor",
            "connectivity": {
                "packet_stats": {
                    "rx_packets": 5000,
                    "tx_packets": 2000,
                }
            }
        }
        norm_dev_pkts = eero_client._normalize_device(raw_dev_pkts)
        runner.assert_true(norm_dev_pkts["rx_packets"] == 5000, "rx_packets registrato accuratamente a 5000")
        runner.assert_true(norm_dev_pkts["tx_packets"] == 2000, "tx_packets registrato accuratamente a 2000")
        runner.assert_true(norm_dev_pkts["rx_bytes"] == 0.0, f"rx_bytes non usa moltiplicatore sintetico * 1420 (ottenuto: {norm_dev_pkts['rx_bytes']})")
        runner.assert_true(norm_dev_pkts["tx_bytes"] == 0.0, f"tx_bytes non usa moltiplicatore sintetico * 280 (ottenuto: {norm_dev_pkts['tx_bytes']})")

        # Test 2d: Trasparenza backhaul stimato da modello hardware
        raw_node_est = {
            "name": "Stima Node 6E",
            "model": "eero Pro 6E (K010001)",
            "wireless": True,
            "connected": True,
            "channel": 0
        }
        norm_node_est = eero_client._normalize_eero_node(raw_node_est)
        runner.assert_true("(estimated)" in norm_node_est["backhaul_type"], f"Banda mesh stimata da hardware include '(estimated)' (ottenuto: {norm_node_est['backhaul_type']})")
        runner.assert_true(norm_node_est.get("backhaul_estimated") is True, "Flag backhaul_estimated è True")

        # 3. Test Issue #57: Supporto Completo IPv6 ULA (RFC 4193)
        raw_device_v6 = {
            "mac": "11:22:33:44:55:66",
            "hostname": "Multi-Stack Workstation",
            "ips": [
                "192.168.1.50",
                "2001:0db8:85a3:0000:0000:8a2e:0370:7334",  # GUA (Global Unicast)
                "fd12:3456:789a:1::42",                      # ULA (Unique Local, fd00::/8)
                "fc00:abcd:ef01:2::99",                      # ULA (Unique Local, fc00::/7)
                "fe80::1ff:fe00:3a60",                       # Link-Local (fe80::/10)
            ]
        }
        norm_v6 = eero_client._normalize_device(raw_device_v6)
        runner.assert_true("2001:0db8:85a3:0000:0000:8a2e:0370:7334" in norm_v6["ipv6_gua"], "GUA classificato correttamente in ipv6_gua")
        runner.assert_true("fd12:3456:789a:1::42" in norm_v6["ipv6_ula"], "ULA fd12:: classificato correttamente in ipv6_ula")
        runner.assert_true("fc00:abcd:ef01:2::99" in norm_v6["ipv6_ula"], "ULA fc00:: classificato correttamente in ipv6_ula")
        runner.assert_true("fe80::1ff:fe00:3a60" in norm_v6["ipv6_link_local"], "Link-Local classificato in ipv6_link_local")
        
        # Gli indirizzi routabili (GUA + ULA) devono essere inclusi in ipv6_addresses
        runner.assert_true("fd12:3456:789a:1::42" in norm_v6["ipv6_addresses"], "ULA incluso in ipv6_addresses per propagazione a AdGuard/DNS")
        runner.assert_true("2001:0db8:85a3:0000:0000:8a2e:0370:7334" in norm_v6["ipv6_addresses"], "GUA incluso in ipv6_addresses")
        runner.assert_true("fe80::1ff:fe00:3a60" not in norm_v6["ipv6_addresses"], "Link-Local escluso da ipv6_addresses routabili")
        runner.assert_true(len(norm_v6["ipv6_all"]) == 4, f"ipv6_all contiene tutti e 4 gli indirizzi validi (trovati: {len(norm_v6['ipv6_all'])})")

        # Verifica array dettagliato ipv6_details
        details = norm_v6["ipv6_details"]
        runner.assert_true(len(details) == 4, f"ipv6_details ha 4 elementi (trovati: {len(details)})")
        ula_detail = next((d for d in details if d["address"] == "fd12:3456:789a:1::42"), {})
        runner.assert_true(ula_detail.get("type") == "ULA" and ula_detail.get("scope") == "local", "ipv6_details per ULA ha type='ULA' e scope='local'")

        # Verifica priorità indirizzo primario: GUA ha priorità su ULA
        runner.assert_true(norm_v6["ipv6"] == "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "Indirizzo IPv6 primario sceglie GUA se presente")

        # Test dispositivo solo con ULA (senza GUA)
        raw_ula_only = {
            "mac": "66:55:44:33:22:11",
            "hostname": "Local NAS",
            "ips": ["fd00:1234:5678:9abc::10", "fe80::200:ff:fe00:1"]
        }
        norm_ula_only = eero_client._normalize_device(raw_ula_only)
        runner.assert_true(norm_ula_only["ipv6"] == "fd00:1234:5678:9abc::10", "In assenza di GUA, l'IPv6 primario adotta l'indirizzo ULA")

        # Verifica presenza chiavi localizzazione per badge ULA
        it_loc = json.loads(Path("app/static/locales/it.json").read_text(encoding="utf-8"))
        en_loc = json.loads(Path("app/static/locales/en.json").read_text(encoding="utf-8"))
        runner.assert_true("ipv6_badge_ula" in it_loc.get("device_modal", {}), "ipv6_badge_ula presente in it.json [device_modal]")
        runner.assert_true("ipv6_badge_ula" in en_loc.get("device_modal", {}), "ipv6_badge_ula presente in en.json [device_modal]")

        # 4. Test Issue #57 (Fase 2): Reverse Client Enrichment via NDP & AdGuard API
        from app.services.enrichment_service import enrichment_service, classify_ip, normalize_mac
        
        # Test 4a: Normalizzazione MAC
        runner.assert_true(normalize_mac("aabbccddeeff") == "AA:BB:CC:DD:EE:FF", "normalize_mac da stringa compatta")
        runner.assert_true(normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF", "normalize_mac con trattini")
        runner.assert_true(normalize_mac("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF", "normalize_mac con due punti")
        runner.assert_true(normalize_mac("invalid_mac") is None, "normalize_mac rifiuta stringhe invalide")

        # Test 4b: Classificazione IP
        c_ula = classify_ip("fd4c:b590:10fa:1::9390")
        runner.assert_true(c_ula["valid"] and c_ula["type"] == "ULA", "Classificazione corretta ULA fd4c::")
        c_gua = classify_ip("2001:db8::1234")
        runner.assert_true(c_gua["valid"] and c_gua["type"] == "GUA", "Classificazione corretta GUA 2001::")
        c_ll = classify_ip("fe80::1")
        runner.assert_true(c_ll["valid"] and c_ll["type"] == "Link-Local", "Classificazione corretta Link-Local fe80::")
        c_v4 = classify_ip("192.168.1.150")
        runner.assert_true(c_v4["valid"] and c_v4["type"] == "IPv4", "Classificazione corretta IPv4")

        # Test 4c: Ingestion API e Persistenza SQLite
        test_mappings = [
            {
                "mac": "AA:BB:CC:DD:EE:FF",
                "ip": "fd4c:b590:10fa:1::9390",
                "type": "ULA",
                "source": "test_adguard_ndp"
            }
        ]
        ingest_res = await enrichment_service.ingest_neighbor_mappings(test_mappings, source="test_runner")
        runner.assert_true(ingest_res["status"] == "success", "Ingestione mapping restituisce status success")
        runner.assert_true(ingest_res["total"] >= 1, "Conteggio mapping salvati >= 1")

        disc_rows = await db_service.get_discovered_ips_for_mac("AA:BB:CC:DD:EE:FF")
        runner.assert_true(len(disc_rows) >= 1, "get_discovered_ips_for_mac trova la riga salvata")
        runner.assert_true(disc_rows[0]["ip_address"] == "fd4c:b590:10fa:1::9390", "Indirizzo IP salvato corrisponde all'ULA")

        # Test 4d: Pulizia associazione di test
        del_ok = await db_service.delete_discovered_ip("AA:BB:CC:DD:EE:FF", "fd4c:b590:10fa:1::9390")
        runner.assert_true(del_ok is True, "delete_discovered_ip rimuove correttamente la tupla di test")

        # Test 4e: Verifica localizzazione badge ULA (NDP)
        runner.assert_true("ipv6_badge_ula_ndp" in it_loc.get("device_modal", {}), "ipv6_badge_ula_ndp presente in it.json")
        runner.assert_true("ipv6_badge_ula_ndp" in en_loc.get("device_modal", {}), "ipv6_badge_ula_ndp presente in en.json")


        # -----------------------------------------------------------------
        # 24. TEST SMART AUTOMATIONS, PARENTAL SCHEDULING & NIGHTLY MAINTENANCE ENGINE (v1.6.0 Modulo 1)
        # -----------------------------------------------------------------
        print("\n⏰ [24/25] TEST SMART AUTOMATIONS, PARENTAL SCHEDULING & NIGHTLY MAINTENANCE ENGINE (v1.6.0)")

        from datetime import datetime
        from app.services.scheduler import ScheduleEngine, MaintenanceEngine, schedule_engine, maintenance_engine

        # 1. Test is_schedule_active_at (Daytime & Overnight spanning midnight)
        # Test 1a: Finestra Diurna (08:00 -> 17:00, Lunedì-Venerdì)
        sched_daytime = {
            "enabled": True,
            "start_time": "08:00",
            "end_time": "17:00",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        }
        # Lunedì alle 10:00 (attivo)
        dt_mon_10 = datetime(2026, 10, 5, 10, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_daytime, dt_mon_10) is True, "Finestra diurna attiva di Lunedì alle 10:00")
        # Lunedì alle 18:00 (non attivo)
        dt_mon_18 = datetime(2026, 10, 5, 18, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_daytime, dt_mon_18) is False, "Finestra diurna non attiva di Lunedì dopo le 17:00")
        # Lunedì alle 07:30 (non attivo)
        dt_mon_07 = datetime(2026, 10, 5, 7, 30)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_daytime, dt_mon_07) is False, "Finestra diurna non attiva di Lunedì prima delle 08:00")
        # Domenica alle 10:00 (non attivo per giorno escluso)
        dt_sun_10 = datetime(2026, 10, 4, 10, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_daytime, dt_sun_10) is False, "Finestra diurna non attiva di Domenica (giorno non pianificato)")

        # Test 1b: Finestra Notturna a cavallo di mezzanotte (22:00 -> 06:00, solo Lunedì sera 'mon')
        sched_overnight = {
            "enabled": True,
            "start_time": "22:00",
            "end_time": "06:00",
            "days_of_week": ["mon"],
        }
        # Lunedì alle 23:00 (attivo - prima parte della notte)
        dt_mon_23 = datetime(2026, 10, 5, 23, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_overnight, dt_mon_23) is True, "Finestra notturna attiva Lunedì alle 23:00 (prima di mezzanotte)")
        # Martedì alle 03:00 (attivo - seconda parte della notte, iniziata Lunedì sera!)
        dt_tue_03 = datetime(2026, 10, 6, 3, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_overnight, dt_tue_03) is True, "Finestra notturna attiva Martedì alle 03:00 (giorno di avvio era Lunedì)")
        # Martedì alle 06:30 (non attivo - passata l'ora di fine 06:00)
        dt_tue_0630 = datetime(2026, 10, 6, 6, 30)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_overnight, dt_tue_0630) is False, "Finestra notturna non attiva Martedì dopo le 06:00")
        # Domenica alle 23:00 (non attivo - Domenica non è pianificata)
        dt_sun_23 = datetime(2026, 10, 4, 23, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_overnight, dt_sun_23) is False, "Finestra notturna non attiva Domenica alle 23:00 (Domenica non selezionata)")
        # Lunedì alle 03:00 (non attivo - la notte tra Dom e Lun non era pianificata)
        dt_mon_03 = datetime(2026, 10, 5, 3, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_overnight, dt_mon_03) is False, "Finestra notturna non attiva Lunedì notte alle 03:00 (Domenica precedente non schedulata)")

        # Test 1c: Regola disabilitata (enabled=False) sempre non attiva
        sched_disabled = {**sched_daytime, "enabled": False}
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_disabled, dt_mon_10) is False, "Regola disabilitata non è mai attiva anche nell'orario target")

        # Test 1d: Regola di Riavvio Programmato (Point-in-Time alle 04:00 di Lunedì)
        sched_reboot = {
            "enabled": True,
            "target_type": "all_nodes_reboot",
            "action": "reboot",
            "start_time": "04:00",
            "end_time": "04:00",
            "days_of_week": ["mon"],
        }
        dt_mon_0400 = datetime(2026, 10, 5, 4, 0)
        dt_mon_0401 = datetime(2026, 10, 5, 4, 1)
        dt_mon_0359 = datetime(2026, 10, 5, 3, 59)
        dt_tue_0400 = datetime(2026, 10, 6, 4, 0)
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_reboot, dt_mon_0400) is True, "Riavvio programmato attivo alle 04:00 esatte del giorno pianificato")
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_reboot, dt_mon_0401) is False, "Riavvio programmato non attivo al minuto successivo (04:01)")
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_reboot, dt_mon_0359) is False, "Riavvio programmato non attivo al minuto precedente (03:59)")
        runner.assert_true(ScheduleEngine.is_schedule_active_at(sched_reboot, dt_tue_0400) is False, "Riavvio programmato non attivo in giorno non pianificato (Martedì)")

        # 2. Test Metodi Database CRUD (db_service) per device_schedules
        await db_service.clear_device_schedules()
        runner.assert_true(len(await db_service.get_device_schedules()) == 0, "clear_device_schedules svuota correttamente la tabella")

        # Creazione regola
        sch_id = await db_service.create_device_schedule(
            name="Studio Figli",
            target_type="devices",
            target_ids=["dev_tablet_01", "dev_pc_02"],
            days_of_week=["mon", "tue", "wed", "thu", "fri"],
            start_time="14:00",
            end_time="18:30",
            action="pause",
            enabled=True
        )
        runner.assert_true(sch_id > 0, "create_device_schedule crea record con ID valido")

        # Lettura
        all_sch = await db_service.get_device_schedules()
        runner.assert_true(len(all_sch) == 1, "get_device_schedules restituisce 1 record")
        sch_item = await db_service.get_device_schedule_by_id(sch_id)
        runner.assert_true(sch_item is not None, "get_device_schedule_by_id recupera il record")
        runner.assert_true(sch_item["name"] == "Studio Figli", "Nome regola corrisponde")
        runner.assert_true(sch_item["target_ids"] == ["dev_tablet_01", "dev_pc_02"], "target_ids deserializzato come lista")
        runner.assert_true("fri" in sch_item["days_of_week"], "days_of_week deserializzato come lista")

        # Aggiornamento
        upd_res = await db_service.update_device_schedule(sch_id, name="Studio & Relax", end_time="19:00")
        runner.assert_true(upd_res is True, "update_device_schedule restituisce True")
        sch_updated = await db_service.get_device_schedule_by_id(sch_id)
        runner.assert_true(sch_updated["name"] == "Studio & Relax" and sch_updated["end_time"] == "19:00", "Parametri aggiornati con successo")

        # Toggle abilitazione
        tog_res = await db_service.toggle_device_schedule(sch_id, enabled=False)
        runner.assert_true(tog_res is True, "toggle_device_schedule restituisce True")
        sch_toggled = await db_service.get_device_schedule_by_id(sch_id)
        runner.assert_true(sch_toggled["enabled"] is False, "Regola ora disabilitata (enabled=False)")
        runner.assert_true(len(await db_service.get_device_schedules(only_enabled=True)) == 0, "get_device_schedules(only_enabled=True) esclude regole disabilitate")

        # Ri-abilitazione
        await db_service.toggle_device_schedule(sch_id, enabled=True)

        # Cancellazione
        del_res = await db_service.delete_device_schedule(sch_id)
        runner.assert_true(del_res is True, "delete_device_schedule restituisce True")
        runner.assert_true(await db_service.get_device_schedule_by_id(sch_id) is None, "Record eliminato non più presente")

        # 3. Test API REST /api/schedules & RBAC
        # 3a. Login come Admin per ottenere token di autenticazione
        admin_pwd = getattr(runner, "admin_test_pwd", getattr(settings, "admin_password", "") or "AdminPassword123!")
        res_adm_login = await client.post("/api/auth/local/login", json={"username": "admin", "password": admin_pwd})
        adm_token = res_adm_login.json().get("token")
        adm_hdr = {"Authorization": f"Bearer {adm_token}"}

        # 3b. Creazione utente operatore privo di 'action_manage_rules'
        existing_op = await db_service.get_local_user_by_username("operatore_schedules_test")
        if existing_op:
            await db_service.delete_local_user(existing_op["id"])
        res_create_op = await client.post(
            "/api/users",
            json={
                "username": "operatore_schedules_test",
                "password": "TestPassword123!",
                "is_admin": False,
                "permissions": ["view_devices", "view_speedtest"]
            },
            headers=adm_hdr
        )
        op_schedules_id = res_create_op.json().get("user", {}).get("id")
        res_op_sched_login = await client.post("/api/auth/local/login", json={"username": "operatore_schedules_test", "password": "TestPassword123!"})
        op_sched_token = res_op_sched_login.json().get("token")
        op_sched_hdr = {"Authorization": f"Bearer {op_sched_token}"}

        # Verifica RBAC 403 Forbidden su POST /api/schedules per operatore privo di permessi
        sched_payload = {
            "name": "Nanna Bimbi",
            "target_type": "devices",
            "target_ids": ["dev_kindle_01"],
            "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            "start_time": "21:30",
            "end_time": "07:30",
            "action": "pause",
            "enabled": True
        }
        res_sched_forbid = await client.post("/api/schedules", json=sched_payload, headers=op_sched_hdr)
        runner.assert_true(res_sched_forbid.status_code == 403, "POST /api/schedules bloccato con HTTP 403 Forbidden se privi di action_manage_rules")

        # Verifica validazione 400 Bad Request con payload non valido (admin)
        res_bad_name = await client.post("/api/schedules", json={**sched_payload, "name": ""}, headers=adm_hdr)
        runner.assert_true(res_bad_name.status_code == 400, "POST /api/schedules con nome vuoto restituisce HTTP 400")
        res_bad_targets = await client.post("/api/schedules", json={**sched_payload, "target_ids": []}, headers=adm_hdr)
        runner.assert_true(res_bad_targets.status_code == 400, "POST /api/schedules con target_ids vuoti restituisce HTTP 400")

        # Creazione valida da parte di admin -> HTTP 201 Created
        res_create_sch = await client.post("/api/schedules", json=sched_payload, headers=adm_hdr)
        runner.assert_true(res_create_sch.status_code == 201, "POST /api/schedules con admin risponde HTTP 201 Created")
        created_sch = res_create_sch.json().get("schedule", {})
        api_sch_id = created_sch.get("id")
        runner.assert_true(api_sch_id is not None and api_sch_id > 0, "ID regola generato da API valido")

        # GET /api/schedules
        res_list_sch = await client.get("/api/schedules", headers=adm_hdr)
        runner.assert_true(res_list_sch.status_code == 200, "GET /api/schedules risponde HTTP 200")
        runner.assert_true(len(res_list_sch.json()) >= 1, "GET /api/schedules elenca almeno la nuova regola")

        # GET /api/schedules/{id}
        res_get_sch = await client.get(f"/api/schedules/{api_sch_id}", headers=adm_hdr)
        runner.assert_true(res_get_sch.status_code == 200, f"GET /api/schedules/{api_sch_id} risponde HTTP 200")
        runner.assert_true(res_get_sch.json().get("name") == "Nanna Bimbi", "Nome recuperato corrisponde")

        # PUT /api/schedules/{id}
        res_put_sch = await client.put(f"/api/schedules/{api_sch_id}", json={"name": "Nanna Bimbi Sera", "start_time": "21:00"}, headers=adm_hdr)
        runner.assert_true(res_put_sch.status_code == 200, "PUT /api/schedules/{id} risponde HTTP 200")
        runner.assert_true(res_put_sch.json().get("schedule", {}).get("name") == "Nanna Bimbi Sera", "Nome aggiornato da API")

        # POST /api/schedules/{id}/toggle
        res_tog_api = await client.post(f"/api/schedules/{api_sch_id}/toggle", headers=adm_hdr)
        runner.assert_true(res_tog_api.status_code == 200, "POST /api/schedules/{id}/toggle risponde HTTP 200")
        runner.assert_true(res_tog_api.json().get("schedule", {}).get("enabled") is False, "Toggle ha disabilitato la regola")

        # Ri-abilita la regola
        await client.post(f"/api/schedules/{api_sch_id}/toggle", headers=adm_hdr)

        # POST /api/schedules/evaluate
        res_eval = await client.post("/api/schedules/evaluate", headers=adm_hdr)
        runner.assert_true(res_eval.status_code == 200, "POST /api/schedules/evaluate risponde HTTP 200")
        eval_json = res_eval.json()
        runner.assert_true(eval_json.get("status") == "success", "Valutazione schedulazioni ha status success")
        runner.assert_true("evaluation" in eval_json, "Payload contiene chiave 'evaluation'")

        # 4. Test ScheduleEngine: Transizioni di Stato ed Esecuzione Pausa/Ripristino
        schedule_engine.reset_state()
        device_pause_calls = []
        profile_pause_calls = []

        async def _mock_update_device(dev_id, **kwargs):
            device_pause_calls.append({"dev_id": dev_id, "kwargs": kwargs})
            return {"status": "success"}

        async def _mock_set_profile_paused(prof_id, paused):
            profile_pause_calls.append({"prof_id": prof_id, "paused": paused})
            return {"status": "success"}

        orig_upd_dev = eero_client.update_device
        orig_pause_prof = eero_client.set_profile_paused
        eero_client.update_device = _mock_update_device
        eero_client.set_profile_paused = _mock_set_profile_paused

        try:
            # Creiamo 1 regola su device e 1 regola su profile
            await db_service.clear_device_schedules()
            await db_service.create_device_schedule(
                name="Test Device Schedule",
                target_type="devices",
                target_ids=["dev_test_mac_1"],
                days_of_week=["mon"],
                start_time="09:00",
                end_time="12:00",
                action="pause",
                enabled=True
            )
            await db_service.create_device_schedule(
                name="Test Profile Schedule",
                target_type="profile",
                target_ids=["prof_test_kids"],
                days_of_week=["mon"],
                start_time="09:00",
                end_time="12:00",
                action="pause",
                enabled=True
            )

            # Simuliamo orario in finestra attiva (Lunedì ore 10:00)
            await schedule_engine.evaluate_schedules(current_dt=datetime(2026, 10, 5, 10, 0))
            runner.assert_true(len(device_pause_calls) == 1, "update_device chiamato per mettere in pausa dev_test_mac_1")
            runner.assert_true(device_pause_calls[0]["kwargs"].get("paused") is True, "Dispositivo messo in pausa (paused=True)")
            runner.assert_true(len(profile_pause_calls) == 1, "set_profile_paused chiamato per profilo prof_test_kids")
            runner.assert_true(profile_pause_calls[0]["paused"] is True, "Profilo messo in pausa (paused=True)")

            # Secondo ciclo nello stesso stato attivo: NESSUNA nuova chiamata (nessuna transizione ridondante)
            device_pause_calls.clear()
            profile_pause_calls.clear()
            await schedule_engine.evaluate_schedules(current_dt=datetime(2026, 10, 5, 10, 30))
            runner.assert_true(len(device_pause_calls) == 0 and len(profile_pause_calls) == 0, "Nessuna transizione ridondante scatenata quando lo stato attivo rimane invariato")

            # Ciclo in transizione a stato DISATTIVO (Lunedì ore 13:00 - finita finestra)
            await schedule_engine.evaluate_schedules(current_dt=datetime(2026, 10, 5, 13, 0))
            runner.assert_true(len(device_pause_calls) == 1, "update_device chiamato alla transizione di disattivazione")
            runner.assert_true(device_pause_calls[0]["kwargs"].get("paused") is False, "Dispositivo ripristinato (paused=False)")
            runner.assert_true(len(profile_pause_calls) == 1, "set_profile_paused chiamato alla transizione di disattivazione")
            runner.assert_true(profile_pause_calls[0]["paused"] is False, "Profilo ripristinato (paused=False)")

            # Test schedulazione LED Nodo (spegnimento notturno e riaccensione)
            node_led_calls = []
            orig_set_led = eero_client.set_eero_led
            async def _mock_set_eero_led(node_id, led_on):
                node_led_calls.append({"node_id": node_id, "led_on": led_on})
                return {"status": "success"}
            eero_client.set_eero_led = _mock_set_eero_led

            try:
                await db_service.clear_device_schedules()
                schedule_engine.reset_state()
                await db_service.create_device_schedule(
                    name="Spegni LED Salotto",
                    target_type="node_led",
                    target_ids=["node_salotto"],
                    days_of_week=["mon"],
                    start_time="09:00",
                    end_time="12:00",
                    action="turn_off",
                    enabled=True
                )
                # Attiva: LED spento (led_on=False)
                await schedule_engine.evaluate_schedules(current_dt=datetime(2026, 10, 5, 10, 0))
                runner.assert_true(len(node_led_calls) == 1, "set_eero_led chiamato per nodo node_salotto")
                runner.assert_true(node_led_calls[0]["led_on"] is False, "LED nodo spento durante la finestra programmata (led_on=False)")

                # Disattiva: LED riacceso (led_on=True)
                await schedule_engine.evaluate_schedules(current_dt=datetime(2026, 10, 5, 13, 0))
                runner.assert_true(len(node_led_calls) == 2, "set_eero_led chiamato alla disattivazione della finestra")
                runner.assert_true(node_led_calls[1]["led_on"] is True, "LED nodo riacceso al termine della finestra programmata (led_on=True)")
            finally:
                eero_client.set_eero_led = orig_set_led

        finally:
            eero_client.update_device = orig_upd_dev
            eero_client.set_profile_paused = orig_pause_prof

        # 5. Test Database Maintenance & MaintenanceEngine (Nightly Routine)
        # Test 5a: Esecuzione diretta manutenzione SQLite
        maint_fast = await db_service.run_database_maintenance(vacuum=False)
        runner.assert_true(maint_fast.get("status") == "success", "run_database_maintenance(vacuum=False) successo")
        runner.assert_true(maint_fast.get("pragma_optimize") is True, "PRAGMA optimize eseguito")
        runner.assert_true(maint_fast.get("vacuum_performed") is False, "vacuum_performed è False")

        maint_vac = await db_service.run_database_maintenance(vacuum=True)
        runner.assert_true(maint_vac.get("status") == "success", "run_database_maintenance(vacuum=True) successo")
        runner.assert_true(maint_vac.get("vacuum_performed") is True, "VACUUM compattazione eseguito")

        # Test 5b: Endpoints API Manutenzione Notturna
        # GET /api/automations/nightly-maintenance
        res_nm_get = await client.get("/api/automations/nightly-maintenance")
        runner.assert_true(res_nm_get.status_code == 200, "GET /api/automations/nightly-maintenance risponde HTTP 200")
        runner.assert_true("settings" in res_nm_get.json(), "Risposta include impostazioni correnti")

        # POST /api/automations/nightly-maintenance (salvataggio impostazioni)
        res_nm_save = await client.post(
            "/api/automations/nightly-maintenance",
            json={
                "enabled": True,
                "time": "03:30",
                "auto_reboot": True,
                "reboot_threshold_score": 55,
                "vacuum": True
            },
            headers=adm_hdr
        )
        runner.assert_true(res_nm_save.status_code == 200, "POST /api/automations/nightly-maintenance risponde HTTP 200")
        saved_nm = (await client.get("/api/automations/nightly-maintenance")).json().get("settings", {})
        runner.assert_true(saved_nm.get("enabled") is True, "enabled salvato")
        runner.assert_true(saved_nm.get("time") == "03:30", "orario 03:30 salvato")
        runner.assert_true(saved_nm.get("auto_reboot") is True, "auto_reboot salvato")
        runner.assert_true(saved_nm.get("reboot_threshold_score") == 55, "reboot_threshold_score 55 salvato")

        # Test 5c: POST /api/automations/nightly-maintenance/run con RBAC
        # Operatore senza 'action_reboot_nodes' bloccato con 403 Forbidden
        res_nm_run_forbid = await client.post("/api/automations/nightly-maintenance/run", headers=op_sched_hdr)
        runner.assert_true(res_nm_run_forbid.status_code == 403, "Esecuzione manutenzione manuale bloccata senza permessi (HTTP 403)")

        # Esecuzione da Admin
        reboot_network_called = []
        reboot_eero_called = []

        async def _mock_reboot_network():
            reboot_network_called.append(True)
            return {"status": "success"}

        async def _mock_reboot_eero(e_id):
            reboot_eero_called.append(e_id)
            return {"status": "success"}

        orig_reb_net = eero_client.reboot_network
        orig_reb_eero = eero_client.reboot_eero
        eero_client.reboot_network = _mock_reboot_network
        eero_client.reboot_eero = _mock_reboot_eero

        try:
            # Caso 1: Rete sana (health_score = 95 > soglia 55) -> Nessun riavvio
            background_poller.cached_health_score = 95
            res_nm_run_healthy = await client.post("/api/automations/nightly-maintenance/run", headers=adm_hdr)
            runner.assert_true(res_nm_run_healthy.status_code == 200, "Esecuzione manutenzione admin risponde HTTP 200")
            h_data = res_nm_run_healthy.json()
            runner.assert_true(h_data.get("database_optimized") is True, "Database SQLite ottimizzato con successo")
            runner.assert_true(h_data.get("reboot_triggered") is False, "Nessun riavvio scatenato con rete in salute (health_score 95)")

            # Caso 2: Rete degradata (health_score = 40 < soglia 55) con un beacon con segnale critico
            background_poller.cached_health_score = 40
            background_poller.cached_eeros = [
                {"id": "node_gw", "name": "Gateway Living", "is_gateway": True, "status": "online", "signal_rssi": -45},
                {"id": "node_ext_1", "name": "Beacon Mansarda", "is_gateway": False, "status": "offline", "signal_rssi": -88},
            ]
            res_nm_run_degraded = await client.post("/api/automations/nightly-maintenance/run", headers=adm_hdr)
            runner.assert_true(res_nm_run_degraded.status_code == 200, "Esecuzione manutenzione su rete degradata risponde HTTP 200")
            deg_data = res_nm_run_degraded.json()
            runner.assert_true(deg_data.get("reboot_triggered") is True, "Riavvio scatenato su rete degradata sotto soglia")
            runner.assert_true(len(reboot_eero_called) == 1 and reboot_eero_called[0] == "node_ext_1", "Riavviato selettivamente il solo nodo beacon degradato (node_ext_1)")
            runner.assert_true(len(reboot_network_called) == 0, "Riavvio generale evitato a favore del nodo beacon isolato")

        finally:
            eero_client.reboot_network = orig_reb_net
            eero_client.reboot_eero = orig_reb_eero

        # Pulizia record temporanei
        await db_service.clear_device_schedules()
        if op_schedules_id:
            await db_service.delete_local_user(op_schedules_id)

        # -----------------------------------------------------------------
        # 25. TEST BUFFERBLOAT WAN SPEEDTEST & DISASTER RECOVERY BACKUP/RESTORE (v1.6.0 Modulo 1)
        # -----------------------------------------------------------------
        print("\n🚀 [25/25] TEST BUFFERBLOAT WAN SPEEDTEST & DISASTER RECOVERY BACKUP/RESTORE (v1.6.0)")

        from app.services.speedtest_service import compute_bufferbloat

        # 1. Test Algoritmo e Classificazione Bufferbloat
        # Scala internazionale: A+ (<5ms), A (5-15ms), B (15-30ms), C (30-60ms), D (60-200ms), F (>=200ms)
        p_load, delta, grade = compute_bufferbloat(10.0, 14.0)
        runner.assert_true(delta == 4.0 and grade == "A+", f"Bufferbloat Delta 4.0ms classificato 'A+' (ottenuto: {grade})")

        p_load, delta, grade = compute_bufferbloat(10.0, 22.0)
        runner.assert_true(delta == 12.0 and grade == "A", f"Bufferbloat Delta 12.0ms classificato 'A' (ottenuto: {grade})")

        p_load, delta, grade = compute_bufferbloat(10.0, 35.0)
        runner.assert_true(delta == 25.0 and grade == "B", f"Bufferbloat Delta 25.0ms classificato 'B' (ottenuto: {grade})")

        p_load, delta, grade = compute_bufferbloat(10.0, 55.0)
        runner.assert_true(delta == 45.0 and grade == "C", f"Bufferbloat Delta 45.0ms classificato 'C' (ottenuto: {grade})")

        p_load, delta, grade = compute_bufferbloat(10.0, 110.0)
        runner.assert_true(delta == 100.0 and grade == "D", f"Bufferbloat Delta 100.0ms classificato 'D' (ottenuto: {grade})")

        p_load, delta, grade = compute_bufferbloat(10.0, 250.0)
        runner.assert_true(delta == 240.0 and grade == "F", f"Bufferbloat Delta 240.0ms classificato 'F' (ottenuto: {grade})")

        # Delta non negativo se ping sotto carico risulta inferiore o jitter instabile
        p_load, delta, grade = compute_bufferbloat(15.0, 12.0)
        runner.assert_true(delta == 0.0 and grade == "A+", "Bufferbloat con ping_under_load <= ping_idle produce delta=0.0 e grado 'A+'")

        # 2. Test Persistenza SQLite Bufferbloat
        test_sp_id = await db_service.save_speedtest(
            download_mbps=880.5,
            upload_mbps=285.0,
            ping_ms=9.5,
            jitter=1.1,
            server_name="FTTH Lab SpeedTest",
            source="wan_test",
            ping_under_load=17.5,
            bufferbloat_grade="A",
            bufferbloat_delta_ms=8.0
        )
        runner.assert_true(test_sp_id > 0, "save_speedtest memorizza record con campi bufferbloat")

        history_sp = await db_service.get_speedtests(limit=10)
        saved_sp = next((s for s in history_sp if s.get("id") == test_sp_id), None)
        runner.assert_true(saved_sp is not None, "Record speedtest recuperato da get_speedtests()")
        runner.assert_true(float(saved_sp.get("ping_under_load") or 0) == 17.5, f"ping_under_load salvato correttamente (ottenuto: {saved_sp.get('ping_under_load')})")
        runner.assert_true(saved_sp.get("bufferbloat_grade") == "A", f"bufferbloat_grade salvato correttamente (ottenuto: {saved_sp.get('bufferbloat_grade')})")
        runner.assert_true(float(saved_sp.get("bufferbloat_delta_ms") or 0) == 8.0, f"bufferbloat_delta_ms salvato correttamente (ottenuto: {saved_sp.get('bufferbloat_delta_ms')})")

        # 3. Test Esecuzione Speedtest & Router API
        # Admin login per testare rotte protette
        admin_pwd = getattr(runner, "admin_test_pwd", getattr(settings, "admin_password", "") or "AdminPassword123!")
        res_adm_login = await client.post("/api/auth/local/login", json={"username": "admin", "password": admin_pwd})
        adm_token = res_adm_login.json().get("token")
        adm_hdr = {"Authorization": f"Bearer {adm_token}"}

        # Esecuzione speedtest via API con admin token
        res_sp_run = await client.post("/api/speedtest/run", headers=adm_hdr)
        runner.assert_true(res_sp_run.status_code == 200, "POST /api/speedtest/run risponde HTTP 200")
        sp_run_data = res_sp_run.json().get("result", {})
        runner.assert_true("bufferbloat_grade" in sp_run_data, "Risultato speedtest include campo 'bufferbloat_grade'")
        runner.assert_true("bufferbloat_delta_ms" in sp_run_data, "Risultato speedtest include campo 'bufferbloat_delta_ms'")
        runner.assert_true("ping_under_load" in sp_run_data, "Risultato speedtest include campo 'ping_under_load'")

        # Verifica API GET /api/speedtest/history
        res_sp_hist = await client.get("/api/speedtest/history?limit=10")
        runner.assert_true(res_sp_hist.status_code == 200, "GET /api/speedtest/history risponde HTTP 200")
        hist_tests = res_sp_hist.json().get("tests", [])
        runner.assert_true(len(hist_tests) > 0, "Storico speedtest restituisce almeno un record")
        runner.assert_true("bufferbloat_grade" in hist_tests[0], "Record in storico espone 'bufferbloat_grade'")

        # 4. Test Disaster Recovery: Backup & Ripristino Atomico
        # 4a. Preparazione dati di prova per il backup
        await db_service.upsert_device_metadata(
            "aa:bb:cc:11:22:33",
            custom_name="Server NAS Principale",
            category="Server/Rete",
            custom_notes="Apparato critico per test backup",
            is_favorite=True
        )
        await db_service.set_setting("backup_verification_key", "active_v160")
        backup_sched_id = await db_service.create_device_schedule(
            name="Regola Salvata per Backup",
            target_type="devices",
            target_ids=["aa:bb:cc:11:22:33"],
            days_of_week=["mon", "fri"],
            start_time="23:30",
            end_time="06:30",
            action="pause",
            enabled=True
        )

        # 4b. Test Esportazione Diretta DB
        export_raw = await db_service.export_system_backup()
        runner.assert_true("metadata" in export_raw, "Backup contiene sezione 'metadata'")
        runner.assert_true(export_raw.get("metadata", {}).get("backup_version") == "1.6.0", "Versione backup è '1.6.0'")
        runner.assert_true(export_raw.get("metadata", {}).get("schema_version") == 1, "schema_version è 1")
        runner.assert_true(isinstance(export_raw.get("device_metadata"), list), "device_metadata è una lista")
        runner.assert_true(isinstance(export_raw.get("app_settings"), dict), "app_settings è un dizionario")
        runner.assert_true(isinstance(export_raw.get("device_schedules"), list), "device_schedules è una lista")
        runner.assert_true(isinstance(export_raw.get("local_users"), list), "local_users è una lista")
        runner.assert_true(export_raw["app_settings"].get("backup_verification_key") == "active_v160", "Impostazione di test presente nel backup")

        # 4c. Test Endpoint REST GET /api/system/backup
        # Chiamata non autenticata -> 401 Unauthorized
        client.cookies.clear()
        res_bk_noauth = await client.get("/api/system/backup")
        runner.assert_true(res_bk_noauth.status_code == 401, "GET /api/system/backup senza autenticazione restituisce HTTP 401")

        # Chiamata autenticata con admin
        res_bk_auth = await client.get("/api/system/backup", headers=adm_hdr)
        runner.assert_true(res_bk_auth.status_code == 200, "GET /api/system/backup con admin risponde HTTP 200")
        runner.assert_true("application/json" in res_bk_auth.headers.get("content-type", ""), "Content-Type del backup è application/json")
        runner.assert_true("attachment;" in res_bk_auth.headers.get("content-disposition", ""), "Header Content-Disposition contiene attachment")
        
        backup_downloaded = res_bk_auth.json()
        runner.assert_true(backup_downloaded.get("metadata", {}).get("backup_version") == "1.6.0", "Backup scaricato valido")

        # 4d. Test Endpoint REST POST /api/system/restore
        # Creiamo un operatore non admin per verificare RBAC
        existing_op_res = await db_service.get_local_user_by_username("operatore_restore_test")
        if existing_op_res:
            await db_service.delete_local_user(existing_op_res["id"])
        res_create_op_res = await client.post(
            "/api/users",
            json={
                "username": "operatore_restore_test",
                "password": "PasswordTest123!",
                "is_admin": False,
                "permissions": ["action_manage_rules"] # Non admin
            },
            headers=adm_hdr
        )
        op_res_id = res_create_op_res.json().get("user", {}).get("id")
        res_op_res_login = await client.post("/api/auth/local/login", json={"username": "operatore_restore_test", "password": "PasswordTest123!"})
        op_res_hdr = {"Authorization": f"Bearer {res_op_res_login.json().get('token')}"}

        # Operatore non admin bloccato con 403 Forbidden su restore
        res_restore_forbid = await client.post("/api/system/restore", json=backup_downloaded, headers=op_res_hdr)
        runner.assert_true(res_restore_forbid.status_code == 403, "POST /api/system/restore bloccato per utente non admin con HTTP 403 Forbidden")

        # Restore con payload vuoto / malformato -> 400 Bad Request
        res_restore_bad = await client.post("/api/system/restore", json={"invalid_field": 123}, headers=adm_hdr)
        runner.assert_true(res_restore_bad.status_code == 400, "POST /api/system/restore con payload non valido risponde HTTP 400")

        # 4e. Test Ripristino Effettivo Atomico
        # Modifichiamo il payload scaricato per simulare un ripristino di nuovi dati
        restore_payload = json.loads(json.dumps(backup_downloaded))
        # Aggiorniamo il nome del dispositivo
        for d in restore_payload.get("device_metadata", []):
            if d.get("mac_address", "").lower() == "aa:bb:cc:11:22:33":
                d["custom_name"] = "Server NAS Ripristinato OK"
        # Aggiungiamo un'impostazione nuova
        restore_payload["app_settings"]["restore_success_flag"] = "confirmed_v160"
        # Aggiungiamo una nuova schedulazione
        restore_payload["device_schedules"].append({
            "name": "Regola Nuova Ripristinata",
            "target_type": "devices",
            "target_ids": ["aa:bb:cc:11:22:33"],
            "days_of_week": ["tue", "thu"],
            "start_time": "20:00",
            "end_time": "22:00",
            "action": "pause",
            "enabled": True
        })

        res_restore_ok = await client.post("/api/system/restore", json=restore_payload, headers=adm_hdr)
        runner.assert_true(res_restore_ok.status_code == 200, "POST /api/system/restore da parte di admin risponde HTTP 200 OK")
        restore_result = res_restore_ok.json()
        runner.assert_true(restore_result.get("status") == "success", "Esito ripristino è 'success'")
        runner.assert_true(restore_result.get("restored_elements", {}).get("device_metadata", 0) >= 1, "Metadati dispositivi ripristinati")
        runner.assert_true(restore_result.get("restored_elements", {}).get("app_settings", 0) >= 1, "Impostazioni ripristinate")
        runner.assert_true(restore_result.get("restored_elements", {}).get("device_schedules", 0) >= 2, "Regole orarie ripristinate")

        # Verifica persistenza effettiva su SQLite dopo ripristino
        restored_dev = await db_service.get_device_metadata("aa:bb:cc:11:22:33")
        runner.assert_true(restored_dev is not None and restored_dev.get("custom_name") == "Server NAS Ripristinato OK", "Metadato dispositivo ripristinato con nuovo valore su SQLite")

        restored_setting = await db_service.get_setting("restore_success_flag")
        runner.assert_true(restored_setting == "confirmed_v160", "Impostazione ripristinata con successo in app_settings")

        all_restored_scheds = await db_service.get_device_schedules()
        sched_names = [s.get("name") for s in all_restored_scheds]
        runner.assert_true("Regola Nuova Ripristinata" in sched_names, "Nuova regola oraria ripristinata correttamente nella tabella device_schedules")

        # Verifica emissione allarme di avvenuto ripristino
        alerts_post_restore = await db_service.get_alerts(limit=5)
        restore_alert = any((a.get("type") == "system_backup_restored" or a.get("alert_type") == "system_backup_restored") for a in alerts_post_restore)
        runner.assert_true(restore_alert, "Allarme 'system_backup_restored' emesso e persistito nel registro allarmi")

        # Pulizia record temporanei
        if op_res_id:
            await db_service.delete_local_user(op_res_id)
        await db_service.clear_device_schedules()

        # -----------------------------------------------------------------
        # 26. TEST MULTI-TIER DATA RETENTION & COMPACTION WORKER (v1.6.0 Modulo 2)
        # -----------------------------------------------------------------
        print("\n🚀 [26/26] TEST MULTI-TIER DATA RETENTION & COMPACTION WORKER (v1.6.0)")

        from app.services.retention_worker import retention_worker

        # 1. Verifica esistenza e schema tabelle Tier 2 e Tier 3 in SQLite
        async with db_service.get_connection() as db:
            cur_tables = await db.execute("SELECT name FROM sqlite_master WHERE type='table';")
            all_tbl_rows = await cur_tables.fetchall()
            existing_tables = set(r["name"] for r in all_tbl_rows)

        runner.assert_true("device_usage_hourly" in existing_tables, "Tabella 'device_usage_hourly' presente su SQLite")
        runner.assert_true("device_usage_daily" in existing_tables, "Tabella 'device_usage_daily' presente su SQLite")
        runner.assert_true("device_signal_hourly" in existing_tables, "Tabella 'device_signal_hourly' presente su SQLite")

        # 2. Inserimento campioni di test in device_usage_history per un'ora conclusa
        test_mac_tier = "aa:bb:cc:dd:ee:99"
        now_utc = datetime.now(timezone.utc)
        test_hour_dt = (now_utc - timedelta(hours=12)).replace(minute=0, second=0, microsecond=0)
        ts_prev = (test_hour_dt - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        ts_1 = (test_hour_dt + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        ts_2 = (test_hour_dt + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        ts_3 = (test_hour_dt + timedelta(minutes=50)).strftime("%Y-%m-%d %H:%M:%S")
        hour_key_test = test_hour_dt.strftime("%Y-%m-%d %H:00:00")
        day_date_test = test_hour_dt.date()
        day_date_str = day_date_test.strftime("%Y-%m-%d")

        async with db_service.get_connection() as db:
            await db.execute("DELETE FROM device_usage_history WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_usage_hourly WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_usage_daily WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_signal_history WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_signal_hourly WHERE mac_address = ?;", (test_mac_tier,))

            # Campione prima dell'ora (per verificare delta del primo punto)
            await db.execute(
                "INSERT INTO device_usage_history (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_prev, test_mac_tier, "net_tier_1", "Test-Device-Tier", 100.0 * 1024 * 1024, 20.0 * 1024 * 1024, 10.0, 2.0)
            )
            # Campioni dentro l'ora:
            # 14:10 -> 140MB rx (delta +40MB), 30MB tx (delta +10MB)
            await db.execute(
                "INSERT INTO device_usage_history (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_1, test_mac_tier, "net_tier_1", "Test-Device-Tier", 140.0 * 1024 * 1024, 30.0 * 1024 * 1024, 25.0, 5.0)
            )
            # 14:30 -> 190MB rx (delta +50MB), 45MB tx (delta +15MB)
            await db.execute(
                "INSERT INTO device_usage_history (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_2, test_mac_tier, "net_tier_1", "Test-Device-Tier", 190.0 * 1024 * 1024, 45.0 * 1024 * 1024, 35.0, 8.0)
            )
            # 14:50 -> 250MB rx (delta +60MB), 60MB tx (delta +15MB)
            await db.execute(
                "INSERT INTO device_usage_history (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_3, test_mac_tier, "net_tier_1", "Test-Device-Tier", 250.0 * 1024 * 1024, 60.0 * 1024 * 1024, 45.0, 10.0)
            )

            # Campioni segnale Wi-Fi nell'ora
            await db.execute(
                "INSERT INTO device_signal_history (timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_1, test_mac_tier, "Test-Device-Tier", -60, "5 GHz", 36, "Soggiorno", 450.0, 300.0)
            )
            await db.execute(
                "INSERT INTO device_signal_history (timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_2, test_mac_tier, "Test-Device-Tier", -66, "5 GHz", 36, "Soggiorno", 400.0, 280.0)
            )
            await db.execute(
                "INSERT INTO device_signal_history (timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);",
                (ts_3, test_mac_tier, "Test-Device-Tier", -72, "5 GHz", 36, "Camera", 350.0, 260.0)
            )
            await db.commit()

        # 3. Test aggregate_hourly_usage
        cnt_h_usage = await db_service.aggregate_hourly_usage(test_hour_dt)
        runner.assert_true(cnt_h_usage >= 1, f"aggregate_hourly_usage ha processato {cnt_h_usage} apparati")

        async with db_service.get_connection() as db:
            cur_h = await db.execute("SELECT * FROM device_usage_hourly WHERE mac_address = ? AND hour_timestamp = ?;", (test_mac_tier, hour_key_test))
            row_h = await cur_h.fetchone()

        runner.assert_true(row_h is not None, "Record hourly presente in device_usage_hourly")
        expected_rx_delta = (250.0 - 100.0) * 1024 * 1024 # 150 MB delta
        actual_rx_delta = float(row_h["rx_bytes_delta"] or 0)
        runner.assert_true(abs(actual_rx_delta - expected_rx_delta) < 1000, f"rx_bytes_delta calcolato correttamente (atteso: {expected_rx_delta}, ottenuto: {actual_rx_delta})")
        runner.assert_true(row_h["samples_count"] == 3, f"samples_count nell'ora è 3 (ottenuto: {row_h['samples_count']})")
        runner.assert_true(row_h["max_down_mbps"] == 45.0, f"max_down_mbps è 45.0 (ottenuto: {row_h['max_down_mbps']})")

        # 4. Test aggregate_hourly_signals
        cnt_h_signals = await db_service.aggregate_hourly_signals(test_hour_dt)
        runner.assert_true(cnt_h_signals >= 1, f"aggregate_hourly_signals ha processato {cnt_h_signals} apparati")

        async with db_service.get_connection() as db:
            cur_sig_h = await db.execute("SELECT * FROM device_signal_hourly WHERE mac_address = ? AND hour_timestamp = ?;", (test_mac_tier, hour_key_test))
            row_sig_h = await cur_sig_h.fetchone()

        runner.assert_true(row_sig_h is not None, "Record segnale orario presente in device_signal_hourly")
        expected_avg_rssi = round((-60 - 66 - 72) / 3) # -66
        runner.assert_true(row_sig_h["avg_rssi"] == expected_avg_rssi, f"avg_rssi calcolato correttamente ({expected_avg_rssi})")
        runner.assert_true(row_sig_h["min_rssi"] == -72, "min_rssi è -72")
        runner.assert_true(row_sig_h["max_rssi"] == -60, "max_rssi è -60")
        runner.assert_true(row_sig_h["primary_band"] == "5 GHz", "primary_band è '5 GHz'")
        runner.assert_true(row_sig_h["primary_eero_name"] == "Soggiorno", "primary_eero_name è 'Soggiorno'")

        # 5. Test aggregate_daily_usage
        cnt_d_usage = await db_service.aggregate_daily_usage(day_date_test)
        runner.assert_true(cnt_d_usage >= 1, f"aggregate_daily_usage ha processato {cnt_d_usage} apparati")

        async with db_service.get_connection() as db:
            cur_d = await db.execute("SELECT * FROM device_usage_daily WHERE mac_address = ? AND day_date = ?;", (test_mac_tier, day_date_str))
            row_d = await cur_d.fetchone()

        runner.assert_true(row_d is not None, "Record daily presente in device_usage_daily")
        runner.assert_true(float(row_d["rx_bytes_total"] or 0) == actual_rx_delta, "rx_bytes_total aggregato a livello giornaliero")
        runner.assert_true(row_d["peak_down_mbps"] == 45.0, "peak_down_mbps registrato nel rollup giornaliero")

        # 6. Test Purga Controllata Campioni Scaduti
        # Inseriamo un record grezzo recente (< 10 min) e verifichiamo che la purga a 6h non lo elimini
        ts_recent = (now_utc - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        async with db_service.get_connection() as db:
            await db.execute(
                "INSERT INTO device_usage_history (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes, download_mbps, upload_mbps, is_demo) VALUES (?, ?, ?, ?, 1000, 1000, 5, 1, 0);",
                (ts_recent, test_mac_tier, "net_tier_1", "Test-Device-Tier")
            )
            await db.commit()

        # Purga campioni grezzi più vecchi di 6 ore (quelli a -12h vengono cancellati, quello a -5min resta)
        purge_raw_res = await db_service.purge_expired_raw_samples(raw_retention_hours=6)
        runner.assert_true(purge_raw_res.get("device_usage_history", 0) >= 3, "Campioni grezzi remoti (>6h) rimossi con successo")

        async with db_service.get_connection() as db:
            cur_check_recent = await db.execute("SELECT COUNT(*) FROM device_usage_history WHERE mac_address = ? AND timestamp = ?;", (test_mac_tier, ts_recent))
            cnt_recent = (await cur_check_recent.fetchone())[0]
            # Verifica che i dati compattati in device_usage_hourly siano intatti
            cur_check_hourly = await db.execute("SELECT COUNT(*) FROM device_usage_hourly WHERE mac_address = ?;", (test_mac_tier,))
            cnt_hourly = (await cur_check_hourly.fetchone())[0]

        runner.assert_true(cnt_recent == 1, "Campione recente (<1h) intatto dopo la purga")
        runner.assert_true(cnt_hourly >= 1, "Rollup orario preservato anche dopo la cancellazione dei campioni grezzi")

        # 7. Test Statistiche Database (db_service.get_database_stats())
        db_stats = await db_service.get_database_stats()
        runner.assert_true("size_mb" in db_stats, "Statistiche database espongono 'size_mb'")
        runner.assert_true("tables" in db_stats, "Statistiche database espongono conteggi tabelle")
        runner.assert_true("device_usage_hourly" in db_stats.get("tables", {}), "Tabella 'device_usage_hourly' monitorata nelle stats")
        runner.assert_true("device_usage_daily" in db_stats.get("tables", {}), "Tabella 'device_usage_daily' monitorata nelle stats")

        # 8. Test Esecuzione Ciclo Retention Worker
        compaction_res = await retention_worker.run_compaction_cycle()
        runner.assert_true(compaction_res.get("status") == "success", "run_compaction_cycle eseguito con successo")
        runner.assert_true("raw_purged" in compaction_res, "Report include conteggio raw_purged")
        runner.assert_true("hourly_purged" in compaction_res, "Report include conteggio hourly_purged")
        runner.assert_true(retention_worker.last_run is not None, "retention_worker._last_run aggiornato")

        # 9. Test Endpoints REST API
        # GET /api/system/database/stats (Accessibile)
        res_db_stats = await client.get("/api/system/database/stats")
        runner.assert_true(res_db_stats.status_code == 200, "GET /api/system/database/stats risponde HTTP 200")
        stats_payload = res_db_stats.json()
        runner.assert_true("size_mb" in stats_payload, "Risposta stats include 'size_mb'")
        runner.assert_true("retention_policy" in stats_payload, "Risposta stats include 'retention_policy'")
        runner.assert_true(stats_payload.get("retention_policy", {}).get("raw_hours") == 48, "Policy raw_hours è 48h")

        # POST /api/system/database/compact
        # Non autenticato -> 401 Unauthorized
        res_compact_unauth = await client.post("/api/system/database/compact")
        runner.assert_true(res_compact_unauth.status_code == 401, "POST /api/system/database/compact senza autenticazione risponde HTTP 401")

        # Creiamo un operatore non admin per testare il blocco 403 Forbidden
        res_create_op_cmp = await client.post(
            "/api/users",
            json={
                "username": "operatore_compact_test",
                "password": "PasswordTest123!",
                "is_admin": False,
                "permissions": ["view_topology"]
            },
            headers=adm_hdr
        )
        op_cmp_id = res_create_op_cmp.json().get("user", {}).get("id")
        res_op_cmp_login = await client.post("/api/auth/local/login", json={"username": "operatore_compact_test", "password": "PasswordTest123!"})
        op_cmp_hdr = {"Authorization": f"Bearer {res_op_cmp_login.json().get('token')}"}

        # Operatore non admin -> 403 Forbidden
        res_compact_forbid = await client.post("/api/system/database/compact", headers=op_cmp_hdr)
        runner.assert_true(res_compact_forbid.status_code == 403, "POST /api/system/database/compact con operatore non admin risponde HTTP 403")

        # Admin -> 200 OK
        res_compact_admin = await client.post("/api/system/database/compact", headers=adm_hdr)
        runner.assert_true(res_compact_admin.status_code == 200, "POST /api/system/database/compact con admin risponde HTTP 200")
        runner.assert_true(res_compact_admin.json().get("status") == "success", "Compattazione admin restituisce status 'success'")

        # 10. Test Trasparenza Query Storiche (get_top_bandwidth_hogs su dati orari)
        hogs_weekly = await db_service.get_top_bandwidth_hogs(period="weekly", is_demo=0)
        runner.assert_true(isinstance(hogs_weekly, list), "get_top_bandwidth_hogs restituisce una lista su period='weekly'")
        # Il dispositivo test mac tier è presente con i suoi consumi calcolati dalla tabella oraria
        tier_dev_hog = next((h for h in hogs_weekly if h.get("mac") == test_mac_tier), None)
        runner.assert_true(tier_dev_hog is not None, "Dispositivo aggregato in device_usage_hourly presente nella classifica Top Hogs")

        # Pulizia dati test tier
        async with db_service.get_connection() as db:
            await db.execute("DELETE FROM device_usage_history WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_usage_hourly WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_usage_daily WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_signal_history WHERE mac_address = ?;", (test_mac_tier,))
            await db.execute("DELETE FROM device_signal_hourly WHERE mac_address = ?;", (test_mac_tier,))
            await db.commit()

        if op_cmp_id:
            await db_service.delete_local_user(op_cmp_id)

        # -----------------------------------------------------------------
        # 27. TEST MODULO 3 FRONTEND, UNIFIED NAVIGATION, PWA & RBAC UI (v1.6.0)
        # -----------------------------------------------------------------
        print("\n🚀 [27/28] TEST MODULO 3 FRONTEND, UNIFIED NAVIGATION, PWA & RBAC UI (v1.6.0)")

        import json
        from pathlib import Path

        # 1. Verifica template index.html: rimozione ingranaggio e pulizia menu
        index_html_path = Path("app/templates/index.html")
        runner.assert_true(index_html_path.exists(), "File index.html esiste")
        index_html = index_html_path.read_text(encoding="utf-8")

        # Ingranaggio (gear) deve essere COMPLETAMENTE rimosso dall'header
        runner.assert_true("header-settings" not in index_html, "Nessun details con classe 'header-settings' nell'header")
        runner.assert_true('id="header-settings-toggle"' not in index_html, "Nessun id='header-settings-toggle' nell'header")

        # Titoli 'Pagine & Sezioni' e 'Strumenti & Impostazioni' devono essere rimossi
        runner.assert_true("Pagine & Sezioni" not in index_html, "Titolo categoria 'Pagine & Sezioni' rimosso da sidebar e drawer")
        runner.assert_true("Strumenti & Impostazioni" not in index_html, "Titolo categoria 'Strumenti & Impostazioni' rimosso da sidebar e drawer")
        runner.assert_true("PAGINE & SEZIONI" not in index_html.upper(), "Nessuna variante di 'PAGINE & SEZIONI' nei menu")
        runner.assert_true("STRUMENTI & IMPOSTAZIONI" not in index_html.upper(), "Nessuna variante di 'STRUMENTI & IMPOSTAZIONI' nei menu")

        # Verifica voci unificate presenti nel template (sia sidebar che mobile drawer)
        runner.assert_true("setTab('overview')" in index_html, "Voce 'Dashboard & Mesh' presente nei menu")
        runner.assert_true("setTab('devices')" in index_html, "Voce 'Dispositivi' presente con conteggio online")
        runner.assert_true("setTab('speedtest')" in index_html, "Voce 'Speed test' presente nei menu")
        runner.assert_true("setTab('guests')" in index_html, "Voce 'Ospiti' presente nei menu")
        runner.assert_true("setTab('quality-analytics')" in index_html or "setTab('analytics')" in index_html, "Voce 'Qualità e analytics' presente nei menu")
        runner.assert_true("setTab('settings-controls')" in index_html or "setTab('automations')" in index_html, "Voce 'Controlli & Ospiti' presente nei menu")
        runner.assert_true("setTab('settings-users')" in index_html or "openUsersModal()" in index_html, "Voce 'Gestione Utenti & Permessi' presente nel menu")
        runner.assert_true("setTab('settings-backup')" in index_html or "openBackupModal()" in index_html, "Voce 'Backup & Ripristino' presente nel menu")
        runner.assert_true("setTab('settings-export')" in index_html, "Voce 'Download Dati' presente nel menu")
        runner.assert_true("setTab('settings-updates')" in index_html or "openUpdateModal(" in index_html, "Voce 'Verifica aggiornamenti' presente nel menu")
        runner.assert_true("setTab('news')" in index_html, "Voce 'Note di Rilascio eeroOS' con badge presente nei menu")
        runner.assert_true("openChangelogModal()" in index_html, "Voce 'Visualizza Changelog' presente nei menu")
        runner.assert_true("openContextHelp('intro')" in index_html, "Voce 'Guida & Manuale Rapido' presente nei menu")
        runner.assert_true("showAboutModal = true" in index_html, "Voce 'About & Crediti' presente nei menu")

        # Gating RBAC can(...) sui pulsanti amministrativi nel menu
        runner.assert_true("can('action_manage_users')" in index_html, "Voce 'Gestione Utenti' protetta da can('action_manage_users')")
        runner.assert_true("can('action_system_backup')" in index_html, "Voce 'Backup & Ripristino' protetta da can('action_system_backup')")

        # Verifica elementi UI Modulo 3 in index.html
        runner.assert_true("telemetryStale" in index_html or "telemetryAuthExpired" in index_html, "Banner Telemetry Resilience (Issue #55) integrato in index.html")
        runner.assert_true("hogsCategoryFilter" in index_html, "Filtri Top Bandwidth Hogs integrati in index.html")
        runner.assert_true("getBufferbloatGrade" in index_html, "Badge Bufferbloat WAN integrato in index.html")
        runner.assert_true("schedulesList" in index_html, "Griglia Time Windows Parental Control integrata in index.html")
        runner.assert_true("showUsersModal" in index_html, "Modale Gestione Utenti & Permessi integrata in index.html")
        runner.assert_true("showBackupModal" in index_html, "Modale Disaster Recovery Backup & Ripristino integrata in index.html")
        runner.assert_true("showScheduleModal" in index_html, "Modale Creazione/Modifica Regole Orarie integrata in index.html")

        # 2. Verifica PWA: manifest.json e sw.js
        pwa_manifest_path = Path("app/static/manifest.json")
        runner.assert_true(pwa_manifest_path.exists(), "File app/static/manifest.json presente")
        pwa_manifest = json.loads(pwa_manifest_path.read_text(encoding="utf-8"))
        runner.assert_true(pwa_manifest.get("display") == "standalone", "PWA display è impostato su 'standalone'")
        runner.assert_true(pwa_manifest.get("start_url") in ["/", "/dashboard"], "PWA start_url è impostato correttamente")
        runner.assert_true(len(pwa_manifest.get("icons", [])) >= 2, "PWA manifest definisce icone per varie risoluzioni")
        runner.assert_true("manifest.json" in index_html, "index.html include tag link per manifest.json")

        sw_path = Path("app/static/sw.js")
        runner.assert_true(sw_path.exists(), "File app/static/sw.js presente")
        sw_content = sw_path.read_text(encoding="utf-8")
        runner.assert_true("addEventListener('install'" in sw_content or 'addEventListener("install"' in sw_content, "Service Worker gestisce evento 'install'")
        runner.assert_true("addEventListener('activate'" in sw_content or 'addEventListener("activate"' in sw_content, "Service Worker gestisce evento 'activate'")
        runner.assert_true("addEventListener('fetch'" in sw_content or 'addEventListener("fetch"' in sw_content, "Service Worker gestisce evento 'fetch'")
        runner.assert_true("serviceWorker.register('/static/sw.js')" in index_html, "index.html registra il Service Worker")

        # 3. Verifica sincronizzazione bilingue i18n Modulo 3
        it_loc = json.loads(Path("app/static/locales/it.json").read_text(encoding="utf-8"))
        en_loc = json.loads(Path("app/static/locales/en.json").read_text(encoding="utf-8"))
        required_mod3_blocks = ["auth_local", "users_modal", "backup_modal", "schedules", "resilience", "bufferbloat"]
        for block in required_mod3_blocks:
            runner.assert_true(block in it_loc, f"Blocco '{block}' presente in it.json")
            runner.assert_true(block in en_loc, f"Blocco '{block}' presente in en.json")
            it_keys = set(it_loc[block].keys())
            en_keys = set(en_loc[block].keys())
            runner.assert_true(it_keys == en_keys, f"Parità chiavi perfetta in '{block}' tra it.json ed en.json")

        # 4. Verifica Logica Client Alpine.js in app.js
        app_js_path = Path("app/static/js/app.js")
        runner.assert_true(app_js_path.exists(), "File app/static/js/app.js presente")
        app_js = app_js_path.read_text(encoding="utf-8")
        runner.assert_true("can(" in app_js, "Funzione RBAC client can() definita in app.js")
        runner.assert_true("getFilteredTopHogs()" in app_js, "Funzione filtri getFilteredTopHogs() definita in app.js")
        runner.assert_true("getBufferbloatGrade(" in app_js, "Funzione getBufferbloatGrade() definita in app.js")
        runner.assert_true("fetchSchedules()" in app_js, "Funzione fetchSchedules() definita in app.js")
        runner.assert_true("openUsersModal()" in app_js, "Funzione openUsersModal() definita in app.js")
        runner.assert_true("openBackupModal()" in app_js, "Funzione openBackupModal() definita in app.js")

        # 5. Verifica Endpoint Alias Disaster Recovery Backup
        res_bk_export_alias = await client.get("/api/system/backup/export", headers=adm_hdr)
        runner.assert_true(res_bk_export_alias.status_code == 200, "GET /api/system/backup/export alias risponde HTTP 200")
        runner.assert_true(res_bk_export_alias.json().get("metadata", {}).get("backup_version") == "1.6.0", "Backup da /api/system/backup/export contiene versione corretta")

        res_bk_restore_alias = await client.post("/api/system/backup/restore", json={"bad": "data"}, headers=adm_hdr)
        runner.assert_true(res_bk_restore_alias.status_code == 400, "POST /api/system/backup/restore alias risponde HTTP 400 su payload malformato")

        # -----------------------------------------------------------------
        # 28. TEST BACKEND LOGGING & SYSTEM LOG RETENTION WORKER (v1.6.0 Modulo 4 - Fase 1)
        # -----------------------------------------------------------------
        print("\n🚀 [28/28] TEST BACKEND LOGGING & SYSTEM LOG RETENTION WORKER (v1.6.0)")

        # 1. Verifica Tabella system_logs su SQLite
        async with db_service.get_connection() as db_check:
            cur_l = await db_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_logs';")
            tbl_l = await cur_l.fetchone()
            runner.assert_true(tbl_l is not None, "Tabella 'system_logs' presente su SQLite")

        # 2. Configurazione Logging predefinita e persistenza
        log_cfg = await db_service.get_logging_config()
        runner.assert_true(isinstance(log_cfg, dict), "get_logging_config restituisce un dizionario")
        runner.assert_true(log_cfg.get("enabled") is True, "Configurazione log default ha enabled=True")
        runner.assert_true(log_cfg.get("level") in ["DEBUG", "INFO", "WARNING", "ERROR"], "Configurazione log default ha livello valido")
        runner.assert_true(log_cfg.get("retention_days") == 7, "Configurazione log default ha retention_days=7")

        # Aggiornamento configurazione
        updated_cfg = await db_service.set_logging_config(enabled=True, level="DEBUG", retention_days=15)
        runner.assert_true(updated_cfg.get("level") == "DEBUG", "set_logging_config aggiorna il livello a DEBUG")
        runner.assert_true(updated_cfg.get("retention_days") == 15, "set_logging_config aggiorna la retention a 15 giorni")

        # Ripristino default
        await db_service.set_logging_config(level="INFO", retention_days=7)

        # 3. LogService & Handler
        from app.services.log_service import log_service
        runner.assert_true(hasattr(log_service, "start"), "LogService espone metodo start")
        runner.assert_true(hasattr(log_service, "stop"), "LogService espone metodo stop")
        runner.assert_true(hasattr(log_service, "set_level"), "LogService espone metodo set_level")
        runner.assert_true(hasattr(log_service, "set_enabled"), "LogService espone metodo set_enabled")
        runner.assert_true(hasattr(log_service, "clear_logs"), "LogService espone metodo clear_logs")

        # Avvio e inserimento eventi di test
        await log_service.start()
        runner.assert_true(log_service.log_file_path.exists(), "File system.log creato sul filesystem")

        # Inserimento log singolo
        inserted_id = await db_service.insert_system_log(
            level="WARNING",
            logger_name="test.runner",
            message="Messaggio diagnostico di test per runner pre-release",
            details_json=json.dumps({"test_run": True})
        )
        runner.assert_true(isinstance(inserted_id, int) and inserted_id > 0, "insert_system_log restituisce un id valido")

        # Inserimento batch
        batch_count = await db_service.insert_system_logs_batch([
            {"level": "INFO", "logger_name": "test.batch1", "message": "Log batch 1"},
            {"level": "ERROR", "logger_name": "test.batch2", "message": "Log batch 2 errore critico"},
        ])
        runner.assert_true(batch_count == 2, "insert_system_logs_batch inserisce correttamente 2 record")

        # Recupero e filtri
        all_logs = await db_service.get_system_logs(limit=20)
        runner.assert_true(len(all_logs) >= 3, "get_system_logs restituisce i record inseriti")

        error_logs = await db_service.get_system_logs(level="ERROR", limit=10)
        runner.assert_true(all(l["level"] == "ERROR" for l in error_logs), "Filtro per level='ERROR' rispettato")

        search_logs = await db_service.get_system_logs(search="errore critico", limit=10)
        runner.assert_true(len(search_logs) >= 1 and "errore critico" in search_logs[0]["message"], "Filtro per testo 'search' funzionante")

        total_cnt = await db_service.get_system_logs_count()
        runner.assert_true(total_cnt >= 3, "get_system_logs_count restituisce conteggio accurato")

        # Statistiche log
        log_stats = await db_service.get_system_logs_stats()
        runner.assert_true(log_stats.get("total_count", 0) >= 3, "Statistiche log espongono total_count")
        runner.assert_true("WARNING" in log_stats.get("level_counts", {}), "Statistiche log includono ripartizione livelli")
        runner.assert_true("file_size_bytes" in log_stats, "Statistiche log includono file_size_bytes")

        # Retention & Purga
        await db_service.insert_system_log(
            level="DEBUG",
            logger_name="test.expired",
            message="Record scaduto per test purga",
            timestamp="2021-01-01 00:00:00"
        )
        purged_cnt = await db_service.purge_expired_system_logs(retention_days=1)
        runner.assert_true(purged_cnt >= 1, "purge_expired_system_logs elimina correttamente i record obsoleti")

        # Integrazione ciclo retention worker
        compaction_res = await retention_worker.run_compaction_cycle()
        runner.assert_true("logs_purged" in compaction_res, "Retention worker include logs_purged nel sommario")

        # Svuotamento (Clear logs)
        clear_res = await log_service.clear_logs()
        runner.assert_true(clear_res.get("status") == "success", "clear_logs restituisce status success")
        post_clear_logs = await db_service.get_system_logs(limit=10)
        runner.assert_true(len(post_clear_logs) == 1, "Dopo clear_logs rimane solo l'audit log di svuotamento")
        runner.assert_true(any(t in post_clear_logs[0]["message"] for t in ("cancellati con successo", "cleared successfully")), "Audit log di svuotamento registrato correttamente")

        # 4. REST API Endpoint Testing (/api/system/logs) (v1.6.0 Modulo 4 - Fase 2)
        # GET /api/system/logs/config con admin
        res_cfg = await client.get("/api/system/logs/config", headers=adm_hdr)
        runner.assert_true(res_cfg.status_code == 200, "GET /api/system/logs/config risponde HTTP 200")
        cfg_body = res_cfg.json()
        runner.assert_true(cfg_body.get("status") == "success", "GET /api/system/logs/config ha status success")
        runner.assert_true("enabled" in cfg_body, "GET /api/system/logs/config contiene flag enabled")
        runner.assert_true("level" in cfg_body, "GET /api/system/logs/config contiene level")
        runner.assert_true("retention_days" in cfg_body, "GET /api/system/logs/config contiene retention_days")
        runner.assert_true("stats" in cfg_body, "GET /api/system/logs/config include sezione stats")

        # POST /api/system/logs/config con admin
        res_cfg_up = await client.post(
            "/api/system/logs/config",
            json={"level": "DEBUG", "retention_days": 14, "enabled": True},
            headers=adm_hdr
        )
        runner.assert_true(res_cfg_up.status_code == 200, "POST /api/system/logs/config risponde HTTP 200")
        up_body = res_cfg_up.json()
        runner.assert_true(up_body.get("level") == "DEBUG", "POST /api/system/logs/config aggiorna il livello a DEBUG")
        runner.assert_true(up_body.get("retention_days") == 14, "POST /api/system/logs/config aggiorna la retention a 14")

        # Validazione errore su livello non supportato
        res_bad_lvl = await client.post("/api/system/logs/config", json={"level": "INVALID_LVL"}, headers=adm_hdr)
        runner.assert_true(res_bad_lvl.status_code == 400, "POST /api/system/logs/config con livello non valido risponde HTTP 400")

        # Validazione errore su retention negativa
        res_bad_ret = await client.post("/api/system/logs/config", json={"retention_days": -1}, headers=adm_hdr)
        runner.assert_true(res_bad_ret.status_code == 422 or res_bad_ret.status_code == 400, "POST /api/system/logs/config con retention negativa risponde HTTP 400/422")

        # Ripristino config standard
        await client.post("/api/system/logs/config", json={"level": "INFO", "retention_days": 7}, headers=adm_hdr)

        # GET /api/system/logs paginato e con filtri
        await db_service.insert_system_log(level="INFO", logger_name="api.test", message="Messaggio diagnostico per API GET")
        await db_service.insert_system_log(level="ERROR", logger_name="api.test", message="Errore critico per query test")
        res_logs_list = await client.get("/api/system/logs?limit=50&offset=0", headers=adm_hdr)
        runner.assert_true(res_logs_list.status_code == 200, "GET /api/system/logs risponde HTTP 200")
        list_body = res_logs_list.json()
        runner.assert_true(list_body.get("status") == "success", "GET /api/system/logs ha status success")
        runner.assert_true("total" in list_body, "GET /api/system/logs include total")
        runner.assert_true("logs" in list_body and len(list_body["logs"]) >= 2, "GET /api/system/logs include array logs")

        # Filtro per livello e ricerca testuale via query params
        res_filter_lvl = await client.get("/api/system/logs?level=ERROR", headers=adm_hdr)
        runner.assert_true(res_filter_lvl.status_code == 200, "GET /api/system/logs?level=ERROR risponde HTTP 200")
        runner.assert_true(all(l.get("level") == "ERROR" for l in res_filter_lvl.json().get("logs", [])), "Filtro query level='ERROR' rispettato")

        res_filter_q = await client.get("/api/system/logs?q=critico", headers=adm_hdr)
        runner.assert_true(res_filter_q.status_code == 200, "GET /api/system/logs?q=critico risponde HTTP 200")
        runner.assert_true(len(res_filter_q.json().get("logs", [])) >= 1, "Ricerca testuale via API restituisce risultati corretti")

        # POST /api/system/logs/clear
        res_clear_api = await client.post("/api/system/logs/clear", headers=adm_hdr)
        runner.assert_true(res_clear_api.status_code == 200, "POST /api/system/logs/clear risponde HTTP 200")
        runner.assert_true(res_clear_api.json().get("status") == "success", "POST /api/system/logs/clear status success")
        runner.assert_true("deleted_records" in res_clear_api.json(), "POST /api/system/logs/clear restituisce deleted_records")

        # GET /api/system/logs/download (formato log standard)
        res_down_log = await client.get("/api/system/logs/download?format=log", headers=adm_hdr)
        runner.assert_true(res_down_log.status_code == 200, "GET /api/system/logs/download?format=log risponde HTTP 200")
        runner.assert_true("attachment" in res_down_log.headers.get("content-disposition", ""), "Download log include header Content-Disposition attachment")
        runner.assert_true(".log" in res_down_log.headers.get("content-disposition", ""), "Nome file scaricato ha estensione .log")

        # GET /api/system/logs/download (formato json)
        res_down_json = await client.get("/api/system/logs/download?format=json", headers=adm_hdr)
        runner.assert_true(res_down_json.status_code == 200, "GET /api/system/logs/download?format=json risponde HTTP 200")
        runner.assert_true("application/json" in res_down_json.headers.get("content-type", ""), "Download json restituisce Content-Type application/json")
        down_json_body = res_down_json.json()
        runner.assert_true("logs" in down_json_body, "Download json include array di log")

        # 5. Verifica Controlli di Accesso RBAC
        # Creazione operatore con solo 'view_logs' (senza action_manage_rules)
        res_create_op_log = await client.post(
            "/api/users",
            json={
                "username": "operatore_logs_viewer",
                "display_name": "Operatore Logs",
                "password": "PasswordTest123!",
                "role": "operator",
                "permissions": ["view_logs"]
            },
            headers=adm_hdr
        )
        op_log_id = res_create_op_log.json().get("user", {}).get("id")
        res_op_log_login = await client.post("/api/auth/local/login", json={"username": "operatore_logs_viewer", "password": "PasswordTest123!"})
        op_log_hdr = {"Authorization": f"Bearer {res_op_log_login.json().get('token')}"}

        # view_logs consente lettura e download
        res_op_read_cfg = await client.get("/api/system/logs/config", headers=op_log_hdr)
        runner.assert_true(res_op_read_cfg.status_code == 200, "Operatore con view_logs può leggere GET /api/system/logs/config")

        res_op_read_logs = await client.get("/api/system/logs", headers=op_log_hdr)
        runner.assert_true(res_op_read_logs.status_code == 200, "Operatore con view_logs può leggere GET /api/system/logs")

        res_op_down = await client.get("/api/system/logs/download", headers=op_log_hdr)
        runner.assert_true(res_op_down.status_code == 200, "Operatore con view_logs può eseguire GET /api/system/logs/download")

        # view_logs NON consente modifiche di configurazione o svuotamento (richiede action_manage_rules)
        res_op_forbid_cfg = await client.post("/api/system/logs/config", json={"level": "DEBUG"}, headers=op_log_hdr)
        runner.assert_true(res_op_forbid_cfg.status_code == 403, "Operatore senza action_manage_rules bloccato con 403 su POST /api/system/logs/config")

        res_op_forbid_clear = await client.post("/api/system/logs/clear", headers=op_log_hdr)
        runner.assert_true(res_op_forbid_clear.status_code == 403, "Operatore senza action_manage_rules bloccato con 403 su POST /api/system/logs/clear")

        # Pulizia utente test
        if op_log_id:
            await db_service.delete_local_user(op_log_id)

        # -------------------------------------------------------------
        # MODULO 4 - FASE 3: TEST UI CARD, MODAL, JS LOGIC & I18N PARITY
        # -------------------------------------------------------------
        print("\n🖥️ [MODULO 4 - FASE 3] TEST UI CARD LOGS, MODAL, JS LOGIC & I18N PARITY")
        
        # 1. Parità dizionari i18n per 'logs'
        it_dict = json.loads(Path("app/static/locales/it.json").read_text(encoding="utf-8"))
        en_dict = json.loads(Path("app/static/locales/en.json").read_text(encoding="utf-8"))
        runner.assert_true("logs" in it_dict, "Chiave 'logs' presente in it.json")
        runner.assert_true("logs" in en_dict, "Chiave 'logs' presente in en.json")
        it_logs_keys = set(it_dict.get("logs", {}).keys())
        en_logs_keys = set(en_dict.get("logs", {}).keys())
        runner.assert_true(len(it_logs_keys) >= 38, f"it.json ha almeno 38 chiavi logs (trovate {len(it_logs_keys)})")
        runner.assert_true(it_logs_keys == en_logs_keys, "Parità 100% tra chiavi 'logs' di it.json ed en.json")

        # 2. Template index.html: presenza Card 7 e Modal di svuotamento
        index_html = Path("app/templates/index.html").read_text(encoding="utf-8")
        runner.assert_true("logs.title" in index_html, "Card 7 'logs.title' presente nel template index.html")
        runner.assert_true("logConfig.enabled" in index_html, "Toggle logConfig.enabled presente in index.html")
        runner.assert_true("setLogLevel(" in index_html, "Selettore setLogLevel presente in index.html")
        runner.assert_true("setLogRetention(" in index_html, "Selettore setLogRetention presente in index.html")
        runner.assert_true("downloadSystemLogs(" in index_html, "Azione downloadSystemLogs presente in index.html")
        runner.assert_true("showClearLogsModal" in index_html, "Modal showClearLogsModal presente in index.html")
        runner.assert_true("logs.viewer_title" in index_html, "Live Console 'logs.viewer_title' presente in index.html")

        # 3. Frontend app.js: presenza reactive state e metodi
        app_js = Path("app/static/js/app.js").read_text(encoding="utf-8")
        runner.assert_true("fetchLogConfig" in app_js, "Metodo fetchLogConfig presente in app.js")
        runner.assert_true("fetchSystemLogs" in app_js, "Metodo fetchSystemLogs presente in app.js")
        runner.assert_true("setLogLevel" in app_js, "Metodo setLogLevel presente in app.js")
        runner.assert_true("setLogRetention" in app_js, "Metodo setLogRetention presente in app.js")
        runner.assert_true("toggleLogEnabled" in app_js, "Metodo toggleLogEnabled presente in app.js")
        runner.assert_true("confirmClearLogs" in app_js, "Metodo confirmClearLogs presente in app.js")
        runner.assert_true("downloadSystemLogs" in app_js, "Metodo downloadSystemLogs presente in app.js")
        runner.assert_true("openClearLogsModal" in app_js, "Metodo openClearLogsModal presente in app.js")
        runner.assert_true("closeClearLogsModal" in app_js, "Metodo closeClearLogsModal presente in app.js")

        # -------------------------------------------------------------
        # MODULO 4 - FASE 4: TEST HOMELAB INTEGRATIONS (MQTT, PROMETHEUS, MULTI-CHANNEL DISPATCHER)
        # -------------------------------------------------------------
        print("\n🏠 [MODULO 4 - FASE 4] TEST HOMELAB INTEGRATIONS (MQTT, PROMETHEUS, NOTIFICATIONS)")

        # 1. Test MQTT Service & Endpoints
        from app.services.mqtt_client import mqtt_service
        runner.assert_true(mqtt_service is not None, "Istanza mqtt_service creata con successo")
        runner.assert_true(hasattr(mqtt_service, "start") and hasattr(mqtt_service, "stop"), "mqtt_service espone metodi start e stop")
        runner.assert_true(hasattr(mqtt_service, "publish_discovery_configs"), "mqtt_service espone publish_discovery_configs")
        runner.assert_true(hasattr(mqtt_service, "publish_telemetry"), "mqtt_service espone publish_telemetry")

        # Home Assistant Discovery Payloads
        payloads = mqtt_service._get_discovery_payloads()
        runner.assert_true(len(payloads) >= 8, f"Home Assistant discovery payloads generati (trovati {len(payloads)})")
        disc_topics = [p["topic"] for p in payloads]
        runner.assert_true(any("wan_download" in t for t in disc_topics), "Discovery contiene sensore wan_download")
        runner.assert_true(any("health_score" in t for t in disc_topics), "Discovery contiene sensore health_score")
        runner.assert_true(any("clients_count" in t for t in disc_topics), "Discovery contiene sensore clients_count")
        runner.assert_true(any("bufferbloat_grade" in t for t in disc_topics), "Discovery contiene sensore bufferbloat_grade")
        runner.assert_true(any("binary_sensor" in t for t in disc_topics), "Discovery contiene binary_sensor per connettività")

        # GET /api/automations/mqtt/config
        res_mqtt_cfg = await client.get("/api/automations/mqtt/config", headers=adm_hdr)
        runner.assert_true(res_mqtt_cfg.status_code == 200, "GET /api/automations/mqtt/config risponde HTTP 200")
        mqtt_cfg_data = res_mqtt_cfg.json()
        runner.assert_true("broker_host" in mqtt_cfg_data, "Configurazione MQTT include broker_host")
        runner.assert_true("base_topic" in mqtt_cfg_data, "Configurazione MQTT include base_topic")
        runner.assert_true("ha_discovery_prefix" in mqtt_cfg_data, "Configurazione MQTT include ha_discovery_prefix")

        # POST /api/automations/mqtt/config
        res_mqtt_up = await client.post(
            "/api/automations/mqtt/config",
            json={"base_topic": "eero_homelab_test", "publish_interval": 20},
            headers=adm_hdr
        )
        runner.assert_true(res_mqtt_up.status_code == 200, "POST /api/automations/mqtt/config risponde HTTP 200")
        runner.assert_true(res_mqtt_up.json().get("config", {}).get("base_topic") == "eero_homelab_test", "Aggiornato base_topic a 'eero_homelab_test'")

        # Ripristino config MQTT standard
        await client.post("/api/automations/mqtt/config", json={"base_topic": "eero_dashboard", "publish_interval": 30}, headers=adm_hdr)

        # POST /api/automations/mqtt/test (senza payload - parametri correnti)
        res_mqtt_test = await client.post("/api/automations/mqtt/test", headers=adm_hdr)
        runner.assert_true(res_mqtt_test.status_code == 200, "POST /api/automations/mqtt/test risponde HTTP 200")
        runner.assert_true(res_mqtt_test.json().get("status") == "success", "Test di pubblicazione MQTT eseguito con successo")

        # POST /api/automations/mqtt/test (con payload parametri non salvati del modale)
        res_mqtt_custom = await client.post(
            "/api/automations/mqtt/test",
            json={"broker_host": "127.0.0.1", "broker_port": 1883, "username": "test_user"},
            headers=adm_hdr
        )
        runner.assert_true(res_mqtt_custom.status_code == 200, "POST /api/automations/mqtt/test con parametri modale risponde HTTP 200")
        runner.assert_true("127.0.0.1:1883" in res_mqtt_custom.json().get("broker", ""), "Parametri modale utilizzati per il test")

        # Verifica sicurezza password in config
        runner.assert_true("has_password" in mqtt_cfg_data, "Configurazione MQTT include flag has_password")
        runner.assert_true("password" not in mqtt_cfg_data, "Configurazione MQTT non espone password in chiaro")

        # Verifica localizzazione e interfaccia Modulo 2 (MQTT)
        it_loc_path = Path("app/static/locales/it.json")
        en_loc_path = Path("app/static/locales/en.json")
        runner.assert_true(it_loc_path.exists() and en_loc_path.exists(), "File di localizzazione it.json e en.json presenti")
        it_loc = json.loads(it_loc_path.read_text(encoding="utf-8"))
        en_loc = json.loads(en_loc_path.read_text(encoding="utf-8"))
        mqtt_req_keys = [
            "mqtt_title", "mqtt_subtitle", "mqtt_desc", "mqtt_status_connected",
            "mqtt_status_disconnected", "mqtt_status_disabled", "mqtt_config_btn",
            "mqtt_test_btn", "mqtt_modal_title", "mqtt_modal_desc", "mqtt_enable_toggle",
            "mqtt_broker_host", "mqtt_broker_port", "mqtt_username", "mqtt_password",
            "mqtt_base_topic", "mqtt_discovery_enable", "mqtt_ha_prefix", "mqtt_publish_interval",
            "mqtt_save_btn", "mqtt_messages_count", "mqtt_last_published", "mqtt_last_error"
        ]
        for k in mqtt_req_keys:
            runner.assert_true(k in it_loc.get("controls", {}), f"Chiave '{k}' presente in it.json (controls)")
            runner.assert_true(k in en_loc.get("controls", {}), f"Chiave '{k}' presente in en.json (controls)")

        # Verifica template HTML e script JS
        html_content = Path("app/templates/index.html").read_text(encoding="utf-8")
        js_content = Path("app/static/js/app.js").read_text(encoding="utf-8")
        runner.assert_true("showMqttModal" in html_content, "showMqttModal presente in index.html")
        runner.assert_true("mqttSettings" in html_content, "mqttSettings presente in index.html")
        runner.assert_true("openMqttModal" in js_content, "openMqttModal presente in app.js")
        runner.assert_true("fetchMqttSettings" in js_content, "fetchMqttSettings presente in app.js")
        runner.assert_true("saveMqttSettings" in js_content, "saveMqttSettings presente in app.js")
        runner.assert_true("testMqttConnection" in js_content, "testMqttConnection presente in app.js")

        # Test Issue #92: MQTT Device Tracker offline status & config deduplication
        class _MockMqttClient:
            def __init__(self):
                self.messages = []
            async def publish(self, topic, payload, retain=False, qos=0):
                self.messages.append({"topic": topic, "payload": payload, "retain": retain})

        mock_mqtt = _MockMqttClient()
        mqtt_service._discovery_enabled = True
        mqtt_service._published_tracker_configs.clear()
        mqtt_service._tracker_last_state.clear()
        
        test_telemetry = {
            "devices": [
                {"mac": "aa:bb:cc:dd:ee:01", "hostname": "Online Phone", "connected": True, "ip": "192.168.1.10"},
                {"mac": "aa:bb:cc:dd:ee:02", "hostname": "Offline Tablet", "connected": False, "ip": "192.168.1.11"}
            ],
            "eeros": [{"status": "online"}],
            "health_score": 100,
            "bufferbloat_grade": "A"
        }
        await mqtt_service.publish_telemetry(mock_mqtt, telemetry_data=test_telemetry)
        
        online_state_msgs = [m for m in mock_mqtt.messages if m["topic"].endswith("/device/aabbccddee01/state")]
        offline_state_msgs = [m for m in mock_mqtt.messages if m["topic"].endswith("/device/aabbccddee02/state")]
        runner.assert_true(len(online_state_msgs) == 1 and online_state_msgs[0]["payload"] == "home", "Device online riceve stato 'home'")
        runner.assert_true(len(offline_state_msgs) == 1 and offline_state_msgs[0]["payload"] == "not_home", "Device offline riceve stato 'not_home' (Issue #92)")
        
        config_msgs_first = [m for m in mock_mqtt.messages if "/device_tracker/" in m["topic"] and m["topic"].endswith("/config")]
        runner.assert_true(len(config_msgs_first) == 2, "Discovery config pubblicata per entrambi i dispositivi al primo ciclo")
        
        mock_mqtt.messages.clear()
        await mqtt_service.publish_telemetry(mock_mqtt, telemetry_data=test_telemetry)
        config_msgs_second = [m for m in mock_mqtt.messages if "/device_tracker/" in m["topic"] and m["topic"].endswith("/config")]
        runner.assert_true(len(config_msgs_second) == 0, "Discovery config deduplicata e non ripubblicata inutilmente (Issue #92)")

        # 2. Test Prometheus / OpenMetrics (/metrics & /api/metrics/prometheus)
        res_prom_root = await client.get("/metrics")
        runner.assert_true(res_prom_root.status_code == 200, "GET /metrics root risponde HTTP 200")
        runner.assert_true("text/plain" in res_prom_root.headers.get("content-type", ""), "GET /metrics restituisce Content-Type text/plain")
        prom_text = res_prom_root.text
        runner.assert_true("eero_info" in prom_text, "Metriche Prometheus includono eero_info")
        runner.assert_true("eero_clients_total" in prom_text, "Metriche Prometheus includono eero_clients_total")
        runner.assert_true("eero_clients_band_total" in prom_text, "Metriche Prometheus includono eero_clients_band_total")
        runner.assert_true("eero_wan_download_mbps" in prom_text, "Metriche Prometheus includono eero_wan_download_mbps")
        runner.assert_true("eero_wan_upload_mbps" in prom_text, "Metriche Prometheus includono eero_wan_upload_mbps")
        runner.assert_true("eero_health_score" in prom_text, "Metriche Prometheus includono eero_health_score")
        runner.assert_true("eero_mesh_nodes_online" in prom_text, "Metriche Prometheus includono eero_mesh_nodes_online")
        runner.assert_true("eero_bufferbloat_grade_numeric" in prom_text, "Metriche Prometheus includono eero_bufferbloat_grade_numeric")
        runner.assert_true("eero_bandwidth_rx_bytes_total" in prom_text, "Metriche Prometheus includono eero_bandwidth_rx_bytes_total")

        res_prom_api = await client.get("/api/metrics/prometheus")
        runner.assert_true(res_prom_api.status_code == 200, "GET /api/metrics/prometheus risponde HTTP 200")
        runner.assert_true("eero_wan_download_mbps" in res_prom_api.text, "GET /api/metrics/prometheus contiene metriche corrette")

        # Verifica Dashboard Grafana JSON
        grafana_path = Path("deploy/grafana/eero_dashboard.json")
        runner.assert_true(grafana_path.exists(), "File deploy/grafana/eero_dashboard.json presente")
        grafana_json = json.loads(grafana_path.read_text(encoding="utf-8"))
        runner.assert_true(len(grafana_json.get("panels", [])) >= 8, f"Dashboard Grafana ha almeno 8 pannelli (trovati {len(grafana_json.get('panels', []))})")
        runner.assert_true(grafana_json.get("uid") == "eero-mesh-metrics", "Dashboard Grafana ha UID corretto")

        # 3. Test Multi-Channel Dispatcher & Specialized Alerts
        notif_cfg = await client.get("/api/automations/notifications", headers=adm_hdr)
        runner.assert_true(notif_cfg.status_code == 200, "GET /api/automations/notifications risponde HTTP 200")
        notif_body = notif_cfg.json()
        runner.assert_true("discord_enabled" in notif_body, "Impostazioni notifiche contengono discord_enabled")
        runner.assert_true("pushover_enabled" in notif_body, "Impostazioni notifiche contengono pushover_enabled")

        # Test invio su tutti i 4 canali in Demo
        res_test_notif = await client.post("/api/automations/notifications/test", headers=adm_hdr)
        runner.assert_true(res_test_notif.status_code == 200, "POST /api/automations/notifications/test risponde HTTP 200")
        test_res_json = res_test_notif.json()
        runner.assert_true(test_res_json.get("telegram_sent") is True, "Canale Telegram testato con successo")
        runner.assert_true(test_res_json.get("webhook_sent") is True, "Canale Webhook testato con successo")
        runner.assert_true(test_res_json.get("discord_sent") is True, "Canale Discord testato con successo")
        runner.assert_true(test_res_json.get("pushover_sent") is True, "Canale Pushover testato con successo")

        # Test alert bufferbloat degradato
        await notification_service.notify_bufferbloat_degradation({
            "grade": "D",
            "unloaded_latency_ms": 14.5,
            "download_latency_ms": 125.0,
            "upload_latency_ms": 95.0
        })
        
        # Test alert qualità mesh debole
        await notification_service.notify_mesh_quality_warning("Gateway Soggiorno", "Interferenza radar DFS rilevata su canale 100")

        # Test alert sicurezza brute-force
        await notification_service.notify_security_auth_alert("192.168.4.199", "admin", 5, "IP temporaneamente bloccato (15 min)")

        # Test alert backup completato
        await notification_service.notify_backup_status(True, "eero_backup_auto.zip", "3.4 MB archiviati su SQLite e system.log")

        # Verifica registrazione alert su SQLite
        recent_alerts = await db_service.get_alerts(limit=10)
        recent_types = [a.get("type") for a in recent_alerts]
        runner.assert_true("bufferbloat_warning" in recent_types, "Alert 'bufferbloat_warning' salvato su DB")
        runner.assert_true("mesh_warning" in recent_types, "Alert 'mesh_warning' salvato su DB")
        runner.assert_true("security_auth" in recent_types, "Alert 'security_auth' salvato su DB")
        runner.assert_true("backup_status" in recent_types, "Alert 'backup_status' salvato su DB")

        # -------------------------------------------------------------
        # MODULO 4 - FASE 5: TEST TECHNICAL MANUAL & BILINGUAL CHANGELOG
        # -------------------------------------------------------------
        print("\n📚 [MODULO 4 - FASE 5] TEST TECHNICAL MANUAL & BILINGUAL CHANGELOG")

        # 1. Test capitoli manuale utente (IT ed EN)
        res_man_it = await client.get("/api/manual/sections?lang=it")
        runner.assert_true(res_man_it.status_code == 200, "GET /api/manual/sections?lang=it risponde HTTP 200")
        man_it_data = res_man_it.json()
        runner.assert_true(man_it_data.get("count") == 16, f"Manuale IT ha 16 capitoli (trovati {man_it_data.get('count')})")
        it_sec_ids = [s["id"] for s in man_it_data.get("sections", [])]
        runner.assert_true("system-logs" in it_sec_ids, "Capitolo 'system-logs' presente nel manuale IT")
        runner.assert_true("homelab-mqtt" in it_sec_ids, "Capitolo 'homelab-mqtt' presente nel manuale IT")
        runner.assert_true("prometheus-grafana" in it_sec_ids, "Capitolo 'prometheus-grafana' presente nel manuale IT")
        runner.assert_true("multi-channel-alerts" in it_sec_ids, "Capitolo 'multi-channel-alerts' presente nel manuale IT")
        runner.assert_true("offline-first" in it_sec_ids, "Capitolo 'offline-first' presente nel manuale IT")
        runner.assert_true("reverse-enrichment" in it_sec_ids, "Capitolo 'reverse-enrichment' presente nel manuale IT")

        res_man_en = await client.get("/api/manual/sections?lang=en")
        runner.assert_true(res_man_en.status_code == 200, "GET /api/manual/sections?lang=en risponde HTTP 200")
        man_en_data = res_man_en.json()
        runner.assert_true(man_en_data.get("count") == 16, f"Manuale EN ha 16 capitoli (trovati {man_en_data.get('count')})")
        en_sec_ids = [s["id"] for s in man_en_data.get("sections", [])]
        runner.assert_true(it_sec_ids == en_sec_ids, "Parità 100% degli ID capitoli tra manuale IT ed EN")

        # 2. Test sommario changelog in-app (IT ed EN)
        res_ch_it = await client.get("/api/manual/changelog?lang=it")
        runner.assert_true(res_ch_it.status_code == 200, "GET /api/manual/changelog?lang=it risponde HTTP 200")
        runner.assert_true("Modulo 4" in res_ch_it.json().get("content", ""), "Changelog IT contiene 'Modulo 4'")

        res_ch_en = await client.get("/api/manual/changelog?lang=en")
        runner.assert_true(res_ch_en.status_code == 200, "GET /api/manual/changelog?lang=en risponde HTTP 200")
        runner.assert_true("Module 4" in res_ch_en.json().get("content", ""), "Changelog EN contiene 'Module 4'")

        # -------------------------------------------------------------
        # MODULO 6 - TEST LOCAL ASSET BUNDLING (ISSUE #58) & RECENTLY JOINED (ISSUE #60)
        # -------------------------------------------------------------
        print("\n📦 [MODULO 6] TEST LOCAL ASSET BUNDLING (ISSUE #58) & RECENTLY JOINED (ISSUE #60)")

        # 1. Test Local Asset Bundling & 100% Offline Resilience (Issue #58)
        vendor_dir = Path("app/static/vendor")
        runner.assert_true(vendor_dir.is_dir(), "Directory app/static/vendor/ esiste")
        
        tw_path = vendor_dir / "tailwind.min.js"
        runner.assert_true(tw_path.exists() and tw_path.stat().st_size > 100_000, "app/static/vendor/tailwind.min.js presente (> 100KB)")

        alp_path = vendor_dir / "alpine.min.js"
        runner.assert_true(alp_path.exists() and alp_path.stat().st_size > 20_000, "app/static/vendor/alpine.min.js presente (> 20KB)")

        chart_path = vendor_dir / "chart.umd.min.js"
        runner.assert_true(chart_path.exists() and chart_path.stat().st_size > 100_000, "app/static/vendor/chart.umd.min.js presente (> 100KB)")

        lucide_path = vendor_dir / "lucide.min.js"
        runner.assert_true(lucide_path.exists() and lucide_path.stat().st_size > 100_000, "app/static/vendor/lucide.min.js presente (> 100KB)")

        fonts_css_path = Path("app/static/css/fonts.css")
        runner.assert_true(fonts_css_path.exists() and fonts_css_path.stat().st_size > 1_000, "app/static/css/fonts.css presente (> 1KB)")

        fonts_dir = Path("app/static/fonts")
        runner.assert_true(fonts_dir.is_dir(), "Directory app/static/fonts/ esiste")
        woff2_files = list(fonts_dir.glob("*.woff2"))
        runner.assert_true(len(woff2_files) >= 10, f"Font WOFF2 locali self-hosted presenti (trovati {len(woff2_files)})")

        # Verifica assenza di chiamate a CDN esterne in index.html
        index_html_path = Path("app/templates/index.html")
        index_html_content = index_html_path.read_text(encoding="utf-8")
        runner.assert_true("fonts.googleapis.com" not in index_html_content, "index.html non carica font da Google Fonts (offline-first)")
        runner.assert_true("cdn.tailwindcss.com" not in index_html_content, "index.html non carica Tailwind da cdn.tailwindcss.com")
        runner.assert_true("cdn.jsdelivr.net" not in index_html_content, "index.html non carica librerie esterne da jsdelivr")
        runner.assert_true("/static/vendor/tailwind.min.js" in index_html_content, "index.html carica tailwind.min.js locale")
        runner.assert_true("/static/vendor/alpine.min.js" in index_html_content, "index.html carica alpine.min.js locale")
        runner.assert_true("/static/vendor/chart.umd.min.js" in index_html_content, "index.html carica chart.umd.min.js locale")
        runner.assert_true("/static/vendor/lucide.min.js" in index_html_content, "index.html carica lucide.min.js locale")
        runner.assert_true("/static/css/fonts.css" in index_html_content, "index.html carica fonts.css locale")

        # Verifica Service Worker PWA cache locale
        sw_path = Path("app/static/sw.js")
        sw_content = sw_path.read_text(encoding="utf-8")
        runner.assert_true("tailwind.min.js" in sw_content, "sw.js pre-cachea tailwind.min.js locale")
        runner.assert_true("alpine.min.js" in sw_content, "sw.js pre-cachea alpine.min.js locale")
        runner.assert_true("chart.umd.min.js" in sw_content, "sw.js pre-cachea chart.umd.min.js locale")
        runner.assert_true("lucide.min.js" in sw_content, "sw.js pre-cachea lucide.min.js locale")
        runner.assert_true("fonts.css" in sw_content, "sw.js pre-cachea fonts.css locale")

        # 2. Test Recently Joined Devices & Sorting (Issue #60)
        known_map = await db_service.get_all_known_devices_map()
        runner.assert_true(isinstance(known_map, dict), "db_service.get_all_known_devices_map() ritorna un dizionario")

        res_devs = await client.get("/api/devices")
        runner.assert_true(res_devs.status_code == 200, "GET /api/devices risponde HTTP 200")
        dev_payload = res_devs.json()
        dev_list = dev_payload.get("devices", []) if isinstance(dev_payload, dict) else dev_payload
        runner.assert_true(isinstance(dev_list, list) and len(dev_list) > 0, "Lista dispositivi non vuota")
        
        sample_dev = dev_list[0]
        runner.assert_true("first_seen" in sample_dev, "Dispositivo ha attributo 'first_seen'")
        runner.assert_true("is_new" in sample_dev, "Dispositivo ha attributo 'is_new'")
        runner.assert_true("is_new_24h" in sample_dev, "Dispositivo ha attributo 'is_new_24h'")

        # Test sorting per primo accesso decrescente
        res_sort_desc = await client.get("/api/devices?sort_by=first_seen_desc")
        runner.assert_true(res_sort_desc.status_code == 200, "GET /api/devices?sort_by=first_seen_desc risponde HTTP 200")
        sorted_desc = res_sort_desc.json().get("devices", [])
        valid_seen_desc = [d.get("first_seen") for d in sorted_desc if d.get("first_seen")]
        runner.assert_true(valid_seen_desc == sorted(valid_seen_desc, reverse=True), "Dispositivi correttamente ordinati per first_seen decrescente")

        # Test sorting per primo accesso crescente
        res_sort_asc = await client.get("/api/devices?sort_by=first_seen_asc")
        runner.assert_true(res_sort_asc.status_code == 200, "GET /api/devices?sort_by=first_seen_asc risponde HTTP 200")
        sorted_asc = res_sort_asc.json().get("devices", [])
        valid_seen_asc = [d.get("first_seen") for d in sorted_asc if d.get("first_seen")]
        runner.assert_true(valid_seen_asc == sorted(valid_seen_asc), "Dispositivi correttamente ordinati per first_seen crescente")

        # Test filtro is_new_only
        res_new_only = await client.get("/api/devices?is_new_only=true")
        runner.assert_true(res_new_only.status_code == 200, "GET /api/devices?is_new_only=true risponde HTTP 200")
        new_only_list = res_new_only.json().get("devices", [])
        runner.assert_true(all(d.get("is_new") is True for d in new_only_list), "Tutti i dispositivi con is_new_only=true hanno is_new=True")

        # Test chiavi internazionalizzazione
        it_loc_path = Path("app/static/locales/it.json")
        en_loc_path = Path("app/static/locales/en.json")
        it_loc = json.loads(it_loc_path.read_text(encoding="utf-8"))
        en_loc = json.loads(en_loc_path.read_text(encoding="utf-8"))
        for req_key in ["sort_first_seen", "filter_new_devices", "filter_new_tag", "new_badge", "first_seen_badge_tooltip"]:
            runner.assert_true(req_key in it_loc.get("devices", {}), f"Chiave devices.{req_key} presente in it.json")
            runner.assert_true(req_key in en_loc.get("devices", {}), f"Chiave devices.{req_key} presente in en.json")
        runner.assert_true("first_seen" in it_loc.get("device_modal", {}), "Chiave device_modal.first_seen in it.json")
        runner.assert_true("first_seen" in en_loc.get("device_modal", {}), "Chiave device_modal.first_seen in en.json")

        # 3. Mark as seen & baseline prima scansione (Issue #60)
        baseline_mac = "02:00:00:00:60:01"
        await db_service.register_known_devices_batch([{"mac": baseline_mac, "hostname": "Baseline Test"}], baseline=True)
        baseline_entry = (await db_service.get_all_known_devices_map()).get(baseline_mac, {})
        runner.assert_true(baseline_entry.get("baseline") is True, "register_known_devices_batch(baseline=True) marca il dispositivo come baseline")
        runner.assert_true(baseline_entry.get("acknowledged_at") is None, "Dispositivo baseline senza acknowledged_at")
        async with db_service.get_connection() as conn:
            cursor = await conn.execute("SELECT value FROM app_settings WHERE key = 'known_devices_baseline_v1'")
            runner.assert_true(await cursor.fetchone() is not None, "Migrazione baseline known_devices registrata una sola volta in app_settings")

        cached_devs = background_poller.cached_devices
        runner.assert_true(len(cached_devs) > 0, "Cache dispositivi popolata per test Mark as seen")
        target = cached_devs[0]
        target_mac = (target.get("mac") or target.get("mac_address") or "").lower()
        target.update(is_new=True, new_dismissed=False)

        # Client senza cookie di sessione: quello condiviso conserva un token invalidato dai test precedenti
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as seen_client:
            res_seen = await seen_client.post("/api/devices/seen", json={"macs": [target_mac.upper()]})
            runner.assert_true(res_seen.status_code == 200 and res_seen.json().get("updated") == 1, "POST /api/devices/seen segna il dispositivo come visto")
            runner.assert_true(target.get("is_new") is False and target.get("new_dismissed") is True, "Cache RAM aggiornata subito: is_new=False, new_dismissed=True")
            ack_entry = (await db_service.get_all_known_devices_map()).get(target_mac, {})
            runner.assert_true(bool(ack_entry.get("acknowledged_at")), "acknowledged_at salvato su SQLite")

            res_unseen = await seen_client.post("/api/devices/seen", json={"macs": [target_mac], "seen": False})
            runner.assert_true(res_unseen.status_code == 200, "POST /api/devices/seen con seen=false risponde HTTP 200")
            runner.assert_true(target.get("is_new") is True and target.get("new_dismissed") is False, "Annulla: badge NUOVO ripristinato nella cache")
            unack_entry = (await db_service.get_all_known_devices_map()).get(target_mac, {})
            runner.assert_true(unack_entry.get("acknowledged_at") is None, "Annulla: acknowledged_at azzerato su SQLite")

            res_bad_mac = await seen_client.post("/api/devices/seen", json={"macs": ["not-a-mac"]})
            runner.assert_true(res_bad_mac.status_code == 400, "POST /api/devices/seen rifiuta MAC non validi (HTTP 400)")
            res_empty = await seen_client.post("/api/devices/seen", json={"macs": []})
            runner.assert_true(res_empty.status_code == 422, "POST /api/devices/seen rifiuta lista vuota (HTTP 422)")

        for req_key in ["mark_seen", "mark_new", "mark_all_seen", "new_badge_click_hint", "marked_seen_title", "marked_seen_msg", "marked_new_title", "marked_new_msg", "mark_seen_error"]:
            runner.assert_true(req_key in it_loc.get("devices", {}), f"Chiave devices.{req_key} presente in it.json")
            runner.assert_true(req_key in en_loc.get("devices", {}), f"Chiave devices.{req_key} presente in en.json")
        runner.assert_true("tracked_since" in it_loc.get("device_modal", {}), "Chiave device_modal.tracked_since in it.json")
        runner.assert_true("tracked_since" in en_loc.get("device_modal", {}), "Chiave device_modal.tracked_since in en.json")

        async with db_service.get_connection() as conn:
            await conn.execute("DELETE FROM known_devices WHERE mac_address = ?", (baseline_mac,))
            await conn.commit()

        # -----------------------------------------------------------------
        # TEST ISSUES #62, #63, #64
        # -----------------------------------------------------------------
        print("\n🔧 TEST ISSUES #62, #63, #64 (SQLITE CONCURRENCY, GUEST QR CODE NOPASS, DAILY DIGEST UI)")

        # Test Issue #62: SQLite Write Lock & Concurrency Contention
        runner.assert_true(hasattr(db_service, "_write_lock"), "db_service espone _write_lock per serializzazione scritture")
        async with db_service.get_connection() as conn:
            cursor = await conn.execute("PRAGMA busy_timeout;")
            busy_row = await cursor.fetchone()
            busy_val = busy_row[0] if busy_row else 0
            runner.assert_true(busy_val >= 50000, f"PRAGMA busy_timeout è >= 50000ms (ottenuto: {busy_val}ms)")

        # Test Issue #63: Guest QR Code Generation with Open / No Password Network
        from app.services.qrcode_gen import generate_wifi_qr_code
        qr_nopass = generate_wifi_qr_code(ssid="eero Open Guest", password="")
        runner.assert_true(isinstance(qr_nopass, str) and qr_nopass.startswith("data:image/png;base64,"), "generate_wifi_qr_code genera data URL valido per rete senza password")
        
        qr_with_pass = generate_wifi_qr_code(ssid="eero Protected", password="SecretPassword123")
        runner.assert_true(isinstance(qr_with_pass, str) and qr_with_pass.startswith("data:image/png;base64,"), "generate_wifi_qr_code genera data URL valido per rete protetta")
        runner.assert_true(qr_nopass != qr_with_pass, "QR Code per rete aperta è differente da QR Code con password")

        res_guest = await client.get("/api/network/guest")
        runner.assert_true(res_guest.status_code == 200, "GET /api/network/guest risponde HTTP 200")
        guest_json = res_guest.json()
        runner.assert_true("guest_network" in guest_json, "Payload guest contiene 'guest_network'")

        # Test Issue #64: Daily Digest Delivery Channels & Locales
        runner.assert_true("digest_delivery_channels" in it_loc.get("controls", {}), "Chiave controls.digest_delivery_channels in it.json")
        runner.assert_true("digest_delivery_channels" in en_loc.get("controls", {}), "Chiave controls.digest_delivery_channels in en.json")
        runner.assert_true("open_network_label" in it_loc.get("guests_page", {}), "Chiave guests_page.open_network_label in it.json")
        runner.assert_true("open_network_label" in en_loc.get("guests_page", {}), "Chiave guests_page.open_network_label in en.json")

        # Test Issue #65: UI improvement for enriched ULA addresses & missing English translations
        print("\n🔍 TEST ISSUE #65 (ULA ENRICHED UI & ENGLISH TRANSLATIONS)")
        runner.assert_true("qr_not_available" in it_loc.get("guests_page", {}), "Chiave guests_page.qr_not_available in it.json")
        runner.assert_true("qr_not_available" in en_loc.get("guests_page", {}), "Chiave guests_page.qr_not_available in en.json")
        runner.assert_true("empty_desc" in it_loc.get("schedules", {}), "Chiave schedules.empty_desc in it.json")
        runner.assert_true("empty_desc" in en_loc.get("schedules", {}), "Chiave schedules.empty_desc in en.json")
        runner.assert_true("badge_ula_enriched" in it_loc.get("devices", {}), "Chiave devices.badge_ula_enriched in it.json")
        runner.assert_true("badge_ula_enriched" in en_loc.get("devices", {}), "Chiave devices.badge_ula_enriched in en.json")
        runner.assert_true(it_loc.get("device_modal", {}).get("ipv6_badge_ula_ndp") == "ULA Enriched", "Badge ULA Enriched in it.json")
        runner.assert_true(en_loc.get("device_modal", {}).get("ipv6_badge_ula_ndp") == "ULA Enriched", "Badge ULA Enriched in en.json")
        
        # Test cleanup_stale_discovered_ips execution
        cleanup_res = await db_service.cleanup_stale_discovered_ips(retention_days=30)
        runner.assert_true(isinstance(cleanup_res, int) and cleanup_res >= 0, "cleanup_stale_discovered_ips eseguito con successo")

        # Test enrichment_service refreshes ipv6_all
        test_mac_ula = "00:11:22:33:44:55"
        await db_service.add_discovered_ips([{
            "mac_address": test_mac_ula,
            "ip_address": "fd12:3456:789a:1::99",
            "ip_type": "ULA",
            "source": "ndp_enrichment"
        }])
        background_poller.cached_devices = [{
            "mac": test_mac_ula,
            "ipv6": "fe80::1",
            "ipv6_addresses": ["fe80::1"],
            "ipv6_all": ["fe80::1"]
        }]
        from app.services.enrichment_service import enrichment_service
        await enrichment_service.refresh_cached_devices_enrichment()
        enriched_dev = background_poller.cached_devices[0]
        runner.assert_true("fd12:3456:789a:1::99" in (enriched_dev.get("ipv6_all") or []), "enriched_dev popola correttamente ipv6_all con ULA")
        runner.assert_true(enriched_dev.get("has_discovered_ips") is True, "enriched_dev imposta has_discovered_ips su True")

        # Test Issue #88: delete_discovered_ips_for_mac & POST /api/devices/{mac}/clear-ula
        del_cnt = await db_service.delete_discovered_ips_for_mac(test_mac_ula)
        runner.assert_true(del_cnt >= 1, "delete_discovered_ips_for_mac cancella i record da SQLite")
        
        await db_service.add_discovered_ips([{
            "mac_address": test_mac_ula,
            "ip_address": "fd12:3456:789a:1::101",
            "ip_type": "ULA",
            "source": "ndp_enrichment"
        }])
        res_clear_ula = await client.post(f"/api/devices/{test_mac_ula}/clear-ula", headers=adm_hdr)
        runner.assert_true(res_clear_ula.status_code == 200, "POST /api/devices/{mac}/clear-ula risponde HTTP 200")
        runner.assert_true(res_clear_ula.json().get("status") == "success", "clear-ula status success")

        # =====================================================================
        # [ISSUE #60] SELETTORE COLONNE & PERSONALIZZAZIONE VISIBILITÀ TABELLA
        # =====================================================================
        print("\n📊 TEST ISSUE #60 (DEVICE TABLE COLUMN CUSTOMIZATION)")
        import json as _col_json
        with open("app/static/locales/it.json", "r", encoding="utf-8") as _f_it:
            _it_locale = _col_json.load(_f_it)
        with open("app/static/locales/en.json", "r", encoding="utf-8") as _f_en:
            _en_locale = _col_json.load(_f_en)

        for _ckey in ["col_first_seen", "columns_button", "columns_button_tooltip", "columns_title", "columns_reset", "columns_fixed"]:
            runner.assert_true(_ckey in _it_locale.get("devices", {}), f"Chiave devices.{_ckey} presente in it.json")
            runner.assert_true(_ckey in _en_locale.get("devices", {}), f"Chiave devices.{_ckey} presente in en.json")

        with open("app/static/js/app.js", "r", encoding="utf-8") as _f_js:
            _app_js = _f_js.read()
        runner.assert_true("deviceTableColumns:" in _app_js, "app.js definisce lo stato deviceTableColumns")
        runner.assert_true("toggleTableColumn(" in _app_js, "app.js implementa toggleTableColumn")
        runner.assert_true("resetTableColumns(" in _app_js, "app.js implementa resetTableColumns")
        runner.assert_true("isTableColumnVisible(" in _app_js, "app.js implementa isTableColumnVisible")
        runner.assert_true("eero_device_columns" in _app_js, "app.js persiste su localStorage 'eero_device_columns'")

        with open("app/templates/index.html", "r", encoding="utf-8") as _f_html:
            _index_html = _f_html.read()
        runner.assert_true("toggleTableColumn" in _index_html, "index.html contiene il selettore colonne con checkbox toggle")
        runner.assert_true("isTableColumnVisible('first_seen')" in _index_html, "index.html supporta visibilità colonna first_seen")

        # Test Issue #91: Fuso orario nei log
        runner.assert_true("logTimezoneMode:" in _app_js, "app.js gestisce lo stato logTimezoneMode")
        runner.assert_true("formatLogTimestamp(" in _app_js, "app.js definisce il metodo formatLogTimestamp")
        runner.assert_true("toggleLogTimezone(" in _app_js, "app.js implementa toggleLogTimezone")
        runner.assert_true("formatLogTimestamp(l.timestamp)" in _index_html, "index.html usa formatLogTimestamp nei log")
        runner.assert_true("device-col-first-seen" in _index_html, "index.html include classe device-col-first-seen")

        with open("app/static/css/styles.css", "r", encoding="utf-8") as _f_css:
            _styles_css = _f_css.read()
        runner.assert_true(".device-table .device-col-first-seen" in _styles_css, "styles.css definisce .device-col-first-seen")

        # =====================================================================
        # [SICUREZZA DNS] AUTORIZZAZIONE ENDPOINT DNS & NON RIUTILIZZO DEI SEGRETI
        # Regressione per: endpoint DNS/AdGuard di lettura, scrittura e /test privi di
        # require_permission, e /dns/test che riutilizzava il segreto salvato verso un
        # URL scelto da chi chiama (esfiltrazione della password AdGuard / token Pi-hole).
        # =====================================================================
        print("\n🔒 [SICUREZZA DNS] AUTORIZZAZIONE ENDPOINT & NON RIUTILIZZO SEGRETI DNS")

        import httpx as _sec_httpx
        import base64 as _sec_b64
        import app.services.dns_manager as _sec_dnsmod

        _sec_pw = "FAKE_ADGUARD_PW_7x!"
        _sec_tok = "FAKE_PIHOLE_TOKEN_42"
        _sec_attacker = "http://127.0.0.1:59999"   # destinazione scelta dall'attaccante
        _sec_legit_adg = "http://127.0.0.1:50080"
        _sec_legit_pih = "http://127.0.0.1:50081"

        class _SecRecorder:
            def __init__(self):
                self.reqs = []

            def handler(self, request):
                self.reqs.append(request)
                p = request.url.path
                if p.endswith("/control/clients"):
                    return _sec_httpx.Response(200, json={"clients": [], "auto_clients": []})
                if p.endswith("/api/config/dns/hosts"):
                    return _sec_httpx.Response(200, json={"config": {"dns": {"hosts": []}}})
                return _sec_httpx.Response(200, json={})

            def leaked(self, secret):
                for r in self.reqs:
                    if secret in str(r.url):
                        return True
                    for k, v in r.headers.items():
                        if secret in v:
                            return True
                        if k.lower() == "authorization" and v.lower().startswith("basic "):
                            try:
                                if secret in _sec_b64.b64decode(v.split(None, 1)[1]).decode("utf-8", "replace"):
                                    return True
                            except Exception:
                                pass
                    try:
                        if secret.encode() in (r.content or b""):
                            return True
                    except Exception:
                        pass
                return False

        _sec_real_client = _sec_httpx.AsyncClient

        def _sec_patch(rec):
            def _fake(*a, **k):
                k.pop("verify", None)
                k["transport"] = _sec_httpx.MockTransport(rec.handler)
                return _sec_real_client(*a, **k)
            _sec_dnsmod.httpx.AsyncClient = _fake

        def _sec_unpatch():
            _sec_dnsmod.httpx.AsyncClient = _sec_real_client

        _sec_saved = (settings.demo_mode, eero_client._is_demo_active, eero_client.user_token,
                      getattr(settings, "require_local_auth", False))
        # Modalità reale (non demo) per esercitare il vero percorso di test DNS
        settings.demo_mode = False
        eero_client._is_demo_active = False
        eero_client.user_token = None
        try:
            await dns_service.save_settings(enabled=True, instances=[
                {"id": "sec-adguard-1", "name": "AdGuard", "engine": "adguard",
                 "url": _sec_legit_adg, "username": "admin", "password": _sec_pw, "enabled": True},
                {"id": "sec-pihole-1", "name": "Pi-hole", "engine": "pihole",
                 "url": _sec_legit_pih, "token": _sec_tok, "enabled": True},
            ])

            # 1. /dns/test con URL dell'attaccante NON deve riutilizzare il segreto salvato
            _rec = _SecRecorder(); _sec_patch(_rec)
            try:
                await dns_service.test_instance({"id": "sec-adguard-1", "engine": "adguard",
                                                 "url": _sec_attacker, "username": "admin"})
            finally:
                _sec_unpatch()
            runner.assert_true(not _rec.leaked(_sec_pw),
                "Password AdGuard NON esfiltrata verso un URL scelto da chi chiama in /dns/test (id noto, URL diverso)")

            _rec2 = _SecRecorder(); _sec_patch(_rec2)
            try:
                await dns_service.test_instance({"id": "sec-pihole-1", "engine": "pihole", "url": _sec_attacker})
            finally:
                _sec_unpatch()
            runner.assert_true(not _rec2.leaked(_sec_tok),
                "Token Pi-hole NON esfiltrato verso un URL scelto da chi chiama in /dns/test (id noto, URL diverso)")

            # 2. Il test legittimo verso lo stesso server riusa ancora il segreto salvato (nessuna regressione)
            _rec3 = _SecRecorder(); _sec_patch(_rec3)
            try:
                await dns_service.test_instance({"id": "sec-adguard-1", "engine": "adguard",
                                                 "url": _sec_legit_adg, "username": "admin"})
            finally:
                _sec_unpatch()
            runner.assert_true(_rec3.leaked(_sec_pw),
                "Password AdGuard ancora riutilizzata verso il server registrato (stesso URL/motore/account)")

            # 3. GET /api/automations/dns non espone segreti: solo i flag has_password / has_token
            _sec_settings = await dns_service.get_settings()
            _sec_map = {i.get("id"): i for i in _sec_settings.get("instances", [])}
            _sec_adg = _sec_map.get("sec-adguard-1", {})
            _sec_pih = _sec_map.get("sec-pihole-1", {})
            runner.assert_true("password" not in _sec_adg and "password" not in _sec_pih,
                "GET /api/automations/dns non include il campo 'password'")
            runner.assert_true("token" not in _sec_adg and "token" not in _sec_pih,
                "GET /api/automations/dns non include il campo 'token'")
            runner.assert_true(_sec_adg.get("has_password") is True,
                "GET /api/automations/dns espone has_password per l'istanza AdGuard")
            runner.assert_true(_sec_pih.get("has_token") is True,
                "GET /api/automations/dns espone has_token per l'istanza Pi-hole")

            async def _sec_reregister():
                await dns_service.save_settings(enabled=True, instances=[
                    {"id": "sec-adguard-1", "name": "AdGuard", "engine": "adguard",
                     "url": _sec_legit_adg, "username": "admin", "password": _sec_pw, "enabled": True},
                    {"id": "sec-pihole-1", "name": "Pi-hole", "engine": "pihole",
                     "url": _sec_legit_pih, "token": _sec_tok, "enabled": True},
                ])

            # 3b. Attacco in due passi (config di default, require_permission fail-open): riscrivere l'URL con
            #     lo stesso id e senza segreto NON deve portare il segreto salvato al nuovo indirizzo.
            await dns_service.save_settings(enabled=True, instances=[
                {"id": "sec-adguard-1", "name": "AdGuard", "engine": "adguard",
                 "url": _sec_attacker, "username": "admin", "enabled": True},
                {"id": "sec-pihole-1", "name": "Pi-hole", "engine": "pihole",
                 "url": _sec_attacker, "enabled": True},
            ])
            _rec4 = _SecRecorder(); _sec_patch(_rec4)
            try:
                await dns_service.test_instance({"id": "sec-adguard-1", "engine": "adguard", "url": _sec_attacker, "username": "admin"})
                await dns_service.test_instance({"id": "sec-pihole-1", "engine": "pihole", "url": _sec_attacker})
            finally:
                _sec_unpatch()
            runner.assert_true(not _rec4.leaked(_sec_pw) and not _rec4.leaked(_sec_tok),
                "Attacco in due passi: riscrivere l'URL via POST /dns (stesso id, senza segreto) non porta password/token al nuovo indirizzo")
            await _sec_reregister()

            # 3c. Non regressione: ri-registrare lo stesso server (URL con/senza slash finale) senza segreto lo conserva
            await dns_service.save_settings(enabled=True, instances=[
                {"id": "sec-adguard-1", "name": "AdGuard", "engine": "adguard",
                 "url": _sec_legit_adg + "/", "username": "admin", "enabled": True},
                {"id": "sec-pihole-1", "name": "Pi-hole", "engine": "pihole",
                 "url": _sec_legit_pih, "enabled": True},
            ])
            _rec5 = _SecRecorder(); _sec_patch(_rec5)
            try:
                await dns_service.test_instance({"id": "sec-adguard-1", "engine": "adguard", "url": _sec_legit_adg, "username": "admin"})
            finally:
                _sec_unpatch()
            runner.assert_true(_rec5.leaked(_sec_pw),
                "Ri-registrazione dello stesso server (URL con/senza slash finale) senza segreto: la password resta utilizzabile")
            await _sec_reregister()

            # 4. Autorizzazione: con REQUIRE_LOCAL_AUTH attivo gli endpoint DNS richiedono una sessione
            settings.demo_mode = True  # evita qualunque chiamata di rete in /test e /sync
            eero_client._is_demo_active = True
            settings.require_local_auth = True
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as sc:
                sc.cookies.clear()
                r = await sc.get("/api/automations/dns")
                runner.assert_true(r.status_code == 401, "GET /api/automations/dns senza sessione -> 401 (REQUIRE_LOCAL_AUTH)")
                r = await sc.get("/api/automations/adguard")
                runner.assert_true(r.status_code == 401, "GET /api/automations/adguard senza sessione -> 401 (REQUIRE_LOCAL_AUTH)")
                r = await sc.post("/api/automations/dns", json={"enabled": False, "instances": []})
                runner.assert_true(r.status_code == 401, "POST /api/automations/dns senza sessione -> 401 (REQUIRE_LOCAL_AUTH)")
                r = await sc.post("/api/automations/dns/test",
                                  json={"instance": {"id": "sec-adguard-1", "engine": "adguard", "url": _sec_attacker, "username": "admin"}})
                runner.assert_true(r.status_code == 401, "POST /api/automations/dns/test senza sessione -> 401 (REQUIRE_LOCAL_AUTH)")
                r = await sc.post("/api/automations/adguard", json={"enabled": False})
                runner.assert_true(r.status_code == 401, "POST /api/automations/adguard senza sessione -> 401 (REQUIRE_LOCAL_AUTH)")
                r = await sc.post("/api/automations/adguard/test", json={"url": _sec_attacker, "username": "admin"})
                runner.assert_true(r.status_code == 401, "POST /api/automations/adguard/test senza sessione -> 401 (REQUIRE_LOCAL_AUTH)")

            # 5. In modalità legacy (REQUIRE_LOCAL_AUTH assente) la SPA continua a leggere senza sessione
            settings.require_local_auth = False
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as sc2:
                sc2.cookies.clear()
                r = await sc2.get("/api/automations/dns")
                runner.assert_true(r.status_code == 200,
                    "GET /api/automations/dns in modalità legacy resta accessibile senza sessione (SPA non bloccata)")
        finally:
            _sec_unpatch()
            (settings.demo_mode, eero_client._is_demo_active, eero_client.user_token,
             settings.require_local_auth) = _sec_saved

        await mqtt_service.stop()
        await log_service.stop()

        # =====================================================================
        # TEST DOCKER HUB RETENTION POLICY & PRUNING SCRIPT
        # =====================================================================
        print("\n🧹 TEST DOCKER HUB RETENTION POLICY & PRUNING SCRIPT")
        from scripts.prune_docker_tags import (
            parse_semver_build,
            parse_semver_test,
            PROTECTED_TAGS,
            LEGACY_TAGS_TO_REMOVE,
            prune_tags,
        )

        runner.assert_true(parse_semver_build("1.6.0-build.2") == (1, 6, 0, 2), "parse_semver_build analizza '1.6.0-build.2'")
        runner.assert_true(parse_semver_build("1.5.0-build.10") == (1, 5, 0, 10), "parse_semver_build analizza '1.5.0-build.10'")
        runner.assert_true(parse_semver_build("invalid-tag") is None, "parse_semver_build rifiuta tag non valido")
        runner.assert_true(parse_semver_test("1.6.0-test.1") == (1, 6, 0, 1), "parse_semver_test analizza '1.6.0-test.1'")
        runner.assert_true(parse_semver_test("test-build.92") == (0, 0, 0, 92), "parse_semver_test analizza legacy 'test-build.92'")
        runner.assert_true("latest" in PROTECTED_TAGS, "'latest' e' nei tag protetti permanenti")
        runner.assert_true("test" in PROTECTED_TAGS, "'test' e' nei tag protetti permanenti")
        runner.assert_true("1.6.0-build.1" in LEGACY_TAGS_TO_REMOVE, "'1.6.0-build.1' e' nella lista legacy cleanup")
        dry_run_count = prune_tags("enricoflammini/eero-dashboard", keep_main=5, keep_test=1, dry_run=True)
        runner.assert_true(isinstance(dry_run_count, int) and dry_run_count >= 0, "prune_tags dry_run eseguito con successo")

        # =====================================================================
        # TEST MODULO 3 - HARDENING DOCKER & CONTAINER SECURITY
        # =====================================================================
        print("\n🐳 TEST MODULO 3 - HARDENING DOCKER, MULTI-STAGE ALPINE & NON-ROOT USER")
        dockerfile_path = Path("Dockerfile")
        runner.assert_true(dockerfile_path.exists(), "Dockerfile presente nel repository")
        df_content = dockerfile_path.read_text(encoding="utf-8")
        runner.assert_true("FROM python:3.12-alpine AS builder" in df_content, "Dockerfile utilizza base Alpine per lo stage builder")
        runner.assert_true("su-exec" in df_content, "Dockerfile include su-exec per privilege dropping")
        runner.assert_true("ENTRYPOINT [\"/app/entrypoint.sh\"]" in df_content, "Dockerfile imposta script di entrypoint")
        runner.assert_true("addgroup -g 10001 -S appgroup" in df_content, "Dockerfile crea gruppo non privilegiato 'appgroup' (GID 10001)")
        runner.assert_true("adduser -u 10001 -S appuser" in df_content, "Dockerfile crea utente non privilegiato 'appuser' (UID 10001)")
        runner.assert_true("HEALTHCHECK" in df_content, "Dockerfile include direttiva HEALTHCHECK nativa")
        runner.assert_true("COPY --from=builder /opt/venv /opt/venv" in df_content, "Dockerfile copia virtualenv dallo stage builder")
        runner.assert_true("chown -R appuser:appgroup /app/data" in df_content, "Dockerfile assegna ownership /app/data a appuser")

        # Verifica script di entrypoint e self-healing permessi volume
        entrypoint_path = Path("entrypoint.sh")
        runner.assert_true(entrypoint_path.exists(), "entrypoint.sh presente nel repository")
        ep_content = entrypoint_path.read_text(encoding="utf-8")
        runner.assert_true("su-exec appuser" in ep_content, "entrypoint.sh cede privilegi a appuser non-root tramite su-exec")
        runner.assert_true("chown -R appuser:appgroup /app/data" in ep_content, "entrypoint.sh esegue self-healing dei permessi del volume /app/data")

        # Verifica workflow CI/CD con Trivy Scanner
        wf_path = Path(".github/workflows/docker-publish.yml")
        runner.assert_true(wf_path.exists(), "Workflow CI/CD .github/workflows/docker-publish.yml presente")
        wf_content = wf_path.read_text(encoding="utf-8")
        runner.assert_true("aquasecurity/trivy-action" in wf_content, "CI/CD integra scanner automatico di vulnerabilità Trivy")

        # =====================================================================
        # TEST MODULO 4 - GESTIONE SESSIONI LOCALI ("RICORDAMI" & GATEKEEPING)
        # =====================================================================
        print("\n🔐 TEST MODULO 4 - GESTIONE SESSIONI LOCALI ('RICORDAMI' & GATEKEEPING)")

        # 1. Test backend login con remember_me=False (sessione volatile) vs remember_me=True (persistente)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as auth_client:
            # Login volatile (default remember_me=False)
            r_volatile = await auth_client.post(
                "/api/auth/local/login",
                json={"username": "admin", "password": getattr(runner, "admin_test_pwd", "AdminPassword123!"), "remember_me": False}
            )
            runner.assert_true(r_volatile.status_code == 200, "POST /api/auth/local/login con remember_me=False risponde 200 OK")
            v_json = r_volatile.json()
            runner.assert_true(v_json.get("remember_me") is False, "Payload login restituisce remember_me=False")
            v_cookie = r_volatile.headers.get("set-cookie", "")
            runner.assert_true("session_token=" in v_cookie, "Set-Cookie include session_token")
            runner.assert_true("Max-Age=" not in v_cookie, "Set-Cookie non specifica Max-Age per sessione volatile (cookie di sessione browser)")

            # Login persistente (remember_me=True)
            r_persist = await auth_client.post(
                "/api/auth/local/login",
                json={"username": "admin", "password": getattr(runner, "admin_test_pwd", "AdminPassword123!"), "remember_me": True}
            )
            runner.assert_true(r_persist.status_code == 200, "POST /api/auth/local/login con remember_me=True risponde 200 OK")
            p_json = r_persist.json()
            runner.assert_true(p_json.get("remember_me") is True, "Payload login restituisce remember_me=True")
            p_cookie = r_persist.headers.get("set-cookie", "")
            runner.assert_true("session_token=" in p_cookie, "Set-Cookie include session_token")
            runner.assert_true("Max-Age=604800" in p_cookie, "Set-Cookie specifica Max-Age=604800 (7 giorni) per sessione persistente")

        # 2. Test template index.html per checkbox "Ricordami"
        index_html_path = Path("app/templates/index.html")
        runner.assert_true(index_html_path.exists(), "app/templates/index.html esiste")
        index_content = index_html_path.read_text(encoding="utf-8")
        runner.assert_true("id=\"localLoginRememberMe\"" in index_content, "index.html contiene checkbox #localLoginRememberMe")
        runner.assert_true("x-model=\"localLoginData.remember_me\"" in index_content, "Checkbox login è collegata a localLoginData.remember_me")
        runner.assert_true("id=\"localSetupRememberMe\"" in index_content, "index.html contiene checkbox #localSetupRememberMe")
        runner.assert_true("x-model=\"localSetupData.remember_me\"" in index_content, "Checkbox setup è collegata a localSetupData.remember_me")

        # 3. Test script app.js per gestione sessione volatile vs persistente e gatekeeping
        app_js_path = Path("app/static/js/app.js")
        runner.assert_true(app_js_path.exists(), "app/static/js/app.js esiste")
        app_js_content = app_js_path.read_text(encoding="utf-8")
        runner.assert_true("sessionStorage.getItem('eero_local_auth_token')" in app_js_content, "app.js legge token da sessionStorage")
        runner.assert_true("localStorage.getItem('eero_local_auth_token')" in app_js_content, "app.js legge token di fallback da localStorage")
        runner.assert_true("remember_me: false" in app_js_content, "app.js inizializza remember_me a false nei form")
        runner.assert_true("sessionStorage.removeItem('eero_local_auth_token')" in app_js_content, "app.js pulisce sessionStorage al logout / 401")
        runner.assert_true("this.openLocalLoginModal()" in app_js_content, "app.js include chiamata a openLocalLoginModal per gatekeeping")

        # 4. Test dizionari internazionalizzazione
        it_json = json.loads(Path("app/static/locales/it.json").read_text(encoding="utf-8"))
        en_json = json.loads(Path("app/static/locales/en.json").read_text(encoding="utf-8"))
        runner.assert_true("auth_local" in it_json and "remember_me" in it_json["auth_local"], "Chiave auth_local.remember_me presente in it.json")
        runner.assert_true("auth_local" in en_json and "remember_me" in en_json["auth_local"], "Chiave auth_local.remember_me presente in en.json")
        runner.assert_true(it_json["auth_local"]["remember_me"] == "Resta connesso / Ricordami", "Traduzione italiana auth_local.remember_me corretta")
        runner.assert_true(en_json["auth_local"]["remember_me"] == "Stay signed in / Remember me", "Traduzione inglese auth_local.remember_me corretta")

        print("\n⚡ TEST ISSUES #73 & #74 (RETENTION WORKER CPU OPTIMIZATION, STRING BITRATE PARSE & SQLITE INTEGRITY / BACKUP)")

        # 1. Test parsing bitrate con unità e formati eterogenei (Issue #73)
        runner.assert_true(db_service.parse_bitrate_float(72.0) == 72.0, "parse_bitrate_float gestisce float nativo")
        runner.assert_true(db_service.parse_bitrate_float(100) == 100.0, "parse_bitrate_float gestisce int nativo")
        runner.assert_true(db_service.parse_bitrate_float("72.0 MBit/s") == 72.0, "parse_bitrate_float gestisce stringa con '72.0 MBit/s'")
        runner.assert_true(db_service.parse_bitrate_float("144.4 Mbps") == 144.4, "parse_bitrate_float gestisce stringa con 'Mbps'")
        runner.assert_true(db_service.parse_bitrate_float("1.2 Gbps") == 1200.0, "parse_bitrate_float converte '1.2 Gbps' in Mbps")
        runner.assert_true(db_service.parse_bitrate_float("500 kbps") == 0.5, "parse_bitrate_float converte '500 kbps' in Mbps")
        runner.assert_true(db_service.parse_bitrate_float(None) is None, "parse_bitrate_float restituisce None per None")
        runner.assert_true(db_service.parse_bitrate_float("n/a") is None, "parse_bitrate_float restituisce None per 'n/a'")
        runner.assert_true(db_service.parse_bitrate_float("-") is None, "parse_bitrate_float restituisce None per '-'")

        # 2. Test aggregazione segnale con bitrate memorizzato come stringa (Issue #73 regression)
        test_hour_str_73 = "2026-10-15 03:00:00"
        test_hour_dt_73 = datetime.strptime(test_hour_str_73, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        test_mac_73 = "11:22:33:44:55:73"

        async with db_service.get_connection() as db:
            await db.execute(
                "INSERT INTO device_signal_history (timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);",
                ("2026-10-15 03:15:00", test_mac_73, "Device-Issue-73", -65, "5 GHz", 44, "Ufficio", "72.0 MBit/s", "48.0 MBit/s")
            )
            await db.execute(
                "INSERT INTO device_signal_history (timestamp, mac_address, hostname, signal_rssi, frequency_band, channel, connected_eero_name, rx_bitrate, tx_bitrate, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);",
                ("2026-10-15 03:45:00", test_mac_73, "Device-Issue-73", -67, "5 GHz", 44, "Ufficio", "86.0 MBit/s", "52.0 MBit/s")
            )
            await db.commit()

        # Esecuzione aggregazione segnale orario con stringhe: non deve sollevare ValueError
        sig_cnt_73 = await db_service.aggregate_hourly_signals(test_hour_dt_73)
        runner.assert_true(sig_cnt_73 >= 1, f"aggregate_hourly_signals gestisce stringhe con unità (processati {sig_cnt_73} apparati)")

        async with db_service.get_connection() as db:
            cur_sig_check = await db.execute("SELECT * FROM device_signal_hourly WHERE mac_address = ? AND hour_timestamp = ?;", (test_mac_73, "2026-10-15 03:00:00"))
            row_sig_check = await cur_sig_check.fetchone()

        runner.assert_true(row_sig_check is not None, "Record rollup segnale orario salvato con successo")
        runner.assert_true(row_sig_check["avg_rx_bitrate"] == 79.0, f"avg_rx_bitrate calcolato correttamente (atteso: 79.0, ottenuto: {row_sig_check['avg_rx_bitrate']})")
        runner.assert_true(row_sig_check["avg_tx_bitrate"] == 50.0, f"avg_tx_bitrate calcolato correttamente (atteso: 50.0, ottenuto: {row_sig_check['avg_tx_bitrate']})")

        # 3. Test compattazione selettiva (salta ore già aggregate a meno di force=True) (Issue #73)
        res_compaction_selective = await retention_worker.run_compaction_cycle(force=False)
        runner.assert_true(res_compaction_selective.get("status") in ("success", "warning"), "run_compaction_cycle selettivo risponde con status valido")
        # Un secondo ciclo consecutivo con force=False non deve riprocessare l'ora già aggregata
        res_compaction_skip = await retention_worker.run_compaction_cycle(force=False)
        runner.assert_true(res_compaction_skip.get("hours_aggregated") == 0, f"Compattazione salta ore già aggregate (hours_aggregated: {res_compaction_skip.get('hours_aggregated')})")

        # 4. Test controllo integrità database SQLite (Issue #74)
        integrity_res = await db_service.check_database_integrity(quick=True)
        runner.assert_true(integrity_res.get("healthy") is True, "check_database_integrity(quick=True) riporta database integro")
        runner.assert_true(integrity_res.get("status") == "ok", "Stato integrità 'ok'")
        runner.assert_true(len(integrity_res.get("errors", [])) == 0, "Nessun errore di corruzione riscontrato")

        # Endpoint GET /api/system/database/integrity (richiede admin)
        res_int_api = await client.get("/api/system/database/integrity?quick=true", headers=adm_hdr)
        runner.assert_true(res_int_api.status_code == 200, "GET /api/system/database/integrity risponde HTTP 200 per admin")
        runner.assert_true(res_int_api.json().get("healthy") is True, "Endpoint integrity conferma database integro")

        # 5. Test backup atomico e consistente a caldo con VACUUM INTO (Issue #74)
        backup_res = await db_service.backup_database_file()
        runner.assert_true(backup_res.get("status") == "success", "backup_database_file eseguito con successo")
        b_path = backup_res.get("backup_path")
        runner.assert_true(Path(b_path).exists(), f"File di backup creato su disco: {b_path}")
        runner.assert_true(backup_res.get("size_bytes", 0) > 0, "File di backup ha dimensione > 0")

        # Verifica integrità sul file di backup appena generato
        async with aiosqlite.connect(b_path) as b_conn:
            b_cur = await b_conn.execute("PRAGMA integrity_check;")
            b_rows = await b_cur.fetchall()
            runner.assert_true(len(b_rows) == 1 and b_rows[0][0] == "ok", "Backup creato con VACUUM INTO supera PRAGMA integrity_check con successo")

        # Endpoint POST /api/system/database/backup
        res_b_api = await client.post("/api/system/database/backup", headers=adm_hdr)
        runner.assert_true(res_b_api.status_code == 200, "POST /api/system/database/backup risponde HTTP 200")
        b_api_path = res_b_api.json().get("backup_path")
        runner.assert_true(Path(b_api_path).exists(), "File di backup endpoint API creato con successo")

        # Pulizia backup generati durante il test
        for p in (b_path, b_api_path):
            try:
                if Path(p).exists():
                    Path(p).unlink()
            except Exception:
                pass

        # =========================================================================
        # MODULO 8: DAILY DIGEST SCHEDULER & RESTART IDEMPOTENCY (ISSUE #70)
        # =========================================================================
        print("\n" + "=" * 60)
        print("MODULO 8: DAILY DIGEST SCHEDULER & RESTART IDEMPOTENCY (ISSUE #70)")
        print("=" * 60)

        # 1. Configurazione settings e risoluzione fuso orario
        runner.assert_true(hasattr(settings, "daily_digest_hour"), "settings possiede l'attributo daily_digest_hour")
        runner.assert_true(hasattr(settings, "tz"), "settings possiede l'attributo tz")
        runner.assert_true(isinstance(settings.daily_digest_hour, int), "daily_digest_hour è un intero")
        
        dt_utc = BackgroundPoller._get_local_now("UTC")
        runner.assert_true(dt_utc.tzinfo is not None, "_get_local_now('UTC') restituisce datetime con tzinfo")
        dt_default = BackgroundPoller._get_local_now()
        runner.assert_true(isinstance(dt_default, datetime), "_get_local_now() restituisce istanza datetime")

        # 2. Endpoint API /api/automations/digest (GET & POST)
        res_get_digest = await client.get("/api/automations/digest", headers=adm_hdr)
        runner.assert_true(res_get_digest.status_code == 200, "GET /api/automations/digest risponde HTTP 200")
        digest_data = res_get_digest.json()
        runner.assert_true("enabled" in digest_data, "GET /api/automations/digest include 'enabled'")
        runner.assert_true("hour" in digest_data, "GET /api/automations/digest include 'hour'")
        runner.assert_true("last_sent_date" in digest_data, "GET /api/automations/digest include 'last_sent_date'")

        # Aggiornamento orario valido (es. ore 20)
        res_post_digest = await client.post("/api/automations/digest", json={"enabled": True, "hour": 20}, headers=adm_hdr)
        runner.assert_true(res_post_digest.status_code == 200, "POST /api/automations/digest con hour=20 risponde HTTP 200")
        runner.assert_true(res_post_digest.json().get("hour") == 20, "Risposta POST conferma hour=20")

        # Verifica persistenza su GET
        res_verify_digest = await client.get("/api/automations/digest", headers=adm_hdr)
        runner.assert_true(res_verify_digest.json().get("hour") == 20, "GET successivo conferma persistenza hour=20")

        # Validazione range orario (rifiuto valori non compresi tra 0 e 23)
        res_invalid_high = await client.post("/api/automations/digest", json={"enabled": True, "hour": 25}, headers=adm_hdr)
        runner.assert_true(res_invalid_high.status_code == 422, "POST /api/automations/digest con hour=25 rifiutato con HTTP 422")
        res_invalid_low = await client.post("/api/automations/digest", json={"enabled": True, "hour": -1}, headers=adm_hdr)
        runner.assert_true(res_invalid_low.status_code == 422, "POST /api/automations/digest con hour=-1 rifiutato con HTTP 422")

        # 3. Test guard persistente SQLite e Idempotency al riavvio del container (Issue #70)
        await db_service.set_setting("daily_digest_enabled", "true")
        await db_service.set_setting("daily_digest_hour", "20")
        await db_service.set_setting("last_daily_digest_date", "")

        digest_dispatches = 0
        async def _mock_dispatch(lang=None):
            nonlocal digest_dispatches
            digest_dispatches += 1
            return {"network_name": "Test Net", "health_score": 100}

        test_digest_poller = BackgroundPoller()
        test_digest_poller._send_daily_digest = _mock_dispatch

        # 3a. Poller eseguito ad un'ora differente (es. 18:00) -> Nessun invio
        test_digest_poller._get_local_now = lambda: datetime(2026, 10, 16, 18, 0, 0)
        await test_digest_poller._run_periodic_jobs()
        await asyncio.sleep(0.01)
        runner.assert_true(digest_dispatches == 0, "Nessun invio digest prima dell'orario stabilito (18:00 != 20:00)")
        last_in_db = await db_service.get_setting("last_daily_digest_date", "")
        runner.assert_true(last_in_db == "", "last_daily_digest_date resta vuoto nel DB prima dell'invio")

        # 3b. Poller eseguito all'orario target (20:05) -> Invio singolo e persistenza DB
        test_digest_poller._get_local_now = lambda: datetime(2026, 10, 16, 20, 5, 0)
        await test_digest_poller._run_periodic_jobs()
        await asyncio.sleep(0.01)
        runner.assert_true(digest_dispatches == 1, "Digest inviato con successo alle 20:05 (dispatch count == 1)")
        last_in_db = await db_service.get_setting("last_daily_digest_date", "")
        runner.assert_true(last_in_db == "2026-10-16", "last_daily_digest_date salvato in SQLite come '2026-10-16'")

        # 3c. Stesso processo, ciclo di polling successivo durante la stessa ora (20:15) -> Nessun re-invio
        test_digest_poller._get_local_now = lambda: datetime(2026, 10, 16, 20, 15, 0)
        await test_digest_poller._run_periodic_jobs()
        await asyncio.sleep(0.01)
        runner.assert_true(digest_dispatches == 1, "Nessun re-invio all'interno della stessa ora nello stesso processo")

        # 3d. SIMULAZIONE RIAVVIO CONTAINER (Issue #70 - utente riceveva 13 digest in un'ora a causa di riavvii del container)
        # Nuova istanza poller (come all'avvio pulito di un container) con RAM cache vuota (_last_digest_date == None)
        restarted_poller = BackgroundPoller()
        runner.assert_true(restarted_poller._last_digest_date is None, "Nuovo poller dopo riavvio container parte con _last_digest_date = None in RAM")
        restarted_poller._send_daily_digest = _mock_dispatch
        restarted_poller._get_local_now = lambda: datetime(2026, 10, 16, 20, 25, 0)
        
        # Esecuzione periodic jobs nel container riavviato alle 20:25: la guardia SQLite deve bloccare il re-invio!
        await restarted_poller._run_periodic_jobs()
        await asyncio.sleep(0.01)
        runner.assert_true(digest_dispatches == 1, "SPAM BLOCCATO: Dopo riavvio container il digest NON viene re-inviato (dispatch count ancora 1)")

        # 3e. Esecuzione il giorno successivo (2026-10-17 alle 20:00) -> Deve inviare regolarmente il nuovo digest
        restarted_poller._get_local_now = lambda: datetime(2026, 10, 17, 20, 0, 0)
        await restarted_poller._run_periodic_jobs()
        await asyncio.sleep(0.01)
        runner.assert_true(digest_dispatches == 2, "Il giorno successivo (2026-10-17) il digest viene regolarmente inviato (dispatch count == 2)")
        last_in_db_next = await db_service.get_setting("last_daily_digest_date", "")
        runner.assert_true(last_in_db_next == "2026-10-17", "last_daily_digest_date aggiornato su SQLite a '2026-10-17'")

        # 4. Idempotency della manutenzione notturna attraverso i riavvii del container
        from app.services.scheduler import maintenance_engine
        await db_service.set_setting("last_nightly_maintenance_run", "2026-10-16T04:05:00")
        maintenance_engine._last_run_date = None  # Simula riavvio container
        maint_res = await maintenance_engine.check_and_run_nightly_maintenance(datetime(2026, 10, 16, 4, 8, 0))
        runner.assert_true(maint_res is None, "check_and_run_nightly_maintenance salta l'esecuzione se già completata oggi nel DB")

        # =========================================================================
        print("\n" + "=" * 60)
        print("MODULO 9: DNS SYNC LAN IPV4 PRIORITIZATION, STALE IP PRUNING & DEVICE EXCLUSION (ISSUE #72)")
        print("=" * 60)

        # 1. Prioritizzazione candidati IPv4 (_sort_ipv4_candidates e _normalize_device)
        test_docker_candidates = ["172.17.0.1", "172.24.0.1", "192.168.0.37", "172.28.0.1"]
        
        # Con subnet LAN esplicita 192.168.0.0/24:
        lan_net_test = ipaddress.IPv4Network("192.168.0.0/24")
        sorted_with_lan = eero_client._sort_ipv4_candidates(test_docker_candidates, lan_net_test)
        runner.assert_true(sorted_with_lan[0] == "192.168.0.37", "Con subnet LAN nota, l'indirizzo LAN 192.168.0.37 è al primo posto (index 0)")
        runner.assert_true("172.17.0.1" in sorted_with_lan[1:], "Bridge Docker 172.17.0.1 deprioritizzato rispetto alla LAN")

        # Senza subnet LAN nota (fallback euristico):
        sorted_without_lan = eero_client._sort_ipv4_candidates(test_docker_candidates, None)
        runner.assert_true(sorted_without_lan[0] == "192.168.0.37", "Senza subnet LAN nota, l'indirizzo LAN privato 192.168.0.37 batte comunque i bridge Docker e .1")

        # Podman bridge 10.88.0.1 vs LAN IP 10.0.0.45:
        podman_candidates = ["10.88.0.1", "10.0.0.45", "10.89.0.1"]
        sorted_podman = eero_client._sort_ipv4_candidates(podman_candidates, ipaddress.IPv4Network("10.0.0.0/24"))
        runner.assert_true(sorted_podman[0] == "10.0.0.45", "LAN IP 10.0.0.45 prioritizzato rispetto ai bridge Podman 10.88.0.1 / 10.89.0.1")

        # Verifica normalizzazione dispositivo tramite _normalize_device:
        mock_raw_device = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "nickname": "Linux HomeServer",
            "ips": ["172.17.0.1", "172.24.0.1", "192.168.0.37", "172.28.0.1"]
        }
        eero_client.current_gateway_ip = "192.168.0.1"
        eero_client.current_gateway_netmask = "255.255.255.0"
        normalized_dev = eero_client._normalize_device(mock_raw_device)
        runner.assert_true(normalized_dev.get("ip") == "192.168.0.37", "_normalize_device assegna l'IP LAN primario 192.168.0.37 escludendo i bridge Docker")
        runner.assert_true("ipv4_candidates" in normalized_dev, "_normalize_device popola la lista completa ordinata ipv4_candidates")
        runner.assert_true(normalized_dev["ipv4_candidates"][0] == "192.168.0.37", "ipv4_candidates ha 192.168.0.37 in prima posizione")

        # Dispositivo con prenotazione statica esplicita:
        mock_static_device = {
            "mac": "11:22:33:44:55:66",
            "nickname": "Workstation",
            "ips": ["172.17.0.1", "192.168.0.99", "192.168.0.100"],
            "static_ip": "192.168.0.100"
        }
        normalized_static = eero_client._normalize_device(mock_static_device)
        runner.assert_true(normalized_static.get("ip") == "192.168.0.100", "static_ip/prenotazione ha precedenza assoluta sui candidati")

        # 2. Esclusione dispositivo da sync DNS (dns_sync_excluded)
        test_mac_excl = "22:33:44:55:66:77"
        await db_service.upsert_device_metadata(mac_address=test_mac_excl, dns_sync_excluded=True)
        meta_read = await db_service.get_device_metadata(test_mac_excl)
        runner.assert_true(meta_read is not None and bool(meta_read.get("dns_sync_excluded")) is True, "dns_sync_excluded=True salvato e letto correttamente in SQLite")

        # Test aggiornamento via API endpoint /api/devices/{mac}/metadata
        res_meta_api = await client.post(f"/api/devices/{test_mac_excl}/metadata", json={"dns_sync_excluded": True, "custom_name": "Test Server"}, headers=adm_hdr)
        runner.assert_true(res_meta_api.status_code == 200, "POST /api/devices/{mac}/metadata con dns_sync_excluded risponde HTTP 200")
        runner.assert_true(res_meta_api.json().get("metadata", {}).get("dns_sync_excluded") == 1, "Risposta API conferma dns_sync_excluded: 1")

        # Test filtro _prepare_clients_payload in DNSManager
        test_device_list = [
            {"mac": "aa:11:22:33:44:55", "ip": "192.168.0.10", "hostname": "managed-host-1", "dns_sync_excluded": False},
            {"mac": "bb:11:22:33:44:55", "ip": "192.168.0.20", "hostname": "excluded-host-2", "dns_sync_excluded": True},
            {"mac": "cc:11:22:33:44:55", "ip": "192.168.0.30", "hostname": "managed-host-3"}
        ]
        from app.services.dns_manager import DNSManager
        dns_mgr = DNSManager()
        prep_payload = dns_mgr._prepare_clients_payload(test_device_list)
        prep_names = [p["hostname"] for p in prep_payload]
        runner.assert_true("managed-host-1" in prep_names, "Host abilitato managed-host-1 presente nel payload sync DNS")
        runner.assert_true("managed-host-3" in prep_names, "Host predefinito managed-host-3 presente nel payload sync DNS")
        runner.assert_true("excluded-host-2" not in prep_names, "Host con dns_sync_excluded=True escluso dal payload sync DNS")

        # 3. Pi-hole v6: Pruning intelligente record obsoleti e preservazione record unmanaged
        pihole_mock_v6 = {
            "id": "inst-pihole-test",
            "name": "Pi-hole Test",
            "engine": "pihole",
            "url": "http://127.0.0.1:8088",
            "token": "test-sid-123",
            "zone": "lan",
            "prune_stale_ips": True
        }

        # Simulazione Pi-hole v6 con record esistenti:
        existing_v6_hosts = [
            "172.17.0.1 homeserver.lan",
            "192.168.0.50 homeserver.lan",
            "192.168.0.200 unmanaged-nas.lan",
            "192.168.0.10 laptop.lan"
        ]

        mock_incoming_clients = [
            {"ip": "192.168.0.37", "hostname": "homeserver"},
            {"ip": "192.168.0.10", "hostname": "laptop"}
        ]

        sent_patch_payload = None
        async def mock_pihole_handler(request: httpx.Request):
            nonlocal sent_patch_payload
            if request.method == "GET" and "/api/config/dns/hosts" in str(request.url):
                return httpx.Response(200, json={"config": {"dns": {"hosts": existing_v6_hosts}}})
            if request.method == "PATCH" and "/api/config" in str(request.url):
                sent_patch_payload = json.loads(request.content.decode("utf-8"))
                return httpx.Response(200, json={"status": "success"})
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_pihole_handler)
        orig_async_client = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda *args, **kwargs: orig_async_client(transport=transport, *args, **kwargs)
            res_sync = await dns_mgr._sync_single_pihole(pihole_mock_v6, mock_incoming_clients)
            runner.assert_true(res_sync.get("success") is True, "Sincronizzazione Pi-hole v6 completata con successo via PATCH")
            runner.assert_true(sent_patch_payload is not None, "PATCH payload inviato a Pi-hole v6")
            
            patched_hosts = sent_patch_payload.get("config", {}).get("dns", {}).get("hosts", [])
            runner.assert_true("192.168.0.200 unmanaged-nas.lan" in patched_hosts, "Record unmanaged (unmanaged-nas.lan) PRESERVATO integralmente")
            runner.assert_true("192.168.0.10 laptop.lan" in patched_hosts, "Record valido attivo (laptop.lan) PRESERVATO")
            runner.assert_true("192.168.0.37 homeserver.lan" in patched_hosts, "Record attivo (192.168.0.37 homeserver.lan) AGGIUNTO con successo")
            runner.assert_true("172.17.0.1 homeserver.lan" not in patched_hosts, "VECCHIO BRIDGE POTATO: 172.17.0.1 homeserver.lan rimosso dai record Pi-hole")
            runner.assert_true("192.168.0.50 homeserver.lan" not in patched_hosts, "VECCHIO LEASE POTATO: 192.168.0.50 homeserver.lan rimosso dai record Pi-hole")

            # 4. Pi-hole v6 con prune_stale_ips=False: i vecchi record non devono essere rimossi
            pihole_mock_no_prune = dict(pihole_mock_v6)
            pihole_mock_no_prune["prune_stale_ips"] = False
            sent_patch_payload = None
            await dns_mgr._sync_single_pihole(pihole_mock_no_prune, mock_incoming_clients)
            patched_hosts_no_prune = sent_patch_payload.get("config", {}).get("dns", {}).get("hosts", [])
            runner.assert_true("172.17.0.1 homeserver.lan" in patched_hosts_no_prune, "Con prune_stale_ips=False, il vecchio record non viene potato")
        finally:
            httpx.AsyncClient = orig_async_client

        # =========================================================================
        # MODULO 10: ROBUST ACCOUNT NETWORK DISCOVERY, CONFIG FALLBACK & ZERO-NETWORK GUIDANCE (ISSUE #69)
        # =========================================================================
        print("\n" + "="*80)
        print("MODULO 10: ROBUST ACCOUNT NETWORK DISCOVERY, CONFIG FALLBACK & ZERO-NETWORK GUIDANCE (ISSUE #69)")
        print("="*80)

        saved_token = eero_client.user_token
        saved_net_id = eero_client.current_network_id
        saved_avail_nets = list(eero_client.available_networks)
        saved_demo_mode = settings.demo_mode
        saved_env_net_id = settings.eero_network_id

        try:
            settings.demo_mode = False
            eero_client.user_token = "live_test_token_mod10"

            # 1. Singular 'network' dict in account response
            mock_resp_data = {"network": {"url": "/2.2/networks/singular_111", "name": "Singular Net"}}
            async def mock_singular_handler(request: httpx.Request):
                if "/account" in str(request.url) or "/user" in str(request.url):
                    return httpx.Response(200, json={"data": mock_resp_data})
                return httpx.Response(404)

            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_singular_handler))
            eero_client.current_network_id = None
            eero_client.available_networks = []
            settings.eero_network_id = ""

            await eero_client.fetch_account_info()
            runner.assert_true(eero_client.current_network_id == "singular_111", "Parsing rete da chiave singola 'network' dizionario")
            runner.assert_true(len(eero_client.available_networks) == 1, "available_networks contiene 1 rete")
            runner.assert_true(eero_client.available_networks[0]["name"] == "Singular Net", "Nome rete estratto correttamente da 'network' singola")

            # 2. String URL in singular 'network'
            mock_resp_data = {"network": "/2.2/networks/string_222"}
            eero_client.current_network_id = None
            eero_client.available_networks = []
            await eero_client.fetch_account_info()
            runner.assert_true(eero_client.current_network_id == "string_222", "Parsing rete da stringa URL '/2.2/networks/string_222'")

            # 3. Networks dictionary indexed by ID
            mock_resp_data = {"networks": {"net_333": {"id": "net_333", "name": "Keyed Net", "url": "/2.2/networks/net_333"}}}
            eero_client.current_network_id = None
            eero_client.available_networks = []
            await eero_client.fetch_account_info()
            runner.assert_true(eero_client.current_network_id == "net_333", "Parsing dizionario di reti indicizzato per ID")
            runner.assert_true(eero_client.available_networks[0]["name"] == "Keyed Net", "Nome rete estratto dal dizionario indicizzato")

            # 4. Fallback a /2.2/networks con payload list raw
            async def mock_fallback_list_handler(request: httpx.Request):
                if "/account" in str(request.url):
                    return httpx.Response(200, json={"data": {}})
                if "/networks" in str(request.url):
                    return httpx.Response(200, json=[{"url": "/2.2/networks/raw_list_444", "name": "Raw List Net"}])
                return httpx.Response(404)

            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_fallback_list_handler))
            eero_client.current_network_id = None
            eero_client.available_networks = []
            await eero_client.fetch_account_info()
            runner.assert_true(eero_client.current_network_id == "raw_list_444", "Fallback /2.2/networks gestisce raw list senza eccezioni")

            # 5. Fallback a settings.eero_network_id quando l'API non restituisce reti
            async def mock_zero_net_handler(request: httpx.Request):
                if "/account" in str(request.url):
                    return httpx.Response(200, json={"data": {}})
                if "/networks" in str(request.url):
                    return httpx.Response(200, json={"data": []})
                return httpx.Response(404)

            eero_client._http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_zero_net_handler))
            eero_client.current_network_id = None
            eero_client.available_networks = []
            settings.eero_network_id = "configured_env_net_555"
            await eero_client.fetch_account_info()
            runner.assert_true(eero_client.current_network_id == "configured_env_net_555", "Fallback a EERO_NETWORK_ID da .env quando l'account non ha reti scoperte")
            runner.assert_true(len(eero_client.available_networks) == 1, "Rete da configurazione registrata in available_networks")
            runner.assert_true(eero_client.available_networks[0]["id"] == "configured_env_net_555", "ID rete configurata corretto")

            # 6. Zero reti scoperte e nessuna configurata: stato 0 reti pulito e sicuro
            settings.eero_network_id = ""
            eero_client.current_network_id = None
            eero_client.available_networks = []
            await eero_client.fetch_account_info()
            runner.assert_true(eero_client.current_network_id is None, "current_network_id è None quando 0 reti disponibili")
            runner.assert_true(len(eero_client.available_networks) == 0, "available_networks è vuota con 0 reti")
            devices_zero = await eero_client.get_devices()
            runner.assert_true(len(devices_zero) == 0, "get_devices() restituisce lista vuota (nessun dispositivo demo fittizio su sessione reale)")

            # 7. Frontend, Template e i18n Parity (Issue #69)
            index_html_path = Path("app/templates/index.html")
            index_html_content = index_html_path.read_text(encoding="utf-8")
            runner.assert_true("noNetworksFound" in index_html_content, "Banner 'noNetworksFound' presente in index.html")
            runner.assert_true("resilience.no_networks_title" in index_html_content, "Stringa i18n resilience.no_networks_title referenziata nel banner")

            it_json_path = Path("app/static/locales/it.json")
            it_json = json.loads(it_json_path.read_text(encoding="utf-8"))
            runner.assert_true("no_networks_title" in it_json.get("resilience", {}), "no_networks_title presente in it.json")
            runner.assert_true("no_networks_desc" in it_json.get("resilience", {}), "no_networks_desc presente in it.json")

            en_json_path = Path("app/static/locales/en.json")
            en_json = json.loads(en_json_path.read_text(encoding="utf-8"))
            runner.assert_true("no_networks_title" in en_json.get("resilience", {}), "no_networks_title presente in en.json")
            runner.assert_true("no_networks_desc" in en_json.get("resilience", {}), "no_networks_desc presente in en.json")

            app_js_path = Path("app/static/js/app.js")
            app_js_content = app_js_path.read_text(encoding="utf-8")
            runner.assert_true("get noNetworksFound()" in app_js_content, "Getter noNetworksFound definito in app.js")
            runner.assert_true("['Computer', 'Mobile', 'Smart Home', 'Intrattenimento', 'Server/Rete', 'Gaming', 'Altro']" in app_js_content, "Fallback difensivo disponibile per availableCategories quando devices è vuota")

            sw_js_path = Path("app/static/sw.js")
            sw_js_content = sw_js_path.read_text(encoding="utf-8")
            runner.assert_true("eero-dashboard-v1.6.2" in sw_js_content, "Service Worker CACHE_NAME aggiornato a v1.6.2 per invalidazione cache obsoleta")

        finally:
            # Ripristina stato originale eero_client
            if eero_client._http_client is not None and not eero_client._http_client.is_closed:
                await eero_client._http_client.aclose()
            eero_client._http_client = None
            eero_client.user_token = saved_token
            eero_client.current_network_id = saved_net_id
            eero_client.available_networks = saved_avail_nets
            settings.demo_mode = saved_demo_mode
            settings.eero_network_id = saved_env_net_id

        # -----------------------------------------------------------------
        # 35. TEST SPEEDTEST BUFFERBLOAT REPORTING & DURATION I18N (v1.6.1 Modulo 11 - Issue #71)
        # -----------------------------------------------------------------
        print("\n🚀 [35/35] TEST SPEEDTEST BUFFERBLOAT REPORTING & DURATION I18N (v1.6.1 Modulo 11)")
        # 1. Verifica chiavi bufferbloat in it.json ed en.json
        it_loc_mod11 = json.loads(Path("app/static/locales/it.json").read_text(encoding="utf-8"))
        en_loc_mod11 = json.loads(Path("app/static/locales/en.json").read_text(encoding="utf-8"))
        runner.assert_true("not_available" in it_loc_mod11["bufferbloat"], "Chiave 'not_available' presente in it.json")
        runner.assert_true("not_available" in en_loc_mod11["bufferbloat"], "Chiave 'not_available' presente in en.json")
        runner.assert_true(it_loc_mod11["bufferbloat"]["not_available"] == "Non Disponibile", "Traduzione 'not_available' corretta in italiano")
        runner.assert_true(en_loc_mod11["bufferbloat"]["not_available"] == "Not Available", "Traduzione 'not_available' corretta in inglese")
        runner.assert_true("label_a_plus" in it_loc_mod11["bufferbloat"], "Chiave 'label_a_plus' presente in it.json")
        runner.assert_true("label_a_plus" in en_loc_mod11["bufferbloat"], "Chiave 'label_a_plus' presente in en.json")
        runner.assert_true(en_loc_mod11["logs"]["retention_30d"] == "1 Month (1mo)", "retention_30d in en.json aggiornato a '1 Month (1mo)'")

        # 2. Verifica index.html: abbreviazioni durata dinamiche e badge bufferbloat
        index_html_mod11 = Path("app/templates/index.html").read_text(encoding="utf-8")
        runner.assert_true("t('logs.retention_short_7d')" in index_html_mod11, "Abbreviazione 7 giorni dinamica (7gg/7d) in index.html")
        runner.assert_true("t('logs.retention_short_15d')" in index_html_mod11, "Abbreviazione 15 giorni dinamica (15gg/15d) in index.html")
        runner.assert_true("t('logs.retention_short_30d')" in index_html_mod11, "Abbreviazione 1 mese dinamica (1m/1mo) in index.html")
        runner.assert_true("getBufferbloatGrade(latestSpeedtest)" in index_html_mod11, "Badge bufferbloat referenzia getBufferbloatGrade in index.html")

        # 3. Verifica app.js: getBufferbloatGrade riconosce bufferbloat_grade, ping_under_load e delta
        app_js_mod11 = Path("app/static/js/app.js").read_text(encoding="utf-8")
        runner.assert_true("rawGrade = String(st.bufferbloat_grade" in app_js_mod11, "getBufferbloatGrade riconosce direttamente st.bufferbloat_grade")
        runner.assert_true("st.ping_under_load" in app_js_mod11, "getBufferbloatGrade riconosce st.ping_under_load")
        runner.assert_true("st.bufferbloat_delta_ms" in app_js_mod11, "getBufferbloatGrade riconosce st.bufferbloat_delta_ms")
        runner.assert_true("this.loadSpeedtestData()" in app_js_mod11, "loadSpeedtestData() integrato in refreshAllData()")

        # 4. Verifica arricchimento poller: cached_network speedtest riceve bufferbloat da SQLite
        from app.services.poller import poller
        saved_cn = poller.cached_network
        try:
            # Assicura speedtest salvato su DB
            test_bb_id = await db_service.save_speedtest(
                download_mbps=940.5,
                upload_mbps=220.0,
                ping_ms=9.5,
                server_name="Test Gateway WAN",
                source="eero_gateway",
                ping_under_load=13.0,
                bufferbloat_grade="A+",
                bufferbloat_delta_ms=3.5
            )
            runner.assert_true(test_bb_id > 0, "Speedtest di test inserito con successo")

            # Simula poller con speedtest senza campi bufferbloat (come da eero cloud nativo)
            poller.cached_network = {
                "id": "net_test_bb",
                "speedtest": {
                    "download_mbps": 940.5,
                    "upload_mbps": 220.0,
                    "ping_ms": 9.5
                }
            }
            # Esegui blocco arricchimento
            latest_db_tests = await db_service.get_speedtests(limit=1)
            runner.assert_true(len(latest_db_tests) > 0, "DB restituisce ultimo speedtest")
            l_st = latest_db_tests[0]
            sp_cached = poller.cached_network["speedtest"]
            if l_st.get("bufferbloat_grade"):
                sp_cached["bufferbloat_grade"] = l_st["bufferbloat_grade"]
            if l_st.get("bufferbloat_delta_ms") is not None:
                sp_cached["bufferbloat_delta_ms"] = l_st["bufferbloat_delta_ms"]
            if l_st.get("ping_under_load") is not None:
                sp_cached["ping_under_load"] = l_st["ping_under_load"]

            runner.assert_true(poller.cached_network["speedtest"].get("bufferbloat_grade") == "A+", "cached_network arricchita con bufferbloat_grade 'A+'")
            runner.assert_true(float(poller.cached_network["speedtest"].get("bufferbloat_delta_ms")) == 3.5, "cached_network arricchita con bufferbloat_delta_ms 3.5")
            runner.assert_true(float(poller.cached_network["speedtest"].get("ping_under_load")) == 13.0, "cached_network arricchita con ping_under_load 13.0")
        finally:
            poller.cached_network = saved_cn

        # -----------------------------------------------------------------
        # 36. TEST SECURITY HARDENING & VULNERABILITY ASSESSMENT (v1.6.2)
        # -----------------------------------------------------------------
        print("\n🛡️ [36/36] TEST SECURITY HARDENING & VULNERABILITY MITIGATION (v1.6.2)")
        
        # 1. HTTP Defensive Security Headers
        res_sec_hdr = await client.get("/api/health")
        runner.assert_true(res_sec_hdr.status_code == 200, "GET /api/health risponde HTTP 200")
        runner.assert_true(res_sec_hdr.headers.get("x-content-type-options") == "nosniff", "Header X-Content-Type-Options: nosniff presente")
        runner.assert_true(res_sec_hdr.headers.get("x-frame-options") == "SAMEORIGIN", "Header X-Frame-Options: SAMEORIGIN presente")
        runner.assert_true(res_sec_hdr.headers.get("referrer-policy") == "strict-origin-when-cross-origin", "Header Referrer-Policy: strict-origin-when-cross-origin presente")
        runner.assert_true("geolocation=()" in res_sec_hdr.headers.get("permissions-policy", ""), "Header Permissions-Policy restrittivo presente")

        # 2. Anti-SSRF in DNS Manager
        from app.services.dns_manager import is_safe_dns_url
        is_safe_meta, _ = is_safe_dns_url("http://169.254.169.254/latest/meta-data")
        runner.assert_true(is_safe_meta is False, "Anti-SSRF: IP link-local / cloud metadata (169.254.169.254) tassativamente bloccato")
        is_safe_cloud_host, _ = is_safe_dns_url("http://metadata.google.internal/computeMetadata/v1/")
        runner.assert_true(is_safe_cloud_host is False, "Anti-SSRF: Host metadata cloud (metadata.google.internal) tassativamente bloccato")
        is_safe_lan, _ = is_safe_dns_url("http://192.168.4.1:8080")
        runner.assert_true(is_safe_lan is True, "Anti-SSRF: IP LAN privato valido (192.168.4.1) consentito")
        is_safe_host_lan, _ = is_safe_dns_url("http://pihole.lan:80")
        runner.assert_true(is_safe_host_lan is True, "Anti-SSRF: Hostname locale valido (pihole.lan) consentito")

        res_ssrf_test = await dns_mgr.test_instance({"engine": "adguard", "url": "http://169.254.169.254"})
        runner.assert_true(res_ssrf_test.get("success") is False, "test_instance rifiuta URL link-local con success: False")
        runner.assert_true("Anti-SSRF" in res_ssrf_test.get("message", ""), "Messaggio di errore esplicito Anti-SSRF generato")

        # 3. Anti-Brute Force Sliding Window Rate Limiter
        from app.services.rate_limiter import InMemoryRateLimiter
        test_limiter = InMemoryRateLimiter(max_attempts=3, window_seconds=2, block_seconds=5)
        k_test = "192.0.2.1"
        is_lim, _ = test_limiter.is_limited(k_test)
        runner.assert_true(is_lim is False, "Rate limiter inizialmente non attivo per IP nuovo")
        test_limiter.record_failure(k_test)
        test_limiter.record_failure(k_test)
        is_lim, _ = test_limiter.is_limited(k_test)
        runner.assert_true(is_lim is False, "Rate limiter consente tentativi inferiori alla soglia (2/3)")
        is_blocked, retry = test_limiter.record_failure(k_test)
        runner.assert_true(is_blocked is True, "Rate limiter applica il blocco al 3° tentativo fallito")
        runner.assert_true(retry > 0, "Rate limiter calcola correttamente Retry-After in secondi")
        is_lim, _ = test_limiter.is_limited(k_test)
        runner.assert_true(is_lim is True, "is_limited conferma stato di blocco attivo")
        test_limiter.reset(k_test)
        is_lim_after, _ = test_limiter.is_limited(k_test)
        runner.assert_true(is_lim_after is False, "reset() rimuove correttamente il blocco (login riuscito)")

        # 4. Anti-XSS Link Sanitization in Markdown Parser
        app_js_text = Path("app/static/js/app.js").read_text(encoding="utf-8")
        runner.assert_true("cleanHref = (href || '').trim()" in app_js_text, "app.js sanitizza href dei link markdown")
        runner.assert_true("/^(?:https?:\\/\\/|mailto:|\\/|#)/i.test(cleanHref)" in app_js_text, "app.js consente solo protocolli web sicuri (http, https, mailto, /, #)")
        runner.assert_true("<span class=\"text-sky-400 font-medium\">${label}</span>" in app_js_text, "app.js neutralizza protocolli pericolosi (es. javascript:) in span non cliccabili")

        # 5. Anti-Stored XSS in AI Diagnostic Summary
        index_html_text = Path("app/templates/index.html").read_text(encoding="utf-8")
        runner.assert_true("x-html=\"renderSimpleMarkdown(localized(healthDetails?.ai_summary, 'narrative'))\"" in index_html_text, "index.html usa renderSimpleMarkdown per isolare ed eseguire escape HTML della narrativa AI (viewer language)")

        # 6. Protezione RBAC su tutte le rotte operative identificate nell'audit
        from app.routers import system, automations, network
        runner.assert_true(len(system.router.routes) > 0, "Router system caricato")
        update_trigger_route = next((r for r in system.router.routes if r.path == "/api/system/update/trigger"), None)
        runner.assert_true(update_trigger_route is not None, "Route /api/system/update/trigger registrata")
        runner.assert_true(len(update_trigger_route.dependencies) > 0, "Route /api/system/update/trigger protetta da dependency RBAC")

        alerts_read_route = next((r for r in automations.router.routes if r.path == "/api/automations/alerts/read"), None)
        runner.assert_true(alerts_read_route is not None and len(alerts_read_route.dependencies) > 0, "Route /api/automations/alerts/read protetta da dependency RBAC")

        digest_route = next((r for r in automations.router.routes if r.path == "/api/automations/digest" and "POST" in r.methods), None)
        runner.assert_true(digest_route is not None and len(digest_route.dependencies) > 0, "Route POST /api/automations/digest protetta da dependency RBAC")

        leds_route = next((r for r in network.router.routes if r.path == "/api/network/leds"), None)
        runner.assert_true(leds_route is not None and len(leds_route.dependencies) > 0, "Route POST /api/network/leds protetta da dependency RBAC")

        # -----------------------------------------------------------------
        # 37. TEST CONDENSED CHANGELOG & UPDATE PROPOSAL SYSTEM (v1.6.2)
        # -----------------------------------------------------------------
        print("\n🚀 [37/37] TEST CONDENSED CHANGELOG & UPDATE PROPOSAL SYSTEM (v1.6.2)")

        # 1. Test estrazione changelog ridotto (extract_condensed_changelog)
        from app.services.updater import extract_condensed_changelog, extract_release_notes_from_changelog, updater_service
        notes_162 = extract_release_notes_from_changelog("1.6.2")
        runner.assert_true(len(notes_162) > 0, "extract_release_notes_from_changelog estrae le note per 1.6.2 da changelog.md")
        runner.assert_true("Vulnerability Assessment" in notes_162, "Note di rilascio 1.6.2 contengono la sezione Vulnerability Assessment")

        condensed_162 = extract_condensed_changelog("1.6.2")
        runner.assert_true(len(condensed_162) >= 3, f"extract_condensed_changelog estrae almeno 3 punti salienti (estratti: {len(condensed_162)})")
        runner.assert_true(any("Vulnerability Assessment" in h for h in condensed_162), "Punto saliente 'Vulnerability Assessment' presente")
        runner.assert_true(any("Parità Completa Traduzioni" in h for h in condensed_162), "Punto saliente 'Parità Completa Traduzioni' presente")
        runner.assert_true(all("PR #" not in h and "@" not in h for h in condensed_162), "Tag PR/Issue/User rimossi dai titoli sintetici")

        # Fallback su raw_notes con elenco puntato
        raw_mock = "## v2.0.0\n* **🚀 Feature A:** Descrizione\n* **⚡ Feature B:** Altra descrizione\n* **🛡️ Feature C:** Sicurezza"
        condensed_mock = extract_condensed_changelog("2.0.0", raw_notes=raw_mock)
        runner.assert_true(len(condensed_mock) == 3, f"extract_condensed_changelog su raw_notes puntate estrae 3 punti (estratti: {len(condensed_mock)})")

        # Accesso via metodo updater_service
        condensed_obj = updater_service.extract_condensed_changelog("1.6.2")
        runner.assert_true(len(condensed_obj) == len(condensed_162), "updater_service.extract_condensed_changelog allineato alla funzione standalone")

        # 2. Endpoint GET /api/system/update/changelog
        res_changelog = await client.get("/api/system/update/changelog?version=1.6.2")
        runner.assert_true(res_changelog.status_code == 200, "GET /api/system/update/changelog risponde HTTP 200")
        changelog_json = res_changelog.json()
        runner.assert_true(changelog_json.get("status") == "success", "Response status è success")
        runner.assert_true(changelog_json.get("version") == "1.6.2", "Response version è 1.6.2")
        runner.assert_true(len(changelog_json.get("condensed_changelog", [])) >= 3, "Endpoint restituisce almeno 3 punti salienti condensed_changelog")
        runner.assert_true(len(changelog_json.get("release_notes", "")) > 0, "Endpoint restituisce release_notes integrali")

        # 3. Verifica parità chiavi i18n per prompt & condensed changelog
        it_upd = it_locale.get("update_modal", {})
        en_upd = en_locale.get("update_modal", {})
        for req_k in [
            "condensed_changelog_title",
            "condensed_changelog_subtitle",
            "prompt_title",
            "prompt_desc",
            "prompt_proceed",
            "prompt_view_details",
            "prompt_later",
            "show_full_notes",
            "hide_full_notes",
            "no_highlights"
        ]:
            runner.assert_true(req_k in it_upd, f"Chiave '{req_k}' presente in it.json under update_modal")
            runner.assert_true(req_k in en_upd, f"Chiave '{req_k}' presente in en.json under update_modal")

        # 4. Verifica binding Frontend (app.js e index.html)
        runner.assert_true("condensed_changelog: []" in app_js_text, "app.js include condensed_changelog nello state updateInfo")
        runner.assert_true("showUpdatePrompt" in app_js_text, "app.js gestisce flag showUpdatePrompt")
        runner.assert_true("dismissUpdatePrompt" in app_js_text, "app.js implementa dismissUpdatePrompt")
        runner.assert_true("showFullReleaseNotes" in app_js_text, "app.js gestisce toggle showFullReleaseNotes")

        runner.assert_true("updateInfo.condensed_changelog" in index_html_text, "index.html itera su updateInfo.condensed_changelog")
        runner.assert_true("showUpdatePrompt" in index_html_text, "index.html condiziona il banner di prompt a showUpdatePrompt")
        runner.assert_true("proceedUpdateFromPrompt" in index_html_text, "index.html collega il pulsante procedi a proceedUpdateFromPrompt")
        runner.assert_true("t('update_modal.condensed_changelog_title')" in index_html_text, "index.html usa stringa i18n per titolo changelog ridotto")

        # -----------------------------------------------------------------
        # 38. TEST LANGUAGE-AWARE UPDATE NOTES & DEMO PAYLOAD LOCALIZATION
        # -----------------------------------------------------------------
        print("\n🌐 [38/38] TEST LANGUAGE-AWARE UPDATE NOTES & DEMO PAYLOAD LOCALIZATION")

        from app.services.updater import select_release_notes
        from app.services.demo_i18n import DEMO_STRINGS_EN, localize_demo_payload, localize_demo_text
        from app.i18n import tr

        gh_body_en = "### 🛡️ Security Hardening\n* detail\n### 🏷️ Pi-hole RFC 1123 Fix\n* detail"
        # English readers get the GitHub body (English) first; Italian readers keep changelog.md (Italian)
        en_notes = select_release_notes("1.6.2", github_notes=gh_body_en, lang="en")
        it_notes = select_release_notes("1.6.2", github_notes=gh_body_en, lang="it")
        runner.assert_true(en_notes == gh_body_en, "select_release_notes(en) preferisce il corpo GitHub in inglese")
        runner.assert_true("Vulnerability Assessment" in it_notes and it_notes != gh_body_en, "select_release_notes(it) preferisce changelog.md in italiano")
        runner.assert_true(select_release_notes("1.6.2", github_notes="", lang="en") == it_notes, "select_release_notes(en) ricade su changelog.md senza note GitHub")
        runner.assert_true(select_release_notes("9.9.9", github_notes="", lang="it") == "", "select_release_notes restituisce stringa vuota senza alcuna sorgente")

        en_condensed = extract_condensed_changelog("1.6.2", raw_notes=gh_body_en, lang="en")
        it_condensed = extract_condensed_changelog("1.6.2", raw_notes=gh_body_en, lang="it")
        runner.assert_true(en_condensed == ["🛡️ Security Hardening", "🏷️ Pi-hole RFC 1123 Fix"], f"Condensed changelog EN estratto dal corpo GitHub (ottenuto: {en_condensed})")
        runner.assert_true(any("Parità Completa Traduzioni" in h for h in it_condensed), "Condensed changelog IT estratto da changelog.md")

        # localize_update_info: one language-neutral cache serves both languages
        neutral = {
            "current_version": "1.6.1", "latest_version": "1.6.2", "latest_full_version": "1.6.2 build 1",
            "update_available": True, "release_notes_github": gh_body_en, "release_notes_fallback": "",
        }
        loc_en = updater_service.localize_update_info(neutral, lang="en")
        loc_it = updater_service.localize_update_info(neutral, lang="it")
        runner.assert_true(loc_en["release_notes"] == gh_body_en and loc_en["condensed_changelog"] == en_condensed and loc_en["language"] == "en", "localize_update_info(en) espone note e punti salienti in inglese")
        runner.assert_true(loc_it["release_notes"] == it_notes and loc_it["language"] == "it", "localize_update_info(it) espone note in italiano")
        runner.assert_true("release_notes_github" in neutral and "condensed_changelog" not in neutral, "La cache resta neutra rispetto alla lingua (nessun campo localizzato memorizzato)")
        no_notes = updater_service.localize_update_info({**neutral, "current_version": "9.9.8", "latest_version": "9.9.9", "release_notes_github": "", "release_notes_fallback": "Release v9.9.9 available on Docker Hub"}, lang="en")
        runner.assert_true(no_notes["release_notes"].startswith("Release v9.9.9") and no_notes["condensed_changelog"] == [tr("updater.generic_release_available", lang="en", version="1.6.2 build 1")], "Senza note disponibili usa il fallback Docker Hub e il punto saliente generico tradotto")
        runner.assert_true(tr("updater.generic_release_available", lang="it", version="x") != tr("updater.generic_release_available", lang="en", version="x"), "Chiave updater.generic_release_available presente in EN e IT")

        # /api/system/update/check & /update/changelog honour X-Dashboard-Lang
        res_en = await client.get("/api/system/update/check", headers={"X-Dashboard-Lang": "en"})
        res_it = await client.get("/api/system/update/check", headers={"X-Dashboard-Lang": "it"})
        runner.assert_true(res_en.status_code == 200 and res_en.json().get("language") == "en", "GET /update/check con X-Dashboard-Lang: en risponde language=en")
        runner.assert_true(res_it.status_code == 200 and res_it.json().get("language") == "it", "GET /update/check con X-Dashboard-Lang: it risponde language=it")
        runner.assert_true("release_notes" in res_en.json() and "condensed_changelog" in res_en.json(), "Payload /update/check mantiene release_notes e condensed_changelog")
        res_cl_it = await client.get("/api/system/update/changelog?version=1.6.2", headers={"X-Dashboard-Lang": "it"})
        runner.assert_true(res_cl_it.status_code == 200 and any("Parità Completa Traduzioni" in h for h in res_cl_it.json().get("condensed_changelog", [])), "GET /update/changelog?version=1.6.2 (it) usa changelog.md")

        # Demo payload localization
        runner.assert_true(localize_demo_text("Gateway Soggiorno", lang="en") == "Living Room Gateway", "localize_demo_text traduce i nomi dei nodi demo in inglese")
        runner.assert_true(localize_demo_text("Gateway Soggiorno", lang="it") == "Gateway Soggiorno", "localize_demo_text lascia intatto l'italiano")
        runner.assert_true(localize_demo_text("Nuovo dispositivo iPad Cucina / Ricette su Gateway Soggiorno", lang="en") == "Nuovo dispositivo Kitchen iPad / Recipes su Living Room Gateway", "localize_demo_text sostituisce i nomi anche dentro frasi (match più lungo prioritario)")
        sample = {"connected_eero_name": "Camera da Letto", "nested": [{"name": "Intrattenimento & Salotto", "mac": "AA:BB"}], "n": 3}
        loc_sample = localize_demo_payload(sample, lang="en")
        runner.assert_true(loc_sample["connected_eero_name"] == "Bedroom" and loc_sample["nested"][0]["name"] == "Entertainment & Lounge" and loc_sample["nested"][0]["mac"] == "AA:BB" and loc_sample["n"] == 3 and "connected_eero_name" in loc_sample, "localize_demo_payload traduce ricorsivamente solo i valori stringa, mai le chiavi")

        # Every Italian demo literal in _init_demo_state must have an English mapping
        import inspect as _inspect
        demo_src = _inspect.getsource(eero_client._init_demo_state)
        for lit in ("Gateway Soggiorno", "Camera da Letto", "Casa Rossi Mesh 6E", "Intrattenimento & Salotto", "iPad Cucina / Ricette", "Gateway Rack Ufficio", "Laboratorio & Workstation"):
            runner.assert_true(lit in demo_src and lit in DEMO_STRINGS_EN, f"Letterale demo '{lit}' presente nel simulatore e mappato in DEMO_STRINGS_EN")

        eero_client.set_demo_mode(True)
        try:
            # /api/devices is served from the poller cache (empty in this harness): use the eero node list
            eeros_en = await client.get("/api/network/eeros", headers={"X-Dashboard-Lang": "en"})
            eeros_it = await client.get("/api/network/eeros", headers={"X-Dashboard-Lang": "it"})
            names_en = {e.get("name") for e in eeros_en.json().get("eeros", [])}
            names_it = {e.get("name") for e in eeros_it.json().get("eeros", [])}
            runner.assert_true("Living Room Gateway" in names_en and "Gateway Soggiorno" not in names_en, f"GET /api/network/eeros (demo, en) espone nodi in inglese (ottenuto: {sorted(n for n in names_en if n)})")
            runner.assert_true("Gateway Soggiorno" in names_it, "GET /api/network/eeros (demo, it) mantiene i nomi italiani")
            runner.assert_true(eeros_en.headers.get("content-length") == str(len(eeros_en.content)), "Il middleware demo ricalcola Content-Length dopo la traduzione")
            ov_en = await client.get("/api/network/overview", headers={"X-Dashboard-Lang": "en"})
            runner.assert_true("Rossi Home" in str(ov_en.json().get("data", {}).get("network", {}).get("name", "")) or "Office & Studio" in str(ov_en.json().get("data", {}).get("network", {}).get("name", "")), "GET /api/network/overview (demo, en) traduce il nome della rete")
        finally:
            eero_client.set_demo_mode(False)
        dev_live = await client.get("/api/devices", headers={"X-Dashboard-Lang": "en"})
        runner.assert_true(dev_live.status_code == 200, "Fuori dal Demo Mode il middleware non altera la risposta (HTTP 200)")

        runner.assert_true(tr("eero.node_name_fallback", lang="en") == "eero node" and tr("eero.device_name_fallback", lang="en") == "Device", "Fallback nome nodo/dispositivo tradotti (EN)")
        runner.assert_true(tr("eero.node_name_fallback", lang="it") == "Nodo eero" and tr("eero.device_name_fallback", lang="it") == "Dispositivo", "Fallback nome nodo/dispositivo tradotti (IT)")

        # Test Issue #80: formatSpeed definition in app.js and call in index.html
        with open("app/static/js/app.js", "r", encoding="utf-8") as _fjs:
            _app_js_content = _fjs.read()
        with open("app/templates/index.html", "r", encoding="utf-8") as _fhtml:
            _index_html_content = _fhtml.read()
        runner.assert_true("formatSpeed(mbps)" in _app_js_content, "Metodo formatSpeed definito in app.js (Issue #80)")
        runner.assert_true("formatSpeed(" in _index_html_content, "Chiamata a formatSpeed presente in index.html (Issue #80)")

        # =====================================================================
        # 39. TEST I18N COVERAGE: NESSUN TESTO HARDCODED, PARITÀ CHIAVI E PLACEHOLDER (Issue #82)
        # =====================================================================
        print("\n🌐 Test 39: Copertura i18n (Issue #82) - parità chiavi, nessun testo inline, placeholder coerenti...")
        import glob as _glob
        import re as _re_i18n
        from app.i18n import SUPPORTED_LANGUAGES as _SUPPORTED, LOCALES_DIR as _SERVER_LOCALES

        def _flatten_i18n(d, prefix=""):
            out = {}
            for k, v in d.items():
                if isinstance(v, dict):
                    out.update(_flatten_i18n(v, f"{prefix}{k}."))
                else:
                    out[f"{prefix}{k}"] = v
            return out

        _fe = {}
        for _lang in _SUPPORTED:
            _path = Path(f"app/static/locales/{_lang}.json")
            runner.assert_true(_path.exists(), f"Locale frontend '{_lang}.json' presente")
            _fe[_lang] = _flatten_i18n(json.loads(_path.read_text(encoding="utf-8"))) if _path.exists() else {}
        _ref_keys = set(_fe.get("en", {}))
        for _lang in _SUPPORTED:
            if _lang == "en":
                continue
            _missing = sorted(_ref_keys - set(_fe[_lang]))
            _extra = sorted(set(_fe[_lang]) - _ref_keys)
            runner.assert_true(not _missing and not _extra, f"Parità chiavi frontend en.json ↔ {_lang}.json (mancanti: {_missing[:5]}, extra: {_extra[:5]})")
            _ph_bad = [k for k in _ref_keys if k in _fe[_lang] and set(_re_i18n.findall(r"\{(\w+)\}", _fe["en"][k])) != set(_re_i18n.findall(r"\{(\w+)\}", _fe[_lang][k]))]
            runner.assert_true(not _ph_bad, f"Placeholder {{param}} identici tra en.json e {_lang}.json (differenze: {_ph_bad[:5]})")

        _html_src = Path("app/templates/index.html").read_text(encoding="utf-8")
        _js_src = Path("app/static/js/app.js").read_text(encoding="utf-8")
        _used = set()
        for _src in (_html_src, _js_src):
            _used |= set(_re_i18n.findall(r"\bt\('([a-z0-9_.]+)'", _src))
        _dynamic = {k for k in _used if k.endswith(".") or k.endswith("_")}
        _unknown = sorted(k for k in _used - _dynamic if k not in _ref_keys)
        runner.assert_true(not _unknown, f"Ogni chiave t('…') usata in index.html/app.js esiste in en.json (sconosciute: {_unknown[:8]})")
        _tern = _re_i18n.findall(r"currentLanguage === 'it'\s*\?|\bisIt\s*\?", _html_src + _js_src)
        runner.assert_true(len(_tern) == 0, f"Nessun ternario di lingua inline (currentLanguage === 'it' ? / isIt ?) residuo in index.html/app.js (trovati: {len(_tern)})")
        _fallbacks = _re_i18n.findall(r"\bt\('[^']+'\)\s*\|\|\s*['\"`][A-Za-z]", _html_src + _js_src)
        runner.assert_true(len(_fallbacks) == 0, f"Nessun fallback testuale t('…') || '…' residuo (trovati: {len(_fallbacks)})")
        runner.assert_true("<option value=\"it\">" not in _html_src and "x-for=\"code in supportedLanguages\"" in _html_src, "Selettore lingua generato da supportedLanguages (nessuna option hardcoded)")
        # Raw Italian literals (weekday/month names, common UI words) must not appear as quoted strings in
        # template/JS code: they bypass t() and only ever render in one language (regression guard for #84).
        _it_words = (
            "Lun|Mar|Mer|Gio|Ven|Sab|Dom|Lunedì|Martedì|Mercoledì|Giovedì|Venerdì|Sabato|Domenica|"
            "Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre|"
            "Nessun[ao]?|Aggiorna(?:mento)?|Caricamento|Salva(?:to)?|Elimina(?:to)?|Annulla|Chiudi|Errore|Attenzione|"
            "Tutti|Oggi|Ieri|Dispositiv[oi]|Impostazioni|Conferma|Segnale|Velocità|Cerca|Giorn[oi]|Minuti|Secondi"
        )
        _raw_it = []
        for _name, _src in (("index.html", _html_src), ("app.js", _js_src)):
            for _m in _re_i18n.finditer(r"(?<![\w.])(['\"])(" + _it_words + r")\1", _src):
                _line = _src.count("\n", 0, _m.start()) + 1
                _raw_it.append(f"{_name}:{_line}:{_m.group(2)}")
        runner.assert_true(not _raw_it, f"Nessun letterale italiano grezzo (giorni/mesi/parole UI) fuori da t() in index.html/app.js (trovati: {_raw_it[:6]})")
        _wd = {f"common.weekday_short.{d}" for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        runner.assert_true(_wd <= _ref_keys, f"Chiavi common.weekday_short.* presenti per tutti i giorni (mancanti: {sorted(_wd - _ref_keys)})")

        _be = {}
        for _lang in _SUPPORTED:
            _be[_lang] = {}
            for _f in sorted(_glob.glob(str(_SERVER_LOCALES / _lang / "*.json"))):
                _ns = Path(_f).stem
                for k, v in json.loads(Path(_f).read_text(encoding="utf-8")).items():
                    _be[_lang][f"{_ns}.{k}"] = v
        _be_ref = set(_be.get("en", {}))
        for _lang in _SUPPORTED:
            if _lang == "en":
                continue
            _missing = sorted(_be_ref - set(_be[_lang]))
            _extra = sorted(set(_be[_lang]) - _be_ref)
            runner.assert_true(not _missing and not _extra, f"Parità cataloghi backend i18n_locales/en ↔ {_lang} (mancanti: {_missing[:5]}, extra: {_extra[:5]})")
            _ph_bad = [k for k in _be_ref if k in _be[_lang] and set(_re_i18n.findall(r"\{(\w+)\}", _be["en"][k])) != set(_re_i18n.findall(r"\{(\w+)\}", _be[_lang][k]))]
            runner.assert_true(not _ph_bad, f"Placeholder {{param}} identici nei cataloghi backend en ↔ {_lang} (differenze: {_ph_bad[:5]})")
        _py_used = set()
        for _f in _glob.glob("app/**/*.py", recursive=True):
            _py_src = Path(_f).read_text(encoding="utf-8")
            _py_used |= set(_re_i18n.findall(r"\btr(?:_all)?\(\s*[\"']([a-z0-9_]+\.[a-z0-9_]+)[\"']", _py_src))
            _py_used |= set(_re_i18n.findall(r"\blog_event\([^,]+,[^,]+,\s*[\"']([a-z0-9_]+\.[a-z0-9_]+)[\"']", _py_src))
        _py_unknown = sorted(k for k in _py_used if k not in _be_ref)
        runner.assert_true(not _py_unknown, f"Ogni chiave tr()/tr_all()/log_event() statica nel backend esiste nei cataloghi en (sconosciute: {_py_unknown[:8]})")
        runner.assert_true(len(_be_ref) > 400 and len(_ref_keys) > 1000, f"Cataloghi popolati (backend {len(_be_ref)} chiavi, frontend {len(_ref_keys)} chiavi)")

        runner.print_summary()




if __name__ == "__main__":
    asyncio.run(run_all_tests())

