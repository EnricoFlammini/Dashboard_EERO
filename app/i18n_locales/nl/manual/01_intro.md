---
id: intro
title: 1. Introductie & Architectuur
icon: book-open
summary: Overzicht van de zelf-gehoste architectuur, 2FA/OAuth-beveiliging, 3-standen thema en 9 Europese talen.
---
### Wat is eero Custom Dashboard & Management Suite?
Deze webapplicatie is een compleet, zelf-gehost beheer- en monitoringsplatform voor uw **Amazon eero** mesh Wi-Fi-netwerk.

#### Belangrijkste architectuurkenmerken:
1. **Zelf-gehost & Volledige privacy:** Draait in een geïsoleerde Docker-container op uw lokale server of NAS (HomeLab). Officiële multi-arch Docker Hub-image voor `linux/amd64` en `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Flexibele authenticatie (2FA OTP & Amazon OAuth2):** Initiële verbinding met de eero-cloud verloopt via de officiële tweefactorauthenticatie (eenmalig wachtwoord per sms of e-mail) of via native **Amazon OAuth2 / PKCE** voor aan Amazon gekoppelde accounts.
3. **Persistentie & Isolatie:** De sessietoken (`session.json`) en de SQLite-database (`metrics.db`) bevinden zich uitsluitend in het persistente volume `./data:/app/data`.
4. **Latenzvrije In-Memory Poller:** Een asynchrone achtergronddienst peilt het netwerk periodiek en houdt een RAM-cache bij voor directe navigatie zonder risico op rate-limiting.
5. **Windows 11 Fluent Design, 3-Standen Thema & Sneltoets `Ctrl+K`:** Moderne interface met ondersteuning voor Licht, Donker en Systeem (Auto OS-detectie via `prefers-color-scheme`), universele snelzoekfunctie `Ctrl+K` / `Cmd+K` en inklapbare zijbalk.
6. **Volledige Europese meertaligheid (9 talen):** Volledige pariteit in frontend en backend voor Engels, Italiaans, Frans, Spaans, Duits, Nederlands, Portugees, Pools en Grieks.
