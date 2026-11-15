---
id: dashboard-mesh
title: 3. Tableau de bord & Topologie Mesh
icon: network
summary: Score de santé du réseau, cartes d'état des nœuds et actions rapides.
---
### Compréhension du tableau de bord général

* **Score de santé du réseau (1-100) :** Indicateur synthétique calculé à partir de la disponibilité des nœuds maillés, de la présence de la passerelle et de la qualité du signal RSSI des clients.
* **Cartes de synthèse :**
  - *État WAN :* Adresse IP publique, fournisseur d'accès, IPv6, barre de santé et dernière actualisation.
  - *Passerelle principale :* Modèle, adresse IP LAN, sous-réseau, DNS, firmware et nombre de nœuds en ligne.
  - *Clients connectés :* Total et répartition 6 GHz / 5 GHz / 2.4 GHz / Câblé, appareils connus, invités et nouveaux.
  - *Dernier test de vitesse :* Débit montant/descendant, ping, score bufferbloat et historique récent.
* **Topologie des nœuds eero :**
  - *Nœud passerelle :* Le nœud principal relié directement au modem ou à l'ONT opérateur.
  - *Balises / Extendeurs Mesh :* Nœuds secondaires étendant la couverture sans fil.
  - *Type de liaison (Backhaul) :* Indique si l'interconnexion s'effectue par câble Ethernet ou par liaison sans fil dédiée.
* **Actions rapides sur les nœuds :**
  - **Redémarrer le réseau :** Envoie une commande de redémarrage synchronisé à l'ensemble du réseau eero.
  - **Redémarrer un nœud :** Redémarre uniquement l'unité sélectionnée sans interrompre le reste de l'installation.
* **Fonctionnalités Mesh avancées :**
  - **Extendeurs Amazon Echo "eero Built-in" :** Détection automatique des enceintes Echo compatibles étendant la couverture Wi-Fi avec badge dédié **`eero Built-in`** et compte des clients associés.
  - **Élection de la passerelle en mode pont (Bridge) :** Identifie avec précision le véritable nœud passerelle via le drapeau `is_primary_node` et les voisins LLDP en amont de la liaison WAN.
  - **Photos officielles du matériel eero :** Chaque nœud affiche la photo officielle de son modèle matériel (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot, etc.).
  - **Assistant IA & Test de placement :** Diagnostic interactif par streaming SSE (`/api/network/assistant`), test de placement radio RF et gestion du VPN Guardian.
