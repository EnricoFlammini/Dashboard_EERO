"""Server-side translations for API messages, alerts and log entries.

Catalogs live in app/i18n_locales/<lang>/<namespace>.json and are addressed as
"<namespace>.<key>", e.g. tr("dns.sync_completed", count=3). English is the
reference language: a key missing from another language falls back to English,
and a key missing everywhere is returned as-is so the gap is visible.

Language resolution, highest priority first:
  1. an explicit ``lang=`` argument
  2. the language of the current HTTP request (X-Dashboard-Lang header, set
     by the frontend on every /api call, or Accept-Language)
  3. the system/alert language (notification setting), used by background
     jobs such as the poller, scheduler and alert dispatch
"""

import json
import logging
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("en", "it")
DEFAULT_LANGUAGE = "en"
# The two original dashboard languages. Payloads and SQLite rows still carry the
# legacy ``<field>_it`` / ``<field>_en`` pair (derived from the ``<field>_i18n``
# map) for stored data and older clients; new languages only live in the map.
LEGACY_FIELD_LANGUAGES = ("it", "en")
LOCALES_DIR = Path(__file__).resolve().parent / "i18n_locales"

_request_language: ContextVar[Optional[str]] = ContextVar("request_language", default=None)
_system_language: str = DEFAULT_LANGUAGE
_catalogs: Dict[str, Dict[str, str]] = {}


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def normalize_language(value: Optional[str]) -> Optional[str]:
    """Maps 'it', 'it-IT', 'IT_it', 'it-IT,it;q=0.9,en;q=0.8' to a supported code, else None."""
    if not value:
        return None
    for part in value.split(","):
        code = part.split(";", 1)[0].strip().lower().replace("_", "-").split("-", 1)[0]
        if code in SUPPORTED_LANGUAGES:
            return code
    return None


def load_catalogs() -> None:
    """(Re)loads every catalog file; called once at import and by tests."""
    _catalogs.clear()
    for lang in SUPPORTED_LANGUAGES:
        merged: Dict[str, str] = {}
        lang_dir = LOCALES_DIR / lang
        if lang_dir.is_dir():
            for path in sorted(lang_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as e:
                    logger.error(f"i18n: cannot load {path}: {e}")
                    continue
                for key, text in data.items():
                    merged[f"{path.stem}.{key}"] = text
        _catalogs[lang] = merged


def set_request_language(lang: Optional[str]):
    """Binds the language for the current request context; returns a reset token."""
    return _request_language.set(normalize_language(lang))


def reset_request_language(token) -> None:
    _request_language.reset(token)


def set_system_language(lang: Optional[str]) -> None:
    """Updates the cached system/alert language used outside of requests."""
    global _system_language
    _system_language = normalize_language(lang) or DEFAULT_LANGUAGE


def get_system_language() -> str:
    return _system_language


def current_language() -> str:
    return _request_language.get() or _system_language


def tr(key: str, lang: Optional[str] = None, **params: Any) -> str:
    """Translates ``key`` into ``lang`` (or the current language) and fills ``{param}`` placeholders."""
    active = normalize_language(lang) or current_language()
    text = _catalogs.get(active, {}).get(key)
    if text is None:
        text = _catalogs.get(DEFAULT_LANGUAGE, {}).get(key)
    if text is None:
        logger.warning(f"i18n: missing key '{key}'")
        return key
    return text.format_map(_SafeDict(params)) if params else text


def _param_for(value: Any, lang: str) -> Any:
    """A param given as a per-language map ({"en": ..., "it": ...}) is resolved for ``lang``."""
    if isinstance(value, dict) and value and all(k in SUPPORTED_LANGUAGES for k in value):
        return value.get(lang, value.get(DEFAULT_LANGUAGE, ""))
    return value


def tr_all(key: str, **params: Any) -> Dict[str, str]:
    """Returns {lang: text} for every language in SUPPORTED_LANGUAGES.

    Payloads carry these maps as ``<field>_i18n`` so the frontend can pick the
    viewer's language. A param may itself be a per-language map (e.g. a list of
    names joined with a localized fallback) and is resolved language by language.
    """
    return {
        lang: tr(key, lang=lang, **{k: _param_for(v, lang) for k, v in params.items()})
        for lang in SUPPORTED_LANGUAGES
    }


def localized_fields(field: str, text_i18n: Dict[str, str]) -> Dict[str, Any]:
    """Expands one per-language map into the payload fields a client may read.

    ``<field>`` is English, ``<field>_i18n`` the full map (every language in
    SUPPORTED_LANGUAGES) and ``<field>_it`` / ``<field>_en`` the legacy pair kept
    for older clients and stored data. Add a language to SUPPORTED_LANGUAGES and
    it appears in the map with no change here.
    """
    english = text_i18n.get(DEFAULT_LANGUAGE) or next(iter(text_i18n.values()), "")
    out: Dict[str, Any] = {field: english, f"{field}_i18n": dict(text_i18n)}
    for lang in LEGACY_FIELD_LANGUAGES:
        out[f"{field}_{lang}"] = text_i18n.get(lang) or english
    return out


def _jsonable(value: Any) -> Any:
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def log_event(logger: logging.Logger, level: int, key: str, /, *, exc_info: Any = False, **params: Any) -> None:
    """Logs an operator-facing event that the Logs page can show in the viewer's language.

    The log file and the stored message are always English (stable for search,
    downloads and bug reports); the key and params ride along on the record so
    the SQLite log handler can persist them and the logs API can re-render the
    message in the requesting user's language.
    """
    clean = {k: _jsonable(v) for k, v in params.items()}
    logger.log(level, tr(key, lang="en", **clean), exc_info=exc_info, extra={"i18n": {"key": key, "params": clean}})


def localize_log_entry(entry: Dict[str, Any], lang: Optional[str] = None) -> Dict[str, Any]:
    """Re-renders a stored log row in ``lang`` (or the current language) when it carries an i18n key."""
    raw = entry.get("details_json")
    if not raw:
        return entry
    try:
        details = json.loads(raw)
    except (TypeError, ValueError):
        return entry
    meta = details.pop("i18n", None) if isinstance(details, dict) else None
    if not isinstance(meta, dict) or not meta.get("key"):
        return entry
    localized = dict(entry)
    localized["message"] = tr(meta["key"], lang=lang, **(meta.get("params") or {}))
    localized["details_json"] = json.dumps(details) if details else None
    return localized


load_catalogs()
