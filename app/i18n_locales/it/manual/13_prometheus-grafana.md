---
id: prometheus-grafana
title: 13. Metriche Prometheus & Dashboard Grafana
icon: presentation-chart-line
summary: Scraping OpenMetrics nativo (/metrics), time-series esposte e template Grafana preconfigurato.
---
### Metriche Prometheus & Dashboard Grafana (v1.6.0)

La dashboard espone un endpoint nativo conforme alle specifiche **Prometheus / OpenMetrics** per consentire il monitoraggio centralizzato dell'infrastruttura mesh:

* **Endpoint di Scraping:**
  - Accessibile direttamente all'indirizzo `GET /metrics` (o `/api/metrics/prometheus`).
  - Risponde nel formato testuale di esposizione Prometheus (`text/plain; version=0.0.4; charset=utf-8`).
* **Serie Temporali Esposte:**
  - `eero_info`: Metadati della dashboard, versione e nome della rete mesh.
  - `eero_clients_total`: Client rilevati con etichetta `status="connected"` o `"disconnected"`.
  - `eero_clients_band_total`: Client attivi raggruppati per banda (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` & `eero_wan_upload_mbps`: Throughput istantaneo aggregato della WAN.
  - `eero_wan_ping_ms`: Latenza gateway verso l'esterno.
  - `eero_health_score`: Punteggio sintetico di efficienza della rete (0-100).
  - `eero_mesh_nodes_total` & `eero_mesh_nodes_online`: Stato e conteggio dei nodi mesh.
  - `eero_bufferbloat_grade_numeric` & latenze (`unloaded`, `download`, `upload` in ms).
  - `eero_bandwidth_rx_bytes_total` & `eero_bandwidth_tx_bytes_total`: Contatori cumulativi di traffico.
* **Template Dashboard Grafana Incluso:**
  - File pronto all'uso disponibile in `deploy/grafana/eero_dashboard.json`.
  - Comprende 13 pannelli grafici (gauge di salute, grafici di velocità, ripartizione bande Wi-Fi, metriche bufferbloat e stato nodi).
