---
id: automations
title: 7. Automatizaciones, QR Invitados, AdGuard Home, Telegram y Notificaciones
icon: zap
summary: Wi-Fi de invitados dinámico con QR, sincronización DNS AdGuard Home, alertas Telegram/Webhook y resumen diario.
---
### Centro de Automatizaciones y Funciones Avanzadas

La pestaña **Controles y QR Invitados** organiza las herramientas en paneles modulares:

1. **Smart Wi-Fi de Invitados con Código QR Dinámico:**
   - Generación instantánea de código QR imprimible adaptado al tema activo (fondo claro para modo día, pizarra oscura para modo noche).
   - Interruptor para habilitar o deshabilitar la red de invitados en 1 clic con generador seguro de contraseñas.
2. **Sincronizador DNS Multimotor:**
   - **Compatibilidad con múltiples instancias heterogéneas:** Gestión simultánea de AdGuard Home, Pi-hole (v5 y v6) y Technitium DNS.
   - **Sincronización continua automática:** Alinea los nombres de host y reservas de IP al detectar nuevos dispositivos.
   - **Limpieza inteligente de direcciones y DNS personalizado:** Resolución de conflictos de concesiones reasignadas, saneamiento RFC 1123 y soporte **Custom y Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) con prioridad IPv4 (`AF_INET`).
   - **Exclusión por dispositivo:** Interruptor individual *"Excluir de sincronización DNS"* en la ficha del equipo.
3. **Alertas Telegram y Webhooks:**
   - **Registro persistente y protección contra avalanchas:** Aislamiento de direcciones MAC de prueba para evitar falsas notificaciones al inicio.
   - **Nuevo dispositivo conectado:** Alerta instantánea cuando un equipo no registrado se conecta a la red.
   - **Nodo Mesh desconectado:** Notificación inmediata en caso de desconexión de cualquier unidad eero.
4. **Resumen Diario (Daily Digest):**
   - Envío automático a la hora configurada (por defecto 21:00) con puntuación de salud, estado de conexión, clientes y último test de velocidad.
5. **Modo Gaming y Concentración (Baja Latencia):**
   - Pausa con un solo clic el tráfico de dispositivos secundarios para eliminar la latencia en sesiones de juego o videollamadas.
6. **Reglas de Cortafuegos IPv6 Pinhole:**
   - Gestión visual para abrir o cerrar puertos TCP/UDP en clientes IPv6 específicos.
