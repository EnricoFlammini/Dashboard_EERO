---
id: dashboard-mesh
title: 3. Panel de Control y Topología Mesh
icon: network
summary: Puntuación de salud de red, tarjetas de estado de nodos y acciones rápidas.
---
### Comprensión del Panel de Control Principal

* **Puntuación de Salud de la Red (1-100):** Indicador sintético calculado a partir de la disponibilidad de nodos, presencia de la puerta de enlace y calidad de la señal RSSI de los clientes.
* **Tarjetas de Resumen:**
  - *Estado WAN:* IP pública, proveedor, IPv6, barra de salud y última actualización.
  - *Puerta de Enlace Principal:* Modelo, IP local, subred, DNS, firmware y nodos en línea.
  - *Clientes Conectados:* Total y desglose en 6 GHz / 5 GHz / 2.4 GHz / Cableado, conocidos, invitados y nuevos.
  - *Último Test de Velocidad:* Velocidad de bajada/subida, ping, calificación bufferbloat y gráficos recientes.
* **Topología de Nodos eero:**
  - *Nodo Pasarela (Gateway):* Nodo principal conectado directamente al módem u ONT.
  - *Balizas / Extensores Mesh:* Nodos secundarios que amplían la cobertura inalámbrica.
  - *Tipo de Enlace (Backhaul):* Muestra si la conexión inter-nodo es por cable Ethernet o por enlace inalámbrico dedicado.
* **Acciones Rápidas sobre Nodos:**
  - **Reiniciar Red:** Envía una orden de reinicio controlado a toda la malla eero.
  - **Reiniciar Nodo Individual:** Reinicia únicamente el nodo seleccionado sin interrumpir el resto de la vivienda.
* **Funcionalidades Mesh Avanzadas:**
  - **Extensores Amazon Echo "eero Built-in":** Reconocimiento automático de altavoces Echo compatibles que amplían la red Wi-Fi, con insignia **`eero Built-in`** y recuento de clientes asociados.
  - **Elección de Pasarela en Modo Puente (Bridge):** Identifica con precisión la verdadera puerta de enlace verificando el indicador `is_primary_node` y los vecinos LLDP en el enlace WAN.
  - **Fotografías Oficiales de Dispositivos eero:** Cada nodo muestra la imagen oficial de su modelo de hardware correspondiente (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot, etc.).
  - **Asistente de IA en Streaming y Test de Ubicación:** Diagnóstico interactivo mediante streaming SSE (`/api/network/assistant`), prueba de ubicación por radiofrecuencia (Placement Test) y estado de Guardian VPN.
