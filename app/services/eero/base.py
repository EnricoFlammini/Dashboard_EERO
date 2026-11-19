"""
Base session, persistence, auth token management and HTTP client for eero Client.
"""
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import json
import logging
import os
import httpx
from app.config import settings
from app.i18n import log_event, tr
from app.services.eero.const import EERO_API_BASE

logger = logging.getLogger(__name__)


class EeroBaseMixin:
    """Gestione sessione, persistence token e client HTTP persistente."""

    def _get_client(self) -> httpx.AsyncClient:
        """Restituisce il client HTTP condiviso persistente con connection pooling e keep-alive (Issue #24)."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=10.0),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=120.0
                )
            )
        return self._http_client

    @asynccontextmanager
    async def _client_session(self, timeout: Optional[float] = None):
        """Context manager per riutilizzare la sessione HTTP ed eliminare query DNS ridondanti."""
        client = self._get_client()
        yield client

    async def close(self):
        """Chiude il pool di connessioni HTTP persistenti su shutdown dell'applicazione."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    def load_session(self):
        """Carica il token di sessione e ID di rete dal file session.json o da .env."""
        # 1. Priorità al token permanente impostato in .env
        if settings.eero_user_token:
            self.user_token = settings.eero_user_token.strip()
            self.saved_live_token = self.user_token
            if settings.eero_network_id:
                self.current_network_id = settings.eero_network_id.strip()
                self.saved_live_network_id = self.current_network_id
            log_event(logger, logging.INFO, "log_eero.session_loaded_env")
            return

        # 2. Caricamento dal file di sessione persistente nel volume ./data
        try:
            if self.session_path.exists():
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    stored_user_token = data.get("user_token")
                    saved_live_tok = data.get("saved_live_token")
                    if not saved_live_tok and stored_user_token and not stored_user_token.startswith("demo_"):
                        saved_live_tok = stored_user_token

                    self.saved_live_token = saved_live_tok
                    self.saved_live_network_id = data.get("saved_live_network_id") or data.get("network_id")
                    self.saved_live_account_info = data.get("saved_live_account_info") or data.get("account_info")
                    self.saved_live_networks = data.get("saved_live_networks") or []
                    self._is_demo_active = bool(data.get("is_demo_active", False))

                    if self._is_demo_active:
                        self.user_token = "demo_verified_master_token"
                        stored_demo_net = data.get("network_id")
                        if stored_demo_net in ("network_demo_mesh_01", "network_demo_mesh_02"):
                            self.current_network_id = stored_demo_net
                        else:
                            self.current_network_id = "network_demo_mesh_01"
                        self.account_info = {"name": "Demo Administrator", "email": "admin@demo-eero.lan"}
                        self.available_networks = self.get_available_networks()
                    else:
                        self.user_token = stored_user_token
                        self.current_network_id = data.get("network_id")
                        self.account_info = data.get("account_info")
                        self.available_networks = data.get("available_networks") or []

                    log_event(logger, logging.INFO, "log_eero.session_loaded", network_id=self.current_network_id, demo=self.is_demo_mode)
        except Exception as e:
            log_event(logger, logging.WARNING, "log_eero.session_load_failed", path=self.session_path, error=e)

    def save_session(self):
        """Salva il token di sessione su disco."""
        try:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "user_token": self.user_token,
                "network_id": self.current_network_id,
                "available_networks": self.available_networks,
                "account_info": self.account_info,
                "saved_live_token": self.saved_live_token,
                "saved_live_network_id": self.saved_live_network_id,
                "saved_live_networks": self.saved_live_networks,
                "saved_live_account_info": self.saved_live_account_info,
                "is_demo_active": self._is_demo_active,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            # Il file contiene il token di sessione eero: leggibile e scrivibile solo dal proprietario (0600)
            fd = os.open(self.session_path, os.O_WRONLY | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                try:
                    os.fchmod(f.fileno(), 0o600)  # corregge anche un file già esistente creato con permessi più ampi
                except (AttributeError, OSError):
                    pass  # fchmod assente (Windows) o non consentito sul volume: il salvataggio prosegue
                f.truncate(0)  # svuotato solo dopo il chmod: un chmod fallito non lascia mai il file vuoto
                json.dump(data, f, indent=2)
            log_event(logger, logging.INFO, "log_eero.session_saved")
        except Exception as e:
            log_event(logger, logging.ERROR, "log_eero.session_save_failed", error=e)

    def set_demo_mode(self, active: bool):
        """Attiva o disattiva la modalità demo preservando il token reale salvato."""
        if active:
            if self.user_token and not self.user_token.startswith("demo_"):
                self.saved_live_token = self.user_token
                self.saved_live_network_id = self.current_network_id
                self.saved_live_account_info = self.account_info
                self.saved_live_networks = list(self.available_networks)
            self._is_demo_active = True
            self.user_token = "demo_verified_master_token"
            self.current_network_id = "network_demo_mesh_01"
            self.account_info = {"name": "Demo Administrator", "email": "admin@demo-eero.lan"}
            self.available_networks = self.get_available_networks()
            if hasattr(self, "_demo_networks_store") and "network_demo_mesh_01" in self._demo_networks_store:
                self._demo_state = self._demo_networks_store["network_demo_mesh_01"]
        else:
            self._is_demo_active = False
            if self.saved_live_token and not self.saved_live_token.startswith("demo_"):
                self.user_token = self.saved_live_token
                self.current_network_id = self.saved_live_network_id
                self.account_info = self.saved_live_account_info
                self.available_networks = self.saved_live_networks
            else:
                self.user_token = None
                self.current_network_id = None
                self.account_info = None
                self.available_networks = []
        self.save_session()

    def clear_session(self):
        """Rimuove la sessione corrente per effettuare il logout."""
        self.user_token = None
        self.current_network_id = None
        self.account_info = None
        self.available_networks = []
        self.saved_live_token = None
        self.saved_live_network_id = None
        self.saved_live_networks = []
        self.saved_live_account_info = None
        self._is_demo_active = False
        if self.session_path.exists():
            try:
                os.remove(self.session_path)
                log_event(logger, logging.INFO, "log_eero.session_removed_logout")
            except Exception as e:
                log_event(logger, logging.ERROR, "log_eero.session_remove_failed", error=e)

    def get_available_networks(self) -> List[Dict[str, Any]]:
        """Restituisce la lista di tutte le reti eero disponibili con il flag is_active aggiornato."""
        if self.is_demo_mode:
            return [
                {
                    "id": "network_demo_mesh_01",
                    "name": "Casa Rossi Mesh 6E",
                    "url": "/2.2/networks/network_demo_mesh_01",
                    "role": "owner",
                    "is_active": self.current_network_id == "network_demo_mesh_01",
                },
                {
                    "id": "network_demo_mesh_02",
                    "name": "Ufficio & Studio Pro Mesh",
                    "url": "/2.2/networks/network_demo_mesh_02",
                    "role": "admin",
                    "is_active": self.current_network_id == "network_demo_mesh_02",
                }
            ]

        result = []
        for n in self.available_networks:
            item = dict(n)
            item["is_active"] = (item.get("id") == self.current_network_id)
            result.append(item)

        # Fallback se non ci sono reti in available_networks ma c'è current_network_id
        if not result and self.current_network_id:
            result.append({
                "id": self.current_network_id,
                "name": f"eero Network ({self.current_network_id})",
                "url": f"/2.2/networks/{self.current_network_id}",
                "role": "owner",
                "is_active": True,
            })
        return result

    async def switch_network(self, network_id: str) -> Dict[str, Any]:
        """Effettua l'hot-swap della rete eero attiva, preservando la sessione e invalidando la cache."""
        clean_id = str(network_id or "").strip()
        if not clean_id:
            raise ValueError(tr("eero.invalid_network_id"))

        old_net_id = self.current_network_id
        log_event(logger, logging.INFO, "log_eero.network_switching", old_network_id=old_net_id, network_id=clean_id)

        if self.is_demo_mode:
            valid_demo_ids = ("network_demo_mesh_01", "network_demo_mesh_02")
            if clean_id not in valid_demo_ids:
                raise ValueError(tr("eero.demo_network_not_found", network_id=clean_id, valid=", ".join(valid_demo_ids)))

            # Salva stato della rete demo precedente nello store
            if hasattr(self, "_demo_networks_store") and old_net_id:
                self._demo_networks_store[old_net_id] = self._demo_state

            self.current_network_id = clean_id
            if hasattr(self, "_demo_networks_store") and clean_id in self._demo_networks_store:
                self._demo_state = self._demo_networks_store[clean_id]
        else:
            self.current_network_id = clean_id
            self.saved_live_network_id = clean_id

        # Invalida cache gateway per la nuova rete
        self.current_gateway_id = None
        self.current_gateway_url = None
        self.current_gateway_name = None
        self.current_gateway_ip = None
        self._last_network_details = None
        self._last_eeros = None

        # Aggiorna flag is_active in available_networks
        for net in self.available_networks:
            net["is_active"] = (net.get("id") == self.current_network_id)

        self.save_session()
        log_event(logger, logging.INFO, "log_eero.network_switched", network_id=self.current_network_id)
        return {
            "status": "success",
            "active_network_id": self.current_network_id,
            "available_networks": self.get_available_networks()
        }

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_token) or self._is_demo_active or settings.demo_mode

    @property
    def is_demo_mode(self) -> bool:
        return bool(settings.demo_mode or self._is_demo_active or (self.user_token and self.user_token.startswith("demo_")))

    @property
    def has_saved_live_token(self) -> bool:
        return bool(self.saved_live_token and not self.saved_live_token.startswith("demo_"))

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "eero-ios/3.47.0",
        }
        if self.user_token:
            headers["Cookie"] = f"s={self.user_token}"
        return headers

    def _get_cookies(self) -> Dict[str, str]:
        if self.user_token:
            return {"s": self.user_token}
        return {}

    # =========================================================================
    # AUTENTICAZIONE EERO API (2FA OTP)
    # =========================================================================

    async def _request_with_fallbacks(
        self,
        method: str,
        endpoints: List[str],
        json_payload: Optional[Dict[str, Any]] = None,
        success_statuses: Tuple[int, ...] = (200, 201, 202, 204),
    ) -> Optional[httpx.Response]:
        """Esegue una richiesta HTTP testando in sequenza una lista di endpoint candidati con fallback automatico."""
        headers = self._get_headers()
        async with self._client_session() as client:
            for ep in endpoints:
                try:
                    resp = await client.request(method, ep, headers=headers, json=json_payload)
                    if resp.status_code in success_statuses:
                        return resp
                except Exception as ex:
                    logger.debug(f"Candidate endpoint {ep} error: {ex}")
        return None
