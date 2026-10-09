import asyncio
import ipaddress
import logging
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set
import httpx

from app.services.db import db_service

logger = logging.getLogger(__name__)

_IPV6_ULA_NET = ipaddress.IPv6Network("fc00::/7")
_IPV6_LL_NET = ipaddress.IPv6Network("fe80::/10")
_MAC_REGEX = re.compile(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")


def normalize_mac(mac: str) -> Optional[str]:
    """Normalizza un MAC address nel formato standard 'AA:BB:CC:DD:EE:FF'."""
    if not mac or not isinstance(mac, str):
        return None
    clean = re.sub(r"[^0-9a-fA-F]", "", mac.strip())
    if len(clean) != 12:
        return None
    return ":".join(clean[i:i + 2].upper() for i in range(0, 12, 2))


def classify_ip(ip_str: str) -> Dict[str, Any]:
    """
    Valida e classifica un indirizzo IP (IPv4 o IPv6).
    Restituisce un dizionario con { 'valid': bool, 'version': 4|6, 'type': 'ULA'|'GUA'|'Link-Local'|'IPv4'|'Unknown', 'normalized': str }.
    """
    if not ip_str or not isinstance(ip_str, str):
        return {"valid": False, "version": None, "type": "Invalid", "normalized": ""}

    clean = ip_str.strip()
    try:
        ip_obj = ipaddress.ip_address(clean)
        if ip_obj.version == 4:
            return {
                "valid": True,
                "version": 4,
                "type": "IPv4",
                "scope": "local" if ip_obj.is_private else "global",
                "normalized": str(ip_obj)
            }
        elif ip_obj.version == 6:
            if ip_obj.is_loopback or ip_obj.is_unspecified:
                return {"valid": False, "version": 6, "type": "Special", "normalized": str(ip_obj)}
            if ip_obj in _IPV6_LL_NET:
                return {"valid": True, "version": 6, "type": "Link-Local", "scope": "link", "normalized": str(ip_obj)}
            elif ip_obj in _IPV6_ULA_NET:
                return {"valid": True, "version": 6, "type": "ULA", "scope": "local", "normalized": str(ip_obj)}
            else:
                return {"valid": True, "version": 6, "type": "GUA", "scope": "global", "normalized": str(ip_obj)}
    except ValueError:
        pass

    return {"valid": False, "version": None, "type": "Invalid", "normalized": clean}


async def probe_ip(ip_str: str, timeout_sec: float = 1.0) -> None:
    """
    Invia un probe ICMPv6/ICMP ping asincrono a bassissimo impatto per forzare
    l'aggiornamento della tabella di vicinato (NDP / ARP cache) nel kernel.
    """
    clean_ip = ip_str.strip()
    is_win = sys.platform.startswith("win")
    
    try:
        if is_win:
            cmd = ["ping", "-n", "1", "-w", str(int(timeout_sec * 1000)), clean_ip]
        else:
            # Linux / Docker: usa ping o ping6
            cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_sec))), clean_ip]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec + 0.5)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"ICMP probe su {clean_ip} non riuscito: {e}")


