# Changelog - eero Custom Dashboard & Management Suite

Tutte le modifiche rilevanti, i miglioramenti e le correzioni di bug apportate al progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) e aderisce al versionamento semantico.

---

## [1.03.00] - 2026-08-28

### 📦 Docker Hub Multi-Arch, Sincronizzazione AdGuard Home & Ottimizzazioni Mesh (#12)
* **📡 Risoluzione Universale Nodi e Client Mesh (Issue #12):**
  * Introdotto motore di indicizzazione multi-chiave in `poller.py` e `eero_client.py` (`id` numerico, `serial`, `url`, `location`/nome, `ip`) per garantire il matching affidabile dei client connessi su tutte le generazioni eero (eero Pro 7, Pro 6E, eero 6+, Max 7) e versioni eeroOS 7.x.
  * Risolto il bug per cui i dispositivi su nodi beacon potevano risultare tutti associati al Gateway in presenza di payload cloud privi del campo `location`.
* **✨ Switch Istantaneo Modalità Demo / Rete Live (senza perdita di Token):**
  * Aggiunto pulsante interattivo nella barra superiore per passare istantaneamente alla **Modalità Demo** a scopo di test/anteprima e ritornare alla **Rete Live** preservando sempre il token di sessione autenticato senza dover reinserire l'OTP.
* **🌡️ Armonizzazione Stato Termico Nodi:**
  * Ottimizzato il rendering dello stato termico e operativo dei nodi mesh, riflettendo accuratamente lo stato di salute reale fornito dalle API ufficiali eero (`thermal_status`: Normale / Nominale).
* **⚡ Velocità Negoziata Ethernet Dispositivi & Backhaul Mesh:**
  * Rimosso il testo fisso `'GbE 1.0 Gbps'`. Ora il sistema rileva e mostra dinamicamente la reale velocità di link per apparati cablati a **10 Gbps**, **5.0 Gbps**, **2.5 Gbps**, **1.0 Gbps** e **100 Mbps**.
  * Ispezione automatica delle porte ethernet fisiche (`ports`/`ethernet_ports`) dei nodi eero per rilevare e mostrare la velocità di backhaul cablato.
* **👤 Selettore Profilo Utente nel Dettaglio Dispositivo:**
  * Aggiunto menu a tendina nel modale dettaglio client per assegnare, modificare o rimuovere un dispositivo dal rispettivo profilo utente Cloud eero direttamente dalla Dashboard.
* **📶 Telemetria Segnale RSSI (dBm) & PHY Link Rate nel Modale:**
  * Integrata la visualizzazione avanzata della qualità del segnale in dBm e della velocità di modulazione PHY nel riquadro di connessione del modale.
* **🌍 Rimozione Residui di Testo e Localizzazione Completa:**
  * Localizzati integralmente in inglese e italiano tutti i messaggi di verifica conflitti IP statici, avvisi e notifiche Toast.
* **Distribuzione Ufficiale Docker Hub Multi-Arch:**
  * Configurato workflow GitHub Actions per la compilazione e il push automatico su Docker Hub (`enricoflammini/eero-dashboard`).
  * Supporto nativo alle architetture `linux/amd64` (Server x86, PC, VM) e `linux/arm64` (Raspberry Pi 4/5, NAS Synology/QNAP/TrueNAS, Apple Silicon).
  * Avvio immediato a riga di comando senza compilazione locale tramite `docker run` o `docker compose pull`.
* **Integrazione Nativa AdGuard Home in-App:**
  * Nuova scheda visuale dedicata nel tab **Automazioni & Controlli** per configurare la connessione verso AdGuard Home (URL, Username, Password).
  * Normalizzazione automatica degli URL locali (pulizia frammenti `#`, supporto HTTP e fallback SSL/TLS per certificati self-signed).
  * Pulsante **"Test Connessione"** con riscontro immediato via Toast e verifica delle credenziali.
  * Pulsante **"Sincronizza Ora Tutti i Client"** con matching intelligente per nome, MAC e IP (`/control/clients/add` e `/control/clients/update`).
  * Toggle **"Abilita sincronizzazione automatica continua"** per sincronizzare silenziosamente in background all'accesso di nuovi dispositivi e su base periodica.
* **🔒 Pulsante Disconnessione con Modale di Sicurezza:**
  * Ripristinato il pulsante di logout nella barra superiore accanto alla guida rapida.
  * Introdotto un modale di conferma Glassmorphism con avviso esplicito sulla necessità di richiedere un nuovo codice 2FA OTP al successivo accesso.
* **📊 Fix & Arricchimento Daily Digest Telegram:**
  * Risolto l'errore di generazione del report giornaliero delle 21:00 (e manuale da interfaccia) causato da riferimenti a tabelle storiche obsolete.
  * Il report inviato su Telegram e via Webhook include ora dati reali certificati: Health Score, ISP, nodi mesh online, client attivi totali, suddivisione dettagliata per frequenza (6GHz, 5GHz, 2.4GHz, Cablati), Speed Test Gateway e Latenza Ping.
  * Introdotto un toggle esplicito *"Abilita invio automatico programmato (ore 21:00)"* per consentire all'utente di disattivare la schedulazione del digest mantenendo disponibile l'invio istantaneo on-demand.
* **🎛️ Riorganizzazione Scheda Automazioni & Toggle Notifiche Telegram:**
  * Layout del tab **Controlli & QR Ospiti** riorganizzato a matrice 2x2: *Guest Wi-Fi* (alto-sx), *Integrazione AdGuard Home* (alto-dx), *Notifiche Telegram & Webhook* (basso-sx) e *Report Digest Giornaliero* (basso-dx).
  * Introdotto un toggle esplicito *"Abilita invio notifiche su Telegram"* per attivare/disattivare rapidamente gli avvisi automatici senza cancellare token o chat ID salvati.
* **🛡️ Registro Persistente Dispositivi Noti (Zero Notifiche Duplicate al Riavvio):**
  * Creata la tabella SQLite `known_devices` per memorizzare in modo permanente gli indirizzi MAC e lo stato di notifica dei client di rete.
  * Al riavvio o all'aggiornamento del server/container, il poller carica l'elenco completo dal database, evitando l'invio ripetuto di notifiche Telegram per apparati già noti.
* **📖 Rendering Ottimizzato del Manuale Utente & Changelog In-App Bilingue:**
  * Riscritto il parser Markdown interno (`renderSimpleMarkdown`) con supporto completo a liste numerate ordinate (`<ol>`), sottoelenchi puntati indentati (`<ul>`), collegamenti ipertestuali e formattazione dei paragrafi.
  * Il visualizzatore del Changelog interno all'app è ora bilingue (Italiano e Inglese) e presenta un sommario essenziale dei soli titoli principali delle release, con link diretto per consultare il registro completo su GitHub.
* **❤️ Modale About, Dedica & Informazioni Open Source:**
  * Aggiunto pulsante dedicato *"About"* nella barra superiore accanto al badge di versione.
  * Include dedica alla community homelab & self-hosted (*Crafted with ❤️ by Enrico Flammini*), collegamenti rapidi a repository GitHub (codice e issues), licenza MIT, immagine Docker Hub e sezione Fun Notes.
* **🔀 Ordinamento Dispositivi & Barra dei Titoli Bloccata (Sticky Header):**
  * Introdotta la possibilità di ordinare la tabella dei dispositivi cliccando direttamente su ciascuna intestazione di colonna (Dispositivo/Host, Indirizzo IP numerico IPv4, Profilo, Nodo Mesh, Banda, Segnale RSSI e Stato).
  * La barra dei titoli della tabella rimane ora bloccata in alto (`sticky`) durante lo scorrimento, garantendo visibilità e orientamento costante anche con centinaia di client connessi.
* **⚙️ Normalizzazione Dinamica Dispositivi & Gestione Flessibile Nodi/Sensori:**
  * Risolto il bug di parsing dei dispositivi che poteva impedire la visualizzazione dei client connessi con determinati payload eero Cloud.
  * Reso pienamente dinamico il rendering dei client e dei conteggi (1, 2, N client o stato vuoto dedicato) con fallback automatico tra endpoint `/devices` e dettagli di rete.
  * I campi e i sensori hardware (es. backhaul su gateway standalone, temperature o firmware) vengono ora mostrati solo se effettivamente disponibili sulla versione hardware in uso.
  * Revisionate e completate al 100% tutte le etichette, placeholder e notifiche Toast in lingua inglese e italiana.
* **Esportazione DNS & Webhooks:**
  * Endpoint `GET /api/devices/export/hosts` (standard `/etc/hosts` / `dnsmasq`) e `GET /api/devices/export/adguard` (JSON provisioning).
  * Script standalone CLI [`scripts/adguard_sync.py`](scripts/adguard_sync.py).
  * Specifiche formali e schemi JSON dei payload Webhook nel `README.md`.

---

## [1.02.00] - 2026-08-26

### 📡 Telemetria Frequenze Wi-Fi (2.4/5/6GHz) & Integrazione Utenti Cloud eero
* **Badge Frequenze di Banda & Canale Wi-Fi:** Visualizzazione esplicita della frequenza per ciascun dispositivo nella tabella principale (**6 GHz**, **5 GHz**, **2.4 GHz**, **Cablato Ethernet**) con badge colorati distintivi (Sky Blue `6 GHz`, Indigo `5 GHz`, Amber `2.4 GHz`, Emerald `Ethernet`) ed etichetta canale wireless (`CH 11`, `CH 36`, ecc.).
* **Integrazione Utente / Profilo Cloud eero nei Dispositivi:** Ciascun client mostra la colonna *Profilo / Utente* con badge `👤 [Nome Profilo]`, sincronizzata in tempo reale con i profili configurati nell'App eero ufficiale.
* **Filtri Multi-Criterio Avanzati:**
  * Filtro rapido a tendina per frequenza di banda (*Tutte le Frequenze, 6 GHz, 5 GHz, 2.4 GHz, Cablato*).
  * Filtro per profilo utente (*Tutti i Profili / Non Assegnati / Profilo Specifico*).
  * Filtro per nodo mesh di attestazione (*Gateway / Beacon*).
  * Filtro per tipo di indirizzo IP (*Tutti gli Assegnamenti / Solo IP Statici / Solo IP DHCP*).
* **Ottimizzazione Modale Dettaglio Dispositivo:** Interfaccia snella e focalizzata sulla modifica di Nome Personalizzato, Categoria, Note locali, Assegnazione IP Statico permanente e Regole di Port Forwarding.

---

## [1.01.00] - 2026-08-26

### 🌍 Supporto Multilingua (i18n) & Rilascio Open Source
* **Supporto Internazionale Completo (Italiano & Inglese):** Aggiunta l'architettura di localizzazione dinamica con dizionari JSON dedicati (`it.json` e `en.json`) e helper reattivo `t(key)`.
* **Selettore Lingua nell'Header:** Aggiunto il menu a tendina 🇮🇹 IT / 🇬🇧 EN nella barra superiore per cambiare istantaneamente la lingua dell'intera dashboard senza ricaricare la pagina.
* **Persistenza & Rilevamento Automatico:** Il sistema rileva automaticamente la lingua del browser dell'utente e memorizza la preferenza selezionata in `localStorage`.
* **Standard Open Source GitHub:** Aggiunto file `LICENSE` (licenza MIT), rafforzato `.gitignore` per prevenire il leak accidentale di credenziali o database e documentazione pronta per la community.

---

## [1.00.08] - 2026-08-26

### ⚡ Sincronizzazione Totale Speed Test & Analisi Prestazioni
* **Congruenza Matematica Assoluta:** Risolto il disallineamento tra il valore istantaneo dello speedtest del Gateway (970 Mbps) e la serie storica del database.
* **Sincronizzazione Automatica Gateway eero:** Il poller registra in modo continuo nel database SQLite ogni nuova misurazione reale completata dal Gateway eero, alimentando correttamente il grafico e le statistiche aggregate.
* **Unificazione Single Source of Truth:** L'ultimo punto del grafico, le schede di riepilogo in cima alla pagina Speed Test, la card di anteprima della Dashboard e le statistiche aggregate (Medie, Picchi Massimi, Latenza) attingono ora alla medesima sorgente dati coerente.
* **Esecuzione Test Ottimizzata:** Il trigger manuale dello speed test attende fino a completamento reale della misura hardware da parte del router eero prima di salvare e aggiornare l'interfaccia.

---

## [1.00.07] - 2026-08-26

### 🏷️ Indicatori Visivi Tipo IP nella Tabella Dispositivi
* **Badge Distintivo STATICO vs DHCP:** Ciascun dispositivo nella tabella principale mostra ora chiaramente lo stato dell'indirizzo IP con un badge dedicato:
  * 🟢 **`STATICO`** (Verde Smeraldo) se il dispositivo ha una prenotazione DHCP attiva su Cloud eero o un IP statico configurato.
  * ⚪ **`DHCP`** (Grigio Slate) se il dispositivo ottiene un indirizzo IP in assegnazione dinamica.
* **Filtro Rapido per Tipo di Assegnamento:** Aggiunto un menu a tendina nella barra filtri per isolare al volo *Solo IP Statici* o *Solo DHCP Dinamici*.
* **Sincronizzazione Poller delle Prenotazioni:** Il poller di background interroga le prenotazioni Cloud eero e propaga lo stato statico in tempo reale su tutta la dashboard.

---

## [1.00.06] - 2026-08-26

### 🔄 Assegnazione IP Corrente & Riassegnazione Intelligente
* **Assegnazione IP Corrente del Dispositivo:** Permette di confermare e rendere permanente tramite prenotazione DHCP l'indirizzo IP che il dispositivo sta già utilizzando (tramite lease dinamico).
* **Riassegnazione Automatica da Altre Schede di Rete / Vecchi Host:** Se un IP apparteneva precedentemente a un'altra scheda di rete (es. Wi-Fi vs Ethernet dello stesso PC) o a un vecchio apparato, la dashboard non blocca più l'operazione ma offre il pulsante **`Riassegna e Riserva`**, rimuovendo automaticamente la vecchia prenotazione obsoleta dal Cloud eero prima di registrare la nuova.
* **Alert Contestuali Informativi:** Gli avvisi di occupazione IP per dispositivi client diventano avvisi informativi (badge ambra) che informano sul trasferimento senza impedire l'azione all'amministratore di rete.

---

## [1.00.05] - 2026-08-26

### 🌐 Gestione Nativa IP Statici (DHCP) & Port Forwarding
* **Prenotazioni DHCP Sincronizzate con Cloud eero:** Aggiunta la gestione autentica delle prenotazioni IP statico con creazione (`POST /reservations`) ed eliminazione (`DELETE /reservations/{id}`) in tempo reale tramite Cloud eero.
* **Rilevamento Conflitti IP in Tempo Reale:** L'interfaccia analizza istantaneamente l'IP digitato confrontandolo con il Gateway, i nodi mesh, le altre prenotazioni attive e tutti i dispositivi connessi, impedendo conflitti o collisioni di rete.
* **Gestione Port Forwarding Integrata per Dispositivo:** Tabella interattiva delle porte aperte per ciascun host (Porta WAN, Porta LAN, Protocollo TCP/UDP/Both, Descrizione) con aggiunta e cancellazione con un clic.
* **Nuova Interfaccia Modale a Schede (Tabs):** Organizzazione in 3 sezioni chiare: `Dati & Categoria`, `IP Statico (DHCP)` e `Port Forwarding`.

---

## [1.00.04] - 2026-08-26

### 🛠️ Gestione Dispositivi & Metadati Locali
* **Fix Categoria e Preferiti:** Risolto il disallineamento maiuscole/minuscole sugli indirizzi MAC che impediva la persistenza e il ricaricamento di Categoria, Preferiti, Note e Flag di Gaming Mode in SQLite.
* **Badge Preferiti ⭐ & Filtro Dedicato:** I dispositivi contrassegnati come preferiti mostrano una stella ⭐ accanto al nome e possono essere filtrati al volo dal selettore di categoria (*Solo Preferiti*).
* **Semplificazione Modale Dispositivo:** Rimossa la configurazione confusa della prenotazione IP statico dal popup; introdotto un box informativo chiaro con **IP Attuale** e **Nodo Mesh Collegato**.
* **Rimozione Pulsanti LED Globali:** Eliminati i pulsanti *"Spegni Tutti i LED"* e *"Accendi Tutti i LED"* dalla testata dei Nodi Mesh in linea con i vincoli firmware eero v7.x.
* **Pulizia Completa Database Banda:** Rimosse le tabelle obsolete `wan_metrics` e `device_metrics` e tutti i cicli di scrittura continui di throughput su SQLite.

---

## [1.00.03] - 2026-08-26

### 🏷️ Raffinamento Interfaccia & Nodi Mesh
* **Etichetta "Stato" sulle schede dei Nodi:** Sostituita la precedente dicitura con un'etichetta univoca e pulita **`Stato: Online • Ottimale`**.
* **Rimozione Controlli LED non supportati da Cloud:** Rimosso il pulsante toggle LED dalle schede dei nodi e lo scheduler Notte LED. I nodi eero (in particolare con firmware v7.x) riservano il controllo fisico dei LED all'app mobile ufficiale / BLE; la dashboard evita comandi che verrebbero sovrascritti dal cloud.
* **Pulsante Riavvio Nodi Dedicato:** Mantenuto il comando nativo e verificato di riavvio individuale per ciascun nodo mesh.

---

## [1.00.02] - 2026-08-26

### 🧹 Semplificazione & Allineamento Diretto API eero
* **Rimozione Scheda Storico Banda & WAN:** Eliminata la sezione e i grafici storici non supportati in modo nativo continuo dall'API base eero.
* **Rimozione Contatore WAN nell'Header:** Eliminato il tachimetro di throughput al centro dell'header per mostrare solo informazioni certe e certificate.
* **Rimozione Velocità Live nella Pagina Dispositivi:** Eliminata la colonna di velocità istantanea, sostituita con i dati fisici autentici delle API eero: **Banda & Canale Wi-Fi**, **Segnale RSSI (dBm)** e **Link Speed PHY (es. 780 / 866.7 Mbps)**.
* **Integrità Assoluta:** L'applicazione visualizza esclusivamente ciò che viene inviato senza intermediari dall'infrastruttura eero.

---

## [1.00.01] - 2026-08-26

### 🛡️ Approccio Rigoroso a Dati Reali (No Simulation)
* **Rimozione stime sintetiche di throughput:** Eliminata qualsiasi logica di generazione fittizia o casuale del throughput istantaneo (`download_rate_mbps` / `upload_rate_mbps`) per i dispositivi live in `eero_client.py`.
* **Eliminazione moltiplicazione temporale artificiale:** Rimosso il calcolo stimato su 24h in `metrics.py` basato su velocità fittizie (`avg_rate * 24h * 0.15`). La classifica dei consumi (*Bandwidth Hogs*) mostra unicamente i byte effettivi misurati.
* **Integrità metrica:** I dispositivi Wi-Fi o IoT a riposo che non scambiano traffico o per cui l'API standard non espone contatori riportano fedelmente `0.0 Mbps` e `0 GB`, senza alcuna alterazione o gonfiamento sintetico.

### 🐛 Bug Fixes
* **Risolto falso positivo consumo robot Higgins:** Corretta la lista delle parole chiave in `eero_client.py` e `metrics.py` in cui il dispositivo `"higgins"` (robot lavapavimenti) era erroneamente classificato tra i client ad alto consumo multimediale/streaming.
* **Correzione calcolo Delta 24h in SQLite:** Risolto un bug in `db.py` in cui, in caso di delta nullo (`MAX - MIN = 0`), veniva mostrato erroneamente il contatore cumulativo a vita (`MAX(rx_bytes)`), facendo apparire il traffico storico dell'intero ciclo vitale del dispositivo come se fosse avvenuto nelle ultime 24 ore.
* **Rimozione baseline sintetica WAN:** Eliminata la generazione di campioni fittizi nei grafici WAN in caso di database appena avviato o con pochi campioni.

### 🎨 Interfaccia Utente & Nuove Funzionalità
* **Aggiornamento versione visiva:** La versione dell'applicazione è stata aggiornata a **v1.00.01** sia nell'header che nel footer.
* **Visualizzatore Changelog interattivo:** Cliccando sul badge della versione (`v1.00.01`) o sul link nel footer si apre direttamente un popup modale con la cronologia dettagliata delle modifiche.
* **Gestione elegante degli stati vuoti:** Aggiunto messaggio descrittivo pulito nella tabella e nei grafici dei consumi quando non sono presenti dispositivi con traffico intensivo registrato.
* **Pulizia database locale:** Azzerati i record legacy con campioni simulati/anomali per garantire una ripartenza pulita e autentica.

### 📚 Documentazione & FAQ
* **Aggiornamento Manuale & FAQ integrate:** Aggiornate le sezioni 4 (*Monitoraggio Banda*) e 8 (*FAQ & Risoluzione Problemi*) del manuale integrato per spiegare nel dettaglio la differenza tra dispositivi cablati e Wi-Fi standard e l'approccio a dati rigorosi adottato.

---

## [1.0.0] - 2026-08-25

### 🚀 Release Iniziale
* **Architettura Self-Hosted su Docker:** Containerizzazione completa con FastAPI, Alpine.js, Tailwind CSS e Chart.js.
* **Autenticazione Ufficiale 2FA OTP:** Login sicuro tramite One-Time Password via SMS/Email con persistenza della sessione su disco.
* **In-Memory Zero-Latency Poller:** Monitoraggio continuo della rete mesh con latenza 0ms per l'interfaccia.
* **Bandwidth Historian & WAN Metrics:** Grafici temporali del traffico di rete (24h, 7gg, 30gg) e classifica Top Consumer.
* **Device Management Suite:** Ricerca, filtri per frequenza (2.4/5/6 GHz/Ethernet), personalizzazione icone, note, assegnazione IP statico e pausa internet a un clic.
* **Automazioni & Controlli Rapidi:** Smart Guest Wi-Fi con QR Code dinamico, Gaming/Focus Mode (Low Latency), Scheduler Notturno LED e Speed Test integrato.
* **Sistema di Notifiche:** Supporto per Bot Telegram e Webhook HTTP generici per nuovi dispositivi connessi e nodi offline.
* **Manuale Utente Integrato:** 8 capitoli con guida interattiva e help contestuale.
