---
id: system-logs
title: 11. Systeemlogboeken & Geavanceerde Diagnose
icon: terminal
summary: Live logconsole, dynamische detailniveaus, bewaartermijnen, exporteren en veilig wissen.
---
### Systeemlogboekbeheer & Geavanceerde Diagnose

Het paneel **Logboekbeheer & Diagnose** biedt volledige controle over systeemgebeurtenissen:

* **Hoofdschakelaar:** Schakelt het wegschrijven van gebeurtenissen naar de lokale SQLite-database en het roterende schijfbestand (`data/system.log`) in of uit.
* **Dynamische detailniveaus zonder herstart:**
  - `DEBUG`: Volledig overzicht van alle API-verzoeken en synchronisaties.
  - `INFO`: Standaardregistratie van relevante gebeurtenissen en verbindingen.
  - `WARNING`: Waarschuwingen bij latentievertraging of signaalverlies.
  - `ERROR`: Uitsluitend kritieke uitzonderingen en communicatiefouten.
* **Automatische bewaartermijn:** Bepaal de bewaartijd: 24u, 7 dagen, 15 dagen, 1 maand of aangepast (met automatische achtergrondopschoning).
* **Live logviewer:** Terminalweergave met monospace-lettertype, zoekfunctie, ernstfilters en automatische verversing elke 10 seconden.
* **Exporteren & Wissen:** Downloaden in standaard `.log`-tekstformaat of als gestructureerd `.json`, en veilig wissen met bevestigingsdialoog.
