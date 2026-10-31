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
* **Wi-Fi Signal Quality & Mesh Coverage (v1.4.0):**
  - **Historical RSSI Logging (dBm):** The background poller continuously samples wireless signal levels, frequencies, and link rates into local SQLite (`device_signal_history`).
  - **Household Average Signal & Quality Bands:** High-level KPI and percentage breakdown across *Excellent* (≥ -50 dBm), *Good* (-51 to -65 dBm), *Fair* (-66 to -75 dBm), and *Critical* (< -75 dBm).
  - **Interactive Chart.js Time-Series:** Select any client to analyze signal trends over the past 24 hours or 7 days with current, min, max, and average RSSI.
  - **Weak Signal Watchlist:** Filtered table of devices with marginal signal along with actionable mesh node repositioning suggestions.
