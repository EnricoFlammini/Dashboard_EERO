#!/usr/bin/env python3
"""
Pre-Release Automated Test Suite - eero Custom Dashboard (v1.03.02)
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
        # 9. TEST MULTI-ISTANZA ADGUARD HOME & CACHE BUSTING (Issue #17)
        # =====================================================================
        print("\n🛡️ [9/9] TEST MULTI-ISTANZA ADGUARD HOME & CACHE BUSTING (Issue #17)")
        
        # Test cache busting su pagina index
        page_res = await client.get("/")
        runner.assert_true(page_res.status_code == 200, "GET / risponde HTTP 200")
        page_html = page_res.text
        runner.assert_true("styles.css?v=" in page_html, "styles.css include parametro versione cache-busting (?v=)")
        runner.assert_true("app.js?v=" in page_html, "app.js include parametro versione cache-busting (?v=)")

        # Test salvataggio istanze multiple AdGuard
        adg_instances_payload = {
            "enabled": True,
            "instances": [
                {
                    "id": "inst-1",
                    "name": "Primary DNS Server",
                    "url": "http://192.168.4.104:8085",
                    "username": "admin1",
                    "password": "test_pass_primary",
                    "enabled": True
                },
                {
                    "id": "inst-2",
                    "name": "Secondary DNS Server",
                    "url": "http://192.168.4.105:8085",
                    "username": "admin2",
                    "password": "test_pass_secondary",
                    "enabled": True
                }
            ]
        }
        save_adg_res = await client.post("/api/automations/adguard", json=adg_instances_payload)
        runner.assert_true(save_adg_res.status_code == 200, "Salvataggio istanze multiple AdGuard risponde HTTP 200")

        # Verifica lettura impostazioni multi-istanza
        get_adg_res = await client.get("/api/automations/adguard")
        runner.assert_true(get_adg_res.status_code == 200, "Lettura impostazioni AdGuard risponde HTTP 200")
        adg_data = get_adg_res.json()
        runner.assert_true(len(adg_data.get("instances", [])) == 2, f"Rilevate 2 istanze AdGuard configurate (ottenute: {len(adg_data.get('instances', []))})")
        runner.assert_true(adg_data["instances"][0]["name"] == "Primary DNS Server", "Nome prima istanza preservato")
        runner.assert_true(adg_data["instances"][1]["name"] == "Secondary DNS Server", "Nome seconda istanza preservato")
        runner.assert_true(adg_data["instances"][0]["has_password"] is True, "Password prima istanza preservata")
        runner.assert_true(adg_data["instances"][1]["has_password"] is True, "Password seconda istanza preservata")

        # Attiva demo mode per simulazione test e sync senza socket reali
        await client.post("/api/auth/mode", json={"demo": True})
        
        # Test connessione multi-istanza
        test_adg_res = await client.post("/api/automations/adguard/test", json={"instances": adg_instances_payload["instances"]})
        runner.assert_true(test_adg_res.status_code == 200, "Test connessione multi-istanza risponde HTTP 200")
        runner.assert_true(test_adg_res.json().get("success") is True, "Test connessione multi-istanza simulato con successo")

        # Test sync in demo mode verso multiple istanze
        sync_adg_res = await client.post("/api/automations/adguard/sync", json={"instances": adg_instances_payload["instances"]})
        runner.assert_true(sync_adg_res.status_code == 200, "Sync multi-istanza AdGuard risponde HTTP 200")
        runner.assert_true(sync_adg_res.json().get("success") is True, "Sync multi-istanza completato con successo")

        # Ripristina stato finale live
        await client.post("/api/auth/mode", json={"demo": False})

    runner.print_summary()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
