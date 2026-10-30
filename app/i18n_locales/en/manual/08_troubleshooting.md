---
id: troubleshooting
title: 8. Troubleshooting, Docker Updates & FAQ
icon: wrench
summary: Frequently asked questions regarding telemetry, in-app Docker auto-updates, security hardening, backups, and maintenance.
---
### Troubleshooting, Docker Updates & FAQ

* **How does In-App 1-Click Docker Auto-Update work (v1.4.0)?**
  - The dashboard automatically checks for new releases on Docker Hub and GitHub Releases.
  - If the Docker Socket is mounted (`/var/run/docker.sock`), clicking "Update Container Now" pulls the latest image, recreates the container preserving your `./data` volume, and reloads the browser once the new version is healthy.
  - Watchtower Webhook triggers and assisted terminal copy commands are also supported.
* **Which client metrics come directly from eero hardware?**
  - The dashboard reads client connection state (Online/Offline), local IP address, MAC Address, connected mesh node (Gateway or Beacon), Wi-Fi frequency band (**2.4 GHz, 5 GHz, 6 GHz, or Wired Ethernet**), wireless channel (**CH**), RSSI signal strength in **dBm**, and negotiated physical rate (**PHY Link Rate**).
* **Security Hardening & Data Protection (v1.5.0 - 4 GHSA Advisories):**
  - **CORS & Anti-CSRF Middleware:** Cross-origin access disabled by default (configured via `CORS_ORIGINS`) and cross-site mutating requests blocked via `Sec-Fetch-Site` inspection.
  - **Wi-Fi Credential Sanitization:** Sensitive Wi-Fi passwords and keys are recursively stripped prior to caching in `/api/network/overview`.
  - **Interactive OpenAPI/Swagger Disabled by Default:** `/docs`, `/redoc`, and `/openapi.json` are only mounted when `API_DOCS=true` to protect operational endpoints.
  - **0600 File Permissions on session.json:** The eero session token file is created with atomic `0600` permissions (owner read/write only).
* **How do I configure the AdGuard Home integration?**
  - Under the *Automations & Controls* tab, enter your instance URL (e.g., `http://192.168.4.100:8085` or `192.168.4.100:8085`), username, and password. Click **Test Connection** and then **Save AdGuard Settings**. Credentials are encrypted and stored safely in the local SQLite database.
* **What should I do if my session expires?**
  - If you encounter authorization errors, click the **Logout** button or re-authenticate from the login modal with a fresh 6-digit OTP code.
* **How do I back up local configurations and custom metadata?**
  - All custom device names, categories, notes, notification settings, signal history, and AdGuard settings are stored in `./data/metrics.db`. To create a complete backup, copy the `./data` directory to your computer or backup storage.
* **Rate Limiting Protection:**
  - The system polls eero cloud at controlled intervals (default 10s-30s) and serves all web client queries directly from RAM, completely eliminating the risk of cloud API blocks.
