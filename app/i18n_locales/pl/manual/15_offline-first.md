---
id: offline-first
title: 15. Architektura Offline-First i Zasoby Lokalne
icon: shield-check
summary: Pełna niezależność dzięki wbudowanym bibliotekom i czcionkom, brak zewnętrznych zależności CDN.
---
### Architektura Offline-First i Zasoby Lokalne

Aplikacja została zaprojektowana zgodnie z regułą pełnej autonomii, gwarantując prywatność, natychmiastowe renderowanie i stabilność działania nawet przy braku połączenia z Internetem:

* **Kompletne Lokalne Zależności:**
  - Wszystkie biblioteki frontendowe (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) są ładowane bezpośrednio z katalogu `/app/static/vendor/`.
  - Całkowity brak zapytań do zewnętrznych sieci CDN: brak śledzenia przez podmioty trzecie oraz odporność na blokery reklam.
* **Czcionki Hostowane Lokalnie:**
  - Czytelne kroje pisma **Inter** (interfejs użytkownika) i **JetBrains Mono** (konsola i tabele) dołączono w formacie WOFF2 w folderze `/app/static/fonts/`.
* **Praca w Środowiskach Odizolowanych (Air-Gapped):**
  - Pakiet bezproblemowo uruchamia się i działa w zamkniętych sieciach LAN oraz serwerach bez dostępu do Internetu.
* **Progressive Web App (PWA) i Service Worker:**
  - Zintegrowany Service Worker zapisuje kluczowe zasoby w pamięci podręcznej przeglądarki, zapewniając ciągłość obsługi przy chwilowych przerwach sieciowych.
