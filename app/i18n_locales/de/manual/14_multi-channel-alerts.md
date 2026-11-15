---
id: multi-channel-alerts
title: 14. Multi-Kanal-Alarme & Notfall-Benachrichtigungen
icon: bell
summary: Mehrkanal-Dispatcher (Telegram, Discord, Webhook, Pushover, Ntfy) und spezialisierte Netzwerkalarme.
---
### Multi-Kanal-Alarme & Notfall-Benachrichtigungen

Das Benachrichtigungssystem unterstützt die parallele Weiterleitung kritischer Netzwerkereignisse über verschiedene Kanäle:

* **Unterstützte Kanäle:**
  - **Telegram Bot:** Sofortige HTML-formatierte Alarmmeldungen mit Knoten- und Gerätedetails.
  - **Discord Webhook:** Formatierte Einbettungskarten mit farblicher Schweregradabstufung.
  - **Pushover:** Priorisierte Push-Nachrichten für mobile Endgeräte.
  - **Natives Ntfy (sh):** Unterstützung für öffentliche `ntfy.sh`-Server oder selbstgehostete Instanzen mit Prioritäten und Token-Authentifizierung.
  - **Generischer Webhook:** Übertragung von JSON-Nutzdaten für eigene Automationssysteme (Node-RED, n8n, Home Assistant).
* **Einstellungskarten & Passwortmaskierung:**
  - Dedizierte Konfigurationsmasken unter *Einstellungen -> Steuerungen* mit Schaltfläche für **Sofortigen Testversand**.
  - Maskierung von Schlüsseln und URLs als `••••••••` zur Vermeidung unbeabsichtigter Offenlegung.
* **Integrierte Spezialalarme:**
  - **Bufferbloat-Verschlechterung:** Warnung bei spürbarem Anstieg der Latenz unter Netzwerklast.
  - **Mesh-Knoten-Qualitätsabweichung:** Meldung bei DFS-Radarereignissen oder Störungen der Funkbrücken.
  - **Unbekanntes Gerät verbunden:** Einbruchsschutz-Warnung bei Erstkontakt nicht registrierter Geräte.
  - **Knoten getrennt:** Sofortmeldung bei Ausfall eines eero-Zugangspunkts.
