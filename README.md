# eero Custom Dashboard, Management Suite & Bandwidth Historian 🚀

Applicazione web self-hosted, modulare e containerizzata con Docker per il monitoraggio avanzato del traffico di rete (WAN e per singolo host), controller di rete mesh, storico delle prestazioni (Speed Test), automazioni e **manuale utente integrato interattivo** per sistemi mesh Amazon eero.

---

## 🌟 Caratteristiche Principali

* **📊 Dashboard Mesh & WAN in Tempo Reale:** Panoramica con Network Health Score (1-100), IP pubblico, DNS, ISP, stato dei singoli nodi eero (Gateway e Beacon) con uptime, temperatura interna e tipo di backhaul (Ethernet 1/2.5Gbps vs Wireless Mesh).
* **📈 Bandwidth Historian & Top Consumer:** Grafici temporali interattivi con Chart.js (Download vs Upload) con intervallo selezionabile a 24h, 7gg, 30gg o personalizzato, e classifica a barre orizzontali dei dispositivi a maggior consumo (Bandwidth Hogs).
* **🖥️ Gestione Avanzata Dispositivi:** Tabella completa con filtri per frequenza (2.4 / 5 / 6 GHz / Cablato), nodo eero collegato, stato e potenza del segnale RSSI (dBm). Scheda di dettaglio con personalizzazione di nomi, icone, note locali, prenotazione IP statico DHCP, regole di Port Forwarding e toggle per mettere in pausa la connessione internet con sincronizzazione API verso eero.
* **⚡ Speed Test & Diagnostica:** Esecuzione test manuali e schedulati a intervalli regolari (es. ogni 12h) con storico completo di Download, Upload, Ping (Latenza) e calcolo delle medie e dei picchi massimi.
* **📱 Smart Guest Wi-Fi con QR Code Dinamico:** Generatore automatico di QR Code standard Wi-Fi (`WIFI:S:...;T:WPA;P:...;;`) da scansionare al volo con smartphone, con pulsante per attivare/disattivare la rete ospiti e generatore di password sicure.
* **🎮 Gaming & Focus Mode (One-Click Low Latency):** Pulsante a un clic che mette automaticamente in pausa il traffico di background di apparati secondari e IoT preconfigurati per azzerare il jitter e la latenza durante sessioni di gaming o videoconferenze.
* **🌙 Modalità Notte Automatica:** Scheduler orario per spegnere automaticamente i LED frontali dei nodi mesh durante la notte (es. 23:00 - 07:00) e riaccenderli al mattino.
* **🔔 Notifiche Telegram & Webhook:** Avvisi in tempo reale per la connessione di nuovi dispositivi sconosciuti (Intruder Alert), anomalie/nodi mesh offline e invio automatico del Daily Digest serale.
* **📖 Manuale Utente Integrato:** Sezione di documentazione navigabile con ricerca istantanea full-text e tooltip informativi con icona "?" posizionati in tutta l'interfaccia per aprire guide contestuali.
* **🛡️ Zero-Latency In-Memory Poller:** Cache in memoria RAM per rispondere all'interfaccia con latenza zero senza sovraccaricare le API eero (protezione da rate limiting).
* **✨ Demo Mode Simulator:** Possibilità di testare e validare tutte le funzioni dell'applicazione senza inserire credenziali reali.

---

## 🛠️ Stack Tecnologico

* **Backend:** Python 3.12 (`python:3.12-slim-bookworm`), FastAPI >= 0.115, Uvicorn >= 0.32, Pydantic v2, `asyncio`.
* **Client HTTP:** `httpx` (client asincrono per REST API eero 2.2).
* **Database & Storico:** SQLite asincrono con `aiosqlite` (WAL mode).
* **Frontend:** HTML5 semantico, Tailwind CSS (v3.4+ via CDN), Alpine.js (v3.14+), Chart.js (v4.4+).
* **Utility:** `qrcode[pil]` per la generazione grafica dei QR Code Wi-Fi.
* **Containerizzazione:** Docker e Docker Compose (Compose V2).

---

## 📁 Struttura del Progetto

