---
id: multi-channel-alerts
title: 14. Avvisi Multi-Canale & Notifiche Emergenza
icon: bell
summary: Dispatcher multi-canale (Telegram, Discord, Webhook, Pushover, Ntfy, Apprise per Microsoft Teams, Slack, Google Chat e Gotify) e avvisi specializzati di sicurezza, degradamento linea e backup.
---
### Avvisi Multi-Canale & Notifiche di Emergenza (v1.6.0)

Il motore di notifica supporta una strategia di inoltro multi-canale per avvisi critici ed eventi di rete:

* **Canali Supportati:**
  - **Telegram Bot:** Avvisi istantanei formattati in HTML con dettagli diretti su nodo e client.
  - **Discord Webhook:** Notifiche ricche con embed card grafiche, codici colore e metadati evento.
  - **Pushover:** Notifiche push prioritarie per smartphone per un recapito immediato.
  - **Generic Webhook:** Payload JSON grezzi per pipeline personalizzate (Node-RED, n8n, Home Assistant).
  - **Ntfy:** Notifiche push tramite ntfy.sh o un server ntfy self-hosted.
  - **Apprise:** Un'unica impostazione per raggiungere Microsoft Teams, Slack, Google Chat, Gotify e oltre 100 altri servizi (vedi sotto).
* **Avvisi Specializzati Integrati:**
  - **Degrado Bufferbloat:** Notifica tempestiva quando la latenza sotto carico peggiora (Voto D o F, o delta di latenza sotto carico > 100 ms).
  - **Anomalie Qualità Nodo Mesh:** Avviso su canali DFS radar o degrado del backhaul wireless di un nodo mesh.
  - **Avviso di Sicurezza Autenticazione (Brute-Force):** Segnalazione di tentativi consecutivi di login falliti da indirizzi IP sospetti.
  - **Esito Backup Notturno:** Esito (riuscito o fallito) del backup automatico degli archivi di database e configurazione.

### Apprise: Microsoft Teams, Slack, Google Chat, Gotify e altro (v1.8.0)

[Apprise](https://github.com/caronc/apprise) è una libreria di notifica inclusa nella dashboard. Funziona all'interno dell'applicazione e invia direttamente a ciascun servizio, senza server o account aggiuntivi. Attivala in **Notifiche** e inserisci uno o più URL Apprise, separati da virgole o spazi. Si possono impostare anche con la variabile d'ambiente `APPRISE_URLS`. Dopo il salvataggio gli URL vengono mascherati (`••••••••`) e **Test** invia un messaggio di prova a tutti i servizi configurati.

Gli avvisi mantengono la loro gravità: avvertimenti, errori e ripristini mostrano icone e colori corrispondenti, e grassetto, valori in codice ed elenchi vengono convertiti nella formattazione di ciascun servizio.

* **Microsoft Teams:** incolla l'URL del webhook di Workflows esattamente come lo fornisce Teams (un indirizzo `powerplatform.com` o `logic.azure.com`).
  - Crea il webhook **da Teams**: sul canale o sulla chat apri **⋯ → Workflows** e scegli il modello **Send webhook alerts to a channel** (o **to a chat**). Si ottiene un URL firmato che termina con `&sig=…`.
  - I flussi creati nel designer di Power Automate possono offrire solo *Qualsiasi utente nel mio tenant*. Questa opzione richiede un token OAuth, che Apprise non può fornire, quindi questi URL vengono rifiutati con HTTP 401.
  - Per avvisi personali, pubblica in **Chat with Flow bot** indicando te stesso come destinatario. Teams elenca la chat "(Tu)" come destinazione, ma l'invio fallisce ("not a ChatThread").
* **Slack:** `slack://TokenA/TokenB/TokenC/#canale`, ricavato da un URL di incoming webhook. Funziona anche l'URL completo `https://hooks.slack.com/services/…`.
* **Google Chat:** incolla l'URL del webhook dello spazio (`https://chat.googleapis.com/v1/spaces/…`).
* **Gotify:** `gotify://tuo-server/AppToken` (oppure `gotifys://` per HTTPS).
* **Altri servizi:** tutti gli altri formati di URL Apprise sono supportati senza garanzia. Consulta la [wiki di Apprise](https://github.com/caronc/apprise/wiki) per l'elenco completo.
