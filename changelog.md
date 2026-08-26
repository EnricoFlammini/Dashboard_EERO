# Changelog - eero Custom Dashboard & Management Suite

Tutte le modifiche rilevanti, i miglioramenti e le correzioni di bug apportate al progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) e aderisce al versionamento semantico.

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
