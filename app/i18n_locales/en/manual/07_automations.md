---
id: automations
title: 7. Automations, Guest QR, AdGuard Home, Telegram & Notifications
icon: zap
summary: Smart Guest Wi-Fi with QR, native AdGuard Home sync, Telegram/Webhook alerts with toggle, and Daily Digest.
---
### Advanced Features & Automations Hub

The **Controls & Guest QR** tab organizes your network tools into a clean 2x2 grid of four cards, plus a fifth item, Gaming Mode, located in the top header:

1. **Smart Guest Wi-Fi with Dual-Theme Dynamic QR Code (Top-Left):**
   - Instantly renders a printable, scannable QR Code with pure white background for Light Mode and dark slate for Dark Mode, automatically synchronized with the active theme.
   - One-click toggle to enable or disable the guest network at any time.
   - Built-in secure password generator and credentials updater.
2. **Multi-Engine DNS Synchronizer (Top-Right):**
   - **Heterogeneous Multi-Engine Support:** Simultaneous management of multiple instances across AdGuard Home, Pi-hole (v5 & v6 REST API), and Technitium DNS (direct A and Reverse PTR records).
   - **Continuous Background Auto-Sync:** Automatically registers newly discovered devices into all active DNS servers.
   - **Intelligent Address Pruning & IPv6 Exclusions (v1.5.0, v1.6.1):** Dedicated per-instance options to automatically prune obsolete IPs and expired leases (covering Pi-hole v6 atomic `PATCH /api/config` as well), with automatic LAN subnet prioritization over Docker virtual bridge gateways (`172.17.x.x`). Includes per-device *"Exclude from DNS Sync"* toggle (`dns_sync_excluded`) in the device modal.
   - **Individual & Global Test and Sync:** Quickly test individual or all instances, with instant 1-click manual synchronization.
   - **Standard Export Endpoints:** `/api/devices/export/hosts` (/etc/hosts text) and `/api/devices/export/adguard` (JSON provisioning).
3. **Telegram Bot & Webhook Notifications (Bottom-Left):**
   - **Persistent Known Devices Registry:** SQLite `known_devices` table tracking previously discovered MACs to prevent duplicate alerts on container restarts.
   - **Dedicated Activation Toggle:** Enable or disable Telegram notifications with one click while safely preserving your Bot Token and Chat ID.
   - **New Device Alert:** Receive an instant alert when an unknown MAC address connects to your mesh.
   - **Mesh Node Offline:** Immediate notification if any eero node loses connectivity.
   - **"Send Test" Button:** Instantly tests message delivery to your Telegram bot and Webhook URL.
4. **Daily Digest Report (Bottom-Right):**
   - **Scheduled Dispatch Toggle & Configurable Hour (v1.6.1):** Enable or suspend the automatic summary and customize dispatch hour (00:00 - 23:00, default 21:00) with `DAILY_DIGEST_HOUR` and `TZ` support.
   - **Restart Idempotency Protection:** Persistent SQLite tracking of `last_daily_digest_date` ensuring exactly one dispatch per calendar day across container restarts.
   - Automated report containing: Network Health Score, ISP, online mesh nodes, active clients breakdown by frequency band (**6 GHz, 5 GHz, 2.4 GHz, Ethernet**), Gateway Speed Test and Ping latency.
   - **"Generate & Send Digest Now"** button for immediate on-demand dispatch.
5. **One-Click Gaming / Focus Mode (Low Latency):**
   - Located in the top header: pauses tagged background streaming/downloading devices with a single click to eliminate latency and jitter for competitive gaming setups.
