---
id: intro
title: 1. Introduction & Architecture
icon: book-open
summary: Présentation de l'architecture auto-hébergée, sécurité 2FA/OAuth, thème à 3 états et 9 langues européennes.
---
### Qu'est-ce que eero Custom Dashboard & Management Suite ?
Cette application web est une plateforme complète et auto-hébergée de gestion et de surveillance avancée pour votre réseau Wi-Fi maillé **Amazon eero**.

#### Caractéristiques architecturales :
1. **Auto-hébergé & Confidentialité totale :** Fonctionne dans un conteneur Docker isolé sur votre serveur local ou NAS (HomeLab). Image officielle multi-architecture Docker Hub pour `linux/amd64` et `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Authentification flexible (2FA OTP & Amazon OAuth2) :** La connexion initiale au cloud eero utilise le mécanisme officiel à double facteur (OTP par SMS ou e-mail) ou le flux fédéré natif **Amazon OAuth2 / PKCE** pour les comptes migrés vers Amazon.
3. **Persistance & Isolation :** Le jeton de session (`session.json`) et la base de données SQLite (`metrics.db`) résident exclusivement dans le volume persistant `./data:/app/data`.
4. **Poller en mémoire à latence zéro :** Un processus asynchrone en arrière-plan interroge régulièrement le réseau et maintient un cache en RAM, assurant une navigation instantanée sans risque de limitation de débit (rate limiting).
5. **Design Windows 11 Fluent, Thème à 3 états & Raccourci `Ctrl+K` :** Interface moderne prenant en charge les modes Clair, Sombre et Système (Auto OS avec synchronisation native `prefers-color-scheme`), barre de recherche rapide globale `Ctrl+K` / `Cmd+K` et barre latérale rétractable.
6. **Support multilingue européen complet (9 langues) :** Parité intégrale des catalogues frontend et backend pour l'anglais, l'italien, le français, l'espagnol, l'allemand, le néerlandais, le portugais, le polonais et le grec.
