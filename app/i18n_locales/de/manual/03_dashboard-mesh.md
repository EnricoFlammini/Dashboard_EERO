---
id: dashboard-mesh
title: 3. Dashboard & Mesh-Topologie
icon: network
summary: Netzwerk-Gesundheitswert, Knotenkarten und Schnellaktionen.
---
### Das Haupt-Dashboard verstehen

* **Netzwerk-Gesundheitswert (1-100):** Zusammenfassende Bewertung des Netzwerkzustands basierend auf Knotenverfügbarkeit, Gateway-Präsenz und RSSI-Signalqualität der Clients.
* **Übersichtskarten:**
  - *WAN-Status:* Öffentliche IP, Provider, IPv6, Gesundheitsbalken und letztes Update.
  - *Haupt-Gateway:* Modell, lokale IP, Subnetz, DNS, Firmware und Online-Knoten.
  - *Verbundene Clients:* Gesamtzahl und Aufteilung nach 6 GHz / 5 GHz / 2.4 GHz / LAN, bekannte Geräte, Gäste und Neuankömmlinge.
  - *Letzter Geschwindigkeitstest:* Download/Upload, Ping, Bufferbloat-Bewertung und Verlaufsdaten.
* **eero-Knoten-Topologie:**
  - *Gateway-Knoten:* Der direkt mit dem Modem oder Glasfaser-ONT verbundene Hauptknoten.
  - *Beacons / Mesh-Extender:* Sekundäre Einheiten zur Vergrößerung der Funkabdeckung.
  - *Verbindungsart (Backhaul):* Zeigt an, ob Knoten über Gigabit-Ethernet-Kabel oder über ein dediziertes Funkband verbunden sind.
* **Schnellaktionen für Knoten:**
  - **Netzwerk neu starten:** Sendet einen kontrollierten Neustart-Befehl an das gesamte Mesh-System.
  - **Einzelnen Knoten neu starten:** Startet gezielt nur das ausgewählte Gerät neu.
* **Erweiterte Mesh-Funktionen:**
  - **Amazon Echo "eero Built-in"-Extender:** Automatische Erkennung kompatibler Echo-Geräte mit Mesh-Erweiterung, Kennzeichnung durch das Badge **`eero Built-in`** und Anzeige verbundener Clients.
  - **Gateway-Erkennung im Bridge-Modus:** Zuverlässige Identifikation des Haupt-Gateways über das Attribut `is_primary_node` und LLDP-Nachbarn an der WAN-Schnittstelle.
  - **Offizielle Hardware-Produktbilder:** Jeder Knoten wird mit dem originalen Produktbild seines Modells dargestellt (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot usw.).
  - **Streaming-KI-Assistent & Platzierungstest:** Interaktive Diagnose via SSE-Streaming (`/api/network/assistant`), Funkabdeckungs-Platzierungstest und Guardian VPN-Verwaltung.
* **Dashboard-Modus (Standard vs Erweitert):** Ein Umschalter oben rechts ermöglicht den sofortigen Wechsel zwischen der **Standard-Ansicht** (optimiert für normale Benutzer mit Internet-Status, Netzwerk-Gesundheit, aktiven Knoten, Speedtest und kompakter Online-/Offline-Geräteliste) und der **Erweiterten Ansicht** (vollständig mit IP-Adressen, DNS, Subnetzen, Radio-Backhaul, Firmware-Versionen und Verwaltungsaktionen).
