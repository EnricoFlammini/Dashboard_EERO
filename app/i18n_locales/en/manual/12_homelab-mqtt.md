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
    - `eero WAN Download` & `eero WAN Upload` (Speed in Mbps with `device_class: data_rate`).
    - `eero Network Health` (Health score from 0 to 100%).
    - `eero Connected Clients` (Active client count with `mdi:devices`).
    - `eero Mesh Nodes Online` (Operational mesh nodes count).
    - `eero Bufferbloat Grade` (Line responsiveness grade from A+ to F).
  - **Connectivity Binary Sensors:**
    - `eero Internet Status` (`ONLINE` / `OFFLINE`).
    - `eero Cloud Status` (`CONNECTED` / `DISCONNECTED`).
  - **Client Device Trackers:**
    - Automatic `device_tracker` creation for client devices on the network.
    - Reports `home` / `not_home` state, local IP, MAC address, connected mesh node, and connection medium (2.4 GHz / 5 GHz / 6 GHz / Ethernet).
* **Broker Configuration & Reliability:**
  - Compatible with standard brokers (Eclipse Mosquitto, EMQX, HiveMQ) with username/password authentication.
  - Asynchronous background reconnection with exponential backoff and seamless Demo mode simulation.
