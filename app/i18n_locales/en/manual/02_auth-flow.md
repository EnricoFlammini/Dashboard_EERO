---
id: auth-flow
title: 2. Authentication & Access Control (RBAC / 2FA)
icon: key
summary: Initial administrator setup (Zero-Default), local RBAC roles, and eero 2FA login procedure.
---
### Access Management, Initial Setup & Authentication

#### 1. Initial Administrator Setup (Zero-Default Security)
On first launch, the suite enforces a strict zero-default credential policy:
- **Guided Setup Wizard:** If no user accounts exist in the local database, an interactive full-screen onboarding modal prompts you to define your administrator username and secure password with confirmation.
- **Headless Docker Bypass (Optional):** For automated deployments or headless container environments, supply `ADMIN_USER` and `ADMIN_PASSWORD` in your `.env` or `docker-compose.yml`. On startup, the container provisions the administrator account automatically and bypasses the web setup wizard.
- **Granular Roles & Permissions (RBAC):** From *Settings -> User Management & Permissions*, the administrator can create accounts with distinct roles (`Admin`, `Operator`, `Viewer`) and toggle individual operational permissions (DNS management, network commands, data exports, log inspection).

#### 2. eero Cloud Authentication (2FA OTP)
Once local authentication is complete (or if local authentication is not required):
1. **Requesting the OTP Code:**
   - In the login screen, enter the phone number or email address associated with your eero account (e.g., `+1234567890` or `user@example.com`).
   - Click **"Send OTP Code"**.
2. **Verifying the Code:**
   - You will receive a 6-digit verification code from eero via SMS or Email.
   - Enter the code into the verification input and confirm.
3. **Session Persistence:**
   - The verified authentication token is saved to `/app/data/session.json` with restrictive `0600` owner permissions. When the Docker container restarts, your session is automatically restored without prompting for another OTP.
4. **Demo Mode & Quick Switcher:**
   - To explore the interface without entering real credentials, activate Demo Mode using the button on the login screen or by setting `DEMO_MODE=true` in `.env`.
   - If authenticated, you can switch anytime using the **"✨ Demo Mode"** button in the lower left sidebar to inspect mock telemetry without losing your live session. When active, it displays a vibrant emerald green button with an explicit **"DEMO ATTIVA"** indicator (and a top header status pill); clicking it again returns immediately to your live network.
