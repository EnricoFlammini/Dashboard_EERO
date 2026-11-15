---
id: system-logs
title: 11. Systemprotokolle & Erweiterte Diagnose
icon: terminal
summary: Live-Protokollkonsole, dynamische Detailstufen, Aufbewahrung, Export und sichere Bereinigung.
---
### Systemprotokoll-Verwaltung & Erweiterte Diagnose

Die Karte **Protokollverwaltung & Diagnose** bietet umfassende Kontrolle über Systemereignisse:

* **Hauptschalter für Protokollierung:** Aktiviert oder pausiert das Schreiben von Ereignissen in die SQLite-Datenbank und die rotierende Protokolldatei (`data/system.log`).
* **Dynamische Protokollierungsstufen ohne Neustart:**
  - `DEBUG`: Detaillierte Protokollierung aller API-Aufrufe und Synchronisierungen.
  - `INFO`: Standardaufzeichnung wichtiger Ereignisse und Verbindungen.
  - `WARNING`: Warnungen bei erhöhten Latenzen oder Signalanomalien.
  - `ERROR`: Beschränkt auf kritische Ausnahmen und Kommunikationsfehler.
* **Automatische Aufbewahrungsdauer:** Festlegung der Historie: 24h, 7 Tage, 15 Tage, 1 Monat oder benutzerdefiniert (mit automatischer Hintergrundbereinigung).
* **Live-Protokollanzeige:** Kontrastreiche Terminalkonsole mit Festbreitenschrift, Volltextsuche, Schweregradfiltern und automatischer Aktualisierung alle 10 Sekunden.
* **Export & Bereinigung:** Download im RFC-5424-Standardtextformat `.log` oder als `.json` sowie rollengeschützte Leerung mit Bestätigungsabfrage.