```
.
├── Dockerfile                  # Immagine Docker ottimizzata su Python 3.12 slim
├── docker-compose.yml          # Configurazione del servizio Docker Compose
├── requirements.txt            # Dipendenze Python bloccate
├── .env.example                # Template delle variabili d'ambiente
├── README.md                   # Documentazione completa
├── data/                       # Volume persistente (montato in /app/data)
│   ├── metrics.db              # Database SQLite (tabelle WAN, dispositivi, speedtest)
│   └── session.json            # Token di autenticazione eero 2FA
└── app/
    ├── __init__.py
    ├── config.py               # Gestione impostazioni tramite Pydantic Settings
    ├── main.py                 # Inizializzazione FastAPI e ciclo di vita (lifespan)
    ├── services/
    │   ├── db.py               # Service SQLite async con retention policy
    │   ├── eero_client.py      # Client API eero 2.2 + simulatore Demo Mode
    │   ├── poller.py           # Background poller, cache RAM e automazioni
    │   ├── speedtest_service.py # Esecutore Speed Test
    │   ├── qrcode_gen.py       # Generatore QR Code Wi-Fi
    │   └── notifications.py    # Notificatore Telegram & Webhook
    ├── routers/
    │   ├── auth.py             # Login 2FA OTP, status, logout
    │   ├── network.py          # WAN, mesh topology, controlli LED, guest Wi-Fi
    │   ├── devices.py          # Client table, metadati, port forwarding, pausa
    │   ├── metrics.py          # Realtime throughput, serie temporali WAN, top hogs
    │   ├── speedtest.py        # Trigger speedtest, storico e statistiche
    │   ├── automations.py      # Gaming mode, night mode, notifiche, digest
    │   └── manual.py           # Capitoli e ricerca per il manuale integrato
    ├── static/
    │   ├── css/styles.css      # Sistema di design dark glassmorphism
    │   └── js/app.js           # Reattività Alpine.js e grafici Chart.js
    └── templates/
        └── index.html          # Template Single Page Application (SPA)
```

---

## 🚀 Avvio Rapido con Docker Compose

### 1. Clona o posizionati nella cartella del progetto
```bash
cd /percorso/del/progetto
```

### 2. Configura le Variabili d'Ambiente (Opzionale)
Copia il file `.env.example` in `.env`:
```bash
cp .env.example .env
```

### 3. Avvia il Container
```bash
docker compose up -d --build
```

L'applicazione sarà immediatamente accessibile all'indirizzo:
👉 **`http://localhost:8085`** (o l'IP del tuo server Linux, es. `http://192.168.1.100:8085`).

---

## 🔑 Primo Accesso e Autenticazione (2FA OTP)

1. Apri il browser all'indirizzo `http://<IP_SERVER>:8085`.
2. Nella schermata di login, inserisci l'**Email** o il **Numero di Telefono** (completo di prefisso internazionale, es. `+393401234567`) associato al tuo account eero.
3. Clicca su **"Invia Codice OTP"**.
4. Riceverai un codice a 6 cifre via SMS o Email da parte di eero. Inseriscilo nel campo di verifica e conferma.
5. Il token di sessione verrà salvato automaticamente in `./data/session.json`. Ad ogni riavvio del container la sessione rimarrà attiva senza dover reinserire il codice.

> 💡 **Nota:** Se vuoi provare l'applicazione prima di collegare il tuo account, clicca sul pulsante **"Prova Subito con la Modalità Demo"** o imposta `DEMO_MODE=true` nel file `.env`.

---

## ⚙️ Variabili d'Ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `HOST_PORT` | `8085` | Porta esposta sulla macchina host |
| `DATA_DIR` | `/app/data` | Directory interna per i file SQLite e sessione |
| `POLL_INTERVAL` | `30` | Intervallo di campionamento dalle API eero (secondi) |
| `HISTORY_RETENTION_DAYS` | `30` | Giorni di conservazione dello storico prima della pulizia automatica |
| `SPEEDTEST_INTERVAL_HOURS` | `12` | Intervallo di esecuzione dello Speed Test automatico (ore, 0 per disattivare) |
| `DEMO_MODE` | `false` | Se impostato su `true`, abilita la simulazione completa di una rete eero mesh |
| `TELEGRAM_BOT_TOKEN` | *(vuoto)* | Token del Bot Telegram per invio allarmi e digest |
| `TELEGRAM_CHAT_ID` | *(vuoto)* | Chat ID Telegram destinatario |
| `WEBHOOK_URL` | *(vuoto)* | Endpoint HTTP POST per inoltro eventi in formato JSON |

---

## 💾 Persistenza dei Dati & Backup

Tutti i dati e lo stato dell'applicazione risiedono nella cartella montata `./data`:
* **`metrics.db`**: Database SQLite contenente le metriche storiche WAN, il campionamento per dispositivo, i risultati dei test di velocità, le annotazioni/icone personalizzate e il registro degli allarmi.
* **`session.json`**: Token di autenticazione eero 2FA.

### Procedura di Backup:
```bash
# Esempio di backup rapido
tar -czvf eero_dashboard_backup_$(date +%F).tar.gz ./data
```

---

## 🔒 Sicurezza & Accesso Remoto

L'applicazione è progettata per il self-hosting privato in rete locale (LAN).
Per accedere in modo sicuro dall'esterno:
* Connettiti tramite la tua **VPN casalinga** (es. WireGuard, Tailscale o OpenVPN).
* Oppure posiziona l'applicazione dietro a un **Reverse Proxy** (es. Nginx Proxy Manager, Traefik o Caddy) con certificato SSL Let's Encrypt e autenticazione aggiuntiva.

---

## 📄 Licenza
Progetto distribuito per uso personale e self-hosted. Sviluppato per integrarsi con l'ecosistema Amazon eero.
