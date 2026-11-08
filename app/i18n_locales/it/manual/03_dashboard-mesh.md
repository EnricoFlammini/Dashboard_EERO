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
