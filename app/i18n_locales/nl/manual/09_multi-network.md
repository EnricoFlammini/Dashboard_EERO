---
id: multi-network
title: 9. Multi-Netwerkbeheer & Direct Schakelen
icon: globe
summary: Ondersteuning voor multi-locatie eero-accounts, direct wisselen en persistente netwerkkeuze.
---
### Multi-Netwerkbeheer & Direct Schakelen

* **Dynamische locatiekiezer in de kopbalk (Windows 11 Fluent):** Beheert uw account meerdere eero-netwerken (bijv. Thuis, Kantoor, Vakantiewoning), dan toont een dropdownmenu direct de knooppunt- en apparaataantallen per locatie.
* **Direct wisselen in het geheugen:** Het selecteren van een andere locatie wisselt de weergave onmiddellijk zonder de container te herstarten of opnieuw in te loggen. De RAM-cache wordt direct vernieuwd.
* **Persistentie van het actieve netwerk:** De gekozen locatie wordt bewaard in `session.json` en de lokale SQLite-database, en blijft actief na herstarts.
* **Ondersteuning in Demo-modus:** Bevat een gesimuleerde vloot met twee locaties (*Casa Rossi Mesh 6E* en *Kantoor Pro Mesh*) om de mogelijkheden te demonstreren.
* **Architectuur & Parallel gebruik:** Het wisselen geldt globaal voor de serverinstantie. Voor gelijktijdige permanente monitoring van meerdere locaties naast elkaar kunnen twee afzonderlijke Docker-containers op verschillende poorten worden uitgevoerd.
