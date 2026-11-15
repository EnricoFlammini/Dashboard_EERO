---
id: offline-first
title: 15. Architecture Offline-First & Ressources locales
icon: shield-check
summary: Fonctionnement autonome avec polices et bibliothèques embarquées, zéro dépendance externe et support air-gapped.
---
### Architecture Offline-First & Ressources locales

L'application applique une architecture 100% hors ligne garantissant une confidentialité totale, un rendu instantané et une disponibilité continue même en cas de panne de connexion Internet :

* **Intégration locale complète des dépendances :**
  - Toutes les bibliothèques frontend (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) sont servies depuis `/app/static/vendor/`.
  - Aucune requête vers des CDN externes : absence de traçage tiers et insensibilité aux bloqueurs de publicité ou filtres parentaux.
* **Polices de caractères auto-hébergées :**
  - Les polices de haute lisibilité **Inter** (interface utilisateur) et **JetBrains Mono** (console et tableaux) sont incluses au format WOFF2 dans `/app/static/fonts/`.
* **Résilience en environnement cloisonné (Air-Gapped) :**
  - La suite démarre et fonctionne parfaitement au sein de réseaux locaux isolés ou de serveurs HomeLab sans accès Internet public.
* **Progressive Web App (PWA) & Service Worker :**
  - Le Service Worker intégré précharge les ressources essentielles, permettant la consultation de l'interface même lors de micro-coupures réseau.
