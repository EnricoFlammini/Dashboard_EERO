---
id: offline-first
title: 15. Offline-First Architectuur & Lokale Bronnen
icon: shield-check
summary: Volledige onafhankelijkheid met ingebouwde bibliotheken en lettertypen, geen externe CDN-afhankelijkheden.
---
### Offline-First Architectuur & Lokale Bronnen

De applicatie volgt een strikte offline-first strategie voor maximale privacy, directe laadtijden en continue werking zelfs tijdens internetstoringen:

* **Volledige lokale bundeling van bibliotheken:**
  - Alle frontend-bibliotheken (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) worden geserveerd vanuit `/app/static/vendor/`.
  - Geen verzoeken naar externe CDN's: geen tracking door derden en ongevoelig voor adblockers of DNS-filters.
* **Lokaal gehoste lettertypen:**
  - De lettertypen **Inter** (gebruikersinterface) en **JetBrains Mono** (terminal en metingen) zijn als geoptimaliseerde WOFF2-bestanden aanwezig in `/app/static/fonts/`.
* **Inzetbaar in geïsoleerde omgevingen (Air-Gapped):**
  - De suite start en functioneert vlekkeloos binnen afgesloten lokale netwerken zonder internettoegang.
* **Progressive Web App (PWA) & Service Worker:**
  - De ingebouwde Service Worker slaat kernbronnen op in de browsercache voor probleemloos gebruik bij korte netwerkonderbrekingen.
