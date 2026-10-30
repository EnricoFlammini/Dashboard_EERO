---
id: multi-network
title: 9. Gestione Multi-Rete & Switch a Caldo
icon: globe
summary: Gestione di account eero multi-sede, switch istantaneo in-app e persistenza della rete attiva.
---
### Gestione Multi-Rete (v1.5.0 - Issue #22)

* **Selettore a Tendina Dinamico (Header Fluent):** Se il tuo account eero gestisce più reti mesh (es. Casa principale, Ufficio, Seconda casa), l'intestazione della dashboard mostra un comodo menu a tendina interattivo che indica per ciascuna rete il numero di nodi mesh e di client online.
* **Switch Istantaneo a Caldo:** Selezionando una rete diversa, la dashboard commuta immediatamente senza necessità di riavviare il container o inserire nuove credenziali OTP. La RAM cache viene rigenerata all'istante e i widget si aggiornano in tempo reale.
* **Persistenza dell'Elezione della Rete:** La rete selezionata viene memorizzata in `session.json` e nel database SQLite locale, garantendo che i cicli periodici di polling non ripristino forzatamente la rete predefinita e che la scelta persista anche dopo il riavvio del container Docker.
* **Supporto in Modalità Demo:** Include un simulatore multi-rete a due ambienti indipendenti (*Casa Rossi Mesh 6E* e *Ufficio & Studio Pro Mesh*) per testare e dimostrare le funzionalità anche senza account live.
