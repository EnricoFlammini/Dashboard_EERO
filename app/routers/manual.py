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
1. **Self-Hosted & Riservatezza:** L'applicazione viene eseguita all'interno di un container Docker isolato sul tuo server locale o NAS (HomeLab). Immagine ufficiale Docker Hub multi-architettura pronta per `linux/amd64` e `linux/arm64` (Raspberry Pi 4/5, Synology, QNAP, TrueNAS, Apple Silicon).
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
4. **Modalità Demo & Switch Rapido:**
   - Se desideri esplorare l'applicazione senza inserire credenziali, puoi attivare la modalità dimostrativa con il pulsante dedicato o impostando `DEMO_MODE=true` nel file `.env`.
   - Se sei già autenticato con il tuo account reale, puoi cliccare in qualunque momento sul pulsante **"✨ Demo Mode"** nella barra superiore per visualizzare i dati demo senza perdere la sessione, e tornare all'istante alla rete live con **"⚡ Torna a Live"**.
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
        "id": "devices-table",
        "title": "4. Dispositivi Connessi & Analisi Frequenze",
        "icon": "devices",
        "summary": "Tabella live dei client, ordinamento colonne, barra titoli sticky, badge bande Wi-Fi e profili.",
        "content": """
### Inventario Client in Tempo Reale

* **Ordinamento Interattivo Multi-Colonna:** Clicca su qualunque intestazione di colonna (Dispositivo/Nome, Indirizzo IP numerico IPv4, Profilo, Nodo Mesh, Banda, Segnale RSSI in dBm e Stato) per commutare istantaneamente l'ordine crescente e decrescente.
* **Barra dei Titoli Bloccata (Sticky Header):** L'intestazione della tabella rimane sempre visibile in cima allo schermo durante lo scorrimento di elenchi con decine o centinaia di apparati.
* **Indicatori di Banda & Canale Wi-Fi:** Badge espliciti per ciascun dispositivo (**6 GHz, 5 GHz, 2.4 GHz, Cablato Ethernet**) e canale wireless attivo (**CH 36, CH 11**, ecc.).
* **Profili Utente Cloud eero:** Visualizzazione del membro della famiglia assegnato a ciascun apparato direttamente sincronizzato con l'app eero.
* **Filtri Multi-Criterio Avanzati:** Filtra rapidamente per Frequenza di Banda, Profilo Utente, Nodo Mesh di attestazione o Tipo di Assegnazione IP (Statico vs DHCP).
        """
    },
    {
        "id": "device-details",
        "title": "5. Metadati Dispositivo, IP Statici & Port Forwarding",
        "icon": "adjustments",
        "summary": "Personalizzazione nomi, categorie, note locali, prenotazioni DHCP e port forwarding.",
        "content": """
### Gestione e Configurazione del Singolo Dispositivo

* **Modale Dettaglio Dispositivo:**
  - **Nome e Categoria Personalizzata:** Assegna categorie (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Altro) salvate nel database SQLite locale.
  - **Note & Documentazione Locale:** Campo note libero per salvare credenziali locali, ubicazione o porte di servizio.
  - **Prenotazione DHCP (IP Statico):** Assegna un indirizzo IP permanente a un dispositivo con verifica automatica dei conflitti.
  - **Port Forwarding Integrato:** Aggiungi e rimuovi regole di apertura porte (Porta Esterna WAN -> Porta Interna LAN, Protocolli TCP/UDP).
  - **Pausa Connessione:** Interruttore per bloccare o consentire l'accesso a Internet del singolo dispositivo.
        """
    },
    {
        "id": "speedtest",
        "title": "6. Speed Test & Diagnostica Prestazioni",
        "icon": "gauge",
        "summary": "Esecuzione test di velocità, storico delle misurazioni e analisi della latenza.",
        "content": """
### Diagnostica di Velocità

* **Test Manuale:** Clicca sul pulsante **"Avvia Speed Test"** per lanciare una misurazione in tempo reale di Download, Upload, Latenza (Ping) e Jitter direttamente dal Gateway eero.
* **Test Automatici Pianificati:** Il sistema monitora e storicizza periodicamente i test eseguiti dall'infrastruttura mesh per valutare la costanza della linea FTTH/VDSL.
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
   - **Registro Persistente Dispositivi Noti:** Tabella SQLite `known_devices` per memorizzare gli apparati già visti ed evitare qualsiasi invio di notifiche duplicate al riavvio o all'aggiornamento del container.
   - **Toggle di Abilitazione Dedicato:** Attiva o disattiva l'invio delle notifiche Telegram con un semplice clic senza eliminare le chiavi salvate.
   - **Nuovo Dispositivo Connesso:** Alert istantaneo quando un apparato mai visto prima si connette alla rete.
   - **Nodo Mesh Offline:** Notifica immediata se un ripetitore eero perde la connessione.
   - **Pulsante "Invia Test":** Verifica il corretto recapito dei messaggi verso il bot Telegram e l'URL Webhook.
4. **Report Digest Giornaliero (In basso a destra):**
   - **Toggle di Abilitazione Programmata:** Consente di attivare o sospendere l'inoltro automatico delle ore 21:00.
   - Invia un riepilogo dettagliato con: stato di salute della rete, ISP, nodi mesh online, client connessi suddivisi per frequenza (**6 GHz, 5 GHz, 2.4 GHz, Cablati**) e velocità Speed Test Gateway.
   - Pulsante **"Genera & Invia Digest Ora"** per richiedere l'inoltro immediato del report in qualsiasi momento.
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
        "summary": "Live device table, multi-column sorting, sticky headers, Wi-Fi band badges, and eero cloud profiles.",
        "content": """
### Real-Time Device Inventory

* **Interactive Multi-Column Sorting:** Click any column header (Device/Name, Numerical IPv4 Address, Profile, Mesh Node, Band, RSSI Signal dBm, or Status) to toggle ascending and descending sort order.
* **Locked Sticky Header Bar:** The table header stays permanently anchored at the top of the viewport while scrolling through dozens of clients.
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
   - **Persistent Known Devices Registry:** SQLite `known_devices` table tracking previously discovered MACs to prevent duplicate alerts on container restarts.
   - **Dedicated Activation Toggle:** Enable or disable Telegram notifications with one click while safely preserving your Bot Token and Chat ID.
   - **New Device Alert:** Receive an instant alert when an unknown MAC address connects to your mesh.
   - **Mesh Node Offline:** Immediate notification if any eero node loses connectivity.
   - **"Send Test" Button:** Instantly tests message delivery to your Telegram bot and Webhook URL.
4. **Daily Digest Report (Bottom-Right):**
   - **Scheduled Dispatch Toggle:** Enable or suspend the automatic 21:00 summary dispatch.
   - Automated report containing: Network Health Score, ISP, online mesh nodes, active clients breakdown by frequency band (**6 GHz, 5 GHz, 2.4 GHz, Ethernet**), Gateway Speed Test and Ping latency.
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
async def get_manual_sections(lang: Optional[str] = Query("en")):
    """Restituisce tutti i capitoli del manuale utente nella lingua richiesta (it/en)."""
    is_it = bool(lang and lang.lower().startswith("it"))
    sections = MANUAL_SECTIONS_IT if is_it else MANUAL_SECTIONS_EN
    return {
        "status": "success",
        "count": len(sections),
        "language": "it" if is_it else "en",
        "sections": sections
    }


@router.get("/sections/{section_id}")
async def get_manual_section(section_id: str, lang: Optional[str] = Query("en")):
    """Restituisce una specifica sezione del manuale (utilizzata anche per i tooltip contestuali)."""
    is_it = bool(lang and lang.lower().startswith("it"))
    sections = MANUAL_SECTIONS_IT if is_it else MANUAL_SECTIONS_EN
    section = next((s for s in sections if s["id"] == section_id), None)
    if not section:
        return {"status": "error", "message": "Section not found."}
    return {"status": "success", "language": "it" if is_it else "en", "section": section}


CHANGELOG_SUMMARY_IT = """# Changelog - Sommario Versioni

Di seguito sono riassunti i titoli principali delle release. Il registro completo con tutti i dettagli tecnici è consultabile su GitHub.

---

## v1.03.00
* **Risoluzione Universale Nodi e Client Mesh Multi-Generazione (Pro 7 / 6E / 6+)**
* **Switch Istantaneo Modalità Demo / Rete Live senza perdita Token**
* **Rilevamento Dinamico Velocità Ethernet 2.5G/10G & Telemetria Segnale dBm/PHY**
* **Sincronizzazione Profili Famiglia / Utente Cloud eero in Tabella e Dettaglio**
* **Distribuzione Ufficiale Docker Hub Multi-Arch (amd64/arm64)**
* **Integrazione Nativa AdGuard Home in-App (DNS & DHCP Sync)**
* **Pulsante Disconnessione Sicura con Modale di Conferma OTP**
* **Fix & Arricchimento Report Daily Digest Telegram**
* **Riorganizzazione Scheda Automazioni & Toggle Notifiche Dedicati**
* **Registro Persistente Dispositivi Noti (Zero Notifiche Duplicate al Riavvio)**
* **Ordinamento Dispositivi & Barra dei Titoli Bloccata (Sticky Header)**
* **Normalizzazione Dinamica Dispositivi & Gestione Flessibile Nodi/Sensori**
* **Modale About & Dedica Open Source**
* **Rendering Ottimizzato del Manuale & Liste Markdown**
* **Esportazione DNS (/etc/hosts, JSON) & Webhooks**

---

## v1.02.00
* **Telemetria Frequenze Wi-Fi (2.4 / 5 / 6 GHz) & Canali Radio**
* **Integrazione Profili Famiglia / Utente Cloud eero**
* **Filtri Multi-Criterio Avanzati su Tabella Client**

---

## v1.01.00
* **Supporto Multilingua Dinamico (Italiano & Inglese)**
* **Selettore Lingua nell'Header & Persistenza Preferenze**
* **Standard Open Source GitHub & Licenza MIT**

---

## v1.00.08
* **Sincronizzazione Totale Speed Test & Statistiche Gateway**

---

## v1.00.07
* **Indicatori Visivi Tipo IP (Badge STATICO vs DHCP)**

---

## v1.00.06
* **Assegnazione IP Corrente & Riassegnazione Intelligente**

---

## v1.00.05
* **Gestione Nativa IP Statici (DHCP) & Port Forwarding**

---

## v1.00.04
* **Gestione Dispositivi, Icone, Categorie e Preferiti**

---

## v1.00.01 - v1.00.03
* **Eliminazione Dati Fittizi a Favore di Telemetria Certificata 100%**

---

## v1.0.0
* **Release Iniziale: Architettura Self-Hosted Docker, 2FA OTP & Poller**
"""

CHANGELOG_SUMMARY_EN = """# Changelog - Release Summary

Below is a summary of the main release highlights. The complete changelog with all technical details is available on GitHub.

---

## v1.03.00
* **Universal Multi-Generation Mesh Nodes & Client Resolution (Pro 7 / 6E / 6+)**
* **Instant Demo Mode / Live Network Switcher without Token Loss**
* **Dynamic 2.5G/10G Ethernet Speed Detection & Signal dBm/PHY Rate Telemetry**
* **eero Cloud User & Family Profile Telemetry in Table and Modal**
* **Official Multi-Arch Docker Hub Image (amd64/arm64)**
* **Native In-App AdGuard Home Integration (DNS & DHCP Sync)**
* **Secure Logout Button with OTP Confirmation Modal**
* **Daily Digest Report Fixes & Rich Live Telemetry**
* **Automations Tab 2x2 Layout & Dedicated Notification Toggles**
* **Persistent Known Devices Registry (Zero Duplicate Alerts on Restart)**
* **Interactive Device Sorting & Sticky Table Header Bar**
* **Dynamic Device Discovery & Adaptive Hardware Sensor Display**
* **About Modal & Open Source Dedication**
* **Optimized In-App Markdown Rendering & Ordered Lists**
* **DNS (/etc/hosts, JSON) & Webhook Exporting**

---

## v1.02.00
* **Wi-Fi Band Telemetry (2.4 / 5 / 6 GHz) & Channel Badges**
* **eero Cloud User & Family Profile Integration**
* **Advanced Multi-Criteria Client Table Filters**

---

## v1.01.00
* **Dynamic Multilingual Support (Italian & English)**
* **Header Language Selector & Preference Persistence**
* **GitHub Open Source Standards & MIT License**

---

## v1.00.08
* **Total Speed Test Synchronization & Gateway Statistics**

---

## v1.00.07
* **Visual IP Assignment Badges (STATIC vs DHCP)**

---

## v1.00.06
* **Current IP Lease Binding & Smart IP Reassignment**

---

## v1.00.05
* **Native Cloud DHCP Reservations & Port Forwarding Rules**

---

## v1.00.04
* **Device Management, Custom Icons, Categories & Favorites**

---

## v1.00.01 - v1.00.03
* **Synthetic Data Removal in Favor of 100% Certified Telemetry**

---

## v1.0.0
* **Initial Release: Self-Hosted Docker Architecture, 2FA OTP & Poller**
"""


@router.get("/changelog")
async def get_changelog(lang: Optional[str] = Query("en")):
    """Restituisce solo i titoli e gli highlight principali delle versioni nella lingua richiesta (it/en)."""
    from app.config import settings

    is_it = bool(lang and lang.lower().startswith("it"))
    content = CHANGELOG_SUMMARY_IT if is_it else CHANGELOG_SUMMARY_EN

    return {
        "status": "success",
        "language": "it" if is_it else "en",
        "version": settings.app_version,
        "content": content
    }
