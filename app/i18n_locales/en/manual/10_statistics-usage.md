---
id: statistics-usage
title: 10. Statistics, Device Data Usage & Data Export Center
icon: chart-bar
summary: Device data usage suite, Top Bandwidth Hogs, network distribution charts, and RFC 4180 CSV/JSON export.
---
### Network Analytics, Data Usage & Data Export Center (v1.5.0)

* **Device Data Usage Insights Suite:**
  - Open the **"Data Usage"** tab in any device details modal to inspect bandwidth consumption across 3 distinct time horizons: **Last 24 Hours** (hourly Mbps throughput), **Last 7 Days** (daily totals), and **Last 30 Days** (monthly summary).
  - Dual-line Chart.js telemetry curves with instant KPI pills for Total Download, Total Upload, and Combined Traffic.
  - **Transparent Delta Estimation:** Resilient calculation algorithm designed to handle client sleep, roaming, and hardware counter resets, with a dedicated explanation modal accessible via contextual `?` buttons.
  - **Ethernet Hardware Switching Technical Note:** For wired clients, the `↓ — / ↑ — (Wired)` indicator accurately reflects Layer 2 hardware ASIC switching within eero nodes.
* **"Top Bandwidth Hogs" Widget:**
  - Dedicated dashboard card showcasing top bandwidth consumers over configurable timeframes with 1-click drill-down into device telemetry.
* **Network Statistics & Analytics View:**
  - **Frequency Distribution:** Real-time breakdown across 2.4 GHz, 5 GHz, 6 GHz, and Wired Ethernet.
  - **Mesh Node Load Balancing:** Identifies client distribution across all eero nodes to optimize beacon placement and eliminate coverage bottlenecks.
  - **Device Categories & Hardware Vendors:** Visual breakdown by device type and manufacturer OUI fingerprinting.
  - **Interactive Tooltip with Device Previews:** Hovering over chart bars or donut slices displays an interactive dark popover listing the actual devices contributing to that segment (up to 15 with smart truncation).
  - **ISP SLA & Line Stability Trends:** 7-day and 30-day dual-axis charts tracking throughput consistency, latency trends, and overall line health.
* **Data Export Center (RFC 4180 CSV & Structured JSON):**
  - One-click standard data export for client devices inventory, WAN speedtest logs, wireless RSSI signal samples, and device bandwidth usage for external reporting or Grafana/Home Assistant ingestion.
