---
id: speedtest
title: 6. Test de vitesse, diagnostics & Qualité du signal Wi-Fi
icon: gauge
summary: Mesure de bande passante, historique des tests, analyse du signal RSSI et couverture mesh.
---
### Diagnostics de vitesse & couverture Wi-Fi

* **Test de vitesse manuel :** Cliquez sur **"Lancer le Speed Test"** pour initier une mesure en direct du débit descendant, montant, de la latence (ping) et de la gigue.
* **Tests automatisés programmés :** Le système peut planifier des tests périodiques en arrière-plan (par exemple toutes les 12 heures) pour surveiller la stabilité de la ligne dans le temps.
* **Graphiques historiques & Statistiques :** Courbes d'évolution du débit et de la latence avec moyennes, débits maximaux et analyse du bufferbloat.
* **Qualité Wi-Fi & Couverture Mesh :**
  - **Historique RSSI en dBm & Analyse universelle :** Échantillonnage précis des niveaux de signal convertis en valeurs numériques standardisées dans la plage `[-120, -1] dBm`.
  - **Indicateur de signal moyen & Niveaux de qualité :** KPI de qualité globale et classification : *Excellent* (≥ -50 dBm), *Bon* (-51 à -65 dBm), *Moyen* (-66 à -75 dBm), *Critique* (< -75 dBm).
  - **Actualisation live & Liste de surveillance :** Agrégation en temps réel des clients sans fil actifs garantissant que la **Weak Signal Watchlist** (`< -75 dBm`) est immédiatement disponible.
  - **Graphique interactif par appareil :** Visualisation Chart.js sur 24 heures ou 7 jours pour n'importe quel client avec liaison dynamique du sélecteur.
  - **Autoréparation SQLite en 3 étapes :** Mécanisme de récupération automatique réparant les index ou reconstruisant la base en cas d'arrêt inopiné sans perte de données.
