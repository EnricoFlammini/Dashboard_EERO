---
id: devices-table
title: 4. Connected Devices & Frequency Analysis
icon: devices
summary: Live device table, multi-column sorting, sticky headers, Wi-Fi band badges, and eero cloud profiles.
---
### Real-Time Device Inventory

* **Interactive Multi-Column Sorting:** Click any column header (Device/Name, Numerical IPv4 Address, Profile, Mesh Node, Band, RSSI Signal dBm, or Status) to toggle ascending and descending sort order.
* **Locked Sticky Header Bar:** The table header stays permanently anchored at the top of the viewport while scrolling through dozens of clients.
* **Wi-Fi Band & Channel Indicators:** Explicit frequency badges (**6 GHz, 5 GHz, 2.4 GHz, Wired Ethernet**) and active wireless channels (**CH 36, CH 11**, etc.).
* **eero Cloud User Profiles:** Displays the assigned family member profile for each client directly from the eero cloud.
* **Advanced Multi-Criteria Filtering:** Filter by Band, Profile, Node, or IP Assignment type (Static vs DHCP).
* **IPv6 Badge & Instant Search (v1.5.0 - Issue #43):** Compact `IPv6` badge next to the MAC address with a tooltip displaying all associated addresses (SLAAC & Link-Local); the search bar filters instantly by prefixes, octets, or full IPv6 addresses.
* **List or Cards View:** Use the **List / Cards** toggle in the toolbar. Cards show 3–4 devices per row with every table field: icon, name, category and manufacturer, MAC, IP with Static/DHCP, online status, band, channel, signal bars, PHY rate and Wi-Fi standard/width, flag chips (Paused, Gaming target, Sticky roaming, IPv6, ULA, Guest), live download/upload rates with totals, profile, node and first seen (or last seen for offline devices). The Columns menu applies to List view only.
* **Live Activity Animation:** A card glows and its rate bars shimmer while the device is moving data, with the glow strengthening as throughput rises. Reduced-motion settings are respected.
* **Open Details from the Name or IP:** In List view, click the device name or IP address (not only the pencil icon) to open its details.
* **Search Includes Vendor Data:** The search box also matches manufacturer, model and the hostname the device reports.
