import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.eero_client import eero_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    login: str = Field(..., description="Email o Numero di Telefono con prefisso internazionale (es. +39...)")


class VerifyOTPRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=8, description="Codice OTP a 6 cifre ricevuto via SMS/Email")
    user_token: Optional[str] = Field(None, description="Token temporaneo restituito dalla richiesta di login")


@router.get("/status")
async def get_auth_status():
    """Restituisce lo stato corrente di autenticazione e le informazioni dell'account."""
    is_auth = eero_client.is_authenticated
    is_demo = settings.demo_mode or (bool(eero_client.user_token) and eero_client.user_token.startswith("demo_"))
    
    account = None
    if is_auth:
        try:
            account = await eero_client.fetch_account_info()
        except Exception as e:
            logger.warning(f"Failed to fetch account info on status check: {e}")
            is_auth = False

    return {
        "authenticated": is_auth,
        "demo_mode": is_demo,
        "network_id": eero_client.current_network_id,
        "account": account,
    }


@router.post("/login")
async def request_login(payload: LoginRequest):
    """Invia la richiesta di accesso per ricevere il codice OTP a 6 cifre."""
    try:
        res = await eero_client.request_login_code(payload.login.strip())
        return res
    except Exception as e:
        logger.error(f"Login request failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify")
async def verify_otp(payload: VerifyOTPRequest):
    """Verifica il codice OTP e salva il session token persistente."""
    try:
        res = await eero_client.verify_login_code(payload.code.strip(), payload.user_token)
        return res
    except Exception as e:
        logger.error(f"OTP verification failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/logout")
async def logout():
    """Rimuove il token di sessione e disconnette l'app."""
    eero_client.clear_session()
    return {"status": "success", "message": "Disconnessione completata."}
