---
id: auth-flow
title: 2. Autenticación y Gestión de Accesos (RBAC / 2FA)
icon: key
summary: Configuración inicial de administrador (Zero-Default), roles locales RBAC y proceso de acceso 2FA de eero.
---
### Gestión de Accesos, Configuración Inicial y Autenticación

#### 1. Configuración Inicial del Administrador (Seguridad Zero-Default)
En el primer inicio, la suite aplica una estricta política de seguridad sin credenciales predeterminadas:
- **Asistente Guiado de Configuración:** Si no existen cuentas en la base de datos, se abre automáticamente un modal a pantalla completa para que el administrador configure su nombre de usuario y una contraseña segura.
- **Bypass Headless Docker (Opcional):** Para despliegues automatizados, puede definir las variables de entorno `ADMIN_USER` y `ADMIN_PASSWORD` en `.env` o `docker-compose.yml`. En el primer inicio se creará el usuario administrador omitiendo el asistente.
- **Roles y Permisos Granulares (RBAC):** Desde la sección *Ajustes -> Gestión de Usuarios y Permisos*, el administrador puede crear cuentas adicionales con roles específicos (`Admin`, `Operator`, `Viewer`) y ajustar permisos operativos.

#### 2. Autenticación con la Nube eero (2FA OTP)
Una vez completado el acceso local (o si la autenticación local no es requerida):
1. **Solicitud del Código OTP:** Introduzca el correo o número de teléfono asociado a su cuenta eero y pulse **"Enviar Código OTP"**.
2. **Verificación del Código:** Introduzca el código numérico de 6 dígitos recibido por SMS o correo y confirme.
3. **Guardado de Sesión:** El token verificado se almacena en `/app/data/session.json` con permisos restrictivos `0600`, persistiendo tras los reinicios del contenedor.
4. **Modo Demo y Cambio Rápido:** Active el modo demostración mediante el botón dedicado o la variable `DEMO_MODE=true` para explorar todas las funciones sin credenciales reales.

#### 3. Autenticación Nativa Amazon OAuth2 / PKCE
Para cuentas de eero vinculadas a un perfil de Amazon, el panel integra el flujo federado oficial **Amazon OAuth2 con PKCE S256 (RFC 7636)**:
1. **Acceso con Amazon:** Pulse en **"🛒 Iniciar sesión con Amazon"** en el modal de inicio para iniciar el flujo seguro PKCE.
2. **Autorización en el Navegador:** Inicie sesión en Amazon y conceda los permisos; al finalizar será redirigido a la URL oficial `/ap/maplanding`.
3. **Vinculación Inmediata:** Copie la URL de redirección o el parámetro `code`, péguelo en el campo correspondiente del panel y confirme con **"Vincular cuenta eero"**.

#### 4. Seguridad Global y Aplicación de `REQUIRE_LOCAL_AUTH`
Para redes compartidas o entornos expuestos, definir `REQUIRE_LOCAL_AUTH=true` en `.env`:
- Protege todas las rutas de la API (`/api/*`) y las métricas de Prometheus (`/metrics`) exigiendo una sesión de usuario válida.
- Solo las rutas indispensables de verificación de estado e inicio de sesión (`/api/health`, `/api/auth/local/*`, `/api/system/language`) permanecen públicas.
