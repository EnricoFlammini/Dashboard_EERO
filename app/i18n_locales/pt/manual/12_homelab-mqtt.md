---
id: homelab-mqtt
title: 12. Integração HomeLab via MQTT e Home Assistant
icon: home
summary: Cliente MQTT assíncrono, Auto-Discovery do Home Assistant, telemetria em tempo real e entidades device_tracker.
---
### Integração HomeLab via MQTT e Deteção no Home Assistant

O sistema integra-se de forma nativa com ambientes de domótica através do protocolo MQTT:

* **Deteção Automática no Home Assistant (MQTT Auto-Discovery):**
  - Publicação de acordo com os padrões oficiais sob o prefixo configurado (por omissão `homeassistant/`).
  - **Sensores de Rede:**
    - `eero WAN Download` e `eero WAN Upload` (unidade padronizada em `Mbit/s` com classe `data_rate`).
    - `eero WAN Ping` (latência em milissegundos).
    - `eero Network Health` (índice de saúde de 0 a 100).
    - `eero Connected Clients` (total de equipamentos ligados).
    - `eero Mesh Nodes Online` (número de nós eero operacionais).
  - **Seguimento de Presença (`device_tracker`):**
    - Criação automática de entidades para cada cliente com estado `home` / `not_home`.
    - Atributos completos: IP local, endereço MAC, nó ligado, banda Wi-Fi e marca temporal `last_seen_connected`.
    - Republicação automática da configuração assim que o dispositivo obtém o seu nome de rede definitivo.
* **Telemetria em Direto de Alta Frequência (`MQTT_LIVE_INTERVAL`):**
  - Permite definir um intervalo rápido independente (ex.: 5 segundos) para publicar o tráfego WAN e clientes sem sobrecarregar o broker.
* **Fiabilidade e Religação:**
  - Compatível com brokers locais e remotos (Mosquitto, EMQX, HiveMQ) com religação automática por recuo exponencial.
