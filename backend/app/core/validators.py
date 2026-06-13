"""
Centralised validators for RecruitAI.

Pure deterministic functions that normalise / validate data extracted from
CVs (by the LLM) and from user input (in API routes) BEFORE it reaches the
database or the frontend. The LLM produces text that varies in case,
formatting, completeness and locale; this module reduces it to a single
canonical shape so the UI never has to defend itself.

Design rules
------------
1. Every function returns ``None`` (or an empty value) when input is
   missing or unparseable — never raises. Pydantic ``field_validator``
   should raise explicitly if a field is required and the validator
   returned ``None``.
2. Functions are pure: no DB access, no network, no LLM calls. Safe to
   call from anywhere, including Pydantic validators that run during
   schema construction.
3. Libraries chosen are all 100 % open-source (MIT / Apache / BSD /
   LGPL / MPL). See ``backend/requirements.txt`` for the full list and
   justification.

Quick reference
---------------
- ``clean_text``         — fix mojibake + NFC + strip zero-width (ftfy)
- ``normalize_phone``    — E.164 via Google libphonenumber (PE default)
- ``normalize_email``    — RFC 5322 + optional MX deliverability check
- ``normalize_linkedin`` — canonical ``linkedin.com/in/<slug>``
- ``normalize_github``   — canonical ``github.com/<user>``
- ``normalize_http_url`` — generic http(s) URL with TLD check
- ``normalize_person_name`` — Title Case respecting hispanic particles
- ``is_valid_dni_pe``    — Peruvian DNI (8 digits)
- ``is_valid_ruc_pe``    — Peruvian RUC with SUNAT checksum
- ``normalize_country``  — ISO 3166-1 alpha-2 ("Perú" → "PE")
- ``normalize_city``     — offline city existence check
- ``normalize_cefr``     — language level to A1-C2 ("avanzado" → "C1")
- ``normalize_currency`` — ISO 4217 ("S/" → "PEN")
- ``validate_date_range``— end ≥ start, no future start, sane duration
- ``fuzzy_pick``         — pick best match from a candidate list with rapidfuzz
- ``validate_pdf_bytes`` — MIME + structural PDF safety (rejects /JS, /Launch)
- ``validate_docx_bytes``— MIME + macro detection (rejects DOCX with VBA)
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date, timedelta
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Text cleanup
# ─────────────────────────────────────────────────────────────────────────────

# Zero-width and bidi-control characters frequently used in prompt-injection
# steganography. Already stripped at the PDF layer; we keep a defensive pass
# here because text can also reach us via JSON API or DOCX.
_INVISIBLE_RE = re.compile(
    r"[​-\u200F\u202A-\u202E⁠-⁯﻿]"
)


def clean_text(value: Optional[str]) -> Optional[str]:
    """Fix mojibake, normalise to NFC, strip invisible Unicode.

    Returns ``None`` when input is empty or only whitespace. Safe to call
    on any string coming from PDF / DOCX / LLM / user input.
    """
    if not value:
        return None
    try:
        import ftfy  # local import keeps the module importable in tests
        fixed = ftfy.fix_text(value)
    except ImportError:  # graceful degradation if ftfy isn't installed
        fixed = value
    fixed = unicodedata.normalize("NFC", fixed)
    fixed = _INVISIBLE_RE.sub("", fixed)
    fixed = fixed.strip()
    return fixed or None


# ─────────────────────────────────────────────────────────────────────────────
# Phone numbers — Google libphonenumber via `phonenumbers`
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PHONE_REGION = "PE"  # AGENTS.md §2 — single-tenant LATAM PYME


def normalize_phone(
    raw: Optional[str], region: str = DEFAULT_PHONE_REGION
) -> Optional[str]:
    """Return phone in E.164 (``+51999111222``) or ``None`` if invalid.

    Accepts numbers with or without country code. When the country code
    is absent, ``region`` (default ``"PE"``) is used as the assumed
    default. Garbage (``"N/A"``, free text) returns ``None``.
    """
    if not raw:
        return None
    candidate = clean_text(raw) or ""
    # Strip everything except digits, +, and whitespace; libphonenumber
    # is tolerant but we don't want emoji or accidental letters from OCR.
    candidate = re.sub(r"[^\d+\s\-\(\)]", "", candidate)
    if not candidate or not re.search(r"\d", candidate):
        return None
    try:
        import phonenumbers
        from phonenumbers import NumberParseException, PhoneNumberFormat

        parsed = phonenumbers.parse(candidate, region)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    except (ImportError, NumberParseException):
        return None
    except Exception as exc:  # pragma: no cover
        logger.debug("phone parse fallback for %r: %s", raw, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Email — RFC 5322 + optional MX (uses `email-validator`, same lib Pydantic uses)
# ─────────────────────────────────────────────────────────────────────────────


def normalize_email(
    raw: Optional[str], check_deliverability: bool = False
) -> Optional[str]:
    """Return normalised email (lowercase domain, IDN canonical) or ``None``.

    ``check_deliverability=True`` performs a DNS MX lookup. Disabled by
    default because it adds 50-300 ms per call; enable in batch jobs but
    keep it off in request-handling paths. The function never raises.
    """
    if not raw:
        return None
    candidate = (clean_text(raw) or "").strip()
    if not candidate:
        return None
    try:
        from email_validator import EmailNotValidError, validate_email

        info = validate_email(candidate, check_deliverability=check_deliverability)
        return info.normalized
    except ImportError:
        # Fallback: minimal RFC-ish check.
        return candidate if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate) else None
    except EmailNotValidError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# URLs: LinkedIn, GitHub, generic http(s)
# ─────────────────────────────────────────────────────────────────────────────

_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/(?:in|pub|profile)/([\w\-%.]+)",
    re.IGNORECASE,
)
_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([\w\-.]+)(?:/[^/\s]*)?",
    re.IGNORECASE,
)
_URL_RE = re.compile(
    r"^https?://[\w\-.]+\.[a-z]{2,}(?:/[\w\-./%?&=#~+]*)?$",
    re.IGNORECASE,
)


def normalize_linkedin(raw: Optional[str]) -> Optional[str]:
    """Return canonical ``https://www.linkedin.com/in/<slug>`` or ``None``.

    Accepts regional variants (``pe.linkedin.com``), legacy ``/pub/`` and
    ``/profile/`` paths, and bare slugs. Never makes HTTP requests —
    LinkedIn returns ``HTTP 999`` to unauthenticated probes, so we only
    validate format.
    """
    if not raw:
        return None
    candidate = (clean_text(raw) or "").strip().rstrip("/")
    if not candidate:
        return None
    match = _LINKEDIN_RE.search(candidate)
    if not match:
        return None
    slug = match.group(1).strip().rstrip("/")
    if not slug or len(slug) < 2:
        return None
    return f"https://www.linkedin.com/in/{slug}"


def normalize_github(raw: Optional[str]) -> Optional[str]:
    """Return canonical ``https://github.com/<user>`` or ``None``."""
    if not raw:
        return None
    candidate = (clean_text(raw) or "").strip().rstrip("/")
    if not candidate:
        return None
    match = _GITHUB_RE.search(candidate)
    if not match:
        return None
    user = match.group(1).strip().rstrip("/")
    # GitHub usernames are 1-39 chars, alphanumeric + hyphen, no leading hyphen.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,38})", user):
        return None
    return f"https://github.com/{user}"


