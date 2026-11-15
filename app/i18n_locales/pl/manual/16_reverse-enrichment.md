---
id: reverse-enrichment
title: 16. Reverse Client Enrichment i Wykrywanie IPv6 ULA
icon: arrows-right-left
summary: Dwukierunkowe wzbogacanie danych z lokalnych serwerów DNS, wykrywanie adresów IPv6 ULA i monitorowanie nowych urządzeń.
---
### Reverse Client Enrichment i Wykrywanie IPv6 ULA

W sieciach Dual-Stack urządzenia często kierują zapytania do lokalnych serwerów DNS za pośrednictwem adresów **IPv6 ULA** (*Unique Local Address*, prefiksy `fc00::/7` oraz `fd00::/8`). Ponieważ ruch ten odbywa się wyłącznie lokalnie na poziomie Warstwy 2 (Layer 2), chmura eero nie posiada informacji o tych adresach.

* **Reverse Client Enrichment przez NDP i REST Ingestion:**
  - **Automatyczne Skanowanie:** Usługa regularnie odpytuje tablicę sąsiedztwa jądra (NDP / ARP) oraz lokalne serwery DNS, przypisując osierocone adresy ULA do fizycznych adresów MAC.
  - **Zewnętrzny Punkt Wprowadzania Danych (`POST /api/network/enrichment/neighbors`):** Umożliwia zewnętrznym skryptom lub kontenerom przekazywanie powiązań IP-MAC w czasie rzeczywistym.
  - **Pełna Synchronizacja Zwrotna:** Zidentyfikowane adresy ULA są aktualizowane w lokalnych serwerach DNS, co pozwala na natychmiastowe przypisanie zapytań do czytelnych nazw urządzeń.
* **Wizualne Oznaczenie i Szczegóły:**
  - Wzbogacone adresy wyróżniono w tabeli i oknie szczegółów urządzenia fioletową odznaką **`ULA Enriched`**.
* **Nowo Podłączone Urządzenia i Odznaka "NEW":**
  - System zapisuje datę pierwszego wykrycia (`first_seen`) każdego urządzenia w sieci.
  - Sprzęt zarejestrowany w ciągu ostatnich 24-48 godzin jest oznaczany szmaragdową odznaką **`NEW`**.
* **Automatyczne Porządkowanie Danych:**
  - Nocna procedura konserwacyjna automatycznie usuwa nieaktywne tymczasowe wpisy ULA po 30 dniach bezczynności.
