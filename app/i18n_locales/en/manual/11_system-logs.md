---
id: system-logs
title: 11. System Logging & Advanced Diagnostics
icon: terminal
summary: Live log viewer console, dynamic log levels (DEBUG/INFO/WARNING/ERROR), retention policies, export and secure clearing.
---
### System Logging & Advanced Diagnostics (v1.6.0)

The **Controls & Guest QR** tab now features Card 7 dedicated to **System Logs & Diagnostics**:

* **Master Logging Switch:**
  - Instant toggle to enable or suspend event logging into the local SQLite database (`system_logs`) and rotating disk file (`data/system.log`).
* **Dynamic Log Levels (Runtime Depth):**
  - Switch log verbosity instantly without restarting the container:
    - `DEBUG`: Verbose. Records detailed API calls, cloud round-trips, and background synchronization events.
    - `INFO`: Normal (default). Records significant network lifecycle events, node states, and device connections.
    - `WARNING`: Alerts. Captures latency spikes, intermittent disconnects, and DNS synchronization warnings.
    - `ERROR`: Critical. Restricts logging strictly to unexpected exceptions and fatal connection failures.
* **Retention Policies:**
  - Configure automatic log lifecycle: **24 Hours (24h)**, **7 Days (7d/7gg)**, **15 Days (15d/15gg)**, **1 Month (1mo/1m)**, or **Custom** (specific day count, or `0` for unlimited).
  - An automated background retention worker purges expired records periodically to safeguard flash storage.
* **Live Log Viewer Console:**
  - Acrylic terminal box styled with monospace typography.
  - Real-time text search filtering by log message or logger module name.
  - Severity chip filters (`ALL`, `DEBUG`, `INFO`, `WARNING`, `ERROR`).
  - Expandable JSON structured details for each log entry (HTTP calls, request parameters, security audits).
  - Optional **Auto-Refresh (10s)** toggle.
* **Export & Maintenance Actions:**
  - **Download Logs:** Export the full log stream in standard RFC 5424 `.log` format or structured `.json`.
  - **Secure Purge (Clear Logs):** RBAC-protected action with confirmation modal to zero disk files and database records.
