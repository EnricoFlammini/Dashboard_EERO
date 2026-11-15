---
id: auth-flow
title: 2. Authentifizierung & Zugriffsverwaltung (RBAC / 2FA)
icon: key
summary: Ersteinrichtung des Administrators (Zero-Default), lokale RBAC-Rollen und eero 2FA-Anmeldung.
---
### Zugriffsverwaltung, Ersteinrichtung & Authentifizierung

#### 1. Ersteinrichtung des Administrators (Zero-Default Security)
Beim ersten Systemstart erzwingt die Suite eine strikte Sicherheitsrichtlinie ohne vorgegebene Passwörter:
- **Geführter Einrichtungsassistent:** Wenn noch kein Benutzerkonto existiert, öffnet sich automatisch ein Dialogfenster, in dem der Administrator Benutzername und ein sicheres Kennwort festlegt.
- **Automatisierte Bereitstellung (Headless Docker):** Für automatisierte Installationen können die Umgebungsvariablen `ADMIN_USER` und `ADMIN_PASSWORD` in `.env` oder `docker-compose.yml` hinterlegt werden. Das Administratorkonto wird dann ohne Assistenten angelegt.
- **Granulare Rollen & Berechtigungen (RBAC):** Unter *Einstellungen -> Benutzer & Berechtigungen* können weitere Konten mit differenzierten Rollen (`Admin`, `Operator`, `Viewer`) angelegt und individuelle Rechte zugewiesen werden.

#### 2. Authentifizierung bei der eero-Cloud (2FA OTP)
Sobald die lokale Anmeldung abgeschlossen ist (oder wenn keine lokale Authentifizierung erfordert wird):
1. **OTP-Code anfordern:** Geben Sie die mit Ihrem eero-Konto verknüpfte E-Mail-Adresse oder Telefonnummer ein und klicken Sie auf **"OTP-Code senden"**.
2. **Code bestätigen:** Geben Sie den per SMS oder E-Mail empfangenen 6-stelligen Code ein und bestätigen Sie die Eingabe.
3. **Sitzung speichern:** Das verifizierte Token wird in `/app/data/session.json` mit restriktiven Dateirechten `0600` gespeichert und übersteht Container-Neustarts.
4. **Demo-Modus & Schnellwechsler:** Erkunden Sie alle Funktionen ohne echte Zugangsdaten über die Schaltfläche **"✨ Demo-Modus"** oder die Umgebungsvariable `DEMO_MODE=true`.

#### 3. Native Amazon OAuth2 / PKCE-Anmeldung
Für eero-Konten, die mit einem Amazon-Profil verknüpft sind, bietet das Dashboard den offiziellen **Amazon OAuth2 mit PKCE S256 (RFC 7636)** Anmeldefluss:
1. **Amazon-Anmeldung:** Klicken Sie im Anmeldedialog auf **"🛒 Mit Amazon anmelden"**, um den kryptografisch abgesicherten PKCE-Ablauf zu starten.
2. **Autorisierung im Browser:** Melden Sie sich bei Amazon an und erteilen Sie die Berechtigung; danach werden Sie auf die Seite `/ap/maplanding` weitergeleitet.
3. **Sofortige Verknüpfung:** Kopieren Sie die Weiterleitungs-URL oder den `code`-Parameter in das entsprechende Eingabefeld und klicken Sie auf **"eero-Konto verknüpfen"**.

#### 4. Globale Sicherheit & `REQUIRE_LOCAL_AUTH`-Erzwingung
In geteilten oder offenen Netzwerken schützt das Setzen von `REQUIRE_LOCAL_AUTH=true` in der `.env`-Datei:
- Alle API-Endpunkte (`/api/*`) und Prometheus-Metriken (`/metrics`) erfordern eine gültige authentifizierte Benutzersitzung.
- Nur essentielle Routen für Statusprüfungen und Anmeldung (`/api/health`, `/api/auth/local/*`, `/api/system/language`) bleiben öffentlich erreichbar.
