---
id: speedtest
title: 6. Speed Test, Diagnostica & Qualità Segnale Wi-Fi
icon: gauge
summary: Esecuzione test di velocità, storico misurazioni, analisi del segnale RSSI e copertura mesh.
---
### Diagnostica di Velocità & Copertura Wi-Fi

* **Test Manuale di Velocità:** Clicca sul pulsante **"Avvia Speed Test"** per lanciare una misurazione in tempo reale di Download, Upload, Latenza (Ping) e Jitter direttamente dal Gateway eero.
* **Test Automatici Pianificati:** Il sistema monitora e storicizza periodicamente i test eseguiti dall'infrastruttura mesh per valutare la costanza della linea FTTH/VDSL.
* **Grafico Storico & Statistiche:**
  - Grafico dell'andamento di velocità e stabilità della linea nel corso dei giorni.
  - Calcolo automatico di velocità media, picco massimo e latenza minima.
* **Qualità Wi-Fi & Copertura Mesh (v1.4.0):**
  - **Storicizzazione Continua Segnale (dBm):** Il poller registra in automatico i livelli RSSI, frequenze e bitrate di tutti i dispositivi wireless attivi nel database SQLite locale (`device_signal_history`).
  - **Segnale Medio & Fasce di Qualità:** KPI con livello medio dell'intera abitazione e ripartizione per fasce: *Eccellente* (≥ -50 dBm), *Buono* (-51 a -65 dBm), *Discreto* (-66 a -75 dBm), *Critico* (< -75 dBm).
  - **Grafico Temporale Interattivo:** Seleziona qualunque client wireless per visualizzare il grafico temporale Chart.js delle ultime 24 ore o 7 giorni con valori attuali, minimi, massimi e medi.
  - **Weak Signal Watchlist:** Elenco degli apparati con segnale debole e consigli di riposizionamento dei nodi mesh.
