---
id: device-details
title: 5. Device Metadata, Static IP & Port Forwarding
icon: adjustments
summary: Custom names, categories, local notes, DHCP reservations, IPv6, and port forwarding.
---
### Device Management & Rules

* **Device Detail Modal:**
  - **Custom Name & Category:** Assign categories (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Other) saved to the local SQLite database.
  - **Local Notes & Documentation:** Free-form notes for tracking device location, service ports, or internal credentials.
  - **Dual-Stack IPv6 Addresses & 1-Click Copy (v1.5.0 - Issue #43):** Dedicated box in the General tab listing all IPv6 addresses with category badges (*SLAAC / Global* vs *Link-Local*) and a 1-click clipboard copy button with visual feedback.
  - **DHCP Reservation (Static IP):** Bind a permanent IP address to a client with automated conflict checking and reassignment support.
  - **Integrated Port Forwarding:** Create and delete port forwarding rules (External WAN Port -> Internal LAN Port, TCP/UDP protocols).
  - **Change Profile in the Modal:** Pick a different eero profile (or *No profile*) in the **General** tab. The change applies immediately and an inline message confirms it (or reports the error and restores the previous value). Requires the *Edit devices* permission.
  - **Device Category as Icon Buttons:** Choose the category (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/Network) by clicking its icon; the icon shown for the device follows the category. The last button, **Auto-detect**, resets to the type and icon eero reports.
  - **Read-Only Details:** Status, MAC address, the hostname reported by the device itself (separate from the display name), manufacturer and model, last active time, Wi-Fi standard and channel width, guest-network flag, live download/upload rates with totals, and first seen.
