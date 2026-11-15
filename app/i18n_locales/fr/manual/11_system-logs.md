---
id: system-logs
title: 11. Journaux système & Diagnostics avancés
icon: terminal
summary: Console en direct des journaux, niveaux de verbosité dynamiques, rétention, exportation et purge sécurisée.
---
### Gestion des journaux système & Diagnostics avancés

La carte **Gestion des journaux & Diagnostics** offre un contrôle complet sur la journalisation :

* **Interrupteur principal (Master Switch) :** Active ou suspend l'écriture des événements dans la base SQLite locale et le fichier rotatif sur disque (`data/system.log`).
* **Niveaux de verbosité dynamiques sans redémarrage :**
  - `DEBUG` : Détails exhaustifs de tous les appels d'API et synchronisations.
  - `INFO` : Suivi standard des événements significatifs et connexions.
  - `WARNING` : Alertes de latence, pertes de signal et anomalies mineures.
  - `ERROR` : Limité aux erreurs critiques et exceptions bloquantes.
* **Période de rétention automatique :** Définissez la durée de conservation : 24h, 7 jours, 15 jours, 1 mois ou durée personnalisée (avec purge automatique par tâche de fond).
* **Visualiseur de journaux en direct :** Console terminale haute visibilité avec police monospace, recherche plein texte, filtres par niveau de gravité et rafraîchissement automatique toutes les 10 secondes.
* **Outils d'exportation & Purge :** Téléchargement au format texte standard `.log` ou `.json` structuré, et bouton de purge sécurisée protégé par autorisation RBAC.