def normalize_http_url(raw: Optional[str]) -> Optional[str]:
    """Return a normalised http(s) URL string or ``None`` if invalid."""
    if not raw:
        return None
    candidate = (clean_text(raw) or "").strip().rstrip("/")
    if not candidate:
        return None
    if not candidate.lower().startswith(("http://", "https://")):
        candidate = "https://" + candidate
    return candidate if _URL_RE.match(candidate) else None


# ─────────────────────────────────────────────────────────────────────────────
# Person names — hispanic-aware capitalisation
# ─────────────────────────────────────────────────────────────────────────────

# Spanish particles that should stay lowercase except when at the start
# of a name (then capitalised). Aligned with RAE & Fundéu recommendations.
_HISPANIC_PARTICLES = {
    "de", "del", "la", "las", "los", "y", "e",
    "da", "do", "das", "dos",   # portuguese variants
    "van", "von", "der", "den",  # european particles seen in immigrant names
}


def normalize_person_name(raw: Optional[str]) -> Optional[str]:
    """Return a person's name with smart Title Case.

    Examples:
        "juan carlos de la cruz"  → "Juan Carlos de la Cruz"
        "MARÍA DEL CARMEN GARCÍA" → "María del Carmen García"
        "  juan  "                → "Juan"
    """
    if not raw:
        return None
    text = clean_text(raw)
    if not text:
        return None
    # Collapse internal whitespace and lowercase first to get a clean base.
    tokens = re.split(r"\s+", text.lower())
    if not tokens:
        return None
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if not tok:
            continue
        # Particles stay lowercase except as first token.
        if i > 0 and tok in _HISPANIC_PARTICLES:
            out.append(tok)
            continue
        # Capitalise after apostrophe / hyphen too: "O'Neil", "Jean-Paul".
        out.append(
            re.sub(
                r"(^|[-'’])(\w)",
                lambda m: m.group(1) + m.group(2).upper(),
                tok,
            )
        )
    return " ".join(out) or None


