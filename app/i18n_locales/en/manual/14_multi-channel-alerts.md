---
id: multi-channel-alerts
title: 14. Multi-Channel Alerts & Emergency Notifications
icon: bell
summary: Multi-channel dispatcher (Telegram, Discord, Webhook, Pushover) and specialized alerts for bufferbloat, mesh quality and security.
---
### Multi-Channel Alerts & Emergency Notifications (v1.6.0)

The notification engine features a unified multi-channel dispatch architecture for critical alerts and network events:

* **Supported Channels:**
  - **Telegram Bot:** Instant HTML-formatted alerts with direct node and client details.
  - **Discord Webhook:** Rich embed cards with color-coded severity bars and structured fields.
  - **Pushover:** High-priority mobile push notifications for immediate delivery.
  - **Generic Webhook:** Raw JSON payloads for custom pipelines (Node-RED, n8n, Home Assistant).
* **Integrated Specialized Alerts:**
  - **Bufferbloat Degradation Warning:** Triggered when loaded latency degrades significantly (Grade D or F, or loaded delta > 100ms).
  - **Mesh Node Signal Anomaly:** Proactive notice on DFS radar interference or weak wireless backhaul.
  - **Authentication Security Alert (Brute-Force):** Security warning upon repeated failed local login attempts from specific IPs.
  - **Nightly Backup Report:** Automated success/failure reporting for database and configuration archives.
