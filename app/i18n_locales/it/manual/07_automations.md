---
id: automations
title: 7. Automazioni, QR Ospiti, AdGuard Home, Telegram & Notifiche
icon: zap
summary: Smart Guest Wi-Fi con QR, integrazione AdGuard Home, allarmi Telegram/Webhook con toggle e report digest.
---
### Funzionalità Avanzate e Centro Automazioni

La scheda **Controlli & QR Ospiti** organizza le automazioni della tua rete in 4 comodi quadranti:

1. **Smart Guest Wi-Fi con QR Code Dinamico & Dual-Theme (In alto a sinistra):**
   - Genera all'istante un QR Code ad alta risoluzione con sfondo bianco puro per il tema Chiaro e sfondo ardesia scuro per il tema Scuro, sincronizzato in tempo reale con il selettore del tema.
   - Toggle per abilitare/disabilitare la rete ospiti con un clic.
   - Generatore integrato di password sicure e aggiornamento credenziali senza accedere all'app mobile.
2. **Multi-Engine DNS Synchronizer (In alto a destra):**
   - **Supporto Multi-Engine Eterogeneo:** Gestione simultanea di molteplici istanze di AdGuard Home, Pi-hole (v5 & v6) e Technitium DNS (record diretti A e Reverse PTR).
   - **Auto-Sync Continuo:** Il poller di background allinea automaticamente i server DNS configurati all'accesso di nuovi dispositivi.
   - **Intelligent Address Pruning & Esclusione IPv6 (v1.5.0, v1.6.1):** Opzioni dedicate per singola istanza DNS per potare automaticamente vecchi IP scaduti e lease obsoleti (anche per Pi-hole v6 via PATCH `/api/config`), con prioritizzazione automatica della subnet LAN fisica eero rispetto ai bridge virtuali Docker (`172.17.x.x`). Include il toggle per singolo apparato *"Escludi da sincronizzazione DNS"* (`dns_sync_excluded`) nel modale dispositivo.
   - **Pulsanti "Test" e "Sincronizza":** Verifica rapida della singola istanza o globale, con trigger di sincronizzazione immediata con un solo clic.
   - **Esportazione Standard:** Endpoint `/api/devices/export/hosts` (standard `/etc/hosts`) e `/api/devices/export/adguard` (JSON provisioning).
3. **Notifiche Telegram & Webhook (In basso a sinistra):**
   - **Registro Persistente Dispositivi Noti:** Tabella SQLite `known_devices` per memorizzare gli apparati già visti ed evitare qualsiasi invio di notifiche duplicate al riavvio o all'aggiornamento del container.
   - **Toggle di Abilitazione Dedicato:** Attiva o disattiva l'invio delle notifiche Telegram con un semplice clic senza eliminare le chiavi salvate.
   - **Nuovo Dispositivo Connesso:** Alert istantaneo quando un apparato mai visto prima si connette alla rete.
   - **Nodo Mesh Offline:** Notifica immediata se un ripetitore eero perde la connessione.
   - **Pulsante "Invia Test":** Verifica il corretto recapito dei messaggi verso il bot Telegram e l'URL Webhook.
4. **Report Digest Giornaliero (In basso a destra):**
   - **Toggle di Abilitazione Programmata & Orario Personalizzabile (v1.6.1):** Consente di attivare o sospendere l'inoltro automatico e selezionare l'orario desiderato (00:00 - 23:00, default 21:00) con supporto alle variabili `DAILY_DIGEST_HOUR` e `TZ`.
   - **Protezione Idempotente ai Riavvii:** Tracciamento su SQLite di `last_daily_digest_date` per garantire un solo invio al giorno senza duplicati in caso di riavvio del container.
   - Invia un riepilogo dettagliato con: stato di salute della rete, ISP, nodi mesh online, client connessi suddivisi per frequenza (**6 GHz, 5 GHz, 2.4 GHz, Cablati**) e velocità Speed Test Gateway.
   - Pulsante **"Genera & Invia Digest Ora"** per richiedere l'inoltro immediato del report in qualsiasi momento.
5. **Gaming & Focus Mode (Bassa Latenza):**
   - Accessibile direttamente dalla barra superiore: sospende temporaneamente il traffico dei dispositivi secondari (Smart TV, download di backup) per azzerare la latenza e il jitter a favore delle postazioni da gioco competitive.
