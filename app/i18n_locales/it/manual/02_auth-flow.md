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
