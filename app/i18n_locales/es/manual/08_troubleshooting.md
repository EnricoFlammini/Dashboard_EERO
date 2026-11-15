---
id: troubleshooting
title: 8. Resolución de Problemas, Actualizaciones y FAQ
icon: wrench
summary: Preguntas frecuentes sobre telemetría, actualización automática Docker, seguridad, copias y mantenimiento.
---
### Preguntas Frecuentes y Resolución de Incidencias

* **¿Cómo funciona la actualización automática de Docker en la aplicación?**
  - La suite comprueba regularmente nuevas versiones en Docker Hub y GitHub Releases.
  - Si el socket de Docker (`/var/run/docker.sock`) está montado, pulsar en **"Actualizar Contenedor Ahora"** descarga la nueva imagen y recrea el contenedor manteniendo el volumen `./data`.
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