# ─────────────────────────────────────────────────────────────────────────────
# Peruvian DNI (8 digits) and RUC (11 digits with SUNAT checksum)
# ─────────────────────────────────────────────────────────────────────────────

_DNI_RE = re.compile(r"\d{8}")
_RUC_PREFIX_VALID = {"10", "15", "17", "20"}
_RUC_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def is_valid_dni_pe(raw: Optional[str]) -> bool:
    """RENIEC DNI: 8 digits. The verifier digit (9th char) does not appear
    in CVs, so we only validate length and that all are digits."""
    if not raw:
        return False
    cleaned = re.sub(r"\D", "", raw)
    return bool(_DNI_RE.fullmatch(cleaned))


def is_valid_ruc_pe(raw: Optional[str]) -> bool:
    """SUNAT RUC: 11 digits with modulo-11 checksum.

    First two digits must be one of {10, 15, 17, 20}:
      10 = persona natural, 15 = no domiciliado, 17 = sucesión indivisa,
      20 = persona jurídica.
    """
    if not raw:
        return False
    cleaned = re.sub(r"\D", "", raw)
    if len(cleaned) != 11 or cleaned[:2] not in _RUC_PREFIX_VALID:
        return False
    total = sum(int(d) * w for d, w in zip(cleaned[:10], _RUC_WEIGHTS))
    check = 11 - (total % 11)
    check = {10: 0, 11: 1}.get(check, check)
    return check == int(cleaned[10])


# ─────────────────────────────────────────────────────────────────────────────
# Country / city — ISO 3166-1 (pycountry) + geonamescache
# ─────────────────────────────────────────────────────────────────────────────


def normalize_country(raw: Optional[str]) -> Optional[str]:
    """Return ISO 3166-1 alpha-2 ("PE", "MX", "CO") or ``None``.

    Tolerant of accents and case ("Perú", "PERU", "peru" → "PE").
    """
    if not raw:
        return None
    candidate = (clean_text(raw) or "").strip()
    if not candidate:
        return None
    try:
        import pycountry

        # Direct match first (fast path).
        c = pycountry.countries.get(alpha_2=candidate.upper()) or \
            pycountry.countries.get(alpha_3=candidate.upper()) or \
            pycountry.countries.get(name=candidate.title())
        if c:
            return c.alpha_2
        # Fuzzy search (handles "Perú", "United States of America", etc.).
        matches = pycountry.countries.search_fuzzy(candidate)
        return matches[0].alpha_2 if matches else None
    except (ImportError, LookupError):
        return None
    except Exception:  # pragma: no cover — pycountry can raise on weird input
        return None


_GC_CACHE: object | None = None


def _get_gc():
    """Lazy-init geonamescache to keep startup time low."""
    global _GC_CACHE
    if _GC_CACHE is None:
        try:
            import geonamescache

            _GC_CACHE = geonamescache.GeonamesCache()
        except ImportError:
            _GC_CACHE = False  # mark "tried and failed"
    return _GC_CACHE or None


