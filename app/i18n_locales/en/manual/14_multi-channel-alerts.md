---
id: multi-channel-alerts
title: 14. Multi-Channel Alerts & Emergency Notifications
icon: bell
summary: Multi-channel dispatcher (Telegram, Discord, Webhook, Pushover) and specialized alerts for bufferbloat, mesh quality and security.
---
### Multi-Channel Alerts & Emergency Notifications

The notification engine features a unified multi-channel dispatch architecture for critical alerts and network events:

* **Supported Channels:**
  - **Telegram Bot:** Instant HTML-formatted alerts with direct node and client details.
  - **Discord Webhook:** Rich embed cards with color-coded severity bars and structured fields.
  - **Pushover:** High-priority mobile push notifications for immediate delivery.
  - **Native Ntfy (sh):** Public `ntfy.sh` or self-hosted server dispatch with priority tags and bearer token authentication.
  - **Generic Webhook:** Raw JSON payloads for custom pipelines (Node-RED, n8n, Home Assistant).
* **Visual UI Controls & Secret Masking:**
  - All channels include dedicated UI configuration cards under *Settings -> Controls* with instant **Test Message** buttons.
  - Bot tokens and webhook URLs are masked with `••••••••` to prevent credential leakage.
* **Integrated Specialized Alerts:**
  - **Bufferbloat Degradation Warning:** Triggered when loaded latency degrades significantly (Grade D or F, or loaded delta > 100ms).
  - **Mesh Node Signal Anomaly:** Proactive notice on DFS radar interference or weak wireless backhaul.
  - **Authentication Security Alert (Brute-Force):** Security warning upon repeated failed local login attempts from specific IPs.
  - **Nightly Backup Report:** Automated success/failure reporting for database and configuration archives.
