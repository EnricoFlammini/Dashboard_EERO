---
id: multi-network
title: 9. Gestion multi-réseaux & Commutation à chaud
icon: globe
summary: Prise en charge des comptes eero multi-sites, basculement instantané et persistance du réseau sélectionné.
---
### Gestion multi-réseaux & Commutation à chaud

* **Sélecteur dynamique d'en-tête (Windows 11 Fluent) :** Si votre compte eero gère plusieurs réseaux (ex. Domicile principal, Bureau, Résidence secondaire), un menu déroulant interactif affiche le nombre de nœuds et de clients actifs pour chaque site.
* **Basculement instantané en mémoire :** La sélection d'un autre réseau commute immédiatement l'affichage sans redémarrer le conteneur ni ressaisir d'identifiants. Le cache RAM est réinitialisé et actualisé en temps réel.
* **Persistance du choix de réseau :** L'emplacement actif est conservé dans `session.json` et dans la base SQLite locale, préservant votre choix après les redémarrages.
* **Prise en charge du mode Démo :** Comprend une flotte virtuelle à double environnement (*Casa Rossi Mesh 6E* et *Bureau Pro Mesh*) pour tester la gestion multi-sites.
* **Architecture du réseau actif & Concurrence :** La commutation s'applique globalement à l'instance du serveur. Pour visualiser simultanément plusieurs réseaux côte à côte, il suffit de déployer deux conteneurs Docker légers sur des ports distincts.
