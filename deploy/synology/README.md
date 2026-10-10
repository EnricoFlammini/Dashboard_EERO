# Synology NAS (Container Manager)

A ready-to-paste `docker-compose.yml` for Synology DSM 7.2+ **Container Manager**.
It pulls the published image from Docker Hub, so you don't need to clone the repo or build
anything on the NAS.

## Install

1. In **File Station**, create the folder `docker/eero-dashboard/data`.
   Container Manager refuses to start a project if a bind-mount folder is missing.
2. Open **Container Manager → Project → Create**:
   - **Project name:** `eero-dashboard`. Use lowercase only; Container Manager rejects
     uppercase.
   - **Path:** `/volume1/docker/eero-dashboard`
   - **Source:** *Create docker-compose.yml*, then paste [`docker-compose.yml`](docker-compose.yml).
3. Set `TZ` to your timezone. Change `/volume1` if your `docker` shared folder is on
   another volume.
4. Skip the Web Station portal step and click **Done**.
5. Open `http://<NAS-IP>:8085` and complete the setup wizard.

The SQLite database and eero session are stored in `/volume1/docker/eero-dashboard/data`.
Include that folder in Hyper Backup.

## Update

Go to **Container Manager → Project → eero-dashboard → Action → Build**. This pulls the latest
image and recreates the container. Your data folder is kept.

## Notes

- `DATA_DIR=/app/data` is the path *inside* the container. Don't change it to a `/volume1` path.
- The healthcheck uses `localhost:8000` inside the container. It doesn't need the NAS IP.
- The Docker socket mount for the 1-click in-app update is commented out. Mounting it gives the
  container control over every container on the NAS. Updating with **Action → Build** is the
  safer option.
