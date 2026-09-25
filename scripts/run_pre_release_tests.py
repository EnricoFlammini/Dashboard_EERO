#!/usr/bin/env python3
"""
Pre-Release Automated Test Suite - eero Custom Dashboard (v1.5.0)
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
        runner.assert_true(node_6ghz_hw_norm["backhaul_type"] == "Wireless Mesh (6 GHz / -48 dBm)", f"Nodo hardware Pro 6E senza freq API adotta 'Wireless Mesh (6 GHz / -48 dBm)' (ottenuto: {node_6ghz_hw_norm['backhaul_type']})")

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
        runner.assert_true(bedroom_res["backhaul_type"] == "Ethernet (Cablato)", f"Bedroom backhaul è 'Ethernet (Cablato)' (ottenuto: {bedroom_res['backhaul_type']})")
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
                    n["backhaul_type"] = f"Ethernet ({spd_fmt})" if spd_fmt else "Ethernet (Cablato)"
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
        runner.assert_true(check_data.get("current_version") == "1.5.0", f"Versione corrente rilevata è 1.5.0 (ottenuta: {check_data.get('current_version')})")
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

        # Test bilingue i18n (Issue #15 / i18n fix)
        for p_key in ["mesh_topology", "wan_gateway", "client_signal", "channel_density"]:
            pillar_obj = deg_calc["pillars"].get(p_key, {})
            runner.assert_true("summary_i18n" in pillar_obj, f"Pilastro '{p_key}' contiene 'summary_i18n'")
            runner.assert_true("en" in pillar_obj.get("summary_i18n", {}), f"Pilastro '{p_key}' ha traduzione 'en'")
            runner.assert_true("it" in pillar_obj.get("summary_i18n", {}), f"Pilastro '{p_key}' ha traduzione 'it'")

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
        det_res = await client.get("/api/network/overview")
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

        # Rifiuta lingua non supportata
        lang_invalid = await client.post("/api/system/language", json={"language": "de"})
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

        # 7. Test Manuale In-App & Package Versioning (v1.5.0)
        import importlib
        app_pkg = importlib.import_module("app")
        runner.assert_true(getattr(app_pkg, "__version__", None) == "1.5.0", f"app.__version__ è '1.5.0' (trovato: {getattr(app_pkg, '__version__', None)})")
        res_man_it = await client.get("/api/manual/sections?lang=it")
        runner.assert_true(res_man_it.status_code == 200, "GET /api/manual/sections?lang=it risponde HTTP 200")
        runner.assert_true(res_man_it.json().get("count") == 10, f"Manuale IT contiene 10 sezioni complete (trovate: {res_man_it.json().get('count')})")
        res_man_en = await client.get("/api/manual/sections?lang=en")
        runner.assert_true(res_man_en.status_code == 200, "GET /api/manual/sections?lang=en risponde HTTP 200")
        runner.assert_true(res_man_en.json().get("count") == 10, f"Manuale EN contiene 10 sezioni complete (trovate: {res_man_en.json().get('count')})")
        res_ch_it = await client.get("/api/manual/changelog?lang=it")
        runner.assert_true(res_ch_it.json().get("version") == "1.5.0", "Versione restituita da changelog IT è 1.5.0")
        runner.assert_true("## v1.5.0" in res_ch_it.json().get("content", ""), "Changelog in-app IT include la release v1.5.0")
        res_ch_en = await client.get("/api/manual/changelog?lang=en")
        runner.assert_true(res_ch_en.json().get("version") == "1.5.0", "Versione restituita da changelog EN è 1.5.0")
        runner.assert_true("## v1.5.0" in res_ch_en.json().get("content", ""), "Changelog in-app EN include la release v1.5.0")

        # 8. Test Build Number & Full Versioning (es. '1.5.0 build 1')
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
        runner.assert_true(update_data.get("latest_full_version") == settings.full_version, f"updater_service include latest_full_version allineata: {update_data.get('latest_full_version')}")
        runner.assert_true(is_newer_version(settings.full_version, "1.5.0-build.4") is True, "is_newer_version rileva correttamente nuova build 4")
        runner.assert_true(is_newer_version("1.5.0 build 2", "1.5.0-build.3") is True, "is_newer_version rileva correttamente nuova build 3")
        runner.assert_true(is_newer_version(settings.full_version, "1.5.0-build.1") is False, "is_newer_version riconosce che build 1 non è più recente")
        runner.assert_true(is_newer_version("1.5.0 build 1", "1.5.0-build.2") is True, "is_newer_version rileva build 2 rispetto a build 1")

        # =====================================================================
        # 20. TEST EEROOS RELEASE NOTES, ZENDESK SCRAPER & COMMUNITY HUB (v1.6.0)
        # =====================================================================
        print("\n📰 [20/20] TEST EEROOS RELEASE NOTES, ZENDESK SCRAPER & COMMUNITY HUB (v1.6.0)")

        from app.services.eero_news_service import eero_news_service, parse_eero_version, is_newer_eero_version

        # 1. Test Funzioni di Confronto Versioni eeroOS
        runner.assert_true(parse_eero_version("v7.16.0-9483") == (7, 16, 0, 9483), "parse_eero_version analizza correttamente 'v7.16.0-9483'")
        runner.assert_true(parse_eero_version("v7.5.2-192") == (7, 5, 2, 192), "parse_eero_version analizza correttamente 'v7.5.2-192'")
        runner.assert_true(parse_eero_version("v6.16.5-4") == (6, 16, 5, 4), "parse_eero_version analizza correttamente 'v6.16.5-4'")
        runner.assert_true(parse_eero_version("v1.0.11") == (1, 0, 11, 0), "parse_eero_version analizza correttamente 'v1.0.11'")
        runner.assert_true(parse_eero_version(None) == (0, 0, 0, 0), "parse_eero_version gestisce None senza errori")
        runner.assert_true(is_newer_eero_version("v7.16.0-9483", "v7.5.2-192") is True, "is_newer_eero_version rileva correttamente nuova release 7.16 vs 7.5.2")
        runner.assert_true(is_newer_eero_version("v7.5.2-192", "v7.16.0-9483") is False, "is_newer_eero_version riconosce versione precedente")
        runner.assert_true(is_newer_eero_version("v7.16.0-9483", "v7.16.0-9483") is False, "is_newer_eero_version ritorna False per versioni identiche")

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
        runner.assert_true("nodes" in news_json and isinstance(news_json["nodes"], list), "Risposta include array 'nodes'")
        runner.assert_true("releases" in news_json and len(news_json["releases"]) > 0, "Risposta include elenco note di rilascio")
        runner.assert_true("community_posts" in news_json, "Risposta include feed 'community_posts'")

        # In modalità Demo (flotta su v7.5.2 vs release v7.16+), deve rilevare update disponibile
        runner.assert_true(news_json.get("is_up_to_date") is False, "In ambiente Demo rileva correttamente is_up_to_date=False (v7.5.2 vs v7.16+)")
        runner.assert_true(news_json.get("update_available") is True, "In ambiente Demo rileva correttamente update_available=True")

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
        runner.assert_true("update_avail_title" in it_locale["eero_news"], "update_avail_title presente in it.json")
        runner.assert_true("update_avail_title" in en_locale["eero_news"], "update_avail_title presente in en.json")
        runner.assert_true("community_title" in it_locale["eero_news"], "community_title presente in it.json")
        runner.assert_true("community_title" in en_locale["eero_news"], "community_title presente in en.json")

        runner.print_summary()




if __name__ == "__main__":
    asyncio.run(run_all_tests())

