"""
Authentication, SMS OTP 2FA verification, account info, and Amazon OAuth2/PKCE for eero Client.
"""
from typing import Dict, Any, List, Optional
import base64
import hashlib
import logging
import secrets
import time
import urllib.parse
from app.config import settings
from app.i18n import log_event, tr
from app.services.eero.const import EERO_API_BASE

logger = logging.getLogger(__name__)


class EeroAuthMixin:
    """Metodi di autenticazione 2FA SMS/Email, Account info e Amazon OAuth2 PKCE."""

    async def request_login_code(self, identifier: str) -> Dict[str, Any]:
        """Invia la richiesta per ricevere l'OTP a 6 cifre via SMS o Email."""
        if settings.demo_mode:
            self.user_token = "demo_temp_unverified_token"
            return {"status": "success", "message": tr("eero.demo_otp_sent"), "login": identifier}

        async with self._client_session() as client:
            resp = await client.post(
                f"{EERO_API_BASE}/login",
                json={"login": identifier.strip()},
                headers=self._get_headers()
            )
            if resp.status_code != 200:
                error_msg = resp.text
                try:
                    error_msg = resp.json().get("error", resp.text)
                except Exception:
                    pass
                raise ValueError(tr("eero.login_request_failed", status=resp.status_code, error=error_msg))

            data = resp.json().get("data", {})
            self.user_token = data.get("user_token")
            return {"status": "success", "user_token": self.user_token, "login": identifier}

    async def verify_login_code(self, code: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Verifica il codice OTP e ottiene il session token definitivo."""
        if user_token:
            self.user_token = user_token

        if settings.demo_mode or self.user_token == "demo_temp_unverified_token":
            if code.strip() in ("123456", "000000", "DEMO", "demo"):
                self.user_token = "demo_verified_master_token"
                self.current_network_id = "network_demo_mesh_01"
                self.account_info = {"name": "Demo Administrator", "email": "admin@demo-eero.lan"}
                self.save_session()
                return {"status": "success", "message": tr("eero.demo_auth_success"), "network_id": self.current_network_id}
            else:
                raise ValueError(tr("eero.demo_otp_invalid"))

        if not self.user_token:
            raise ValueError(tr("eero.no_login_pending"))

        async with self._client_session() as client:
            resp = await client.post(
                f"{EERO_API_BASE}/login/verify",
                json={"code": code.strip()},
                headers=self._get_headers(),
                cookies=self._get_cookies()
            )
            if resp.status_code != 200:
                error_msg = resp.text
                try:
                    error_msg = resp.json().get("error", resp.text)
                except Exception:
                    pass
                raise ValueError(tr("eero.otp_verification_failed", error=error_msg))

            data = resp.json().get("data", {})
            if "user_token" in data:
                self.user_token = data["user_token"]
                self.saved_live_token = data["user_token"]
                self._is_demo_active = False

            # Salvataggio sessione definitiva e fetch rete
            account = await self.fetch_account_info()
            self.saved_live_network_id = self.current_network_id
            self.saved_live_account_info = account
            self.saved_live_networks = list(self.available_networks)
            self.save_session()
            return {"status": "success", "account": account}

    async def fetch_account_info(self) -> Dict[str, Any]:
        """Recupera le informazioni dell'account e tutte le reti disponibili (Issue #22), preservando la rete attiva."""
        if settings.demo_mode or not self.is_authenticated or self.user_token.startswith("demo_"):
            return self._get_demo_account()

        async with self._client_session() as client:
            resp = await client.get(f"{EERO_API_BASE}/account", headers=self._get_headers())
            if resp.status_code != 200:
                resp = await client.get(f"{EERO_API_BASE}/user", headers=self._get_headers())

            if resp.status_code != 200:
                log_event(logger, logging.ERROR, "log_eero.account_info_fetch_failed", status=resp.status_code, response=resp.text)
                return self.account_info or {}

            data = resp.json().get("data", {})
            self.account_info = data

            # 1. Parsing delle reti da account/user (supporta reti proprietarie, singole, condivise e admin - Issue #69)
            raw_networks = []
            for net_key in ("networks", "network", "shared_networks", "guest_networks", "admin_networks"):
                net_val = data.get(net_key)
                if isinstance(net_val, dict):
                    cand = net_val.get("data") or net_val.get("networks") or net_val.get("items")
                    if isinstance(cand, list):
                        raw_networks.extend(cand)
                    elif "url" in net_val or "id" in net_val or "name" in net_val:
                        raw_networks.append(net_val)
                    else:
                        # Gestione dizionario indicizzato per ID rete
                        for v in net_val.values():
                            if isinstance(v, dict) and ("url" in v or "id" in v or "name" in v):
                                raw_networks.append(v)
                            elif isinstance(v, str) and ("/networks/" in v or v.isdigit()):
                                raw_networks.append(v)
                elif isinstance(net_val, list):
                    raw_networks.extend(net_val)
                elif isinstance(net_val, (str, int)) and net_val:
                    raw_networks.append(str(net_val))

            # 2. Fallback per account con sole reti condivise/admin o endpoint dedicato: /2.2/networks
            if not raw_networks:
                try:
                    net_resp = await client.get(f"{EERO_API_BASE}/networks", headers=self._get_headers())
                    if net_resp.status_code == 200:
                        payload = net_resp.json()
                        if isinstance(payload, list):
                            raw_networks.extend(payload)
                        elif isinstance(payload, dict):
                            cand = payload.get("data") or payload.get("networks") or payload.get("items")
                            if isinstance(cand, list):
                                raw_networks.extend(cand)
                            elif "url" in payload or "id" in payload:
                                raw_networks.append(payload)
                            else:
                                for v in payload.values():
                                    if isinstance(v, dict) and ("url" in v or "id" in v or "name" in v):
                                        raw_networks.append(v)
                                    elif isinstance(v, list):
                                        raw_networks.extend(v)
                except Exception as e:
                    log_event(logger, logging.WARNING, "log_eero.networks_fallback_failed", error=str(e))

            # 3. Normalizzazione lista reti disponibili (Multi-Network Fleet Management - Issue #22, Issue #69)
            parsed_networks = []
            for item in raw_networks:
                if isinstance(item, dict):
                    net_url = str(item.get("url") or "")
                    net_id = str(item.get("id") or "")
                    if not net_id and "/" in net_url:
                        net_id = net_url.split("/")[-1]
                    net_name = item.get("name") or item.get("nickname") or (f"eero Network ({net_id})" if net_id else "eero Network")
                    role = item.get("role") or ("admin" if "shared" in net_url.lower() or "guest" in net_url.lower() else "owner")
                    if net_id and not any(x["id"] == net_id for x in parsed_networks):
                        parsed_networks.append({
                            "id": net_id,
                            "name": net_name,
                            "url": net_url or f"/2.2/networks/{net_id}",
                            "role": role,
                        })
                elif isinstance(item, (str, int)):
                    str_item = str(item).strip()
                    net_id = str_item.split("/")[-1] if "/" in str_item else str_item
                    if net_id and not any(x["id"] == net_id for x in parsed_networks):
                        parsed_networks.append({
                            "id": net_id,
                            "name": f"eero Network ({net_id})",
                            "url": str_item if "/" in str_item else f"/2.2/networks/{net_id}",
                            "role": "owner",
                        })

            # 4. Fallback configurazione: se nessuna rete è stata rilevata dall'account, usa EERO_NETWORK_ID da .env/settings (Issue #69)
            env_net_id = (settings.eero_network_id or "").strip()
            if not parsed_networks and env_net_id:
                log_event(logger, logging.INFO, "log_eero.network_env_fallback", network_id=env_net_id)
                parsed_networks.append({
                    "id": env_net_id,
                    "name": f"eero Network ({env_net_id})",
                    "url": f"/2.2/networks/{env_net_id}",
                    "role": "owner",
                })

            if parsed_networks:
                self.available_networks = parsed_networks
                # Risoluzione network ID attivo:
                # - Se c'è settings.eero_network_id in .env ed è presente, priorità a quello
                # - Se self.current_network_id è già impostato ed esiste tra le reti disponibili, MANTIENILO! (Issue #22 bug fix)
                # - Altrimenti fallback alla prima rete disponibile
                known_ids = [x["id"] for x in parsed_networks]

                if env_net_id and env_net_id in known_ids:
                    self.current_network_id = env_net_id
                elif self.current_network_id and self.current_network_id in known_ids:
                    # Preserva la rete già selezionata dall'utente!
                    pass
                else:
                    self.current_network_id = parsed_networks[0]["id"]

                for n in self.available_networks:
                    n["is_active"] = (n["id"] == self.current_network_id)
            else:
                self.available_networks = []
                self.current_network_id = None
                log_event(logger, logging.WARNING, "log_eero.no_networks_found")

            log_event(logger, logging.INFO, "log_eero.network_resolved", network_id=self.current_network_id, count=len(self.available_networks))
            self.save_session()
            return data

    # =========================================================================
    # NORMALIZZAZIONE DATI EERO API
    # =========================================================================

    def generate_amazon_oauth_url(self) -> Dict[str, Any]:
        """Genera l'URL di autenticazione Amazon OpenID + OAuth2 PKCE (S256) nativo eero (Issue #93)."""
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        state = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")

        device_type = "A2W01JEFAJFTXI"
        serial = secrets.token_hex(16).upper()
        client_hex = f"{serial}#{device_type}".encode("utf-8").hex()

        self._amazon_pkce_state = {
            "code_verifier": verifier,
            "code_challenge": challenge,
            "state": state,
            "client_id": client_hex,
            "created_at": time.time(),
        }

        return_to = f"https://www.amazon.com/ap/maplanding?state={state}"
        params = {
            "openid.assoc_handle": "amzn_eero_mobile_android_us",
            "pageId": "eero_mobile_accounts",
            "language": "en_US",
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.mode": "checkid_setup",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.ns.pape": "http://specs.openid.net/extensions/pape/1.0",
            "openid.pape.max_auth_age": "0",
            "openid.ns.oa2": "http://www.amazon.com/ap/ext/oauth/2",
            "openid.oa2.response_type": "code",
            "openid.oa2.scope": "device_auth_access",
            "openid.oa2.client_id": f"device:{client_hex}",
            "openid.oa2.code_challenge": challenge,
            "openid.oa2.code_challenge_method": "S256",
            "openid.return_to": return_to,
            "accountStatusPolicy": "P1",
        }
        login_url = f"https://www.amazon.com/ap/signin?{urllib.parse.urlencode(params)}"
        return {
            "status": "success",
            "login_url": login_url,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "redirect_uri": "https://www.amazon.com/ap/maplanding",
        }

    async def exchange_amazon_oauth_code(self, code_or_url: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Completa il login Amazon OAuth2/PKCE nativo (Issue #93).
        Accetta:
        - L'URL completo di callback Amazon (/ap/maplanding?state=...&openid.oa2.authorization_code=...)
        - Il codice di autorizzazione (`openid.oa2.authorization_code` o `code`) o `access_token` Amazon (`Atna|...` / `Atza|...`)
        - Un `user_token` di sessione eero estratto dal flusso Amazon
        """
        raw = str(code_or_url or "").strip()
        if not raw:
            raise ValueError("Authorization code, callback URL, or token is required")

        if self.is_demo_mode:
            return {
                "status": "success",
                "authenticated": True,
                "network_id": self.current_network_id or "demo_net_001",
                "account": {"name": "Demo Amazon User", "email": "demo@amazon.example"},
            }

        extracted_code = ""
        extracted_access_token = ""
        returned_state = ""
        if raw.startswith("http://") or raw.startswith("https://") or "?" in raw or "openid.oa2.authorization_code=" in raw or "code=" in raw or "access_token=" in raw:
            parsed = urllib.parse.urlparse(raw)
            qs = urllib.parse.parse_qs(parsed.query or parsed.fragment)
            if qs.get("error") or qs.get("openid.error"):
                raise ValueError(tr("auth.amazon_exchange_failed"))
            if qs.get("state"):
                returned_state = qs["state"][0]
            if qs.get("openid.oa2.authorization_code"):
                extracted_code = qs["openid.oa2.authorization_code"][0]
            elif qs.get("code"):
                extracted_code = qs["code"][0]
            if qs.get("access_token"):
                extracted_access_token = qs["access_token"][0]
            if qs.get("user_token"):
                raw = qs["user_token"][0]
        else:
            if raw.startswith("Atza|") or raw.startswith("Atna|"):
                extracted_access_token = raw
            else:
                extracted_code = raw

        pkce_state = getattr(self, "_amazon_pkce_state", {}) or {}
        if returned_state and pkce_state.get("state") and returned_state != pkce_state.get("state"):
            raise ValueError(tr("auth.amazon_exchange_failed"))

        verifier = code_verifier or pkce_state.get("code_verifier") or ""
        client_hex = pkce_state.get("client_id") or ""

        async with self._client_session() as client:
            # 1. Scambio authorization_code -> Amazon access_token su api.amazon.com/auth/token
            if extracted_code and not extracted_access_token and verifier and client_hex:
                try:
                    token_resp = await client.post(
                        "https://api.amazon.com/auth/token",
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "x-amzn-identity-auth-domain": "api.amazon.com",
                        },
                        json={
                            "app_name": "eero",
                            "app_version": "1.1.0",
                            "source_token_type": "authorization_code",
                            "source_token": extracted_code,
                            "requested_token_type": "access_token",
                            "code_verifier": verifier,
                            "code_algorithm": "SHA-256",
                            "client_id": client_hex,
                            "client_domain": "DeviceLegacy",
                        },
                    )
                    if token_resp.status_code == 200:
                        token_data = token_resp.json()
                        if token_data.get("access_token"):
                            extracted_access_token = token_data["access_token"]
                except Exception as e:
                    logger.debug(f"Amazon /auth/token exchange failed: {e}")

            # 2. Scambio Amazon access_token -> eero user_token su /2.2/login/amazon
            if extracted_access_token:
                try:
                    resp = await client.post(
                        f"{EERO_API_BASE}/login/amazon",
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "User-Agent": "eero-ios/3.47.0",
                        },
                        json={
                            "auth_token": extracted_access_token,
                            "create_account": False,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        user_token = resp.cookies.get("s") or data.get("user_token")
                        if user_token:
                            self.user_token = user_token
                            self.saved_live_token = user_token
                            self._is_demo_active = False
                            account = await self.fetch_account_info()
                            self.saved_live_network_id = self.current_network_id
                            self.saved_live_account_info = account
                            self.saved_live_networks = list(self.available_networks)
                            self.save_session()
                            return {
                                "status": "success",
                                "authenticated": True,
                                "network_id": self.current_network_id,
                                "account": account,
                            }
                except Exception as e:
                    logger.debug(f"Direct /login/amazon exchange attempt failed: {e}")

            # 3. Fallback: se l'utente ha fornito direttamente un user_token eero valido dal flusso Amazon
            candidate_token = raw
            if len(candidate_token) >= 16 and not candidate_token.startswith("http"):
                prev_token = self.user_token
                prev_demo = self._is_demo_active
                try:
                    self.user_token = candidate_token
                    self._is_demo_active = False
                    account = await self.fetch_account_info()
                    if account and (account.get("email") or account.get("name") or self.current_network_id):
                        self.saved_live_token = candidate_token
                        self.saved_live_network_id = self.current_network_id
                        self.saved_live_account_info = account
                        self.saved_live_networks = list(self.available_networks)
                        self.save_session()
                        return {
                            "status": "success",
                            "authenticated": True,
                            "network_id": self.current_network_id,
                            "account": account,
                        }
                except Exception:
                    self.user_token = prev_token
                    self._is_demo_active = prev_demo

        raise ValueError(tr("auth.amazon_exchange_failed"))


