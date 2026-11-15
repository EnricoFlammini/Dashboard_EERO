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
* **Authentication & RBAC Security (v1.7.0):**
  - The `/metrics` endpoint is protected by the `view_topology` RBAC permission.
  - When `REQUIRE_LOCAL_AUTH=true` is enabled (Security Advisory GHSA-r5vj-jfjp-m88q), requests to `/metrics` require an authenticated local session. In homelab environments where the Prometheus scraper does not support session cookies, keep `REQUIRE_LOCAL_AUTH=false` (relying on network-level firewall or reverse proxy access control) or forward requests through an authenticated reverse proxy.
