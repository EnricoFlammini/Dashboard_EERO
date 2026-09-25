import asyncio
import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.db import db_service
from app.services.eero_client import eero_client

logger = logging.getLogger(__name__)

PRIMARY_ZENDESK_URL = "https://eero.zendesk.com/api/v2/help_center/en-us/articles/209636523.json"
FALLBACK_ZENDESK_URL = "https://support.eero.com/api/v2/help_center/en-us/articles/209636523.json"
REDDIT_COMMUNITY_URL = (
    "https://www.reddit.com/r/amazoneero/search.json?q=flair%3AUpdate+OR+%22release+notes%22&sort=new&limit=5"
)
CACHE_TTL_SECONDS = 6 * 3600  # 6 ore di cache


def parse_eero_version(ver_str: Optional[str]) -> Tuple[int, int, int, int]:
    """Converte una stringa di versione eeroOS (es. 'v7.16.0-9483', 'v7.17.1-24' o '7.5.2-192') in una tupla confrontabile.

    Ritorna: (major, minor, patch, build)
    """
    if not ver_str:
        return (0, 0, 0, 0)
    clean = ver_str.strip().lstrip("vV")
    # Formato tipico: X.Y.Z-BUILD o X.Y.Z o X.Y-BUILD (supporta separatori standard '-' o '.')
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[-.bB]+(\d+))?", clean)
    if not match:
        return (0, 0, 0, 0)
    major = int(match.group(1) or 0)
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    build = int(match.group(4) or 0)
    return (major, minor, patch, build)


def compare_eero_versions(v1: Optional[str], v2: Optional[str]) -> int:
    """Confronta numericamente due versioni eeroOS (major, minor, patch, build).

    Ritorna:
      1 se v1 > v2
      0 se v1 == v2
     -1 se v1 < v2
    """
    t1 = parse_eero_version(v1)
    t2 = parse_eero_version(v2)
    if t1 > t2:
        return 1
    elif t1 < t2:
        return -1
    return 0


def is_newer_eero_version(target_ver: str, base_ver: str) -> bool:
    """Verifica se target_ver è strettamente più recente di base_ver."""
    return compare_eero_versions(target_ver, base_ver) > 0


def compute_firmware_alignment(
    current_firmware: str,
    latest_official_firmware: str,
    pending_api_target: Optional[str] = None,
) -> Dict[str, Any]:
    """Calcola in modo rigoroso e mutualmente esclusivo lo stato del firmware della flotta.

    Stati possibili (firmware_status):
      - 'up_to_date': la flotta esegue esattamente l'ultima versione ufficiale censita
      - 'newer_than_published': la versione installata è più recente di quella pubblicata
                                sull'articolo di supporto Zendesk (tipico early-rollout eero)
      - 'update_available': è disponibile un aggiornamento firmware target pendente o
                            la flotta è indietro rispetto all'ultima versione ufficiale censita
    """
    curr_tuple = parse_eero_version(current_firmware)
    latest_tuple = parse_eero_version(latest_official_firmware)

    # 1. Verifica se le API eero segnalano un target_firmware pendente valido e strettamente più recente
    valid_pending_target = None
    if pending_api_target and is_newer_eero_version(pending_api_target, current_firmware):
        valid_pending_target = pending_api_target

    # 2. Decisione dello stato mutualmente esclusivo:
    if valid_pending_target:
        return {
            "is_up_to_date": False,
            "update_available": True,
            "firmware_status": "update_available",
            "target_firmware": valid_pending_target,
        }

    if is_newer_eero_version(latest_official_firmware, current_firmware):
        return {
            "is_up_to_date": False,
            "update_available": True,
            "firmware_status": "update_available",
            "target_firmware": latest_official_firmware,
        }

    # Se arriviamo qui, current_firmware >= latest_official_firmware
    # Non ci sono aggiornamenti disponibili: la flotta è aggiornata.
    if curr_tuple > latest_tuple and latest_tuple > (0, 0, 0, 0):
        return {
            "is_up_to_date": True,
            "update_available": False,
            "firmware_status": "newer_than_published",
            "target_firmware": None,
        }
    else:
        return {
            "is_up_to_date": True,
            "update_available": False,
            "firmware_status": "up_to_date",
            "target_firmware": None,
        }