async def resolve_mac_via_ndp(ip_str: str, probe_first: bool = True) -> Optional[str]:
    """
    Risolve il MAC address associato a un indirizzo IPv6/IPv4 ispezionando
    la tabella di vicinato (NDP) o ARP del sistema operativo.
    Funziona nativamente in container Docker con accesso host o bridge locale e su host Linux.
    """
    clean_info = classify_ip(ip_str)
    if not clean_info.get("valid"):
        return None

    clean_ip = clean_info["normalized"]

    if probe_first:
        await probe_ip(clean_ip)

    is_win = sys.platform.startswith("win")
    resolved_mac: Optional[str] = None

    if not is_win:
        # 1. Prova comando standard Linux: ip -6 neigh show <ip> (o ip neigh show <ip>)
        try:
            cmd = ["ip", "-6" if clean_info["version"] == 6 else "-4", "neigh", "show", clean_ip]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            text = out.decode("utf-8", errors="ignore")
            # Cerca pattern lladdr o MAC generico
            match = _MAC_REGEX.search(text)
            if match:
                resolved_mac = normalize_mac(match.group(0))
        except Exception as e:
            logger.debug(f"Errore esecuzione 'ip neigh' per {clean_ip}: {e}")

        # 2. Fallback su /proc/net/arp se IPv4
        if not resolved_mac and clean_info["version"] == 4 and os.path.exists("/proc/net/arp"):
            try:
                with open("/proc/net/arp", "r", encoding="utf-8") as f:
                    for line in f:
                        if clean_ip in line:
                            match = _MAC_REGEX.search(line)
                            if match:
                                resolved_mac = normalize_mac(match.group(0))
                                break
            except Exception:
                pass
    else:
        # Ambiente Windows (dev / testing locale)
        try:
            proc = await asyncio.create_subprocess_exec(
                "arp", "-a", clean_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            text = out.decode("utf-8", errors="ignore")
            match = _MAC_REGEX.search(text)
            if match:
                resolved_mac = normalize_mac(match.group(0))
        except Exception:
            pass

    return resolved_mac


class EnrichmentService:
    """
    Servizio di Reverse Client Enrichment per la gestione di indirizzi IPv6 ULA,
    scoperta via Neighbor Discovery Protocol (NDP) e sincronizzazione bidirezionale AdGuard Home.
    """

    async def ingest_neighbor_mappings(
        self,
        mappings: List[Dict[str, Any]],
        source: str = "api"
    ) -> Dict[str, Any]:
        """
        Valida, normalizza e inserisce un lotto di associazioni IP-MAC in SQLite.
        Aggiorna immediatamente in RAM lo stato dei dispositivi nella cache di background_poller.
        """
        if not mappings:
            return {"status": "success", "added": 0, "updated": 0, "total": 0, "valid_count": 0}

        valid_entries: List[Dict[str, Any]] = []
        errors: List[str] = []

        for idx, item in enumerate(mappings):
            raw_mac = item.get("mac") or item.get("mac_address")
            raw_ip = item.get("ip") or item.get("ip_address")
            
            clean_mac = normalize_mac(str(raw_mac or ""))
            if not clean_mac:
                errors.append(f"Elemento #{idx}: MAC address '{raw_mac}' non valido.")
                continue

            ip_info = classify_ip(str(raw_ip or ""))
            if not ip_info.get("valid"):
                errors.append(f"Elemento #{idx}: Indirizzo IP '{raw_ip}' non valido.")
                continue

            specified_type = str(item.get("ip_type") or item.get("type") or "").strip().upper()
            final_type = specified_type if specified_type in ("ULA", "GUA", "IPV4", "LINK-LOCAL") else ip_info["type"].upper()

            valid_entries.append({
                "mac": clean_mac,
                "ip": ip_info["normalized"],
                "ip_type": final_type,
                "source": str(item.get("source") or source).strip()
            })

        if not valid_entries:
            return {
                "status": "error",
                "message": "Nessuna associazione IP-MAC valida fornita.",
                "errors": errors[:10],
                "added": 0,
                "updated": 0,
                "total": 0
            }

        # Salva in SQLite
        db_res = await db_service.add_discovered_ips(valid_entries)

        # Re-arricchisci subito la cache dispositivi in RAM
        await self.refresh_cached_devices_enrichment()

        logger.info(
            f"Reverse Enrichment: elaborati {len(valid_entries)} record da '{source}' "
            f"(aggiunti={db_res['added']}, aggiornati={db_res['updated']})."
        )

        return {
            "status": "success",
            "added": db_res["added"],
            "updated": db_res["updated"],
            "total": db_res["total"],
            "valid_count": len(valid_entries),
            "errors_count": len(errors),
            "errors": errors[:5] if errors else []
        }

    async def scan_adguard_instance(self, inst: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interroga un'istanza AdGuard Home per recuperare gli indirizzi 'bare/auto' non ancora assegnati,
        effettua una probe NDP locale per risolvere il rispettivo MAC e registra i risultati.
        """
        from app.services.dns_manager import normalize_dns_url

        url = normalize_dns_url(inst.get("url", ""))
        username = inst.get("username", "")
        password = inst.get("password", "")
        auth = (username.strip(), password.strip()) if username and password else None

        if not url:
            return {"success": False, "message": "URL AdGuard non configurato.", "found_count": 0, "resolved_count": 0}

        candidate_ips: Set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=True) as client:
                # 1. Recupera i client configurati e auto_clients
                resp = await client.get(f"{url}/control/clients", auth=auth)
                if resp.status_code == 200:
                    data = resp.json() if isinstance(resp.json(), dict) else {}
                    # Esamina auto_clients
                    for ac in (data.get("auto_clients") or []):
                        if isinstance(ac, dict):
                            ip = ac.get("ip")
                            if ip:
                                candidate_ips.add(str(ip).strip())

                # 2. Esamina anche le query recenti per intercettare client attivi non salvati
                try:
                    q_resp = await client.get(f"{url}/control/querylog?limit=150", auth=auth)
                    if q_resp.status_code == 200:
                        q_data = q_resp.json() if isinstance(q_resp.json(), dict) else {}
                        for q in (q_data.get("data") or []):
                            if isinstance(q, dict):
                                c_ip = q.get("client")
                                if c_ip:
                                    candidate_ips.add(str(c_ip).strip())
                except Exception as eq:
                    logger.debug(f"AdGuard querylog inspection skipped: {eq}")

        except Exception as e:
            return {
                "success": False,
                "message": f"Errore connessione ad AdGuard ({url}): {str(e)}",
                "found_count": 0,
                "resolved_count": 0
            }

        if not candidate_ips:
            return {
                "success": True,
                "message": "Nessun client auto/orfano rilevato su AdGuard Home.",
                "found_count": 0,
                "resolved_count": 0,
                "candidates": []
            }

        # Filtra specificamente gli indirizzi ULA (o routabili)
        ula_candidates = []
        for c in candidate_ips:
            info = classify_ip(c)
            if info.get("valid") and info["type"] in ("ULA", "GUA"):
                ula_candidates.append(info["normalized"])

        resolved_mappings = []
        # Risolvi ciascun candidato via NDP con probe
        for ula_ip in ula_candidates:
            mac = await resolve_mac_via_ndp(ula_ip, probe_first=True)
            if mac:
                resolved_mappings.append({
                    "mac": mac,
                    "ip": ula_ip,
                    "ip_type": "ULA",
                    "source": f"adguard_ndp_{inst.get('id', 'default')}"
                })

        # Salva i mapping risolti
        saved_stats = {"added": 0, "updated": 0, "total": 0}
        if resolved_mappings:
            saved_stats = await db_service.add_discovered_ips(resolved_mappings)
            await self.refresh_cached_devices_enrichment()

        return {
            "success": True,
            "message": f"Rilevati {len(ula_candidates)} candidati ULA, {len(resolved_mappings)} risolti con successo via NDP.",
            "found_count": len(candidate_ips),
            "ula_candidates_count": len(ula_candidates),
            "resolved_count": len(resolved_mappings),
            "saved_stats": saved_stats,
            "resolved": resolved_mappings
        }

    async def scan_all_adguard_instances(self) -> Dict[str, Any]:
        """Scansiona tutte le istanze AdGuard configurate in DNSManager."""
        from app.services.dns_manager import dns_manager
        settings = await dns_manager.get_settings()
        instances = settings.get("instances", [])
        adguard_instances = [i for i in instances if i.get("engine") == "adguard" and i.get("enabled", True)]

        if not adguard_instances:
            return {
                "success": False,
                "message": "Nessuna istanza AdGuard Home attiva configurata.",
                "total_instances": 0,
                "results": []
            }

        results = []
        total_resolved = 0
        for inst in adguard_instances:
            res = await self.scan_adguard_instance(inst)
            results.append({"instance_id": inst.get("id"), "instance_name": inst.get("name"), **res})
            total_resolved += res.get("resolved_count", 0)

        return {
            "success": True,
            "total_instances": len(adguard_instances),
            "total_resolved": total_resolved,
            "results": results
        }

    async def refresh_cached_devices_enrichment(self) -> None:
        """
        Rifonde in RAM la tabella device_discovered_ips all'interno
        dei dispositivi memorizzati in background_poller.
        """
        from app.services.poller import background_poller

        discovered_map = await db_service.get_all_discovered_ips_map()
        if not discovered_map:
            return

        cached_devices = background_poller.cached_devices or []
        for dev in cached_devices:
            mac = str(dev.get("mac") or "").strip().lower()
            if not mac or mac not in discovered_map:
                continue

            disc_list = discovered_map[mac]
            existing_ula = list(dev.get("ipv6_ula") or [])
            existing_all_v6 = list(dev.get("ipv6_addresses") or [])
            existing_details = list(dev.get("ipv6_details") or [])

            for item in disc_list:
                ip_addr = item.get("ip_address")
                ip_type = item.get("ip_type") or "ULA"
                ip_src = item.get("source") or "ndp_enrichment"
                if not ip_addr:
                    continue

                if ip_addr not in existing_ula and ip_type.upper() == "ULA":
                    existing_ula.append(ip_addr)
                if ip_addr not in existing_all_v6:
                    existing_all_v6.append(ip_addr)

                if not any(d.get("address") == ip_addr for d in existing_details):
                    existing_details.append({
                        "address": ip_addr,
                        "type": ip_type,
                        "scope": "local" if ip_type == "ULA" else "global",
                        "origin": "ndp_discovered",
                        "source": ip_src
                    })

            dev["ipv6_ula"] = existing_ula
            dev["ipv6_addresses"] = existing_all_v6
            dev["ipv6_all"] = existing_all_v6
            dev["ipv6_details"] = existing_details
            dev["has_discovered_ips"] = True
            dev["discovered_ips"] = disc_list

            if not dev.get("ipv6") or str(dev.get("ipv6")).lower().startswith("fe80:"):
                if existing_ula:
                    dev["ipv6"] = existing_ula[0]
        # Assicura il riferimento della lista dispositivi aggiornata in RAM
        background_poller.cached_devices = cached_devices


enrichment_service = EnrichmentService()
