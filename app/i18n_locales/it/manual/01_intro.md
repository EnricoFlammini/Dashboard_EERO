---
id: intro
title: 1. Introduzione & Architettura
icon: book-open
summary: Panoramica dell'architettura self-hosted, sicurezza 2FA/OAuth, tema 3-stati e 9 lingue europee.
---
### Cos'è eero Custom Dashboard & Management Suite?
Questa applicazione web è un sistema completo e self-hosted per il monitoraggio, il controllo e l'analisi avanzata della tua infrastruttura mesh **Amazon eero**.

#### Caratteristiche Architetturali:
1. **Self-Hosted & Riservatezza:** L'applicazione viene eseguita all'interno di un container Docker isolato sul tuo server locale o NAS (HomeLab). Immagine ufficiale Docker Hub multi-architettura pronta per `linux/amd64` e `linux/arm64` (Raspberry Pi 4/5, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Autenticazione Flessibile (2FA OTP & Amazon OAuth2):** La connessione iniziale con il cloud eero avviene tramite il meccanismo a doppio fattore ufficiale (OTP via SMS o Email) oppure tramite il flusso federato nativo **Amazon OAuth2 / PKCE** per gli account migrati.
3. **Persistenza e Isolamento:** Il token di sessione (`session.json`) e il database SQLite (`metrics.db`) risiedono esclusivamente nel volume persistente `./data:/app/data`.
4. **Zero-Latency In-Memory Poller:** Un worker asincrono in background interroga periodicamente la rete e mantiene una cache in memoria RAM, garantendo navigazione istantanea senza rallentamenti o sovraccarico di richieste (rate-limiting).
5. **Design System Windows 11 Fluent, Tema a 3 Stati & Scorciatoia `Ctrl+K`:** Interfaccia moderna con supporto ai temi Chiaro, Scuro e Sistema (Auto OS con negoziazione nativa `prefers-color-scheme` e sincronizzazione browser), barra di ricerca rapida universale `Ctrl+K` / `Cmd+K` e navigazione collassabile.
6. **Supporto Multilingua Europeo al 100% (9 Lingue):** Traduzione integrale di tutte le etichette frontend e backend per Italiano, Inglese, Francese, Spagnolo, Tedesco, Olandese, Portoghese, Polacco e Greco.
