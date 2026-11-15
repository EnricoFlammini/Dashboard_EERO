---
id: multi-channel-alerts
title: 14. Alertes multicanaux & Notifications d'urgence
icon: bell
summary: Dispatcher multicanal (Telegram, Discord, Webhook, Pushover, Ntfy) et alertes spécialisées.
---
### Alertes multicanaux & Notifications d'urgence

Le moteur de notifications prend en charge une diffusion multicanal des événements réseau critiques :

* **Canaux pris en charge :**
  - **Bot Telegram :** Alertes instantanées formatées en HTML avec détails du nœud et de l'appareil.
  - **Webhook Discord :** Notifications riches avec cartes intégrées et codes couleur de gravité.
  - **Pushover :** Notifications push prioritaires pour appareils mobiles.
  - **Ntfy (sh) natif :** Support des serveurs publics `ntfy.sh` ou instances auto-hébergées avec priorités et authentification par jeton.
  - **Webhook générique :** Envoi de charges utiles JSON pour intégrations personnalisées (Node-RED, n8n, Home Assistant).
* **Panneaux de contrôle & Masquage des secrets :**
  - Interface dédiée dans *Paramètres -> Contrôles* avec bouton de **Test immédiat**.
  - Masquage des jetons et URL de webhooks sous forme de `••••••••` pour prévenir les fuites accidentelles.
* **Alertes spécialisées intégrées :**
  - **Dégradation du Bufferbloat :** Avertissement lorsque la latence sous charge se dégrade fortement.
  - **Anomalie de qualité du nœud Mesh :** Alerte en cas de détection radar DFS ou d'affaiblissement de la liaison inter-nœuds.
  - **Appareil inconnu connecté (Alerte intrusion) :** Notification dès qu'un équipement non répertorié rejoint le réseau.
  - **Nœud déconnecté :** Notification d'urgence en cas de coupure d'un point d'accès eero.
