---
id: auth-flow
title: 2. Authenticatie & Toegangsbeheer (RBAC / 2FA)
icon: key
summary: Eerste configuratie beheerder (Zero-Default), lokale RBAC-rollen en eero 2FA-inlogprocedure.
---
### Toegangsbeheer, Eerste Installatie & Authenticatie

#### 1. Eerste installatie beheerder (Zero-Default Security)
Bij de eerste opstart hanteert de suite een strikt beveiligingsbeleid zonder standaardwachtwoorden:
- **Begeleide installatiewizard:** Als er nog geen gebruikers bestaan, verschijnt er automatisch een schermvullend venster waarin de beheerder een gebruikersnaam en veilig wachtwoord instelt.
- **Headless Docker-bypass (optioneel):** Voor geautomatiseerde uitrol kunnen de omgevingsvariabelen `ADMIN_USER` en `ADMIN_PASSWORD` worden ingesteld in `.env` of `docker-compose.yml`. Het beheerdersaccount wordt dan direct aangemaakt.
- **Granulaire rollen & rechten (RBAC):** Onder *Instellingen -> Gebruikers & Rechten* kan de beheerder extra accounts toevoegen met specifieke rollen (`Admin`, `Operator`, `Viewer`) en operationele rechten aanpassen.

#### 2. Authenticatie bij de eero-cloud (2FA OTP)
Zodra de lokale aanmelding voltooid is (of indien lokale authenticatie niet verplicht is):
1. **OTP-code aanvragen:** Voer het e-mailadres of telefoonnummer in dat aan uw eero-account gekoppeld is en klik op **"Verstuur OTP-code"**.
2. **Code verifiëren:** Voer de 6-cijferige numerieke code in die u per sms of e-mail heeft ontvangen en bevestig.
3. **Sessie opslaan:** De geverifieerde token wordt bewaard in `/app/data/session.json` met strikte bestandsrechten `0600`, en blijft behouden na herstarts.
4. **Demo-modus & Snelle wisselaar:** Verken alle functies zonder echte inloggegevens via de knop **"✨ Demo-modus"** of met `DEMO_MODE=true`.

#### 3. Native Amazon OAuth2 / PKCE-aanmelding
Voor eero-accounts die gekoppeld zijn aan een Amazon-profiel biedt het dashboard de officiële **Amazon OAuth2 met PKCE S256 (RFC 7636)** login:
1. **Aanmelden met Amazon:** Klik op **"🛒 Aanmelden met Amazon"** in het inlogscherm om de beveiligde PKCE-procedure te starten.
2. **Autorisatie in browser:** Log in op Amazon en verleen toestemming; u wordt vervolgens doorgestuurd naar de officiële URL `/ap/maplanding`.
3. **Directe koppeling:** Kopieer de doorstuur-URL of de `code`-parameter, plak deze in het invoerveld en klik op **"eero-account koppelen"**.

#### 4. Globale beveiliging & Handhaving van `REQUIRE_LOCAL_AUTH`
In gedeelde netwerkomgevingen zorgt het instellen van `REQUIRE_LOCAL_AUTH=true` in `.env` voor:
- Beveiliging van alle API-routes (`/api/*`) en Prometheus-statistieken (`/metrics`) met verplichte geauthenticeerde sessie.
- Alleen essentiële status- en aanmeldingsroutes (`/api/health`, `/api/auth/local/*`, `/api/system/language`) blijven publiek bereikbaar.
