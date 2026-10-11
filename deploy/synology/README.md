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
3. Set `TZ` to your timezone (e.g. `Europe/Rome`, `America/New_York`). Change `/volume1` if
   your `docker` shared folder is on another volume.
4. Skip the Web Station portal step and click **Done**.
5. Open `http://<NAS-IP>:8085` and complete the setup wizard.

The SQLite database and eero session are stored in `/volume1/docker/eero-dashboard/data`.
Include that folder in Hyper Backup.

## Updates

The compose file sets `pull_policy: always`, so the image is checked against Docker Hub every
time the project is brought up. What that covers:

| Action | Pulls a new image? |
| --- | --- |
| **Project → eero-dashboard → Action → Build** | Yes, and recreates the container |
| **Project → eero-dashboard → Stop**, then **Start** | Yes |
| **Container → eero_custom_dashboard → Restart** | No, restarts the existing container |
| NAS reboot (the `restart: unless-stopped` policy) | No, restarts the existing container |

To update manually, use **Action → Build** (or Stop then Start on the project). Your data
folder is kept.

### Automatic updates (after reboots and on a schedule)

A container restart can't pull an image, so add a DSM task that runs the project's compose
file. Go to **Control Panel → Task Scheduler → Create → Triggered Task → User-defined script**:

- **User:** `root`
- **Event:** *Boot-up*
- **Run command:**

  ```sh
  sleep 60
  cd /volume1/docker/eero-dashboard && \
    docker compose -p eero-dashboard pull && \
    docker compose -p eero-dashboard up -d && \
    docker image prune -f
  ```

To also pick up new releases while the NAS stays on, create a **Scheduled Task → User-defined
script** with the same command (minus the `sleep 60`), running daily at a quiet hour.

- `-p eero-dashboard` must match the Container Manager project name. Without it, compose
  derives a different project name from the folder and fails on the `container_name` clash.
- `up -d` only recreates the container when the image actually changed, so the task is safe
  to run often.
- `docker image prune -f` removes the old, now-untagged image layers.
- `sleep 60` gives Container Manager time to start Docker after boot.

## Notes

- `DATA_DIR=/app/data` is the path *inside* the container. Don't change it to a `/volume1` path.
- The healthcheck uses `localhost:8000` inside the container. It doesn't need the NAS IP.
- The in-app 1-click update needs `/var/run/docker.sock` mounted, which gives the container
  control over every container on the NAS. This file doesn't mount it; the Task Scheduler job
  above is the safer way to stay current.
- `mem_limit: 512m` caps the container's memory. Raise it if you keep a long history.
