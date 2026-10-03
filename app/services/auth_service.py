"""
Modulo di autenticazione e sicurezza crittografica locale per eero Dashboard.
Implementa l'hashing PBKDF2-HMAC-SHA256 (100.000 iterazioni con salt casuale),
generazione e gestione dei token di sessione e matrice permessi RBAC (v1.6.0 Modulo 1).
"""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =========================================================================
# MATRICE DEI PERMESSI GRANULARI (RBAC SCOPES)
# =========================================================================

READ_SCOPES: List[Dict[str, str]] = [
    {"key": "view_topology", "name_it": "Visualizzazione Topologia Mesh & WAN", "name_en": "Mesh Topology & WAN View", "description_it": "Visualizzazione mappa nodi mesh, stato operativo e backhaul", "description_en": "View mesh nodes map, operational status and backhaul"},
    {"key": "view_clients", "name_it": "Visualizzazione Flotta Dispositivi", "name_en": "Device Fleet View", "description_it": "Accesso all'elenco dei dispositivi connessi/noti, IP, MAC e frequenze", "description_en": "Access to connected/known devices list, IP, MAC and bands"},
    {"key": "view_devices", "name_it": "Visualizza Elenco Dispositivi", "name_en": "View Devices List", "description_it": "Accesso all'elenco dei dispositivi connessi/noti", "description_en": "Access to connected devices list"},
    {"key": "view_analytics", "name_it": "Visualizzazione Grafici & SLA", "name_en": "Analytics & SLA View", "description_it": "Consultazione grafici di traffico, latenza e metriche SLA", "description_en": "Consult traffic graphs, latency and SLA metrics"},
    {"key": "view_speedtest", "name_it": "Visualizza Storico Speed Test & SLA", "name_en": "View Speed Test & SLA History", "description_it": "Consultazione storico misurazioni WAN e metriche di prestazione", "description_en": "Consult WAN speed measurements history and performance metrics"},
    {"key": "view_logs", "name_it": "Visualizzazione Log & Audit", "name_en": "Logs & Audit View", "description_it": "Consultazione registro allarmi, audit di sistema e log eventi", "description_en": "Consult alert history, system audit and event logs"},
    {"key": "view_rules", "name_it": "Visualizza Prenotazioni & Port Forwarding", "name_en": "View DHCP Rules & Port Forwarding", "description_it": "Consultazione prenotazioni DHCP statiche e regole port forwarding", "description_en": "Consult static DHCP reservations and port forwarding rules"},
    {"key": "view_guest_wifi", "name_it": "Visualizza Wi-Fi Ospiti", "name_en": "View Guest Wi-Fi", "description_it": "Visualizzazione stato rete ospiti e QR code di connessione", "description_en": "View guest network status and connection QR code"},
    {"key": "view_dns_sync", "name_it": "Visualizza Stato Sincronizzazione Multi-DNS", "name_en": "View Multi-DNS Sync Status", "description_it": "Monitoraggio istanze DNS locali (AdGuard, Pi-hole, Technitium) e log", "description_en": "Monitor local DNS instances and synchronization logs"},
]

ACTION_SCOPES: List[Dict[str, str]] = [
    {"key": "action_reboot_nodes", "name_it": "Riavvio Nodi Mesh eero", "name_en": "Reboot Mesh Nodes", "description_it": "Autorizzazione al riavvio dell'intera rete mesh o dei singoli beacon", "description_en": "Authorization to reboot entire mesh network or individual beacons"},
    {"key": "action_pause_devices", "name_it": "Sospensione / Pausa Wi-Fi Dispositivi", "name_en": "Pause Devices Wi-Fi", "description_it": "Messa in pausa temporanea dell'accesso a Internet per dispositivi specifici", "description_en": "Temporarily pause internet access for specific devices"},
    {"key": "action_edit_devices", "name_it": "Modifica Dettagli & Alias Dispositivi", "name_en": "Edit Device Details & Aliases", "description_it": "Modifica nomi personalizzati, categorie, note, icone e preferiti", "description_en": "Edit custom nicknames, categories, notes, icons and favorites"},
    {"key": "action_manage_rules", "name_it": "Gestione Regole & Port Forwarding", "name_en": "Manage DHCP Rules & Port Forwarding", "description_it": "Creazione, modifica ed eliminazione di IP statici e inoltro porte", "description_en": "Create, modify and delete static IP reservations and port forwards"},
    {"key": "action_manage_schedules", "name_it": "Gestisci Pianificazioni & Parental Control", "name_en": "Manage Schedules & Parental Control", "description_it": "Creazione, modifica ed eliminazione di regole di pausa temporizzata per dispositivi e profili", "description_en": "Create, modify and delete timed pause rules for devices and profiles"},
    {"key": "action_sync_dns", "name_it": "Sincronizzazione Host DNS Esterni", "name_en": "Sync External DNS Hosts", "description_it": "Esecuzione manuale forzata del sync verso i server DNS locali", "description_en": "Forced manual execution of sync to local DNS servers"},
    {"key": "action_manage_users", "name_it": "Amministrazione Utenti & RBAC", "name_en": "Administer Users & RBAC", "description_it": "Creazione, abilitazione, modifica e gestione permessi per gli account locali", "description_en": "Create, enable, edit and manage permissions for local accounts"},
    {"key": "action_system_backup", "name_it": "Esportazione & Ripristino Backup", "name_en": "Backup & Disaster Recovery", "description_it": "Creazione snapshot di backup, download archivio e ripristino disaster recovery", "description_en": "Create backup snapshots, download archives and disaster recovery restore"},
    {"key": "action_toggle_guest", "name_it": "Controlla Rete Wi-Fi Ospiti", "name_en": "Control Guest Wi-Fi", "description_it": "Attivazione/disattivazione rete ospiti e rigenerazione password", "description_en": "Enable/disable guest network and regenerate guest credentials"},
    {"key": "action_run_speedtest", "name_it": "Esegui Speed Test On-Demand", "name_en": "Run Speed Test On-Demand", "description_it": "Esecuzione manuale di nuovi test di velocità sull'hardware gateway", "description_en": "Manually trigger new speed tests on gateway hardware"},
]

