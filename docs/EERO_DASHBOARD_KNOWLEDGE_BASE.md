# eero Custom Dashboard & Management Suite — Knowledge Base Completa (v1.5.0)

> **Documento di Riferimento per NotebookLM, Sviluppatori e Amministratori di Sistema**  
> *Versione di riferimento del software:* **v1.5.0**  
> *Autore e Maintainer:* **Enrico Flammini**  
> *Licenza:* **MIT (Open Source)**  
> *Repository Ufficiale:* [GitHub - EnricoFlammini/Dashboard_EERO](https://github.com/EnricoFlammini/Dashboard_EERO)  
> *Immagine Docker Ufficiale:* [`enricoflammini/eero-dashboard`](https://hub.docker.com/r/enricoflammini/eero-dashboard) (Multi-Arch `linux/amd64`, `linux/arm64`)

---

## Indice dei Contenuti

1. [Panoramica del Progetto & Visione](#1-panoramica-del-progetto--visione)
2. [Architettura del Sistema & Stack Tecnologico](#2-architettura-del-sistema--stack-tecnologico)
3. [Autenticazione Cloud eero & Gestione Sessione](#3-autenticazione-cloud-eero--gestione-sessione)
4. [Funzionalità Chiave della Suite](#4-funzionalità-chiave-della-suite)
   * 4.1 [Multi-Network Fleet Management & Hot-Swap (v1.5.0 - Issue #22)](#41-multi-network-fleet-management--hot-swap-v150---issue-22)
   * 4.2 [Intelligent Address Pruning & Esclusione IPv6 DNS (v1.5.0 - Issue #31 & #30)](#42-intelligent-address-pruning--esclusione-ipv6-dns-v150---issue-31--30)
   * 4.3 [Device Data Usage Insights Suite & Top Bandwidth Hogs (v1.5.0)](#43-device-data-usage-insights-suite--top-bandwidth-hogs-v150)
   * 4.4 [Windows 11 Fluent Design & Dual-Theme Engine (v1.4.0)](#44-windows-11-fluent-design--dual-theme-engine-v140)
   * 4.5 [Sidebar Navigation Collassabile & Controlli Rapidi (v1.4.0)](#45-sidebar-navigation-collassabile--controlli-rapidi-v140)
   * 4.6 [Network Health Score Breakdown a 4 Pilastri (v1.4.0 - Issue #15)](#46-network-health-score-breakdown-a-4-pilastri-v140---issue-15)
   * 4.7 [Multi-Engine DNS Synchronizer (AdGuard, Pi-hole, Technitium)](#47-multi-engine-dns-synchronizer-adguard-pi-hole-technitium)
   * 4.8 [Storicizzazione Segnale Wi-Fi RSSI & Mesh Coverage (v1.4.0)](#48-storicizzazione-segnale-wi-fi-rssi--mesh-coverage-v140)
   * 4.9 [Auto-Update Docker In-App a 1-Clic (/api/system/update)](#49-auto-update-docker-in-app-a-1-clic-apisystemupdate)
   * 4.10 [Prenotazioni DHCP & Port Forwarding](#410-prenotazioni-dhcp--port-forwarding)
   * 4.11 [Gaming Focus Mode (Bassa Latenza)](#411-gaming-focus-mode-bassa-latenza)
   * 4.12 [Smart Guest Wi-Fi & QR Code Dual-Theme](#412-smart-guest-wi-fi--qr-code-dual-theme)
   * 4.13 [Notifiche Telegram, Webhook & Daily Digest](#413-notifiche-telegram-webhook--daily-digest)
   * 4.14 [Speed Test & Analisi Prestazioni Gateway](#414-speed-test--analisi-prestazioni-gateway)
   * 4.15 [Modalità Demo (Simulatore Integrato Dual-Network)](#415-modalità-demo-simulatore-integrato-dual-network)
   * 4.16 [Statistiche & Analytics di Rete, SLA ISP & Data Export Center (v1.5.0)](#416-statistiche--analytics-di-rete-sla-isp--data-export-center-v150)
   * 4.17 [Telemetria Switching Hardware Layer 2 & Dispositivi Cablati (Issue #40 & #42)](#417-telemetria-switching-hardware-layer-2--dispositivi-cablati-issue-40--42)
   * 4.18 [Community Hall of Fame & Crediti Open Source](#418-community-hall-of-fame--crediti-open-source)
5. [Specifiche del Database SQLite (`metrics.db`)](#5-specifiche-del-database-sqlite-metricsdb)
6. [Catalogo Completo API REST (Endpoint Reference)](#6-catalogo-completo-api-rest-endpoint-reference)
7. [Variabili d'Ambiente & Configurazione (`.env`)](#7-variabili-dambiente--configurazione-env)
8. [Storico Bug Risolti, Cause Radice (RCA) & Issue di Riferimento](#8-storico-bug-risolti-cause-radice-rca--issue-di-riferimento)
9. [Guida al Troubleshooting & FAQ per l'Utente](#9-guida-al-troubleshooting--faq-per-lutente)

---

## 1. Panoramica del Progetto & Visione

**eero Custom Dashboard & Management Suite** è un'applicazione web containerizzata e self-hosted progettata per colmare il divario tra l'ecosistema mobile proprietario di **Amazon eero** e le esigenze avanzate di utenti prosumer, sistemisti e appassionati di homelab.

### Principi Fondamentali
1. **Telemetria Hardware Autentica e Certificata al 100%:** Rifiuto categorico di metriche fittizie o stime sintetiche; tutti i dati (bande Wi-Fi 2.4/5/6 GHz, canali radio, bitrate PHY, potenze RSSI, indirizzi IP, lease DHCP, porte fisiche WAN/LAN) derivano direttamente dalla telemetria ufficiale eero.
2. **Zero-Latency In-Memory RAM Cache:** Un motore asincrono di polling in background interroga periodicamente le API cloud di eero, mantenendo lo stato sincronizzato in memoria RAM. L'interfaccia utente web risponde a tutte le richieste in **0 ms**, proteggendo l'account da rate-limiting cloud.
3. **Zero Telemetria Esterna & Privacy-First:** Nessuna raccolta di telemetria analitica verso terzi. I dati di rete rimangono confinati nel container Docker locale e nel volume SQLite persistente.
4. **Resilienza e Isolamento Demo:** Separazione rigorosa tra la sessione Live e la modalità Demo/Simulatore, permettendo di testare e validare tutte le funzioni senza inviare comandi reali alla rete fisica e senza sovrascrivere il token di sessione dell'utente.

---

## 2. Architettura del Sistema & Stack Tecnologico

### Stack Tecnologico
* **Backend:** Python 3.12 (`python:3.12-slim-bookworm`), FastAPI >= 0.115, Uvicorn >= 0.32, Pydantic v2.
* **HTTP Client & Connection Pooling:** `httpx.AsyncClient` con DNS cache in memoria (`InMemoryDnsCache`, TTL 300s) e Keep-Alive per minimizzare l'overhead di handshaking TLS verso `api-user.e2ro.com`.
* **Database Relazionale Locale:** SQLite in modalità WAL (*Write-Ahead Logging*) gestito asincronamente con `aiosqlite`.
* **Frontend:** Architettura Single-Page Application reattiva e ultraleggera con Semantic HTML5, Vanilla CSS e Tailwind CSS, Alpine.js (v3.14+) per il reactive data binding e Chart.js (v4.4+) per i grafici temporali.
* **Containerizzazione:** Immagini Docker multi-architettura (`linux/amd64` per PC/Server x86 e `linux/arm64` per Raspberry Pi / Apple Silicon).

### Diagramma dei Componenti

```
 +-------------------------------------------------------------------------+
 |                              FRONTEND SPA                               |
 |       Alpine.js 3.14 + Tailwind CSS + Windows 11 Fluent Design System   |
 +--------------------+-------------------------------+--------------------+
                      |                               |
              HTTP/JSON (0 ms)                REST API (Commands)
                      v                               v
 +--------------------+-------------------------------+--------------------+
 |                        FASTAPI ROUTERS LAYER                            |
 |  /api/network | /api/devices | /api/automations | /api/metrics | ...     |
 +--------------------+-------------------------------+--------------------+
                      |                               |
                      v                               v
 +--------------------+----------------+    +---------+--------------------+
 |       BACKGROUND POLLER (RAM)       |    |         SQLITE ENGINE        |
 |  • Cache In-Memory (Zero Rate-Limit)|    |  • aiosqlite (WAL Mode)      |
 |  • Campionamento Segnale RSSI       |    |  • metrics.db persistente    |
 |  • Campionamento Delta Traffico     |    |  • Dispositivi Noti          |
 |  • Calcolo Dinamico Health Score    |    |  • Storico Speedtest & Usage |
 +--------------------+----------------+    +------------------------------+
                      |
           Async HTTPS (TLS + DNS Cache)
                      v
 +-------------------------------------------------------------------------+
 |                        AMAZON EERO CLOUD REST API                       |
 |             api-user.e2ro.com (Endpoint 2.2 / Login 2FA OTP)            |
 +-------------------------------------------------------------------------+
```

---

## 3. Autenticazione Cloud eero & Gestione Sessione

### Flusso di Autenticazione Ufficiale (2FA OTP)
1. L'utente inserisce il proprio numero di telefono internazionale (es. `+393331234567`) o la propria email dell'account Amazon/eero.
2. Il server invoca l'endpoint cloud `POST /2.2/login` ricevendo un `user_token` temporaneo.
3. eero invia all'utente un codice di verifica a 6 cifre (One-Time Password via SMS o email).
4. L'utente invia il codice al dashboard: il sistema invoca `POST /2.2/login/verify` confermando la sessione e ottenendo il token di autenticazione definitivo permanente.
5. Il token e l'identificativo della rete attiva vengono memorizzati in `data/session.json` (volume Docker montato `/app/data`).

### Token Persistente da Variabile d'Ambiente
È possibile impostare `EERO_USER_TOKEN` direttamente nel file `.env` o nel `docker-compose.yml`. All'avvio, il sistema verifica la presenza del token configurato ed effettua il bypass automatico del login interattivo.

### Preservazione Token Reale in Demo Mode
Quando l'utente attiva la **Modalità Demo**, il token Live reale viene preservato in `saved_live_token`. L'applicazione commuta l'ambiente sui dati simulati senza invalidare né cancellare il cookie di sessione autenticato. Facendo clic su *"Torna a Live"*, la dashboard ripristina la sessione autenticata senza dover ripetere la 2FA.

---

## 4. Funzionalità Chiave della Suite

### 4.1 Multi-Network Fleet Management & Hot-Swap (v1.5.0 - Issue #22)
* **Contesto & Risoluzione:** Utenti che gestiscono molteplici reti eero sotto un unico account (abitazione principale, ufficio, seconda casa, rete dei genitori) in precedenza venivano forzati alla sola prima rete restituita dall'API (`networks[0]`).
* **Mappatura Completa dell'Account:** Ispezione di tutte le chiavi dell'account eero: `networks`, `shared_networks`, `admin_networks` e chiamata di fallback a `/2.2/networks`.
* **Hot-Swap Dinamico:** Cambio a caldo della rete selezionata tramite l'endpoint `POST /api/network/switch` con payload `{"network_id": "..."}`.
* **Persistenza Rete Attiva:** La scelta dell'utente viene salvata in `current_network_id` sia in RAM sia su disco in `session.json`. Durante ogni ciclo di polling in background, il sistema interroga esclusivamente la rete attiva scelta, prevenendo reset involontari.
* **UI Windows 11 Fluent Dropdown:** Se l'account gestisce $\ge 2$ reti, il nome della rete nell'header diventa un menu a tendina interattivo con chevron e indicatore del numero di nodi e client connessi.
* **Dual-Network in Demo Mode:** Include due reti simulate (*"Casa Rossi Mesh 6E"* e *"Ufficio & Studio Pro Mesh"*) per testare e mostrare lo switch in tempo reale.

### 4.2 Intelligent Address Pruning & Esclusione IPv6 DNS (v1.5.0 - Issue #31 & #30)
* **Contesto & Risoluzione:** La sincronizzazione con AdGuard Home causava l'accumulo di centinaia di indirizzi IPv6 SLAAC temporanei e vecchi lease DHCP per il medesimo dispositivo, congestionando la tabella client di AdGuard.
* **Riconciliazione Deterministica con `ipaddress`:** Il metodo `_merge_adguard_client_data` di `DNSManager` classifica gli identificatori mediante analisi deterministica:
  * **MAC Address hardware:** Preservati sempre.
  * **Custom CIDR subnet e Host Aliases:** Preservati sempre (es. `custom-alias.lan`, `storage.local`, `192.168.4.0/24`).
  * **Indirizzi IPv4:** Viene mantenuto l'IP attivo; se il dispositivo è offline, si preserva l'ultimo noto.
  * **Indirizzi IPv6 SLAAC:** Vengono potati chirurgicamente tutti gli indirizzi IPv6 temporanei non più presenti nella telemetria attiva di eero.
* **Controlli per Istanza DNS:**
  * `prune_stale_ips` (default: `true`): Abilita la pulizia dei lease e SLAAC obsoleti.
  * `drop_ipv6` (default: `false`): Esclude totalmente gli indirizzi IPv6 dalla sincronizzazione per infrastrutture con stack locale esclusivamente IPv4.

### 4.3 Device Data Usage Insights Suite & Top Bandwidth Hogs (v1.5.0)
* **Telemetria Consumi per Dispositivo:** Tabella SQLite dedicata `device_usage_history` con indici compositi per MAC e timestamp.
* **Campionamento Delta Traffico:** Ad ogni ciclo del poller vengono calcolati il delta di byte trasferiti in download e upload e la velocità effettiva di trasferimento in Mbps.
* **Algoritmo Delta Resiliente a Reset Hardware:** Il calcolo dei consumi di periodo in `db.py` non esegue una banale differenza tra ultimo e primo campione (`last - first`), ma accumula iterativamente gli incrementi e rileva gli azzeramenti dei contatori hardware Wi-Fi (causati da standby, disconnessioni o roaming mesh), evitando la perdita o la sottostima dei dati scaricati.
* **Tab 4 "Consumo Dati" nel Modale Dispositivo:**
  * Selettore di intervallo temporale: **Ultime 24h** (campionamento orario/a intervalli), **7 Giorni** (giornaliero), **30 Giorni** (mensile).
  * KPI aggregati: **Download Totale**, **Upload Totale**, **Traffico Combinato** corredati da pulsanti `?` di approfondimento contestuale e badge esplicativo "Dati Stimati".
  * Grafico temporale interattivo Chart.js con linee per download (blu) e upload (verde smeraldo).
  * **Modale Trasparenza Calcolo Dati (`showUsageInfoModal`):** Documentazione integrata che illustra la stima dai pacchetti fisici (per reti senza eero Plus), l'effetto della compressione di rete rispetto allo spazio su disco dei giochi/installer, e la differenza tra contatore cumulativo assoluto e delta di periodo.
* **Widget Dashboard "Top Bandwidth Hogs":** Card nella schermata principale con la classifica dei dispositivi che consumano più dati nella rete, evidenziando i primi 3 classificati (Oro, Argento, Bronzo) e offrendo l'apertura con 1-click del dettaglio dispositivo.

### 4.4 Windows 11 Fluent Design & Dual-Theme Engine (v1.4.0)
* Materiali visivi Mica e Acrylic con trasparenze graduate in CSS Vanilla.
* Font Segoe UI Variable con fallback su Inter e JetBrains Mono per dati di rete (IP, MAC, Mbps).
* Motore a doppio tema (Chiaro / Scuro / Sistema) con script anti-FOUC nell'head che previene sfarfallii all'avvio.
* Riadattamento cromatico dinamico delle griglie e delle palette di Chart.js al cambio tema.

### 4.5 Sidebar Navigation Collassabile & Controlli Rapidi (v1.4.0)
* Barra di navigazione verticale espandibile (`256px`) e collassabile (`68px`) con memoria di stato in `localStorage`.
* Icone perfettamente centrate a 44x44px in modalità compatta con micro-badge d'angolo per il conteggio dei client.
* Controlli rapidi integrati: pulsante **Gaming Mode** e pulsante **Simulatore Rete (Demo Mode)** con indicatore verde smeraldo pulsante quando la modalità demo è attiva.

### 4.6 Network Health Score Breakdown a 4 Pilastri (v1.4.0 - Issue #15)
Algoritmo ponderato che calcola un punteggio di salute da 0 a 100% analizzando 4 pilastri:
1. **Topologia Mesh & Nodi (35 pt):** Presenza e stabilità del Gateway, stato operativo dei nodi (`online`, `rebooting`, `offline`), qualità del backhaul cablato o wireless (6 GHz / 5 GHz).
2. **Gateway WAN & Connettività (25 pt):** Stato uplink internet, disponibilità IP pubblico, latenza ping verso gateway e server speedtest.
3. **Qualità Segnale Wi-Fi Client (25 pt):** Valutazione della distribuzione RSSI dei dispositivi wireless (percentuale di client con segnale $\ge -65\text{ dBm}$ vs deboli $< -75\text{ dBm}$).
4. **Distribuzione Spettro & Canali (15 pt):** Bilanciamento dei client tra le bande 6 GHz, 5 GHz e 2.4 GHz per prevenire saturazione sui 2.4 GHz.

Finestra modale con spiegazione dettagliata in bilingue, elenco delle penalità attive per dispositivo/nodo e raccomandazioni correttive concrete.

### 4.7 Multi-Engine DNS Synchronizer (AdGuard, Pi-hole, Technitium)
* Sincronizzazione automatica e continua dei nomi host e degli indirizzi IP dei dispositivi verso server DNS locali.
* Supporto per istanze simultanee eterogenee:
  * **AdGuard Home:** Autenticazione HTTP Basic, tag client (`device_laptop`, `device_phone`, ecc.), upstreams personalizzati.
  * **Pi-hole:** Autenticazione token WEBPASSWORD / session SID, gestione `/admin/api.php?customdns`.
  * **Technitium DNS Server:** Autenticazione session token, creazione zone autoritative PTR e record A/AAAA.
* Test di connettività per singola istanza o globale e pulsante "Sync Now".

### 4.8 Storicizzazione Segnale Wi-Fi RSSI & Mesh Coverage (v1.4.0)
* Tabella SQLite `device_signal_history`.
* Rilevamento continuo del livello RSSI (dBm), banda e frequenza.
* Indicatore visivo del segnale medio dell'intera abitazione.
* Rilevamento continuo del livello RSSI (dBm), banda e frequenza.
* Indicatore visivo del segnale medio dell'intera abitazione.
* **Smart Signal Watchlist & Prevenzione Falsi Positivi:** Monitoraggio dei dispositivi con segnale critico ($< -75\text{ dBm}$) con consigli per il riposizionamento dei nodi mesh. Include due innovazioni fondamentali:
  * **Bonifica Transitori di Uscita (*Exit Transient Pruning*):** Quando un dispositivo mobile lascia l'abitazione, il segnale degrada drasticamente prima dello sgancio definitivo. Il poller rileva la disconnessione (`connected: True -> False`) e purga in automatico gli ultimi campioni critici registrati nei 5 minuti precedenti, impedendo che lo smartphone rimanga bloccato nella watchlist per 6 ore dopo essere uscito di casa.
  * **Filtro di Presenza Attiva in Tempo Reale:** La watchlist e i KPI di salute mesh considerano esclusivamente i client wireless attualmente connessi alla rete.

### 4.9 Auto-Update Docker In-App a 1-Clic (`/api/system/update`)
* Verifica oraria di nuove versioni disponibili confrontando i tag su Docker Hub e GitHub Releases.
* Badge animato nell'header quando è disponibile un aggiornamento.
* Ricreazione automatica del container in 1 clic tramite socket Docker (`/var/run/docker.sock`), webhook Watchtower o istruzioni assistite da riga di comando.

### 4.10 Prenotazioni DHCP & Port Forwarding
* Visualizzazione istantanea delle prenotazioni IP statiche con badge dedicato nella tabella principale.
* Risoluzione preventiva dei conflitti di IP (segnalazione di collisioni con subnet o altri client).
* Gestione completa del Port Forwarding cloud eero (porta esterna WAN, porta interna LAN, protocollo TCP/UDP, descrizione del servizio).

### 4.11 Gaming Focus Mode (Bassa Latenza)
* Automazione low-latency con un solo clic: mette temporaneamente in pausa il traffico di background di apparati secondari, TV o dispositivi IoT per azzerare bufferbloat e jitter durante videoconferenze o sessioni di gioco online.

### 4.12 Smart Guest Wi-Fi & QR Code Dual-Theme
* Generazione istantanea del QR Code standard Wi-Fi (`WIFI:S:...;T:WPA;P:...;;`) per la connessione immediata degli ospiti senza digitare la chiave di rete.
* Rendering dual-theme: matrice con sfondo bianco puro in Light Mode e ardesia scuro in Dark Mode per garantire scansione ottica ottimale da qualsiasi fotocamera.
* Attivazione/disattivazione della rete ospiti cloud e generazione di password casuali robuste.

### 4.13 Notifiche Telegram, Webhook & Daily Digest
* **Intruder Alert (Nuovo Dispositivo):** Alert immediato all'apparire di un nuovo MAC address non presente nella tabella SQLite `known_devices`.
* **Mesh Node Offline:** Notifica tempestiva in caso di caduta di un nodo mesh.
* **Daily Digest:** Report serale (ore 21:00) con riepilogo su stabilità di rete, velocità WAN, stato nodi e ripartizione bande.
* Supporto per bot Telegram e webhook JSON generici compatibili con Home Assistant.

### 4.14 Speed Test & Analisi Prestazioni Gateway
* **Esecuzione NATIVA sull'Hardware del Router Gateway eero:** A differenza di altri applicativi che eseguono benchmark locali sul container Docker (colli di bottiglia su bridge virtuali, CPU dell'host o Wi-Fi), il test viene scatenato direttamente sul processore del Gateway eero verso i server di test Amazon/eero tramite chiamata REST `POST /2.2/networks/{network_id}/speedtest`.
* **Campionamento Reale della Porta WAN verso l'ISP:** La misurazione riflette la reale capacità fisica di linea della fibra/rame dell'ISP senza alcuna influenza da parte dell'hardware o della rete in cui gira il container Docker.
* **Sincronizzazione Automatica Test Notturni eero:** Il router eero esegue nativamente test periodici notturni per ottimizzare il QoS/SQM di rete; la dashboard intercetta tali misurazioni da eero Cloud e le storicizza su SQLite.
* **Storico Dati su SQLite:** Grafici storici Chart.js di Download, Upload e Latenza Ping.
* **Protezione e Purga Dati Mock:** Rimozione garantita dei record fittizi (`912.45 Mbps / 298.10 Mbps`) per prevenire alterazioni dello storico reale (Issue #35).

### 4.15 Modalità Demo (Simulatore Integrato Dual-Network)
* Simulazione realistica completa a zero configurazione, senza bisogno di credenziali eero.
* Due reti simulate:
  1. **Casa Rossi Mesh 6E:** Topologia a 3 nodi con gateway eero Pro 6E, nodi mesh wireless 6 GHz e dispositivi consumer.
  2. **Ufficio & Studio Pro Mesh:** Rete avanzata con gateway eero Max 7, porte 2.5/10 Gbps, nodi extender PoE e server locali (Proxmox, TrueNAS, switch gestiti).

### 4.16 Statistiche & Analytics di Rete, SLA ISP & Data Export Center (v1.5.0)
* **Nuova Vista UI Dedicata:** Scheda "Statistiche & Analytics" accessibile dalla sidebar principale, disegnata con linee guida Windows 11 Fluent e rigorosa assenza di emoji (iconografia SVG pura).
* **4 Card KPI di Sintesi Rete:**
  1. *Affidabilità Provider (SLA):* Indice percentuale (0-100%) calcolato ponderando la costanza delle velocità misurate rispetto alla banda massima contrattuale registrata e la presenza di test degradati (<70% del picco).
  2. *Velocità Media WAN:* Velocità media aggregata di Download e Upload registrata nei test storici.
  3. *Latenza & Jitter Medio:* Tempo medio di ping e varianza millisecondica (jitter) che misura la stabilità della linea internet.
  4. *Densità Dispositivi Mesh:* Rapporto medio client/nodo e conteggio apparati attivi rispetto alla capacità dell'infrastruttura.
* **Griglia 2x2 Grafici di Ripartizione Rete (Chart.js):**
  * *Distribuzione Frequenze:* Analisi a ciambella della ripartizione dei client tra 6 GHz (Wi-Fi 6E/7), 5 GHz, 2.4 GHz e connessioni fisiche Ethernet.
  * *Carico Nodi Mesh:* Grafico a barre orizzontali del numero di client associati a ciascun beacon eero.
  * *Categorie Dispositivi:* Suddivisione visiva dei client per tipologia d'uso.
  * *Top Produttori Hardware (OUI):* Fingerprinting dei dispositivi basato sui primi 3 ottetti del MAC address per riconoscere i vendor dominanti nella rete.
  * **Tooltip Interattivo con Elenco Dispositivi:** Hovering su qualsiasi elemento dei 4 grafici mostra nel tooltip scuro (sfondo `rgba(15, 23, 42, 0.96)`) l'elenco nominativo completo dei dispositivi che compongono quel dato, con intestazione `Dispositivi (N):`, voci puntate `•` e troncamento automatico a 15 con contatore overflow. Il nome visualizzato per ciascun client è risolto con precedenza: alias personalizzato → nickname → hostname → IP → MAC.
* **Trend Temporale & Monitoraggio SLA ISP:**
  * Grafico multilinea a doppio asse Y (Throughput WAN vs Ping) con periodo selezionabile (7 o 30 giorni).
  * Tabella KPI con picco download/upload, ping minimo e numero test condotti.
* **Centro Esportazione Dati Aperto (Data Export Center):**
  * Esportazione istantanea con 1 clic in formato CSV RFC 4180 o JSON formattato UTF-8 con header HTTP `Content-Disposition: attachment`.
  * 4 Dataset esportabili: `devices` (anagrafica e dettagli tecnici client), `speedtest` (storico WAN), `signal` (serie temporale RSSI dBm), `usage` (volumi dati consumati).

### 4.17 Telemetria Switching Hardware Layer 2 & Dispositivi Cablati (Issue #40 & #42)
* **Architettura Switching ASIC Hardware:** Nei router ed extender eero, le porte Ethernet LAN/WAN commutano i frame a livello Layer 2 (Data Link) direttamente nei circuiti ASIC hardware. La commutazione non passa attraverso il demone software per-client o la CPU locale.
* **Assenza di Contatori Realtime nel Kernel eero:** A differenza dei client Wi-Fi (dove il sottosistema wireless 802.11 traccia frame e byte per ciascuna associazione radio), il kernel Linux degli apparati eero non espone contatori di byte/secondo o throughput istantaneo per le interfacce cablate.
* **Chiarimento Abbonamento eero Plus:** Nemmeno con una sottoscrizione eero Plus attiva sono disponibili contatori in tempo reale per apparati cablati nelle API del router (le statistiche mostrate dall'app ufficiale eero derivano da aggregazioni periodiche asincrone a blocchi temporali su server cloud AWS). Tutti i disclaimer fuorvianti che richiedevano l'abbonamento Plus sono stati rimossi.
* **Rappresentazione Accurata nella UI:** La dashboard espone il valore trasparente `↓ — / ↑ — (Cablato)` (o `(Wired)` in inglese) e include tooltip e popover esplicativi sulla natura hardware della commutazione.

### 4.18 Community Hall of Fame & Crediti Open Source
* **Riconoscimento Contributi Community:** Nel modale *About & Crediti*, una sezione dedicata con badge *Hall of Fame* riconosce gli utenti di GitHub e Reddit che hanno fornito proposte di feature, issue e feedback tecnici:
  * `@jpatchMC`: Multi-DNS Sync UI, IPv6 SLAAC Pruning, telemetria Layer 2 (#16, #21, #23, #31, #36, #40, #42).
  * `@Hatton920`: Health Score Breakdown, velocità link PHY, stato nodi rebooting vs offline, sanitizzazione speedtest (#14, #15, #34, #35, #41).
  * `@jimcampbell100`: Multi-Network Fleet Management (#22).
  * `@stevehoek`: Switch multi-rete (#37) e localizzazione inglese Daily Digest (#38).
  * `@DannyFeliz`: Layout responsive mobile/tablet (#27, #28, #29, #46).
  * `@carbones73`: Telemetria rigorosa, accuratezza canali 5 GHz UNII-3 vs 6 GHz, isolamento sessioni live da demo, stabilizzazione drift simulatore ed elezione deterministica Primary Gateway (#47, #48, #49, #50, #51, #52, #53).
* **Tassonomia Giuridica Standard:** Per tutelare pienamente la paternità intellettuale, l'architettura e il copyright dell'applicazione in capo all'autore esclusivo (**Enrico Flammini**), tutti i collaboratori sono designati esclusivamente con lo status standard di **Contributor** e le sezioni intitolate **"Community Feature Proposals & Feedback"**, escludendo qualsiasi dicitura ("co-designer") suscettibile di fraintendimenti di titolarità.

---

## 5. Specifiche del Database SQLite (`metrics.db`)

Il database si trova in `data/metrics.db` (percorso configurabile via `DATA_DIR`). Viene aperto in modalità WAL (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`) per garantire massima concorrenza tra letture e scritture asincrone.

### Tabelle dello Schema

#### 1. `app_settings`
Memorizza impostazioni e preferenze dell'applicazione (DNS instances, canali di notifica, retention).
* `key` (TEXT PRIMARY KEY)
* `value` (TEXT)
* `updated_at` (DATETIME)

#### 2. `known_devices`
Registro dei MAC address noti per prevenire notifiche duplicate di "nuovo dispositivo".
* `mac_address` (TEXT PRIMARY KEY)
* `first_seen` (DATETIME)
* `last_seen` (DATETIME)
* `hostname` (TEXT)
* `ip` (TEXT)
* `is_guest` (BOOLEAN)
* `nickname` (TEXT)

#### 3. `speedtest_history`
Storico dei risultati dei test di velocità WAN eseguiti dal gateway eero.
* `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP)
* `download_mbps` (REAL)
* `upload_mbps` (REAL)
* `ping_ms` (REAL)
* `server_name` (TEXT)
* `source` (TEXT) — `eero_gateway` o `manual`

#### 4. `device_signal_history`
Campionamenti continui dei parametri radio Wi-Fi dei client connessi.
* `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP)
* `mac_address` (TEXT NOT NULL)
* `hostname` (TEXT)
* `ip` (TEXT)
* `signal_dbm` (INTEGER)
* `frequency_band` (TEXT) — `2.4 GHz`, `5 GHz`, `6 GHz`, `Ethernet`
* `channel` (INTEGER)
* `rx_rate_mbps` (REAL)
* `connected_node_name` (TEXT)
* `is_demo` (INTEGER DEFAULT 0)

#### 5. `device_usage_history` (v1.5.0)
Campionamento del volume dati e throughput per singolo client.
* `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP)
* `mac_address` (TEXT NOT NULL)
* `network_id` (TEXT NOT NULL)
* `rx_bytes` (REAL NOT NULL DEFAULT 0)
* `tx_bytes` (REAL NOT NULL DEFAULT 0)
* `download_mbps` (REAL NOT NULL DEFAULT 0)
* `upload_mbps` (REAL NOT NULL DEFAULT 0)
* `is_demo` (INTEGER DEFAULT 0)

*Indici:*
* `idx_device_usage_mac_time` (`mac_address`, `timestamp`)
* `idx_device_usage_net_time` (`network_id`, `timestamp`)
* `idx_device_usage_time` (`timestamp`)

---

## 6. Catalogo Completo API REST (Endpoint Reference)

Tutti gli endpoint rispondono in formato JSON con intestazione `application/json`.

| Metodo | Endpoint | Descrizione | Parametri / Payload |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/auth/status` | Stato autenticazione e modalità Demo/Live | Nessuno |
| **POST** | `/api/auth/login` | Avvia procedura 2FA eero inviando codice OTP | `{"identifier": "+39333..."}` |
| **POST** | `/api/auth/verify` | Verifica codice OTP e salva sessione permanente | `{"code": "123456", "user_token": "..."}` |
| **POST** | `/api/auth/mode` | Commuta tra Modalità Demo e Modalità Live | `{"demo": true/false}` |
| **POST** | `/api/auth/logout` | Disconnette la sessione cloud e ripulisce la cache | Nessuno |
| **GET** | `/api/network/list` | Elenco di tutte le reti dell'account e rete attiva (v1.5.0) | Nessuno |
| **POST** | `/api/network/switch` | Switch dinamico a caldo della rete attiva (v1.5.0) | `{"network_id": "..."}` |
| **GET** | `/api/network/overview` | Panoramica stato WAN, nodi mesh e Health Score | Nessuno |
| **GET** | `/api/network/top-hogs` | Classifica dispositivi con maggior consumo dati (v1.5.0) | `?period=daily|weekly|monthly&limit=5` |
| **GET** | `/api/network/health-breakdown` | Dettaglio diagnostico a 4 pilastri dell'Health Score | Nessuno |
| **POST** | `/api/network/refresh` | Forza re-polling immediato dai server eero Cloud | Nessuno |
| **POST** | `/api/network/reboot` | Riavvia l'intera rete mesh eero | Nessuno |
| **POST** | `/api/network/eeros/{serial}/reboot` | Riavvia un singolo nodo mesh specifico | Nessuno |
| **GET** | `/api/devices` | Elenco completo di tutti i dispositivi client connessi/noti | Nessuno |
| **GET** | `/api/devices/{mac}/usage` | Storico consumo dati per dispositivo (v1.5.0) | `?period=daily|weekly|monthly` |
| **GET** | `/api/devices/{mac}/rules` | Prenotazioni DHCP e regole di port forwarding del client | Nessuno |
| **POST** | `/api/devices/{mac}/rules/reservation` | Crea o aggiorna prenotazione IP statico sul cloud eero | `{"ip": "192.168.4.50"}` |
| **DELETE** | `/api/devices/{mac}/rules/reservation` | Rimuove prenotazione IP statico dal cloud eero | Nessuno |
| **POST** | `/api/devices/{mac}/rules/forward` | Crea regola di port forwarding per il dispositivo | `{"port_from": 80, "port_to": 80, "protocol": "tcp", "description": "Web"}` |
| **DELETE** | `/api/devices/{mac}/rules/forward/{rule_id}` | Elimina una specifica regola di inoltro porte | Nessuno |
| **POST** | `/api/devices/metadata` | Salva metadati locali (nome personalizzato, categoria, note, ⭐) | `{"mac": "...", "custom_name": "...", ...}` |
| **GET** | `/api/devices/export/hosts` | Esporta lista host in formato standard `/etc/hosts` | `?domain_suffix=lan` |
| **GET** | `/api/devices/export/adguard` | Esporta lista client in formato REST per AdGuard Home | `?include_ipv6=true/false` |
| **GET** | `/api/automations/dns` | Elenco istanze Multi-Engine DNS e stato sincronizzazione | Nessuno |
| **POST** | `/api/automations/dns` | Salva configurazione istanze DNS (AdGuard, Pi-hole, Technitium) | `{"enabled": true, "instances": [...]}` |
| **POST** | `/api/automations/dns/test` | Esegue test di connettività verso istanza/e DNS | Opzionale `{"instance_id": "..."}` |
| **POST** | `/api/automations/dns/sync` | Avvia sincronizzazione massiva immediata dei client | Opzionale `{"instance_id": "..."}` |
| **GET** | `/api/automations/gaming` | Stato modalità a bassa latenza (Gaming Mode) | Nessuno |
| **POST** | `/api/automations/gaming/toggle` | Attiva o disattiva la Gaming Mode | `{"enabled": true/false}` |
| **GET** | `/api/automations/guest` | Dati e stato rete Wi-Fi Ospiti e QR Code | Nessuno |
| **POST** | `/api/automations/guest` | Aggiorna configurazione rete ospiti (SSID, password, abilitazione) | `{"enabled": true, "name": "...", "password": "..."}` |
| **POST** | `/api/automations/notifications/test` | Invia notifica di test su Telegram o Webhook | Nessuno |
| **GET** | `/api/metrics/speedtest` | Storico misurazioni speed test e statistiche aggregate | Nessuno |
| **POST** | `/api/metrics/speedtest/run` | Avvia un nuovo test di velocità sul gateway eero | Nessuno |
| **GET** | `/api/metrics/signal/overview` | Panoramica potenza segnale Wi-Fi e Watchlist deboli | Nessuno |
| **GET** | `/api/metrics/signal/history` | Storico temporale potenza RSSI per un client | `?mac_address=...&hours=24` |
| **GET** | `/api/system/update/check` | Verifica disponibilità aggiornamenti Docker/GitHub | `?force=true` |
| **POST** | `/api/system/update/trigger` | Avvia aggiornamento automatico 1-clic del container | Nessuno |
| **GET** | `/api/analytics/distribution` | Distribuzione frequenze Wi-Fi, carico nodi mesh, categorie e vendor OUI con campo `devices: [...]` per ciascuna categoria (v1.5.0) | Nessuno |
| **GET** | `/api/analytics/isp-sla` | Trend temporale e indice SLA affidabilità provider internet (v1.5.0) | `?days=7|30` |
| **GET** | `/api/analytics/export/{data_type}` | Esportazione dataset (devices, speedtest, signal, usage) in formato CSV o JSON (v1.5.0) | `?format=csv|json&limit=500` |
| **GET** | `/api/manual/chapters` | Elenco capitoli e argomenti del manuale integrato | `?lang=it|en` |
| **GET** | `/api/manual/chapter/{id}` | Contenuto HTML formattato di un capitolo del manuale | `?lang=it|en` |
| **GET** | `/api/manual/changelog` | Restituisce il sommario formattato del changelog e release notes (v1.5.0) | `?lang=it|en` |
| **GET** | `/api/system/language` | Restituisce la preferenza di lingua attiva e persistita su SQLite (v1.5.0) | Nessuno |
| **POST** | `/api/system/language` | Salva e sincronizza la lingua di sistema per dashboard e digest (v1.5.0) | `{"language": "en"\|"it"}` |

---

## 7. Variabili d'Ambiente & Configurazione (`.env`)

| Variabile | Valore Predefinito | Descrizione |
| :--- | :--- | :--- |
| `DATA_DIR` | `./data` | Percorso locale del volume persistente per sessioni e database |
| `POLL_INTERVAL` | `10` | Intervallo di campionamento e polling verso eero Cloud (secondi) |
| `HISTORY_RETENTION_DAYS` | `30` | Giorni di mantenimento storico campionamenti segnale e speedtest |
| `SPEEDTEST_INTERVAL_HOURS` | `12` | Frequenza test di velocità pianificati automatici (ore) |
| `DEMO_MODE` | `false` | Se `true`, forza l'avvio in modalità simulazione |
| `EERO_USER_TOKEN` | `""` | Token permanente per bypassare il login interattivo 2FA |
| `EERO_NETWORK_ID` | `""` | ID opzionale della rete preferita da avviare come attiva |
| `TELEGRAM_BOT_TOKEN` | `""` | Token API Telegram per invio allarmi e digest |
| `TELEGRAM_CHAT_ID` | `""` | ID numerico chat/canale Telegram destinatario delle notifiche |
| `WEBHOOK_URL` | `""` | Endpoint HTTP POST per eventi JSON verso Home Assistant / script |
| `DOCKER_SOCKET_PATH` | `/var/run/docker.sock` | Percorso socket Docker per consentire l'auto-update in-app |
| `WATCHTOWER_URL` | `""` | URL opzionale webhook Watchtower per triggerare il pull dell'immagine |
| `UPDATE_CHECK_INTERVAL_HOURS`| `6` | Frequenza controllo nuove versioni su Docker Hub (ore) |
| `DASHBOARD_LANG` | `"en"` | Lingua predefinita della dashboard e delle notifiche Telegram (`"en"` o `"it"`) |

---

## 8. Storico Bug Risolti, Cause Radice (RCA) & Issue di Riferimento

Questa sezione documenta le cause radice dei bug riscontrati durante lo sviluppo e la relativa soluzione architetturale.

### Issue #38 — Telegram Daily Digest & Controls Tab Localization
* **Sintomo:** Il report giornaliero inviato su Telegram (Daily Digest) risultava sempre in italiano anche quando l'interfaccia utente era impostata in inglese (`currentLanguage: 'en'`). Inoltre, nella scheda *Controlli & QR Ospiti* erano presenti testi fissi in italiano (descrizione notifiche Telegram, card *Aggiornamenti Container & Manutenzione Docker*, e dettagli di stato del DNS Synchronizer).
* **Causa Radice:** In `NotificationService` i messaggi formattati per Telegram (`notify_digest`, `notify_new_device`, `notify_node_offline`) erano scritti direttamente in italiano senza supporto multilingua e il backend non disponeva di alcuna sincronizzazione o persistenza della lingua selezionata dal client. Nell'HTML, vari elementi della scheda Controlli non utilizzavano i binding reattivi `x-text="t(...)"`.
* **Risoluzione:**
  * Implementati gli endpoint `GET /api/system/language` e `POST /api/system/language` e salvataggio della chiave `system_language` in SQLite (`metrics.db`).
  * In `app.js`, `setLanguage()` propaga la lingua selezionata al backend, sincronizzando automaticamente le schedulazioni notturne del digest (ore 21:00).
  * `NotificationService` adatta dinamicamente testi e titoli in inglese o italiano in base alla lingua salvata (o al parametro opzionale `language` passato via API).
  * Aggiunte le chiavi mancanti in `it.json` ed `en.json` (`controls.notifications_desc`, `controls.docker_*`, `controls.dns_*`) e aggiornati i tag in `index.html`.

### Issue #22 — Multi-Network Fleet Management
* **Sintomo:** Utenti con più reti mesh eero sul proprio account (es. casa e ufficio) non potevano visualizzare né gestire la seconda rete; la dashboard restava vincolata a `networks[0]`.
* **Causa Radice:** In `fetch_account_info()` la rete veniva forzata indiscriminatamente a `networks[0]`, sovrascrivendo qualsiasi selezione precedente ad ogni ciclo di polling.
* **Risoluzione:** Introdotto l'attributo `available_networks`, l'endpoint REST `/api/network/switch` e la logica di conservazione di `current_network_id` in sessione persistente.

### Issue #31 & Issue #30 — SLAAC IPv6 Accumulation & Stale Lease Pruning in AdGuard
* **Sintomo:** La sincronizzazione automatica verso AdGuard Home accumulava centinaia di indirizzi IPv6 SLAAC obsoleti e vecchi lease DHCP per lo stesso client MAC, rendendo illeggibile la lista client.
* **Causa Radice:** Il merge non distingueva tra indirizzi IP effettivi e alias host, e univa indistintamente tutti gli IP storici presenti su AdGuard con quelli in arrivo da eero.
* **Risoluzione:** Ispezione deterministica tramite `ipaddress`. Gli identificatori non-IP (MAC, CIDR, domini personalizzati come `custom-alias.lan`) vengono sempre conservati. Gli indirizzi IPv6 SLAAC scaduti non più presenti nella telemetria attiva di eero vengono potati chirurgicamente. Aggiunta opzione per escludere totalmente gli IPv6 (`drop_ipv6`).

### Issue #26 — Incorrect Primary Gateway Listed with PoE Extenders
* **Sintomo:** Nodi extender secondari alimentati tramite iniettore PoE (es. eero Outdoor 7) venivano etichettati erroneamente come `PRIMARY GATEWAY (WAN)` anziché il router principale (eero Max 7 su porta 10G).
* **Causa Radice:** L'algoritmo di normalizzazione si affidava al primo nodo dell'elenco o alla presenza di un link cablato, senza verificare se la porta Ethernet fosse configurata come WAN verso l'ISP.
* **Risoluzione:** Correlazione autoritativa con l'endpoint `/2.2/networks/{id}` (`gateway_eero_id`), ispezione dell'IP gateway della subnet (es. `192.168.4.1`) e verifica esplicita del ruolo della porta (`isWanPort: true`, `role: wan`). Demotion automatica degli extender PoE a backhaul wireless.

### Issue #34 — Mesh Offline Node Detection & Reboot Differentiation
* **Sintomo:** Nodi mesh disconnessi non venivano rilevati come offline e la notifica `node_offline` non partiva.
* **Causa Radice:** L'uso di un fallback errato `node.get("connected", True)` in `_normalize_eero_node()`, dato che l'API REST `/eeros` non espone una proprietà `connected`.
* **Risoluzione:** Ispezione gerarchica di `heartbeat_ok`, `status` (`green`, `yellow`, `red`) e `state` (`ONLINE`, `REBOOTING`, `OFFLINE`). Distinzione esplicita dei nodi in fase di riavvio (`rebooting`) per evitare falsi allarmi durante manutenzione.

### Issue #35 — Mock Speedtest Data Leakage & SQLite Lock on Startup
* **Sintomo:** All'avvio del container appariva l'errore `OperationalError: database is locked` e nello storico dei test di velocità comparivano misurazioni fittizie TIM FTTH (`912.45 Mbps / 298.10 Mbps`).
* **Causa Radice:** Durante l'inizializzazione dello schema, `purge_all_mock_data()` apriva una seconda connessione concorrente a SQLite mentre la transazione di `init_db()` era ancora aperta. Inoltre, i metodi di fallback su errore API autenticata ritornavano dati mock invece di generare eccezioni o riutilizzare l'ultimo stato noto.
* **Risoluzione:** `purge_all_mock_data(conn=db)` riutilizza ora la connessione attiva all'interno della stessa transazione atomica. Rimozione di qualsiasi fallback a dati fittizi in ambiente live autenticato.

### Issue #36 — Incorrect Primary Gateway in Multi-Ethernet Switched Topologies
* **Sintomo:** In reti con più nodi eero secondari connessi a switch gigabit (es. nodo "Office" con link a 1 Gbps), la dashboard etichettava erroneamente "Office" come Primary Gateway al posto del vero router principale "Family Room" (`192.168.4.1`).
* **Causa Radice:** Nelle porte auto-sensing eero con switch upstream, i metadati locali delle porte possono includere stringhe `Port 1 (WAN)` o `has_wan_port`. La precedente logica di fallback considerava la presenza di porte WAN fisiche con precedenza superiore rispetto all'IP autoritativo di subnet (`gateway_ip = 192.168.4.1`) e al nome autoritativo registrato (`gateway_name = "Family Room"`).
* **Risoluzione:** Riorganizzata la gerarchia di elezione in `get_eeros()` per dare precedenza assoluta ai metadati di rete eero Cloud (`current_gateway_id`, `current_gateway_name`, `current_gateway_ip = 192.168.4.1`). I nodi secondari cablati via switch vengono correttamente demotati ed etichettati come `Ethernet (1.0 Gbps)` o `Ethernet (Cablato)`.

### Issue #40 & Issue #42 — Telemetria Switching Hardware Layer 2 & Disclaimer eero Plus
* **Sintomo:** Utenti con abbonamento eero Plus attivo (`jpatchMC`) riscontravano la dicitura `↓ — / ↑ — (Wired)` sui dispositivi collegati via cavo Ethernet e chiedevano perché venisse mostrato il trattino o se fosse richiesto un abbonamento aggiuntivo.
* **Causa Radice:** Nelle porte Ethernet degli apparati eero la commutazione avviene tramite switch ASIC hardware a livello Layer 2; il kernel Linux del router non emette stream di contatori pacchetti/byte software per le porte cablate. Nella UI precedente, un disclaimer informativo suggeriva erroneamente che l'abbonamento eero Plus potesse abilitare la telemetria cablata in tempo reale.
* **Risoluzione:** Rimossa la dicitura fuorviante su eero Plus in `it.json`, `en.json` e `index.html`. Aggiornato il tooltip contestuale e il popover di trasparenza dati, spiegando tecnicamente la commutazione hardware Layer 2. Localizzati i badge in `(Cablato)` o `(Wired)` a seconda della lingua attiva.

### Issue #41 — Collisione Nodi Mesh a Sottostringa & Localizzazione Vendor/Categorie in Analytics
* **Sintomo:** Nel grafico *Carico per Nodo Mesh* della sezione Analytics, quando due nodi avevano nomi correlati da sottostringa (es. "Bedroom" e "Issac Bedroom"), tutti i dispositivi venivano attribuiti a "Bedroom", azzerando il conteggio client di "Issac Bedroom". Inoltre, la stringa "Altro" appariva hardcoded in italiano anche impostando la dashboard in lingua inglese (`Hatton920`).
* **Causa Radice:** In `analytics.py` il matching tra nome nodo e dispositivo utilizzava l'operatore di contenimento `in` anziché l'uguaglianza rigorosa. Nelle funzioni di charting in `app.js`, la stringa `'Altro'` era fissata senza passare dal resolver di localizzazione.
* **Risoluzione:** Introdotto algoritmo deterministico a più livelli in `analytics.py` (priorità assoluta a `node_id`, poi URL cloud univoco, seriale hardware e infine uguaglianza esatta `==` normalizzata). Introdotte in `app.js` le funzioni di formattazione reattive `formatCategoryName` e `formatVendorName` con fallback `'Other'` in inglese e `'Altro'` in italiano.

### CI/CD & Docker Hub Release Isolation (Protezione Tag `latest`)
* **Sintomo:** Il push di commit sui rami secondari di test (`test`, `dev`) causava l'aggiornamento automatico del puntatore `:latest` su Docker Hub, distribuendo immagini pre-rilascio instabili agli utenti di produzione (`u/djbills` su Reddit).
* **Causa Radice:** L'action GitHub `docker/metadata-action` generava implicitamente la regola `latest=auto`, applicandola ai rami di sviluppo.
* **Risoluzione:** Aggiunto `flavor: | latest=false` in `.github/workflows/docker-publish.yml`, garantendo che solo i tag semantici espliciti di release approvata possano aggiornare il puntatore `:latest` di produzione.

### Note Tecniche — Tooltip Interattivo Grafici Analytics (v1.5.0)
* **Contesto:** I grafici di distribuzione di rete (frequenze, carico nodi, categorie, vendor) non mostravano il dettaglio dei dispositivi singoli al passaggio del mouse.
* **Soluzione Backend:** L'endpoint `GET /api/analytics/distribution` ora include il campo `"devices": [...]` per ogni categoria/segmento. Il nome di ogni client viene risolto tramite `_get_device_display_name(dev)` con precedenza: alias personalizzato (`custom_name`) → nickname (`nickname`) → hostname → IP → MAC address.
* **Soluzione Frontend:** La funzione `formatDevicesTooltipAfterBody(devicesList)` formatta la lista come array di stringhe restituite da `callbacks.afterBody` di Chart.js. Il tooltip è configurato con `backgroundColor: 'rgba(15, 23, 42, 0.96)'` e marcato con il flag privato `_customDark: true`. La funzione `updateAllChartsTheme()` controlla questo flag prima di sovrascrivere il colore di sfondo, preservando il tooltip scuro in tutti i temi UI.
* **Troncamento:** La lista viene mostrata per intero fino a 15 dispositivi; oltre tale soglia viene aggiunta la riga `... e altri X` (o `... and X more` in inglese) per mantenere il tooltip compatto.

### PR #47 a #53 — Telemetria Rigorosa, Radiofrequenza & Stabilità Nodi (@carbones73)
* **PR #47 (Isolamento Sessioni Live):** In `get_devices()`, se l'ID rete non è ancora risolto (`not current_network_id`) in una sessione reale autenticata, restituisce `[]` anziché i 10 dispositivi demo, prevenendo allarmi fantasma e sincronizzazioni DNS fittizie.
* **PR #48 (Bonifica Speedtest Fittizio):** In `_normalize_network_details()`, rimossi i valori inventati hardcoded (`951.0` Mbps down, `193.0` Mbps up, `9.0` ms ping e `now()`) su reti che non hanno mai condotto test di velocità WAN, azzerando le misurazioni e preservando l'integrità dello storico SQLite e dello speedtest cloud interattivo.
* **PR #49 (Elezione Gateway Deterministica per Segmento URL):** In `get_eeros()` e `_is_gateway_node()`, la condizione di matching per l'ID gateway confronta l'ultimo segmento di percorso dell'URL (`str(url).rstrip('/').split('/')[-1] == str(gw_id)`), eliminando collisioni da sottostringa (es. ID `10` vs `104`/`210`).
* **PR #50 (Spettro RF 5 GHz UNII-3 vs 6 GHz & Disaccoppiamento Wi-Fi 7 EHT):** La banda 5 GHz UNII-3 opera su canali dispari (149, 153, 157, 161, 165); la logica radio limita i canali dispari per 6 GHz a `15 <= channel < 149` e classifica esplicitamente come 5 GHz `36 <= channel <= 177 and (channel % 2 == 0 or channel >= 149)`. Rimosso `phy_type == "EHT"` come indicatore esclusivo di 6 GHz, poiché il Wi-Fi 7 opera anche a 5 GHz e 2.4 GHz.
* **PR #51 (Risoluzione Network ID Regole & Prenotazioni):** Sostituita l'invocazione del metodo inesistente `_resolve_network_id()` con `fetch_account_info()` in `get_forwards_and_reservations()` e aggiunta protezione preventiva contro chiamate verso `/networks/None`.
* **PR #52 (Eliminazione Segnale Fittizio -55 dBm):** In `_normalize_device()`, se la telemetria cloud eero non riporta il segnale RSSI, `signal_rssi` rimane `None` senza inventare `-55 dBm`, ripulendo la Weak Signal Watchlist e l'Health Score.
* **PR #53 (Stabilizzazione Drift Tassi Demo Mode):** In `_get_demo_devices()`, il throughput simulato viene variato attorno a valori base fissi memorizzati (`_demo_base_rates`) anziché moltiplicare a cascata il valore del ciclo precedente, eliminando il moto browniano con drift positivo esponenziale.

---

## 9. Guida al Troubleshooting & FAQ per l'Utente

### D: Lo Speed Test viene eseguito dal container Docker o dal router eero?
R: **Viene eseguito al 100% dal router Gateway eero hardware.** Il container Docker non installa né esegue software o librerie locali di benchmarking (come `speedtest-cli` o `iperf`), che sarebbero limitate dalla scheda di rete del server host o dal virtual bridge Docker. Quando l'utente preme *"Esegui Speed Test"*, la dashboard invia una richiesta REST protetta da token all'infrastruttura cloud di Amazon (`POST /2.2/networks/{id}/speedtest`), ordinando al microprocessore dell'apparato eero di effettuare il test direttamente sulla sua porta WAN connessa all'ONT/modem verso i server speedtest eero. La dashboard si limita a interrogare i risultati certificati calcolati dal router.

### D: Perché un telefono uscito di casa non compare più nella "Weak Signal Watchlist"?
R: Nelle versioni precedenti, quando un utente usciva di casa con lo smartphone, l'ultimo segnale registrato prima dello sgancio (es. -89 dBm sul cancello) restava memorizzato per 6 ore come segnale critico. Dalla versione 1.5.0, il sistema implementa la **Bonifica dei Transitori di Uscita** (*Exit Transient Pruning*): non appena il poller rileva la disconnessione (`connected: True -> False`), elimina automaticamente gli ultimi campioni deboli registrati negli ultimi 5 minuti prima dell'uscita, e filtra l'elenco escludendo i client non attivi.

### D: Come posso far ripartire il container se perdo la connessione o il token scade?
R: È sufficiente accedere all'interfaccia web: se il token è scaduto, la dashboard mostra automaticamente la schermata di login 2FA. In alternativa, è possibile eliminare il file `data/session.json` e riavviare il container per iniziare un'autenticazione pulita.

### D: Il selettore di rete nell'header non compare. Perché?
R: Il menu a tendina nell'header per il Multi-Network compare solo se l'account eero autenticato possiede **2 o più reti** configurate. Se l'account gestisce un'unica rete mesh, la dashboard mostra direttamente il nome della rete senza ingombro visivo. In modalità Demo, sono sempre presenti 2 reti per poter testare il componente.

### D: Perché su AdGuard Home vedo sparire gli indirizzi IPv6 SLAAC dopo la sincronizzazione?
R: Questa è una funzionalità introdotta nella v1.5.0 (Issue #31). I dispositivi mobili e i moderni sistemi operativi generano indirizzi IPv6 temporanei casuali (SLAAC Privacy Extensions) che scadono continuamente. La dashboard rimuove automaticamente gli indirizzi non più utilizzati, mantenendo la tabella client ordinata. Se desideri conservare tutti gli IP o disattivare questa funzione, puoi deselezionare il flag *"Pruning Intelligente IP"* nella configurazione dell'istanza DNS.

### D: Come configuro l'aggiornamento automatico Docker in-app a 1-clic?
R: Nel file `docker-compose.yml`, assicurati di aver montato il socket di Docker:
```yaml
volumes:
  - ./data:/app/data
  - /var/run/docker.sock:/var/run/docker.sock:ro
```
Quando la dashboard rileva una nuova release su Docker Hub, apparirà un badge pulsante nell'header. Cliccando su *"Aggiorna Ora"*, il container invocherà le API di Docker per scaricare l'immagine aggiornata e ricreare il container senza perdita di configurazione.

### D: Come esportare i dati per Home Assistant o Prometheus?
R: La dashboard espone endpoint REST pronti all'uso:
* `GET /api/network/overview`: Metriche aggregate, stato WAN e nodi.
* `GET /api/devices`: Array JSON di tutti i client con IP, MAC, nodo collegato, banda e potenza RSSI.
* `GET /api/network/top-hogs`: Statistiche di consumo dati in formato JSON.
* I webhook automatici trasmettono payload completi con eventi `new_device`, `node_offline` e `daily_digest` contenente il campo `line_stability`.

### D: Perché per i dispositivi connessi via cavo Ethernet vedo "↓ — / ↑ — (Cablato)" e non il consumo in tempo reale?
R: Le porte Ethernet degli apparati eero funzionano come un normale switch hardware Layer 2: il traffico viaggia direttamente tra i circuiti integrati della porta fisica senza essere analizzato pacchetto per pacchetto dal sistema operativo Linux del router. Pertanto, il kernel eero non espone contatori di byte/secondo per apparati cablati nelle sue API (nemmeno per chi possiede l'abbonamento eero Plus). La dashboard adotta quindi il valore neutro `↓ — / ↑ — (Cablato)` per trasparenza tecnica e rigore scientifico, evitando di mostrare stime fittizie.

### D: Perché nel grafico "Carico Nodi Mesh" alcuni nodi con nomi simili mostravano 0 dispositivi?
R: Nelle versioni precedenti, il motore di matching utilizzava una ricerca per sottostringa. Se due nodi avevano nomi correlati (es. "Bedroom" e "Issac Bedroom"), i dispositivi venivano raggruppati sul primo nodo trovato. Dalla versione 1.5.0 (Issue #41), il matching è rigoroso ed esatto basandosi su ID univoco cloud, seriale hardware e uguaglianza esatta dei nomi.
