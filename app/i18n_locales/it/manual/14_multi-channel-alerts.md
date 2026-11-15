---
id: multi-channel-alerts
title: 14. Avvisi Multi-Canale & Notifiche Emergenza
icon: bell
summary: Dispatcher multi-canale (Telegram, Discord, Webhook, Pushover) e avvisi specializzati di sicurezza, degradamento linea e backup.
---
### Avvisi Multi-Canale & Notifiche di Emergenza

Il motore di notifica supporta una strategia di inoltro multi-canale per avvisi critici ed eventi di rete:

* **Canali Supportati:**
  - **Telegram Bot:** Avvisi istantanei formattati in HTML con dettagli diretti su nodo e client.
  - **Discord Webhook:** Notifiche ricche con embed card grafiche, codici colore e metadati evento.
  - **Pushover:** Notifiche push prioritarie per smartphone per un recapito immediato.
  - **Ntfy (sh) Nativo:** Supporto a server pubblici `ntfy.sh` o istanze self-hosted con priorità, tag contestuali e autenticazione bearer token.
  - **Generic Webhook:** Payload JSON grezzi per pipeline personalizzate (Node-RED, n8n, Home Assistant).
* **Controlli Visivi & Mascheramento Segreti:**
  - Tutti i canali dispongono di pannelli di configurazione grafici dedicati in *Impostazioni -> Controlli* con pulsanti di **Test Immediato**.
  - Token e URL dei webhook sono mascherati con `••••••••` per prevenire fughe di credenziali accidentali (shoulder surfing o log inspection).
* **Avvisi Specializzati Integrati:**
  - **Degrado Bufferbloat:** Notifica tempestiva quando la latenza sotto carico peggiora (Voto D o F, o delta di latenza sotto carico > 100 ms).
  - **Anomalie Qualità Nodo Mesh:** Avviso su canali DFS radar o degrado del backhaul wireless di un nodo mesh.
  - **Avviso di Sicurezza Autenticazione (Brute-Force):** Segnalazione di tentativi consecutivi di login falliti da indirizzi IP sospetti.
  - **Esito Backup Notturno:** Esito (riuscito o fallito) del backup automatico degli archivi di database e configurazione.
