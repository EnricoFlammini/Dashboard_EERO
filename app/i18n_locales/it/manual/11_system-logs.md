---
id: system-logs
title: 11. Gestione Log di Sistema & Diagnostica Avanzata
icon: terminal
summary: Console live dei log, livelli di dettaglio dinamici (DEBUG/INFO/WARNING/ERROR), retention, esportazione e svuotamento sicuro.
---
### Gestione Log di Sistema & Diagnostica Avanzata (v1.6.0)

La scheda **Controlli & QR Ospiti** include ora la Card 7 dedicata alla **Gestione Log & Diagnostica**:

* **Master Switch Logging:**
  - Toggle rapido per attivare o sospendere la scrittura degli eventi nel database locale SQLite (`system_logs`) e nel file rotativo su disco (`data/system.log`).
* **Profondità di Analisi (Livelli di Dettaglio a Caldo):**
  - Seleziona istantaneamente il livello di severità senza riavviare il container:
    - `DEBUG`: Dettagliato. Traccia tutte le chiamate API interne, le risposte del cloud e le sincronizzazioni di rete.
    - `INFO`: Normale (predefinito). Registra gli eventi significativi, variazioni di stato dei nodi e connessioni client.
    - `WARNING`: Avvisi. Segnala degradi di latenza, disconnessioni temporanee e anomalie di sincronizzazione.
    - `ERROR`: Critico. Limita i log esclusivamente alle eccezioni bloccanti e agli errori di comunicazione.
* **Periodo di Conservazione (Retention Temporale):**
  - Imposta il periodo di persistenza: **24 Ore (24h)**, **7 Giorni (7gg/7d)**, **15 Giorni (15gg/15d)**, **1 Mese (1m/1mo)** o **Personalizzato** (inserimento del numero esatto di giorni, con `0` per conservazione illimitata).
  - Un worker di background compila e rimuove periodicamente i log obsoleti garantendo che lo storage non si saturi mai.
* **Console Live Log Viewer:**
  - Box terminale ad alto contrasto con font monospazio (`Fira Code`).
  - Ricerca rapida full-text sul testo dei messaggi e sul nome del modulo (`logger_name`).
  - Filtro rapido a chip per livello di gravità (`TUTTI`, `DEBUG`, `INFO`, `WARNING`, `ERROR`).
  - Esplorazione interattiva dei dettagli JSON per ogni record (chiamate HTTP, payload, audit di sicurezza).
  - Toggle per **Auto-Refresh ogni 10s**.
* **Strumenti di Esportazione & Svuotamento:**
  - **Download Log:** Esportazione del log completo in formato testo `.log` standard RFC 5424 oppure in formato strutturato `.json`.
  - **Svuotamento Sicuro (Clear Logs):** Pulsante protetto da permessi RBAC con modale di conferma per azzerare tabella e file di log in un clic.
