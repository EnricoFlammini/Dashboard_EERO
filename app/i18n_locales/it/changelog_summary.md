# Changelog - Sommario Versioni

Di seguito sono riassunti i titoli principali delle release. Il registro completo con tutti i dettagli tecnici è consultabile su GitHub.

## v1.6.2
* **Parità Completa Traduzioni Frontend & Backend (PR #79 - @todddube):** Parità al 100% dei cataloghi linguistici (457 chiavi backend e 1051 chiavi frontend in `en.json` e `it.json`), audit automatizzato e validazione continua in CI/CD.
* **Sanificazione Hostname RFC 1123 per Pi-hole v6 & Rimozione 404 Endpoint (Issue #83 - @richlilly2004):** Sanificazione rigorosa degli hostname per sincronizzazione Pi-hole v6 (conversione caratteri speciali e parentesi in trattini) e rimozione delle chiamate ridondanti a `/port_forwards`.
* **Persistenza & Caricamento Resiliente Configurazione MQTT (Issue #81 - @jpatchMC):** Allineamento payload API, supporto bi-direzionale per `discovery_prefix` / `homeassistant_prefix` e destrutturazione difensiva nel frontend.
* **Risoluzione Glitch Layout Tabella Dispositivi su Firefox (Issue #80 - @jpatchMC):** Eliminazione del tag `<colgroup>` dinamico a favore di definizioni native a celle per prevenire collassi o sfarfallii su Gecko.
* **Serializzazione Payload Notifiche Webhook & Isolamento Canali (Issue #85 - @Hatton920):** Serializzatore difensivo `_json_safe()`, ripristino allarmi istantanei di nodi offline e nuovi dispositivi su Home Assistant, e popolamento di `_known_macs` all'avvio.
* **Rifiniture UI/UX, Localizzazione & Nomi Dispositivi Troncati (Issue #84 - @XprofQ):** 11 perfezionamenti mirati: icone dinamiche fluent in tabella, tooltip e line-clamp a 2 righe per nomi lunghi, throughput WAN `whitespace-nowrap`, dropdown estesi a 30 con conteggio cablati corretto e note di rilascio GitHub originali bilingue.
* **Refactoring Architetturale i18n & Isolamento Test Suite (Issue #82 - @todddube):** Eliminazione traduttori legacy e regex (~90 righe potate), `affected_items_i18n` renderizzati nella lingua del visualizzatore e isolamento del database di test su cartella temporanea (`tempfile.mkdtemp`).

## v1.6.1
* **Bilinguismo Completo Impostazioni & Eliminazione FOUT Caricamento (PR #78 - @todddube):** Traduzione al 100% di tutte le schede e modali Impostazioni (Controlli, Utenti, Backup, Export, Aggiornamenti, MQTT, Schedulazioni, Pulizia Log), interpolazione nativa dei parametri e rimozione del flash di testo all'avvio (`body.i18n-pending`).
* **Prioritizzazione IPv4 Subnet LAN, Pruning Record Obsoleti Pi-hole v6 ed Esclusione Dispositivi (Issue #72):** Algoritmo a 5 livelli in `_sort_ipv4_candidates` che privilegia gli IP appartenenti alla subnet LAN fisica eero e penalizza i bridge container (`172.17.x.x`), potatura automatica (`prune_stale_ips`) dei vecchi record su Pi-hole v6 preservando i record manuali, e nuovo switch "Escludi da sincronizzazione DNS" (`dns_sync_excluded`).
* **Rilevamento Reti Robusto, Fallback EERO_NETWORK_ID e Guida Zero-Reti (Issue #69):** Parsing flessibile per payload eero singolari o atipici, fallback trasparente su variabile d'ambiente `EERO_NETWORK_ID`, banner guida reattivo "Nessuna Rete Rilevata" e protezione assoluta da inquinamento del database con dati demo su sessioni reali.
* **Scheduler Daily Digest Idempotente ai Riavvii & Orario Flessibile (Issue #70):** Tracciamento persistente su SQLite di `last_daily_digest_date` per eliminare lo spam di notifiche duplicate ai riavvii, orario di invio configurabile (`DAILY_DIGEST_HOUR` e `TZ`) con selettore orario interattivo nella card riepilogo.
* **Risoluzione Bug Bufferbloat WAN & Localizzazione Abbreviazioni Durata (Issue #71):** Riconoscimento immediato di `bufferbloat_grade`, `ping_under_load` e `bufferbloat_delta_ms` dal frontend `app.js` e arricchimento della cache `poller.py`, rating localizzati dinamicamente (IT/EN) e abbreviazioni di durata responsive (`7d`/`7gg`, `15d`/`15gg`, `1mo`/`1m`).
* **Compattazione Selettiva Multi-Tier, Indici Timestamp & Parsing Bitrate (Issue #73, #74):** Compattazione incrementale selettiva delle sole ore non ancora aggregate (risparmio CPU del 99.4%), indici B-tree su espressioni temporali SQLite, parser universale dei bitrate con unità di misura e strumenti di verifica integrità e backup deframmentato a caldo (`VACUUM INTO`).

## v1.6.0
* **Modulo 1 - Autenticazione Locale, RBAC & Smart Automations:** Gestione accessi multi-utente con ruoli `Admin`, `Operator` e `Viewer`, parental scheduling avanzato a fasce orarie e giorni della settimana, motore di manutenzione notturna programmata e backup di emergenza.
* **Modulo 2 - Compattazione Dati Multi-Tier, Bufferbloat & PWA Offline-First:** Compattazione scalabile SQLite (Raw 48h -> Oraria 30gg -> Giornaliera 365gg), indicatore analitico Bufferbloat con grading da A+ a F e latenze a riposo/carico, supporto Progressive Web App (PWA) con Service Worker per consultazione offline.
* **Modulo 3 - Notifiche & Disaster Recovery Snapshot:** Sistema di esportazione e ripristino snapshot crittografati/validati della configurazione, gestione scheduler parentale interattivo da interfaccia.
* **Modulo 4 - Gestione Log di Sistema, Live Console & Integrazioni Homelab:** Card di controllo per profondità di logging a caldo (`DEBUG`, `INFO`, `WARNING`, `ERROR`), retention temporale configurabile (24h, 7gg, 15gg, 1m, custom), Live Console Viewer acrilica con ricerca e filtri per severità, download log (.log / .json) e svuotamento sicuro con modale di conferma; integrazione MQTT con Home Assistant Auto-Discovery e device tracking; esportazione metrica nativa Prometheus/OpenMetrics (`/metrics`) con dashboard Grafana (13 pannelli); dispatcher notifiche multi-canale esteso a Discord Webhook e Pushover con allarmi per degrado bufferbloat, interferenze mesh, brute-force e backup.
* **Hub Note di Rilascio eeroOS & Community Feedback (Issue #55):** Monitoraggio firmware ufficiale via Zendesk REST API e feed Reddit r/amazoneero, con confronto allineamento flotta locale vs release cloud (Up-to-date, Update Available, Newer than published).
* **AI Network Diagnostics, Roaming Advisor & IoT Night Anomaly Detection (Issue #56):** Diagnostica intelligente in linguaggio naturale con narrative bilingue (IT/EN), checklist correttiva prioritaria, rilevamento sticky client con raccomandazione roaming e monitoraggio anomalie traffico notturno IoT.
* **Deep-Linking Navigazione & Sincronizzazione Stato URL (PR #28 / Issue #45):** Routing completo con sincronizzazione bidirezionale dell'URL hash/query e supporto cronologia browser.
* **Responsive App Shell, Header Windows 11 Fluent & Mobile Drawer (PR #29 / Issue #46):** Sidebar scorrevole con scrim su schermi mobile, header responsive con menu impostazioni Fluent, tabella dispositivi a schede su schermi piccoli e frame grafici ad altezza dinamica.
* **Modulo 6 - 100% Offline-First & Asset Locali (Issue #58) & Dispositivi "Recently Joined" (Issue #60):** Vendoring locale completo di librerie (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) e font WOFF2 (`Inter`, `JetBrains Mono`) per funzionamento 100% offline e air-gapped; tracciamento data primo accesso (`first_seen`), badge animato smeraldo "NEW" e ordinamento per data d'ingresso.
* **Modulo 7 - Reverse Client Enrichment & Scoperta IPv6 ULA (Issue #57):** Risoluzione del limite di routing L2 eero per query DNS locali; API REST di ingestion (`/api/network/enrichment/neighbors`), worker di probe ICMP/NDP, tabella persistente `device_discovered_ips` e chiusura del ciclo con sync "full-circle" su AdGuard Home; badge fucsia "ULA Enriched" con tooltip contestuale.
* **Modulo 8 - Concorrenza SQLite WAL, QR Code Wi-Fi Ospiti Aperti & Trasparenza Notifiche (Issue #62, #63, #64):** Risoluzione definitiva lock contention SQLite con semaforo `_write_lock`, timeout 60s e pragmi `busy_timeout=60000`; generazione QR Code standard Wi-Fi per reti ospiti aperte (`T:nopass;`) o protette; trasparenza canali di recapito (Telegram, Discord, Pushover, Webhook) nel Daily Digest Report.
* **Modulo 9 - Perfezionamento Discovery IPv6 ULA & Filtri Tabella Client (Issue #65):** Risoluzione visualizzazione e sincronizzazione IPv6 ULA su client dual-stack con fallback resiliente `ipv6_all || ipv6_addresses || [ipv6]`; completamento localizzazioni mancanti in inglese; lifecycle e auto-pruning notturno degli indirizzi scoperti obsoleti dopo 30 giorni.
* **Setup Wizard Iniziale Amministratore (Zero-Default Security):** Modale di onboarding guidato al primo accesso web per l'impostazione sicura di username e password admin; rimozione definitiva delle credenziali hardcoded da interfaccia e supporto al deploy headless Docker via `ADMIN_USER` e `ADMIN_PASSWORD`.

---

## v1.5.0
* **Statistiche & Analytics di Rete, Analisi SLA ISP & Data Export Center:** Nuova vista con grafici di ripartizione frequenze, carico nodi mesh, categorie, vendor e trend SLA con esportazione CSV/JSON.
* **Device Data Usage Insights Suite:** Nuova scheda "Consumo Dati" con selettore temporale (Ultime 24h, 7 Giorni, 30 Giorni), curve Chart.js e widget Top Bandwidth Hogs.
* **Multi-Network Fleet Management & Hot-Swap Dinamico (Issue #22):** Gestione di account multi-rete eero con switch immediato e conservazione della rete attiva nei cicli di polling.
* **Intelligent Address Pruning & Esclusione IPv6 DNS (Issue #31 & #30):** Pruning automatico di IP obsoleti e lease SLAAC IPv6 scaduti su AdGuard Home e DNS multipli.
* **Localizzazione Multilingua Daily Digest Telegram & Scheda Controlli (Issue #38):** Supporto bilingue completo EN/IT per report giornalieri, allarmi e preferenze utente.
* **Risoluzione Collisione Nodi Mesh & Localizzazione "Other/Altro" (Issue #41):** Match deterministico esatto per nomi a sottostringa e localizzazione dinamica di categorie e vendor.
* **Correzione Primary Gateway in Topologie Multi-Ethernet (Issue #36):** Gerarchia di elezione rigorosa del gateway primario su switch e reti cablate.
* **Chiarimento Telemetria Hardware Layer 2 & Dispositivi Cablati (Issue #40 & #42):** Eliminazione disclaimer fuorvianti e corretta spiegazione della commutazione hardware Ethernet.
* **Isolamento Release CI/CD Docker Hub:** Build isolate per branch di test senza sovrascrittura accidentale del tag `latest` stabile.
* **Community Hall of Fame & Crediti:** Sezione speciale nel modale About con ringraziamenti ai contributori e ai tester della community.
* **Telemetria Rigorosa, Accuratezza RF & Stabilità Nodi (PR #47-#53):** Correzioni per canali 5 GHz UNII-3 vs 6 GHz, isolamento sessione live/demo, elezione Primary Gateway per segmento URL, bonifica speedtest/RSSI sintetici e risoluzione network ID su regole/prenotazioni (crediti a @carbones73).
* **Hardening di Sicurezza & Vulnerability Remediation (4 Advisory GHSA):** Protezione Cross-Origin e middleware CSRF (`CORS_ORIGINS`), sanitizzazione credenziali Wi-Fi dall'overview pubblico, disattivazione documentazione interattiva `/docs` di default (`API_DOCS`) e permessi `0600` su `session.json` (crediti a @carbones73).
* **Visibilità & Ricerca Indirizzi IPv6 (Issue #43):** Estrazione dual-stack Global Unicast e Link-Local (`fe80::`), ricerca per IPv6 nella tabella client e sezione dedicata nel modale dispositivo con copia con 1 clic (crediti a @jpatchMC).
* **Simulatore Multi-Rete in Demo Mode:** Supporto dual-network indipendente (Casa Rossi Mesh 6E e Ufficio & Studio Pro Mesh).

---

## v1.4.02
* **Fix Lock SQLite all'Avvio durante la Pulizia dei Dati Mock Speedtest (Issue #35)**

---

## v1.4.01
* **Fix Risoluzione Accurata Primary Gateway con Nodi PoE e Mesh Misti (Issue #26)**
* **Risoluzione Server DNS Personalizzati & Rimozione Fallback IP Sviluppatore (Issue #30)**
* **Riconoscimento Dinamico Backhaul Wireless 6 GHz sui Nodi Mesh Wi-Fi 6E / Wi-Fi 7**
* **Fix Risoluzione Bug Filtri di Frequenza Tabella Dispositivi (ReferenceError)**
* **Allineamento Metriche Daily Digest & Esposizione Campo `line_stability` nei Webhook (Issue #32)**
* **Rilevamento Accurato Nodi Mesh Offline & Distinzione Nodi in Fase di Riavvio (Issue #34)**
* **Prevenzione Infiltrazione Dati Mock TIM nello Storico Speedtest & Purge SQLite (Issue #35)**

---

## v1.4.0
* **Restyling Windows 11 Fluent Design & Dual Theme Engine (Dark & Light Mode)**
* **Navigazione a Barra Laterale Collassabile (Stile Windows 11 Fluent) con Memoria di Stato**
* **Riposizionamento Controlli Rapidi (Gaming Focus & Demo Mode) con Indicatore Verde Smeraldo ad Alta Visibilità**
* **Network Health Score Breakdown & Modale Diagnostico Interattivo a 4 Pilastri (Issue #15)**
* **Multi-Engine DNS Synchronizer (Istanze Multiple Simultanee: AdGuard, Pi-hole, Technitium)**
* **Motore di Auto-Update Docker in-App a 1-Clic (/api/system/update)**
* **Rilevamento Automatico Nuove Versioni Docker Hub & GitHub Releases**
* **Storicizzazione Continua Segnale RSSI Dispositivi Wireless (SQLite)**
* **Nuova Sezione Qualità Wi-Fi & Copertura Mesh con Grafici Interattivi**
* **Watchlist Dispositivi con Segnale Critico & Suggerimenti Ottimizzazione**
* **Fix & Normalizzazione Prenotazioni DHCP Cloud ("Altre Prenotazioni Attive")**
* **Fix & Normalizzazione Regole Port Forwarding Multi-Formato per Dispositivo**
* **Supporto Nativo Pi-hole v6 REST API & Hostname Senza Dominio (Issue #25)**

---

## v1.03.03
* **Fix Risoluzione Accurata Primary Gateway Mesh in Bridge & Routed Mode (Issue #19)**
* **Preservazione Integrale Regole, Filtri, Upstreams e Blacklist AdGuard Home su Sync (Issue #21)**
* **Distinzione Accurata Tag Desktop / PC vs Laptop (`device_pc` / `device_laptop`)**
* **Eliminazione Falsi Positivi Gateway su Nodi Satellite da Stringhe URL API eero**
* **Riconciliazione Univoca del Nodo Gateway Principale della Rete**

---

## v1.03.02
* **Fix Formattazione Velocità Backhaul 2.5 Gbps su Card Nodi Mesh (Issue #14)**
* **Riconoscimento Frequenze e Canali Wi-Fi 6E & Wi-Fi 7 a 6 GHz (5900-7200 MHz, EHT 320MHz)**
* **Isolamento Grafico Badge 6 GHz e Prevenzione Sovrapposizione con 5 GHz**
* **Cache-Busting Automatico Asset Statici (Issue #17)**
* **Supporto Account Amministratori Invitati e Reti Condivise (Amazon Workaround)**
* **Mapping Categorie Native eero e Tag Ufficiali AdGuard (Issue #13)**

---

## v1.03.01
* **Fix Rilevamento Velocità Porte Ethernet Nodi Mesh (Issue #14)**
* **Distinzione Rigorosa Backhaul Wi-Fi vs Client Cablati su Nodi Satellite**
* **Velocità Link Ethernet Dispositivi Reale (Zero Hardcoding)**
* **Estrazione Avanzata Segnale Wireless RSSI (dBm) sui Beacon**

---

## v1.03.00
* **Risoluzione Universale Nodi e Client Mesh Multi-Generazione (Pro 7 / 6E / 6+)**
* **Switch Istantaneo Modalità Demo / Rete Live senza perdita Token**
* **Rilevamento Dinamico Velocità Ethernet 2.5G/10G & Telemetria Segnale dBm/PHY**
* **Sincronizzazione Profili Famiglia / Utente Cloud eero in Tabella e Dettaglio**
* **Distribuzione Ufficiale Docker Hub Multi-Arch (amd64/arm64)**
* **Integrazione Nativa AdGuard Home in-App (DNS & DHCP Sync)**
* **Pulsante Disconnessione Sicura con Modale di Conferma OTP**
* **Fix & Arricchimento Report Daily Digest Telegram**
* **Riorganizzazione Scheda Automazioni & Toggle Notifiche Dedicati**
* **Registro Persistente Dispositivi Noti (Zero Notifiche Duplicate al Riavvio)**
* **Ordinamento Dispositivi & Barra dei Titoli Bloccata (Sticky Header)**
* **Normalizzazione Dinamica Dispositivi & Gestione Flessibile Nodi/Sensori**
* **Modale About & Dedica Open Source**
* **Rendering Ottimizzato del Manuale & Liste Markdown**
* **Esportazione DNS (/etc/hosts, JSON) & Webhooks**

---

## v1.02.00
* **Telemetria Frequenze Wi-Fi (2.4 / 5 / 6 GHz) & Canali Radio**
* **Integrazione Profili Famiglia / Utente Cloud eero**
* **Filtri Multi-Criterio Avanzati su Tabella Client**

---

## v1.01.00
* **Supporto Multilingua Dinamico (Italiano & Inglese)**
* **Selettore Lingua nell'Header & Persistenza Preferenze**
* **Standard Open Source GitHub & Licenza MIT**

---

## v1.00.08
* **Sincronizzazione Totale Speed Test & Statistiche Gateway**

---

## v1.00.07
* **Indicatori Visivi Tipo IP (Badge STATICO vs DHCP)**

---

## v1.00.06
* **Assegnazione IP Corrente & Riassegnazione Intelligente**

---

## v1.00.05
* **Gestione Nativa IP Statici (DHCP) & Port Forwarding**

---

## v1.00.04
* **Gestione Dispositivi, Icone, Categorie e Preferiti**

---

## v1.00.01 - v1.00.03
* **Eliminazione Dati Fittizi a Favore di Telemetria Certificata 100%**

---

## v1.0.0
* **Release Iniziale: Architettura Self-Hosted Docker, 2FA OTP & Poller**
