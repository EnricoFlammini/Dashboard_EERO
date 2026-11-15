---
id: reverse-enrichment
title: 16. Reverse Client Enrichment & IPv6 ULA-Erkennung
icon: arrows-right-left
summary: Bidirektionale Datenanreicherung über lokale DNS-Server, Erkennung von IPv6-ULA-Adressen und Neu-Geräte-Status.
---
### Reverse Client Enrichment & IPv6 ULA-Erkennung

In Dual-Stack-Netzen senden Geräte ihre DNS-Anfragen häufig über lokale **IPv6 ULA**-Adressen (*Unique Local Address*, Präfixe `fc00::/7` und `fd00::/8`). Da dieser Datenverkehr auf der lokalen Vermittlungsebene (Layer 2) verbleibt, besitzt die eero-Cloud keine Einsicht in diese Adressen.

* **Reverse Client Enrichment via NDP & REST-Ingestion:**
  - **Automatischer Hintergrund-Scan:** Das System prüft regelmäßig die Kernel-Nachbarschaftstabelle (NDP / ARP) und lokale DNS-Server, um ULA-Adressen den physischen MAC-Adressen zuzuordnen.
  - **Externe Ingestion-API (`POST /api/network/enrichment/neighbors`):** Ermöglicht Hilfsskripten oder Containern das Einspeisen von IP-MAC-Zuordnungen in Echtzeit.
  - **Vollständige Rücksynchronisation:** Erkannte ULA-Adressen werden mit den lokalen DNS-Servern abgeglichen, sodass anonyme IP-Abfragen stets dem Gerätenamen zugeordnet werden.
* **Kennzeichnung & Detaileinsicht:**
  - Angereicherte Adressen werden in der Tabelle und Gerätedetailansicht mit dem lila Badge **`ULA Enriched`** hervorgehoben.
* **Kürzlich beigetretene Geräte & "NEW"-Badge:**
  - Das System speichert den Erstverbindungszeitpunkt (`first_seen`) jedes Geräts.
  - Geräte, die in den letzten 24 bis 48 Stunden erstmals erkannt wurden, tragen das auffällige smaragdgrüne Badge **`NEW`**.
* **Automatische Wartungsbereinigung:**
  - Nicht mehr genutzte temporäre ULA-Einträge werden nach 30 Tagen Inaktivität automatisch aus der SQLite-Datenbank entfernt.
