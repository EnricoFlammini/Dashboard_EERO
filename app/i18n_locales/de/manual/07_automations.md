---
id: automations
title: 7. Automatisierungen, Gäste-QR, AdGuard Home, Telegram & Benachrichtigungen
icon: zap
summary: Dynamisches Gäste-WLAN mit QR-Code, AdGuard Home DNS-Sync, Telegram/Webhook-Alarme und Tagesberichte.
---
### Automatisierungszentrale & Erweiterte Funktionen

Die Registerkarte **Steuerung & Gäste-QR** fasst wichtige Werkzeuge in Modulen zusammen:

1. **Smartes Gäste-WLAN mit dynamischem QR-Code:**
   - Erzeugt sofort druckbare QR-Codes, die sich an das aktive Farbschema anpassen (heller Hintergrund im Tag-Modus, dunkler Schieferton im Nacht-Modus).
   - 1-Klick-Schalter zum Aktivieren/Deaktivieren des Gastzugangs mit integriertem Passwortgenerator.
2. **Multi-Engine DNS-Synchronisierer:**
   - **Unterstützung heterogener DNS-Instanzen:** Gleichzeitige Verwaltung von AdGuard Home, Pi-hole (v5 und v6) und Technitium DNS.
   - **Kontinuierlicher Auto-Sync:** Gleicht Gerätenamen und IP-Adressen bei neuen Geräten automatisch ab.
   - **Intelligente Adressbereinigung & Custom DNS:** Automatische Auflösung veralteter DHCP-Leases, RFC 1123-Konformität und Unterstützung für **Custom & Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) mit IPv4-Priorität (`AF_INET`).
   - **Geräteausschluss:** Dedizierter Schalter *"Von DNS-Sync ausschließen"* in den Gerätedetails.
3. **Telegram- & Webhook-Benachrichtigungen:**
   - **Persistentes Register & Schutz vor Alarmfluten:** Demo-Geräte werden isoliert, um Fehlalarme beim ersten Verbindungsaufbau auszuschließen.
   - **Neues Gerät verbunden:** Sofortige Benachrichtigung bei Erstverbindung unbekannter Geräte.
   - **Mesh-Knoten getrennt:** Dringlichkeitsmeldung bei Verbindungsverlust eines eero-Knotens.
4. **Tageszusammenfassung (Daily Digest):**
   - Automatisierter Versand zu konfigurierbarer Uhrzeit (Standard 21:00 Uhr) mit Netzwerkgesundheit, aktiven Clients und letztem Speedtest.
5. **Gaming- & Fokus-Modus (Niedrige Latenz):**
   - Pausiert sekundäre Streaming- und Downloadgeräte mit einem Klick, um Jitter bei Online-Spielen oder Videokonferenzen zu minimieren.
6. **IPv6-Pinhole-Firewallregeln:**
   - Visuelle Verwaltung zum Öffnen und Schließen von TCP/UDP-Ports auf einzelnen IPv6-Clients.
