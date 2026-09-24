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
    """Estrae la tupla (major, minor, patch) da stringhe di versione come 'v1.4.0', '1.3.1', '1.4.0-dev'."""
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


def parse_version_and_build(v: str) -> Tuple[int, int, int, int]:
    """
    Estrae la tupla (major, minor, patch, build) da stringhe di versione come:
    '1.5.0', '1.5.0 build 1', 'v1.5.0-build.1', '1.5.0-build1', '1.5.0-build.2'.
    """
    clean = str(v).strip().lstrip("vV")
    build_num = 0
    build_match = re.search(r'[-_\s.]*(?:build|b)[-_\s.]*(\d+)', clean, re.IGNORECASE)
    if build_match:
        try:
            build_num = int(build_match.group(1))
        except ValueError:
            build_num = 0
        clean = clean[:build_match.start()]

    parts = re.findall(r'\b\d+\b', clean)
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0

    return (major, minor, patch, build_num)


def is_newer_version(current: str, remote: str) -> bool:
    """Verifica se la versione remota (comprensiva di build) è strettamente maggiore della versione corrente."""
    cur_p = parse_version_and_build(current)
    rem_p = parse_version_and_build(remote)

    if rem_p[:3] > cur_p[:3]:
        return True
    if rem_p[:3] == cur_p[:3]:
        return rem_p[3] > cur_p[3]
    return False


def extract_release_notes_from_changelog(version: str) -> str:
    """Estrae le note di rilascio dal changelog se disponibili."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "changelog.md",
        Path("/app/changelog.md"),
        Path("changelog.md")
    ]
    clean = version.lstrip("vV")
    pattern = rf"##\s*\[?v?{re.escape(clean)}\]?[^\r\n]*\r?\n(.*?)(?=\r?\n##|\Z)"
    for p in candidates:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(1).strip()
            except Exception:
                pass
    return ""


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
        current_build = settings.build_number
        current_full = settings.full_version

        latest_ver = current_ver
        latest_build = current_build
        latest_full_ver = current_full
        release_title = f"v{current_full}"
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
                        p_gh = parse_version_and_build(clean_tag)
                        if p_gh[:3] > parse_version_and_build(latest_full_ver)[:3]:
                            latest_ver = f"{p_gh[0]}.{p_gh[1]}.{p_gh[2]}"
                            latest_build = str(p_gh[3]) if p_gh[3] > 0 else "1"
                            latest_full_ver = f"{latest_ver} build {latest_build}"
                        release_title = data.get("name") or tag_name
                        release_notes = data.get("body") or ""
                        published_at = data.get("published_at") or ""
                        html_url = data.get("html_url") or html_url
        except Exception as e:
            logger.warning(f"Error checking GitHub Releases: {e}")

        # 2. Interroga sempre anche Docker Hub Tags API per identificare l'effettiva immagine Docker più recente
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://hub.docker.com/v2/repositories/{DOCKER_IMAGE}/tags?page_size=50")
                if resp.status_code == 200:
                    data = resp.json()
                    best_candidate = None
                    best_tag_obj = None

                    for tag_obj in data.get("results", []):
                        t_name = tag_obj.get("name", "")
                        # Salta 'latest', tag di test e main branch
                        if not t_name or t_name == "latest" or "test" in t_name.lower() or t_name == "main":
                            continue
                        parsed = parse_version_and_build(t_name)
                        if parsed[0] == 0 and parsed[1] == 0 and parsed[2] == 0:
                            continue
                        # Salta numeri di run legacy non isolati (>= 90)
                        if parsed[3] >= 90:
                            continue

                        if best_candidate is None or parsed > best_candidate:
                            best_candidate = parsed
                            best_tag_obj = tag_obj

                    if best_candidate:
                        b_maj, b_min, b_pat, b_bld = best_candidate
                        cand_ver = f"{b_maj}.{b_min}.{b_pat}"
                        cand_bld = str(b_bld) if b_bld > 0 else "1"
                        cand_full = f"{cand_ver} build {cand_bld}"

                        # Se è maggiore o uguale alla release attuale, adotta questo tag Docker
                        if best_candidate >= parse_version_and_build(latest_full_ver):
                            latest_ver = cand_ver
                            latest_build = cand_bld
                            latest_full_ver = cand_full
                            if best_tag_obj:
                                published_at = best_tag_obj.get("last_updated", "")
                            release_title = f"v{latest_full_ver}"
                            local_notes = extract_release_notes_from_changelog(cand_ver)
                            if local_notes:
                                release_notes = local_notes
                            else:
                                release_notes = f"Release v{latest_full_ver} pubblicata su Docker Hub ({DOCKER_IMAGE}:{best_tag_obj.get('name') if best_tag_obj else 'latest'})."
        except Exception as e:
            logger.warning(f"Error checking Docker Hub: {e}")

        update_avail = is_newer_version(current_full, latest_full_ver)
        docker_sock = self.is_docker_socket_available
        watchtower = self.is_watchtower_configured
        can_auto = bool(docker_sock or watchtower)

        result = {
            "status": "success",
            "current_version": current_ver,
            "build_number": current_build,
            "full_version": current_full,
            "latest_version": latest_ver,
            "latest_build_number": latest_build,
            "latest_full_version": latest_full_ver,
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
