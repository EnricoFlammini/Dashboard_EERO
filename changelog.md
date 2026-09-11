# Changelog - eero Custom Dashboard & Management Suite

Tutte le modifiche rilevanti, i miglioramenti e le correzioni di bug apportate al progetto sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) e aderisce al versionamento semantico.

## [1.4.0] - 2026-08-29

### 🔧 Normalizzazione Prenotazioni DHCP & Regole Port Forwarding su Eero Cloud
* **🔧 Risoluzione Visualizzazione Port Forwarding per Dispositivo:**
  * Risolto il disallineamento nei nomi di campo restituiti dall'API eero Cloud (`gateway_port`, `client_port`, `internal_ip`, associazione a `reservation`), garantendo il mapping bidirezionale con i campi dell'interfaccia (`port_from`, `port_to`, `ip`, `description`).
  * Ottimizzato il matching delle regole di inoltro porte nella scheda del dispositivo (`/api/devices/{mac}/rules`) verificando sia l'IP attivo che l'IP riservato e il puntatore URL della prenotazione DHCP.
* **📋 Normalizzazione Estrazione Prenotazioni DHCP ("Other Active Reservations"):**
  * Risolto il bug per cui le prenotazioni DHCP attive non venivano elencate nella sezione "Altre prenotazioni attive" nel modale dettagli dispositivo a causa di payload eterogenei o incapsulati in dizionario (`{"reservations": [...]}` o dizionari indicizzati per ID) restituiti dal cloud eero.
  * Introdotta la funzione `_extract_raw_list` e `_normalize_reservation` in `EeroClient` con gestione difensiva di `ip`/`ip_address` e `mac`/`mac_address`, prevenendo eccezioni HTTP 500 e allineando l'interfaccia sia per IP statico riservato che per la rilevazione dei conflitti.

