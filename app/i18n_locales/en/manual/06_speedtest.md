---
id: speedtest
title: 6. Speed Test, Performance Diagnostics & Wi-Fi Signal Quality
icon: gauge
summary: On-demand speed testing, historical performance tracking, RSSI signal analytics, and mesh coverage.
---
### Performance Diagnostics & Wi-Fi Coverage

* **Manual Speed Test:** Click **"Start Speedtest"** to trigger a real-time measurement of Download, Upload, Ping/Latency, and Jitter.
* **Automated Scheduled Testing:** The system can be scheduled to run automated background tests (e.g., every 12 hours) to track line consistency over time.
* **Historical Charts & Statistics:**
  - Visual time-series graph of speeds and latency over days and weeks.
  - Aggregate statistics including average download/upload, maximum peak speeds, and average ping.
* **Wi-Fi Signal Quality & Mesh Coverage:**
  - **Historical RSSI Logging & Universal dBm Parsing:** The background poller continuously samples wireless signal levels, normalizing strings with units (`"-78 dBm"`), floats, and nested structures into clean integer dBm values in `[-120, -1]`.
  - **Household Average Signal & Quality Bands:** High-level KPI and percentage breakdown across *Excellent* (≥ -50 dBm), *Good* (-51 to -65 dBm), *Fair* (-66 to -75 dBm), and *Critical* (< -75 dBm).
  - **Instant Live Fallback & Weak Signal Watchlist:** Merges active wireless clients directly from poller RAM cache so overview KPIs and the **Weak Signal Watchlist** (`< -75 dBm`) populate immediately on startup before historical aggregation.
  - **Interactive Chart.js Time-Series:** Select any client to analyze signal trends over the past 24 hours or 7 days with current, min, max, and average RSSI, backed by reactive Alpine `:selected` option binding.
  - **3-Stage SQLite Self-Repair Engine:** Transparent self-healing (`repair_if_malformed`) that automatically reindexes, recreates tables, or reconstructs corrupt database files without losing user settings or device customizations.
