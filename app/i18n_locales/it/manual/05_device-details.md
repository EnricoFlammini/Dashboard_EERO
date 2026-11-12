---
id: device-details
title: 5. Metadati Dispositivo, IP Statici & Port Forwarding
icon: adjustments
summary: Profilo, nomi personalizzati, icone categoria, note locali, riserve DHCP, IPv6 e port forwarding.
---
### Gestione e Configurazione del Singolo Dispositivo

* **Modale Dettaglio Dispositivo:**
  - **Nome e Categoria Personalizzata:** Assegna categorie (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Altro) salvate nel database SQLite locale.
  - **Note & Documentazione Locale:** Campo note libero per salvare credenziali locali, ubicazione o porte di servizio.
  - **Indirizzi IPv6 Dual-Stack & Copia con 1 Clic (v1.5.0 - Issue #43):** Box dedicato nella scheda Generale che elenca tutti gli indirizzi IPv6, con badge cromatici di categoria (*SLAAC / Global* vs *Link-Local*) e pulsante rapido di copia negli appunti con feedback visivo.
  - **Riserva DHCP (IP Statico):** Assegna un indirizzo IP permanente a un dispositivo con verifica automatica dei conflitti e supporto alla riassegnazione.
  - **Port Forwarding Integrato:** Aggiungi e rimuovi regole di apertura porte (Porta Esterna WAN -> Porta Interna LAN, Protocolli TCP/UDP).
  - **Cambio Profilo:** Scegli un altro profilo eero nella scheda Generale; la modifica è immediata con conferma in linea (richiede il permesso *Modifica dispositivi*).
  - **Categoria con Pulsanti Icona:** Clicca un'icona per impostare la categoria; l'icona del dispositivo la segue. **Automatico** ripristina il tipo riportato da eero.
  - **Dettagli di Sola Lettura:** MAC, hostname segnalato, produttore/modello, ultima attività, standard e larghezza Wi-Fi, flag ospite, velocità live e prima comparsa.
