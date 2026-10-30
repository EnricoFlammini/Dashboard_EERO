---
id: offline-first
title: 15. Architettura Offline-First & Asset Locali
icon: shield-check
summary: Resilienza totale della dashboard con font e librerie salvati in locale, zero dipendenze CDN esterne e funzionamento air-gapped.
---
### Architettura Offline-First & Asset Locali (v1.6.0)

La dashboard adotta un'architettura 100% offline-first per garantire privacy assoluta, velocità istantanea di rendering e operatività anche in assenza di connettività internet o in blackout WAN:

* **Vendoring Locale Completo delle Dipendenze:**
  - Tutte le librerie client-side (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons e generatori QR Code) sono archiviate e servite direttamente dalla directory locale `/app/static/vendor/`.
  - Nessuna richiesta verso CDN pubbliche esterne (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`, `unpkg.com`): zero tracking da parte di terzi e immunità totale rispetto a blocchi DNS, filtri parental control o ad-blocker aggressivi.
* **Self-Hosting dei Font Tipografici:**
  - I font ad alta leggibilità **Inter** (interfaccia utente) e **JetBrains Mono** / **Fira Code** (console terminale e tabelle telemetriche) sono inclusi nel container in formato WOFF2 ad alte prestazioni in `/app/static/fonts/`.
  - Caricamento istantaneo senza alcun contatto con Google Fonts o server esterni.
* **Resilienza Air-Gapped & Homelab Isolati:**
  - La dashboard si avvia, carica e renderizza con fluidità al 100% all'interno di reti LAN isolate, VLAN di gestione o server homelab senza accesso alla rete internet pubblica.
* **Progressive Web App (PWA) & Service Worker:**
  - Il Service Worker integrato (`sw.js`) effettua il pre-caching di tutte le risorse essenziali, consentendo l'apertura e la consultazione della dashboard anche durante interruzioni temporanee della rete locale.
