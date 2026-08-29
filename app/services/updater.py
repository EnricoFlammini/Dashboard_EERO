import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_REPO = "EnricoFlammini/Dashboard_EERO"
DOCKER_IMAGE = "enricoflammini/eero-dashboard"


def parse_semver(v: str) -> Tuple[int, int, int]:
    """Estrae la tupla (major, minor, patch) da stringhe di versione come 'v1.04.00', '1.3.1', '1.04.00-dev'."""
    clean = re.sub(r'^[vV]', '', str(v).strip())
    parts = re.split(r'[-+.]', clean)
    numbers = []
    for p in parts:
        if p.isdigit():
            numbers.append(int(p))
        if len(numbers) == 3:
            break
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


def is_newer_version(current: str, remote: str) -> bool:
    """Verifica se la versione remota è strettamente maggiore della versione corrente."""
    return parse_semver(remote) > parse_semver(current)


class UpdaterService:
    """Gestisce il rilevamento e l'installazione automatica delle nuove release dell'applicazione."""

    def __init__(self):
        self._cached_update_info: Optional[Dict[str, Any]] = None
        self._last_check_time: Optional[datetime] = None
        self._is_updating: bool = False

    @property
    def is_docker_socket_available(self) -> bool:
        """Verifica se il socket del daemon Docker è montato e accessibile nel container."""
        sock_path = Path(settings.docker_socket_path)
        return sock_path.exists() and os.access(sock_path, os.R_OK | os.W_OK)

    @property
    def is_watchtower_configured(self) -> bool:
        """Verifica se è configurato un webhook URL per Watchtower."""
        return bool(settings.watchtower_url and settings.watchtower_url.startswith("http"))

    async def check_for_updates(self, force: bool = False) -> Dict[str, Any]:
        """Interroga GitHub Releases e Docker Hub per verificare la disponibilità di una nuova versione."""
        now = datetime.now(timezone.utc)
        
        # Usa la cache in memoria se non è forzato e non sono passate le ore di intervallo
        if not force and self._cached_update_info and self._last_check_time:
            elapsed = (now - self._last_check_time).total_seconds()
            if elapsed < (settings.update_check_interval_hours * 3600):
                return self._cached_update_info

        current_ver = settings.app_version
        latest_ver = current_ver
        release_title = f"v{current_ver}"
        release_notes = ""
        published_at = ""
        html_url = f"https://github.com/{GITHUB_REPO}/releases"

        # 1. Interroga GitHub Releases API
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": f"eero-dashboard/{current_ver}"}
                resp = await client.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    tag_name = data.get("tag_name", "")
                    clean_tag = tag_name.lstrip("vV")
                    if clean_tag:
                        latest_ver = clean_tag
                        release_title = data.get("name") or tag_name
                        release_notes = data.get("body") or ""
                        published_at = data.get("published_at") or ""
                        html_url = data.get("html_url") or html_url
        except Exception as e:
            logger.warning(f"Error checking GitHub Releases: {e}")

        # 2. Fallback: Se GitHub non ha risposto, prova Docker Hub Tags API
        if latest_ver == current_ver:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"https://hub.docker.com/v2/repositories/{DOCKER_IMAGE}/tags?page_size=10")
                    if resp.status_code == 200:
                        data = resp.json()
                        for tag_obj in data.get("results", []):
                            t_name = tag_obj.get("name", "")
                            if t_name and t_name != "latest" and t_name[0].isdigit():
                                if is_newer_version(latest_ver, t_name):
                                    latest_ver = t_name.lstrip("vV")
                                    published_at = tag_obj.get("last_updated", "")
            except Exception as e:
                logger.warning(f"Error checking Docker Hub: {e}")

        update_avail = is_newer_version(current_ver, latest_ver)
        docker_sock = self.is_docker_socket_available
        watchtower = self.is_watchtower_configured
        can_auto = bool(docker_sock or watchtower)

        result = {
            "status": "success",
            "current_version": current_ver,
            "latest_version": latest_ver,
            "update_available": update_avail,
            "release_title": release_title,
            "release_notes": release_notes,
            "published_at": published_at,
            "release_url": html_url,
            "docker_image": f"{DOCKER_IMAGE}:latest",
            "docker_socket_available": docker_sock,
            "watchtower_configured": watchtower,
            "can_auto_install": can_auto,
            "cli_command": "docker compose pull && docker compose up -d",
            "checked_at": now.isoformat()
        }

        self._cached_update_info = result
        self._last_check_time = now
        logger.info(f"Update check completed: current={current_ver}, latest={latest_ver}, update_available={update_avail}")
        return result

    async def trigger_update(self) -> Dict[str, Any]:
        """Esegue l'aggiornamento automatico del container Docker tramite Docker Socket o Watchtower."""
        if self._is_updating:
            return {
                "success": True,
                "status": "in_progress",
                "message": "Un aggiornamento è già in corso..."
            }

        # 1. Se configurato Watchtower Webhook
        if self.is_watchtower_configured:
            try:
                self._is_updating = True
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(settings.watchtower_url)
                    if resp.status_code in (200, 204):
                        return {
                            "success": True,
                            "method": "watchtower",
                            "message": "Segnale di aggiornamento inviato con successo a Watchtower. Il container si riavvierà a breve."
                        }
                    else:
                        raise RuntimeError(f"Watchtower ha risposto con codice {resp.status_code}: {resp.text}")
            except Exception as ex:
                self._is_updating = False
                logger.error(f"Errore trigger Watchtower: {ex}")
                raise RuntimeError(f"Errore trigger Watchtower: {ex}")

        # 2. Se è montato il Docker Socket (/var/run/docker.sock)
        if self.is_docker_socket_available:
            self._is_updating = True
            sock_path = settings.docker_socket_path
            logger.info(f"Avvio auto-update tramite Docker Socket: {sock_path}")
            
            # Esegui in background il pull e il recreate
            asyncio.create_task(self._perform_docker_socket_update(sock_path))
            
            return {
                "success": True,
                "method": "docker_socket",
                "message": "Aggiornamento avviato: download della nuova immagine Docker in corso. L'applicazione si riavvierà automaticamente."
            }

        # 3. Modalità assistita se nessun metodo automatico è disponibile
        return {
            "success": False,
            "method": "manual",
            "message": "Nessun Docker Socket o Watchtower configurato. Esegui il comando 'docker compose pull && docker compose up -d' sul server.",
            "cli_command": "docker compose pull && docker compose up -d"
        }

    async def _perform_docker_socket_update(self, sock_path: str):
        """Esegue il pull della nuova immagine Docker e invia il comando di restart al Docker Daemon."""
        try:
            transport = httpx.AsyncHTTPTransport(uds=sock_path)
            async with httpx.AsyncClient(transport=transport, timeout=180.0, base_url="http://docker") as client:
                # 1. Pull immagine latest da Docker Hub
                pull_url = f"/images/create?fromImage={DOCKER_IMAGE}&tag=latest"
                logger.info(f"Docker API pull: {pull_url}")
                pull_resp = await client.post(pull_url)
                if pull_resp.status_code != 200:
                    logger.error(f"Docker pull fallito ({pull_resp.status_code}): {pull_resp.text}")
                    return

                logger.info("Docker image pull completato con successo. Segnalazione restart...")
                await asyncio.sleep(2.0)
                
                # 2. Invia segnale di restart al container corrente
                hostname = os.getenv("HOSTNAME", "")
                if hostname:
                    try:
                        await client.post(f"/containers/{hostname}/restart?t=5")
                        logger.info(f"Container {hostname} restarted via Docker Socket.")
                    except Exception as e:
                        logger.warning(f"Could not restart container by hostname: {e}")
        except Exception as ex:
            logger.error(f"Errore durante l'aggiornamento via Docker Socket: {ex}")
        finally:
            self._is_updating = False


updater_service = UpdaterService()
