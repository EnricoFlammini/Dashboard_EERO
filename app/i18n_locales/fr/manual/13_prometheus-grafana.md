---
id: prometheus-grafana
title: 13. Métriques Prometheus & Tableau de bord Grafana
icon: presentation-chart-line
summary: Scraping OpenMetrics natif (/metrics), séries temporelles exposées et modèle Grafana prêt à l'emploi.
---
### Métriques Prometheus & Tableau de bord Grafana

L'application expose un point de terminaison natif conforme aux spécifications **Prometheus / OpenMetrics** :

* **Point de terminaison de collecte :**
  - Accessible directement sur `GET /metrics` (ou `/api/metrics/prometheus`).
  - Restitue les métriques au format texte standard Prometheus (`text/plain; version=0.0.4; charset=utf-8`).
* **Séries temporelles exposées :**
  - `eero_info` : Métadonnées, version et nom du réseau actif.
  - `eero_clients_total` : Nombre de clients marqués `status="connected"` ou `"disconnected"`.
  - `eero_clients_band_total` : Clients répartis par bande (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` & `eero_wan_upload_mbps` : Débit WAN agrégé en temps réel.
  - `eero_wan_ping_ms` : Latence aller-retour vers la passerelle.
  - `eero_health_score` : Indice de santé du réseau (0 à 100).
  - `eero_mesh_nodes_total` & `eero_mesh_nodes_online` : Nombre total et état des nœuds.
  - `eero_bufferbloat_grade_numeric` & latences sous charge.
  - `eero_bandwidth_rx_bytes_total` & `eero_bandwidth_tx_bytes_total` : Compteurs cumulés de transfert.
* **Modèle de tableau de bord Grafana inclus :**
  - Modèle prêt à l'importation situé dans `deploy/grafana/eero_dashboard.json` avec 13 panneaux préconfigurés.
* **Sécurité & Authentification RBAC :**
  - L'accès à `/metrics` requiert la permission RBAC `view_topology`.
  - Lorsque `REQUIRE_LOCAL_AUTH=true` est activé, une session authentifiée est requise pour collecter les métriques.
