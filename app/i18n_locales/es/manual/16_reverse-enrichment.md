---
id: reverse-enrichment
title: 16. Enriquecimiento Inverso de Clientes y Descubrimiento IPv6 ULA
icon: arrows-right-left
summary: Enriquecimiento bidireccional desde DNS locales, descubrimiento de direcciones IPv6 ULA y control de nuevos clientes.
---
### Enriquecimiento Inverso de Clientes y Descubrimiento IPv6 ULA

En redes de doble pila, los dispositivos suelen consultar servidores DNS locales mediante direcciones **IPv6 ULA** (*Unique Local Address*, prefijos `fc00::/7` y `fd00::/8`). Al ser tráfico de Capa 2 confinado a la red interna, la nube de eero no tiene visibilidad sobre ellas.

* **Reverse Client Enrichment vía NDP e Ingesta REST:**
  - **Proceso de sondeo automático:** Consulta periódicamente la tabla de vecinos del sistema (NDP / ARP) y los servidores DNS locales para asociar direcciones ULA a sus correspondientes direcciones MAC.
  - **API de Ingesta Externa (`POST /api/network/enrichment/neighbors`):** Permite a scripts y contenedores complementarios enviar asociaciones IP-MAC en tiempo real.
  - **Sincronización Bidireccional:** Las direcciones detectadas se incorporan a los registros y se devuelven a los servidores DNS, vinculando las consultas al nombre reconocible del dispositivo.
* **Distintivo Visual e Inspección Detallada:**
  - Los clientes enriquecidos muestran la etiqueta violeta **`ULA Enriched`** en la tabla y en la ficha de detalle.
* **Dispositivos Recientes e Insignia "NEW":**
  - Se registra la fecha del primer avistamiento (`first_seen`) de cada cliente.
  - Los equipos detectados en las últimas 24 a 48 horas se resaltan con la insignia verde esmeralda **`NEW`**.
* **Mantenimiento y Purga Automática:**
  - Un proceso nocturno retira las direcciones ULA inactivas tras 30 días para optimizar la base de datos SQLite.
