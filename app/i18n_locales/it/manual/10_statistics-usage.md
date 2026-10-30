---
id: statistics-usage
title: 10. Statistiche, Consumo Dati Dispositivi & Centro Esportazione
icon: chart-bar
summary: Suite di consumo dati per apparato, widget Top Bandwidth Hogs, grafici di distribuzione e Centro Esportazione CSV/JSON.
---
### Statistiche Avanzate, Consumo Dati & Data Export Center (v1.5.0)

* **Device Data Usage Insights Suite:**
  - Accedendo alla scheda **"Consumo Dati"** nel modale del dispositivo, è possibile analizzare il volume di traffico scaricato e caricato su 3 orizzonti temporali: **Ultime 24 ore** (con andamento orario in Mbps), **Ultimi 7 giorni** (consumo giornaliero) e **Ultimi 30 giorni** (panoramica mensile).
  - Grafico interattivo Chart.js a doppia linea con indicatori KPI di Download totale, Upload totale e Traffico combinato.
  - **Trasparenza di Calcolo:** Algoritmo resiliente a standby, disconnessioni temporanee e azzeramenti contatori hardware, con modale esplicativo accessibile tramite i pulsanti `?` di aiuto.
  - **Nota Tecnica Commutazione Cablata:** Per i dispositivi collegati via cavo Ethernet, l'indicatore `↓ — / ↑ — (Cablato)` riflette la commutazione trasparente Layer 2 hardware dello switch ASIC eero.
* **Widget "Top Bandwidth Hogs":**
  - Card dedicata nella dashboard principale che evidenzia in tempo reale i dispositivi che hanno generato il maggior volume di traffico, con accesso rapido alla vista dettagliata in un solo clic.
* **Sezione Statistiche & Analytics di Rete:**
  - **Ripartizione Frequenze Wi-Fi:** Distribuzione in percentuale e conteggio client tra 2.4 GHz, 5 GHz, 6 GHz e Cablati.
  - **Bilanciamento Carico Nodi Mesh:** Monitoraggio del carico di apparati attestati su ciascun eero per ottimizzare il posizionamento dei ripetitori.
  - **Categorie & Vendor OUI:** Ripartizione per tipologia di apparato e costruttore hardware (Apple, Samsung, Espressif, ecc.).
  - **Tooltip Interattivi con Elenco Dispositivi:** Passando il cursore su qualunque barra o fetta di grafico, un tooltip avanzato elenca i nomi di tutti i dispositivi corrispondenti (fino a 15 con troncamento intelligente).
  - **Trend Prestazioni Linea & Diagnostica SLA ISP:** Grafici storici a 7 e 30 giorni per velocità di download/upload, latenza ping e indice di stabilità complessiva della linea FTTH/VDSL.
* **Centro Esportazione Dati (RFC 4180 CSV & JSON):**
  - Esportazione rapida e standardizzata dell'inventario dispositivi, storico speedtest, campionamenti del segnale RSSI e storico consumo dati per integrazione con fogli di calcolo, Grafana o Home Assistant.
