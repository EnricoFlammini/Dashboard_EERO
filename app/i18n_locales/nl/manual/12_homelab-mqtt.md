---
id: homelab-mqtt
title: 12. HomeLab-Integratie via MQTT & Home Assistant
icon: home
summary: Asynchrone MQTT-client, Home Assistant Auto-Discovery, realtime telemetrie en device_tracker-entiteiten.
---
### HomeLab-Integratie via MQTT & Home Assistant-detectie

De applicatie integreert naadloos met domoticasystemen via het MQTT-protocol:

* **Automatische detectie in Home Assistant (MQTT Auto-Discovery):**
  - Publicatie conform officiële Home Assistant-specificaties onder het ingestelde voorvoegsel (standaard `homeassistant/`).
  - **Netwerksensoren:**
    - `eero WAN Download` & `eero WAN Upload` (gestandaardiseerd in `Mbit/s` met apparaatklasse `data_rate`).
    - `eero WAN Ping` (latentie in milliseconden).
    - `eero Network Health` (gezondheidsscore van 0 tot 100).
    - `eero Connected Clients` (totaalaantal verbonden apparaten).
    - `eero Mesh Nodes Online` (aantal actieve eero-punten).
  - **Aanwezigheidsdetectie (`device_tracker`):**
    - Automatische aanmaak van entiteiten per client met status `home` / `not_home`.
    - Volledige attributen: Lokaal IP, MAC-adres, verbonden knooppunt, Wi-Fi-band en tijdstempel `last_seen_connected`.
    - Automatische herpublicatie van de configuratie zodra een apparaat zijn echte computernaam verkrijgt.
* **Hoogfrequente live-telemetrie (`MQTT_LIVE_INTERVAL`):**
  - Mogelijkheid voor een apart snel publicatie-interval (bijv. 5 seconden) voor WAN-doorvoer en clientaantallen zonder de broker te belasten.
* **Betrouwbaarheid & Herverbinding:**
  - Ondersteuning voor lokale en externe brokers (Mosquitto, EMQX, HiveMQ) met automatische herverbinding via exponentiële back-off.