ALL_READ_PERMISSION_KEYS: List[str] = [p["key"] for p in READ_SCOPES]
ALL_ACTION_PERMISSION_KEYS: List[str] = [p["key"] for p in ACTION_SCOPES]
ALL_PERMISSION_KEYS: List[str] = ALL_READ_PERMISSION_KEYS + ALL_ACTION_PERMISSION_KEYS

UI_PERMISSIONS_CATALOG: List[Dict[str, str]] = [
    {"key": "view_topology", "label": "Visualizzazione Topologia Mesh & WAN", "label_en": "Mesh Topology & WAN View", "description": "Visualizzazione mappa nodi mesh, stato operativo e backhaul"},
    {"key": "view_clients", "label": "Visualizzazione Flotta Dispositivi", "label_en": "Device Fleet View", "description": "Accesso all'elenco dei dispositivi connessi/noti, IP, MAC e frequenze"},
    {"key": "view_analytics", "label": "Visualizzazione Grafici & SLA", "label_en": "Analytics & SLA View", "description": "Consultazione grafici di traffico, latenza e metriche SLA"},
    {"key": "view_logs", "label": "Visualizzazione Log & Audit", "label_en": "Logs & Audit View", "description": "Consultazione registro allarmi, audit di sistema e log eventi"},
    {"key": "action_reboot_nodes", "label": "Riavvio Nodi Mesh eero", "label_en": "Reboot Mesh Nodes", "description": "Autorizzazione al riavvio dell'intera rete mesh o dei singoli nodi"},
    {"key": "action_pause_devices", "label": "Sospensione / Pausa Wi-Fi Dispositivi", "label_en": "Pause Devices Wi-Fi", "description": "Messa in pausa temporanea dell'accesso a Internet per dispositivi"},
    {"key": "action_manage_rules", "label": "Gestione Regole & Port Forwarding", "label_en": "Manage DHCP Rules & Port Forwarding", "description": "Creazione, modifica ed eliminazione di IP statici e inoltro porte"},
    {"key": "action_sync_dns", "label": "Sincronizzazione Host DNS Esterni", "label_en": "Sync External DNS Hosts", "description": "Esecuzione manuale forzata del sync verso i server DNS locali"},
    {"key": "action_manage_users", "label": "Amministrazione Utenti & RBAC", "label_en": "Administer Users & RBAC", "description": "Creazione, abilitazione e gestione utenti locali e permessi"},
    {"key": "action_system_backup", "label": "Esportazione & Ripristino Backup", "label_en": "Backup & Disaster Recovery", "description": "Creazione snapshot di backup, download archivio e ripristino"}
]


class AuthService:
    """Servizio per la crittografia, verifica password e gestione dei token di sessione."""

    PBKDF2_ITERATIONS = 100_000
    HASH_NAME = "sha256"

    @classmethod
    def hash_password(cls, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Genera l'hash PBKDF2-HMAC-SHA256 con salt crittografico casuale.
        Restituisce una tupla (hash_hex, salt_hex).
        """
        if not password:
            raise ValueError("La password non può essere vuota.")
        
        salt_hex = salt if salt else secrets.token_hex(16)
        salt_bytes = bytes.fromhex(salt_hex)
        pw_bytes = password.encode("utf-8")
        
        digest = hashlib.pbkdf2_hmac(
            cls.HASH_NAME,
            pw_bytes,
            salt_bytes,
            cls.PBKDF2_ITERATIONS
        )
        return digest.hex(), salt_hex

    @classmethod
    def verify_password(cls, password: str, password_hash: str, salt: str) -> bool:
        """
        Verifica una password in tempo costante (resistente ad attacchi di timing).
        """
        if not password or not password_hash or not salt:
            return False
        try:
            salt_bytes = bytes.fromhex(salt)
            computed_digest = hashlib.pbkdf2_hmac(
                cls.HASH_NAME,
                password.encode("utf-8"),
                salt_bytes,
                cls.PBKDF2_ITERATIONS
            )
            expected_digest = bytes.fromhex(password_hash)
            return hmac.compare_digest(computed_digest, expected_digest)
        except Exception as e:
            logger.warning(f"Errore durante la verifica della password: {e}")
            return False

    @staticmethod
    def generate_session_token() -> str:
        """Genera un token crittograficamente sicuro a 256 bit in formato URL-safe."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def get_permissions_catalog() -> Dict[str, Any]:
        """Restituisce il catalogo bilingue completo dei permessi disponibili."""
        return {
            "read_scopes": READ_SCOPES,
            "action_scopes": ACTION_SCOPES,
            "all_keys": ALL_PERMISSION_KEYS,
            "permissions": UI_PERMISSIONS_CATALOG
        }

    @staticmethod
    def validate_permissions(perms: List[str]) -> List[str]:
        """Filtra e valida l'elenco dei permessi passati verificando che appartengano ai chiavi ammesse."""
        if not isinstance(perms, list):
            return []
        valid_keys = set(ALL_PERMISSION_KEYS)
        return [p for p in perms if isinstance(p, str) and p in valid_keys]


auth_service = AuthService()
