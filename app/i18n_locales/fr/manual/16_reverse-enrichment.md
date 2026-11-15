---
id: reverse-enrichment
title: 16. Reverse Client Enrichment & Découverte IPv6 ULA
icon: arrows-right-left
summary: Enrichissement bidirectionnel des interfaces locales, découverte d'adresses IPv6 ULA et suivi des nouveaux appareils.
---
### Reverse Client Enrichment & Découverte IPv6 ULA

Dans les réseaux double pile (Dual-Stack), les appareils interrogent fréquemment les résolveurs DNS locaux via des adresses **IPv6 ULA** (*Unique Local Address*, préfixes `fc00::/7` et `fd00::/8`). Comme ce trafic reste confiné au niveau Layer 2 local sans traverser le routeur WAN, le cloud eero n'a pas de visibilité sur ces adresses.

* **Reverse Client Enrichment via NDP & Ingestion REST :**
  - **Processus d'analyse automatique :** Le service interroge périodiquement la table de voisinage du noyau (NDP / ARP) et les serveurs DNS locaux pour associer les adresses ULA orphelines à leurs adresses MAC physiques.
  - **API d'ingestion externe (`POST /api/network/enrichment/neighbors`) :** Permet à des scripts ou conteneurs auxiliaires de transmettre des associations IP-MAC en direct.
  - **Synchronisation bidirectionnelle :** Les adresses découvertes sont réinjectées dans les enregistrements des clients et synchronisées avec les serveurs DNS pour associer automatiquement chaque adresse IP au nom lisible de l'appareil.
* **Badge visuel & Inspection détaillée :**
  - Les adresses enrichies sont signalées dans la table et la fiche détaillée par le badge distinctif violet **`ULA Enriched`**.
* **Appareils récents & Badge "NEW" :**
  - La date de première détection (`first_seen`) est conservée pour chaque appareil.
  - Tout appareil apparu dans les dernières 24 à 48 heures est mis en valeur avec le badge vert émeraude **`NEW`**.
* **Purge automatique de maintenance :**
  - Une tâche nocturne élimine automatiquement les adresses ULA temporaires inactives depuis plus de 30 jours pour préserver la base SQLite.
