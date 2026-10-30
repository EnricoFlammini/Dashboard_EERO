"""In-app user manual and changelog summary.

Content lives in per-language files under ``app/i18n_locales/<lang>/``:

* ``manual/<NN>_<slug>.md`` - one section per file, ordered by the ``NN`` prefix.
  Each file starts with a ``---`` front-matter block of ``key: value`` lines
  (``id``, ``title``, ``icon``, ``summary``); the Markdown body is the section ``content``.
* ``changelog_summary.md`` - the release-notes summary shown in the changelog modal.

Resolution: ``?lang=`` wins, else the request language (``X-Dashboard-Lang`` header),
else English. A language without a manual directory falls back to English entirely;
a language missing a single section file falls back to the English file for that section.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from app.i18n import DEFAULT_LANGUAGE, LOCALES_DIR, current_language, normalize_language

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manual", tags=["User Manual"])

SECTION_META_KEYS = ("id", "title", "icon", "summary")

_sections_cache: Dict[str, List[Dict[str, Any]]] = {}
_changelog_cache: Dict[str, str] = {}


def _parse_section_file(text: str) -> Optional[Dict[str, Any]]:
    """Parses a '---' front-matter block of 'key: value' lines followed by the Markdown body."""
    if not text.startswith("---"):
        return None
    head, sep, body = text[3:].partition("\n---")
    if not sep:
        return None
    meta: Dict[str, str] = {}
    for line in head.strip().splitlines():
        key, colon, value = line.partition(":")
        if colon:
            meta[key.strip()] = value.strip()
    if not meta.get("id"):
        return None
    section: Dict[str, Any] = {key: meta.get(key, "") for key in SECTION_META_KEYS}
    section["content"] = body.strip()
    return section


def _read_language_sections(lang: str) -> Dict[str, Dict[str, Any]]:
    """Loads every section file of a language, keyed by section id, in file-name order."""
    manual_dir = LOCALES_DIR / lang / "manual"
    sections: Dict[str, Dict[str, Any]] = {}
    if not manual_dir.is_dir():
        return sections
    for path in sorted(manual_dir.glob("*.md")):
        try:
            section = _parse_section_file(path.read_text(encoding="utf-8"))
        except OSError as e:
            logger.error(f"manual: cannot read {path}: {e}")
            continue
        if section is None:
            logger.error(f"manual: invalid front matter in {path}")
            continue
        sections[section["id"]] = section
    return sections


def load_manual_sections(lang: str) -> List[Dict[str, Any]]:
    """Returns the ordered sections for ``lang``; order and the per-section fallback come from English."""
    if lang in _sections_cache:
        return _sections_cache[lang]
    base = _read_language_sections(DEFAULT_LANGUAGE)
    localized = base if lang == DEFAULT_LANGUAGE else _read_language_sections(lang)
    ordered = [localized.get(section_id, section) for section_id, section in base.items()]
    ordered += [section for section_id, section in localized.items() if section_id not in base]
    _sections_cache[lang] = ordered
    return ordered


def load_changelog_summary(lang: str) -> str:
    """Returns the changelog summary for ``lang``, falling back to the English file."""
    if lang in _changelog_cache:
        return _changelog_cache[lang]
    text = ""
    for code in (lang, DEFAULT_LANGUAGE):
        path = LOCALES_DIR / code / "changelog_summary.md"
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            break
    _changelog_cache[lang] = text
    return text


def clear_cache() -> None:
    """Drops the loaded content so the next request re-reads the files (used by tests)."""
    _sections_cache.clear()
    _changelog_cache.clear()


def _resolve_lang(lang: Optional[str]) -> str:
    """``?lang=`` if given, else the request language; languages without a manual map to English."""
    code = (normalize_language(lang) if lang else current_language()) or DEFAULT_LANGUAGE
    return code if (LOCALES_DIR / code / "manual").is_dir() else DEFAULT_LANGUAGE


@router.get("/sections")
async def get_manual_sections(lang: Optional[str] = Query(None)):
    """Restituisce tutti i capitoli del manuale utente nella lingua richiesta."""
    code = _resolve_lang(lang)
    sections = load_manual_sections(code)
    return {
        "status": "success",
        "count": len(sections),
        "language": code,
        "sections": sections
    }


@router.get("/sections/{section_id}")
async def get_manual_section(section_id: str, lang: Optional[str] = Query(None)):
    """Restituisce una specifica sezione del manuale (utilizzata anche per i tooltip contestuali)."""
    code = _resolve_lang(lang)
    section = next((s for s in load_manual_sections(code) if s["id"] == section_id), None)
    if not section:
        return {"status": "error", "message": "Section not found."}
    return {"status": "success", "language": code, "section": section}


@router.get("/changelog")
async def get_changelog(lang: Optional[str] = Query(None)):
    """Restituisce solo i titoli e gli highlight principali delle versioni nella lingua richiesta."""
    from app.config import settings

    code = _resolve_lang(lang)
    return {
        "status": "success",
        "language": code,
        "version": settings.app_version,
        "content": load_changelog_summary(code)
    }
