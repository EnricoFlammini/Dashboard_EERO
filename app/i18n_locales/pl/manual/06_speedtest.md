---
id: speedtest
title: 6. Test Prędkości, Diagnostyka i Jakość Sygnału Wi-Fi
icon: gauge
summary: Pomiary przepustowości, historia wyników, analiza sygnału RSSI i zasięg sieci mesh.
---
### Diagnostyka Łącza i Pokrycie Radiowe Wi-Fi

* **Ręczny Test Prędkości:** Kliknij **"Uruchom Speed Test"**, aby zmierzyć w czasie rzeczywistym prędkość pobierania, wysyłania, ping i jitter.
* **Zaplanowane Pomiary Automatyczne:** System może wykonywać cykliczne testy w tle (np. co 12 godzin), rejestrując stabilność łącza w czasie.
* **Wykresy Długoterminowe i Statystyki:** Wizualizacja Chart.js zmian prędkości i opóźnień z wartościami średnimi i oceną bufferbloat.
* **Jakość Wi-Fi i Pokrycie Sieci Mesh:**
  - **Historia RSSI w dBm i Uniwersalna Analiza:** Precyzyjne próbkowanie poziomów sygnału znormalizowane do zakresu `[-120, -1] dBm`.
  - **Średni Sygnał i Przedziały Jakości:** Syntetyczny wskaźnik i podział: *Doskonały* (≥ -50 dBm), *Dobry* (-51 do -65 dBm), *Dostateczny* (-66 do -75 dBm), *Krytyczny* (< -75 dBm).
  - **Dane na Żywo i Lista Urządzeń o Słabym Sygnale:** Bieżące łączenie aktywnych klientów zapewnia natychmiastową dostępność listy **Weak Signal Watchlist** (`< -75 dBm`).
  - **Interaktywny Wykres dla Urządzenia:** Przegląd historii sygnału z ostatnich 24 godzin lub 7 dni dla dowolnego urządzenia.
  - **3-Etapowa Samonaprawa SQLite:** Automatyczny mechanizm naprawy uszkodzonych indeksów lub tabel w przypadku nieoczekiwanego restartu systemu.
