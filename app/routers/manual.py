import logging
from typing import Any, Dict, List
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manual", tags=["User Manual"])

MANUAL_SECTIONS: List[Dict[str, Any]] = [
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
  - **Controllo LED:** Pulsanti per accendere o spegnere all'istante i LED frontali dei singoli nodi o di tutta la rete.
        """
    },
    {
        "id": "bandwidth-historian",
        "title": "4. Monitoraggio Banda & Bandwidth Hogs",
        "icon": "chart-bar",
        "summary": "Analisi temporale del traffico WAN e identificazione dei dispositivi più esigenti a dati reali.",
        "content": """
### Storico Consumi e Metriche WAN a Dati Reali al 100%

1. **Grafico Temporale WAN (Download vs Upload):**
   - Traccia i volumi di traffico e la velocità aggregata reale misurata nel tempo.
   - Utilizza i pulsanti rapidi **24 Ore**, **7 Giorni**, **30 Giorni** o imposta un intervallo orario personalizzato.
   - Visualizza il totale dei GigaByte (GB) scambiati nel periodo selezionato calcolato dai delta effettivi registrati.
2. **Classifica Top Consumi (Bandwidth Hogs):**
   - Grafico a barre orizzontale e tabella dettagliata che ordina i dispositivi in base alla quantità totale di dati realmente scambiati (`delta_rx + delta_tx`).
   - **Approccio Rigoroso:** Nessuna simulazione o stima artificiale. Se un dispositivo (es. robot aspirapolvere o domotica) è a riposo o scambia solo minimi pacchetti di telemetria, non viene sovrastimato o inserito artificialmente nei grafici di consumo intensivo.
3. **Throughput Istantaneo in Tempo Reale:**
   - Visualizza la velocità live in Mbps (Down/Up) attualmente impegnata da tutti gli host attivi.
        """
    },
    {
        "id": "device-management",
        "title": "5. Gestione Dispositivi, IP Statici & Porte",
        "icon": "cpu",
        "summary": "Personalizzazione metadati, prenotazioni DHCP, Port Forwarding e pausa internet.",
        "content": """
### Controllo Avanzato dei Client di Rete

* **Ricerca e Filtri:**
  - Cerca per Nome, Indirizzo IP o MAC Address.
  - Filtra per frequenza di connessione (**2.4 GHz, 5 GHz, 6 GHz, Cablato Ethernet**), nodo eero a cui sono agganciati o stato Online/Offline.
  - Indicatore visuale della potenza segnale in dBm (RSSI).
* **Scheda Dettaglio Dispositivo:**
  - **Nome e Icona Personalizzata:** Assegna un'icona specifica (Server, PC, Smartphone, Console, Domotica, Telecamera, ecc.) salvata nel database SQLite locale.
  - **Note & Documentazione:** Campo note libero per salvare credenziali locali, ubicazione, garanzie o porte di servizio.
  - **Prenotazione DHCP (IP Statico):** Assegna un indirizzo IP permanente a un dispositivo basandoti sul suo indirizzo MAC.
  - **Port Forwarding Integrato:** Aggiungi regole di apertura porte (Porta Esterna WAN -> Porta Interna LAN, Protocolli TCP/UDP).
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
   - **Daily Digest:** Ricevi ogni sera alle 21:00 un riassunto dei GB consumati, il dispositivo top consumer e la velocità media.
        """
    },
    {
        "id": "troubleshooting",
        "title": "8. Risoluzione Problemi & Domande Frequenti (FAQ)",
        "icon": "wrench",
        "summary": "FAQ su telemetria reale, gestione sessione, backup e manutenzione.",
        "content": """
### Domande Frequenti & Troubleshooting

* **Perché per alcuni dispositivi Wi-Fi o IoT non compare un consumo elevato o indicano 0 GB?**
  - La dashboard segue un **approccio rigoroso a dati reali al 100%**. A differenza di altre app che inventano stime sintetiche, se un dispositivo (robot aspirapolvere, lampadine smart, sensori) non trasmette flussi consistenti o l'API eero non registra byte per quel client, il sistema mostrerà rigorosamente 0 o il valore esatto campionato, senza gonfiare artificialmente il consumo.
* **Come viene calcolato il consumo delle ultime 24 ore?**
  - Il consumo 24h è calcolato calcolando la differenza esatta (delta) tra i campioni registrati nel database SQLite locale all'interno della finestra temporale selezionata: `Consumo = MAX(rx_bytes) - MIN(rx_bytes)`.
* **Cosa fare se la sessione scade?**
  - Se ricevi un errore di autorizzazione, clicca sul pulsante **Disconnetti** nella barra laterale o nella schermata di login e riesegui la procedura di ricezione del codice OTP a 6 cifre.
* **Come effettuare il backup dei dati storici?**
  - Tutti i dati storici sono contenuti nel file `./data/metrics.db`. Per fare un backup completo, è sufficiente copiare la cartella `./data` sul tuo computer o archivio cloud.
* **Come modificare il periodo di conservazione dei dati?**
  - Nel file `.env` imposta `HISTORY_RETENTION_DAYS=60` (oppure 90) e riavvia il container con `docker compose restart`. Il cleaner notturno adatterà la politica di pulizia.
* **Protezione da Rate Limiting:**
  - L'applicazione interroga il cloud eero solo a intervalli definiti dal poller (default 30s) e risponde a tutte le richieste dell'interfaccia direttamente dalla memoria RAM del server, azzerando il rischio di blocco da parte dei server eero.
        """
    }
]


@router.get("/sections")
async def get_manual_sections():
    """Restituisce tutti i capitoli e le sezioni del manuale utente integrato."""
    return {
        "status": "success",
        "count": len(MANUAL_SECTIONS),
        "sections": MANUAL_SECTIONS
    }


@router.get("/sections/{section_id}")
async def get_manual_section(section_id: str):
    """Restituisce una specifica sezione del manuale (utilizzata anche per i tooltip contestuali)."""
    section = next((s for s in MANUAL_SECTIONS if s["id"] == section_id), None)
    if not section:
        return {"status": "error", "message": "Sezione non trovata."}
    return {"status": "success", "section": section}


@router.get("/changelog")
async def get_changelog():
    """Restituisce il contenuto del file changelog.md per il visualizzatore in-app."""
    import os
    from pathlib import Path

    possible_paths = [
        Path("/app/changelog.md"),
        Path(__file__).resolve().parent.parent.parent / "changelog.md",
        Path("changelog.md")
    ]
    for p in possible_paths:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                return {"status": "success", "version": "1.00.01", "content": content}
            except Exception as e:
                logger.error(f"Error reading changelog from {p}: {e}")
                
    return {
        "status": "success",
        "version": "1.00.01",
        "content": "# Changelog v1.00.01\n\n- Approccio rigoroso a dati reali al 100%.\n- Risolto bug consumo Higgins e delta 24h.\n- Visualizzatore changelog integrato."
    }
