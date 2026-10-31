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

from app.i18n import log_event, tr, tr_all

logger = logging.getLogger(__name__)

# =========================================================================
# MATRICE DEI PERMESSI GRANULARI (RBAC SCOPES)
# =========================================================================

# Texts for every scope live in app/i18n_locales/<lang>/permissions.json as "<key>_label" / "<key>_desc".
READ_SCOPES: List[Dict[str, str]] = [
    {"key": "view_topology"},
    {"key": "view_clients"},
    {"key": "view_devices"},
    {"key": "view_analytics"},
    {"key": "view_speedtest"},
    {"key": "view_logs"},
    {"key": "view_rules"},
    {"key": "view_guest_wifi"},
    {"key": "view_dns_sync"},
]

ACTION_SCOPES: List[Dict[str, str]] = [
    {"key": "action_reboot_nodes"},
    {"key": "action_pause_devices"},
    {"key": "action_edit_devices"},
    {"key": "action_manage_rules"},
    {"key": "action_manage_schedules"},
    {"key": "action_sync_dns"},
    {"key": "action_manage_users"},
    {"key": "action_system_backup"},
    {"key": "action_toggle_guest"},
    {"key": "action_run_speedtest"},
]

ALL_READ_PERMISSION_KEYS: List[str] = [p["key"] for p in READ_SCOPES]
ALL_ACTION_PERMISSION_KEYS: List[str] = [p["key"] for p in ACTION_SCOPES]
ALL_PERMISSION_KEYS: List[str] = ALL_READ_PERMISSION_KEYS + ALL_ACTION_PERMISSION_KEYS

# Permission texts live in app/i18n_locales/<lang>/permissions.json as
# "<key>_label" / "<key>_desc"; the order here is the display order in the UI.
UI_PERMISSION_KEYS: List[str] = [
    "view_topology",
    "view_clients",
    "view_analytics",
    "view_logs",
    "action_reboot_nodes",
    "action_pause_devices",
    "action_manage_rules",
    "action_sync_dns",
    "action_manage_users",
    "action_system_backup"
]


def build_permissions_catalog(lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns the permission catalog with label/description in ``lang`` (default: request language)
    plus ``label_i18n`` / ``description_i18n`` maps for every supported language.
    ``label_en`` / ``description_en`` stay for older clients."""
    catalog: List[Dict[str, Any]] = []
    for key in UI_PERMISSION_KEYS:
        label_i18n = tr_all(f"permissions.{key}_label")
        desc_i18n = tr_all(f"permissions.{key}_desc")
        catalog.append({
            "key": key,
            "label": tr(f"permissions.{key}_label", lang=lang),
            "label_en": label_i18n.get("en", ""),
            "label_i18n": label_i18n,
            "description": tr(f"permissions.{key}_desc", lang=lang),
            "description_en": desc_i18n.get("en", ""),
            "description_i18n": desc_i18n,
        })
    return catalog


def _describe_scopes(scopes: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Expands scope keys into ``{key, name, name_i18n, description, description_i18n}`` entries."""
    described: List[Dict[str, Any]] = []
    for scope in scopes:
        key = scope["key"]
        name_i18n = tr_all(f"permissions.{key}_label")
        desc_i18n = tr_all(f"permissions.{key}_desc")
        described.append({
            "key": key,
            "name": tr(f"permissions.{key}_label"),
            "name_i18n": name_i18n,
            "description": tr(f"permissions.{key}_desc"),
            "description_i18n": desc_i18n,
        })
    return described


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
            raise ValueError(tr("auth.password_empty"))
        
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
            log_event(logger, logging.WARNING, "log_system.password_verify_failed", error=str(e))
            return False

    @staticmethod
    def generate_session_token() -> str:
        """Genera un token crittograficamente sicuro a 256 bit in formato URL-safe."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def get_permissions_catalog() -> Dict[str, Any]:
        """Returns the full permissions catalog, labelled in the request language plus ``*_i18n`` maps."""
        return {
            "read_scopes": _describe_scopes(READ_SCOPES),
            "action_scopes": _describe_scopes(ACTION_SCOPES),
            "all_keys": ALL_PERMISSION_KEYS,
            "permissions": build_permissions_catalog()
        }

    @staticmethod
    def validate_permissions(perms: List[str]) -> List[str]:
        """Filtra e valida l'elenco dei permessi passati verificando che appartengano ai chiavi ammesse."""
        if not isinstance(perms, list):
            return []
        valid_keys = set(ALL_PERMISSION_KEYS)
        return [p for p in perms if isinstance(p, str) and p in valid_keys]


auth_service = AuthService()
