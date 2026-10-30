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
