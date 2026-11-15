---
id: troubleshooting
title: 8. Risoluzione Problemi, Aggiornamenti & FAQ
icon: wrench
summary: FAQ su telemetria, motore di auto-aggiornamento Docker, sicurezza, backup e manutenzione.
---
### Domande Frequenti & Troubleshooting

* **Come funziona il motore di Auto-Update Docker in-App?**
  - La dashboard controlla periodicamente la presenza di nuove versioni su Docker Hub e GitHub Releases.
  - Se è montato il Docker Socket (`/var/run/docker.sock`), facendo clic su **"Aggiorna Container Ora"** l'applicazione scaricherà la nuova immagine, ricreerà il container preservando il volume `./data` e ricaricherà il browser quando la nuova versione è operativa.
  - In alternativa sono supportati trigger via **Watchtower Webhook** e modalità assistita da riga di comando.
* **Quali dati sui dispositivi provengono direttamente dall'infrastruttura eero?**
  - La dashboard interroga l'infrastruttura eero leggendo: lo stato di connessione (Online/Offline), l'indirizzo IP locale, il MAC Address, il nodo mesh a cui sono associati (Gateway o Beacon), la banda radio Wi-Fi (**2.4 GHz, 5 GHz, 6 GHz o Cablato (Ethernet)**), il canale wireless (**CH**), il livello del segnale in **dBm** e la velocità di link fisico negoziata (**PHY Link Rate**).
* **Hardening di Sicurezza & Protezione Dati:**
  - **CORS & Protezione CSRF:** Accesso cross-origin disattivato di default (configurabile con `CORS_ORIGINS`) e blocco delle richieste cross-site mutanti con intestazioni `Sec-Fetch-Site`.
  - **Sanitizzazione Password Wi-Fi:** Le credenziali Wi-Fi sono rimosse ricorsivamente prima dell'esposizione nella cache pubblica `/api/network/overview`.
  - **Documentazione Interattiva FastAPI Disattivata di Default:** `/docs`, `/redoc` e `/openapi.json` sono montati solo con `API_DOCS=true` per proteggere gli endpoint operativi.
  - **Permessi Restrittivi 0600 su session.json:** Il token cloud eero viene creato e salvato con permessi `0600` (lettura/scrittura esclusiva del proprietario del file).
* **Come configurare l'integrazione con AdGuard Home?**
  - Nella scheda *Controlli & QR Ospiti*, inserisci l'URL della tua istanza (es. `http://192.168.4.100:8085` o semplicemente `192.168.4.100:8085`), il tuo username e la password. Clicca su **Test Connessione** per verificare il collegamento e poi su **Salva Impostazioni AdGuard**. Le credenziali vengono cifrate e salvate in modo sicuro nel database SQLite locale.
* **Cosa fare se la sessione scade?**
  - Se ricevi un errore di autorizzazione, clicca sul pulsante **Disconnetti** nella barra laterale o nella schermata di login e riesegui la procedura di ricezione del codice OTP a 6 cifre.
* **Come effettuare il backup delle configurazioni e metadati locali?**
  - Tutti i dati personalizzati (nomi personalizzati, categorie, note, impostazioni notifiche, storico segnale e AdGuard) sono contenuti nel file `./data/metrics.db`. Per fare un backup completo, è sufficiente copiare la cartella `./data` sul tuo computer o archivio cloud.
* **Perché il login email/SMS non mostra reti o fallisce con errore 401?**
  - Se il tuo account eero è stato collegato o migrato ad Amazon, l'accesso tradizionale via email/SMS viene disabilitato dai server eero. Utilizza la sezione **"Accedi con Amazon (OAuth2 / PKCE)"** nella modale di login per autenticarti tramite il flusso federato sicuro.
* **Come risolvere FQDN interni e domini locali con Custom & Split DNS?**
  - Se il container non riesce a risolvere host interni della tua LAN (es. `adguard.casa.lan`), puoi impostare le variabili d'ambiente `CUSTOM_DNS_SERVERS` (es. `192.168.4.13`) e `CUSTOM_DNS_DOMAINS` (es. `*.casa.lan=192.168.4.13`). Il resolver integrato eseguirà query UDP dirette con priorità IPv4-first, senza bisogno di modificare i file di sistema.
* **Come interviene l'auto-riparazione automatica SQLite se il database si danneggia?**
  - In caso di arresto brusco del server durante un checkpoint WAL, la suite attiva un motore di self-healing a 3 stadi (`repair_if_malformed`): tenta prima una reindicizzazione con `REINDEX`, poi ricrea la tabella compromessa, e se il file è corrotto esegue un salvataggio integrale delle impostazioni e ricrea un database pulito, conservando una copia `.corrupt.bak`.
* **Protezione da Rate Limiting:**
  - L'applicazione interroga il cloud eero a intervalli definiti dal poller (default 10s-30s) e risponde a tutte le richieste dell'interfaccia direttamente dalla memoria RAM del server, azzerando il rischio di blocco da parte dei server eero.
