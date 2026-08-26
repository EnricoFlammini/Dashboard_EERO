# Changelog - eero Custom Dashboard & Management Suite

Tutte le modifiche rilevanti, i miglioramenti e le correzioni di bug apportate al progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) e aderisce al versionamento semantico.

---

## [1.02.01] - 2026-08-26

### 📡 Ripristino Badge Frequenze Banda & Ottimizzazione Integrazione Profili
* **Ripristino Visualizzazione Banda Wi-Fi (6 GHz, 5 GHz, 2.4 GHz, Ethernet):** Ripristinata e potenziata la colonna *Banda / Canale* nella tabella dispositivi con badge cromatici dedicati (Sky Blue `6 GHz`, Indigo `5 GHz`, Amber `2.4 GHz`, Emerald `Ethernet`) ed etichetta canale Wi-Fi (`CH 11`, `CH 36`, ecc.).
* **Filtro Multi-Frequenza Avanzato:** Potenziato il filtro a tendina nella barra superiore per filtrare istantaneamente i client per frequenza (Tutte le Frequenze, 6 GHz, 5 GHz, 2.4 GHz, Cablato).
* **Ottimizzazione Sezione Profili & Utente:** Rimossa la schermata dedicata separata a favore di una gestione più pulita e diretta: la colonna *Profilo / Utente* rimane pienamente visibile nella tabella Dispositivi con badge `👤 [Nome Profilo]` e filtro rapido, sincronizzata in tempo reale con l'App eero ufficiale.

---

## [1.02.00] - 2026-08-26

### 👤 Gestione Completa Profili Utente Cloud eero & Assegnazione Dispositivi
* **Integrazione Nativa Profili Famiglia Cloud eero:** Aggiunta la gestione completa dei Profili Utente eero (`/profiles`) con supporto a creazione, modifica, eliminazione e pausa istantanea dell'accesso a Internet per tutti i dispositivi del profilo.
* **Nuovo Tab Dedicato "Profili & Utenti":** Introdotta un'intera sezione dell'interfaccia con schede profilo interattive, statistiche aggregate (Totale Profili, Dispositivi Assegnati, Dispositivi Non Assegnati), avatar colorati e gestione unificata.
* **Assegnazione & Disassociazione Dispositivi Bidirezionale:**
  * **Dalla scheda Profilo:** Selettore rapido per aggiungere istantaneamente dispositivi non assegnati e pulsante di rimozione con un clic.
  * **Dalla sezione "Dispositivi Non Assegnati":** Tabella/griglia dedicata con menu a tendina per assegnare subito ogni dispositivo a un utente.
  * **Dalla modale di Modifica Dispositivo:** Aggiunto il menu *Profilo Utente Cloud* nel tab Generale, con sincronizzazione immediata all'atto del salvataggio.
* **Badge & Filtro nella Tabella Dispositivi:**
  * Ciascun dispositivo nella tabella mostra la colonna con badge profilo `👤 [Nome Profilo]`.
  * Aggiunto il filtro rapido *Tutti i Profili / Non Assegnati / Profilo Specifico* nella barra superiore.
  * La barra di ricerca testuale permette di cercare i dispositivi anche digitando il nome del profilo utente.
* **Architettura Zero-Latency & Rate Limit Safe:** I profili sono memorizzati nella cache RAM del Background Poller e arricchiscono ogni oggetto dispositivo in memoria; le mutazioni aggiornano il Cloud eero e sincronizzano istantaneamente la cache RAM senza attendere il ciclo di polling successivo.

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