### ⚡ Ottimizzazione Connection Pooling & In-Memory DNS Caching (Issue #24)
* **⚡ Risoluzione Query DNS Eccessive verso `api-user.e2ro.com`:**
  * Risolta la segnalazione [Issue #24](https://github.com/EnricoFlammini/Dashboard_EERO/issues/24) relativa all'elevato numero di richieste DNS generate dal container (oltre 160.000 query in 30 giorni) registrate nei server DNS di rete (AdGuard Home / Pi-hole).
  * **Persistent HTTP Connection Pooling & Keep-Alive:** `EeroClient` ora mantiene un'istanza condivisa di `httpx.AsyncClient` riutilizzando le connessioni TCP/TLS con keep-alive a 120s. Finché la connessione è attiva nel pool, le richieste API avvengono senza generare alcuna query DNS.
  * **In-Memory DNS TTL Cache (`dns_cache.py`):** implementato un resolver cache thread-safe in memoria con TTL di 300 secondi (5 minuti) attorno a `socket.getaddrinfo`. In caso di riconnessione o timeout, l'IP di `api-user.e2ro.com` viene fornito istantaneamente dalla RAM a 0ms, abbattendo oltre il 99.9% delle query DNS verso l'upstream.
  * **Zero Impatto sulla Frequenza Dati:** la frequenza di aggiornamento della telemetria e dei dispositivi in tempo reale rimane invariata, con una latenza per ciclo del poller ridotta da ~1.5s a ~250ms grazie al riutilizzo della sessione crittografica TLS.

### 🛡️ Opzione Drop IPv6 per Sincronizzazione AdGuard Home (Issue #23)
* **Flag CLI `--drop-ipv6` / `--no-ipv6` e Variabile d'Ambiente `EERO_DROP_IPV6`:**
  * Risolta la richiesta [Issue #23](https://github.com/EnricoFlammini/Dashboard_EERO/issues/23) consentendo di escludere gli indirizzi IPv6 temporanei/rotanti (SLAAC / Privacy Extensions RFC 4941) che possono creare anomalie, conflitti o record duplicati nei log di AdGuard Home.
  * **Epurazione Retroattiva su AdGuard Home:** eseguendo `adguard_sync.py --drop-ipv6`, gli indirizzi IPv6 precedentemente registrati nei client AdGuard vengono automaticamente rimossi dagli identificatori `ids` preservando tutte le regole personalizzate, upstream e filtri.
  * **Parametro Query API:** aggiunto `include_ipv6: bool = Query(True)` all'endpoint REST `GET /api/devices/export/adguard` per permettere l'esportazione selettiva (`?include_ipv6=false`).

### ❤️ Network Health Score Breakdown & Modale Diagnostico Interattivo (Issue #15)
* **❤️ Finestra Modale Diagnostica Interattiva a 4 Pilastri:**
  * Risolta la richiesta [Issue #15](https://github.com/EnricoFlammini/Dashboard_EERO/issues/15) rendendo il badge circolare dello **Health Score** nell'header completamente cliccabile e interattivo in Windows 11 Fluent Design.
  * Accessibilità ottimizzata anche per smartphone e schermi compatti grazie all'access point integrato nella card WAN della tab Overview.
  * Suddivisione analitica dello stato di salute su 4 Pilastri Fondamentali (Totale 100 pt):
    1. 🌐 **Topologia Mesh & Nodi (Max 40 pt):** Monitoraggio nodi mesh online/offline e integrità backhaul (1Gbps/cablato vs wireless mesh degradato).
    2. ⚡ **Gateway WAN & Internet (Max 30 pt):** Raggiungibilità uplink provider, stato gateway e controllo latenza ping.
    3. 📶 **Qualità Segnale Wi-Fi Client (Max 20 pt):** Identificazione precisa dei client con segnale RSSI degradato (< -75 dBm / < -82 dBm) e relative penalità.
    4. 📡 **Distribuzione Canali & Frequenze (Max 10 pt):** Bilanciamento frequenze (6 GHz, 5 GHz, 2.4 GHz) e prevenzione affollamento canali/nodi.
  * **Analisi Puntuale delle Penalità (Active Factors):** Visualizzazione chiara dei fattori attivi che riducono il punteggio con badge d'impatto numerico (es. `-2 pt`, `-20 pt`) ed elenco dei nodi o client coinvolti.
  * **Raccomandazioni Intelligenti Contestuali:** Consigli pratici personalizzati generati dinamicamente per ottimizzare la copertura e le prestazioni della rete.
  * **Nuovo Endpoint REST:** Esposto `GET /api/network/health-breakdown` e arricchita la risposta cache zero-latency `GET /api/network/overview` con il payload `health_details`.
  * **Localizzazione Bilingue Completa (i18n):** Supporto bilingue integrato (IT/EN) nativo per tutti i 4 pilastri, penalità calcolate e raccomandazioni intelligenti con cambio lingua istantaneo.

### 🎨 Windows 11 Fluent Design & Dual Theme Engine (Dark & Light Mode)
* **🎨 Restyling Completo Windows 11 Fluent Design:**
  * Implementato il design system di Windows 11 con Segoe UI Variable font stack, Mica/Acrylic material effects, bordi sottili multistrato (`rgba(0,0,0,0.08)` / `rgba(255,255,255,0.08)`) e ombre morbide stratificate.
  * Palette cromatica calibrata per la massima leggibilità e contrasto in entrambe le modalità:
    * **Tema Chiaro (Light Mode):** Sfondo canvas `#f3f3f3`, pannelli in vetro acrilico bianco opaco (`rgba(255, 255, 255, 0.82)`), testi ad alto contrasto (`#1c1c1c`) e accento blu Fluent `#0067c0`.
    * **Tema Scuro (Dark Mode):** Sfondo canvas `#202020`, card `#2b2b2b`, testi `#ffffff` e accento azzurro Fluent `#60cdff`.
* **☀️ Selettore a 3 Stati & Zero FOUC:**
  * Toggle ergonomico posizionato nell'header con 3 modalità: ☀️ Chiaro, 🌙 Scuro, 💻 Sistema (Auto).
  * Script headless inline anti-flicker e sincronizzazione istantanea in `localStorage` e con le preferenze del sistema operativo (`prefers-color-scheme`).
  * Palette adattiva dinamica per tutti i grafici Chart.js (WAN, Top Hogs, Speedtest, Segnale RSSI) con aggiornamento in tempo reale senza ricaricare la pagina.

### 🛡️ Multi-Engine DNS Synchronizer Suite (AdGuard, Pi-hole & Technitium)
* **🛡️ Sincronizzazione Multi-Engine e Multi-Istanza Simultanea:**
  * Architettura modulare unificata in `DNSManager` (`app/services/dns_manager.py`) capace di gestire $N$ istanze contemporanee eterogenee (es. **2 istanze AdGuard Home + 1 Pi-hole** o Technitium).
  * **Supporto Pi-hole (v5 & v6 REST API):** Sincronizzazione automatica dei record DNS locali (`/api/config/dns/hosts` e `/admin/api.php?customdns`) con associazione istantanea IP-hostname.
  * **Supporto Technitium DNS Server:** Allineamento record diretti A/AAAA nella zona locale e generazione automatica dei record PTR nelle zone inverse `in-addr.arpa` per Reverse DNS lookup.
  * **Test Connettività & Sincronizzazione Flessibile:** Pulsanti per il test della singola istanza o di tutte le istanze simultaneamente, con sincronizzazione massiva globale o mirata.
  * **Isolamento Completo Demo Mode:** Esecuzione completamente sicura e simulata in Demo Mode con zero chiamate di rete esterne.
  * **Piena Retrocompatibilità:** Preservazione trasparente di tutti gli endpoint preesistenti `/api/automations/adguard*` e delle strutture dati.

### 🔄 1-Click Docker Auto-Update & Version Checker
* **🔄 Motore di Auto-Update Docker in-App:**
  * Controllo automatico periodico e manuale di nuove release su Docker Hub (`/v2/repositories/enricoflammini/eero-dashboard/tags`) e GitHub Releases (`/releases/latest`).
  * Badge animato di notifica nell'header per aggiornamenti disponibili.
  * Modale interattivo con visualizzazione changelog e supporto a 3 modalità di installazione:
    1. **Docker Socket (`/var/run/docker.sock`)**: Pull dell'immagine `latest` e ricreazione del container automatica in 1 clic.
    2. **Watchtower Webhook**: Invio del trigger di aggiornamento all'istanza Watchtower configurata.
    3. **Modalità Assistita / CLI**: Visualizzazione e copia a un clic del comando `docker compose pull && docker compose up -d`.
  * Overlay con barra di avanzamento del download e polling di riconnessione automatica (`/api/health`) al riavvio del container.

### 📱 QR Code Wi-Fi Ospiti Dual-Theme & UI Contrast Refinements
* **📱 QR Code Wi-Fi Dinamico Dual-Theme:**
  * Supporto per rendering dinamico con sfondo bianco puro `(255, 255, 255)` e moduli blu Windows 11 Fluent `(0, 103, 192)` in Light Mode, per una scansione nitida e istantanea con qualsiasi fotocamera smartphone.
  * Mantenuto lo sfondo scuro ardesia `(15, 23, 42)` con moduli azzurro cielo `(56, 189, 248)` in Dark Mode.
  * Switch automatico reattivo (Alpine.js) ad ogni variazione del selettore del tema (Chiaro / Scuro / Sistema).
  * Contenitore visivo del QR in `index.html` allineato con sfondo bianco e bordi coordinati senza riquadri grigi residui.
* **🎨 Ottimizzazione Contrasto e Leggibilità Light Mode:**
  * Calibrazione ad alto contrasto di tutti i badge della tabella Dispositivi:
    * **Profilo Utente:** `text-sky-950` su `bg-sky-100` con bordo `border-sky-400`.
    * **STATICO:** `text-emerald-950` su `bg-emerald-100` con bordo `border-emerald-400` e indicatore verde scuro.
    * **DHCP:** `text-slate-900` su `bg-slate-200` con bordo `border-slate-400`.
    * **Bande Wi-Fi:** Badge ad alto contrasto per 5 GHz (`indigo-950`/`indigo-100`), 2.4 GHz (`amber-950`/`amber-100`), 6 GHz (`cyan-950`/`cyan-100`) ed Ethernet (`emerald-950`/`emerald-100`).
    * **Stato Online/Offline:** Verde e grigio ad alta visibilità.
  * Riquadro informativo di conferma prenotazione IP nel modale del Dispositivo ottimizzato con `bg-emerald-100` e testo in grassetto `text-emerald-950`.
  * Header superiore, badge versione e modale About affinati con contrasto ottimale.
* **🛠️ Ripristino Griglia Automazioni & Pulizia Toolbar DNS:**
  * Risolto il layout della pagina *Controlli & QR Ospiti*, ripristinando la corretta griglia responsive a due colonne affiancate.
  * Rimozione di icone duplicate ed emoji statiche dai pulsanti Multi-Engine DNS (`Aggiungi Istanza DNS`, `Testa Tutti`, `Sincronizza Tutti`) e dai pulsanti delle singole istanze (`Test`, `Sync`).
  * Rimosso il pulsante duplicato di aggiunta istanza nel contenitore vuoto.

### 📐 Navigazione a Barra Laterale Collassabile (Sidebar UX) & Controlli Rapidi
* **📐 Menu Laterale Verticale Collassabile (Windows 11 Fluent Design):**
  * Riorganizzazione dell'architettura di navigazione dell'applicazione con passaggio dalla barra a schede orizzontale superiore ad una barra laterale verticale a scomparsa posizionata sulla sinistra (`#sidebarNav`).
  * Supporto a due modalità operative: espanso (`256px` / `w-64`) con etichette descrittive complete ed etichette tasti, e compresso/collassato (`68px` / `w-[68px]`) in modalità compatta ad icone con tooltip nativi informativi al passaggio del mouse (`title`).
  * Layout del contenuto principale dinamico e responsive con transizioni animate fluide (`transition-all duration-300`) che adatta il margine sinistro in base allo stato del menu (`ml-64` espanso, `ml-[68px]` compresso, `ml-0` su dispositivi mobili).
  * Memorizzazione automatica e trasparente dello stato di apertura o chiusura in `localStorage` (`eero_sidebar_collapsed`), preservando l'assetto desiderato dell'utente tra ricaricamenti della pagina e sessioni successive.
* **🎯 Centratura Geometrica delle Icone & Doppio Toggle:**
  * Centratura rigorosa orizzontale e verticale di tutti i pulsanti e delle rispettive icone SVG in modalità collassata (`44x44px` / `w-11 h-11 justify-center mx-auto`), risolvendo ogni disallineamento visivo.
  * Posizionamento intelligente del badge numerico dei dispositivi connessi: in modalità collassata si ancora come micro-pillola ad alto contrasto nell'angolo in alto a destra dell'icona (`top-1 right-1`).
  * Pulsante dedicato per l'espansione e compressione nel footer della barra (`#btnToggleSidebarNav`) con freccia dinamica (`<<` / `>>`) ed etichetta testuale contestuale.
  * Integrazione e sincronizzazione reattiva con il pulsante hamburger (`#btnToggleSidebarNavHeader`) posizionato nell'header superiore dell'interfaccia.
* **🎮 Riposizionamento Controlli Rapidi & Indicatore Visivo Demo Mode ad Alta Visibilità:**
  * Spostamento delle scorciatoie operative rapide **Gaming Focus Mode** (`#btnGamingMode`) e **Demo Mode** (`#btnDemoMode`) nella sezione inferiore della sidebar (`#sidebarControls`), rendendole sempre accessibili indipendentemente dalla pagina visualizzata.
  * Nuova identità cromatica ad alto contrasto per lo stato della **Modalità Demo**:
    * **Demo Attiva:** Il pulsante assume una colorazione verde smeraldo brillante (`bg-emerald-500/20 text-emerald-300 border-emerald-500/40`), animazione a punto pulsante luminoso (`animate-ping`) e dicitura esplicita *"DEMO ATTIVA"*, eliminando ogni dubbio sullo stato di simulazione.
    * **Rete Live (Disattivata):** Stile neutro e discreto (`bg-slate-800/40 text-slate-400 border-slate-700/40`) con etichetta *"LIVE / NORMALE"*.
  * Sincronizzazione dinamica con la pillola di stato interattiva nell'header (`#headerDemoPill`) che visualizza *"✨ DEMO"* in verde smeraldo con indicatore cliccabile per tornare istantaneamente alla rete live.

---

## [1.03.03] - 2026-08-31

### 🌐 Fix Risoluzione Primary Gateway Mesh in Bridge & Routed Mode (#19)
* **🌐 Risoluzione Accurata del Nodo Gateway Principale (Issue #19):**
  * Risolto il bug di casting booleano indiscriminato in cui i campi stringa URL/ID (es. `"/2.2/eeros/104"`) restituiti dall'API eero come puntatore al nodo root venivano valutati come `True` per tutti i beacon/nodi foglia della rete, forzando tutti i nodi su `Gateway (WAN)` ed eleggendo erroneamente il primo nodo alfabetico (es. *Bedroom* al posto di *Wiring Closet*).
  * Introdotto il metodo `_is_gateway_node` in `eero_client.py` per confrontare le chiavi URL, ID, serial e IP locali con il puntatore gateway effettivo, supportando in modo trasparente reti in **Bridge Mode** (con router/DHCP esterno come Peplink, pfSense o modem operatore) e reti standard in **Routed Mode**.
  * Implementato algoritmo di riconciliazione univoca in `get_eeros` per garantire l'elezione di un singolo Primary Gateway certificato anche in caso di ambiguità nei payload cloud.

### 🛡️ Preservazione Regole AdGuard Home & Distinzione Tag Desktop/Laptop (#21)
* **🛡️ Preservazione Integrale Regole e Filtri Client su AdGuard Home (Issue #21):**
  * Risolto il bug di sincronizzazione per cui le chiamate `POST /control/clients/update` verso AdGuard Home azzeravano i parametri custom impostati dall'utente.
  * Implementato il metodo `_merge_adguard_client_data` per ereditare e mantenere al 100% tutte le regole attive: server DNS personalizzati (`upstreams`), servizi bloccati (`blocked_services`), pianificazioni (`blocked_services_schedule`), `parental_enabled`, `safebrowsing_enabled`, `safesearch_enabled`, `use_global_settings`, filtri querylog e tag personalizzati.
  * Unito l'elenco degli identificatori (`ids`) preservando eventuali IP, alias o MAC aggiunti manualmente in AdGuard senza sovrascriverli.
* **🖥️ Distinzione Accurata Tag Desktop / PC vs Laptop (`device_pc` / `device_laptop`):**
  * Perfezionato `map_eero_device_type` e `get_adguard_tags` per distinguere i PC fissi/workstation/tower (assegnando icona `pc` e tag `device_pc`) dai portatili (assegnando icona `laptop` e tag `device_laptop`).

---

## [1.03.02] - 2026-08-30

### ⚡ Fix Formattazione Velocità Backhaul & Rilevamento Frequenze Wi-Fi 6 GHz (#14)
* **⚡ Fix Formattazione Velocità Backhaul 2.5 Gbps:**
  * Risolto il bug di parsing stringa in frontend (`formatBackhaul`) in cui il controllo generico `.includes('5 Gbps')` intercettava la parte terminale di `2.5 Gbps` restituendo erroneamente `Ethernet (5.0 Gbps)`. Sostituito con regex strict con boundary di parola (`/\b2\.5\s*Gbps\b/i`).
* **📶 Supporto e Rilevamento Dinamico Frequenze Wi-Fi 6E & Wi-Fi 7 a 6 GHz:**
  * Esteso il parser `_normalize_device` per interpretare i valori di frequenza numerica espressi in MHz (`5900 MHz - 7200 MHz`), mappando correttamente i dispositivi Wi-Fi 6E/7 (es. iPhone 17 a 6295 MHz e PC Wi-Fi 7 EHT su canale 69 con ampiezza 320 MHz) su **`6 GHz`** / **`6GHz`**.
  * Aggiornato il frontend con classi CSS esclusive e indipendenti (`bg-sky-500/20 text-sky-400`) per evidenziare i dispositivi a 6 GHz ed evitare sovrapposizioni visive con la banda a 5 GHz.
* **🔄 Cache-Busting Automatico Asset Statici (#17):**
  * Aggiunto parametro di versione `?v={{ app_version }}` agli asset CSS e JS in `index.html` per garantire l'aggiornamento automatico della cache del browser ad ogni rilascio.

---

## [1.03.01] - 2026-08-29

### ⚡ Fix Negoziazione Porte Ethernet Nodi Mesh & Telemetria Dispositivi (#14)
* **⚡ Priorità Porta WAN/Upstream su Nodi Mesh Multi-Porta (Issue #14):**
  * Risolto il caso di nodi con più porte attive (es. Bedroom con uplink 2.5 Gbps verso Living Room e porta LAN 1 Gbps): il sistema ora identifica e prioritizza la porta WAN (`isWanPort`, `is_wan_port` o con `neighbour`) rispetto alle porte LAN client locali.
  * Risolto il bug di parsing in cui stringhe di frequenza Wi-Fi (es. `"5GHz"`) venivano scambiate per link Ethernet a 5.0 Gbps (5000 Mbps).
* **🖥️ Parsing Velocità Ethernet Dispositivi Client (`connectivity.ethernet_status`):**
  * Introdotta l'estrazione e decodifica dei codici di velocità `speed` (es. `P2500` ➔ 2.5 Gbps, `P1000` ➔ 1.0 Gbps) direttamente dall'oggetto `connectivity.ethernet_status` dei dispositivi client, consentendo alla UI di mostrare correttamente `2.5 Gbps • Ethernet`.
* **📶 Telemetria RSSI dBm su Nodi Mesh Wireless:**
  * Supportata l'estrazione di valori di segnale anche quando strutturati come dizionari (`signal.rx_rssi`, `signal_dbm`, `mesh_quality`), garantendo la corretta visualizzazione del badge (es. `Wireless Mesh (5 GHz / -58 dBm)`).

### 🏷️ Mapping Automatico Categorie Dispositivi, Tag AdGuard Home & Metadati (#13)
* **🏷️ Categorizzazione Nativa eero Intelligente (Issue #13):**
  * Implementata la funzione `map_eero_device_type` per interpretare automaticamente il campo nativo `device_type` del cloud eero (`laptop`, `phone`, `tv`, `gaming_console`, `camera`, `nas`, `smart_plug`, `printer`, `speaker`) assegnando categoria e icona corrette senza forzare tutto su `"Altro"`.
  * Gerarchia di fallback corretta: Priorità alle personalizzazioni utente salvate nel DB locale SQLite > Categoria/Icona nativa eero > Fallback `"Altro"`.
* **🛡️ Mappatura Tag Ufficiali AdGuard Home:**
  * Integrata la conversione delle categorie e icone nei tag client standard di AdGuard Home (`device_laptop`, `device_pc`, `device_phone`, `device_tablet`, `device_tv`, `device_gameconsole`, `device_nas`, `device_other`) nell'endpoint di esportazione `/api/devices/export/adguard` e nel motore di sincronizzazione automatica.
* **🔧 Risoluzione Robusta Salvataggio Metadati & JSON Error Handling:**
  * Aggiornati gli endpoint `/api/devices/{device_id_or_mac}/metadata` per consentire la ricerca per MAC address, ID eero univoco, URL o indirizzo IP.
  * Inserito controllo preventivo `res.ok` e safe JSON parsing in `app.js` per eliminare l'errore `json parse unexpected character line 1 column 1` in caso di risposte HTTP non riuscite.

### 🛡️ Supporto a Istanze Multiple AdGuard Home & Cache-Busting Asset (#17)
* **🛡️ Sincronizzazione DNS Multi-Server (Issue #17):**
  * Introdotto il supporto per la configurazione e sincronizzazione verso **molteplici istanze target AdGuard Home** (es. DNS Primario, Secondario o failover).
  * Nuova interfaccia grafica nella card AdGuard con gestione dinamica delle istanze (aggiunta `+`, rimozione, toggle abilitazione individuale, stato e ora dell'ultimo sync per ciascuna istanza).
  * Endpoint di test e sync aggiornati per verificare e riconciliare tutti i server contemporaneamente in modo parallelo/sequenziale.
* **🔄 Cache-Busting Automatico & Nota Aggiornamento Browser (Issue #17):**
  * Aggiunto parametro di versione `?v={{ app_version }}` ai link degli asset CSS e JavaScript in `index.html` per forzare l'aggiornamento automatico della cache del browser ad ogni rilascio.
  * Documentato nel file `README.md` (sia in inglese che in italiano) il comportamento della cache del browser e le istruzioni per l'hard reload (`Ctrl + F5` / `Cmd + Shift + R`) all'aggiornamento del container.

### 👥 Supporto Utenti Amministratori Invitati e Reti Condivise (Amazon Workaround)
* **🔑 Risoluzione Flessibile Topologia per Account Multi-Rete e Admin Invitati:**
  * Potenziato il metodo `fetch_account_info` in `eero_client.py` per identificare e mappare le reti mesh non solo da `account.networks`, ma anche dalle strutture `shared_networks`, `guest_networks`, `admin_networks` e tramite fallback automatico sull'endpoint `/2.2/networks`.
  * Garantito il pieno supporto agli utenti con account proprietario Amazon SSO che invitano un account amministratore secondario dall'app mobile eero per accedere alla Dashboard con 2FA OTP.

---

## [1.03.00] - 2026-08-28

### 📦 Docker Hub Multi-Arch, Sincronizzazione AdGuard Home & Ottimizzazioni Mesh (#12)
* **📡 Risoluzione Universale Nodi e Client Mesh (Issue #12):**
  * Introdotto motore di indicizzazione multi-chiave in `poller.py` e `eero_client.py` (`id` numerico, `serial`, `url`, `location`/nome, `ip`) per garantire il matching affidabile dei client connessi su tutte le generazioni eero (eero Pro 7, Pro 6E, eero 6+, Max 7) e versioni eeroOS 7.x.
  * Risolto il bug per cui i dispositivi su nodi beacon potevano risultare tutti associati al Gateway in presenza di payload cloud privi del campo `location`.
* **✨ Switch Istantaneo Modalità Demo / Rete Live (senza perdita di Token):**
  * Aggiunto pulsante interattivo nella barra superiore per passare istantaneamente alla **Modalità Demo** a scopo di test/anteprima e ritornare alla **Rete Live** preservando sempre il token di sessione autenticato senza dover reinserire l'OTP.
* **🛡️ Isolamento e Dati Fittizi per AdGuard e Telegram in Ambiente Demo:**
  * Configurate credenziali e dati fittizi completi (URL `http://192.168.1.50:80`, utente `demo_admin`, token Telegram e webhook demo) per l'ambiente Demo.
  * Inibito l'invio di chiamate di rete reali e notifiche verso server AdGuard o canali Telegram quando la modalità Demo è attiva, prevenendo la trasmissione accidentale di dati simulati.
* **🌡️ Armonizzazione Stato Termico Nodi:**
  * Ottimizzato il rendering dello stato termico e operativo dei nodi mesh, riflettendo accuratamente lo stato di salute reale fornito dalle API ufficiali eero (`thermal_status`: Normale / Nominale).
* **⚡ Velocità Negoziata Ethernet Dispositivi & Backhaul Mesh:**
  * Rimosso il testo fisso `'GbE 1.0 Gbps'`. Ora il sistema rileva e mostra dinamicamente la reale velocità di link per apparati cablati a **10 Gbps**, **5.0 Gbps**, **2.5 Gbps**, **1.0 Gbps** e **100 Mbps**.
  * Ispezione automatica delle porte ethernet fisiche (`ports`/`ethernet_ports`) dei nodi eero per rilevare e mostrare la velocità di backhaul cablato.
* **👤 Sincronizzazione Profilo Famiglia / Utente Cloud eero:**
  * Visualizzazione e filtro in tempo reale dell'assegnazione profilo utente eero sia nella tabella principale che nel modale dettaglio client.
* **📶 Telemetria Segnale RSSI (dBm) & PHY Link Rate nel Modale:**
  * Integrata la visualizzazione avanzata della qualità del segnale in dBm e della velocità di modulazione PHY nel riquadro di connessione del modale.
* **🌍 Rimozione Residui di Testo e Localizzazione Completa:**
  * Localizzati integralmente in inglese e italiano tutti i messaggi di verifica conflitti IP statici, avvisi e notifiche Toast.
* **Distribuzione Ufficiale Docker Hub Multi-Arch:**
  * Configurato workflow GitHub Actions per la compilazione e il push automatico su Docker Hub (`enricoflammini/eero-dashboard`).
  * Supporto nativo alle architetture `linux/amd64` (Server x86, PC, VM) e `linux/arm64` (Raspberry Pi 4/5, NAS Synology/QNAP/TrueNAS, Apple Silicon).
  * Avvio immediato a riga di comando senza compilazione locale tramite `docker run` o `docker compose pull`.
* **Integrazione Nativa AdGuard Home in-App:**
  * Nuova scheda visuale dedicata nel tab **Automazioni & Controlli** per configurare la connessione verso AdGuard Home (URL, Username, Password).
  * Normalizzazione automatica degli URL locali (pulizia frammenti `#`, supporto HTTP e fallback SSL/TLS per certificati self-signed).
  * Pulsante **"Test Connessione"** con riscontro immediato via Toast e verifica delle credenziali.
  * Pulsante **"Sincronizza Ora Tutti i Client"** con matching intelligente per nome, MAC e IP (`/control/clients/add` e `/control/clients/update`).
  * Toggle **"Abilita sincronizzazione automatica continua"** per sincronizzare silenziosamente in background all'accesso di nuovi dispositivi e su base periodica.
* **🔒 Pulsante Disconnessione con Modale di Sicurezza:**
  * Ripristinato il pulsante di logout nella barra superiore accanto alla guida rapida.
  * Introdotto un modale di conferma Glassmorphism con avviso esplicito sulla necessità di richiedere un nuovo codice 2FA OTP al successivo accesso.
* **📊 Fix & Arricchimento Daily Digest Telegram:**
  * Risolto l'errore di generazione del report giornaliero delle 21:00 (e manuale da interfaccia) causato da riferimenti a tabelle storiche obsolete.
  * Il report inviato su Telegram e via Webhook include ora dati reali certificati: Health Score, ISP, nodi mesh online, client attivi totali, suddivisione dettagliata per frequenza (6GHz, 5GHz, 2.4GHz, Cablati), Speed Test Gateway e Latenza Ping.
  * Introdotto un toggle esplicito *"Abilita invio automatico programmato (ore 21:00)"* per consentire all'utente di disattivare la schedulazione del digest mantenendo disponibile l'invio istantaneo on-demand.
* **🎛️ Riorganizzazione Scheda Automazioni & Toggle Notifiche Telegram:**
  * Layout del tab **Controlli & QR Ospiti** riorganizzato a matrice 2x2: *Guest Wi-Fi* (alto-sx), *Integrazione AdGuard Home* (alto-dx), *Notifiche Telegram & Webhook* (basso-sx) e *Report Digest Giornaliero* (basso-dx).
  * Introdotto un toggle esplicito *"Abilita invio notifiche su Telegram"* per attivare/disattivare rapidamente gli avvisi automatici senza cancellare token o chat ID salvati.
* **🛡️ Registro Persistente Dispositivi Noti (Zero Notifiche Duplicate al Riavvio):**
  * Creata la tabella SQLite `known_devices` per memorizzare in modo permanente gli indirizzi MAC e lo stato di notifica dei client di rete.
  * Al riavvio o all'aggiornamento del server/container, il poller carica l'elenco completo dal database, evitando l'invio ripetuto di notifiche Telegram per apparati già noti.
* **📖 Rendering Ottimizzato del Manuale Utente & Changelog In-App Bilingue:**
  * Riscritto il parser Markdown interno (`renderSimpleMarkdown`) con supporto completo a liste numerate ordinate (`<ol>`), sottoelenchi puntati indentati (`<ul>`), collegamenti ipertestuali e formattazione dei paragrafi.
  * Il visualizzatore del Changelog interno all'app è ora bilingue (Italiano e Inglese) e presenta un sommario essenziale dei soli titoli principali delle release, con link diretto per consultare il registro completo su GitHub.
* **❤️ Modale About, Dedica & Informazioni Open Source:**
  * Aggiunto pulsante dedicato *"About"* nella barra superiore accanto al badge di versione.
  * Include dedica alla community homelab & self-hosted (*Crafted with ❤️ by Enrico Flammini*), collegamenti rapidi a repository GitHub (codice e issues), licenza MIT, immagine Docker Hub e sezione Fun Notes.
* **🔀 Ordinamento Dispositivi & Barra dei Titoli Bloccata (Sticky Header):**
  * Introdotta la possibilità di ordinare la tabella dei dispositivi cliccando direttamente su ciascuna intestazione di colonna (Dispositivo/Host, Indirizzo IP numerico IPv4, Profilo, Nodo Mesh, Banda, Segnale RSSI e Stato).
  * La barra dei titoli della tabella rimane ora bloccata in alto (`sticky`) durante lo scorrimento, garantendo visibilità e orientamento costante anche con centinaia di client connessi.
* **⚙️ Normalizzazione Dinamica Dispositivi & Gestione Flessibile Nodi/Sensori:**
  * Risolto il bug di parsing dei dispositivi che poteva impedire la visualizzazione dei client connessi con determinati payload eero Cloud.
  * Reso pienamente dinamico il rendering dei client e dei conteggi (1, 2, N client o stato vuoto dedicato) con fallback automatico tra endpoint `/devices` e dettagli di rete.
  * I campi e i sensori hardware (es. backhaul su gateway standalone, temperature o firmware) vengono ora mostrati solo se effettivamente disponibili sulla versione hardware in uso.
  * Revisionate e completate al 100% tutte le etichette, placeholder e notifiche Toast in lingua inglese e italiana.
* **Esportazione DNS & Webhooks:**
  * Endpoint `GET /api/devices/export/hosts` (standard `/etc/hosts` / `dnsmasq`) e `GET /api/devices/export/adguard` (JSON provisioning).
  * Script standalone CLI [`scripts/adguard_sync.py`](scripts/adguard_sync.py).
  * Specifiche formali e schemi JSON dei payload Webhook nel `README.md`.

---

## [1.02.00] - 2026-08-26

### 📡 Telemetria Frequenze Wi-Fi (2.4/5/6GHz) & Integrazione Utenti Cloud eero
* **Badge Frequenze di Banda & Canale Wi-Fi:** Visualizzazione esplicita della frequenza per ciascun dispositivo nella tabella principale (**6 GHz**, **5 GHz**, **2.4 GHz**, **Cablato Ethernet**) con badge colorati distintivi (Sky Blue `6 GHz`, Indigo `5 GHz`, Amber `2.4 GHz`, Emerald `Ethernet`) ed etichetta canale wireless (`CH 11`, `CH 36`, ecc.).
* **Integrazione Utente / Profilo Cloud eero nei Dispositivi:** Ciascun client mostra la colonna *Profilo / Utente* con badge `👤 [Nome Profilo]`, sincronizzata in tempo reale con i profili configurati nell'App eero ufficiale.
* **Filtri Multi-Criterio Avanzati:**
  * Filtro rapido a tendina per frequenza di banda (*Tutte le Frequenze, 6 GHz, 5 GHz, 2.4 GHz, Cablato*).
  * Filtro per profilo utente (*Tutti i Profili / Non Assegnati / Profilo Specifico*).
  * Filtro per nodo mesh di attestazione (*Gateway / Beacon*).
  * Filtro per tipo di indirizzo IP (*Tutti gli Assegnamenti / Solo IP Statici / Solo IP DHCP*).
* **Ottimizzazione Modale Dettaglio Dispositivo:** Interfaccia snella e focalizzata sulla modifica di Nome Personalizzato, Categoria, Note locali, Assegnazione IP Statico permanente e Regole di Port Forwarding.

---

## [1.01.00] - 2026-08-26

### 🌍 Supporto Multilingua (i18n) & Rilascio Open Source
* **Supporto Internazionale Completo (Italiano & Inglese):** Aggiunta l'architettura di localizzazione dinamica con dizionari JSON dedicati (`it.json` e `en.json`) e helper reattivo `t(key)`.
* **Selettore Lingua nell'Header:** Aggiunto il menu a tendina 🇮🇹 IT / 🇬🇧 EN nella barra superiore per cambiare istantaneamente la lingua dell'intera dashboard senza ricaricare la pagina.
* **Persistenza & Rilevamento Automatico:** Il sistema rileva automaticamente la lingua del browser dell'utente e memorizza la preferenza selezionata in `localStorage`.
* **Standard Open Source GitHub:** Aggiunto file `LICENSE` (licenza MIT), rafforzato `.gitignore` per prevenire il leak accidentale di credenziali o database e documentazione pronta per la community.

---

## [1.00.08] - 2026-08-26

### ⚡ Sincronizzazione Totale Speed Test & Analisi Prestazioni
* **Congruenza Matematica Assoluta:** Risolto il disallineamento tra il valore istantaneo dello speedtest del Gateway (970 Mbps) e la serie storica del database.
* **Sincronizzazione Automatica Gateway eero:** Il poller registra in modo continuo nel database SQLite ogni nuova misurazione reale completata dal Gateway eero, alimentando correttamente il grafico e le statistiche aggregate.
* **Unificazione Single Source of Truth:** L'ultimo punto del grafico, le schede di riepilogo in cima alla pagina Speed Test, la card di anteprima della Dashboard e le statistiche aggregate (Medie, Picchi Massimi, Latenza) attingono ora alla medesima sorgente dati coerente.
* **Esecuzione Test Ottimizzata:** Il trigger manuale dello speed test attende fino a completamento reale della misura hardware da parte del router eero prima di salvare e aggiornare l'interfaccia.

---

## [1.00.07] - 2026-08-26

### 🏷️ Indicatori Visivi Tipo IP nella Tabella Dispositivi
* **Badge Distintivo STATICO vs DHCP:** Ciascun dispositivo nella tabella principale mostra ora chiaramente lo stato dell'indirizzo IP con un badge dedicato:
  * 🟢 **`STATICO`** (Verde Smeraldo) se il dispositivo ha una prenotazione DHCP attiva su Cloud eero o un IP statico configurato.
  * ⚪ **`DHCP`** (Grigio Slate) se il dispositivo ottiene un indirizzo IP in assegnazione dinamica.
* **Filtro Rapido per Tipo di Assegnamento:** Aggiunto un menu a tendina nella barra filtri per isolare al volo *Solo IP Statici* o *Solo DHCP Dinamici*.
* **Sincronizzazione Poller delle Prenotazioni:** Il poller di background interroga le prenotazioni Cloud eero e propaga lo stato statico in tempo reale su tutta la dashboard.

---

## [1.00.06] - 2026-08-26

### 🔄 Assegnazione IP Corrente & Riassegnazione Intelligente
* **Assegnazione IP Corrente del Dispositivo:** Permette di confermare e rendere permanente tramite prenotazione DHCP l'indirizzo IP che il dispositivo sta già utilizzando (tramite lease dinamico).
* **Riassegnazione Automatica da Altre Schede di Rete / Vecchi Host:** Se un IP apparteneva precedentemente a un'altra scheda di rete (es. Wi-Fi vs Ethernet dello stesso PC) o a un vecchio apparato, la dashboard non blocca più l'operazione ma offre il pulsante **`Riassegna e Riserva`**, rimuovendo automaticamente la vecchia prenotazione obsoleta dal Cloud eero prima di registrare la nuova.
* **Alert Contestuali Informativi:** Gli avvisi di occupazione IP per dispositivi client diventano avvisi informativi (badge ambra) che informano sul trasferimento senza impedire l'azione all'amministratore di rete.

---

## [1.00.05] - 2026-08-26

### 🌐 Gestione Nativa IP Statici (DHCP) & Port Forwarding
* **Prenotazioni DHCP Sincronizzate con Cloud eero:** Aggiunta la gestione autentica delle prenotazioni IP statico con creazione (`POST /reservations`) ed eliminazione (`DELETE /reservations/{id}`) in tempo reale tramite Cloud eero.
* **Rilevamento Conflitti IP in Tempo Reale:** L'interfaccia analizza istantaneamente l'IP digitato confrontandolo con il Gateway, i nodi mesh, le altre prenotazioni attive e tutti i dispositivi connessi, impedendo conflitti o collisioni di rete.
* **Gestione Port Forwarding Integrata per Dispositivo:** Tabella interattiva delle porte aperte per ciascun host (Porta WAN, Porta LAN, Protocollo TCP/UDP/Both, Descrizione) con aggiunta e cancellazione con un clic.
* **Nuova Interfaccia Modale a Schede (Tabs):** Organizzazione in 3 sezioni chiare: `Dati & Categoria`, `IP Statico (DHCP)` e `Port Forwarding`.

---

## [1.00.04] - 2026-08-26

### 🛠️ Gestione Dispositivi & Metadati Locali
* **Fix Categoria e Preferiti:** Risolto il disallineamento maiuscole/minuscole sugli indirizzi MAC che impediva la persistenza e il ricaricamento di Categoria, Preferiti, Note e Flag di Gaming Mode in SQLite.
* **Badge Preferiti ⭐ & Filtro Dedicato:** I dispositivi contrassegnati come preferiti mostrano una stella ⭐ accanto al nome e possono essere filtrati al volo dal selettore di categoria (*Solo Preferiti*).
* **Semplificazione Modale Dispositivo:** Rimossa la configurazione confusa della prenotazione IP statico dal popup; introdotto un box informativo chiaro con **IP Attuale** e **Nodo Mesh Collegato**.
* **Rimozione Pulsanti LED Globali:** Eliminati i pulsanti *"Spegni Tutti i LED"* e *"Accendi Tutti i LED"* dalla testata dei Nodi Mesh in linea con i vincoli firmware eero v7.x.
* **Pulizia Completa Database Banda:** Rimosse le tabelle obsolete `wan_metrics` e `device_metrics` e tutti i cicli di scrittura continui di throughput su SQLite.

---

## [1.00.03] - 2026-08-26

### 🏷️ Raffinamento Interfaccia & Nodi Mesh
* **Etichetta "Stato" sulle schede dei Nodi:** Sostituita la precedente dicitura con un'etichetta univoca e pulita **`Stato: Online • Ottimale`**.
* **Rimozione Controlli LED non supportati da Cloud:** Rimosso il pulsante toggle LED dalle schede dei nodi e lo scheduler Notte LED. I nodi eero (in particolare con firmware v7.x) riservano il controllo fisico dei LED all'app mobile ufficiale / BLE; la dashboard evita comandi che verrebbero sovrascritti dal cloud.
* **Pulsante Riavvio Nodi Dedicato:** Mantenuto il comando nativo e verificato di riavvio individuale per ciascun nodo mesh.

---

## [1.00.02] - 2026-08-26

### 🧹 Semplificazione & Allineamento Diretto API eero
* **Rimozione Scheda Storico Banda & WAN:** Eliminata la sezione e i grafici storici non supportati in modo nativo continuo dall'API base eero.
* **Rimozione Contatore WAN nell'Header:** Eliminato il tachimetro di throughput al centro dell'header per mostrare solo informazioni certe e certificate.
* **Rimozione Velocità Live nella Pagina Dispositivi:** Eliminata la colonna di velocità istantanea, sostituita con i dati fisici autentici delle API eero: **Banda & Canale Wi-Fi**, **Segnale RSSI (dBm)** e **Link Speed PHY (es. 780 / 866.7 Mbps)**.
* **Integrità Assoluta:** L'applicazione visualizza esclusivamente ciò che viene inviato senza intermediari dall'infrastruttura eero.

---

## [1.00.01] - 2026-08-26

### 🛡️ Approccio Rigoroso a Dati Reali (No Simulation)
* **Rimozione stime sintetiche di throughput:** Eliminata qualsiasi logica di generazione fittizia o casuale del throughput istantaneo (`download_rate_mbps` / `upload_rate_mbps`) per i dispositivi live in `eero_client.py`.
* **Eliminazione moltiplicazione temporale artificiale:** Rimosso il calcolo stimato su 24h in `metrics.py` basato su velocità fittizie (`avg_rate * 24h * 0.15`). La classifica dei consumi (*Bandwidth Hogs*) mostra unicamente i byte effettivi misurati.
* **Integrità metrica:** I dispositivi Wi-Fi o IoT a riposo che non scambiano traffico o per cui l'API standard non espone contatori riportano fedelmente `0.0 Mbps` e `0 GB`, senza alcuna alterazione o gonfiamento sintetico.

### 🐛 Bug Fixes
* **Risolto falso positivo consumo robot Higgins:** Corretta la lista delle parole chiave in `eero_client.py` e `metrics.py` in cui il dispositivo `"higgins"` (robot lavapavimenti) era erroneamente classificato tra i client ad alto consumo multimediale/streaming.
* **Correzione calcolo Delta 24h in SQLite:** Risolto un bug in `db.py` in cui, in caso di delta nullo (`MAX - MIN = 0`), veniva mostrato erroneamente il contatore cumulativo a vita (`MAX(rx_bytes)`), facendo apparire il traffico storico dell'intero ciclo vitale del dispositivo come se fosse avvenuto nelle ultime 24 ore.
* **Rimozione baseline sintetica WAN:** Eliminata la generazione di campioni fittizi nei grafici WAN in caso di database appena avviato o con pochi campioni.

### 🎨 Interfaccia Utente & Nuove Funzionalità
* **Aggiornamento versione visiva:** La versione dell'applicazione è stata aggiornata a **v1.00.01** sia nell'header che nel footer.
* **Visualizzatore Changelog interattivo:** Cliccando sul badge della versione (`v1.00.01`) o sul link nel footer si apre direttamente un popup modale con la cronologia dettagliata delle modifiche.
* **Gestione elegante degli stati vuoti:** Aggiunto messaggio descrittivo pulito nella tabella e nei grafici dei consumi quando non sono presenti dispositivi con traffico intensivo registrato.
* **Pulizia database locale:** Azzerati i record legacy con campioni simulati/anomali per garantire una ripartenza pulita e autentica.

### 📚 Documentazione & FAQ
* **Aggiornamento Manuale & FAQ integrate:** Aggiornate le sezioni 4 (*Monitoraggio Banda*) e 8 (*FAQ & Risoluzione Problemi*) del manuale integrato per spiegare nel dettaglio la differenza tra dispositivi cablati e Wi-Fi standard e l'approccio a dati rigorosi adottato.

---

## [1.0.0] - 2026-08-25

### 🚀 Release Iniziale
* **Architettura Self-Hosted su Docker:** Containerizzazione completa con FastAPI, Alpine.js, Tailwind CSS e Chart.js.
* **Autenticazione Ufficiale 2FA OTP:** Login sicuro tramite One-Time Password via SMS/Email con persistenza della sessione su disco.
* **In-Memory Zero-Latency Poller:** Monitoraggio continuo della rete mesh con latenza 0ms per l'interfaccia.
* **Bandwidth Historian & WAN Metrics:** Grafici temporali del traffico di rete (24h, 7gg, 30gg) e classifica Top Consumer.
* **Device Management Suite:** Ricerca, filtri per frequenza (2.4/5/6 GHz/Ethernet), personalizzazione icone, note, assegnazione IP statico e pausa internet a un clic.
* **Automazioni & Controlli Rapidi:** Smart Guest Wi-Fi con QR Code dinamico, Gaming/Focus Mode (Low Latency), Scheduler Notturno LED e Speed Test integrato.
* **Sistema di Notifiche:** Supporto per Bot Telegram e Webhook HTTP generici per nuovi dispositivi connessi e nodi offline.
* **Manuale Utente Integrato:** 8 capitoli con guida interattiva e help contestuale.
