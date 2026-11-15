---
id: device-details
title: 5. Metadatos de Dispositivo, IP Estáticas y Reenvío de Puertos
icon: adjustments
summary: Perfil, nombres personalizados, iconos de categoría, notas locales, reservas DHCP, IPv6 y reenvío de puertos.
---
### Gestión y Configuración de Dispositivos Individuales

* **Modal de Detalles del Dispositivo:**
  - **Nombre y Categoría Personalizada:** Asigne categorías (Ordenador, Móvil, Hogar inteligente, Entretenimiento, Gaming, Servidor/NAS, Otro) almacenadas en la base de datos local SQLite.
  - **Notas y Documentación Local:** Espacio libre para registrar credenciales locales, ubicaciones físicas o puertos de servicios.
  - **Direcciones IPv6 Dual-Stack y Copia en 1 Clic:** Panel dedicado que lista las direcciones SLAAC y Link-Local con botón de copia rápida al portapapeles.
  - **Reserva DHCP (IP Estática):** Asigne una dirección IP fija permanente con detección automática de colisiones y reasignación sencilla.
  - **Reenvío de Puertos y Cortafuegos IPv6:** Configure reglas de reenvío IPv4 (Puerto WAN -> Puerto LAN) y aperturas de cortafuegos IPv6 (pinholes) sobre puertos TCP/UDP del cliente.
  - **Cambio de Perfil:** Reasigne el dispositivo a otro perfil de eero directamente desde la ficha con confirmación inmediata.
  - **Selector Visual de Categorías:** Elija entre iconos representativos con opción de restablecimiento automático según los datos de eero.
  - **Sincronización Inmediata de Caché RAM:** Al guardar los cambios, la caché en memoria del sondeo se actualiza al instante sin esperar al siguiente ciclo.
