import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manual", tags=["User Manual"])

MANUAL_SECTIONS_IT: List[Dict[str, Any]] = [
    {
        "id": "intro",
        "title": "1. Introduzione & Architettura",
        "icon": "book-open",
        "summary": "Panoramica dell'architettura self-hosted, sicurezza 2FA e persistenza dei dati.",
        "content": """
### Cos'è eero Custom Dashboard & Management Suite?
Questa applicazione web è un sistema completo e self-hosted per il monitoraggio, il controllo e l'analisi avanzata della tua infrastruttura mesh **Amazon eero**.

#### Caratteristiche Architetturali:
1. **Self-Hosted & Riservatezza:** L'applicazione viene eseguita all'interno di un container Docker isolato sul tuo server locale o NAS (HomeLab). Non trasmette dati a terzi ed è accessibile via LAN o VPN privata.
2. **Autenticazione Sicura 2FA OTP:** La connessione iniziale con il cloud eero avviene tramite il meccanismo ufficiale a doppio fattore (One-Time Password via SMS o Email).
3. **Persistenza e Isolamento:** Il token di sessione (`session.json`) e il database SQLite (`metrics.db`) risiedono esclusivamente nel volume persistente `./data:/app/data`.
4. **Zero-Latency In-Memory Poller:** Un worker asincrono in background interroga periodicamente la rete e mantiene una cache in memoria RAM, garantendo navigazione istantanea senza rallentamenti o sovraccarico di richieste (rate-limiting).
        """
    },
    {
        "id": "auth-flow",
        "title": "2. Autenticazione 2FA & Gestione Sessione",
        "icon": "key",
        "summary": "Procedura di primo accesso OTP e mantenimento della sessione.",
        "content": """
### Come autenticare la Dashboard con il tuo account eero

1. **Richiesta del Codice OTP:**
   - Inserisci nella schermata di login l'email o il numero di telefono associato al tuo account eero (es. `+393401234567` o `tuonome@email.com`).
   - Clicca su **"Invia Codice OTP"**.
2. **Verifica del Codice:**
   - Riceverai un codice numerico a 6 cifre via SMS o Email da parte di eero.
   - Digita il codice nel campo e conferma.
3. **Salvataggio Sessione:**
   - Il token verificato viene salvato in `/app/data/session.json`. Ad ogni riavvio del container Docker, la sessione verrà ripristinata automaticamente senza dover reinserire l'OTP.
4. **Modalità Demo:**
   - Se desideri esplorare l'applicazione senza inserire credenziali, puoi attivare la modalità dimostrativa con il pulsante dedicato o impostando `DEMO_MODE=true` nel file `.env`.
        """
    },
    {
        "id": "dashboard-mesh",
        "title": "3. Dashboard & Topologia Mesh",
        "icon": "network",
        "summary": "Interpretazione dello Health Score, stato dei nodi e controlli rapidi.",
        "content": """
### Comprensione della Dashboard Generale

* **Network Health Score (1-100):** Un indicatore sintetico dello stato di salute della rete, calcolato analizzando la disponibilità dei nodi mesh, la presenza del gateway e la qualità del segnale RSSI dei client.
* **Topologia Nodi eero:**
  - *Gateway Node:* Il nodo principale connesso direttamente al modem/ONT dell'operatore.
  - *Beacon / Mesh Extender:* Nodi secondari che estendono la copertura.
  - *Tipo di Backhaul:* Visualizza se il collegamento tra i nodi avviene via cavo Ethernet (1 Gbps o 2.5 Gbps) oppure tramite canale Wireless dedicato (5GHz/6GHz).
* **Azioni Rapide sui Nodi:**
  - **Riavvio Rete:** Invia un comando di riavvio controllato a tutta l'infrastruttura.
  - **Riavvio Singolo Nodo:** Riavvia unicamente il nodo selezionato senza interrompere il resto della casa.
        """
    },
    {
        "id": "telemetry-api",
        "title": "4. Telemetria & Dati Fisici Certificati eero",
        "icon": "cpu",
        "summary": "Lettura autentica dei parametri di rete direttamente dall'infrastruttura eero.",
        "content": """
### Telemetria e Dati Ufficiali al 100%

La dashboard adotta un approccio di trasparenza e integrità totale sui dati di rete:
1. **Dati Fisici Certificati:**
   - Visualizzazione dei parametri reali inviati dai nodi mesh eero: **Frequenza e Banda Wi-Fi (2.4 GHz, 5 GHz, 6 GHz o Cablato Ethernet)**, **Canale Wi-Fi (es. CH 36, CH 11)**, **Potenza Segnale RSSI (dBm)** e **Velocità di Link Fisico PHY negoziata (es. 780.0 / 866.7 MBit/s)**.
2. **Speed Test Gateway Ufficiale:**
   - La velocità della connessione WAN visualizzata nei dettagli di rete è quella misurata direttamente dal nodo Gateway eero verso i server di test dell'infrastruttura (es. 907 Mbps Down / 193 Mbps Up).
3. **Nessun Dato Simulato o Fittizio:**
   - L'applicazione esclude intenzionalmente qualsiasi stima artificiale o contatore fittizio, visualizzando unicamente i valori effettivi restituiti dall'API eero.
        """
    },
    {
        "id": "device-management",
        "title": "5. Gestione Dispositivi, IP Statici & Porte",
        "icon": "devices",
        "summary": "Personalizzazione metadati, prenotazioni DHCP, Port Forwarding e pausa internet.",
        "content": """
### Controllo Avanzato dei Client di Rete

* **Ricerca e Filtri:**
  - Cerca per Nome, Indirizzo IP o MAC Address.
  - Filtra per frequenza di connessione (**2.4 GHz, 5 GHz, 6 GHz, Cablato Ethernet**), nodo eero a cui sono agganciati o stato Online/Offline.
  - Visualizzazione immediata della potenza segnale in dBm (RSSI) e velocità di link PHY.
* **Scheda Dettaglio Dispositivo:**
  - **Nome e Icona Personalizzata:** Assegna un'icona specifica (Server, PC, Smartphone, Console, Domotica, Telecamera, ecc.) salvata nel database SQLite locale.
  - **Note & Documentazione:** Campo note libero per salvare credenziali locali, ubicazione, garanzie o porte di servizio.
  - **Prenotazione DHCP (IP Statico):** Assegna un indirizzo IP permanente a un dispositivo basandoti sul suo indirizzo MAC con controllo automatico dei conflitti e supporto alla riassegnazione.
  - **Port Forwarding Integrato:** Aggiungi e rimuovi regole di apertura porte (Porta Esterna WAN -> Porta Interna LAN, Protocolli TCP/UDP).
  - **Pausa Connessione:** Interruttore con 1 clic per bloccare o consentire l'accesso a Internet del singolo dispositivo (es. parental control o isolamento).
        """
    },
    {
        "id": "speedtest",
        "title": "6. Speed Test & Diagnostica Prestazioni",
        "icon": "gauge",
        "summary": "Esecuzione test di velocità, storico delle misurazioni e analisi della latenza.",
        "content": """
### Diagnostica di Velocità

* **Test Manuale:** Clicca sul pulsante **"Avvia Speed Test"** per lanciare una misurazione in tempo reale di Download, Upload, Latenza (Ping) e Jitter.
* **Test Automatici Pianificati:** Il sistema è configurabile per eseguire automaticamente test a intervalli regolari (es. ogni 12 ore) per monitorare la costanza della linea FTTH/VDSL.
* **Grafico Storico & Statistiche:**
  - Grafico dell'andamento di velocità e stabilità della linea nel corso dei giorni.
  - Calcolo automatico di velocità media, picco massimo e latenza minima.
        """
    },
    {
        "id": "automations",
        "title": "7. Automazioni, QR Ospiti, AdGuard Home, Telegram & Notifiche",
        "icon": "zap",
        "summary": "Smart Guest Wi-Fi con QR, integrazione AdGuard Home, allarmi Telegram/Webhook con toggle e report digest.",
        "content": """
### Funzionalità Avanzate e Centro Automazioni

La scheda **Controlli & QR Ospiti** organizza le automazioni della tua rete in 4 comodi quadranti:

1. **Smart Guest Wi-Fi con QR Code Dinamico (In alto a sinistra):**
   - Genera all'istante un QR Code ad alta risoluzione pronto per essere inquadrato da ospiti e smartphone.
   - Toggle per abilitare/disabilitare la rete ospiti con un clic.
   - Generatore integrato di password sicure e aggiornamento credenziali senza accedere all'app mobile.
2. **Integrazione Nativa AdGuard Home (In alto a destra):**
   - **Sincronizzazione Nomi Dispositivi:** Associa i nickname personalizzati e gli indirizzi IP/MAC dei client eero direttamente nella lista dei client persistenti di AdGuard Home (`/control/clients`).
   - **Auto-Sync Continuo:** Il poller di background aggiorna automaticamente AdGuard Home all'accesso di ogni nuovo dispositivo o a intervalli regolari.
   - **Pulsante "Sincronizza Ora":** Forza l'allineamento istantaneo di tutta la tabella host verso AdGuard Home.
   - **Esportazione Standard:** Endpoint `/api/devices/export/hosts` (standard `/etc/hosts`) e `/api/devices/export/adguard` (JSON provisioning).
3. **Notifiche Telegram & Webhook (In basso a sinistra):**
   - **Toggle di Abilitazione Dedicato:** Attiva o disattiva l'invio delle notifiche Telegram con un semplice clic senza eliminare le chiavi salvate.
   - **Nuovo Dispositivo Connesso:** Alert istantaneo quando un apparato mai visto prima si connette alla rete.
   - **Nodo Mesh Offline:** Notifica immediata se un ripetitore eero perde la connessione.
   - **Pulsante "Invia Test":** Verifica il corretto recapito dei messaggi verso il bot Telegram e l'URL Webhook.
4. **Report Digest Giornaliero (In basso a destra):**
   - Invia automaticamente alle ore 21:00 un riepilogo dettagliato con: stato di salute della rete, ISP, nodi mesh online, client connessi suddivisi per frequenza (**6 GHz, 5 GHz, 2.4 GHz, Cablati**) e velocità Speed Test Gateway.
   - Pulsante **"Genera & Invia Digest Ora"** per richiedere l'inoltro immediato del report.
5. **Gaming & Focus Mode (Bassa Latenza):**
   - Accessibile direttamente dalla barra superiore: sospende temporaneamente il traffico dei dispositivi secondari (Smart TV, download di backup) per azzerare la latenza e il jitter a favore delle postazioni da gioco competitive.
        """
    },
    {
        "id": "troubleshooting",
        "title": "8. Risoluzione Problemi & Domande Frequenti (FAQ)",
        "icon": "wrench",
        "summary": "FAQ su telemetria autentica, gestione sessione, AdGuard Home, backup e manutenzione.",
        "content": """
### Domande Frequenti & Troubleshooting

* **Quali dati sui dispositivi provengono direttamente dall'infrastruttura eero?**
  - La dashboard interroga l'infrastruttura eero leggendo: lo stato di connessione (Online/Offline/Pausa), l'indirizzo IP locale, il MAC Address, il nodo mesh a cui sono associati (Gateway o Beacon), la banda radio Wi-Fi (**2.4 GHz, 5 GHz, 6 GHz o Ethernet Cablato**), il canale wireless (**CH**), il livello del segnale in **dBm** e la velocità di link fisico negoziata (**PHY Link Rate**).
* **Come configurare l'integrazione con AdGuard Home?**
  - Nel tab *Automazioni & Controlli*, inserisci l'URL della tua istanza (es. `http://192.168.4.100:8085` o semplicemente `192.168.4.100:8085`), il tuo username e la password. Clicca su **Test Connessione** per verificare il collegamento e poi su **Salva Impostazioni AdGuard**. La password viene salvata in modo sicuro nel database SQLite locale e non viene mai esposta in chiaro.
* **Cosa fare se la sessione scade?**
  - Se ricevi un errore di autorizzazione, clicca sul pulsante **Disconnetti** nella barra laterale o nella schermata di login e riesegui la procedura di ricezione del codice OTP a 6 cifre.
* **Come effettuare il backup delle configurazioni e metadati locali?**
  - Tutti i dati personalizzati (nomi custom, icone, note, impostazioni notifiche e AdGuard) sono contenuti nel file `./data/metrics.db`. Per fare un backup completo, è sufficiente copiare la cartella `./data` sul tuo computer o archivio cloud.
* **Protezione da Rate Limiting:**
  - L'applicazione interroga il cloud eero a intervalli definiti dal poller (default 10s-30s) e risponde a tutte le richieste dell'interfaccia direttamente dalla memoria RAM del server, azzerando il rischio di blocco da parte dei server eero.
        """
    }
]

