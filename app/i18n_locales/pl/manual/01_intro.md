---
id: intro
title: 1. Wprowadzenie i Architektura
icon: book-open
summary: Przegląd architektury self-hosted, bezpieczeństwo 2FA/OAuth, motyw 3-stanowy i 9 języków europejskich.
---
### Czym jest eero Custom Dashboard & Management Suite?
Ta aplikacja internetowa to kompleksowa, samodzielnie hostowana platforma do zaawansowanego zarządzania i monitorowania sieci Wi-Fi mesh **Amazon eero**.

#### Główne cechy architektury:
1. **Self-Hosted i Pełna Prywatność:** Działa w izolowanym kontenerze Docker na Twoim lokalnym serwerze lub urządzeniu NAS (HomeLab). Oficjalny obraz multi-arch na Docker Hub dla `linux/amd64` i `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Elastyczne Uwierzytelnianie (2FA OTP i Amazon OAuth2):** Połączenie z chmurą eero wykorzystuje oficjalne uwierzytelnianie dwuskładnikowe (hasło jednorazowe SMS/e-mail) lub natywny przepływ federacyjny **Amazon OAuth2 / PKCE** dla kont powiązanych z profilem Amazon.
3. **Trwałość i Izolacja:** Token sesji (`session.json`) oraz baza danych SQLite (`metrics.db`) znajdują się wyłącznie w trwałym wolumenie `./data:/app/data`.
4. **Bezlatenencyjny Poller w Pamięci:** Asynchroniczny proces w tle cyklicznie odpytuje sieć i utrzymuje pamięć podręczną RAM, zapewniając natychmiastowe ładowanie bez ryzyka limitów zapytań (rate limiting).
5. **Projekt Windows 11 Fluent, 3-Stanowy Motyw i Skrót `Ctrl+K`:** Nowoczesny interfejs z obsługą trybu Jasnego, Ciemnego i Systemowego (Auto OS poprzez synchronizację `prefers-color-scheme`), globalnym skrótem szybkiego wyszukiwania `Ctrl+K` / `Cmd+K` oraz zwijanym panelem bocznym.
6. **Pełna Europejska Wielojęzyczność (9 Języków):** Pełna zgodność katalogów w interfejsie użytkownika i na serwerze dla języka angielskiego, włoskiego, francuskiego, hiszpańskiego, niemieckiego, holenderskiego, portugalskiego, polskiego i greckiego.
