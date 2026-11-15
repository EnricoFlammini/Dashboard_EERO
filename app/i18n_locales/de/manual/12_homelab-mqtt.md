---
id: homelab-mqtt
title: 12. HomeLab-Integration via MQTT & Home Assistant
icon: home
summary: Asynchroner MQTT-Client, Home Assistant Auto-Discovery, Echtzeit-Telemetrie und device_tracker-Entitäten.
---
### HomeLab-Integration via MQTT & Home Assistant-Erkennung

Die Suite bindet sich über das MQTT-Protokoll nahtlos in Heimautomationssysteme ein:

* **Home Assistant Automatische Erkennung (MQTT Auto-Discovery):**
  - Standardkonforme Veröffentlichung von Entitäten unter dem konfigurierten Präfix (Standard `homeassistant/`).
  - **Netzwerksensoren:**
    - `eero WAN Download` & `eero WAN Upload` (standardisierte Einheit `Mbit/s` mit Geräteklasse `data_rate`).
    - `eero WAN Ping` (Latenz in Millisekunden).
    - `eero Network Health` (Gesundheitswert von 0 bis 100).
    - `eero Connected Clients` (Gesamtzahl angemeldeter Geräte).
    - `eero Mesh Nodes Online` (Anzahl betriebsbereiter Knoten).
  - **Präsenzerkennung (`device_tracker`):**
    - Automatische Generierung von Entitäten für jedes Endgerät mit Status `home` / `not_home`.
    - Zusätzliche Attribute: Lokale IP, MAC-Adresse, verbundener Knoten, Funkband und Zeitstempel `last_seen_connected`.
    - Automatische Neukonfiguration, sobald ein Gerät seinen echten Netzwerknamen auflöst.
* **Hochfrequente Live-Telemetrie (`MQTT_LIVE_INTERVAL`):**
  - Ermöglicht ein separates, schnelles Abfrageintervall (z. B. 5 Sekunden) für Durchsatz- und Clientdaten, ohne den Broker zu überlasten.
* **Verbindungszuverlässigkeit:**
  - Unterstützt lokale und entfernte Broker (Mosquitto, EMQX, HiveMQ) mit automatischer Wiederverbindung via exponentiellem Backoff.
