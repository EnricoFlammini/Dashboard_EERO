import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROJECT_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = PROJECT_DIR / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

class ChromeCDP:
    def __init__(self, port=9222):
        self.port = port
        self.proc = None
        self.ws = None
        self.msg_id = 1
        self.user_data = None

    async def start(self):
        self.user_data = tempfile.mkdtemp(prefix="chrome_cdp_screen_")
        cmd = [
            CHROME_PATH,
            "--headless=new",
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.user_data}",
            "--window-size=1920,1080",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            "about:blank"
        ]
        self.proc = subprocess.Popen(cmd)
        
        # Wait for port to become available
        ws_url = None
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=1) as resp:
                    targets = json.loads(resp.read().decode())
                    if targets:
                        for t in targets:
                            if t.get("type") == "page":
                                ws_url = t.get("webSocketDebuggerUrl")
                                break
                        if not ws_url and targets:
                            ws_url = targets[0].get("webSocketDebuggerUrl")
                        if ws_url:
                            break
            except Exception:
                await asyncio.sleep(0.3)
        
        if not ws_url:
            raise RuntimeError("Impossibile connettersi a Chrome CDP")
        
        self.ws = await websockets.connect(ws_url, max_size=50*1024*1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")
        await self.send("Emulation.setDeviceMetricsOverride", {
            "width": 1920,
            "height": 1080,
            "deviceScaleFactor": 1,
            "mobile": False
        })

    async def send(self, method, params=None):
        mid = self.msg_id
        self.msg_id += 1
        msg = {"id": mid, "method": method}
        if params:
            msg["params"] = params
        await self.ws.send(json.dumps(msg))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == mid:
                return data

    async def evaluate(self, expr):
        res = await self.send("Runtime.evaluate", {
            "expression": expr,
            "awaitPromise": True,
            "returnByValue": True
        })
        return res.get("result", {}).get("result", {}).get("value")

    async def capture_screenshot(self, target_path: Path):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        b64 = res.get("result", {}).get("data")
        if b64:
            target_path.write_bytes(base64.b64decode(b64))
            print(f" [OK] Screenshot salvato: {target_path.name} ({target_path.stat().st_size} bytes)")
        else:
            print(f" [ERR] Cattura fallita per {target_path.name}: {res}")

    async def close(self):
        if self.ws:
            await self.ws.close()
        if self.proc:
            self.proc.terminate()
            self.proc.wait()


async def wait_for_server(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            await asyncio.sleep(0.5)
    return False


async def run():
    print("=" * 60)
    print(" CATTURA SCREENSHOT AUTOMATICA PER README v1.6.0 CON CHROME")
    print("=" * 60)
    
    # 1. Avvio Server Demo su porta 8098
    env = os.environ.copy()
    env["DEMO_MODE"] = "true"
    env["PORT"] = "8098"
    env["DASHBOARD_LANG"] = "it"
    
    server_cmd = [
        str(PROJECT_DIR / ".venv" / "Scripts" / "python.exe"),
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8098",
        "--log-level", "warning"
    ]
    print("-> Avvio server uvicorn in modalità Demo su http://127.0.0.1:8098 ...")
    server_proc = subprocess.Popen(server_cmd, cwd=str(PROJECT_DIR), env=env)
    
    try:
        ready = await wait_for_server("http://127.0.0.1:8098/api/health")
        if not ready:
            raise RuntimeError("Timeout in attesa del server uvicorn")
        print("-> Server attivo e pronto!")

        # 2. Avvio Chrome CDP
        cdp = ChromeCDP(port=9222)
        await cdp.start()
        print("-> Chrome headless connesso!")

        try:
            # Naviga all'applicazione
            print("-> Navigazione su http://127.0.0.1:8098 ...")
            await cdp.send("Page.navigate", {"url": "http://127.0.0.1:8098/"})
            
            # Attendi caricamento e inizializzazione Alpine
            for _ in range(30):
                is_ready = await cdp.evaluate("""
                    Boolean(window.Alpine && document.body && Alpine.$data(document.body) && !Alpine.$data(document.body).authLoading && !Alpine.$data(document.body).loading)
                """)
                if is_ready:
                    break
                await asyncio.sleep(0.5)
            
            # Imposta utente amministratore per sbloccare tutte le viste della dashboard
            print("-> Sblocco privilegi Amministratore e caricamento dati demo...")
            await cdp.evaluate("""
                (async () => {
                    const app = Alpine.$data(document.body);
                    app.currentUser = {
                        id: 1,
                        username: 'admin',
                        display_name: 'Administrator',
                        role: 'admin',
                        is_admin: true,
                        permissions: ['*']
                    };
                    app.isAuthenticated = true;
                    app.isDemoMode = true;
                    await app.refreshAllData();
                    await app.setTab('overview');
                })()
            """)
            await asyncio.sleep(2.5)
            
            # Assicurati lingua italiana
            await cdp.evaluate("Alpine.$data(document.body).switchLanguage('it')")
            await asyncio.sleep(1.0)

            # --- SCREENSHOT 1: DASHBOARD OVERVIEW ---
            print("-> 1/7 Cattura Dashboard Overview (IT)...")
            await cdp.evaluate("Alpine.$data(document.body).setTab('overview')")
            await asyncio.sleep(2.5)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "dashboard_overview.png")
            (SCREENSHOTS_DIR / "dashboard_overview_it.png").write_bytes((SCREENSHOTS_DIR / "dashboard_overview.png").read_bytes())

            # --- SCREENSHOT 2: DEVICES TABLE (Con nuova colonna traffico v1.6.0) ---
            print("-> 2/7 Cattura Gestione Dispositivi...")
            await cdp.evaluate("Alpine.$data(document.body).setTab('devices')")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "devices_management.png")

            # --- SCREENSHOT 3: DEVICE DETAIL MODAL (Con prenotazione IP DHCP e statistiche) ---
            print("-> 3/7 Cattura Modale Dettagli Dispositivo...")
            await cdp.evaluate("""
                (() => {
                    const app = Alpine.$data(document.body);
                    const dev = (app.filteredDevices && app.filteredDevices.length > 0) ? app.filteredDevices[0] : null;
                    if (dev) app.openDeviceModal(dev);
                })()
            """)
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "device_dhcp_modal.png")
            # Chiudi modale dispositivo
            await cdp.evaluate("Alpine.$data(document.body).showDeviceModal = false")
            await asyncio.sleep(1.0)

            # --- SCREENSHOT 4: SPEEDTEST & BUFFERBLOAT ---
            print("-> 4/7 Cattura Speed Test & Bufferbloat...")
            await cdp.evaluate("Alpine.$data(document.body).setTab('speedtest')")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "speedtest_analytics.png")

            # --- SCREENSHOT 5: AUTOMAZIONI & HOMELAB (MQTT + Prometheus) ---
            print("-> 5/7 Cattura Automazioni & HomeLab...")
            await cdp.evaluate("Alpine.$data(document.body).setTab('settings-controls')")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "automations_dns_docker.png")

            # --- SCREENSHOT 6: ANALYTICS & QUALITA SPETTRO ---
            print("-> 6/7 Cattura Qualità & Spettro Wi-Fi...")
            await cdp.evaluate("Alpine.$data(document.body).setTab('quality-analytics')")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "speedtest_signal_quality.png")

            # --- SCREENSHOT 7: MANUALE UTENTE INTERATTIVO (Modulo 4 / v1.6.0) ---
            print("-> 7/7 Cattura Manuale Tecnico 2 Colonne...")
            await cdp.evaluate("Alpine.$data(document.body).openContextHelp('intro')")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "manual_reader.png")
            # Chiudi modale guida
            await cdp.evaluate("Alpine.$data(document.body).showHelpModal = false")
            await asyncio.sleep(0.8)

            # --- VERSIONE EN DI DASHBOARD OVERVIEW ---
            print("-> Generazione Dashboard Overview (EN)...")
            await cdp.evaluate("Alpine.$data(document.body).switchLanguage('en')")
            await cdp.evaluate("Alpine.$data(document.body).setTab('overview')")
            await asyncio.sleep(2.0)
            await cdp.capture_screenshot(SCREENSHOTS_DIR / "dashboard_overview_en.png")

            print("\n[SUCCESS] TUTTI GLI SCREENSHOT SONO STATI CATTURATI CON SUCCESSO!")

        finally:
            await cdp.close()

    finally:
        server_proc.terminate()
        server_proc.wait()
        print("-> Server di test arrestato.")

if __name__ == "__main__":
    asyncio.run(run())
