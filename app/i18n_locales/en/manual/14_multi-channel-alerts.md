---
id: multi-channel-alerts
title: 14. Multi-Channel Alerts & Emergency Notifications
icon: bell
summary: Multi-channel dispatcher (Telegram, Discord, Webhook, Pushover, Ntfy, Apprise for Microsoft Teams, Slack, Google Chat and Gotify) and specialized alerts for bufferbloat, mesh quality and security.
---
### Multi-Channel Alerts & Emergency Notifications (v1.6.0)

The notification engine features a unified multi-channel dispatch architecture for critical alerts and network events:

* **Supported Channels:**
  - **Telegram Bot:** Instant HTML-formatted alerts with direct node and client details.
  - **Discord Webhook:** Rich embed cards with color-coded severity bars and structured fields.
  - **Pushover:** High-priority mobile push notifications for immediate delivery.
  - **Generic Webhook:** Raw JSON payloads for custom pipelines (Node-RED, n8n, Home Assistant).
  - **Ntfy:** Push notifications through ntfy.sh or a self-hosted ntfy server.
  - **Apprise:** One setting that reaches Microsoft Teams, Slack, Google Chat, Gotify and 100+ other services (see below).
* **Integrated Specialized Alerts:**
  - **Bufferbloat Degradation Warning:** Triggered when loaded latency degrades significantly (Grade D or F, or loaded delta > 100ms).
  - **Mesh Node Signal Anomaly:** Proactive notice on DFS radar interference or weak wireless backhaul.
  - **Authentication Security Alert (Brute-Force):** Security warning upon repeated failed local login attempts from specific IPs.
  - **Nightly Backup Report:** Automated success/failure reporting for database and configuration archives.

### Apprise: Microsoft Teams, Slack, Google Chat, Gotify and more (v1.8.0)

[Apprise](https://github.com/caronc/apprise) is a notification library bundled with the dashboard. It runs inside the app and posts directly to each service, so it needs no extra server or account. Enable it in **Notifications** and enter one or more Apprise URLs, separated by commas or spaces. They can also be set with the `APPRISE_URLS` environment variable. The URLs are masked (`••••••••`) once saved, and **Test** sends a test message to every configured service.

Alerts keep their severity: warnings, failures and recoveries show matching icons and colours, and bold text, code values and lists are converted to each service's formatting.

* **Microsoft Teams:** paste the Workflows webhook URL exactly as Teams gives it (a `powerplatform.com` or `logic.azure.com` address).
  - Create the webhook **from Teams**: on the channel or chat, open **⋯ → Workflows** and choose **Send webhook alerts to a channel** (or **to a chat**). This produces a signed URL ending in `&sig=…`.
  - Flows built in the Power Automate designer may only offer *Any user in my tenant*. That setting needs an OAuth token, which Apprise cannot provide, so those URLs are rejected with HTTP 401.
  - For personal alerts, post to **Chat with Flow bot** with yourself as recipient. Teams lists your "(You)" self-chat as a destination, but posts to it fail ("not a ChatThread").
* **Slack:** `slack://TokenA/TokenB/TokenC/#channel`, built from an incoming-webhook URL. A full `https://hooks.slack.com/services/…` URL also works.
* **Google Chat:** paste the space's webhook URL (`https://chat.googleapis.com/v1/spaces/…`).
* **Gotify:** `gotify://your-server/AppToken` (or `gotifys://` for HTTPS).
* **Other services:** every other Apprise URL format is supported on a best-effort basis. See the [Apprise wiki](https://github.com/caronc/apprise/wiki) for the full list.
