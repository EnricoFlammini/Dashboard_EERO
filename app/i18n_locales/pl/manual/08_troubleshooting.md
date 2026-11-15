---
id: troubleshooting
title: 8. Rozwiązywanie Problemów, Aktualizacje i FAQ
icon: wrench
summary: Często zadawane pytania dotyczące telemetrii, aktualizacji Docker, bezpieczeństwa, kopii zapasowych i napraw.
---
### Często Zadawane Pytania i Diagnostyka

* **Jak działa automatyczna aktualizacja kontenera Docker z poziomu aplikacji?**
  - Pakiet cyklicznie sprawdza dostępność nowych wydań na Docker Hub i GitHub Releases.
  - Przy podłączonym gnieździe Docker (`/var/run/docker.sock`) kliknięcie **"Zaktualizuj kontener teraz"** pobiera nowy obraz i odtwarza kontener z zachowaniem wolumenu `./data`.
* **Jakie dane urządzeń pochodzą bezpośrednio z infrastruktury eero?**
  - Stan połączenia, lokalny IP, adres MAC, węzeł nadrzędny, pasmo częstotliwości (**2.4 GHz, 5 GHz, 6 GHz lub Przewodowe**), kanał, moc sygnału w **dBm** oraz fizyczna prędkość połączenia (**PHY Link Rate**).
* **Zabezpieczenia i Ochrona Danych:**
  - **Ochrona CORS i CSRF:** Domyślnie zablokowane zapytania cross-origin i weryfikacja nagłówków żądań modyfikujących.
  - **Filtrowanie Haseł Wi-Fi:** Hasła sieciowe są usuwane przed prezentacją w publicznych punktach API.
  - **Ścisłe Uprawnienia:** Plik `session.json` zapisywany jest z restrykcyjnymi uprawnieniami `0600`.
* **Co zrobić, gdy sesja eero wygaśnie?**
  - Kliknij **Wyloguj** w menu bocznym i przejdź ponownie procedurę logowania (SMS, e-mail lub Amazon OAuth2).
* **Jak utworzyć kopię zapasową konfiguracji lokalnej?**
  - Wszystkie własne ustawienia (nazwy, kategorie, notatki, historia pomiarów) znajdują się w pliku `./data/metrics.db`. Wystarczy skopiować folder `./data`.
* **Dlaczego logowanie SMS/e-mail zwraca błąd 401?**
  - Jeśli konto eero zostało powiązane z profilem Amazon, skorzystaj z opcji **"Zaloguj się przez Amazon (OAuth2 / PKCE)"** w oknie logowania.
* **Jak skonfigurować Custom & Split DNS?**
  - Ustaw zmienne środowiskowe `CUSTOM_DNS_SERVERS` oraz `CUSTOM_DNS_DOMAINS`, aby lokalne zapytania były kierowane bezpośrednio do wewnętrznych serwerów DNS.
* **Jak działa automatyczna naprawa bazy SQLite?**
  - W razie uszkodzenia pliku w wyniku nagłego braku zasilania procedura naprawcza (`REINDEX`, odtworzenie tabel, odbudowa) przywraca spójność danych i zachowuje kopię `.corrupt.bak`.
