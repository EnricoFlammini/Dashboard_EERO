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

There are three ways to update. All of them keep your data folder.

| Method | Effort | When to use |
| --- | --- | --- |
| [Update now](#update-now) | One click in Container Manager | You saw the update badge in the dashboard |
| [Automatic updates](#automatic-updates) | Set up once in Task Scheduler | You want the NAS to stay current on its own (recommended) |
| [In-app button](#the-in-app-update-button) | Not supported on Synology yet | See the note in that section |

Take a Hyper Backup of `docker/eero-dashboard/data` before moving to a new minor version
(for example 1.7 to 1.8). The new version may upgrade the database when it starts.

### Update now

The compose file sets `pull_policy: always`, so Docker Hub is checked for a newer image every
time the project is brought up:

| Action | Pulls a new image? |
| --- | --- |
| **Project → eero-dashboard → Action → Build** | Yes, and recreates the container |
| **Project → eero-dashboard → Stop**, then **Start** | Yes |
| **Container → eero_custom_dashboard → Restart** | No, restarts the existing container |
| NAS reboot (the `restart: unless-stopped` policy) | No, restarts the existing container |

To update, open **Container Manager → Project → eero-dashboard** and choose **Action → Build**.
The dashboard is unavailable for about a minute while the new container starts.

Container Manager may also show an "update available" notice for the
`enricoflammini/eero-dashboard:latest` image. Update through **Project → Action → Build**
rather than from the **Image** page, so the container is recreated from your compose file.

### Automatic updates

A container restart or a NAS reboot can't pull an image, so a DSM task does it instead. It
runs the same pull-and-recreate as **Action → Build**, but only replaces the container when a
new image is actually on Docker Hub. On other runs it changes nothing, so it's safe to run
often.

Create two tasks in **Control Panel → Task Scheduler**: one daily, and one at boot-up so
the NAS doesn't come back on an old image after it's been off for a while.

**Task 1: daily.** Choose **Create → Scheduled Task → User-defined script**.

- **General → Task:** `eero-dashboard update`
- **General → User:** `root`
- **Schedule:** *Run on the following days → Daily*, at a quiet hour (e.g. 04:00)
- **Task Settings → Run command:**

  ```sh
  cd /volume1/docker/eero-dashboard || exit 1
  {
    date
    docker compose -p eero-dashboard pull &&
    docker compose -p eero-dashboard up -d &&
    docker image prune -f
  } >> update.log 2>&1
  ```

**Task 2: at boot-up.** Choose **Create → Triggered Task → User-defined script**.

- **General → Task:** `eero-dashboard update at boot`
- **General → User:** `root`
- **General → Event:** *Boot-up*
- **Task Settings → Run command:** the same script with `sleep 60` as its first line. The
  pause gives Container Manager time to start Docker.

In both tasks, tick **Task Settings → Send run details by email** and **Send run details only
when the script terminates abnormally**. You'll then get an email only when an update fails
(this needs DSM email notifications set up in **Control Panel → Notification**).

To test a task, select it and click **Run**. Then check that it worked:

- `/volume1/docker/eero-dashboard/update.log` has a new entry, with the pull either reporting
  a newer image or saying the image is up to date.
- In the dashboard, the update badge clears and **About & Credits** in the sidebar shows the new version.

About the script:

- `-p eero-dashboard` must match the Container Manager project name. Without it, compose
  derives a different project name from the folder and fails on the `container_name` clash.
- `docker compose` finds the compose file Container Manager saved in the project folder, so
  no `-f` is needed.
- `docker image prune -f` removes old, untagged image layers. It applies to every project on
  the NAS, but only removes images no container uses.
- If the log says `docker: command not found`, replace `docker` with `/usr/local/bin/docker`.
- `update.log` grows by a few lines a day. Delete it whenever you like.

### Pin a version or roll back

`:latest` always follows the newest release. To stay on one release, or to go back after a
bad update, replace `latest` in the `image:` line with a version tag from
[Docker Hub](https://hub.docker.com/r/enricoflammini/eero-dashboard/tags), for example
`enricoflammini/eero-dashboard:1.7.0-build.5`. Edit the compose file in **Project →
eero-dashboard → YAML Configurations**, then **Action → Build**. While the tag is pinned,
the automatic updates above keep you on that version. Switch back to `latest` to resume them.

Going back to an older version after the database was upgraded may not work. Restore the
Hyper Backup of the data folder taken before the update.

### The in-app update button

When a new version is out, the dashboard shows an update badge. Its **Update Container Now (1-Click)**
button works only when the container can reach the Docker socket (`/var/run/docker.sock`).
This guide doesn't mount it, for two reasons:

- The socket gives the container root-level control of every container on the NAS.
- At the moment the button downloads the new image but leaves the running container on the
  old one, so you'd still need **Action → Build**.

Without the socket, the button shows the update command instead. On Synology, use
**Action → Build** or the automatic updates above.

## Notes

- `DATA_DIR=/app/data` is the path *inside* the container. Don't change it to a `/volume1` path.
- The healthcheck uses `localhost:8000` inside the container. It doesn't need the NAS IP.
- `mem_limit: 512m` caps the container's memory. Raise it if you keep a long history.
