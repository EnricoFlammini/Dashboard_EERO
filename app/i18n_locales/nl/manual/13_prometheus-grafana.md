---
id: prometheus-grafana
title: 13. Prometheus-statistieken & Grafana-dashboard
icon: presentation-chart-line
summary: Native OpenMetrics-scraping (/metrics), geëxporteerde tijdreeksen en kant-en-klaar Grafana-sjabloon.
---
### Prometheus-statistieken & Grafana-dashboard

De applicatie biedt een native eindpunt conform de standaarden van **Prometheus / OpenMetrics**:

* **Scraping-eindpunt:**
  - Direct bereikbaar via `GET /metrics` (of `/api/metrics/prometheus`).
  - Levert gegevens in het officiële Prometheus-formaat (`text/plain; version=0.0.4; charset=utf-8`).
* **Beschikbare tijdreeksen:**
  - `eero_info`: Metagegevens, versie en naam van het actieve netwerk.
  - `eero_clients_total`: Apparaten gemarkeerd als `status="connected"` of `"disconnected"`.
  - `eero_clients_band_total`: Clients per frequentieband (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` & `eero_wan_upload_mbps`: Realtime geaggregeerde WAN-doorvoer.
  - `eero_wan_ping_ms`: Gateway-retourtijd in milliseconden.
  - `eero_health_score`: Algemene gezondheidsindex (0 tot 100).
  - `eero_mesh_nodes_total` & `eero_mesh_nodes_online`: Aantal en status van knooppunten.
  - `eero_bufferbloat_grade_numeric` & latentie onder belasting.
  - `eero_bandwidth_rx_bytes_total` & `eero_bandwidth_tx_bytes_total`: Cumulatieve verkeerstellers.
* **Meegeleverd Grafana-sjabloon:**
  - Direct te importeren dashboard via `deploy/grafana/eero_dashboard.json` met 13 vooraf geconfigureerde panelen.
* **Beveiliging & RBAC-toegangscontrole:**
  - Toegang tot `/metrics` vereist het recht `view_topology`.
  - Bij actieve `REQUIRE_LOCAL_AUTH=true` is een geauthenticeerde sessie vereist voor scraping.
