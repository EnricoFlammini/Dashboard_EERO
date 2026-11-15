---
id: troubleshooting
title: 8. Probleemoplossing, Updates & Veelgestelde Vragen
icon: wrench
summary: Veelgestelde vragen over telemetrie, Docker auto-update, beveiliging, back-ups en onderhoud.
---
### Veelgestelde Vragen & Probleemoplossing

* **Hoe werkt de automatische Docker-containerupdate via de webapp?**
  - De suite controleert geregeld op nieuwe versies via Docker Hub en GitHub Releases.
  - Met een gekoppelde Docker-socket (`/var/run/docker.sock`) downloadt een klik op **"Container nu bijwerken"** de nieuwste image en herstart de container met behoud van het `./data`-volume.
* **Welke apparaatgegevens zijn rechtstreeks afkomstig van eero?**
  - Verbindingsstatus, lokaal IP, MAC-adres, verbonden mesh-knooppunt, frequentieband (**2.4 GHz, 5 GHz, 6 GHz of bekabeld**), kanaal, signaalsterkte in **dBm** en fysieke verbindingssnelheid (**PHY Link Rate**).
* **Beveiliging & Gegevensbescherming:**
  - **CORS- & CSRF-bescherming:** Cross-origin-toegang standaard beperkt en verificatie van wijzigingsverzoeken.
  - **Wachtwoordfiltering:** Wi-Fi-wachtwoorden worden automatisch verwijderd uit publieke API-eindpunten.
  - **Strikte rechten:** `session.json` wordt beveiligd met toegangsrechten `0600`.
* **Wat te doen als de eero-sessie verloopt?**
  - Klik op **Afmelden** in de zijbalk en doorloop de aanmeldprocedure opnieuw (sms, e-mail of Amazon OAuth2).
* **Hoe maak ik een back-up van mijn lokale instellingen?**
  - Alle aanpassingen (namen, categorieën, notities, testhistorie) staan in `./data/metrics.db`. Het volstaat een kopie te maken van de map `./data`.
* **Waarom mislukt inloggen via sms/e-mail met fout 401?**
  - Als uw eero-account gekoppeld is aan Amazon, gebruikt u de optie **"Aanmelden met Amazon (OAuth2 / PKCE)"** in het inlogvenster.
* **Hoe stel ik Custom & Split DNS in?**
  - Configureer de omgevingsvariabelen `CUSTOM_DNS_SERVERS` en `CUSTOM_DNS_DOMAINS` om interne domeinen direct via lokale DNS-servers op te lossen.
* **Hoe werkt automatisch SQLite-herstel?**
  - Bij databasefouten door onverwachte stroomuitval voert het systeem een herstelprocedure in 3 stappen uit (`REINDEX`, tabelherstel, reconstructie) en bewaart een kopie `.corrupt.bak`.
