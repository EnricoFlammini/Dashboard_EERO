---
id: multi-network
title: 9. Zarządzanie Wieloma Sieciami i Szybkie Przełączanie
icon: globe
summary: Obsługa kont eero z wieloma lokalizacjami, natychmiastowe przełączanie i trwałość wybranej sieci.
---
### Zarządzanie Wieloma Sieciami i Szybkie Przełączanie

* **Dynamiczny Przełącznik w Nagłówku (Windows 11 Fluent):** Jeśli Twoje konto obsługuje kilka sieci eero (np. Dom, Biuro, Dom letniskowy), rozwijane menu prezentuje liczbę węzłów i połączonych urządzeń w każdej lokalizacji.
* **Natychmiastowe Przełączanie w Pamięci:** Zmiana sieci następuje natychmiast bez konieczności restartu kontenera czy ponownego logowania. Pamięć podręczna RAM jest odświeżana w czasie rzeczywistym.
* **Trwałość Wybranej Sieci:** Aktywna lokalizacja jest zapisywana w `session.json` i bazie SQLite, dzięki czemu wybór pozostaje zachowany po ponownym uruchomieniu.
* **Wsparcie w Trybie Demo:** Zawiera dwie symulowane lokalizacje (*Casa Rossi Mesh 6E* oraz *Biuro Pro Mesh*) do testowania środowisk wielosieciowych.
* **Architektura Aktywnej Sieci i Równoległość:** Przełączenie działa globalnie dla instancji serwera. Aby stale monitorować kilka lokalizacji równolegle na jednym ekranie, można uruchomić dwa niezależne kontenery Docker na oddzielnych portach.
