---
id: system-logs
title: 11. Registros del Sistema y Diagnóstico Avanzado
icon: terminal
summary: Consola de logs en directo, niveles de detalle dinámicos, retención, exportación y vaciado seguro.
---
### Gestión de Registros del Sistema y Diagnóstico Avanzado

El panel **Gestión de Registros y Diagnóstico** proporciona supervisión total de la actividad:

* **Interruptor General (Master Switch):** Habilita o pausa el registro de eventos en la base SQLite local y en el archivo rotativo en disco (`data/system.log`).
* **Niveles de Detalle Dinámicos sin Reinicio:**
  - `DEBUG`: Registro exhaustivo de todas las peticiones a la API y sincronizaciones.
  - `INFO`: Seguimiento normal de eventos relevantes y conexiones de clientes.
  - `WARNING`: Avisos de degradación de latencia o anomalías de señal.
  - `ERROR`: Restringido exclusivamente a excepciones críticas y fallos de comunicación.
* **Periodo de Retención Automático:** Configure la duración del historial: 24h, 7 días, 15 días, 1 mes o plazo personalizado (con purga periódica en segundo plano).
* **Consola de Registros en Vivo:** Terminal de alta visibilidad con tipografía monoespaciada, búsqueda de texto completo, filtros por severidad y refresco automático cada 10 segundos.
* **Herramientas de Exportación y Vaciado:** Descarga en formato de texto plano `.log` o estructurado `.json`, y botón de borrado seguro protegido por permisos RBAC.
