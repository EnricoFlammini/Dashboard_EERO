---
id: dashboard-mesh
title: 3. Dashboard & Topologia Mesh
icon: network
summary: Interpretazione dello Health Score, stato dei nodi e controlli rapidi.
---
### Comprensione della Dashboard Generale

* **Punteggio di Salute della Rete (1-100):** Un indicatore sintetico dello stato di salute della rete, calcolato analizzando la disponibilità dei nodi mesh, la presenza del gateway e la qualità del segnale RSSI dei client.
* **Schede di Riepilogo:**
  - *Stato WAN:* IP pubblico, provider, IPv6, barra del punteggio di salute e ultimo aggiornamento. Clic per aprire i dettagli Salute Rete.
  - *Gateway Principale:* Modello, IP LAN, subnet, DNS, firmware e numero di nodi mesh online.
  - *Client Connessi:* Totale con ripartizione 6 / 5 / 2.4 GHz e cablati, dispositivi noti, ospiti e nuovi. Clic per aprire Dispositivi filtrati sui client connessi.
  - *Ultimo Speed Test:* Download/upload, ping, voto bufferbloat, andamento recente del download e medie complessive. Clic per aprire la pagina Speed Test.
* **Topologia Nodi eero:**
  - *Gateway Node:* Il nodo principale connesso direttamente al modem/ONT dell'operatore.
  - *Beacon / Mesh Extender:* Nodi secondari che estendono la copertura.
  - *Client Connessi:* Clic sul conteggio client di un nodo per aprire Dispositivi filtrati su quel nodo.
  - *Tipo di Backhaul:* Visualizza se il collegamento tra i nodi avviene via cavo Ethernet (1 Gbps o 2.5 Gbps) oppure tramite canale Wireless dedicato (5 GHz / 6 GHz).
* **Azioni Rapide sui Nodi:**
  - **Riavvio Rete:** Invia un comando di riavvio controllato a tutta l'infrastruttura.
  - **Riavvio Singolo Nodo:** Riavvia unicamente il nodo selezionato senza interrompere il resto della casa.
* **Funzionalità Mesh Avanzate (v1.7.0):**
  - **Estensori Amazon Echo "eero Built-in" (Issue #96):** Rilevamento automatico e sintesi dei dispositivi Amazon Echo compatibili che estendono la copertura mesh Wi-Fi. Sono evidenziati con il badge dedicato **`eero Built-in`**, conteggio dei client associati e blocco di sicurezza del pulsante di riavvio non supportato.
  - **Elezione Gateway Primario in Bridge Mode (Issue #105):** In modalità Bridge (dove tutti i nodi riportano `gateway: false`), la suite riconosce deterministicamente il vero router primario verificando il flag `is_primary_node` e i neighbor LLDP non-eero della porta WAN, evitando selezioni arbitrarie.
  - **Immagini Ufficiali Hardware eero:** Ogni nodo mesh è accompagnato dalla foto ufficiale del modello hardware specifico (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot, ecc.) per un immediato riconoscimento visivo.
  - **Assistente AI Streaming & Placement Test (Issues #90, #102):** Diagnostica interattiva mesh in streaming SSE (`/api/network/assistant`), verifica del posizionamento RF nodi (`Placement Test`), stato Guardian VPN e aggiunta nodi tramite codice seriale.
