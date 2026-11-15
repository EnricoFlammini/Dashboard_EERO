---
id: homelab-mqtt
title: 12. Integración HomeLab vía MQTT y Home Assistant
icon: home
summary: Cliente MQTT asíncrono, Auto-Discovery de Home Assistant, telemetría en tiempo real y entidades device_tracker.
---
### Integración HomeLab vía MQTT y Detección en Home Assistant

La suite se integra de forma nativa con entornos domóticos a través del protocolo MQTT:

* **Descubrimiento Automático en Home Assistant (MQTT Auto-Discovery):**
  - Publicación conforme a las especificaciones oficiales bajo el prefijo configurado (por defecto `homeassistant/`).
  - **Sensores de Red:**
    - `eero WAN Download` y `eero WAN Upload` (velocidad estandarizada en `Mbit/s` con clase `data_rate`).
    - `eero WAN Ping` (latencia en milisegundos).
    - `eero Network Health` (puntuación de salud de 0 a 100).
    - `eero Connected Clients` (recuento total de dispositivos conectados).
    - `eero Mesh Nodes Online` (número de nodos eero activos).
  - **Seguimiento de Dispositivos (`device_tracker`):**
    - Creación automática de entidades para cada cliente con estados `home` / `not_home`.
    - Atributos completos: IP local, dirección MAC, nodo conectado, banda Wi-Fi y marca temporal `last_seen_connected`.
    - Republicación automática de la configuración en cuanto el equipo adquiere su nombre de host real.
* **Telemetría en Vivo de Alta Frecuencia (`MQTT_LIVE_INTERVAL`):**
  - Permite configurar un intervalo rápido (ej. 5 segundos) para publicar el ancho de banda WAN y clientes activos sin sobrecargar el broker.
* **Fiabilidad y Conectividad:**
  - Compatible con brokers locales y remotos (Mosquitto, EMQX, HiveMQ) con reconexión automática mediante retroceso exponencial.
