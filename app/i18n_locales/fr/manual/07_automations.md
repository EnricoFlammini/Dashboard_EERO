---
id: automations
title: 7. Automations, QR Invités, AdGuard Home, Telegram & Notifications
icon: zap
summary: Wi-Fi Invités dynamique avec QR code, synchronisation DNS AdGuard Home, alertes Telegram/Webhook et rapport quotidien.
---
### Centre d'automatisations & fonctionnalités avancées

L'onglet **Contrôles & QR Invités** regroupe les outils sous forme de modules interactifs :

1. **Smart Wi-Fi Invités avec QR Code dynamique :**
   - Génère instantanément un QR code imprimable adapté au thème actif (fond clair en mode jour, ardoise foncée en mode nuit).
   - Bouton d'activation/désactivation du réseau invités en 1 clic avec générateur de mot de passe sécurisé.
2. **Synchroniseur DNS multi-moteurs :**
   - **Support multi-instances hétérogène :** Gestion simultanée d'instances AdGuard Home, Pi-hole (v5 et v6) et Technitium DNS.
   - **Synchronisation automatique continue :** Aligne les noms d'hôtes et réservations d'adresses IP dès la découverte de nouveaux clients.
   - **Nettoyage intelligent des adresses & Custom DNS :** Résolution des baux DHCP réattribués, assainissement RFC 1123 et support **Custom & Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) avec priorité IPv4 (`AF_INET`).
   - **Exclusion par appareil :** Commutateur individuel *"Exclure de la synchronisation DNS"* dans la fiche de l'appareil.
3. **Alertes Telegram & Webhooks :**
   - **Registre persistant & Protection anti-tempête :** Isolation des adresses MAC de démonstration pour éviter les fausses alertes au premier démarrage.
   - **Nouveaux appareils connectés :** Alerte immédiate lorsqu'un nouvel équipement se connecte au réseau.
   - **Nœud Mesh hors ligne :** Notification instantanée en cas de perte de connectivité d'un point d'accès eero.
4. **Rapport quotidien (Daily Digest) :**
   - Envoi automatisé à heure configurable (par défaut 21:00) avec score de santé, statut de la connexion, clients connectés et dernier test de débit.
5. **Mode Gaming & Focus (Basse latence) :**
   - Met en pause d'un clic le trafic des appareils secondaires pour éliminer la gigue lors des sessions de jeu ou réunions vidéo.
6. **Règles de pare-feu IPv6 Pinhole :**
   - Gestion visuelle pour ouvrir ou fermer des ports TCP/UDP sur des appareils IPv6 spécifiques.
