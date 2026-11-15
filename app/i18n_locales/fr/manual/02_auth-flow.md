---
id: auth-flow
title: 2. Authentification & Gestion des accès (RBAC / 2FA)
icon: key
summary: Configuration initiale administrateur (Zero-Default), rôles locaux RBAC et procédure d'accès 2FA eero.
---
### Gestion des accès, configuration initiale & authentification

#### 1. Configuration initiale administrateur (Zero-Default Security)
Dès le premier lancement, la suite applique une stricte politique de sécurité sans identifiants préenregistrés :
- **Assistant guidé de configuration :** Si aucun compte n'existe dans la base, une fenêtre modale s'ouvre automatiquement pour inviter l'administrateur à définir son nom d'utilisateur et un mot de passe sécurisé.
- **Bypass Headless Docker (Optionnel) :** Pour les déploiements automatisés, il est possible de renseigner les variables d'environnement `ADMIN_USER` et `ADMIN_PASSWORD` dans `.env` ou `docker-compose.yml`. Au premier démarrage, le compte administrateur sera créé sans assistant.
- **Rôles & Permissions granulaires (RBAC) :** Depuis la section *Paramètres -> Utilisateurs & Permissions*, l'administrateur peut créer des comptes avec des rôles distincts (`Admin`, `Operator`, `Viewer`) et ajuster les droits opérationnels.

#### 2. Authentification avec le Cloud eero (2FA OTP)
Une fois l'accès local validé (ou si l'authentification locale n'est pas requise) :
1. **Demande du code OTP :** Saisissez l'e-mail ou le numéro de téléphone associé à votre compte eero puis cliquez sur **"Envoyer le code OTP"**.
2. **Vérification du code :** Saisissez le code à 6 chiffres reçu par SMS ou e-mail et validez.
3. **Sauvegarde de session :** Le jeton vérifié est enregistré dans `/app/data/session.json` avec des permissions strictes `0600`, persistant après chaque redémarrage du conteneur.
4. **Mode Démo & Commutateur rapide :** Activez le mode démonstration avec le bouton dédié ou la variable `DEMO_MODE=true` pour explorer les fonctionnalités sans identifiants réels.

#### 3. Authentification native Amazon OAuth2 / PKCE
Pour les comptes eero liés à un profil Amazon, le tableau de bord intègre le flux officiel **Amazon OAuth2 avec PKCE S256 (RFC 7636)** :
1. **Connexion Amazon :** Cliquez sur **"🛒 Se connecter avec Amazon"** dans la fenêtre de connexion pour initier le flux PKCE sécurisé.
2. **Autorisation dans le navigateur :** Connectez-vous sur Amazon et autorisez l'accès ; vous serez redirigé vers l'URL officielle `/ap/maplanding`.
3. **Liaison instantanée :** Copiez l'URL de redirection ou le paramètre `code`, collez-le dans le champ dédié et validez avec **"Lier le compte eero"**.

#### 4. Sécurité globale & Application `REQUIRE_LOCAL_AUTH`
Pour les environnements partagés ou exposés, définir `REQUIRE_LOCAL_AUTH=true` dans `.env` :
- Protège l'ensemble des routes API (`/api/*`) et les métriques Prometheus (`/metrics`) en exigeant une session utilisateur authentifiée.
- Seules les routes publiques indispensables (`/api/health`, `/api/auth/local/*`, `/api/system/language`) restent accessibles sans authentification.
