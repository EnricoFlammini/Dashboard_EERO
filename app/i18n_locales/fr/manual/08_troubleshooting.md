---
id: troubleshooting
title: 8. Résolution des problèmes, Mises à jour & FAQ
icon: wrench
summary: FAQ sur la télémétrie, mise à jour automatique Docker, sécurité, sauvegardes et dépannage.
---
### Questions fréquentes & Résolution des problèmes

* **Comment mettre à jour le tableau de bord ?**
  - Le tableau de bord vérifie les nouvelles versions sur Docker Hub et GitHub Releases et affiche un badge de mise à jour lorsqu'une version sort.
  - Pour mettre à jour, exécutez `docker compose pull && docker compose up -d` dans le dossier qui contient votre `docker-compose.yml`. Le dossier `./data` est conservé.
  - Sur un NAS Synology, utilisez **Container Manager → Projet → Action → Construire**, ou laissez le Planificateur de tâches de DSM faire la mise à jour automatiquement. Consultez le [guide Synology](https://github.com/EnricoFlammini/Dashboard_EERO/blob/main/deploy/synology/README.md).
  - Le bouton **Mettre à jour le conteneur maintenant (1 clic)** nécessite le socket Docker (`/var/run/docker.sock`) monté dans le conteneur. Pour l'instant il télécharge seulement la nouvelle image : exécutez ensuite la commande ci-dessus pour basculer dessus.
* **Quelles informations proviennent directement de l'infrastructure eero ?**
  - L'état de connexion, l'adresse IP locale, le MAC, le nœud de rattachement, la bande de fréquence (**2.4 GHz, 5 GHz, 6 GHz ou Câblé**), le canal, le niveau RSSI en **dBm** et le débit de liaison physique (**PHY Link Rate**).
* **Sécurité & Protection des données :**
  - **Protection CORS & CSRF :** Accès cross-origin restreint par défaut et validation des requêtes mutantes.
  - **Nettoyage des identifiants Wi-Fi :** Les mots de passe du réseau sont systématiquement expurgés des données publiques d'aperçu.
  - **Permissions strictes sur session.json :** Créé avec des droits restreints `0600` accessibles uniquement au processus du conteneur.
* **Que faire si la connexion eero expire ?**
  - Cliquez sur **Déconnexion** dans le menu latéral puis réitérez la procédure d'authentification (SMS, e-mail ou Amazon OAuth2).
* **Comment sauvegarder la configuration locale ?**
  - L'ensemble des données personnalisées (noms, catégories, notes, historiques, règles) réside dans `./data/metrics.db`. Il suffit de sauvegarder le dossier `./data`.
* **Pourquoi la connexion SMS/e-mail échoue-t-elle avec une erreur 401 ?**
  - Si votre compte eero est associé à un profil Amazon, utilisez l'option **"Connexion avec Amazon (OAuth2 / PKCE)"** dans la modale d'accès.
* **Comment configurer le Custom & Split DNS ?**
  - Définissez les variables d'environnement `CUSTOM_DNS_SERVERS` et `CUSTOM_DNS_DOMAINS` pour résoudre directement les domaines locaux via vos serveurs DNS internes.
* **Comment fonctionne l'autoréparation SQLite ?**
  - En cas de corruption liée à un arrêt brusque, le moteur applique une récupération en 3 phases (`REINDEX`, recréation de table, sauvegarde et reconstruction) en créant une copie `.corrupt.bak`.