def normalize_city(
    raw: Optional[str], country_code: Optional[str] = None
) -> Optional[str]:
    """Return canonical city name if it exists in the offline geonames db.

    ``country_code`` (ISO 3166-1 alpha-2) restricts the search — preferred
    because city names repeat across countries ("Lima" is a city in PE,
    OH-USA and PY).
    """
    if not raw:
        return None
    candidate = (clean_text(raw) or "").strip()
    if not candidate:
        return None
    gc = _get_gc()
    if gc is None:
        return candidate  # geonamescache unavailable — return cleaned text
    matches = gc.get_cities_by_name(candidate.title())
    if not matches:
        return None
    if country_code:
        cc = country_code.upper()
        for item in matches:
            for _, city in item.items():
                if city.get("countrycode") == cc:
                    return city.get("name")
        return None
    # Return the most populous match.
    best = max(
        (next(iter(m.values())) for m in matches),
        key=lambda c: c.get("population", 0),
    )
    return best.get("name")


# ─────────────────────────────────────────────────────────────────────────────
# Language level — CEFR (A1-C2)
# ─────────────────────────────────────────────────────────────────────────────

# Council of Europe canonical levels. Free text on CVs in Spanish/English
# is mapped to the closest CEFR. Order matters for fuzzy fallback: most
# specific phrases first.
_CEFR_MAP: dict[str, str] = {
    # A1 — Beginner
    "a1": "A1", "principiante": "A1", "beginner": "A1", "starter": "A1",
    # A2 — Elementary
    "a2": "A2", "elemental": "A2", "elementary": "A2", "basico": "A2",
    "básico": "A2", "basic": "A2",
    # B1 — Intermediate
    "b1": "B1", "intermedio": "B1", "intermediate": "B1",
    "pre-intermedio": "B1", "pre intermedio": "B1",
    # B2 — Upper-Intermediate
    "b2": "B2", "intermedio alto": "B2", "upper intermediate": "B2",
    "upper-intermediate": "B2", "independiente": "B2",
    # C1 — Advanced
    "c1": "C1", "avanzado": "C1", "advanced": "C1", "fluent": "C1",
    "fluido": "C1", "fluente": "C1", "competente": "C1",
    # C2 — Proficient / Native
    "c2": "C2", "nativo": "C2", "native": "C2", "bilingüe": "C2",
    "bilingue": "C2", "proficient": "C2", "proficiente": "C2",
    "maestria": "C2",
}


def normalize_cefr(raw: Optional[str]) -> Optional[str]:
    """Map free-text language level to CEFR (A1-C2). ``None`` if unknown."""
    if not raw:
        return None
    key = (clean_text(raw) or "").strip().lower()
    if not key:
        return None
    if key in _CEFR_MAP:
        return _CEFR_MAP[key]
    # Fuzzy fallback — handles typos / extra words like "nivel avanzado".
    try:
        from rapidfuzz import fuzz, process

        match = process.extractOne(
            key, list(_CEFR_MAP.keys()), scorer=fuzz.WRatio, score_cutoff=82
        )
        if match:
            return _CEFR_MAP[match[0]]
    except ImportError:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Currency — ISO 4217 ("S/" → "PEN")
# ─────────────────────────────────────────────────────────────────────────────

_CURRENCY_SYMBOLS: dict[str, str] = {
    # Peru
    "s/": "PEN", "s/.": "PEN", "sol": "PEN", "soles": "PEN", "pen": "PEN",
    # USA / generic dollar
    "$": "USD", "us$": "USD", "usd": "USD", "dollars": "USD", "dólares": "USD",
    "dolares": "USD",
    # Europe
    "€": "EUR", "eur": "EUR", "euros": "EUR",
    # UK
    "£": "GBP", "gbp": "GBP",
    # LATAM common
    "ars": "ARS", "$ars": "ARS",
    "clp": "CLP",
    "cop": "COP",
    "mxn": "MXN", "mx$": "MXN",
    "brl": "BRL", "r$": "BRL",
}


