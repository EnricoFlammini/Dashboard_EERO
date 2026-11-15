---
id: troubleshooting
title: 8. Fehlerbehebung, Updates & FAQ
icon: wrench
summary: Häufige Fragen zur Telemetrie, Docker-Auto-Update, Sicherheit, Backups und Wartung.
---
### Häufige Fragen & Fehlerbehebung

* **Wie funktioniert das Docker-Container-Update direkt aus der Web-App?**
  - Die Suite prüft regelmäßig neue Versionen auf Docker Hub und GitHub Releases.
  - Bei eingebundenem Docker-Socket (`/var/run/docker.sock`) lädt ein Klick auf **"Container jetzt aktualisieren"** das neue Image herunter und startet den Container unter Beibehaltung des `./data`-Volumes neu.
* **Welche Gerätedaten stammen direkt von eero?**
  - Verbindungsstatus, lokale IP, MAC-Adresse, verbundener Mesh-Knoten, Frequenzband (**2.4 GHz, 5 GHz, 6 GHz oder Kabel**), Funkkanal, Signalstärke in **dBm** und physikalische Link-Geschwindigkeit (**PHY Link Rate**).
* **Sicherheits-Hardening & Datenschutz:**
  - **CORS- & CSRF-Schutz:** Cross-Origin-Zugriff standardmäßig eingeschränkt und Verifikation mutierender Anfragen.
  - **WLAN-Passwort-Bereinigung:** WLAN-Schlüssel werden vor Veröffentlichung in öffentlichen API-Endpunkten gefiltert.
  - **Restriktive Dateirechte:** `session.json` wird mit Zugriffsrechten `0600` geschützt.
* **Was tun bei abgelaufener eero-Sitzung?**
  - Klicken Sie in der Seitenleiste auf **Abmelden** und durchlaufen Sie den Anmeldevorgang erneut (SMS, E-Mail oder Amazon OAuth2).
* **Wie sichere ich meine lokalen Einstellungen?**
  - Alle Anpassungen (Gerätenamen, Kategorien, Notizen, Messverläufe) sind in `./data/metrics.db` gespeichert. Eine Sicherung des Ordners `./data` genügt.
* **Warum schlägt die SMS/E-Mail-Anmeldung mit Fehler 401 fehl?**
  - Ist das eero-Konto mit Amazon verknüpft, nutzen Sie die Option **"Mit Amazon anmelden (OAuth2 / PKCE)"** im Anmeldedialog.
* **Wie richte ich Custom & Split DNS ein?**
  - Setzen Sie die Umgebungsvariablen `CUSTOM_DNS_SERVERS` und `CUSTOM_DNS_DOMAINS`, um lokale Domänen direkt über interne Nameserver aufzulösen.
* **Wie funktioniert die automatische SQLite-Selbstreparatur?**
  - Bei Dateibeschädigungen durch plötzliche Stromunterbrechungen repariert die 3-Stufen-Routine (`REINDEX`, Tabellenreparatur, Neuerstellung) die Datenbank und sichert eine Kopie `.corrupt.bak`.
