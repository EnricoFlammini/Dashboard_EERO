---
id: prometheus-grafana
title: 13. Metryki Prometheus i Pulpit Grafana
icon: presentation-chart-line
summary: Natywny scraping OpenMetrics (/metrics), eksportowane serie czasowe i gotowy szablon pulpitu Grafana.
---
### Metryki Prometheus i Pulpit Grafana

Aplikacja udostępnia natywny punkt końcowy zgodny ze specyfikacją **Prometheus / OpenMetrics**:

* **Punkt Pobierania Metryk:**
  - Dostępny bezpośrednio pod adresem `GET /metrics` (lub `/api/metrics/prometheus`).
  - Dane zwracane w oficjalnym formacie tekstowym Prometheus (`text/plain; version=0.0.4; charset=utf-8`).
* **Dostępne Serie Czasowe:**
  - `eero_info`: Metadane, wersja i nazwa aktywnej sieci.
  - `eero_clients_total`: Liczba urządzeń ze statusem `status="connected"` lub `"disconnected"`.
  - `eero_clients_band_total`: Klienci według pasma (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` i `eero_wan_upload_mbps`: Zagregowana przepustowość WAN w czasie rzeczywistym.
  - `eero_wan_ping_ms`: Czas odpowiedzi bramy w milisekundach.
  - `eero_health_score`: Ogólny wskaźnik sprawności sieci (0 do 100).
  - `eero_mesh_nodes_total` i `eero_mesh_nodes_online`: Liczba i stan węzłów mesh.
  - `eero_bufferbloat_grade_numeric` oraz opóźnienia pod obciążeniem.
  - `eero_bandwidth_rx_bytes_total` i `eero_bandwidth_tx_bytes_total`: Narastające liczniki transferu.
* **Dołączony Szablon Pulpitu Grafana:**
  - Gotowy do zaimportowania plik w katalogu `deploy/grafana/eero_dashboard.json` zawierający 13 paneli diagnostycznych.
* **Bezpieczeństwo i Uprawnienia RBAC:**
  - Dostęp do punktu `/metrics` wymaga uprawnienia `view_topology`.
  - Gdy włączona jest opcja `REQUIRE_LOCAL_AUTH=true`, do pobrania metryk wymagana jest uwierzytelniona sesja.