def normalize_currency(raw: Optional[str]) -> Optional[str]:
    """Return ISO 4217 code ("PEN", "USD", ...) or ``None``."""
    if not raw:
        return None
    key = (clean_text(raw) or "").strip().lower()
    if not key:
        return None
    if key in _CURRENCY_SYMBOLS:
        return _CURRENCY_SYMBOLS[key]
    # Confirm against pycountry's ISO 4217 table for exotic 3-letter codes.
    try:
        import pycountry

        currency = pycountry.currencies.get(alpha_3=key.upper())
        return currency.alpha_3 if currency else None
    except ImportError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Date range validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_date_range(
    start: Optional[date],
    end: Optional[date],
    *,
    max_years: int = 50,
    allow_future_end: bool = False,
) -> tuple[bool, Optional[str]]:
    """Return ``(ok, error_message)``.

    Rules
    -----
    - ``start`` cannot be in the future (a candidate didn't start working
      in 2099).
    - ``end`` cannot be before ``start``.
    - ``end`` cannot exceed ``max_years`` past ``start`` (defensive cap;
      a single role doesn't last 80 years).
    - ``allow_future_end`` lets education entries with anticipated
      graduation dates pass.
    """
    if start is None:
        return True, None
    today = date.today()
    if start > today:
        return False, "La fecha de inicio está en el futuro."
    if end is not None:
        if end < start:
            return False, "La fecha fin es anterior a la fecha de inicio."
        if not allow_future_end and end > today:
            return False, "La fecha fin está en el futuro."
        if end - start > timedelta(days=365 * max_years):
            return False, f"Duración mayor a {max_years} años."
    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy matching helper (rapidfuzz)
# ─────────────────────────────────────────────────────────────────────────────


def fuzzy_pick(
    query: Optional[str],
    candidates: Iterable[str],
    *,
    score_cutoff: int = 85,
) -> Optional[str]:
    """Return the best fuzzy match from ``candidates`` or ``None``.

    Useful for normalising skills with typos ("Phyton" → "Python") or
    institutional acronyms ("PUCP" → "Pontificia Universidad Católica del
    Perú") when the canonical list is small enough to scan in memory.
    For large catalogues (>10k items) use Qdrant + embeddings instead.
    """
    if not query:
        return None
    try:
        from rapidfuzz import fuzz, process

        match = process.extractOne(
            query, list(candidates), scorer=fuzz.WRatio, score_cutoff=score_cutoff
        )
        return match[0] if match else None
    except ImportError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Upload safety — PDF and DOCX structural checks
# ─────────────────────────────────────────────────────────────────────────────

# PDF object keys that should NOT appear in a legitimate CV. They enable
# code execution at open time (Acrobat / Foxit / older readers).
_PDF_DANGEROUS_KEYS = (
    "/JS",          # JavaScript action
    "/JavaScript",
    "/OpenAction",  # auto-run on open
    "/AA",          # additional actions (page open, focus, etc.)
    "/Launch",      # external executable
    "/EmbeddedFile",  # arbitrary file payload
    "/SubmitForm",  # form data exfiltration
)


