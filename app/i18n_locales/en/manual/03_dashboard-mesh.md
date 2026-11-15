---
id: dashboard-mesh
title: 3. Dashboard & Mesh Topology
icon: network
summary: Network Health Score, node status cards, and one-click actions.
---
### Understanding the Overview Dashboard

* **Network Health Score (1-100):** A comprehensive real-time score calculated from mesh node availability, gateway status, and client RSSI signal quality.
* **Summary Cards:**
  - *WAN Status:* Public IP, ISP, IPv6, health score bar and last update. Click to open the Network Health details.
  - *Primary Gateway:* Model, LAN IP, subnet, DNS, firmware and how many mesh nodes are online.
  - *Connected Clients:* Total plus a 6 / 5 / 2.4 GHz and wired split, known devices, guests and new devices. Click to open Devices filtered to connected clients.
  - *Last Speed Test:* Download/upload, ping, bufferbloat grade, recent download trend and overall averages. Click to open the Speed Test page.
* **eero Mesh Nodes Topology:**
  - *Gateway Node:* The primary node connected directly to your modem/ONT.
  - *Beacon / Mesh Extenders:* Secondary nodes extending wireless coverage.
  - *Connected Clients:* Click a node's client count to open Devices filtered to that node.
  - *Backhaul Type:* Displays whether inter-node links use high-speed Ethernet (1 Gbps / 2.5 Gbps) or dedicated wireless mesh backhaul (5 GHz / 6 GHz).
* **Quick Node Actions:**
  - **Reboot Network:** Dispatches a controlled reboot command across the entire mesh infrastructure.
  - **Reboot Single Node:** Reboots only the selected node without disrupting the rest of the household.
* **Advanced Mesh Features:**
  - **Amazon Echo "eero Built-in" Extenders:** Automatic synthesis and display of compatible Amazon Echo devices extending mesh Wi-Fi coverage. Highlighted with a distinctive **`eero Built-in`** badge, real-time client association counts, and safety suppression of unsupported reboot commands.
  - **Bridge Mode Primary Gateway Election:** In Bridge Mode (where all nodes report `gateway: false`), the suite deterministically elects the true primary gateway by evaluating `is_primary_node` and non-eero upstream WAN LLDP neighbors.
  - **Official eero Product Imagery:** Every mesh node card displays an authentic product photo of its hardware model (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot, etc.) for instant physical recognition.
  - **Streaming AI Assistant & Placement Test:** Interactive SSE streaming mesh diagnostics (`/api/network/assistant`), RF node placement assessment (`Placement Test`), Guardian VPN status, and serial number node onboarding.
