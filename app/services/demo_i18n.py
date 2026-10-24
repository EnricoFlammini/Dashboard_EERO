"""
Demo Mode payload localization.

The Demo Mode simulator in ``eero_client._init_demo_state`` describes a fictional Italian household
("Casa Rossi"): node locations, device nicknames, profile and guest-network names are Italian
literals. They are plain data, not UI strings, so the regular catalogs cannot translate them.

This module maps those known demo literals to English and is applied by the
``localize_demo_payloads`` middleware in ``app.main`` to every ``/api`` JSON response while Demo Mode
is active and the caller's language is not Italian. Live-network data never passes through it.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.i18n import normalize_language

# Italian demo literal -> English. Keep entries in sync with eero_client._init_demo_state and the demo
# branches in routers/metrics.py. Brand/person names (TIM, Fastweb, Mario Rossi, Giulia, Marco) stay.
DEMO_STRINGS_EN: Dict[str, str] = {
    # eero nodes
    "Gateway Soggiorno": "Living Room Gateway",
    "Studio & Server Room": "Study & Server Room",
    "Camera da Letto": "Bedroom",
    "Gateway Rack Ufficio": "Office Rack Gateway",
    "Laboratorio & Workstation": "Lab & Workstation",
    # networks / guest networks
    "Casa Rossi Mesh 6E": "Rossi Home Mesh 6E",
    "Casa Rossi - Ospiti": "Rossi Home - Guests",
    "Ufficio & Studio Pro Mesh": "Office & Studio Pro Mesh",
    "Studio - Ospiti Pro": "Studio - Pro Guests",
    # profiles
    "Intrattenimento & Salotto": "Entertainment & Lounge",
    # device nicknames
    "iPad Cucina / Ricette": "Kitchen iPad / Recipes",
    "iPad Pro Studio": "Studio iPad Pro",
    "iPhone Personale": "Personal iPhone",
    "MacBook Pro Lavoro": "Work MacBook Pro",
    "Quadro Elettrico Domotica": "Smart Home Electrical Panel",
    "Sonos Speaker Salone": "Living Room Sonos Speaker",
    "Storage ZFS Primario": "Primary ZFS Storage",
    "Tablet Studio & Lettura": "Study & Reading Tablet",
    "Videocitofono Ingresso": "Entrance Video Doorbell",
    "Dev Workstation Linux": "Linux Dev Workstation",
    "Switch PoE 2.5G Rack": "2.5G PoE Rack Switch",
    "Hypervisor Proxmox VE": "Proxmox VE Hypervisor",
    # demo history / analytics samples (routers/metrics.py)
    "Termostato Soggiorno": "Living Room Thermostat",
    "Sonos Salone": "Living Room Sonos",
    "iPad Cucina": "Kitchen iPad",
    "Shelly Domotica Quadro": "Shelly Smart Panel",
}

# Longest first so "iPad Cucina / Ricette" wins over "iPad Cucina" inside longer sentences.
_PATTERN = re.compile("|".join(re.escape(k) for k in sorted(DEMO_STRINGS_EN, key=len, reverse=True)))


def localize_demo_text(text: str, lang: Optional[str] = None) -> str:
    """Translates known demo literals inside ``text`` for non-Italian readers; Italian is returned as is."""
    if (normalize_language(lang) or "en") == "it" or not text:
        return text
    return _PATTERN.sub(lambda m: DEMO_STRINGS_EN[m.group(0)], text)


def localize_demo_payload(data: Any, lang: Optional[str] = None) -> Any:
    """Recursively translates string values (never keys) of a JSON-like payload."""
    if (normalize_language(lang) or "en") == "it":
        return data
    if isinstance(data, str):
        return localize_demo_text(data, lang)
    if isinstance(data, list):
        return [localize_demo_payload(v, lang) for v in data]
    if isinstance(data, dict):
        return {k: localize_demo_payload(v, lang) for k, v in data.items()}
    return data
