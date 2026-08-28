# eero Custom Dashboard & Mesh Management Suite 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![i18n](https://img.shields.io/badge/i18n-IT%20%7C%20EN-purple.svg)](#)

> **Language / Lingua:** [🇬🇧 English](#-english) | [🇮🇹 Italiano](#-italiano)

<p align="center">
  <img src="docs/screenshots/dashboard_overview.png" alt="eero Dashboard Overview" width="100%" style="border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);" />
</p>

---

<a name="english"></a>
# 🇬🇧 English Documentation

Self-hosted, containerized web dashboard and management suite for **Amazon eero** mesh Wi-Fi networks. Features authentic certified hardware telemetry, real-time traffic monitoring, DHCP static IP reservation with collision detection, port forwarding rules, speed testing history, dynamic guest Wi-Fi QR generator, one-click gaming focus mode, and interactive documentation.

---

## 📸 Screenshots Showcase

<div align="center">

| Dashboard & Mesh Topology | Speed Test & Analytics |
| :---: | :---: |
| <img src="docs/screenshots/dashboard_overview.png" width="480" /> | <img src="docs/screenshots/speedtest_analytics.png" width="480" /> |

| Device Details & Static IP (DHCP) |
| :---: |
| <img src="docs/screenshots/device_dhcp_modal.png" width="550" /> |

</div>

---

## 🌟 Key Features

* **📊 Mesh Topology & Health Score:** Live overview with Network Health Score (1-100), WAN public IP, gateway status, DNS servers, ISP information, and individual eero nodes (Gateway & Beacons) with backhaul type (`Ethernet (Wired)` vs `Wireless Mesh`).
* **🖥️ Certified Hardware Telemetry & Frequency Bands:** Full client table with explicit frequency band badges (**2.4 GHz, 5 GHz, 6 GHz, Wired Ethernet**), wireless channels (`CH 11`, `CH 36`, etc.), eero Cloud User Profiles integration (`👤 [Profile Name]`), connected mesh node, RSSI signal strength (dBm), negotiated physical PHY rate, and **Static IP vs Dynamic DHCP indicators**.
* **⚙️ DHCP Reservations & Port Forwarding:** Dedicated device modals with custom nicknames (synced to eero cloud), categories, local documentation notes, favorite flags (⭐), **DHCP static IP reservations with reassignment support**, and integrated **Port Forwarding rule management** (WAN port -> LAN port, TCP/UDP).
* **🌍 Real-Time Multi-Language (i18n):** Native bilingual interface (**English 🇬🇧 / Italian 🇮🇹**) with automatic browser language detection and instant live switcher.
* **⚡ Speed Test & Performance Analytics:** Manual and scheduled automated speed tests (e.g. every 12 hours) with historical charts (Download, Upload, Ping/Latency) and aggregate statistics.
* **📱 Dynamic Guest Wi-Fi QR Code:** Scannable Wi-Fi QR Code generator (`WIFI:S:...;T:WPA;P:...;;`) with one-click enable/disable and secure password generation.
* **🎮 One-Click Gaming Focus Mode:** Low-latency automation that temporarily pauses non-essential streaming/IoT devices to eliminate jitter during competitive gaming or video calls.
* **🔔 Telegram Bot & Webhook Alerts:** Instant notifications on new unknown device connections (Intruder Alert) or mesh node disconnections.
* **📖 Interactive In-App User Manual:** Fully searchable embedded documentation and release notes changelog viewer.
* **🛡️ Zero-Latency RAM Cache:** Asynchronous in-memory background poller eliminating eero API rate-limiting.
* **✨ Demo Mode Simulator:** Test and explore all dashboard features without real credentials.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.12 (`python:3.12-slim-bookworm`), FastAPI >= 0.115, Uvicorn >= 0.32, Pydantic v2, `asyncio`.
* **HTTP Client:** `httpx` (async client for eero REST API 2.2).
* **Storage:** Async SQLite with `aiosqlite` (WAL mode).
* **Frontend:** Semantic HTML5, Vanilla CSS / Tailwind CSS, Alpine.js (v3.14+), Chart.js (v4.4+).
* **Containerization:** Docker & Docker Compose (Compose V2).

---

## 🚀 Quick Start with Docker Compose

### 1. Clone or download the repository
```bash
git clone https://github.com/EnricoFlammini/Dashboard_EERO.git
cd Dashboard_EERO
```

### 2. Configure Environment Variables (Optional)
```bash
cp .env.example .env
```

### 3. Launch the Container
```bash
docker compose up -d --build
```

Access the dashboard in your browser:
👉 **`http://localhost:8085`** (or your server's IP, e.g. `http://192.168.1.100:8085`).

---

## 🔑 Authentication & Login Methods

1. **2FA OTP Login (Recommended):**
   - Open the web interface at `http://localhost:8085`.
   - Enter your email address or phone number associated with your eero account (e.g. `+1234567890` or `user@example.com`).
   - Click **"Send OTP Code"** and type the 6-digit verification code received via SMS/Email.
   - The session token is securely saved to `./data/session.json` and automatically restored across container restarts.
2. **Demo Mode:**
   - Click **"✨ Try Demo Mode"** on the login screen or set `DEMO_MODE=true` in `.env` to explore with simulated realistic mesh data.

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST_PORT` | `8085` | Port exposed on host machine |
| `DATA_DIR` | `/app/data` | Directory for SQLite DB and session storage |
| `POLL_INTERVAL` | `30` | eero API sampling interval (seconds) |
| `HISTORY_RETENTION_DAYS` | `30` | Number of days to retain historical records |
| `SPEEDTEST_INTERVAL_HOURS` | `12` | Scheduled speed test interval in hours (0 to disable) |
| `DEMO_MODE` | `false` | Enable simulated mesh network environment |
| `TELEGRAM_BOT_TOKEN` | *(optional)* | Telegram Bot Token for alerts & daily digest |
| `TELEGRAM_CHAT_ID` | *(optional)* | Destination Telegram Chat ID |
| `WEBHOOK_URL` | *(optional)* | HTTP POST endpoint for JSON event forwarding |

---

## 💾 Data Persistence & Backup

All stateful data is isolated in the `./data` volume:
* **`metrics.db`**: SQLite database containing device metadata, speed tests, and alerts.
* **`session.json`**: Official eero cloud 2FA session token.

```bash
# Backup command
tar -czvf eero_dashboard_backup_$(date +%F).tar.gz ./data
```

---

## 🔔 Webhooks & REST API Reference

When `WEBHOOK_URL` is set in `.env` (or configured via the in-app settings UI), the dashboard issues an asynchronous `HTTP POST` request with a JSON payload whenever critical network events occur.

### Webhook Event Types & JSON Payloads

#### 1. `new_device` (Intruder Alert / New Device Connected)
Triggered immediately when a device connects to the mesh network for the first time:
```json
{
  "event": "new_device",
  "timestamp": "2026-08-28T08:25:00Z",
  "source": "eero_custom_dashboard",
  "data": {
    "hostname": "Living-Room-AppleTV",
    "ip": "192.168.4.52",
    "mac": "AA:BB:CC:DD:EE:FF",
    "wireless": true,
    "wireless_band": "5GHz",
    "connected_eero_name": "Living Room Gateway"
  }
}
```

#### 2. `node_offline` (Mesh Node Disconnected)
Triggered when an eero Beacon or Gateway drops offline:
```json
{
  "event": "node_offline",
  "timestamp": "2026-08-28T08:26:00Z",
  "source": "eero_custom_dashboard",
  "data": {
    "location": "Kitchen Beacon",
    "model": "eero Pro 6E",
    "status": "offline",
    "ip": "192.168.4.2"
  }
}
```

#### 3. `daily_digest` (Daily Network Health Summary)
Sent daily with WAN performance, latency averages, and active device counts:
```json
{
  "event": "daily_digest",
  "timestamp": "2026-08-28T09:00:00Z",
  "source": "eero_custom_dashboard",
  "data": {
    "avg_download_mbps": 842.5,
    "avg_upload_mbps": 110.2,
    "avg_ping_ms": 11.4,
    "total_devices_seen": 34,
    "nodes_online": 3
  }
}
```

---

## 🛡️ AdGuard Home & Pi-hole DNS Integration

You can easily synchronize your eero mesh client names, IP assignments, and MAC addresses into **AdGuard Home** or **Pi-hole** so your DNS query logs display readable hostnames instead of raw IP addresses.

### 1. `/etc/hosts` / `dnsmasq` Plain-Text Export
* **Endpoint:** `GET http://<dashboard-ip>:8085/api/devices/export/hosts`
* **Query Parameters:**
  * `connected_only=true` *(default: true)* — Only export active devices.
  * `domain_suffix=lan` *(optional)* — Appends a local domain suffix (e.g. `.lan` or `.home`).

```bash
# Pull hosts file from dashboard
curl -s "http://localhost:8085/api/devices/export/hosts?domain_suffix=lan"
```
**Output Example:**
```text
# ========================================================================
# eero Mesh Network - Hosts Export for AdGuard Home / Pi-hole / dnsmasq
# ========================================================================
192.168.4.20    eagle.lan                        # eagle (AA:BB:CC:11:22:33)
192.168.4.31    mantra-kitchen.lan               # Mantra (AA:BB:CC:44:55:66)
192.168.4.52    living-room-appletv.lan          # Apple TV (AA:BB:CC:77:88:99)
```

### 2. AdGuard Home REST API Format (`/control/clients`)
* **Endpoint:** `GET http://<dashboard-ip>:8085/api/devices/export/adguard`
* Returns a structured JSON list ready for AdGuard Home client provisioning.

### 3. Automated AdGuard Home Sync Script
A ready-to-use Python sync script is provided in [`scripts/adguard_sync.py`](scripts/adguard_sync.py).

```bash
# Run once or add to crontab (e.g. every 10 minutes)
python scripts/adguard_sync.py \
  --eero http://localhost:8085 \
  --adguard http://192.168.4.2:80 \
  --user admin \
  --pass MySecretPassword
```

---

## 🙏 Acknowledgements & Prior Art

This project stands on the shoulders of the open-source networking and home automation community:
* **[`343max/eero-client`](https://github.com/343max/eero-client):** The foundational pioneer library for reverse-engineering and exploring the private eero cloud REST API.
* **[Home Assistant Community](https://github.com/home-assistant/core):** For valuable historical insights into eero authentication flows, device tracker models, and API stability.
* **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) & [Pi-hole](https://github.com/pi-hole/pi-hole):** For inspiring clean local DNS resolution and client discovery patterns.

---

<a name="italiano"></a>
# 🇮🇹 Documentazione in Italiano

Dashboard web e suite di gestione containerizzata per reti mesh Wi-Fi **Amazon eero**. Offre telemetria autentica hardware, monitoraggio in tempo reale, prenotazioni IP statici DHCP con risoluzione automatica dei conflitti, gestione regole di port forwarding, storico misurazioni speed test, generazione dinamica di QR Code per rete ospiti, modalità gaming low-latency e manuale integrato.

---

## 📸 Galleria Screenshot

<div align="center">

| Panoramica Dashboard & Topologia Mesh | Diagnostica Speed Test & Storico |
| :---: | :---: |
| <img src="docs/screenshots/dashboard_overview.png" width="480" /> | <img src="docs/screenshots/speedtest_analytics.png" width="480" /> |

| Dettaglio Dispositivo & Assegnazione IP Statico DHCP |
| :---: |
| <img src="docs/screenshots/device_dhcp_modal.png" width="550" /> |

</div>

---

## 🌟 Caratteristiche Principali

* **📊 Dashboard Mesh & Health Score:** Panoramica con Network Health Score (1-100), IP pubblico, DNS, ISP, Speed Test Gateway e stato dei singoli nodi eero (Gateway e Beacon) con tipo di backhaul (`Ethernet (Cablato)` vs `Wireless Mesh (5/6 GHz)`).
* **🖥️ Telemetria Hardware & Frequenze Wi-Fi:** Tabella completa con badge cromatici per frequenza (**2.4 GHz, 5 GHz, 6 GHz, Cablato Ethernet**), canali Wi-Fi (`CH 11`, `CH 36`, ecc.), integrazione profilo utente eero (`👤 [Nome Profilo]`), nodo di attestazione, potenza segnale RSSI (dBm), velocità di link PHY e **indicatori visivi IP Statico vs DHCP**.
* **⚙️ Prenotazioni DHCP & Port Forwarding:** Scheda dettaglio dispositivo con sincronizzazione nomi sul cloud eero, categorie, note locali, preferiti (⭐), **prenotazione IP statico con rilevamento intelligente dei conflitti** e **gestione regole di apertura porte (Port Forwarding)**.
* **🌍 Supporto Multilingua (i18n):** Interfaccia bilingue (**Italiano 🇮🇹 / Inglese 🇬🇧**) con rilevamento automatico della lingua del browser e selettore istantaneo nella barra superiore.
* **⚡ Speed Test & Diagnostica Prestazioni:** Esecuzione test manuali e schedulati (es. ogni 12h) con storico completo di Download, Upload, Ping (Latenza) e calcolo delle medie e dei picchi massimi.
* **📱 Smart Guest Wi-Fi con QR Code Dinamico:** Generatore automatico di QR Code standard Wi-Fi (`WIFI:S:...;T:WPA;P:...;;`) da scansionare al volo con smartphone, con toggle rapido di attivazione e generatore di password sicure.
* **🎮 Gaming & Focus Mode (One-Click Low Latency):** Pulsante a un clic che mette automaticamente in pausa il traffico di background di apparati secondari e IoT preconfigurati per azzerare il jitter e la latenza durante sessioni di gaming o videoconferenze.
* **🔔 Notifiche Telegram & Webhook:** Avvisi in tempo reale per la connessione di nuovi dispositivi sconosciuti (Intruder Alert) e anomalie/nodi mesh offline.
* **📖 Manuale Utente Integrato & Changelog:** Documentazione completa navigabile con ricerca full-text, tooltip contestuali e visualizzatore Changelog interattivo in-app.
* **🛡️ Zero-Latency In-Memory Poller:** Cache in memoria RAM per rispondere all'interfaccia con latenza zero senza sovraccaricare le API eero (protezione da rate limiting).
* **✨ Modalità Demo:** Simulatore integrato per testare l'applicazione senza inserire credenziali reali.

---

## 🛠️ Stack Tecnologico

* **Backend:** Python 3.12 (`python:3.12-slim-bookworm`), FastAPI >= 0.115, Uvicorn >= 0.32, Pydantic v2, `asyncio`.
* **Client HTTP:** `httpx` (client asincrono per REST API eero 2.2).
* **Database & Storico:** SQLite asincrono con `aiosqlite` (WAL mode).
* **Frontend:** HTML5 semantico, Vanilla CSS / Tailwind CSS, Alpine.js (v3.14+), Chart.js (v4.4+).
* **Containerizzazione:** Docker e Docker Compose (Compose V2).

---

## 🚀 Avvio Rapido con Docker Compose

### 1. Clona il repository o posizionati nella cartella
```bash
git clone https://github.com/EnricoFlammini/Dashboard_EERO.git
cd Dashboard_EERO
```

### 2. Configura le Variabili d'Ambiente (Opzionale)
```bash
cp .env.example .env
```

### 3. Avvia il Container
```bash
docker compose up -d --build
```

Accedi alla dashboard dal browser:
👉 **`http://localhost:8085`** (o l'IP del tuo server Linux/NAS, es. `http://192.168.1.100:8085`).

---

## 🔑 Creazione Account eero & Modalità di Accesso

1. **Accesso Guidato 2FA OTP (Consigliato):**
   - Apri la schermata iniziale all'indirizzo `http://localhost:8085`.
   - Inserisci l'email o il numero di telefono associato al tuo account eero (es. `+393401234567` o `mario.rossi@email.com`).
   - Clicca su **"Invia Codice OTP"** ed inserisci il codice a 6 cifre ricevuto via SMS o Email.
   - Il token verificato viene salvato in `./data/session.json` e ripristinato automaticamente ad ogni riavvio del container.
2. **Modalità Demo:**
   - Clicca su **"✨ Prova Subito con la Modalità Demo"** nella schermata di login o imposta `DEMO_MODE=true` nel file `.env`.

---

## ⚙️ Variabili d'Ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `HOST_PORT` | `8085` | Porta esposta sulla macchina host |
| `DATA_DIR` | `/app/data` | Directory interna per i file SQLite e sessione |
| `POLL_INTERVAL` | `30` | Intervallo di campionamento dalle API eero (secondi) |
| `HISTORY_RETENTION_DAYS` | `30` | Giorni di conservazione dello storico prima della pulizia automatica |
| `SPEEDTEST_INTERVAL_HOURS` | `12` | Intervallo di esecuzione dello Speed Test automatico (ore, 0 per disattivare) |
| `DEMO_MODE` | `false` | Se impostato su `true`, abilita la simulazione completa di una rete eero |
| `TELEGRAM_BOT_TOKEN` | *(opzionale)* | Token del Bot Telegram per invio allarmi e digest |
| `TELEGRAM_CHAT_ID` | *(opzionale)* | Chat ID Telegram destinatario |
| `WEBHOOK_URL` | *(opzionale)* | Endpoint HTTP POST per inoltro eventi in formato JSON |

---

## 💾 Persistenza dei Dati & Backup

Tutti i dati risiedono nella cartella montata `./data`:
* **`metrics.db`**: Database SQLite con storico prestazioni, metadati e allarmi.
* **`session.json`**: Token di autenticazione eero 2FA.

```bash
# Esempio di backup rapido
tar -czvf eero_dashboard_backup_$(date +%F).tar.gz ./data
```

---

## 🔔 Riferimento Webhook & Integrazione DNS (AdGuard Home / Pi-hole)

Quando viene impostata la variabile `WEBHOOK_URL` in `.env` (o tramite il pannello Impostazioni nell'interfaccia web), la dashboard invia automaticamente una richiesta `HTTP POST` con un payload JSON all'accadere di eventi critici sulla rete.

### Tipologie di Eventi Webhook & Payload JSON

* **`new_device` (Rilevamento Nuovo Dispositivo):** Inviato istantaneamente quando un dispositivo si collega per la prima volta. Contiene `hostname`, `ip`, `mac`, frequenza Wi-Fi e nodo eero di connessione.
* **`node_offline` (Nodo Mesh Disconnesso):** Inviato quando un Beacon o il Gateway perde la connessione.
* **`daily_digest` (Report Giornaliero):** Inviato ogni 24 ore con medie di download, upload, latenza (ping) e conteggio dispositivi.

### Sincronizzazione Nomi Dispositivi con AdGuard Home & Pi-hole

1. **Export Formato File `/etc/hosts` / `dnsmasq`:**  
   `GET http://<dashboard-ip>:8085/api/devices/export/hosts?domain_suffix=lan`  
   Restituisce l'elenco dei dispositivi attivi nel formato compatibile con file hosts e regole DNS personalizzate.
2. **Export Formato JSON AdGuard Home (`/control/clients`):**  
   `GET http://<dashboard-ip>:8085/api/devices/export/adguard`  
   Restituisce un array JSON strutturato per il provisioning diretto dei client in AdGuard.
3. **Script di Sincronizzazione Python Automatico:**  
   È disponibile lo script pronto all'uso [`scripts/adguard_sync.py`](scripts/adguard_sync.py) eseguibile manualmente o via cron:
   ```bash
   python scripts/adguard_sync.py --eero http://localhost:8085 --adguard http://192.168.4.2:80 --user admin --pass MiaPassword
   ```

---

## 🙏 Fonti & Riconoscimenti (Acknowledgements)

Questo progetto si basa e si ispira al lavoro pionieristico della community open-source e dell'home automation:
* **[`343max/eero-client`](https://github.com/343max/eero-client):** La libreria di riferimento originaria per il reverse-engineering e l'esplorazione delle REST API private del cloud eero.
* **[Home Assistant Community](https://github.com/home-assistant/core):** Per gli studi approfonditi sui flussi di autenticazione 2FA e la stabilità delle chiamate di telemetria.
* **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) & [Pi-hole](https://github.com/pi-hole/pi-hole):** Per gli standard e l'ispirazione nella gestione della risoluzione DNS locale e mappatura host.

---

## 📄 Licenza / License

Distribuito sotto licenza **MIT**. Consulta il file [LICENSE](LICENSE) per i dettagli completi.  
Copyright (c) 2026 Enrico Flammini.
