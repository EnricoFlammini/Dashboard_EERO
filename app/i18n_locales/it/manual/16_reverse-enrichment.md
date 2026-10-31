---
id: reverse-enrichment
title: 16. Reverse Client Enrichment & Scoperta IPv6 ULA
icon: arrows-right-left
summary: Arricchimento bidirezionale delle interfacce secondarie dai server DNS locali, discovery IPv6 Unique Local Address (ULA) e client Recently Joined.
---
### Reverse Client Enrichment & Scoperta IPv6 ULA (v1.6.0)

Nelle reti dual-stack, i dispositivi interrogano spesso i server DNS locali (AdGuard Home, Pi-hole, Technitium) utilizzando indirizzi **IPv6 ULA** (*Unique Local Address*, prefissi `fc00::/7` e `fd00::/8`). Poiché questo traffico rimane confinato a livello Layer 2 locale e non attraversa la WAN, il cloud eero non ha visibilità su tali indirizzi.

* **Reverse Client Enrichment via NDP & Ingestion REST:**
  - **Worker di Scansione Automatica:** Il servizio di enrichment esegue periodicamente la scansione della tabella di vicinato (Neighbor Discovery Protocol - NDP / ARP del kernel) e interroga le API dei server DNS locali per mappare gli indirizzi ULA orfani ai relativi indirizzi MAC fisici.
  - **API di Ingestion Esterna (`POST /api/network/enrichment/neighbors`):** Consente a script di cron, container sidecar o motori di script esterni di inviare associazioni IP-MAC in tempo reale.
  - **Sincronizzazione Completa (Full-Circle):** Gli indirizzi ULA scoperti vengono integrati nei record dei client e sincronizzati di nuovo verso i server DNS, associando automaticamente le query con il solo indirizzo IP al nome leggibile del dispositivo.
* **Badge Distintivo UI & Ispezione Dettagliata:**
  - La tabella dispositivi e il modale di dettaglio evidenziano gli indirizzi scoperti con il badge distintivo fucsia/ametista **`ULA Enriched`** o **`ULA (NDP / AdGuard)`**.
  - Ricerca istantanea nella tabella dispositivi per prefisso o indirizzo IPv6 ULA completo.
* **Dispositivi "Recently Joined" & Badge "NEW":**
  - La dashboard traccia la data di prima apparizione (`first_seen`) di ciascun dispositivo nella tabella persistente `known_devices`.
  - I dispositivi rilevati nelle ultime 24-48 ore vengono evidenziati con il badge visivo ad alta visibilità **`NEW`** con indicatore animato verde smeraldo, ed è disponibile un ordinamento rapido per data di primo accesso.
* **Ciclo di Pulizia & Auto-Pruning:**
  - Una routine programmata di manutenzione notturna rimuove automaticamente gli indirizzi ULA transitori non più rinnovati dopo 30 giorni di inattività, preservando le prestazioni del database SQLite.
