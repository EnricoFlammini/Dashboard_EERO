---
id: troubleshooting
title: 8. Resolución de Problemas, Actualizaciones y FAQ
icon: wrench
summary: Preguntas frecuentes sobre telemetría, actualización automática Docker, seguridad, copias y mantenimiento.
---
### Preguntas Frecuentes y Resolución de Incidencias

* **¿Cómo actualizo el panel?**
  - El panel comprueba si hay nuevas versiones en Docker Hub y GitHub Releases y muestra un aviso de actualización cuando sale una.
  - Para actualizar, ejecuta `docker compose pull && docker compose up -d` en la carpeta que contiene tu `docker-compose.yml`. La carpeta `./data` se conserva.
  - En un NAS Synology, usa **Container Manager → Proyecto → Acción → Compilar**, o deja que el Programador de tareas de DSM lo actualice automáticamente. Consulta la [guía de Synology](https://github.com/EnricoFlammini/Dashboard_EERO/blob/main/deploy/synology/README.md).
  - El botón **Actualizar contenedor ahora (1 clic)** necesita el socket de Docker (`/var/run/docker.sock`) montado en el contenedor. Por ahora solo descarga la nueva imagen, así que ejecuta después el comando anterior para pasar a ella.
* **¿Qué información procede directamente de la infraestructura eero?**
  - Estado de conexión, dirección IP local, dirección MAC, nodo de conexión, banda Wi-Fi (**2.4 GHz, 5 GHz, 6 GHz o Cableado**), canal, nivel de señal en **dBm** y velocidad de enlace físico (**PHY Link Rate**).
* **Seguridad y Protección de Datos:**
  - **Protección CORS y CSRF:** Restricción de accesos cruzados por defecto y validación de peticiones mutantes.
  - **Saneamiento de Contraseñas Wi-Fi:** Las credenciales de red se excluyen automáticamente de los datos de vista pública.
  - **Permisos estrictos en session.json:** Creado con permisos `0600` accesibles exclusivamente por el proceso del contenedor.
* **¿Qué hacer si la sesión con eero caduca?**
  - Pulse en **Cerrar Sesión** en la barra lateral y repita el proceso de autenticación (SMS, correo o Amazon OAuth2).
* **¿Cómo realizar una copia de seguridad de la configuración local?**
  - Toda la información personalizada (nombres, categorías, notas, historial, reglas) reside en `./data/metrics.db`. Basta con respaldar la carpeta `./data`.
* **¿Por qué el inicio por SMS/correo falla con error 401?**
  - Si su cuenta de eero está vinculada a Amazon, utilice la opción **"Iniciar sesión con Amazon (OAuth2 / PKCE)"** en el diálogo de acceso.
* **¿Cómo configurar Custom y Split DNS?**
  - Configure las variables `CUSTOM_DNS_SERVERS` y `CUSTOM_DNS_DOMAINS` para resolver dominios locales mediante sus servidores DNS internos.
* **¿Cómo actúa la autorreparación de SQLite?**
  - En caso de corrupción por apagado imprevisto, el motor ejecuta una recuperación en 3 fases (`REINDEX`, recreación de tablas, volcado y reconstrucción) generando un archivo `.corrupt.bak`.
