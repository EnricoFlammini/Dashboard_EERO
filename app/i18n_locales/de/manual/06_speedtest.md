---
id: speedtest
title: 6. Geschwindigkeitstest, Diagnose & WLAN-Signalqualität
icon: gauge
summary: Bandbreitenmessung, Messverlauf, RSSI-Signalanalyse und Mesh-Abdeckung.
---
### Geschwindigkeitsdiagnose & Funkabdeckung

* **Manueller Geschwindigkeitstest:** Klicken Sie auf **"Speed Test starten"**, um eine Echtzeitmessung von Download, Upload, Ping und Jitter durchzuführen.
* **Automatisch geplante Messungen:** Das System kann Messungen periodisch im Hintergrund ausführen (z. B. alle 12 Stunden), um Leitungsstabilität langfristig zu dokumentieren.
* **Verlaufsdiagramme & Statistiken:** Chart.js-Verlaufskurven für Datenraten und Latenzen mit Durchschnittswerten und Bufferbloat-Einstufung.
* **WLAN-Signalqualität & Mesh-Abdeckung:**
  - **RSSI-Verlaufsprotokollierung in dBm:** Präzise Erfassung der Funksignalwerte, standardisiert im Bereich `[-120, -1] dBm`.
  - **Durchschnittssignal & Qualitätsstufen:** Gesamtübersicht und Einstufung: *Hervorragend* (≥ -50 dBm), *Gut* (-51 bis -65 dBm), *Ausreichend* (-66 bis -75 dBm), *Kritisch* (< -75 dBm).
  - **Live-Daten-Aktualisierung & Beobachtungsliste:** Echtzeit-Zusammenführung aktiver WLAN-Clients garantiert, dass die **Weak Signal Watchlist** (`< -75 dBm`) immer aktuell gefüllt ist.
  - **Interaktiver Signalverlauf pro Gerät:** Zeitreihendiagramm über 24 Stunden oder 7 Tage für jedes ausgewählte Gerät.
  - **3-Stufen-SQLite-Selbstreparatur:** Automatischer Reparaturmechanismus, der beschädigte Indizes oder Tabellen nach Systemabstürzen ohne Datenverlust wiederherstellt.
