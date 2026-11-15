---
id: multi-network
title: 9. Gestión Multirred y Cambio en Caliente
icon: globe
summary: Compatibilidad con cuentas eero multisitio, conmutación instantánea y persistencia de red seleccionada.
---
### Gestión Multirred y Cambio en Caliente

* **Selector Dinámico en Encabezado (Windows 11 Fluent):** Si su cuenta gestiona varias redes eero (ej. Casa principal, Oficina, Segunda residencia), un menú desplegable muestra el número de nodos y clientes activos en cada ubicación.
* **Conmutación Instantánea en Memoria:** Al seleccionar otra red, la interfaz cambia al instante sin reiniciar el contenedor ni solicitar credenciales. La caché en RAM se renueva en tiempo real.
* **Persistencia de la Red Seleccionada:** La red activa se conserva en `session.json` y en la base de datos local SQLite, manteniéndose tras los reinicios.
* **Soporte en Modo Demo:** Incluye una flota simulada con dos entornos (*Casa Rossi Mesh 6E* y *Oficina Pro Mesh*) para probar la gestión multirred.
* **Arquitectura de Red Activa y Concurrencia:** El cambio afecta globalmente a la instancia del servidor. Para supervisar simultáneamente varias ubicaciones en paralelo, se pueden ejecutar dos contenedores Docker independientes en puertos distintos.
