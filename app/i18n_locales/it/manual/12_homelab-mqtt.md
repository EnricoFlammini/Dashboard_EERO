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
    - `eero WAN Download` & `eero WAN Upload` (Velocità standardizzata in `Mbit/s` con `device_class: data_rate` per conformità nativa Home Assistant - Issue #104).
    - `eero Network Health` (Punteggio di salute 0-100%).
    - `eero Connected Clients` (Conteggio client attivi con icona `mdi:devices`).
    - `eero Mesh Nodes Online` (Nodi mesh operativi).
    - `eero Bufferbloat Grade` (Voto di reattività linea da A+ a F).
  - **Sensori Binari di Connettività:**
    - `eero Internet Status` (`ONLINE` / `OFFLINE`).
    - `eero Cloud Status` (`CONNECTED` / `DISCONNECTED`).
  - **Device Tracker dei Client di Rete:**
    - Generazione automatica di entità `device_tracker` per ciascun dispositivo della rete.
    - Riporta lo stato `home` / `not_home`, IP locale, indirizzo MAC, nodo eero di collegamento, interfaccia radio (2.4 GHz / 5 GHz / 6 GHz / Ethernet) e attributo temporale `last_seen_connected` (Issue #101).
    - Ri-pubblicazione automatica e istantanea della configurazione discovery non appena un dispositivo acquisisce il suo hostname reale (Issue #103).
    - Vengono pubblicati fino a 1000 dispositivi per ciclo; oltre tale soglia i restanti vengono ignorati e viene registrato un avviso una sola volta.
* **Telemetria Live ad Alta Frequenza (`MQTT_LIVE_INTERVAL` - Issue #104):**
  - Consente di impostare un intervallo separato rapido (es. 5 secondi) per pubblicare solo le velocità WAN e i client attivi sul topic `{base_topic}/live` senza sovraccaricare il broker con l'intero catalogo dei device tracker.
* **Configurazione Broker & Affidabilità:**
  - Supporta broker locali e remoti (Mosquitto, EMQX, HiveMQ) con autenticazione via username e password e test di connessione in tempo reale dalla modale UI.
  - Riconnessione asincrona automatica con backoff esponenziale e gestione trasparente in modalità Demo.
