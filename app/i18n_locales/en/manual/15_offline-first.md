---
id: offline-first
title: 15. Offline-First Architecture & Local Assets
icon: shield-check
summary: Total dashboard resilience with 100% locally bundled fonts and libraries, zero external CDN dependencies, and air-gapped operation.
---
### Offline-First Architecture & Local Assets (v1.6.0)

The dashboard adopts a 100% offline-first architecture to deliver maximum privacy, instant page rendering, and uninterrupted reliability even during internet outages or WAN blackouts:

* **Complete Local Dependency Vendoring:**
  - All client-side libraries (Tailwind CSS, Alpine.js, Chart.js, and Lucide Icons) are bundled locally and served directly from `/app/static/vendor/`.
  - Zero requests to external public CDNs (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`, `unpkg.com`): absolute third-party tracking immunity and resilience against DNS filters or aggressive ad-blockers.
* **Self-Hosted Typography Fonts:**
  - High-legibility web fonts **Inter** (UI design system) and **JetBrains Mono** (Live Log Console and data tables) are packaged inside the container as high-performance WOFF2 files in `/app/static/fonts/`.
  - Instant typography rendering with zero round-trips to Google Fonts or remote providers.
* **Air-Gapped & Isolated Homelab Readiness:**
  - The dashboard starts, initializes, and functions flawlessly inside isolated management VLANs, air-gapped lab servers, or offline local networks without outbound WAN access.
* **Progressive Web App (PWA) & Service Worker:**
  - Built-in Service Worker (`sw.js`) pre-caches core assets, enabling seamless dashboard launch and offline status review during transient local connectivity hiccups.
