---
id: prometheus-grafana
title: 13. Métricas de Prometheus y Panel de Grafana
icon: presentation-chart-line
summary: Scraping nativo OpenMetrics (/metrics), series temporales expuestas y plantilla de Grafana preconfigurada.
---
### Métricas de Prometheus y Panel de Grafana

La aplicación expone un punto de enlace nativo conforme a los estándares **Prometheus / OpenMetrics**:

* **Punto de Enlace de Métricas:**
  - Accesible directamente en `GET /metrics` (o `/api/metrics/prometheus`).
  - Devuelve las métricas en formato de texto estándar (`text/plain; version=0.0.4; charset=utf-8`).
* **Series Temporales Disponibles:**
  - `eero_info`: Metadatos, versión y nombre de la red activa.
  - `eero_clients_total`: Dispositivos etiquetados como `status="connected"` o `"disconnected"`.
  - `eero_clients_band_total`: Clientes por frecuencia (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` y `eero_wan_upload_mbps`: Ancho de banda WAN agregado en tiempo real.
  - `eero_wan_ping_ms`: Latencia de ida y vuelta a la pasarela.
  - `eero_health_score`: Índice integral de salud (0 a 100).
  - `eero_mesh_nodes_total` y `eero_mesh_nodes_online`: Estado y número de nodos mesh.
  - `eero_bufferbloat_grade_numeric` y latencias bajo carga.
  - `eero_bandwidth_rx_bytes_total` y `eero_bandwidth_tx_bytes_total`: Contadores acumulados de tráfico.
* **Plantilla de Grafana Incluida:**
  - Archivo listo para importar en `deploy/grafana/eero_dashboard.json` con 13 paneles visuales prediseñados.
* **Seguridad y Control de Acceso RBAC:**
  - El acceso a `/metrics` requiere el permiso `view_topology`.
  - Cuando `REQUIRE_LOCAL_AUTH=true` está habilitado, las solicitudes exigen una sesión autenticada.
