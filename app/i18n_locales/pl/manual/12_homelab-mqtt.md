---
id: homelab-mqtt
title: 12. Integracja HomeLab przez MQTT i Home Assistant
icon: home
summary: Asynchroniczny klient MQTT, automatyczne wykrywanie w Home Assistant, telemetria na żywo i encje device_tracker.
---
### Integracja HomeLab przez MQTT i Wykrywanie w Home Assistant

Aplikacja integruje się bezpośrednio z systemami automatyki domowej za pośrednictwem protokołu MQTT:

* **Automatyczne Wykrywanie Home Assistant (MQTT Auto-Discovery):**
  - Zgodna z oficjalnymi standardami publikacja encji pod skonfigurowanym prefiksem (domyślnie `homeassistant/`).
  - **Sensory Sieciowe:**
    - `eero WAN Download` i `eero WAN Upload` (standardowa jednostka `Mbit/s` z klasą `data_rate`).
    - `eero WAN Ping` (opóźnienie w milisekundach).
    - `eero Network Health` (ogólna ocena kondycji 0-100).
    - `eero Connected Clients` (liczba połączonych klientów).
    - `eero Mesh Nodes Online` (liczba sprawnych węzłów eero).
  - **Śledzenie Obecności Urządzeń (`device_tracker`):**
    - Tworzenie encji dla każdego urządzenia ze stanem `home` / `not_home`.
    - Szczegółowe atrybuty: lokalny IP, MAC, powiązany węzeł, pasmo Wi-Fi oraz znacznik czasu `last_seen_connected`.
    - Automatyczna ponowna publikacja konfiguracji w momencie ustalenia właściwej nazwy hosta.
* **Telemetria na Żywo o Wysokiej Częstotliwości (`MQTT_LIVE_INTERVAL`):**
  - Osobny, krótki interwał (np. 5 sekund) do publikacji przepustowości WAN i liczby klientów bez obciążania brokera.
* **Niezawodność i Ponowne Łączenie:**
  - Obsługa lokalnych i zdalnych brokerów (Mosquitto, EMQX, HiveMQ) z automatycznym wznawianiem połączenia.
