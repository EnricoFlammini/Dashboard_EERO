---
id: dashboard-mesh
title: 3. Pulpit Nawigacyjny i Topologia Mesh
icon: network
summary: Wskaźnik kondycji sieci, karty stanu węzłów i szybkie działania.
---
### Zrozumienie Głównego Pulpitu Nawigacyjnego

* **Wskaźnik Kondycji Sieci (1-100):** Syntetyczna ocena stanu sieci obliczana na podstawie dostępności węzłów, obecności bramy głównej i jakości sygnału RSSI urządzeń końcowych.
* **Karty Podsumowania:**
  - *Stan WAN:* Publiczny IP, dostawca, IPv6, pasek kondycji i czas ostatniej aktualizacji.
  - *Główna Brama:* Model, lokalny adres IP, podsieć, DNS, wersja oprogramowania i aktywne węzły.
  - *Połączone Urządzenia:* Łączna liczba i podział na 6 GHz / 5 GHz / 2.4 GHz / Przewodowe, urządzenia znane, goście i nowe.
  - *Ostatni Test Prędkości:* Pobieranie/wysyłanie, ping, ocena bufferbloat oraz wykres ostatnich wyników.
* **Topologia Węzłów eero:**
  - *Węzeł Bramy (Gateway):* Główny węzeł połączony bezpośrednio z modemem lub terminalem ONT.
  - *Beacon / Wzmacniacze Mesh:* Dodatkowe węzły rozszerzające zasięg bezprzewodowy.
  - *Typ Połączenia (Backhaul):* Informacja, czy połączenie między węzłami realizowane jest kablem Ethernet, czy dedykowanym pasmem radiowym.
* **Szybkie Działania dla Węzłów:**
  - **Uruchom Ponownie Sieć:** Wysyła polecenie kontrolowanego restartu do całej sieci eero.
  - **Uruchom Ponownie Pojedynczy Węzeł:** Restartuje tylko wybrane urządzenie.
* **Zaawansowane Funkcje Mesh:**
  - **Wzmacniacze Amazon Echo "eero Built-in":** Automatyczne rozpoznawanie zgodnych głośników Echo działających jako punkty dostępowe, oznaczone odznaką **`eero Built-in`**.
  - **Wybór Bramy w Trybie Mostu (Bridge):** Niezawodna identyfikacja rzeczywistej bramy głównej na podstawie flagi `is_primary_node` i sąsiadów LLDP na porcie WAN.
  - **Oficjalne Zdjęcia Produktów eero:** Każdy węzeł prezentuje oficjalne zdjęcie swojego modelu sprzętowego (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot itp.).
  - **Asystent AI i Test Rozmieszczenia:** Interaktywna diagnostyka w czasie rzeczywistym przez SSE (`/api/network/assistant`), test propagacji fal radiowych i obsługa Guardian VPN.
* **Tryb pulpitu (Podstawowy vs Zaawansowany):** Przełącznik w prawym górnym rogu umożliwia natychmiastowe przełączanie między **Widokiem Podstawowym** (stworzonym dla zwykłych użytkowników, ze statusem sieci WAN, kondycją sieci, aktywnymi węzłami, testem prędkości i minimalną listą urządzeń online/offline) a **Widokiem Zaawansowanym** (ze szczegółami IP, DNS, podsieciami, backhaulem radiowym, wersjami oprogramowania i działaniami administracyjnymi).
