---
id: homelab-mqtt
title: 12. Homelab Integration via MQTT & Home Assistant Discovery
icon: share
summary: MQTT broker connectivity, Home Assistant MQTT Auto-Discovery, telemetry sensors and client device tracking.
---
### Homelab Integration via MQTT & Home Assistant Discovery (v1.6.0)

The dashboard natively integrates into your HomeLab ecosystem via **MQTT**:

* **Home Assistant MQTT Auto-Discovery:**
  - Zero-configuration discovery: all entities are automatically declared under the standard `homeassistant/` discovery prefix.
  - **Telemetry Sensors:**
    - `eero WAN Download` & `eero WAN Upload` (Standardized `Mbit/s` units with `device_class: data_rate` for Home Assistant compliance - Issue #104).
    - `eero Network Health` (Health score from 0 to 100%).
    - `eero Connected Clients` (Active client count with `mdi:devices`).
    - `eero Mesh Nodes Online` (Operational mesh nodes count).
    - `eero Bufferbloat Grade` (Line responsiveness grade from A+ to F).
  - **Connectivity Binary Sensors:**
    - `eero Internet Status` (`ONLINE` / `OFFLINE`).
    - `eero Cloud Status` (`CONNECTED` / `DISCONNECTED`).
  - **Client Device Trackers:**
    - Automatic `device_tracker` creation for client devices on the network.
    - Reports `home` / `not_home` state, local IP, MAC address, connected mesh node, connection medium (2.4 GHz / 5 GHz / 6 GHz / Ethernet), and `last_seen_connected` timestamp attribute (Issue #101).
    - Instant discovery config republishing as soon as a device resolves its genuine hostname (Issue #103).
    - Up to 1000 devices are published per cycle; if a network has more, the extras are skipped and a warning is logged once.
* **High-Frequency Live Telemetry (`MQTT_LIVE_INTERVAL` - Issue #104):**
  - Optional fast interval (e.g. 5 seconds) publishing solely WAN speed metrics and client counts to `{base_topic}/live`, preventing broker saturation from full tracker catalog cycles.
* **Broker Configuration & Reliability:**
  - Compatible with standard brokers (Eclipse Mosquitto, EMQX, HiveMQ) with username/password authentication and in-app connection testing.
  - Asynchronous background reconnection with exponential backoff and seamless Demo mode simulation.