class EeroNewsService:
    """Servizio autonomo per il recupero, parsing e gestione delle note di rilascio eeroOS

    e dei feedback della community, con persistenza SQLite e correlazione firmware locale.
    """

    def __init__(self):
        self._last_fetched: Optional[datetime] = None
        self._cached_community_posts: List[Dict[str, Any]] = []
        self._last_community_fetch: Optional[datetime] = None
        self._is_fetching: bool = False

    def parse_zendesk_html(self, html_body: str) -> List[Dict[str, Any]]:
        """Esegue il parsing strutturato dell'HTML dell'articolo Zendesk delle release notes eero."""
        if not html_body:
            return []

        # Normalizza caratteri non standard o artefatti di codifica
        cleaned_body = (
            html_body.replace("\ufffd", "'")
            .replace("&rsquo;", "'")
            .replace("&lsquo;", "'")
            .replace("&ldquo;", '"')
            .replace("&rdquo;", '"')
        )

        pattern = re.compile(
            r"eeroOS:?\s*(v[0-9]+(?:\.[0-9]+)+(?:-[0-9]+)?).*?Released\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        )
        matches = list(pattern.finditer(cleaned_body))
        if not matches:
            # Fallback pattern più permissivo per date formattate diversamente
            pattern_fallback = re.compile(
                r"eeroOS:?\s*(v[0-9]+(?:\.[0-9]+)+(?:-[0-9]+)?).*?Released\s+([A-Za-z0-9, ]+?)(?:<|\n)",
                re.IGNORECASE,
            )
            matches = list(pattern_fallback.finditer(cleaned_body))

        releases: List[Dict[str, Any]] = []
        for i, m in enumerate(matches):
            version = m.group(1).strip()
            release_date = m.group(2).strip()

            start_pos = m.end()
            end_pos = matches[i + 1].start() if (i + 1 < len(matches)) else len(cleaned_body)
            section_html = cleaned_body[start_pos:end_pos]

            # Estrazione dei bullet point (tag <li>)
            raw_bullets = re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL)
            bullets: List[str] = []
            for b in raw_bullets:
                clean_text = re.sub(r"<[^>]+>", "", b).strip()
                clean_text = html.unescape(clean_text)
                # Pulisce spazi multipli
                clean_text = re.sub(r"\s+", " ", clean_text)
                if clean_text:
                    bullets.append(clean_text)

            # Se non ci sono <li>, cerca paragrafi di testo nella sezione
            if not bullets:
                raw_paras = re.findall(r"<p[^>]*>(.*?)</p>", section_html, re.DOTALL)
                for p in raw_paras:
                    clean_p = re.sub(r"<[^>]+>", "", p).strip()
                    clean_p = html.unescape(clean_p)
                    clean_p = re.sub(r"\s+", " ", clean_p)
                    if clean_p and not clean_p.lower().startswith("eeroos"):
                        bullets.append(clean_p)

            # Rilevamento tag e patch di sicurezza
            full_text = " ".join(bullets).lower()
            is_security = "security" in full_text or "sicurezza" in full_text
            tags: List[str] = []

            if is_security:
                tags.append("Sicurezza")
            if any(k in full_text for k in ("wi-fi 7", "wifi 7", "6 ghz", "6ghz", "truechannel", "awgn")):
                tags.append("Wi-Fi 7 / 6 GHz")
            if any(k in full_text for k in ("stability", "crash", "reboot", "disconnection", "stabilità")):
                tags.append("Stabilità")
            if any(k in full_text for k in ("performance", "throughput", "latency", "velocità", "prestazioni")):
                tags.append("Prestazioni")
            if any(k in full_text for k in ("thread", "matter", "zigbee", "smart home", "iot")):
                tags.append("Smart Home")

            summary = bullets[0] if bullets else "Aggiornamento firmware eeroOS"

            releases.append(
                {
                    "version": version,
                    "release_date": release_date,
                    "title": f"eeroOS: {version}",
                    "summary": summary,
                    "content": bullets,
                    "tags": tags,
                    "is_security_patch": is_security,
                }
            )

        return releases

    async def fetch_official_release_notes(self, force: bool = False) -> List[Dict[str, Any]]:
        """Recupera le release notes dall'API pubblica Zendesk e le persiste su SQLite."""
        # Se siamo in demo mode o se non forzato e cache recente
        now = datetime.now(timezone.utc)
        if not force and self._last_fetched:
            elapsed = (now - self._last_fetched).total_seconds()
            if elapsed < CACHE_TTL_SECONDS:
                cached = await db_service.get_release_notes(limit=100)
                if cached:
                    return cached

        # Se in Demo Mode, popola con mock realistici se assenti
        if settings.demo_mode or eero_client.is_demo_mode:
            demo_notes = self._get_demo_releases()
            await db_service.save_release_notes(demo_notes)
            self._last_fetched = now
            return demo_notes

        # In Live Mode: Chiamata HTTP asincrona all'endpoint pubblico Zendesk
        html_body: Optional[str] = None
        urls_to_try = [PRIMARY_ZENDESK_URL, FALLBACK_ZENDESK_URL]

        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers={"User-Agent": "eero-dashboard/1.6.0"}
        ) as client:
            for url in urls_to_try:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        article = data.get("article", {})
                        html_body = article.get("body", "")
                        if html_body:
                            logger.info(f"Successfully fetched eero release notes from {url}")
                            break
                    else:
                        logger.warning(f"Zendesk API {url} returned status {resp.status_code}")
                except Exception as ex:
                    logger.warning(f"Error connecting to eero Zendesk API at {url}: {ex}")

        # Se il recupero remoto ha avuto successo
        if html_body:
            releases = self.parse_zendesk_html(html_body)
            if releases:
                await db_service.save_release_notes(releases)
                self._last_fetched = now
                logger.info(f"Persisted {len(releases)} eero release notes to SQLite.")
                return releases

        # Fallback se la connessione fallisce o offline: recupera dalla cache SQLite esistente
        cached = await db_service.get_release_notes(limit=100)
        if cached:
            logger.info("Using cached eero release notes from SQLite after remote fetch failure.")
            return cached

        # Se anche il DB è vuoto (es. primo avvio offline), carica i dati di default
        default_notes = self._get_demo_releases()
        await db_service.save_release_notes(default_notes)
        self._last_fetched = now
        return default_notes

    async def fetch_community_feedback(self) -> List[Dict[str, Any]]:
        """Recupera in modo asincrono gli ultimi thread di discussione da Reddit r/amazoneero."""
        now = datetime.now(timezone.utc)
        if self._cached_community_posts and self._last_community_fetch:
            elapsed = (now - self._last_community_fetch).total_seconds()
            if elapsed < 3600:  # 1 ora di cache per i feedback community
                return self._cached_community_posts

        # Se in demo mode
        if settings.demo_mode or eero_client.is_demo_mode:
            posts = self._get_demo_community_posts()
            self._cached_community_posts = posts
            self._last_community_fetch = now
            return posts

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                resp = await client.get(REDDIT_COMMUNITY_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    posts = []
                    for item in children[:5]:
                        post_data = item.get("data", {})
                        posts.append(
                            {
                                "id": post_data.get("id"),
                                "title": post_data.get("title", ""),
                                "author": post_data.get("author", "redditor"),
                                "url": f"https://reddit.com{post_data.get('permalink', '')}"
                                if post_data.get("permalink")
                                else "",
                                "score": post_data.get("score", 0),
                                "num_comments": post_data.get("num_comments", 0),
                                "created_utc": post_data.get("created_utc"),
                                "flair": post_data.get("link_flair_text", "Update"),
                            }
                        )
                    if posts:
                        self._cached_community_posts = posts
                        self._last_community_fetch = now
                        return posts
        except Exception as e:
            logger.debug(f"Reddit community fetch fallback: {e}")

        # Se la chiamata a Reddit è bloccata (403) o timeout, restituisce post curati/fallback
        posts = self._get_demo_community_posts()
        self._cached_community_posts = posts
        self._last_community_fetch = now
        return posts

    async def get_news_summary(self, force: bool = False) -> Dict[str, Any]:
        """Restituisce il riepilogo completo: release ufficiali, stato di allineamento della rete,

        versione installata vs target firmware e feedback community.
        """
        # 1. Recupero note di rilascio
        releases = await self.fetch_official_release_notes(force=force)

        # 2. Informazioni firmware dei nodi locali
        eeros_list: List[Dict[str, Any]] = []
        try:
            # Prova prima dai nodi in cache del background poller per latenza 0
            from app.services.poller import background_poller

            if background_poller and background_poller.cached_eeros:
                eeros_list = background_poller.cached_eeros
            else:
                eeros_list = await eero_client.get_eeros()
        except Exception as ex:
            logger.warning(f"Unable to read mesh nodes firmware: {ex}")
            eeros_list = []

        nodes_summary = []
        gateway_version = None
        for node in eeros_list:
            os_ver = node.get("os_version") or "Sconosciuta"
            is_gw = node.get("is_gateway", False)
            if is_gw and not gateway_version:
                gateway_version = os_ver
            nodes_summary.append(
                {
                    "id": node.get("id"),
                    "name": node.get("name") or node.get("model") or "eero Node",
                    "model": node.get("model", ""),
                    "os_version": os_ver,
                    "is_gateway": is_gw,
                    "wired": node.get("wired", False),
                    "status": node.get("status", "online"),
                }
            )

        # Versione attualmente in esecuzione
        current_firmware = gateway_version or (nodes_summary[0]["os_version"] if nodes_summary else "v7.5.2-192")

        # Ultima release ufficiale censita
        latest_release = releases[0] if releases else None
        latest_firmware = latest_release.get("version") if latest_release else current_firmware

        # Verifica target update pendente dalle API eero
        pending_target_firmware = None
        try:
            updates_data = await eero_client.get_network_updates()
            if updates_data:
                if updates_data.get("has_update") or updates_data.get("target_firmware"):
                    pending_target_firmware = updates_data.get("target_firmware")
        except Exception:
            pass

        # Calcolo allineamento rigoroso e mutualmente esclusivo
        alignment = compute_firmware_alignment(
            current_firmware=current_firmware,
            latest_official_firmware=latest_firmware,
            pending_api_target=pending_target_firmware,
        )

        # 3. Community posts
        community_posts = await self.fetch_community_feedback()

        last_checked_iso = (
            self._last_fetched.isoformat()
            if self._last_fetched
            else datetime.now(timezone.utc).isoformat()
        )

        return {
            "status": "success",
            "firmware_status": alignment["firmware_status"],  # "up_to_date" | "update_available" | "newer_than_published"
            "current_firmware": current_firmware,
            "latest_firmware": latest_firmware,
            "is_up_to_date": alignment["is_up_to_date"],
            "update_available": alignment["update_available"],
            "target_firmware": alignment["target_firmware"],
            "nodes": nodes_summary,
            "releases": releases,
            "total_releases": len(releases),
            "community_posts": community_posts,
            "last_checked": last_checked_iso,
            "is_demo": bool(settings.demo_mode or eero_client.is_demo_mode),
        }

    def _get_demo_releases(self) -> List[Dict[str, Any]]:
        """Restituisce un set realistico e ricco di release notes eeroOS per la modalità Demo e test."""
        return [
            {
                "version": "v7.16.0-9483",
                "release_date": "July 21, 2026",
                "title": "eeroOS: v7.16.0-9483",
                "summary": "Migliorata la gestione TrueChannel delle interferenze AWGN su 6 GHz e ottimizzazioni stabilità.",
                "content": [
                    "Improved TrueChannel handling of Additive White Gaussian Noise (AWGN) interference on 6 GHz band",
                    "Performance and stability improvements for multi-node mesh backhaul",
                    "Security patches for core network stack",
                    "Update file size: up to 175 MB compressed (600 MB installed)",
                ],
                "tags": ["Sicurezza", "Wi-Fi 7 / 6 GHz", "Stabilità", "Prestazioni"],
                "is_security_patch": True,
            },
            {
                "version": "v7.15.1-119",
                "release_date": "June 19, 2026",
                "title": "eeroOS: v7.15.1-119",
                "summary": "Miglioramenti generali alle prestazioni e stabilità del mesh.",
                "content": [
                    "Performance and stability improvements across all eero 6 and 7 models",
                    "Resolved edge-case DHCP lease renewal delays on busy IoT segments",
                    "Update file size: up to 175 MB compressed (600 MB installed)",
                ],
                "tags": ["Stabilità", "Prestazioni"],
                "is_security_patch": False,
            },
            {
                "version": "v7.15.0-9714",
                "release_date": "May 28, 2026",
                "title": "eeroOS: v7.15.0-9714",
                "summary": "Miglioramento del client roaming advisor e gestione canali DFS.",
                "content": [
                    "Enhanced dynamic channel selection during radar detection on DFS channels",
                    "Improved client steering for Wi-Fi 6E/7 dual-band connected devices",
                    "Security enhancements and protocol robustness",
                    "Update file size: up to 180 MB compressed",
                ],
                "tags": ["Sicurezza", "Wi-Fi 7 / 6 GHz", "Stabilità"],
                "is_security_patch": True,
            },
            {
                "version": "v7.14.1-137",
                "release_date": "April 22, 2026",
                "title": "eeroOS: v7.14.1-137",
                "summary": "Miglioramenti di stabilità per eero Signal e sincronizzazione mesh.",
                "content": [
                    "Stability improvements for eero Signal metrics and mesh latency calculation",
                    "Refined band steering algorithm for legacy 2.4 GHz IoT sensors",
                    "Performance optimizations under heavy WAN load",
                ],
                "tags": ["Stabilità", "Prestazioni"],
                "is_security_patch": False,
            },
            {
                "version": "v7.5.2-192",
                "release_date": "September 15, 2024",
                "title": "eeroOS: v7.5.2-192",
                "summary": "Patch di sicurezza cumulativa e supporto esteso per i nodi eero Pro 6E.",
                "content": [
                    "Security, performance, and stability improvements",
                    "Fix for occasional packet retransmission on wired PoE backhauls",
                    "Optimized memory footprint for long uptimes",
                ],
                "tags": ["Sicurezza", "Stabilità"],
                "is_security_patch": True,
            },
        ]

    def _get_demo_community_posts(self) -> List[Dict[str, Any]]:
        """Restituisce discussioni realistiche della community r/amazoneero per demo e test."""
        return [
            {
                "id": "post_01",
                "title": "eeroOS v7.16.0 Rollout Experience - AWGN Fix and Wi-Fi 7 Stability",
                "author": "MeshExpert_Net",
                "url": "https://www.reddit.com/r/amazoneero/comments/eeroos_7_16_0_experience/",
                "score": 42,
                "num_comments": 19,
                "created_utc": 1784650000,
                "flair": "Update / eeroOS",
            },
            {
                "id": "post_02",
                "title": "v7.16.0 vs v7.15.1: 6 GHz throughput tests on eero Max 7 & Pro 6E",
                "author": "TechHomelabGuy",
                "url": "https://www.reddit.com/r/amazoneero/comments/v7_16_throughput_benchmarks/",
                "score": 35,
                "num_comments": 14,
                "created_utc": 1784560000,
                "flair": "Review / Benchmark",
            },
            {
                "id": "post_03",
                "title": "Anyone else noticing faster roaming on Apple devices with latest firmware?",
                "author": "CupertinoWifi",
                "url": "https://www.reddit.com/r/amazoneero/comments/fast_roaming_feedback/",
                "score": 28,
                "num_comments": 8,
                "created_utc": 1784400000,
                "flair": "Discussion",
            },
        ]


eero_news_service = EeroNewsService()
