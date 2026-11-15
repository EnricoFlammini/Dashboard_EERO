---
id: automations
title: 7. Automatiseringen, Gasten-QR, AdGuard Home, Telegram & Meldingen
icon: zap
summary: Slim gasten-Wi-Fi met QR, AdGuard Home DNS-synchronisatie, Telegram/Webhook-meldingen en dagelijks overzicht.
---
### Automatiseringscentrum & Geavanceerde Functies

Het tabblad **Bediening & Gasten-QR** groepeert netwerkgereedschappen in overzichtelijke panelen:

1. **Smart Gasten-Wi-Fi met dynamische QR-code:**
   - Genereert direct een printbare QR-code die zich aanpast aan het actieve thema (witte achtergrond bij dagmodus, donker leisteen bij nachtmodus).
   - 1-Klik schakelaar om het gastennetwerk in of uit te schakelen met ingebouwde veilige wachtwoordgenerator.
2. **Multi-Engine DNS-synchronisator:**
   - **Ondersteuning voor heterogene DNS-instanties:** Gelijktijdig beheer van AdGuard Home, Pi-hole (v5 en v6) en Technitium DNS.
   - **Continue automatische synchronisatie:** Synchroniseert hostnamen en IP-reserveringen bij het detecteren van nieuwe apparaten.
   - **Intelligente adresopschoning & Custom DNS:** Automatisch oplossen van hergebruikte DHCP-leases, RFC 1123-opschoning en ondersteuning voor **Custom & Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) met IPv4-prioriteit (`AF_INET`).
   - **Uitsluiten per apparaat:** Schakelaar *"Uitsluiten van DNS-sync"* in het apparaatvenster.
3. **Telegram- & Webhook-meldingen:**
   - **Persistent register & Bescherming tegen meldingsstormen:** Isolatie van demo-apparaten om valse meldingen bij eerste start te voorkomen.
   - **Nieuw apparaat verbonden:** Directe waarschuwing zodra een onbekend apparaat verbinding maakt met het netwerk.
   - **Mesh-knooppunt offline:** Dringende melding als een eero-punt de verbinding verliest.
4. **Dagelijks overzicht (Daily Digest):**
   - Geautomatiseerde verzending op een instelbaar tijdstip (standaard 21:00 uur) met gezondheidsscore, actieve clients en laatste speedtest.
5. **Gaming & Focus-modus (Lage latentie):**
   - Pauzeert secundair download- en streamingverkeer met één klik om jitter tijdens gaming of videovergaderingen te voorkomen.
6. **IPv6 Pinhole-firewallregels:**
   - Visueel beheer voor het openen of sluiten van TCP/UDP-poorten op specifieke IPv6-clients.
