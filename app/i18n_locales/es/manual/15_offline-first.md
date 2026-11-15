---
id: offline-first
title: 15. Arquitectura Offline-First y Recursos Locales
icon: shield-check
summary: Funcionamiento autónomo con fuentes y librerías locales, cero dependencias externas y soporte air-gapped.
---
### Arquitectura Offline-First y Recursos Locales

La plataforma sigue una arquitectura 100% autónoma que garantiza total privacidad, renderizado instantáneo y funcionamiento ininterrumpido sin acceso a Internet:

* **Inclusión Local Completa de Librerías:**
  - Todas las bibliotecas frontend (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) se sirven desde `/app/static/vendor/`.
  - Cero peticiones a CDN externas: sin rastreo de terceros e inmune a bloqueadores de publicidad o restricciones de DNS.
* **Fuentes Tipográficas Alojadas Localmente:**
  - Las tipografías de alta legibilidad **Inter** y **JetBrains Mono** se suministran en formato WOFF2 en `/app/static/fonts/`.
* **Resiliencia en Redes Aisladas (Air-Gapped):**
  - La suite se inicia y opera con normalidad en servidores locales y VLANs sin acceso a Internet exterior.
* **Progressive Web App (PWA) y Service Worker:**
  - El Service Worker precarga los recursos esenciales, permitiendo el uso de la interfaz incluso ante pérdidas temporales de conexión.
