---
id: reverse-enrichment
title: 16. Reverse Client Enrichment & IPv6 ULA-detectie
icon: arrows-right-left
summary: Tweerichtings-verrijking via lokale DNS-servers, detectie van IPv6 ULA-adressen en opvolging van nieuwe apparaten.
---
### Reverse Client Enrichment & IPv6 ULA-detectie

In Dual-Stack-netwerken sturen apparaten hun DNS-verzoeken vaak via lokale **IPv6 ULA**-adressen (*Unique Local Address*, voorvoegsels `fc00::/7` en `fd00::/8`). Omdat dit dataverkeer lokaal op Layer 2 blijft en de router niet passeert, heeft de eero-cloud geen zicht op deze adressen.

* **Reverse Client Enrichment via NDP & REST-ingestie:**
  - **Automatische achtergrondscan:** Het systeem peilt regelmatig de netwerktabel van de kernel (NDP / ARP) en lokale DNS-servers om ULA-adressen te koppelen aan fysieke MAC-adressen.
  - **Externe ingestie-API (`POST /api/network/enrichment/neighbors`):** Maakt het mogelijk voor externe scripts of containers om IP-MAC-koppelingen in realtime aan te leveren.
  - **Volledige terugsynchronisatie:** Gedetecteerde ULA-adressen worden teruggekoppeld naar lokale DNS-servers, zodat anonieme IP-query's altijd herleid kunnen worden naar de leesbare apparaatnaam.
* **Visuele badge & Detailinspectie:**
  - Verrijkte adressen worden in de tabel en op de detailkaart aangeduid met de paarse badge **`ULA Enriched`**.
* **Recent verbonden apparaten & "NEW"-badge:**
  - De datum van eerste detectie (`first_seen`) wordt voor elk apparaat bewaard.
  - Apparaten die in de afgelopen 24 tot 48 uur voor het eerst zijn gezien, dragen de opvallende smaragdgroene badge **`NEW`**.
* **Automatische onderhoudsopschoning:**
  - Niet meer gebruikte tijdelijke ULA-adressen worden na 30 dagen inactiviteit automatisch verwijderd om de database schoon te houden.
