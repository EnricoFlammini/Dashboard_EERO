---
id: prometheus-grafana
title: 13. Prometheus-Metriken & Grafana-Dashboard
icon: presentation-chart-line
summary: Natives OpenMetrics-Scraping (/metrics), exportierte Zeitreihen und vorgefertigte Grafana-Vorlage.
---
### Prometheus-Metriken & Grafana-Dashboard

Die Anwendung stellt einen nativen Endpunkt gemäß den Spezifikationen von **Prometheus / OpenMetrics** bereit:

* **Scraping-Endpunkt:**
  - Direkt erreichbar unter `GET /metrics` (oder `/api/metrics/prometheus`).
  - Liefert Daten im Standard-Prometheus-Textformat (`text/plain; version=0.0.4; charset=utf-8`).
* **Verfügbare Zeitreihen:**
  - `eero_info`: Metadaten, Versionsnummer und Name des aktiven Netzwerks.
  - `eero_clients_total`: Anzahl der Geräte mit Status `status="connected"` oder `"disconnected"`.
  - `eero_clients_band_total`: Aktive Clients nach Frequenzband (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` & `eero_wan_upload_mbps`: Aggregierter WAN-Echtzeitdurchsatz.
  - `eero_wan_ping_ms`: Gateway-Rundlaufzeit in Millisekunden.
  - `eero_health_score`: Gesamter Gesundheitswert (0 bis 100).
  - `eero_mesh_nodes_total` & `eero_mesh_nodes_online`: Anzahl und Status der Netzknoten.
  - `eero_bufferbloat_grade_numeric` & Latenzwerte unter Last.
  - `eero_bandwidth_rx_bytes_total` & `eero_bandwidth_tx_bytes_total`: Kumulierte Übertragungszähler.
* **Mitgelieferte Grafana-Dashboard-Vorlage:**
  - Sofort importierbare Vorlage unter `deploy/grafana/eero_dashboard.json` mit 13 vorgefertigten Visualisierungen.
* **Sicherheit & RBAC-Zugriffskontrolle:**
  - Der Zugriff auf `/metrics` erfordert die Berechtigung `view_topology`.
  - Bei aktiver Option `REQUIRE_LOCAL_AUTH=true` ist eine authentifizierte Sitzung für das Scraping erforderlich.
