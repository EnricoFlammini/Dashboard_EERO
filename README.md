# eero Custom Dashboard & Mesh Management Suite 🚀

Applicazione web self-hosted, modulare e containerizzata con Docker per il controllo dell'infrastruttura mesh, gestione avanzata dei dispositivi con dati fisici certificati, storico delle prestazioni (Speed Test), automazioni e **manuale utente integrato interattivo** per sistemi mesh Amazon eero.

---

## 🌟 Caratteristiche Principali

* **📊 Dashboard Mesh & Health Score:** Panoramica con Network Health Score (1-100), IP pubblico, DNS, ISP, Speed Test Gateway e stato dei singoli nodi eero (Gateway e Beacon) con uptime e tipo di backhaul (Ethernet 1/2.5Gbps vs Wireless Mesh).
* **🖥️ Gestione Avanzata Dispositivi con Dati Fisici Certificati:** Tabella completa con filtri per frequenza (2.4 / 5 / 6 GHz / Cablato), canale Wi-Fi, nodo eero collegato, potenza del segnale RSSI (dBm), velocità di link PHY negoziata, **indicatori visivi di IP Statico vs DHCP** e filtro dedicato. Scheda di dettaglio a schede con personalizzazione nomi (sincronizzati con Cloud eero), categorie, note locali, preferiti (⭐), flag per Gaming Mode, toggle pausa internet, **prenotazioni IP statico DHCP con rilevamento conflitti** e **regole di Port Forwarding**.
* **⚡ Speed Test & Diagnostica Prestazioni:** Esecuzione test manuali e schedulati a intervalli regolari (es. ogni 12h) con storico completo di Download, Upload, Ping (Latenza) e calcolo delle medie e dei picchi massimi.
* **📱 Smart Guest Wi-Fi con QR Code Dinamico:** Generatore automatico di QR Code standard Wi-Fi (`WIFI:S:...;T:WPA;P:...;;`) da scansionare al volo con smartphone, con pulsante per attivare/disattivare la rete ospiti e generatore di password sicure.
* **🎮 Gaming & Focus Mode (One-Click Low Latency):** Pulsante a un clic che mette automaticamente in pausa il traffico di background di apparati secondari e IoT preconfigurati per azzerare il jitter e la latenza durante sessioni di gaming o videoconferenze.
* **🔔 Notifiche Telegram & Webhook:** Avvisi in tempo reale per la connessione di nuovi dispositivi sconosciuti (Intruder Alert) e anomalie/nodi mesh offline.
* **📖 Manuale Utente Integrato & Changelog:** Sezione di documentazione navigabile con ricerca istantanea full-text, tooltip contestuali e visualizzatore Changelog interattivo in-app (v1.00.08).
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

## 🔑 Creazione Account eero & Modalità di Accesso

L'applicazione si interfaccia in modo sicuro con il cloud ufficiale **Amazon eero**. Di seguito sono riportate le istruzioni complete per la configurazione dell'account e l'accesso alla dashboard.

---

### 1. Prerequisiti & Creazione Account eero
Se non possiedi ancora un account eero o stai configurando una nuova rete:
1. **Scarica l'App Ufficiale eero:**
   * [eero per iOS su App Store](https://apps.apple.com/app/eero-home-wifi-system/id969248441)
   * [eero per Android su Google Play Store](https://play.google.com/store/apps/details?id=com.e2ro.view)
2. **Registrazione Account:**
   * Apri l'app sul tuo smartphone e seleziona **"Crea un account"** (oppure accedi con il tuo account **Amazon**).
   * Associa un **indirizzo email valido** e un **numero di cellulare con prefisso internazionale** (es. `+39 340 1234567`). Questi recapiti saranno utilizzati per ricevere i codici di sicurezza a doppio fattore (2FA OTP).
3. **Associazione della Rete Mesh:**
   * Segui la procedura guidata nell'app per connettere il nodo principale (**Gateway eero**) al tuo modem/ONT e configurare il nome della rete Wi-Fi (SSID).

---

### 2. Metodi di Accesso alla Dashboard

La dashboard supporta due modalità di accesso a seconda delle tue esigenze:

#### 🔹 Metodo A: Login Grafico Guidato 2FA OTP (Consigliato)
1. Avvia il container Docker ed apri il browser all'indirizzo **`http://<IP_SERVER>:8085`** (es. `http://localhost:8085`).
2. Nella finestra di autenticazione, inserisci l'**Email** o il **Numero di Telefono** associato al tuo account eero (es. `+393401234567` o `mario.rossi@email.com`).
3. Clicca su **"Invia Codice OTP"**.
4. Riceverai un **codice a 6 cifre via SMS o Email** direttamente da eero.
5. Inserisci il codice a 6 cifre nel campo di verifica e clicca su **"Conferma ed Accedi"**.
6. **Persistenza Automatica:** Il token di autenticazione verificato viene salvato in `./data/session.json`. Ai successivi riavvii del server o del container Docker, l'applicazione ripristinerà la sessione in automatico senza richiedere nuovamente l'OTP.

#### 🔹 Metodo B: Configurazione Headless con Token Permanente (`.env`)
Se desideri avviare la dashboard in modalità completamente automatizzata (es. in ambienti CI/CD o server remoti senza interfaccia di login iniziale):
1. Estrai il tuo token utente e ID di rete (ad esempio da una sessione attiva o tramite script).
2. Nel file `.env` configura le seguenti variabili:
   ```env
   EERO_USER_TOKEN=il_tuo_session_token_segreto
   EERO_NETWORK_ID=il_tuo_id_rete_mesh
   ```
3. Avvia il container con `docker compose up -d`. L'applicazione leggerà direttamente il token dall'ambiente e salterà la schermata di login.

---

### 3. Gestione Sessione, Logout e Rinnovo
* **Logout / Cambio Account:**
  * Puoi disconnettere la sessione in qualsiasi momento cliccando sull'icona **"Disconnetti"** in alto a destra nella barra di navigazione.
  * In alternativa, puoi eliminare manualmente il file `./data/session.json` e riavviare il container.
* **Cosa fare se la sessione scade:**
  * I token eero hanno una validità prolungata (mesi/anni). Qualora eero revocasse la sessione (es. cambio password dell'account Amazon), l'app mostrerà automaticamente la schermata di login per richiedere un nuovo codice OTP a 6 cifre.

---

### 4. Modalità Dimostrativa (Demo Mode)
Se desideri esplorare l'interfaccia, i grafici e tutte le funzionalità prima di collegare il tuo account:
* Clicca su **"✨ Prova Subito con la Modalità Demo"** nella schermata iniziale di login.
* Oppure imposta `DEMO_MODE=true` nel file `.env` per forzare l'avvio con una rete simulata realistica (3 nodi eero Pro 6E, client connessi e speed test simulato).

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
