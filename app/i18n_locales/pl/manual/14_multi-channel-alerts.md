---
id: multi-channel-alerts
title: 14. Alerty Wielokanałowe i Powiadomienia Awaryjne
icon: bell
summary: Dyspozytor wielokanałowy (Telegram, Discord, Webhook, Pushover, Ntfy) i specjalistyczne alerty sieciowe.
---
### Alerty Wielokanałowe i Powiadomienia Awaryjne

Moduł powiadomień umożliwia równoległe przesyłanie krytycznych alertów wieloma kanałami:

* **Obsługiwane Kanały:**
  - **Telegram Bot:** Błyskawiczne komunikaty w formacie HTML ze szczegółami urządzeń i węzłów.
  - **Discord Webhook:** Rozbudowane powiadomienia w formie kart z oznaczeniem kolorystycznym.
  - **Pushover:** Priorytetowe powiadomienia push na urządzenia mobilne.
  - **Natywny Ntfy (sh):** Obsługa serwerów publicznych `ntfy.sh` oraz instancji prywatnych z obsługą tokenów.
  - **Generic Webhook:** Surowe ładunki JSON do integracji z zewnętrznymi systemami (Node-RED, n8n, Home Assistant).
* **Karty Konfiguracji i Maskowanie Haseł:**
  - Przejrzyste panele w menu *Ustawienia -> Sterowanie* z przyciskiem **Testuj natychmiast**.
  - Zabezpieczenie tokenów i adresów URL w postaci `••••••••` przed przypadkowym ujawnieniem.
* **Wbudowane Alerty Specjalistyczne:**
  - **Pogorszenie Bufferbloat:** Ostrzeżenie przy gwałtownym wzroście opóźnień pod obciążeniem.
  - **Niestabilność Węzła Mesh:** Informacja o wykryciu radaru DFS lub degradacji połączenia bezprzewodowego.
  - **Podłączenie Nieznanego Urządzenia:** Natychmiastowy alert po wykryciu nowego sprzętu w sieci.
  - **Odłączenie Węzła:** Komunikat awaryjny w przypadku utraty łączności przez punkt eero.
