---
id: device-details
title: 5. Metadane Urządzenia, Statyczne IP i Przekierowanie Portów
icon: adjustments
summary: Profil, własne nazwy, ikony kategorii, lokalne notatki, rezerwacje DHCP, IPv6 i port forwarding.
---
### Zarządzanie i Konfiguracja Pojedynczego Urządzenia

* **Szczegóły Urządzenia:**
  - **Własna Nazwa i Kategoria:** Przypisywanie kategorii (Komputer, Telefon, Smart Home, Rozrywka, Gry, Serwer/NAS, Inne) zapisywanych w lokalnej bazie SQLite.
  - **Lokalne Notatki i Dokumentacja:** Pole na własne informacje o danych logowania, lokalizacji fizycznej czy portach usług.
  - **Adresy Dual-Stack IPv6 i Kopiowanie 1-Kliknięciem:** Dedykowany blok prezentujący adresy SLAAC i Link-Local z przyciskiem szybkiego kopiowania do schowka.
  - **Rezerwacja DHCP (Statyczny IP):** Przypisanie stałego adresu IP z automatyczną weryfikacją konfliktów.
  - **Przekierowanie Portów i Firewall IPv6:** Konfiguracja reguł przekierowania IPv4 (Port WAN -> Port LAN) oraz otwierania portów pinhole IPv6 na protokołach TCP/UDP.
  - **Zmiana Profilu:** Bezpośrednie przypisanie urządzenia do innego profilu domowników.
  - **Wizualny Wybór Kategorii:** Intuicyjne ikony z możliwością przywrócenia domyślnej klasyfikacji eero.
  - **Błyskawiczna Synchronizacja Pamięci RAM:** Po zapisaniu metadanych pamięć podręczna jest natychmiast odświeżana bez oczekiwania na kolejny cykl odpytywania.
