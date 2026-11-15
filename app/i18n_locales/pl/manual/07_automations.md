---
id: automations
title: 7. Automatyzacje, QR Gości, AdGuard Home, Telegram i Powiadomienia
icon: zap
summary: Inteligentne Wi-Fi dla gości z kodem QR, synchronizacja DNS z AdGuard Home, alerty Telegram/Webhook i raporty dobowe.
---
### Centrum Automatyzacji i Zaawansowane Funkcje

Zakładka **Sterowanie i QR Gości** grupuje narzędzia w modułowe panele:

1. **Smart Wi-Fi dla Gości z Dynamicznym Kodem QR:**
   - Natychmiastowe generowanie kodu QR dostosowanego do aktywnego motywu (jasne tło w trybie dziennym, ciemny grafit w trybie nocnym).
   - Włączanie i wyłączanie sieci dla gości jednym kliknięciem z wbudowanym generatorem bezpiecznych haseł.
2. **Synchronizator DNS dla Wielu Silników:**
   - **Obsługa Różnorodnych Instancji DNS:** Równoległa integracja z AdGuard Home, Pi-hole (v5 i v6) oraz Technitium DNS.
   - **Ciągła Synchronizacja Automatyczna:** Automatyczne dodawanie nazw urządzeń i rezerwacji IP po wykryciu nowych klientów.
   - **Inteligentne Czyszczenie i Custom DNS:** Rozwiązywanie konfliktów wygasłych dzierżaw, standaryzacja RFC 1123 i obsługa **Custom & Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) z priorytetem IPv4 (`AF_INET`).
   - **Wykluczanie Pojedynczych Urządzeń:** Dedykowany przełącznik *"Wyklucz z synchronizacji DNS"* w karcie urządzenia.
3. **Powiadomienia Telegram i Webhook:**
   - **Trwały Rejestr i Ochrona Przed Lawiną Powiadomień:** Izolacja adresów testowych zapobiegająca fałszywym alertom przy pierwszym uruchomieniu.
   - **Nowe Urządzenie w Sieci:** Natychmiastowe ostrzeżenie przy podłączeniu nieznanego wcześniej sprzętu.
   - **Węzeł Mesh Offline:** Błyskawiczna informacja w przypadku utraty łączności przez punkt dostępowy eero.
4. **Raport Dobowy (Daily Digest):**
   - Zautomatyzowane wysyłanie raportu o ustalonej godzinie (domyślnie 21:00) z oceną kondycji sieci, listą aktywnych urządzeń i wynikami testu prędkości.
5. **Tryb Gaming i Focus (Niskie Opóźnienia):**
   - Jednym kliknięciem tymczasowo wstrzymuje ruch urządzeń drugorzędnych, eliminując zakłócenia podczas rozgrywek online czy telekonferencji.
6. **Reguły Pinhole Firewalla IPv6:**
   - Wygodne otwieranie i zamykanie portów TCP/UDP dla wskazanych klientów IPv6.
