---
id: auth-flow
title: 2. Uwierzytelnianie i Zarządzanie Dostępem (RBAC / 2FA)
icon: key
summary: Wstępna konfiguracja administratora (Zero-Default), lokalne role RBAC i procedura logowania 2FA eero.
---
### Zarządzanie Dostępem, Wstępna Konfiguracja i Uwierzytelnianie

#### 1. Wstępna Konfiguracja Administratora (Zasada Zero-Default)
Przy pierwszym uruchomieniu pakiet stosuje ścisłą politykę bezpieczeństwa bez domyślnych haseł:
- **Kreator Konfiguracji:** Jeśli w bazie nie ma jeszcze użytkowników, automatycznie wyświetla się okno konfiguracji, w którym administrator definiuje nazwę użytkownika oraz silne hasło.
- **Automatyzacja Headless Docker (Opcjonalnie):** W przypadku wdrożeń automatycznych można ustawić zmienne środowiskowe `ADMIN_USER` i `ADMIN_PASSWORD` w pliku `.env` lub `docker-compose.yml`. Konto administratora zostanie utworzone bez kreatora.
- **Granularne Role i Uprawnienia (RBAC):** W sekcji *Ustawienia -> Użytkownicy i Uprawnienia* administrator może dodawać kolejne konta z określonymi rolami (`Admin`, `Operator`, `Viewer`) i dostosowywać uprawnienia operacyjne.

#### 2. Uwierzytelnianie w Chmurze eero (2FA OTP)
Po zakończeniu logowania lokalnego (lub jeśli uwierzytelnianie lokalne nie jest wymagane):
1. **Żądanie Kodu OTP:** Wprowadź adres e-mail lub numer telefonu powiązany z kontem eero i kliknij **"Wyślij kod OTP"**.
2. **Weryfikacja Kodu:** Wpisz 6-cyfrowy kod otrzymany w wiadomości SMS lub e-mail i zatwierdź.
3. **Zapisywanie Sesji:** Zweryfikowany token jest zapisywany w pliku `/app/data/session.json` z uprawnieniami `0600`, zachowując ważność po restarcie kontenera.
4. **Tryb Demo i Szybkie Przełączanie:** Wypróbuj funkcje bez wprowadzania danych logowania za pomocą przycisku **"✨ Tryb Demo"** lub ustawiając `DEMO_MODE=true`.

#### 3. Natywne Logowanie Amazon OAuth2 / PKCE
Dla kont eero powiązanych z kontem Amazon dostępny jest oficjalny przepływ **Amazon OAuth2 z PKCE S256 (RFC 7636)**:
1. **Logowanie Amazon:** Kliknij **"🛒 Zaloguj się przez Amazon"** w oknie logowania, aby zainicjować bezpieczny proces PKCE.
2. **Autoryzacja w Przeglądarce:** Zaloguj się w serwisie Amazon i zaakceptuj uprawnienia; nastąpi przekierowanie na stronę `/ap/maplanding`.
3. **Natychmiastowe Powiązanie:** Skopiuj adres przekierowania lub parametr `code`, wklej go w wyznaczonym polu i zatwierdź przyciskiem **"Połącz konto eero"**.

#### 4. Globalne Bezpieczeństwo i Wymuszenie `REQUIRE_LOCAL_AUTH`
W środowiskach współdzielonych ustawienie `REQUIRE_LOCAL_AUTH=true` w pliku `.env` zapewnia:
- Ochronę wszystkich punktów końcowych API (`/api/*`) oraz metryk Prometheus (`/metrics`) wymagających aktywnej sesji użytkownika.
- Publicznie dostępne pozostają jedynie podstawowe ścieżki weryfikacji stanu i logowania (`/api/health`, `/api/auth/local/*`, `/api/system/language`).
