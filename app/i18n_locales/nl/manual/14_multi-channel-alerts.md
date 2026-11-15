---
id: multi-channel-alerts
title: 14. Meerkanaals-meldingen & Noodwaarschuwingen
icon: bell
summary: Meerkanaals-dispatcher (Telegram, Discord, Webhook, Pushover, Ntfy) en gespecialiseerde netwerkwaarschuwingen.
---
### Meerkanaals-meldingen & Noodwaarschuwingen

Het notificatiesysteem ondersteunt parallelle distributie van kritieke netwerkgebeurtenissen over meerdere kanalen:

* **Ondersteunde kanalen:**
  - **Telegram Bot:** Directe HTML-meldingen met gedetailleerde gegevens over knooppunten en apparaten.
  - **Discord Webhook:** Rijke embed-kaarten met kleurgecodeerde urgentieniveaus.
  - **Pushover:** Prioritaire pushmeldingen voor mobiele apparaten.
  - **Native Ntfy (sh):** Ondersteuning voor openbare `ntfy.sh`-servers of zelf-gehoste instanties met prioriteiten en token-authenticatie.
  - **Generieke Webhook:** JSON-payloads voor aangepaste integraties (Node-RED, n8n, Home Assistant).
* **Bedieningspanelen & Veiligheid:**
  - Instelbare configuratiekaarten onder *Instellingen -> Bediening* met **Direct testen**-knop.
  - Maskering van tokens en URL's als `••••••••` om onbedoelde openbaarmaking te voorkomen.
* **Geïntegreerde gespecialiseerde waarschuwingen:**
  - **Bufferbloat-verslechtering:** Waarschuwing bij een aanzienlijke toename van latentie onder belasting.
  - **Mesh-knooppunt kwaliteitsafwijking:** Melding bij DFS-radardetectie of storingen op de draadloze verbinding.
  - **Onbekend apparaat verbonden:** Inbraakdetectiemelding bij eerste verbinding van niet-geregistreerde apparaten.
  - **Knooppunt offline:** Dringende melding als een eero-toegangspunt uitvalt.
