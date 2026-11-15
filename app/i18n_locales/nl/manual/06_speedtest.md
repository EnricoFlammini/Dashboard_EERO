---
id: speedtest
title: 6. Snelheidstest, Diagnose & Wi-Fi-signaalkwaliteit
icon: gauge
summary: Bandbreedtemeting, testhistorie, RSSI-signaalanalyse en mesh-dekking.
---
### Snelheidsdiagnose & Wi-Fi-dekking

* **Handmatige snelheidstest:** Klik op **"Start Speed Test"** voor een realtime meting van download, upload, ping en jitter.
* **Geautomatiseerde periodieke tests:** Het systeem kan metingen automatisch op de achtergrond plannen (bijv. elke 12 uur) om de lijnstabiliteit te bewaken.
* **Historische grafieken & Statistieken:** Verloop van snelheden en latentie over dagen en weken met gemiddelden en bufferbloat-beoordeling.
* **Wi-Fi-signaalkwaliteit & Mesh-dekking:**
  - **RSSI-historie in dBm & Universele verwerking:** Nauwkeurige registratie van draadloze signaalwaarden gestandaardiseerd binnen het bereik `[-120, -1] dBm`.
  - **Gemiddeld signaal & Kwaliteitsniveaus:** Algemene kwaliteitsindicator en indeling: *Uitstekend* (≥ -50 dBm), *Goed* (-51 tot -65 dBm), *Matig* (-66 tot -75 dBm), *Kritiek* (< -75 dBm).
  - **Realtime gegevens & Aandachtslijst:** Directe samenvoeging van actieve draadloze clients garandeert dat de **Weak Signal Watchlist** (`< -75 dBm`) direct beschikbaar is.
  - **Interactieve tijdsgrafiek per apparaat:** Chart.js-grafiek over 24 uur of 7 dagen voor elk geselecteerd apparaat.
  - **3-Fasen SQLite-zelftests & Herstel:** Automatisch herstelmechanisme dat beschadigde indexen of tabellen herstelt na onverwachte herstarts.
