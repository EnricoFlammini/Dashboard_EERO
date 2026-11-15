---
id: homelab-mqtt
title: 12. Intégration HomeLab via MQTT & Home Assistant
icon: home
summary: Client MQTT asynchrone, Auto-Discovery Home Assistant, télémétrie en temps réel et entités device_tracker.
---
### Intégration HomeLab via MQTT & Découverte Home Assistant

La suite s'intègre nativement à votre environnement domotique via le protocole MQTT :

* **Découverte automatique Home Assistant (MQTT Auto-Discovery) :**
  - Publication automatique conforme aux spécifications officielles de Home Assistant sous le préfixe configuré (par défaut `homeassistant/`).
  - **Capteurs d'état du réseau :**
    - `eero WAN Download` & `eero WAN Upload` (débit standardisé en `Mbit/s` avec classe `data_rate`).
    - `eero WAN Ping` (latence en millisecondes).
    - `eero Network Health` (score synthétique de 0 à 100).
    - `eero Connected Clients` (nombre total de clients connectés).
    - `eero Mesh Nodes Online` (nombre de nœuds eero opérationnels).
  - **Suivi de présence des appareils (`device_tracker`) :**
    - Création automatique d'une entité pour chaque équipement du réseau avec état `home` / `not_home`.
    - Attributs complets : IP locale, adresse MAC, nœud de connexion, bande Wi-Fi et horodatage `last_seen_connected`.
    - Réactualisation automatique de la configuration discovery dès qu'un appareil acquiert son nom d'hôte définitif.
* **Télémétrie en direct à haute fréquence (`MQTT_LIVE_INTERVAL`) :**
  - Permet d'ajuster un intervalle rapide dédié (ex. 5 secondes) pour publier les débits WAN et le nombre de clients sans surcharger le broker.
* **Fiabilité & Reconnexion :**
  - Prise en charge des brokers locaux et distants (Mosquitto, EMQX, HiveMQ) avec reconnexion automatique par backoff exponentiel.
