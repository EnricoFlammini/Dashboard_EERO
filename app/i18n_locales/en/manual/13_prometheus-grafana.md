---
id: prometheus-grafana
title: 13. Prometheus Metrics & Grafana Dashboard
icon: presentation-chart-line
summary: Native OpenMetrics scraping (/metrics), exported time-series and ready-to-import Grafana dashboard template.
---
### Prometheus Metrics & Grafana Dashboard (v1.6.0)

The dashboard provides a native **Prometheus / OpenMetrics** export endpoint for centralized homelab observability:

* **Scraping Endpoint:**
  - Directly accessible at `GET /metrics` (or `/api/metrics/prometheus`).
  - Serves the Prometheus text exposition format (`text/plain; version=0.0.4; charset=utf-8`).
* **Exported Metrics Series:**
  - `eero_info`: Metadata, version tag, and active mesh network name.
  - `eero_clients_total`: Client counts tagged with `status="connected"` or `"disconnected"`.
  - `eero_clients_band_total`: Active clients partitioned by band (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` & `eero_wan_upload_mbps`: Real-time aggregated WAN throughput.
  - `eero_wan_ping_ms`: Gateway round-trip latency in milliseconds.
  - `eero_health_score`: Comprehensive health index (0 to 100).
  - `eero_mesh_nodes_total` & `eero_mesh_nodes_online`: Mesh node operational counts.
  - `eero_bufferbloat_grade_numeric` & latency breakdown (`unloaded`, `download`, `upload` in ms).
  - `eero_bandwidth_rx_bytes_total` & `eero_bandwidth_tx_bytes_total`: Monotonic transfer counters.
* **Prebuilt Grafana Dashboard Template:**
  - Ready-to-import dashboard located at `deploy/grafana/eero_dashboard.json`.
  - Features 13 preconfigured panels covering speed gauges, historical bandwidth curves, frequency breakdowns, and mesh node statuses.
