---
id: prometheus-grafana
title: 13. Métricas Prometheus e Painel Grafana
icon: presentation-chart-line
summary: Scraping nativo OpenMetrics (/metrics), séries temporais exportadas e modelo pré-configurado para o Grafana.
---
### Métricas Prometheus e Painel Grafana

A aplicação disponibiliza um ponto de recolha nativo em conformidade com as normas **Prometheus / OpenMetrics**:

* **Ponto de Recolha de Métricas:**
  - Acessível diretamente em `GET /metrics` (ou `/api/metrics/prometheus`).
  - Devolve dados no formato de texto oficial do Prometheus (`text/plain; version=0.0.4; charset=utf-8`).
* **Séries Temporais Disponíveis:**
  - `eero_info`: Metadados, versão e nome da rede ativa.
  - `eero_clients_total`: Dispositivos marcados como `status="connected"` ou `"disconnected"`.
  - `eero_clients_band_total`: Clientes por banda (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` e `eero_wan_upload_mbps`: Débito WAN agregado em tempo real.
  - `eero_wan_ping_ms`: Latência de ida e volta ao gateway.
  - `eero_health_score`: Índice geral de saúde (0 a 100).
  - `eero_mesh_nodes_total` e `eero_mesh_nodes_online`: Quantidade e estado dos nós mesh.
  - `eero_bufferbloat_grade_numeric` e latências sob carga.
  - `eero_bandwidth_rx_bytes_total` e `eero_bandwidth_tx_bytes_total`: Contadores cumulativos de transferência.
* **Modelo de Painel Grafana Incluído:**
  - Ficheiro pronto a importar em `deploy/grafana/eero_dashboard.json` com 13 painéis pré-configurados.
* **Segurança e Controlo de Acesso RBAC:**
  - O acesso ao endereço `/metrics` requer a permissão `view_topology`.
  - Com a definição `REQUIRE_LOCAL_AUTH=true` ativada, a recolha de métricas exige uma sessão autenticada.