def validate_pdf_bytes(content: bytes) -> tuple[bool, Optional[str]]:
    """Validate uploaded PDF content. ``(ok, reason_if_rejected)``.

    Checks:
      1. MIME magic bytes match ``application/pdf``.
      2. The PDF opens without error in pikepdf (rejects truncated /
         malformed payloads that crash downstream extractors).
      3. The PDF does NOT contain ``/JS``, ``/JavaScript``,
         ``/OpenAction``, ``/Launch``, ``/EmbeddedFile`` or ``/AA``
         entries — none of which a real CV needs.

    The existing PDF security scan in ``document_extractor.py`` covers
    white text, micro-fonts and hidden layers; this function adds the
    structural layer that ``pymupdf`` alone does not provide.
    """
    if not content or len(content) < 32:
        return False, "Archivo PDF vacío o demasiado pequeño."

    # ── 1. MIME magic ────────────────────────────────────────────────────────
    try:
        import magic  # python-magic

        mime = magic.from_buffer(content[:2048], mime=True)
        if mime != "application/pdf":
            return False, f"El archivo no es un PDF real (detectado: {mime})."
    except ImportError:
        # Soft fallback to header sniff if libmagic isn't available.
        if not content.startswith(b"%PDF-"):
            return False, "El archivo no es un PDF real."
    except Exception as exc:  # pragma: no cover
        logger.debug("python-magic failed, falling back to header sniff: %s", exc)
        if not content.startswith(b"%PDF-"):
            return False, "El archivo no es un PDF real."

    # ── 2. & 3. Structural inspection with pikepdf ───────────────────────────
    # Busca las claves peligrosas como CLAVES reales de diccionario PDF, no
    # como subcadenas del objeto serializado. El scan por subcadena rechazaba
    # CVs legítimos: las fuentes embebidas con subset se llaman
    # ``/AAAAAB+Calibri`` y contienen "/AA" sin ser un Additional-Actions
    # dict (falso positivo confirmado con CVs reales en junio 2026).
    try:
        import pikepdf

        def _scan_obj(obj, depth: int = 0) -> Optional[str]:
            """Devuelve la clave peligrosa si ``obj`` la declara (recursivo).

            Recorre diccionarios/arrays directos anidados; las referencias
            indirectas se omiten porque ``pdf.objects`` ya las visita.
            """
            if depth > 30:
                return None
            if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                for key in _PDF_DANGEROUS_KEYS:
                    if key in obj:
                        return key
                for _k, v in obj.items():
                    if getattr(v, "is_indirect", False):
                        continue
                    hit = _scan_obj(v, depth + 1)
                    if hit:
                        return hit
            elif isinstance(obj, pikepdf.Array):
                for v in obj:
                    if getattr(v, "is_indirect", False):
                        continue
                    hit = _scan_obj(v, depth + 1)
                    if hit:
                        return hit
            return None

        with pikepdf.open(io.BytesIO(content)) as pdf:
            # El trailer es un dict directo (su /Root indirecto se visita
            # abajo); /OpenAction puede vivir aquí.
            hit = _scan_obj(pdf.trailer)
            if hit:
                return False, f"PDF rechazado: contiene {hit} (riesgo activo)."
            for obj in pdf.objects:
                try:
                    hit = _scan_obj(obj)
                except Exception:
                    continue
                if hit:
                    return False, f"PDF rechazado: contiene {hit} (riesgo activo)."
    except ImportError:
        # pikepdf missing → trust the existing pymupdf scan downstream.
        return True, None
    except Exception as exc:
        return False, f"PDF malformado: {exc}"

    return True, None


def validate_docx_bytes(content: bytes) -> tuple[bool, Optional[str]]:
    """Validate uploaded DOCX content. ``(ok, reason_if_rejected)``.

    Checks:
      1. MIME magic bytes match an Office Open XML document.
      2. The file is not a VBA-enabled DOCM (``application/vnd.ms-word.*``).
      3. No VBA macro project is embedded.

    A legitimate CV never needs macros; rejecting them eliminates a
    long-standing malware delivery vector.
    """
    if not content or len(content) < 64:
        return False, "Archivo DOCX vacío o demasiado pequeño."

    # ── 1./2. MIME magic ─────────────────────────────────────────────────────
    try:
        import magic

        mime = magic.from_buffer(content[:4096], mime=True)
        # DOCX is a ZIP container; libmagic typically reports
        # "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        # but on older systems can report "application/zip" or "application/octet-stream".
        # We accept those provided the file extension was already validated upstream.
        allowed_mimes = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
        }
        if mime not in allowed_mimes:
            return False, f"El archivo no es un DOCX válido (detectado: {mime})."
        if mime == "application/vnd.ms-word.document.macroEnabled.12":
            return False, "DOCM (con macros) no permitido."
    except ImportError:
        # Soft fallback — DOCX always starts with PK\x03\x04 (ZIP magic).
        if not content.startswith(b"PK\x03\x04"):
            return False, "El archivo no es un DOCX válido."
    except Exception as exc:  # pragma: no cover
        logger.debug("python-magic failed for DOCX: %s", exc)

    # ── 3. Macro detection via oletools ──────────────────────────────────────
    try:
        from oletools.olevba import VBA_Parser

        parser = VBA_Parser("upload.docx", data=content)
        try:
            if parser.detect_vba_macros():
                return False, "DOCX rechazado: contiene macros VBA."
        finally:
            parser.close()
    except ImportError:
        # oletools missing → can't enforce; let it through and log.
        logger.warning("oletools not installed — macro check skipped.")
    except Exception as exc:
        # A parse error is suspicious for a CV but not necessarily malicious.
        # Reject conservatively.
        return False, f"DOCX malformado: {exc}"

    return True, None
