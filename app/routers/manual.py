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
        "title": "7. Automazioni, QR Ospiti, Gaming Mode & Notifiche",
        "icon": "zap",
        "summary": "Smart Guest Wi-Fi con QR Code, Gaming Mode a un clic, modalità notte e notifiche Telegram.",
        "content": """
### Funzionalità Avanzate & Automazioni

1. **Smart Guest Wi-Fi con QR Code Dinamico:**
   - Genera all'istante un QR Code pronto per essere inquadrato da smartphone per connettersi senza dover digitare la password.
   - Pulsante per attivare/disattivare la rete ospiti in qualsiasi momento.
   - Generatore rapido di password sicure e rotazione delle credenziali.
2. **Modalità Gaming / Focus (One-Click Low-Latency):**
   - Con un solo clic, mette automaticamente in pausa tutti i dispositivi secondari/IoT contrassegnati (es. TV in streaming, download di backup) per abbattere il jitter e garantire la minima latenza alle console e ai PC da gioco.
   - Un secondo clic ripristina la normale connettività per tutti gli host.
3. **Modalità Notte Automatica (Night Mode LED):**
   - Scheduler orario (es. 23:00 - 07:00) per spegnere automaticamente i LED dei nodi mesh durante la notte e riaccenderli al mattino.
4. **Notifiche Webhook e Telegram Bot:**
   - **Nuovo Dispositivo Connesso:** Ricevi un alert istantaneo su Telegram quando un apparato mai visto prima si connette alla tua rete.
   - **Nodo Mesh Offline:** Notifica immediata se un ripetitore eero perde la connessione.
        """
    },
    {
        "id": "troubleshooting",
        "title": "8. Risoluzione Problemi & Domande Frequenti (FAQ)",
        "icon": "wrench",
        "summary": "FAQ su telemetria autentica, gestione sessione, backup e manutenzione.",
        "content": """
### Domande Frequenti & Troubleshooting

* **Quali dati sui dispositivi provengono direttamente dall'infrastruttura eero?**
  - La dashboard interroga l'infrastruttura eero leggendo: lo stato di connessione (Online/Offline/Pausa), l'indirizzo IP locale, il MAC Address, il nodo mesh a cui sono associati (Gateway o Beacon), la banda radio Wi-Fi (**2.4 GHz, 5 GHz, 6 GHz o Ethernet Cablato**), il canale wireless (**CH**), il livello del segnale in **dBm** e la velocità di link fisico negoziata (**PHY Link Rate**).
* **Cosa fare se la sessione scade?**
  - Se ricevi un errore di autorizzazione, clicca sul pulsante **Disconnetti** nella barra laterale o nella schermata di login e riesegui la procedura di ricezione del codice OTP a 6 cifre.
* **Come effettuare il backup delle configurazioni e metadati locali?**
  - Tutti i dati personalizzati (nomi custom, icone, note, impostazioni notifiche) sono contenuti nel file `./data/metrics.db`. Per fare un backup completo, è sufficiente copiare la cartella `./data` sul tuo computer o archivio cloud.
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
1. **Self-Hosted & Private:** Runs inside an isolated Docker container on your local server or NAS (HomeLab). Zero external data telemetry, accessible via LAN or private VPN (Tailscale/WireGuard).
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
        "id": "telemetry-api",
        "title": "4. Telemetry & Certified eero Hardware Metrics",
        "icon": "cpu",
        "summary": "Authentic physical network telemetry straight from eero hardware nodes.",
        "content": """
### 100% Authentic Telemetry & Certified Hardware Metrics

The dashboard adheres to strict data integrity standards:
1. **Certified Physical Metrics:**
   - Real-time data reported by eero mesh nodes: **Wi-Fi Band & Frequency (2.4 GHz, 5 GHz, 6 GHz, or Wired Ethernet)**, **Wi-Fi Channel (e.g., CH 36, CH 11)**, **Signal Power RSSI (dBm)**, and **Negotiated Physical PHY Link Rate (e.g., 780.0 / 866.7 Mbps)**.
2. **Official Gateway Speed Test:**
   - WAN speeds shown in network overviews are measured directly by the eero Gateway node to cloud test servers (e.g., 907 Mbps Down / 193 Mbps Up).
3. **Zero Fabricated or Simulated Telemetry:**
   - The platform deliberately excludes artificial bandwidth counters or synthetic estimates, displaying strictly genuine telemetry returned by the eero API.
        """
    },
    {
        "id": "device-management",
        "title": "5. Device Management, Static IP & Port Forwarding",
        "icon": "devices",
        "summary": "Custom metadata, DHCP reservations, port forwarding rules, and internet access control.",
        "content": """
### Advanced Client Control & Configuration

* **Search & Filter:**
  - Search instantly by Custom Name, Hostname, IP Address, or MAC Address.
  - Filter by frequency (**2.4 GHz, 5 GHz, 6 GHz, Wired Ethernet**), connected mesh node, or Online/Offline status.
  - Instant visibility of signal strength in dBm and physical link speed.
* **Device Detail Modal:**
  - **Custom Name & Category:** Assign categories (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Other) saved to the local SQLite database.
  - **Local Notes & Documentation:** Free-form notes for tracking device location, service ports, or internal credentials.
  - **DHCP Reservation (Static IP):** Bind a permanent IP address to a client with automated conflict checking and reassignment support.
  - **Integrated Port Forwarding:** Create and delete port forwarding rules (External WAN Port -> Internal LAN Port, TCP/UDP protocols).
  - **Pause Internet Access:** One-click toggle to block or restore internet access for individual devices.
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
        "title": "7. Automations, Guest QR, Gaming Mode & Notifications",
        "icon": "zap",
        "summary": "Smart Guest Wi-Fi with QR Code, one-click Gaming Focus Mode, and Telegram alerts.",
        "content": """
### Advanced Features & Automations

1. **Smart Guest Wi-Fi with Dynamic QR Code:**
   - Instantly renders a printable, scannable QR Code for guests to connect without manually entering the password.
   - One-click toggle to enable or disable the guest network at any time.
   - Built-in secure password generator and credentials updater.
2. **One-Click Gaming / Focus Mode (Low-Latency Priority):**
   - Pauses all tagged secondary/streaming devices (smart TVs, backup downloads) with a single click to eliminate jitter and minimize latency for competitive gaming rigs.
   - A second click instantly restores normal internet access for all devices.
3. **Automated Night Mode (LED Dimming):**
   - Scheduled night mode (e.g., 23:00 - 07:00) to turn off node LEDs at night and restore them in the morning.
4. **Telegram Bot & Webhook Notifications:**
   - **New Device Alert:** Receive an instant Telegram alert when an unknown MAC address connects to your network.
   - **Mesh Node Offline:** Immediate notification if any eero node loses connectivity.
        """
    },
    {
        "id": "troubleshooting",
        "title": "8. Troubleshooting & Frequently Asked Questions (FAQ)",
        "icon": "wrench",
        "summary": "Frequently asked questions regarding telemetry, session handling, backups, and maintenance.",
        "content": """
### Troubleshooting & FAQ

* **Which client metrics come directly from eero hardware?**
  - The dashboard reads client connection state (Online/Offline/Paused), local IP address, MAC Address, connected mesh node (Gateway or Beacon), Wi-Fi frequency band (**2.4 GHz, 5 GHz, 6 GHz, or Wired Ethernet**), wireless channel (**CH**), RSSI signal strength in **dBm**, and negotiated physical rate (**PHY Link Rate**).
* **What should I do if my session expires?**
  - If you encounter authorization errors, click the **Logout** button or re-authenticate from the login modal with a fresh 6-digit OTP code.
* **How do I back up local configurations and custom metadata?**
  - All custom device names, categories, notes, and notification settings are stored in `./data/metrics.db`. To create a complete backup, copy the `./data` directory to your computer or backup storage.
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
* **Esportazione DNS & Webhooks:** Endpoint `/api/devices/export/hosts` e `/api/devices/export/adguard` + script CLI.
"""
    }

