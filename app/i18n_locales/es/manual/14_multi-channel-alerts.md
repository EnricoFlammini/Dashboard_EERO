---
id: multi-channel-alerts
title: 14. Alertas Multicanal y Notificaciones de Emergencia
icon: bell
summary: Despachador multicanal (Telegram, Discord, Webhook, Pushover, Ntfy) y alertas especializadas.
---
### Alertas Multicanal y Notificaciones de Emergencia

El gestor de notificaciones admite el envío multicanal de eventos críticos de red:

* **Canales Compatibles:**
  - **Bot de Telegram:** Avisos inmediatos en formato HTML con información detallada de nodos y dispositivos.
  - **Webhook de Discord:** Notificaciones ricas con tarjetas visuales y colores según la gravedad.
  - **Pushover:** Avisos push prioritarios para dispositivos móviles.
  - **Ntfy (sh) Nativo:** Soporte para servidores `ntfy.sh` o instancias autoalojadas con prioridades y autenticación por token.
  - **Webhook Genérico:** Envío de cargas JSON para integraciones personalizadas (Node-RED, n8n, Home Assistant).
* **Controles Visuales y Ocultación de Claves:**
  - Paneles de configuración en *Ajustes -> Controles* con botón de **Prueba Inmediata**.
  - Ocultación de tokens y URLs como `••••••••` para evitar exposición involuntaria de contraseñas.
* **Alertas Especializadas:**
  - **Degradación de Bufferbloat:** Notificación si la latencia bajo carga empeora de forma acusada.
  - **Anomalías en Nodos Mesh:** Avisos por interferencias radar DFS o deterioro del enlace inalámbrico.
  - **Dispositivo Desconocido Conectado:** Aviso inmediato cuando un nuevo equipo accede a la red.
  - **Nodo Desconectado:** Alerta urgente si un punto de acceso eero pierde la conexión.
