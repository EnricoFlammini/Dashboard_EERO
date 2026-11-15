---
id: auth-flow
title: 2. Autenticazione & Gestione Accessi (RBAC / 2FA)
icon: key
summary: Setup iniziale amministratore (Zero-Default), ruoli locali RBAC e procedura di accesso 2FA eero.
---
### Gestione degli Accessi, Setup Iniziale & Autenticazione

#### 1. Setup Iniziale Amministratore (Zero-Default Security)
Al primissimo avvio dell'applicazione, la suite adotta una rigida politica di sicurezza senza credenziali predefinite hardcoded:
- **Wizard Guidato di Configurazione:** Se non è ancora presente alcun account nel database, si apre automaticamente un modale di onboarding a tutto schermo che richiede all'amministratore di impostare il proprio nome utente e una password sicura con conferma.
- **Bypass Headless Docker (Opzionale):** Per installazioni automatizzate o in ambienti container senza interfaccia, è possibile pre-popolare le variabili d'ambiente `ADMIN_USER` e `ADMIN_PASSWORD` nel file `.env` o in `docker-compose.yml`. Al primo avvio, l'applicazione creerà automaticamente l'utente amministratore bypassando il wizard interattivo.
- **Ruoli & Permessi Granulari (RBAC):** Dalla sezione *Impostazioni -> Gestione Utenti & Permessi*, l'amministratore può creare ulteriori account con ruoli differenziati (`Admin`, `Operator`, `Viewer`) e attivare/disattivare specifici permessi operativi (gestione DNS, comandi di rete, export dati, visualizzazione log).

#### 2. Autenticazione con il Cloud eero (2FA OTP)
Una volta effettuato l'accesso locale (o se l'autenticazione locale non è richiesta):
1. **Richiesta del Codice OTP:**
   - Inserisci nella schermata di login l'email o il numero di telefono associato al tuo account eero (es. `+393401234567` o `tuonome@email.com`).
   - Clicca su **"Invia Codice OTP"**.
2. **Verifica del Codice:**
   - Riceverai un codice numerico a 6 cifre via SMS o Email da parte di eero.
   - Digita il codice nel campo e conferma.
3. **Salvataggio Sessione:**
   - Il token verificato viene salvato in `/app/data/session.json` con permessi restrittivi `0600`. Ad ogni riavvio del container Docker, la sessione verrà ripristinata automaticamente senza dover reinserire l'OTP.
4. **Modalità Demo & Switch Rapido:**
   - Se desideri esplorare l'applicazione senza inserire credenziali, puoi attivare la modalità dimostrativa con il pulsante dedicato o impostando `DEMO_MODE=true` nel file `.env`.
   - Se sei già autenticato con il tuo account reale, puoi cliccare in qualunque momento sul pulsante **"✨ Demo Mode"** posizionato nella parte inferiore della barra laterale sinistra per visualizzare i dati demo senza perdere la sessione. Quando la modalità demo è attiva, il pulsante assume una vivace colorazione verde smeraldo con indicatore ad alta visibilità **"DEMO ATTIVA"** (e un badge di stato sincronizzato compare nell'header superiore); cliccando nuovamente si torna all'istante alla rete live con **"⚡ Torna a Live"**.

#### 3. Autenticazione Nativa Amazon OAuth2 / PKCE (v1.7.0 - Issue #93)
Per gli account eero collegati a un profilo Amazon (dove l'accesso via email/SMS non mostra reti o fallisce con errore 401), la dashboard integra il flusso ufficiale federato **Amazon OAuth2 con PKCE S256 (RFC 7636)**:
1. **Accesso Amazon:** Clicca sul pulsante **"🛒 Accedi con Amazon"** nella modale di login per avviare il flusso con `code_verifier` crittografico sicuro.
2. **Autorizzazione nel Browser:** Effettua il login su Amazon e concedi l'accesso ai servizi eero; al termine verrai reindirizzato all'URL ufficiale Amazon `/ap/maplanding`.
3. **Collegamento Istantaneo:** Copia l'intero URL di reindirizzamento o il parametro `code`, incollalo nel campo dedicato della dashboard e clicca su **"Collega Account eero"**. La sessione viene scambiata con il token di accesso e salvata in `session.json`.

#### 4. Sicurezza Globale & Enforcement `REQUIRE_LOCAL_AUTH` (v1.7.0 - GHSA-r5vj-jfjp-m88q)
Per ambienti esposti o reti LAN condivise, impostando `REQUIRE_LOCAL_AUTH=true` nel file `.env`:
- Tutte le rotte API (`/api/*`) e le metriche Prometheus (`/metrics`) vengono protette da middleware globale che richiede una sessione utente locale valida.
- Sono esposti pubblicamente solo gli endpoint essenziali di health check e login (`/api/health`, `/api/auth/local/*`, `/api/system/language`), prevenendo qualsiasi lettura o modifica non autorizzata da apparati terzi sulla LAN.
