---
id: device-details
title: 5. Metadati Dispositivo, IP Statici & Port Forwarding
icon: adjustments
summary: Personalizzazione nomi, categorie, note locali, riserve DHCP, IPv6 e port forwarding.
---
### Gestione e Configurazione del Singolo Dispositivo

* **Modale Dettaglio Dispositivo:**
  - **Nome e Categoria Personalizzata:** Assegna categorie (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Altro) salvate nel database SQLite locale.
  - **Note & Documentazione Locale:** Campo note libero per salvare credenziali locali, ubicazione o porte di servizio.
  - **Indirizzi IPv6 Dual-Stack & Copia con 1 Clic (v1.5.0 - Issue #43):** Box dedicato nella scheda Generale che elenca tutti gli indirizzi IPv6, con badge cromatici di categoria (*SLAAC / Global* vs *Link-Local*) e pulsante rapido di copia negli appunti con feedback visivo.
  - **Riserva DHCP (IP Statico):** Assegna un indirizzo IP permanente a un dispositivo con verifica automatica dei conflitti e supporto alla riassegnazione.
  - **Port Forwarding Integrato:** Aggiungi e rimuovi regole di apertura porte (Porta Esterna WAN -> Porta Interna LAN, Protocolli TCP/UDP).
  - **Cambio Profilo nel Modale:** Scegli un altro profilo eero (o *Nessun profilo*) nella scheda **Generale**. La modifica è immediata e un messaggio in linea la conferma (o segnala l'errore e ripristina il valore precedente). Richiede il permesso *Modifica dispositivi*.
  - **Categoria come Pulsanti Icona:** Scegli la categoria (Computer, Mobile, Smart Home, Intrattenimento, Gaming, Server/Rete) cliccando la relativa icona; l'icona del dispositivo segue la categoria. L'ultimo pulsante, **Automatico**, ripristina tipo e icona riportati da eero.
  - **Dettagli di Sola Lettura:** Stato, indirizzo MAC, hostname segnalato dal dispositivo (distinto dal nome visualizzato), produttore e modello, ultima attività, standard Wi-Fi e larghezza di canale, flag rete ospiti, velocità live di download/upload con totali e prima comparsa.
