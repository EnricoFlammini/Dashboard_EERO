---
id: device-details
title: 5. Métadonnées appareil, IP statiques & Redirection de ports
icon: adjustments
summary: Profil, noms personnalisés, icônes de catégorie, notes locales, baux DHCP statiques, IPv6 et redirection de ports.
---
### Gestion et configuration d'un appareil individuel

* **Fiche détaillée de l'appareil :**
  - **Nom et catégorie personnalisés :** Attribuez des catégories (Ordinateur, Mobile, Maison connectée, Multimédia, Jeux, Serveur/NAS, Autre) persistées dans la base SQLite locale.
  - **Notes & documentation locale :** Espace libre pour consigner des identifiants locaux, emplacements physiques ou ports de services.
  - **Adresses IPv6 Dual-Stack & Copie en 1 clic :** Bloc dédié répertoriant les adresses SLAAC et Link-Local avec bouton de copie rapide dans le presse-papier.
  - **Réservation DHCP (IP Statique) :** Définissez une adresse IP permanente avec détection automatique des collisions et réassignation simplifiée.
  - **Redirection de ports & Pare-feu IPv6 :** Configurez les règles de redirection IPv4 (Port WAN -> Port LAN) et les ouvertures de pare-feu IPv6 (pinholes) sur les ports TCP/UDP du client.
  - **Changement de profil :** Réaffectez l'appareil à un autre profil eero directement depuis la fiche avec confirmation immédiate.
  - **Sélecteur visuel de catégorie :** Choisissez parmi des icônes explicites avec option de réinitialisation automatique selon les données eero.
  - **Synchronisation immédiate du cache RAM :** Lors de l'enregistrement des métadonnées, le cache mémoire du poller est actualisé sans attendre le cycle suivant.