MANUAL_SECTIONS_EN: List[Dict[str, Any]] = [
    {
        "id": "intro",
        "title": "1. Introduction & Architecture",
        "icon": "book-open",
        "summary": "Overview of the self-hosted architecture, 2FA security, and data persistence.",
        "content": """
### What is eero Custom Dashboard & Management Suite?
This web application is a full-featured, self-hosted management and monitoring platform for your **Amazon eero** mesh Wi-Fi network.

#### Architectural Features:
1. **Self-Hosted & Private:** Runs inside an isolated Docker container on your local server or NAS (HomeLab). Multi-Arch official Docker Hub image for `linux/amd64` and `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Official 2FA OTP Authentication:** Initial connection to the eero cloud utilizes the official two-factor authentication (One-Time Password via SMS or Email).
3. **Persistence & Isolation:** User session token (`session.json`) and SQLite database (`metrics.db`) reside exclusively in the persistent `./data:/app/data` volume.
4. **Zero-Latency In-Memory Poller:** An asynchronous background worker periodically polls the network and maintains an in-memory cache, providing instant UI navigation with zero rate-limiting risk.
        """
    },
    {
        "id": "auth-flow",
        "title": "2. 2FA Authentication & Session Management",
        "icon": "key",
        "summary": "Step-by-step OTP login procedure and session lifecycle.",
        "content": """
### Authenticating the Dashboard with your eero Account

1. **Requesting the OTP Code:**
   - In the login screen, enter the phone number or email address associated with your eero account (e.g., `+1234567890` or `user@example.com`).
   - Click **"Send OTP Code"**.
2. **Verifying the Code:**
   - You will receive a 6-digit verification code from eero via SMS or Email.
   - Enter the code into the verification input and confirm.
3. **Session Persistence:**
   - The verified authentication token is saved to `/app/data/session.json`. When the Docker container restarts, your session is automatically restored without prompting for another OTP.
4. **Demo Mode:**
   - To explore the interface without entering real credentials, activate Demo Mode using the button on the login screen or by setting `DEMO_MODE=true` in `.env`.
        """
    },
    {
        "id": "dashboard-mesh",
        "title": "3. Dashboard & Mesh Topology",
        "icon": "network",
        "summary": "Network Health Score, node status cards, and one-click actions.",
        "content": """
### Understanding the Overview Dashboard

* **Network Health Score (1-100):** A comprehensive real-time score calculated from mesh node availability, gateway status, and client RSSI signal quality.
* **eero Mesh Nodes Topology:**
  - *Gateway Node:* The primary node connected directly to your modem/ONT.
  - *Beacon / Mesh Extenders:* Secondary nodes extending wireless coverage.
  - *Backhaul Type:* Displays whether inter-node links use high-speed Ethernet (1 Gbps / 2.5 Gbps) or dedicated wireless mesh backhaul (5 GHz / 6 GHz).
* **Quick Node Actions:**
  - **Reboot Network:** Dispatches a controlled reboot command across the entire mesh infrastructure.
  - **Reboot Single Node:** Reboots only the selected node without disrupting the rest of the household.
        """
    },
    {
        "id": "devices-table",
        "title": "4. Connected Devices & Frequency Analysis",
        "icon": "devices",
        "summary": "Live device table, Wi-Fi band badges, eero cloud profile integration, and multi-filters.",
        "content": """
### Real-Time Device Inventory

* **Wi-Fi Band & Channel Indicators:** Explicit frequency badges (**6 GHz, 5 GHz, 2.4 GHz, Wired Ethernet**) and active wireless channels (**CH 36, CH 11**, etc.).
* **eero Cloud User Profiles:** Displays the assigned family member profile for each client directly from the eero cloud.
* **Advanced Multi-Criteria Filtering:** Filter by Band, Profile, Node, or IP Assignment type (Static vs DHCP).
        """
    },
    {
        "id": "device-details",
        "title": "5. Device Metadata, Static IP & Port Forwarding",
        "icon": "adjustments",
        "summary": "Custom names, categories, local notes, DHCP reservations, and port forwarding.",
        "content": """
### Device Management & Rules

* **Device Detail Modal:**
  - **Custom Name & Category:** Assign categories (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Other) saved to the local SQLite database.
  - **Local Notes & Documentation:** Free-form notes for tracking device location, service ports, or internal credentials.
  - **DHCP Reservation (Static IP):** Bind a permanent IP address to a client with automated conflict checking and reassignment support.
  - **Integrated Port Forwarding:** Create and delete port forwarding rules (External WAN Port -> Internal LAN Port, TCP/UDP protocols).
        """
    },
    {
        "id": "speedtest",
        "title": "6. Speed Test & Performance Diagnostics",
        "icon": "gauge",
        "summary": "On-demand speed testing, historical performance tracking, and latency analytics.",
        "content": """
### Performance & Bandwidth Diagnostics

* **Manual Speed Test:** Click **"Start Speedtest"** to trigger a real-time measurement of Download, Upload, Ping/Latency, and Jitter.
* **Automated Scheduled Testing:** The system can be scheduled to run automated background tests (e.g., every 12 hours) to track line consistency over time.
* **Historical Charts & Statistics:**
  - Visual time-series graph of speeds and latency over days and weeks.
  - Aggregate statistics including average download/upload, maximum peak speeds, and average ping.
        """
    },
    {
        "id": "automations",
        "title": "7. Automations, Guest QR, AdGuard Home, Telegram & Notifications",
        "icon": "zap",
        "summary": "Smart Guest Wi-Fi with QR, native AdGuard Home sync, Telegram/Webhook alerts with toggle, and Daily Digest.",
        "content": """
### Advanced Features & Automations Hub

The **Automations & Controls** tab organizes your network tools into a clean 2x2 grid:

1. **Smart Guest Wi-Fi with Dynamic QR Code (Top-Left):**
   - Instantly renders a printable, scannable QR Code for guests to connect without typing credentials.
   - One-click toggle to enable or disable the guest network at any time.
   - Built-in secure password generator and credentials updater.
2. **Native AdGuard Home DNS & Client Sync (Top-Right):**
   - **Client Nickname Synchronization:** Push eero custom device nicknames, IP leases, and MAC addresses directly into AdGuard Home persistent client registry (`/control/clients`).
   - **Continuous Background Auto-Sync:** Automatically registers newly discovered devices into AdGuard Home.
   - **One-Click "Sync Now":** Instantly reconciles all network clients against AdGuard Home.
   - **Standard Export Endpoints:** `/api/devices/export/hosts` (/etc/hosts text) and `/api/devices/export/adguard` (JSON provisioning).
3. **Telegram Bot & Webhook Notifications (Bottom-Left):**
   - **Dedicated Activation Toggle:** Enable or disable Telegram notifications with one click while safely preserving your Bot Token and Chat ID.
   - **New Device Alert:** Receive an instant alert when an unknown MAC address connects to your mesh.
   - **Mesh Node Offline:** Immediate notification if any eero node loses connectivity.
   - **"Send Test" Button:** Instantly tests message delivery to your Telegram bot and Webhook URL.
4. **Daily Digest Report (Bottom-Right):**
   - Automated 21:00 report containing: Network Health Score, ISP, online mesh nodes, active clients breakdown by frequency band (**6 GHz, 5 GHz, 2.4 GHz, Ethernet**), Gateway Speed Test and Ping latency.
   - **"Generate & Send Digest Now"** button for immediate on-demand dispatch.
5. **One-Click Gaming / Focus Mode (Low Latency):**
   - Located in the top header: pauses tagged background streaming/downloading devices with a single click to eliminate latency and jitter for competitive gaming setups.
        """
    },
    {
        "id": "troubleshooting",
        "title": "8. Troubleshooting & Frequently Asked Questions (FAQ)",
        "icon": "wrench",
        "summary": "Frequently asked questions regarding telemetry, session handling, AdGuard sync, backups, and maintenance.",
        "content": """
### Troubleshooting & FAQ

* **Which client metrics come directly from eero hardware?**
  - The dashboard reads client connection state (Online/Offline/Paused), local IP address, MAC Address, connected mesh node (Gateway or Beacon), Wi-Fi frequency band (**2.4 GHz, 5 GHz, 6 GHz, or Wired Ethernet**), wireless channel (**CH**), RSSI signal strength in **dBm**, and negotiated physical rate (**PHY Link Rate**).
* **How do I configure the AdGuard Home integration?**
  - Under the *Automations & Controls* tab, enter your instance URL (e.g., `http://192.168.4.100:8085` or `192.168.4.100:8085`), username, and password. Click **Test Connection** and then **Save AdGuard Settings**. Credentials are encrypted and stored safely in the local SQLite database.
* **What should I do if my session expires?**
  - If you encounter authorization errors, click the **Logout** button or re-authenticate from the login modal with a fresh 6-digit OTP code.
* **How do I back up local configurations and custom metadata?**
  - All custom device names, categories, notes, notification settings, and AdGuard settings are stored in `./data/metrics.db`. To create a complete backup, copy the `./data` directory to your computer or backup storage.
* **Rate Limiting Protection:**
  - The system polls eero cloud at controlled intervals (default 10s-30s) and serves all web client queries directly from RAM, completely eliminating the risk of cloud API blocks.
        """
    }
]


