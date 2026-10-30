---
id: device-details
title: 5. Metadati Dispositivo, IP Statici & Port Forwarding
icon: adjustments
summary: Personalizzazione nomi, categorie, note locali, prenotazioni DHCP, IPv6 e port forwarding.
---
### Gestione e Configurazione del Singolo Dispositivo

* **Modale Dettaglio Dispositivo:**
  - **Nome e Categoria Personalizzata:** Assegna categorie (Computer, Mobile, Smart Home, Entertainment, Gaming, Server/NAS, Altro) salvate nel database SQLite locale.
  - **Note & Documentazione Locale:** Campo note libero per salvare credenziali locali, ubicazione o porte di servizio.
  - **Indirizzi IPv6 Dual-Stack & Copia con 1 Clic (v1.5.0 - Issue #43):** Box dedicato nella scheda Generale che elenca tutti gli indirizzi IPv6, con badge cromatici di categoria (*SLAAC / Global* vs *Link-Local*) e pulsante rapido di copia negli appunti con feedback visivo.
  - **Prenotazione DHCP (IP Statico):** Assegna un indirizzo IP permanente a un dispositivo con verifica automatica dei conflitti.
  - **Port Forwarding Integrato:** Aggiungi e rimuovi regole di apertura porte (Porta Esterna WAN -> Porta Interna LAN, Protocolli TCP/UDP).
