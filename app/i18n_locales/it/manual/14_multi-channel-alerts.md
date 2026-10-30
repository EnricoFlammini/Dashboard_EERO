---
id: multi-channel-alerts
title: 14. Allarmi Multi-Canale & Notifiche Emergenza
icon: bell
summary: Dispatcher multi-canale (Telegram, Discord, Webhook, Pushover) e allarmi specializzati di sicurezza, degradamento linea e backup.
---
### Allarmi Multi-Canale & Notifiche di Emergenza (v1.6.0)

Il motore di notifica supporta una strategia di inoltro multi-canale per avvisi critici ed eventi di rete:

* **Canali Supportati:**
  - **Telegram Bot:** Messaggistica istantanea formattata HTML con pulsanti di interazione rapida.
  - **Discord Webhook:** Notifiche ricche con embed card grafiche, codici colore e metadati evento.
  - **Pushover:** Notifiche push prioritarie per smartphone con supporto alert di emergenza.
  - **Generic Webhook:** Payload JSON per l'integrazione con Node-RED, Home Assistant automations o script custom.
* **Allarmi Specializzati Integrati:**
  - **Degrado Bufferbloat:** Notifica tempestiva quando la latenza sotto carico peggiora (Grade D o F, o latenza caricata > 100ms).
  - **Anomalie Qualità Nodo Mesh:** Avviso su canali DFS radar o degrado del backhaul wireless di un nodo mesh.
  - **Allarme Sicurezza Autenticazione (Brute-Force):** Segnalazione di tentativi consecutivi di login fallito da indirizzi IP sospetti.
  - **Esito Backup Notturno:** Conferma di avvenuto backup dei dati SQLite e dei file di log o notifica di errore.
