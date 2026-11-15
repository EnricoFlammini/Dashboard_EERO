---
id: dashboard-mesh
title: 3. Dashboard & Mesh-topologie
icon: network
summary: Netwerkgezondheidsscore, knooppuntkaarten en snelle acties.
---
### Het Hoofddashboard Begrijpen

* **Netwerkgezondheidsscore (1-100):** Samenvattende indicatie van de toestand van het netwerk, berekend op basis van de beschikbaarheid van mesh-knooppunten, aanwezigheid van de gateway en RSSI-signaalkwaliteit van clients.
* **Overzichtskaarten:**
  - *WAN-status:* Publiek IP, provider, IPv6, gezondheidsbalk en laatste synchronisatie.
  - *Hoofdgateway:* Model, lokaal IP, subnet, DNS, firmware en online knooppunten.
  - *Verbonden apparaten:* Totaal en verdeling over 6 GHz / 5 GHz / 2.4 GHz / bekabeld, bekende apparaten, gasten en nieuwkomers.
  - *Laatste snelheidstest:* Download/upload, ping, bufferbloat-score en recente trends.
* **eero-knooppuntentopologie:**
  - *Gateway-knooppunt:* Het hoofdknooppunt dat rechtstreeks op het modem of glasvezel-ONT is aangesloten.
  - *Beacons / Mesh-extenders:* Secundaire knooppunten die de draadloze dekking uitbreiden.
  - *Verbindingstype (Backhaul):* Geeft aan of de onderlinge koppeling verloopt via Ethernet-kabel of via een dedicated draadloze verbinding.
* **Snelle knooppuntacties:**
  - **Netwerk herstarten:** Stuurt een gecontroleerde herstartopdracht naar het gehele mesh-systeem.
  - **Enkel knooppunt herstarten:** Start uitsluitend het geselecteerde apparaat opnieuw op.
* **Geavanceerde mesh-functionaliteiten:**
  - **Amazon Echo "eero Built-in"-extenders:** Automatische detectie van compatibele Echo-luidsprekers die als Wi-Fi-extender fungeren, aangeduid met de badge **`eero Built-in`**.
  - **Gateway-detectie in Bridge-modus:** Identificeert betrouwbaar de echte gateway via de vlag `is_primary_node` en LLDP-buren op de WAN-poort.
  - **Officiële productafbeeldingen:** Elk knooppunt toont de officiële hardware-afbeelding van het betreffende model (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot enz.).
  - **Streaming AI-assistent & Plaatsingstest:** Interactieve diagnose via SSE-streaming (`/api/network/assistant`), RF-plaatsingstest en beheer van Guardian VPN.
