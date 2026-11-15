---
id: system-logs
title: 11. Dzienniki Systemowe i Zaawansowana Diagnostyka
icon: terminal
summary: Konsola dziennika na żywo, dynamiczne poziomy szczegółowości, retencja, eksport i bezpieczne czyszczenie.
---
### Zarządzanie Dziennikiem Systemowym i Diagnostyka

Moduł **Zarządzanie Dziennikami i Diagnostyka** zapewnia pełny wgląd w zdarzenia systemowe:

* **Główny Wyłącznik Rejestrowania:** Umożliwia włączanie lub wstrzymywanie zapisu zdarzeń do lokalnej bazy SQLite i rotacyjnego pliku na dysku (`data/system.log`).
* **Dynamiczne Poziomy Szczegółowości bez Restartu:**
  - `DEBUG`: Dokładny zapis wszystkich wywołań API i synchronizacji.
  - `INFO`: Standardowa rejestracja istotnych zdarzeń i połączeń.
  - `WARNING`: Ostrzeżenia o opóźnieniach i anomaliach sygnału.
  - `ERROR`: Wyłącznie krytyczne błędy i wyjątki blokujące.
* **Automatyczny Czas Przechowywania:** Ustalanie okresu retencji: 24h, 7 dni, 15 dni, 1 miesiąc lub okres niestandardowy (z automatycznym usuwaniem starych wpisów w tle).
* **Podgląd Dziennika na Żywo:** Terminal o wysokim kontraście ze stałą szerokością znaków, wyszukiwaniem pełnotekstowym, filtrami wagi i odświeżaniem co 10 sekund.
* **Eksport i Czyszczenie:** Pobieranie pliku `.log` w formacie RFC 5424 lub `.json` oraz bezpieczne usuwanie wpisów chronione uprawnieniami RBAC.
