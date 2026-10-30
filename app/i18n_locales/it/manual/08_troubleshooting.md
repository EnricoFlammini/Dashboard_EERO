---
id: troubleshooting
title: 8. Risoluzione Problemi, Aggiornamenti & FAQ
icon: wrench
summary: FAQ su telemetria, motore di auto-aggiornamento Docker, sicurezza, backup e manutenzione.
---
### Domande Frequenti & Troubleshooting

* **Come funziona il motore di Auto-Update Docker in-App (v1.4.0)?**
  - La dashboard controlla periodicamente la presenza di nuove versioni su Docker Hub e GitHub Releases.
  - Se è montato il Docker Socket (`/var/run/docker.sock`), puoi aggiornare il container in 1 clic: l'applicazione scaricherà la nuova immagine, ricreerà il container preservando la cartella dati `./data` e ricaricherà automaticamente la pagina.
  - In alternativa sono supportati trigger via **Watchtower Webhook** e modalità assistita da riga di comando.
* **Quali dati sui dispositivi provengono direttamente dall'infrastruttura eero?**
  - La dashboard interroga l'infrastruttura eero leggendo: lo stato di connessione (Online/Offline), l'indirizzo IP locale, il MAC Address, il nodo mesh a cui sono associati (Gateway o Beacon), la banda radio Wi-Fi (**2.4 GHz, 5 GHz, 6 GHz o Ethernet Cablato**), il canale wireless (**CH**), il livello del segnale in **dBm** e la velocità di link fisico negoziata (**PHY Link Rate**).
* **Hardening di Sicurezza & Protezione Dati (v1.5.0 - 4 Advisory GHSA):**
  - **CORS & Protezione CSRF:** Accesso cross-origin disabilitato di default (configurabile con `CORS_ORIGINS`) e blocco delle richieste cross-site mutanti con intestazioni `Sec-Fetch-Site`.
  - **Sanitizzazione Password Wi-Fi:** Le credenziali Wi-Fi sono rimosse ricorsivamente prima dell'esposizione nella cache pubblica `/api/network/overview`.
  - **Documentazione Interattiva FastAPI Disattivata di Default:** `/docs`, `/redoc` e `/openapi.json` sono montati solo con `API_DOCS=true` per proteggere gli endpoint operativi.
  - **Permessi Restrittivi 0600 su session.json:** Il token cloud eero viene creato e salvato con permessi `0600` (lettura/scrittura esclusiva del proprietario del file).
* **Come configurare l'integrazione con AdGuard Home?**
  - Nel tab *Automazioni & Controlli*, inserisci l'URL della tua istanza (es. `http://192.168.4.100:8085` o semplicemente `192.168.4.100:8085`), il tuo username e la password. Clicca su **Test Connessione** per verificare il collegamento e poi su **Salva Impostazioni AdGuard**. La password viene salvata in modo sicuro nel database SQLite locale e non viene mai esposta in chiaro.
* **Cosa fare se la sessione scade?**
  - Se ricevi un errore di autorizzazione, clicca sul pulsante **Disconnetti** nella barra laterale o nella schermata di login e riesegui la procedura di ricezione del codice OTP a 6 cifre.
* **Come effettuare il backup delle configurazioni e metadati locali?**
  - Tutti i dati personalizzati (nomi custom, icone, note, impostazioni notifiche, storico segnale e AdGuard) sono contenuti nel file `./data/metrics.db`. Per fare un backup completo, è sufficiente copiare la cartella `./data` sul tuo computer o archivio cloud.
* **Protezione da Rate Limiting:**
  - L'applicazione interroga il cloud eero a intervalli definiti dal poller (default 10s-30s) e risponde a tutte le richieste dell'interfaccia direttamente dalla memoria RAM del server, azzerando il rischio di blocco da parte dei server eero.
