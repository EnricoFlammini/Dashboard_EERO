---
id: multi-network
title: 9. Multi-Netzwerk-Verwaltung & Schnellwechsel
icon: globe
summary: Unterstützung für Multi-Standort-Konten, sofortiger Wechsel und dauerhafte Netzwerkauswahl.
---
### Multi-Netzwerk-Verwaltung & Schnellwechsel

* **Dynamischer Standort-Wähler im Header (Windows 11 Fluent):** Verwaltet Ihr Konto mehrere eero-Netzwerke (z. B. Hauptwohnsitz, Büro, Ferienhaus), zeigt ein Dropdown-Menü die Knoten- und Clientzahlen für jeden Standort an.
* **Unterbrechungsfreier Wechsel im Arbeitsspeicher:** Das Auswählen eines anderen Standorts schaltet die Ansicht sofort um, ohne den Container neu zu starten oder Anmeldedaten erneut abzufragen.
* **Dauerhafte Speicherung des aktiven Netzwerks:** Die Auswahl wird in `session.json` und in der lokalen SQLite-Datenbank hinterlegt und bleibt über Neustarts hinweg erhalten.
* **Unterstützung im Demo-Modus:** Enthält zwei simulierte Umgebungen (*Casa Rossi Mesh 6E* und *Büro Pro Mesh*) zum Testen standortübergreifender Funktionen.
* **Architektur & Parallelbetrieb:** Der Wechsel gilt global für die Serverinstanz. Um mehrere Netzwerke dauerhaft parallel nebeneinander anzuzeigen, können zwei separate Docker-Container auf unterschiedlichen Ports betrieben werden.
