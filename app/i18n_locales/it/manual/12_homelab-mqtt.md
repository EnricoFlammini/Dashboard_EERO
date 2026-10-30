---
id: homelab-mqtt
title: 12. Integrazione Homelab via MQTT & Home Assistant Discovery
icon: share
summary: Connessione a broker MQTT, Home Assistant MQTT Auto-Discovery, sensori telemetrici e device tracking dei client.
---
### Integrazione Homelab via MQTT & Home Assistant Discovery (v1.6.0)

La dashboard si integra nativamente nel tuo ambiente HomeLab tramite il protocollo **MQTT**:

* **Home Assistant MQTT Auto-Discovery:**
  - Rilevamento istantaneo senza configurazioni YAML manuali: tutte le entità vengono create automaticamente sotto il prefisso standard `homeassistant/`.
  - **Sensori Telemetrici:**
    - `eero WAN Download` & `eero WAN Upload` (Velocità in Mbps con `device_class: data_rate`).
    - `eero Network Health` (Punteggio di salute 0-100%).
    - `eero Connected Clients` (Conteggio client attivi con icona `mdi:devices`).
    - `eero Mesh Nodes Online` (Nodi mesh operativi).
    - `eero Bufferbloat Grade` (Voto di reattività linea da A+ a F).
  - **Sensori Binari di Connettività:**
    - `eero Internet Status` (`ONLINE` / `OFFLINE`).
    - `eero Cloud Status` (`CONNECTED` / `DISCONNECTED`).
  - **Device Tracker dei Client di Rete:**
    - Generazione automatica di entità `device_tracker` per ciascun dispositivo della rete.
    - Riporta lo stato `home` / `not_home`, IP locale, indirizzo MAC, nodo eero di attestazione e interfaccia radio (5 GHz / 6 GHz / Ethernet).
* **Configurazione Broker & Sicurezza:**
  - Supporta broker locali e remoti (Mosquitto, EMQX, HiveMQ) con autenticazione via username e password.
  - Riconnessione asincrona automatica e gestione trasparente in modalità Demo.
