---
id: speedtest
title: 6. Speed Test, Diagnostica & Qualità Segnale Wi-Fi
icon: gauge
summary: Esecuzione test di velocità, storico misurazioni, analisi del segnale RSSI e copertura mesh.
---
### Diagnostica di Velocità & Copertura Wi-Fi

* **Test Manuale di Velocità:** Clicca sul pulsante **"Avvia Speed Test"** per lanciare una misurazione in tempo reale di Download, Upload, Latenza (Ping) e Jitter.
* **Test Automatici Pianificati:** Il sistema può pianificare test automatici in background (ad esempio ogni 12 ore) per monitorare nel tempo la costanza della linea.
* **Grafico Storico & Statistiche:**
  - Grafico temporale di velocità e latenza nel corso di giorni e settimane.
  - Statistiche aggregate con velocità media di download/upload, picchi massimi di velocità e ping medio.
* **Qualità Wi-Fi & Copertura Mesh:**
  - **Registro Storico RSSI (dBm) & Parsing Universale:** Il poller campiona e memorizza in SQLite i livelli di segnale wireless convertendo deterministicamente ogni formato (interi, float, stringhe con unità come `"-78 dBm"` o campi annidati `signal_avg`) in valori dBm puliti nell'intervallo `[-120, -1]`.
  - **Segnale Medio & Fasce di Qualità:** KPI con livello medio dell'intera abitazione e ripartizione per fasce: *Eccellente* (≥ -50 dBm), *Buono* (-51 a -65 dBm), *Discreto* (-66 a -75 dBm), *Critico* (< -75 dBm).
  - **Popolamento Live Istantaneo & Watchlist Segnale Debole:** L'overview unisce in tempo reale i client wireless attivi dalla cache del poller, garantendo che i KPI, le barre percentuali e la **Weak Signal Watchlist** (`< -75 dBm`) siano sempre popolati anche al primissimo avvio prima dell'accumulo storico.
  - **Grafico Temporale Interattivo:** Seleziona qualunque client wireless per visualizzare il grafico temporale Chart.js delle ultime 24 ore o 7 giorni con valori attuali, minimi, massimi e medi, con binding reattivo sul selettore dispositivo.
  - **Auto-Riparazione SQLite a 3 Stadi:** Meccanismo di auto-guarigione trasparente (`repair_if_malformed`) che ripara indici corrotti o ripristina la struttura del database in caso di riavvii anomali del container senza alcuna perdita di impostazioni o personalizzazioni.
