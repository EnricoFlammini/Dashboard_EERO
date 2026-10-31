# Changelog - Release Summary

Below is a summary of the main release highlights. The complete changelog with all technical details is available on GitHub.

## v1.6.2
* **Complete Frontend & Backend Translation Parity (PR #79 - @todddube):** 100% key parity across all linguistic catalogs (457 backend keys and 1051 frontend keys in `en.json` and `it.json`), automated parity audit and CI/CD validation.
* **RFC 1123 Hostname Sanitization for Pi-hole v6 & Silenced 404 Endpoint Probe (Issue #83 - @richlilly2004):** Strict RFC 1123 hostname sanitization for Pi-hole v6 sync (converting parentheses and special characters to hyphens) and removal of redundant `/port_forwards` API probes.
* **Resilient MQTT Configuration Save & Load (Issue #81 - @jpatchMC):** Aligned REST API responses, added bidirectional support for `discovery_prefix` / `homeassistant_prefix`, and resilient frontend destructuring.
* **Fixed Firefox Device Table Rendering Glitch (Issue #80 - @jpatchMC):** Removed dynamic `<colgroup>` declaration in favor of direct cell constraints, completely eliminating column collapsing and scroll flicker in Gecko.
* **Webhook Payload Serialization & Isolated Channel Dispatch (Issue #85 - @Hatton920):** Recursive `_json_safe()` serialization, restored instant real-time alerts for offline nodes and new devices in Home Assistant, and pre-populated `_known_macs` on startup.
* **UI/UX Polish, Localization & Truncated Device Names (Issue #84 - @XprofQ):** 11 targeted improvements: dynamic Fluent category icons in tables, 2-line clamp with hover tooltip for long names, `whitespace-nowrap` on WAN throughput, Top Bandwidth Hogs dropdowns expanded to 30 with fixed wired detection logic, and preserved original GitHub release notes.
* **Architectural i18n Refactoring & Test Suite Safety (Issue #82 - @todddube):** Pruned dead regex-based health translators (~90 lines removed), rendered health `affected_items_i18n` in viewer active language, and isolated pre-release test suite to a secure temporary directory (`tempfile.mkdtemp`).

## v1.6.1
* **Complete Settings Localization & Loading Flash Prevention (PR #78 - @todddube):** 100% translation of all Settings pages and modals (Controls, Users, Backup, Export, Updates, MQTT, Schedules, Clear Logs), parameter interpolation, and loading flash prevention via `body.i18n-pending`.
* **Subnet-Aware IPv4 Prioritization, Pi-hole v6 Stale Record Pruning & Device Exclusions (Issue #72):** Multi-level scoring algorithm prioritizing physical eero LAN subnet addresses over virtual container bridge gateways (`172.17.x.x`), automated atomic pruning of expired DHCP leases and obsolete mappings for Pi-hole v6 while strictly preserving custom unmanaged records, and a dedicated per-device "Exclude from DNS Sync" toggle (`dns_sync_excluded`).
* **Robust Network Discovery, EERO_NETWORK_ID Fallback & Zero-Network Guidance (Issue #69):** Universal parsing of eero API responses, transparent fallback to `EERO_NETWORK_ID` for delegated or multi-network accounts, zero-network guidance banner with quick retry, and prevention of demo device leakage into live production databases.
* **Daily Digest Restart Idempotency & Custom Dispatch Hour (Issue #70):** Persistent SQLite tracking of `last_daily_digest_date` preventing notification spam on container restarts, paired with configurable `DAILY_DIGEST_HOUR` (0-23) and `TZ` support with an interactive time-picker UI.
* **Speed Test Bufferbloat Accuracy & Localized Duration Units (Issue #71):** Direct frontend recognition of stored `bufferbloat_grade`, `ping_under_load`, and `bufferbloat_delta_ms` resolving `"n/a Non Disponibile"` reporting, bilingual localized ratings, and dynamic duration abbreviations in retention buttons (`7d`/`7gg`, `15d`/`15gg`, `1mo`/`1m`).
* **Multi-Tier Selective Compaction, Timestamp Indexes & Resilient Bitrate Parsing (Issues #73, #74):** Selective retention engine processing only uncompacted hours (reducing CPU overhead by 99.4%), SQLite B-tree expression indexes on cleaned timestamps, universal `parse_bitrate_float()` handling units (`Mbps`, `MBit/s`), database health integrity check endpoints, and defragmented online hot backups via `VACUUM INTO`.

## v1.6.0
* **Module 1 - Local Authentication, RBAC & Smart Automations:** Multi-user authentication with `Admin`, `Operator`, and `Viewer` roles, advanced parental time scheduling with day-of-week matrices, nightly maintenance engine, and disaster recovery emergency backups.
* **Module 2 - Multi-Tier Data Compaction, Bufferbloat & PWA Offline-First:** Scalable multi-tier SQLite archiving (Raw 48h -> Hourly 30d -> Daily 365d), analytical Bufferbloat rating gauge (A+ to F with loaded/unloaded latencies), Progressive Web App (PWA) offline-first service worker support.
* **Module 3 - Notifications & Disaster Recovery Snapshot:** Validated and encrypted configuration snapshots export/restore suite, interactive parental control schedule editor.
* **Module 4 - System Logging, Live Console & Homelab Integrations:** Runtime log depth controls (`DEBUG`, `INFO`, `WARNING`, `ERROR`), configurable retention policies (24h, 7d, 15d, 1m, custom), acrylic Live Console Viewer with full-text search and severity chips, full stream download (.log / .json) and secure purge modal; MQTT integration with Home Assistant Auto-Discovery and device trackers; native Prometheus/OpenMetrics (`/metrics`) endpoint with 13-panel prebuilt Grafana dashboard; multi-channel notification dispatcher extended to Discord Webhooks and Pushover with dedicated alerts for bufferbloat degradation, mesh anomalies, brute-force attempts and backup status.
* **Official eeroOS Release Notes Hub & Community Feedback (Issue #55):** Real-time firmware tracking via Zendesk REST API and r/amazoneero Reddit feed, with local fleet firmware alignment comparison (Up-to-date, Update Available, Newer than published).
* **AI Network Diagnostics, Roaming Advisor & IoT Night Anomaly Detection (Issue #56):** Natural language AI diagnostic engine with bilingual narratives (EN/IT), prioritized action checklist, sticky client roaming advisor, and off-hours IoT traffic anomaly detection.
* **Navigation Deep-Linking & URL State Synchronization (PR #28 / Issue #45):** Bidirectional URL hash and query parameter synchronization with browser history support and shareable direct links.
* **Responsive App Shell, Windows 11 Fluent Header & Mobile Drawer (PR #29 / Issue #46):** Sliding mobile drawer sidebar with scrim backdrop, responsive header with Fluent settings menu, responsive device table cards on small screens, and clamp-height dynamic chart frames.
* **Module 6 - 100% Offline-First & Local Asset Bundling (Issue #58) & "Recently Joined" Devices (Issue #60):** Complete local vendoring of client libraries (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) and self-hosted WOFF2 fonts (`Inter`, `JetBrains Mono`) for 100% offline and air-gapped readiness; persistent `first_seen` tracking with animated emerald "NEW" badges and dedicated "Recently Joined" sorting.
* **Module 7 - Reverse Client Enrichment & IPv6 ULA Discovery (Issue #57):** Resolving eero Layer 2 routing visibility limit for local DNS queries; ingestion REST API (`/api/network/enrichment/neighbors`), ICMP/NDP probe worker, persistent `device_discovered_ips` table, and full-circle sync to AdGuard Home; magenta "ULA Enriched" badges with context tooltips.
* **Module 8 - SQLite WAL Concurrency, Open Guest Wi-Fi QR Codes & Notification Transparency (Issues #62, #63, #64):** Definitive resolution of SQLite lock contention via `_write_lock` serialization, 60s timeout, and `busy_timeout=60000` pragmas; ZXing-compliant Wi-Fi QR Code generation for open guest networks (`T:nopass;`) and disabled network state handling; active multi-channel delivery transparency (Telegram, Discord, Pushover, Webhook) on Daily Digest cards.
* **Module 9 - IPv6 ULA Discovery Refinement, ULA Enriched Badge & Table Filtering (Issue #65):** Fixed IPv6 ULA display and synchronization on dual-stack devices with resilient `ipv6_all || ipv6_addresses || [ipv6]` fallback; completed missing English localization keys; nightly lifecycle auto-pruning for stale discovered addresses after 30 days.
* **Initial Administrator Setup Wizard (Zero-Default Security):** Guided first-run web onboarding wizard for secure admin username and password configuration; complete removal of hardcoded default credentials from the UI, with optional headless Docker bypass via `ADMIN_USER` and `ADMIN_PASSWORD`.

---

## v1.5.0
* **Network Statistics & Analytics, ISP SLA Analysis & Data Export Center:** New main view with frequency breakdown, mesh node load, device categories, vendors, and SLA trends with CSV/JSON export.
* **Device Data Usage Insights Suite:** New "Data Usage" tab per device with time-range selector (Last 24h, 7 Days, 30 Days), Chart.js telemetry charts, and Top Bandwidth Hogs widget.
* **Multi-Network Fleet Management & Dynamic Hot-Swap (Issue #22):** Multi-network eero account switching with instant active network persistence across polling cycles.
* **Intelligent Address Pruning & IPv6 DNS Exclusions (Issue #31 & #30):** Automated pruning of obsolete IP addresses and expired SLAAC IPv6 leases on AdGuard Home and multi-DNS sync.
* **Bilingual Daily Digest Telegram & Controls Tab (Issue #38):** Full EN/IT bilingual support for daily digest reports, disconnections alerts, and user language synchronization.
* **Mesh Node Collision Resolution & "Other/Altro" Localization (Issue #41):** Strict exact name matching for substring nodes and dynamic real-time localization of categories and vendors.
* **Primary Gateway Reconciliation in Multi-Ethernet Topologies (Issue #36):** Strict election hierarchy for primary gateway identification across switches and leaf nodes.
* **Layer 2 Hardware Switching Telemetry Clarification (Issue #40 & #42):** Clear technical explanation of Ethernet hardware switching and removal of misleading subscription disclaimers.
* **CI/CD Docker Hub Release Isolation:** Test branch builds isolated to prevent accidental overwrite of production `latest` tag.
* **Community Hall of Fame & Special Thanks:** Dedicated recognition section in About modal honoring community contributors and testers.
* **Strict Telemetry, RF Accuracy & Node Stability (PRs #47-#53):** Fixes for 5 GHz UNII-3 vs 6 GHz radio channels, live/demo session isolation, exact URL-segment gateway matching, removal of placeholder speedtest/RSSI values and network ID resolution on DHCP/port rules (credits to @carbones73).
* **Security Hardening & Vulnerability Remediation (4 GHSA Advisories):** Cross-Origin & CSRF protection (`CORS_ORIGINS`), Wi-Fi credential sanitization from public overview, interactive `/docs` Swagger toggle (`API_DOCS`), and restrictive `0600` file permissions on `session.json` (credits to @carbones73).
* **Dual-Stack IPv6 Visibility & Instant Search (Issue #43):** Extraction and display of Global Unicast and Link-Local (`fe80::`) IPv6 addresses with 1-click clipboard copy, unobtrusive device table badge, and instant search (credits to @jpatchMC).
* **Dual-Network Simulator in Demo Mode:** Simultaneous independent mock environments (Casa Rossi Mesh 6E and Office & Studio Pro Mesh).

---

## v1.4.02
* **Fix SQLite Lock on Startup during Mock Speedtest Data Purge (Issue #35)**

---

## v1.4.01
* **Fix Primary Gateway Resolution with PoE & Mixed Mesh Nodes (Issue #26)**
* **Custom DNS Servers Extraction & Developer IP Fallback Removal (Issue #30)**
* **Dynamic 6 GHz Wireless Backhaul Detection for Wi-Fi 6E / Wi-Fi 7 Mesh Nodes**
* **Fix Device Table Frequency Band Filters (ReferenceError Resolution)**
* **Align Daily Digest Metrics & Expose `line_stability` in Webhook Payload (Issue #32)**
* **Accurate Mesh Offline Node Detection & Rebooting State Differentiation (Issue #34)**
* **Prevent Mock TIM Telemetry Leakage into Performance History & SQLite Purge (Issue #35)**

---

## v1.4.0
* **Windows 11 Fluent Design Restyling & Dual Theme Engine (Dark & Light Mode)**
* **Collapsible Left Sidebar Navigation (Windows 11 Fluent Style) with State Persistence**
* **Relocated Quick Controls (Gaming Focus & Demo Mode) with High-Visibility Emerald Green Indicator**
* **Network Health Score Breakdown & Interactive 4-Pillar Diagnostics Modal (Issue #15)**
* **Multi-Engine DNS Synchronizer Suite (Simultaneous Instances: AdGuard, Pi-hole, Technitium)**
* **In-App 1-Click Docker Auto-Update Engine (/api/system/update)**
* **Automated New Release Detection via Docker Hub & GitHub Releases**
* **Continuous Wireless Client RSSI Signal History Logging in SQLite**
* **New Wi-Fi Signal Quality & Mesh Coverage Suite with Chart.js Graphs**
* **Weak Signal Watchlist & Proactive Node Repositioning Recommendations**
* **Fix & Cloud DHCP Reservations Normalization ("Other Active Reservations")**
* **Fix & Multi-Format Port Forwarding Rules Normalization per Device**
* **Native Pi-hole v6 REST API Sync & Bare Hostnames Support (Issue #25)**

---

## v1.03.03
* **Fix Mesh Primary Gateway Resolution in Bridge & Routed Modes (Issue #19)**
* **Preserve AdGuard Home Custom Rules, Upstreams, Blocked Services & Tags on Sync (Issue #21)**
* **Accurate Desktop / PC vs Laptop Tag Mapping (`device_pc` / `device_laptop`)**
* **Eliminate False-Positive Gateway Flags from eero Cloud API URL Strings**
* **Guaranteed Certified Single Primary Gateway Resolution & Backhaul Badging**

---

## v1.03.02
* **Fix 2.5 Gbps Backhaul Speed Formatting on Mesh Node Cards (Issue #14)**
* **Wi-Fi 6E & Wi-Fi 7 6 GHz Frequency Detection (5900-7200 MHz, EHT 320MHz)**
* **Isolated 6 GHz Sky-Blue Badging & Styling De-confliction with 5 GHz**
* **Automatic Cache-Busting Versioning on Static Assets (Issue #17)**
* **Invited Administrator Accounts & Shared Networks Resolution Support**
* **Native eero Category Mapping & Official AdGuard Client Tags (Issue #13)**

---

## v1.03.01
* **Fix Mesh Node Ethernet Port Negotiation Speeds (Issue #14)**
* **Strict Separation of Wireless Mesh Backhaul vs Local Wired Client Devices**
* **Authentic Device Ethernet Speeds (Zero Hardcoding)**
* **Expanded Wireless Node RSSI (dBm) Signal Telemetry on Beacons**

---

## v1.03.00
* **Universal Multi-Generation Mesh Nodes & Client Resolution (Pro 7 / 6E / 6+)**
* **Instant Demo Mode / Live Network Switcher without Token Loss**
* **Dynamic 2.5G/10G Ethernet Speed Detection & Signal dBm/PHY Rate Telemetry**
* **eero Cloud User & Family Profile Telemetry in Table and Modal**
* **Official Multi-Arch Docker Hub Image (amd64/arm64)**
* **Native In-App AdGuard Home Integration (DNS & DHCP Sync)**
* **Secure Logout Button with OTP Confirmation Modal**
* **Daily Digest Report Fixes & Rich Live Telemetry**
* **Automations Tab 2x2 Layout & Dedicated Notification Toggles**
* **Persistent Known Devices Registry (Zero Duplicate Alerts on Restart)**
* **Interactive Device Sorting & Sticky Table Header Bar**
* **Dynamic Device Discovery & Adaptive Hardware Sensor Display**
* **About Modal & Open Source Dedication**
* **Optimized In-App Markdown Rendering & Ordered Lists**
* **DNS (/etc/hosts, JSON) & Webhook Exporting**

---

## v1.02.00
* **Wi-Fi Band Telemetry (2.4 / 5 / 6 GHz) & Channel Badges**
* **eero Cloud User & Family Profile Integration**
* **Advanced Multi-Criteria Client Table Filters**

---

## v1.01.00
* **Dynamic Multilingual Support (Italian & English)**
* **Header Language Selector & Preference Persistence**
* **GitHub Open Source Standards & MIT License**

---

## v1.00.08
* **Total Speed Test Synchronization & Gateway Statistics**

---

## v1.00.07
* **Visual IP Assignment Badges (STATIC vs DHCP)**

---

## v1.00.06
* **Current IP Lease Binding & Smart IP Reassignment**

---

## v1.00.05
* **Native Cloud DHCP Reservations & Port Forwarding Rules**

---

## v1.00.04
* **Device Management, Custom Icons, Categories & Favorites**

---

## v1.00.01 - v1.00.03
* **Synthetic Data Removal in Favor of 100% Certified Telemetry**

---

## v1.0.0
* **Initial Release: Self-Hosted Docker Architecture, 2FA OTP & Poller**