@router.get("/sections")
async def get_manual_sections(lang: Optional[str] = Query("it")):
    """Restituisce tutti i capitoli del manuale utente nella lingua richiesta (it/en)."""
    sections = MANUAL_SECTIONS_EN if lang and lang.lower().startswith("en") else MANUAL_SECTIONS_IT
    return {
        "status": "success",
        "count": len(sections),
        "language": "en" if lang and lang.lower().startswith("en") else "it",
        "sections": sections
    }


@router.get("/sections/{section_id}")
async def get_manual_section(section_id: str, lang: Optional[str] = Query("it")):
    """Restituisce una specifica sezione del manuale (utilizzata anche per i tooltip contestuali)."""
    sections = MANUAL_SECTIONS_EN if lang and lang.lower().startswith("en") else MANUAL_SECTIONS_IT
    section = next((s for s in sections if s["id"] == section_id), None)
    if not section:
        return {"status": "error", "message": "Section not found."}
    return {"status": "success", "language": "en" if lang and lang.lower().startswith("en") else "it", "section": section}


@router.get("/changelog")
async def get_changelog():
    """Restituisce il contenuto del file changelog.md per il visualizzatore in-app."""
    from pathlib import Path
    from app.config import settings

    possible_paths = [
        Path("/app/changelog.md"),
        Path(__file__).resolve().parents[2] / "changelog.md",
        Path.cwd() / "changelog.md",
        Path("changelog.md")
    ]
    for p in possible_paths:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                return {"status": "success", "version": settings.app_version, "content": content}
            except Exception as e:
                logger.error(f"Error reading changelog from {p}: {e}")
                
    return {
        "status": "success",
        "version": settings.app_version,
        "content": f"""# Changelog v{settings.app_version}

### 📦 Docker Hub Multi-Arch (amd64/arm64) & 🛡️ Sincronizzazione Nativa AdGuard Home in-App
* **Distribuzione Ufficiale Docker Hub:** Immagine multi-architettura pronta per `linux/amd64` e `linux/arm64`.
* **Integrazione Nativa AdGuard Home in-App:** Configurazione grafica diretta in Automazioni per la sincronizzazione continua di nomi host, IP e MAC address verso AdGuard Home.
* **🎛️ Riorganizzazione Scheda Automazioni:** Layout a quadranti con toggle dedicato per le notifiche Telegram.
* **🔒 Pulsante Disconnessione Sicura:** Ripristinato il logout con modale di sicurezza e avviso per ri-autenticazione OTP.
* **📊 Fix Daily Digest Telegram & Webhook:** Report arricchito con suddivisione dettagliata delle frequenze Wi-Fi e telemetria live.
* **Esportazione DNS & Webhooks:** Endpoint `/api/devices/export/hosts` e `/api/devices/export/adguard` + script CLI.
"""
    }
