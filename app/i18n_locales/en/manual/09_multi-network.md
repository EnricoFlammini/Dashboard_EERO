---
id: multi-network
title: 9. Multi-Network Fleet Management & Hot-Swap
icon: globe
summary: Multi-location eero account support, instant in-app switching, and network election persistence.
---
### Multi-Network Fleet Management

* **Dynamic Header Dropdown Selector (Windows 11 Fluent):** If your eero account manages multiple networks or physical locations (e.g., Main Residence, Office, Vacation Home), the dashboard header automatically displays an interactive dropdown showing mesh node and active client counts for each location.
* **Instant In-Memory Hot-Swap:** Selecting another network switches the dashboard immediately without restarting the Docker container or prompting for new 2FA credentials. The RAM cache is immediately flushed and refreshed, updating all widgets and tables in real time.
* **Network Election Persistence:** The chosen active network is stored in `session.json` and local SQLite `app_settings`, ensuring periodic polling cycles never force-reset your selection and that preferences survive container restarts.
* **Demo Mode Support:** Includes an independent dual-network simulated fleet (*Casa Rossi Mesh 6E* and *Office & Studio Pro Mesh*) to demonstrate fleet capabilities without needing an active live account.
* **Active Network Architecture & Concurrency:** The hot-swap switch alternates the active network globally for the entire server instance. In current homelab setups, monitoring multiple locations concurrently side-by-side or in separate browser tabs is easily achieved by running two lightweight Docker containers mapped to separate host ports; native single-instance multi-tenancy is scheduled for future platform updates.
