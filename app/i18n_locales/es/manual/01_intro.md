---
id: intro
title: 1. Introducción y Arquitectura
icon: book-open
summary: Descripción general de la arquitectura autoalojada, seguridad 2FA/OAuth, tema de 3 estados y 9 idiomas europeos.
---
### ¿Qué es eero Custom Dashboard & Management Suite?
Esta aplicación web es una plataforma integral y autoalojada de gestión, control y monitorización avanzada para su red Wi-Fi en malla **Amazon eero**.

#### Características arquitectónicas:
1. **Autoalojado y Privacidad Total:** Se ejecuta dentro de un contenedor Docker aislado en su servidor local o NAS (HomeLab). Imagen oficial multiarquitectura de Docker Hub para `linux/amd64` y `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Autenticación Flexible (2FA OTP y Amazon OAuth2):** La conexión inicial con la nube de eero utiliza el mecanismo oficial de doble factor (OTP por SMS o correo electrónico) o el flujo federado nativo **Amazon OAuth2 / PKCE** para cuentas vinculadas a Amazon.
3. **Persistencia y Aislamiento:** El token de sesión (`session.json`) y la base de datos SQLite (`metrics.db`) residen exclusivamente en el volumen persistente `./data:/app/data`.
4. **Sondeo en Memoria de Latencia Cero:** Un proceso asíncrono en segundo plano sondea periódicamente la red y mantiene una caché en RAM, garantizando una navegación fluida sin riesgo de limitación de tasa (rate limiting).
5. **Diseño Windows 11 Fluent, Tema de 3 Estados y Atajo `Ctrl+K`:** Interfaz moderna con soporte para modos Claro, Oscuro y Sistema (Auto OS con sincronización nativa de `prefers-color-scheme`), barra de búsqueda rápida global `Ctrl+K` / `Cmd+K` y barra lateral plegable.
6. **Soporte Multilingüe Europeo Completo (9 Idiomas):** Paridad total de catálogos frontend y backend para inglés, italiano, francés, español, alemán, neerlandés, portugués, polaco y griego.
