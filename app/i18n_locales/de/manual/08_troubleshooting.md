---
id: troubleshooting
title: 8. Fehlerbehebung, Updates & FAQ
icon: wrench
summary: Häufige Fragen zur Telemetrie, Docker-Auto-Update, Sicherheit, Backups und Wartung.
---
### Häufige Fragen & Fehlerbehebung

* **Wie aktualisiere ich das Dashboard?**
  - Das Dashboard prüft Docker Hub und GitHub Releases auf neue Versionen und zeigt ein Update-Symbol an, sobald eine erscheint.
  - Zum Aktualisieren führe `docker compose pull && docker compose up -d` in dem Ordner aus, in dem deine `docker-compose.yml` liegt. Der Ordner `./data` bleibt erhalten.
  - Auf einem Synology-NAS nutze **Container Manager → Projekt → Aktion → Erstellen** oder lass den DSM-Aufgabenplaner automatisch aktualisieren. Siehe die [Synology-Anleitung](https://github.com/EnricoFlammini/Dashboard_EERO/blob/main/deploy/synology/README.md).
  - Die Schaltfläche **Container jetzt aktualisieren (1-Klick)** benötigt den im Container eingebundenen Docker-Socket (`/var/run/docker.sock`). Derzeit lädt sie nur das neue Image herunter; führe danach den obigen Befehl aus, um darauf umzustellen.
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
