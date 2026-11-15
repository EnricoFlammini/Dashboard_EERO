---
id: automations
title: 7. Automazioni, QR Ospiti, AdGuard Home, Telegram & Notifiche
icon: zap
summary: Smart Guest Wi-Fi con QR, integrazione AdGuard Home, avvisi Telegram/Webhook con toggle e report digest.
---
### Funzionalità Avanzate e Centro Automazioni

La scheda **Controlli & QR Ospiti** organizza gli strumenti della tua rete in una griglia 2x2 di quattro schede, più un quinto elemento, la Gaming Mode, posizionato nell'intestazione superiore:

1. **Smart Guest Wi-Fi con QR Code Dinamico & Dual-Theme (In alto a sinistra):**
   - Genera all'istante un QR Code stampabile e scansionabile con sfondo bianco puro per il tema Chiaro e sfondo ardesia scuro per il tema Scuro, sincronizzato automaticamente con il tema attivo.
   - Toggle per attivare/disattivare la rete ospiti con un clic.
   - Generatore integrato di password sicure e aggiornamento delle credenziali.
2. **Multi-Engine DNS Synchronizer (In alto a destra):**
   - **Supporto Multi-Engine Eterogeneo:** Gestione simultanea di molteplici istanze di AdGuard Home, Pi-hole (v5 & v6) e Technitium DNS (record diretti A e Reverse PTR).
   - **Auto-Sync Continuo:** Il poller di background allinea automaticamente i server DNS configurati all'accesso di nuovi dispositivi.
   - **Intelligent Address Pruning, Unico Proprietario & Custom DNS (v1.6.1, v1.7.0):** Risolve conflitti di lease DHCP riassegnati (`ip_owner`), sanifica hostname RFC 1123 e supporta **Custom & Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) per interrogare server DNS locali (BIND/AdGuard/Pi-hole) con priorità IPv4-first (`AF_INET`). Include il toggle per singolo dispositivo *"Escludi da sincronizzazione DNS"* (`dns_sync_excluded`) nel modale dispositivo.
   - **Pulsanti "Test" e "Sincronizza":** Verifica rapida della singola istanza o globale, con trigger di sincronizzazione immediata con un solo clic.
   - **Esportazione Standard:** Endpoint `/api/devices/export/hosts` (standard `/etc/hosts`) e `/api/devices/export/adguard` (JSON provisioning).
3. **Notifiche Telegram & Webhook (In basso a sinistra):**
   - **Registro Persistente & Lock Anti-Tempesta (Issue #112):** Tabella SQLite `known_devices` e lock asincrono `_poll_lock` che isola i MAC demo e garantisce che il primo ciclo autenticato dopo il login non generi false notifiche per i dispositivi già presenti.
   - **Toggle di Attivazione Dedicato:** Attiva o disattiva l'invio delle notifiche Telegram con un semplice clic senza eliminare le chiavi salvate.
   - **Nuovo Dispositivo Connesso:** Avviso istantaneo quando un dispositivo mai visto prima si connette alla rete.
   - **Nodo Mesh Offline:** Notifica immediata se un nodo eero perde la connessione.
   - **Pulsante "Invia Test":** Verifica il corretto recapito dei messaggi verso il bot Telegram e l'URL Webhook.
4. **Riepilogo Giornaliero (In basso a destra):**
   - **Toggle di Attivazione Programmata & Orario Personalizzabile (v1.6.1, v1.7.0):** Consente di attivare o sospendere l'inoltro automatico e selezionare l'orario desiderato (00:00 - 23:00, default 21:00) con supporto alle variabili `DAILY_DIGEST_HOUR` e `TZ` e binding reattivo dell'ora salvata (Issue #113).
   - **Protezione Idempotente ai Riavvii:** Tracciamento su SQLite di `last_daily_digest_date` per garantire un solo invio al giorno senza duplicati in caso di riavvio del container.
   - Invia un riepilogo dettagliato con: Punteggio di Salute della Rete, ISP, nodi mesh online, client connessi suddivisi per frequenza (**6 GHz, 5 GHz, 2.4 GHz, Cablati**) e velocità Speed Test del Gateway e latenza (ping).
   - Pulsante **"Genera & Invia Digest Ora"** per richiedere l'inoltro immediato del report in qualsiasi momento.
5. **Gaming & Focus Mode (Bassa Latenza):**
   - Accessibile direttamente dalla barra superiore: sospende con un solo clic i dispositivi in background contrassegnati (streaming/download) per eliminare latenza e jitter nelle postazioni da gioco competitive.
6. **Regole Firewall IPv6 Pinhole (v1.7.0 - Issue #90):**
   - Gestione visiva in Impostazioni Rete per creare e revocare regole firewall IPv6 per porte TCP/UDP su singoli client locali, senza dover ricorrere all'app mobile eero.
