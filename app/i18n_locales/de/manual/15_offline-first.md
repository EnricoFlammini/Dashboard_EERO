---
id: offline-first
title: 15. Offline-First-Architektur & Lokale Ressourcen
icon: shield-check
summary: Vollständige Unabhängigkeit durch integrierte Bibliotheken und Schriftarten, keine externen CDN-Abhängigkeiten.
---
### Offline-First-Architektur & Lokale Ressourcen

Die Plattform verfolgt eine strikte Offline-First-Strategie für maximale Privatsphäre, blitzschnelle Ladezeiten und uneingeschränkte Nutzbarkeit auch bei Internetausfällen:

* **Vollständige lokale Einbindung von Abhängigkeiten:**
  - Sämtliche Frontend-Bibliotheken (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) werden direkt aus `/app/static/vendor/` ausgeliefert.
  - Keine Anfragen an externe CDNs: kein Tracking durch Dritte und Immunität gegenüber Werbeblockern oder DNS-Filtern.
* **Lokal gehostete Schriftarten:**
  - Die modernen Systemschriften **Inter** (Benutzeroberfläche) und **JetBrains Mono** (Konsole und Messwerte) sind im optimierten WOFF2-Format unter `/app/static/fonts/` enthalten.
* **Einsatz in isolierten Umgebungen (Air-Gapped):**
  - Die Suite startet und arbeitet problemlos in abgeschirmten LAN-Segmenten oder lokalen Serverumgebungen ohne Internetverbindung.
* **Progressive Web App (PWA) & Service Worker:**
  - Der integrierte Service Worker speichert Kernressourcen lokal im Browser-Cache und erlaubt Zugriff auch bei kurzen Netzunterbrechungen.
