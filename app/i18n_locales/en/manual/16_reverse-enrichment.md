---
id: reverse-enrichment
title: 16. Reverse Client Enrichment & IPv6 ULA Discovery
icon: arrows-right-left
summary: Bidirectional secondary interface enrichment from local DNS engines, IPv6 Unique Local Address (ULA) discovery, and Recently Joined clients.
---
### Reverse Client Enrichment & IPv6 ULA Discovery (v1.6.0)

In dual-stack home networks, connected devices frequently query local DNS resolvers (such as AdGuard Home, Pi-hole, Technitium) using **IPv6 ULA** (*Unique Local Address*, prefixes `fc00::/7` and `fd00::/8`). Because this traffic remains strictly on local Layer 2 switches and never traverses the WAN gateway, the eero cloud platform has zero visibility into these ULA assignments.

* **Reverse Client Enrichment via NDP & Ingestion REST:**
  - **Automated Scan Worker:** The background enrichment service regularly inspects the kernel neighbor cache (Neighbor Discovery Protocol - NDP / ARP) and polls local DNS resolver APIs to map orphan ULA addresses back to their physical MAC addresses.
  - **External Ingestion REST API (`POST /api/network/enrichment/neighbors`):** Allows custom cron jobs, sidecar containers, or external script engines to submit live IP-to-MAC associations.
  - **Full-Circle DNS Synchronization:** Discovered ULA addresses are merged into client records and synced back to DNS resolvers, automatically associating bare IP queries with friendly device hostnames.
* **Distinctive UI Badges & Deep Inspection:**
  - The client table and device modal sheet prominently highlight discovered addresses with a magenta/amethyst **`ULA Enriched`** or **`ULA (NDP / AdGuard)`** badge with rich context tooltips.
  - Instant live filtering in the devices table by ULA prefix or complete IPv6 address strings.
* **"Recently Joined" Devices & "NEW" Badge:**
  - The system tracks first discovery timestamps (`first_seen`) within the persistent `known_devices` SQLite table.
  - Newly joined clients in the last 24-48 hours display an eye-catching **`NEW`** badge with an emerald pulsing dot, accompanied by quick "Recently Joined" sorting options.
* **Automated Maintenance & Pruning:**
  - Nightly maintenance tasks periodically prune stale or decommissioned ULA addresses that have not been observed in 30 days, keeping the SQLite database lean and responsive.
