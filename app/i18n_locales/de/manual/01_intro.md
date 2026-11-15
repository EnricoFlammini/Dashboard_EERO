---
id: intro
title: 1. Einführung & Architektur
icon: book-open
summary: Übersicht über die selbstgehostete Architektur, 2FA/OAuth-Sicherheit, 3-Stufen-Design und 9 europäische Sprachen.
---
### Was ist die eero Custom Dashboard & Management Suite?
Diese Webanwendung ist eine voll ausgestattete, selbstgehostete Management- und Überwachungsplattform für Ihr **Amazon eero** Mesh-WLAN-Netzwerk.

#### Architektur-Highlights:
1. **Selbstgehostet & Vollständige Privatsphäre:** Läuft in einem isolierten Docker-Container auf Ihrem lokalen Server oder NAS (HomeLab). Offizielles Multi-Architektur-Image auf Docker Hub für `linux/amd64` und `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Flexible Authentifizierung (2FA OTP & Amazon OAuth2):** Die Verbindung zur eero-Cloud erfolgt über das offizielle Zwei-Faktor-Verfahren (SMS- oder E-Mail-Einmalpasswort) oder über natives **Amazon OAuth2 / PKCE** für mit Amazon verknüpfte Konten.
3. **Persistenz & Isolation:** Das Sitzungstoken (`session.json`) und die SQLite-Datenbank (`metrics.db`) liegen ausschließlich im persistenten Volume `./data:/app/data`.
4. **Latenzfreier In-Memory-Poller:** Ein asynchroner Hintergrunddienst fragt das Netzwerk periodisch ab und hält einen RAM-Cache vor, der verzögerungsfreie Navigation ohne Überlastung der Schnittstellen gewährleistet.
5. **Windows 11 Fluent Design, 3-Stufen-Farbschema & Tastenkürzel `Strg+K`:** Moderne Benutzeroberfläche mit Hell-, Dunkel- und System-Modus (automatische Betriebssystem-Erkennung via `prefers-color-scheme`), universeller Schnellsuche `Strg+K` / `Cmd+K` und einklappbarer Seitenleiste.
6. **Vollständige europäische Mehrsprachigkeit (9 Sprachen):** Vollständige Katalogparität im Frontend und Backend für Englisch, Italienisch, Französisch, Spanisch, Deutsch, Niederländisch, Portugiesisch, Polnisch und Griechisch.
