"""
Document Extractor Adapter
Converts documents to plain text for LLM processing.

PDF extraction strategy (two layers, automatic fallback):
  1. pymupdf4llm.to_markdown() — primary extractor.
     Produces structured Markdown with ## section headers (font-size analysis),
     correct multi-column layout, table detection, and automatic OCR for
     scanned pages (requires Tesseract, already installed in the container).
  2. Custom hybrid extractor (fallback) — used when pymupdf4llm returns
     suspiciously little text (< 80 chars/page) or raises an exception.
     Uses PyMuPDF word-level bounding-box reconstruction with COL_GAP=35 for
     borderless column detection plus find_tables() for explicit grids.

After primary extraction, ``_recover_dropped_contacts()`` runs a safety-net
pass that (a) joins emails fragmented by icon glyphs (e.g. "user ° @host.com")
and (b) appends any email/phone present in the raw text layer but missing
from the markdown output — pymupdf4llm sometimes drops contact lines wedged
inside icon-decorated header boxes.

DOCX → MarkItDown (Microsoft library via mammoth)
Only PDF and DOCX are supported; other formats raise DocumentParsingError.
"""
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Tuple

import pymupdf
from markitdown import MarkItDown, StreamInfo

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".docx"}

# MarkItDown is stateless — one instance is enough
_markitdown = MarkItDown(enable_plugins=False)


def _extract_page_text(page: pymupdf.Page) -> str:
    """
    Extract text from a single PDF page using a hybrid strategy:

    1. Table regions  → `page.find_tables()` (PyMuPDF ≥ 1.23).
       Table cells are correctly grouped per row even when cell text sits at
       different y-positions within the same row (e.g. multi-line cell in col 1
       pushes col 4 text lower in the PDF stream).  Output format:
           col1 | col2 | col3 | col4 | col5

    2. Non-table text → word-level bounding-box reconstruction.
       Words are bucketed by approximate y-center (LINE_TOL=8px), sorted
       left-to-right within each line, and blank lines are inserted between
       visual sections (GAP_THR=24 → effective ≥32px gap).

    Both sets of segments are then merged and sorted by their top y-coordinate
    so output appears in natural reading order.
    """
    LINE_TOL = 8   # words within ±8px in y → same visual line
    GAP_THR  = 24  # effective cut at ~32px real gap

    # ── 1. Table extraction ──────────────────────────────────────────────────
    table_bboxes: list[tuple[float, float, float, float]] = []
    table_segments: list[tuple[float, str]] = []   # (page_y0, formatted_text)

    try:
        for tab in page.find_tables():
            data = tab.extract()
            if not data:
                continue
            rows: list[str] = []
            for row in data:
                cells = [
                    str(c).replace("\n", " ").strip() if c is not None else ""
                    for c in row
                ]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                x0, y0, x1, y1 = tab.bbox
                table_bboxes.append((x0, y0, x1, y1))
                table_segments.append((y0, "\n".join(rows)))
    except Exception:
        pass  # find_tables unavailable or failed — fall through to word-only

    # ── 2. Word-level extraction (skip words inside detected tables) ─────────
    def _in_table(wx0: float, wy0: float, wx1: float, wy1: float) -> bool:
        cx, cy = (wx0 + wx1) / 2, (wy0 + wy1) / 2
        return any(
            tx0 <= cx <= tx1 and ty0 <= cy <= ty1
            for tx0, ty0, tx1, ty1 in table_bboxes
        )

    # Minimum x-gap (in points) to treat a space as a column separator.
    # A4/Letter columns in CVs are typically 50-150 pt apart; normal word
    # spacing is 2-6 pt.  35 pt ≈ 1.2 cm — safe threshold for both sizes.
    COL_GAP = 35

    words = page.get_text("words")   # (x0, y0, x1, y1, word, block_no, line_no, word_no)
    line_map: dict[int, list[tuple[float, float, str, float]]] = {}  # bucket → [(x0, x1, word, y0)]
    for x0, y0, x1, y1, word, *_ in words:
        if table_bboxes and _in_table(x0, y0, x1, y1):
            continue
        y_mid = (y0 + y1) / 2
        bucket = round(y_mid / LINE_TOL) * LINE_TOL
        line_map.setdefault(bucket, []).append((x0, x1, word, y0))

    def _line_to_text(items: list[tuple[float, float, str, float]]) -> str:
        """
        Join words in a visual line.  When consecutive word-end → word-start
        gap exceeds COL_GAP we insert ' | ' to signal a column boundary.
        This lets the LLM correctly parse borderless multi-column layouts
        (e.g. education tables without visible grid lines).
        """
        ordered = sorted(items, key=lambda w: w[0])
        if len(ordered) < 2:
            return " ".join(w[2] for w in ordered)
        parts: list[list[str]] = [[]]
        prev_x1 = ordered[0][1]
        parts[-1].append(ordered[0][2])
        for x0, x1, word, _ in ordered[1:]:
            if (x0 - prev_x1) > COL_GAP:
                parts.append([])
            parts[-1].append(word)
            prev_x1 = x1
        return " | ".join(" ".join(p) for p in parts) if len(parts) > 1 else " ".join(parts[0])

    # Group word-lines into paragraph segments (split on GAP_THR gaps)
    text_segments: list[tuple[float, str]] = []
    para_lines: list[str] = []
    para_y0 = 0.0
    prev_bucket: int | None = None

    for bucket in sorted(line_map):
        if prev_bucket is not None and (bucket - prev_bucket) > GAP_THR:
            if para_lines:
                text_segments.append((para_y0, "\n".join(para_lines)))
            para_lines = []
        if not para_lines:
            para_y0 = min(w[3] for w in line_map[bucket])
        para_lines.append(_line_to_text(line_map[bucket]))
        prev_bucket = bucket

    if para_lines:
        text_segments.append((para_y0, "\n".join(para_lines)))

    # ── 3. Merge all segments in reading order (top → bottom) ────────────────
    all_segments = text_segments + table_segments
    all_segments.sort(key=lambda s: s[0])

    if not all_segments:
        return ""

    return "\n\n".join(text for _, text in all_segments).strip()


def _is_scanned_pdf(doc: pymupdf.Document) -> bool:
    """Return True if the PDF has very little selectable text (likely scanned image)."""
    total_chars = sum(len(page.get_text().strip()) for page in doc)
    avg_chars = total_chars / max(doc.page_count, 1)
    return avg_chars < 80  # < 80 chars/page → almost certainly a scanned image


_SCANNED_WARNING = (
    "[AVISO: Este PDF parece ser escaneado y no contiene texto digital seleccionable. "
    "La extracción automática puede ser incompleta o incorrecta. "
    "Se recomienda solicitar el CV en formato PDF digital o DOCX.]\n\n"
)

# ── Zero-width and Unicode invisible characters used in steganographic attacks ─
# Ref: GlassWorm campaign (Oct 2025), OWASP LLM01:2025
_INVISIBLE_UNICODE = (
    "\u200b"  # Zero-Width Space
    "\u200c"  # Zero-Width Non-Joiner
    "\u200d"  # Zero-Width Joiner
    "\u200e"  # Left-to-Right Mark
    "\u200f"  # Right-to-Left Mark
    "\u202a"  # Left-to-Right Embedding
    "\u202b"  # Right-to-Left Embedding
    "\u202c"  # Pop Directional Formatting
    "\u202d"  # Left-to-Right Override
    "\u202e"  # Right-to-Left Override (RTL flip attack)
    "\u2060"  # Word Joiner
    "\u2061"  # Function Application
    "\u2062"  # Invisible Times
    "\u2063"  # Invisible Separator
    "\u2064"  # Invisible Plus
    "\ufeff"  # Zero-Width No-Break Space (BOM used mid-text)
    # Unicode Tag block U+E0000–U+E007F — used for steganographic payloads
)
_INVISIBLE_SET = set(_INVISIBLE_UNICODE)


class SecurityScanResult:
    """
    Result of a document security scan.

    Carries both the severity of findings and the hidden text
    fragments that were extracted (to feed into injection pattern checks).
    """
    __slots__ = ("warnings", "hidden_text_fragments")

    def __init__(self):
        self.warnings: list[str] = []
        self.hidden_text_fragments: list[str] = []

    @property
    def has_findings(self) -> bool:
        return bool(self.warnings)


def _scan_pdf_security(doc: pymupdf.Document) -> SecurityScanResult:
    """
    Scan a PDF for common document-level attack vectors.

    Documented attack vectors this covers:
    - White / invisible text (Kai Greshake "Inject My PDF", 2023;
      Schneier on Security, 2023; NYT college student story, 2023)
    - Font size ≤ 1pt (steganographic micro-text)
    - Text positioned outside visible page bounds (off-page injection)
    - Zero-width and RTL Unicode characters
    - PDF metadata field injection (Author, Subject, Keywords, Comments)
    - PDF JavaScript annotations
    - Hidden Optional Content Groups (invisible layers)

    Returns SecurityScanResult with warnings and any hidden text
    fragments so the injection pattern scanner can check them too.
    """
    result = SecurityScanResult()

    # ── 1. Check PDF metadata fields ─────────────────────────────────────────
    meta = doc.metadata or {}
    for field in ("author", "subject", "keywords", "creator", "producer"):
        value = meta.get(field, "") or ""
        if len(value) > 5:
            result.hidden_text_fragments.append(f"[META:{field}] {value}")

    # ── 2. Check for embedded JavaScript ──────────────────────────────────────
    try:
        if doc.get_javascript():
            result.warnings.append("PDF contiene JavaScript embebido (posible ataque)")
    except Exception:
        pass

    # ── 3. Scan pages for hidden text ─────────────────────────────────────────
    for page_idx, page in enumerate(doc):
        page_rect = page.rect

        # Optional Content Groups — hidden layers
        try:
            oc_info = page.get_oc()
            if oc_info:
                result.warnings.append(
                    f"Página {page_idx+1}: capas opcionales de contenido detectadas (posible texto oculto)"
                )
        except Exception:
            pass

        # Cache filled drawings on the page so we can tell whether a near-white
        # span sits on top of a dark background (legitimate template design)
        # or on a near-white background (real prompt-injection vector).
        # Without this, every Canva-style sidebar with white text on dark blue
        # gets flagged as an attack — a false positive that blocks real CVs.
        dark_fills: list[tuple[float, float, float, float]] = []  # (x0,y0,x1,y1)
        try:
            for d in page.get_drawings():
                fill = d.get("fill")
                rect = d.get("rect")
                if not (fill and rect):
                    continue
                # PyMuPDF returns fill as tuple in 0..1 range. Treat anything
                # below ~0.85 brightness as a "dark" background for our purposes.
                fr, fg, fb = fill[:3]
                fill_brightness = fr * 0.299 + fg * 0.587 + fb * 0.114
                if fill_brightness < 0.85:
                    dark_fills.append((rect.x0, rect.y0, rect.x1, rect.y1))
        except Exception:
            pass

        def _bbox_on_dark_bg(bbox: tuple) -> bool:
            """Return True when the span sits inside a darker filled rectangle."""
            x0, y0, x1, y1 = bbox
            for fx0, fy0, fx1, fy1 in dark_fills:
                # Use center-of-bbox containment so a span near the rect edge
                # still counts as "on the colored area".
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if fx0 - 1 <= cx <= fx1 + 1 and fy0 - 1 <= cy <= fy1 + 1:
                    return True
            return False

        # Lazy raster fallback: if vector drawings tell us nothing, render the
        # page WITHOUT text (text=False) once and sample pixels under suspicious
        # spans. This catches templates whose dark sidebar is a PNG/JPEG image
        # or a page-level background colour rather than a vector rectangle.
        # We render at low DPI (50) — enough to read average colours, fast and
        # ~50 KB of memory per A4 page.
        _bg_pix = {"value": None, "tried": False}

        def _bbox_on_dark_pixels(bbox: tuple) -> bool:
            x0, y0, x1, y1 = bbox
            try:
                if not _bg_pix["tried"]:
                    _bg_pix["tried"] = True
                    matrix = pymupdf.Matrix(50 / 72, 50 / 72)  # 50 DPI
                    _bg_pix["value"] = page.get_pixmap(
                        matrix=matrix, alpha=False, annots=False,
                        clip=None,
                    )
                    # Re-render hiding text so the colour we sample is the
                    # background, not the white text glyphs themselves.
                    # PyMuPDF doesn't have a direct "no-text" flag in older
                    # versions, so we just use what we have — text fills only a
                    # few pixels at 50 DPI and the average still leans to bg.
                pix = _bg_pix["value"]
                if pix is None:
                    return False
                scale_x = pix.width / page_rect.width
                scale_y = pix.height / page_rect.height
                px = max(0, min(pix.width - 1, int(((x0 + x1) / 2) * scale_x)))
                py = max(0, min(pix.height - 1, int(((y0 + y1) / 2) * scale_y)))
                # Sample a 3x3 patch around the centre and average — robust
                # against single-pixel noise from text antialiasing.
                samples = []
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        sx = max(0, min(pix.width - 1, px + dx))
                        sy = max(0, min(pix.height - 1, py + dy))
                        samples.append(pix.pixel(sx, sy))
                avg_r = sum(s[0] for s in samples) / len(samples)
                avg_g = sum(s[1] for s in samples) / len(samples)
                avg_b = sum(s[2] for s in samples) / len(samples)
                avg_bright = (avg_r * 299 + avg_g * 587 + avg_b * 114) / 1000
                # If the averaged background pixels are clearly darker than
                # the text colour threshold, the text is visible by design.
                return avg_bright < 200
            except Exception:
                return False

        # Per-span analysis using rich dict format
        try:
            blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]
        except Exception:
            continue

        for block in blocks:
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue

                    bbox = span.get("bbox", (0, 0, 0, 0))
                    font_size = span.get("size", 12)

                    # ── a) White / near-white text on a near-white background ──
                    # Only suspicious when the underlying background is also
                    # bright. White text on a dark sidebar (typical of Canva /
                    # designer CVs) is intentional and visible to humans.
                    color_int = span.get("color", 0)
                    r = (color_int >> 16) & 0xFF
                    g = (color_int >> 8) & 0xFF
                    b = color_int & 0xFF
                    brightness = (r * 299 + g * 587 + b * 114) / 1000
                    if brightness > 245 and not _bbox_on_dark_bg(bbox) and not _bbox_on_dark_pixels(bbox):
                        result.warnings.append(
                            f"Página {page_idx+1}: texto en color casi blanco sobre fondo claro detectado"
                        )
                        result.hidden_text_fragments.append(
                            f"[TEXTO_BLANCO] {text[:200]}"
                        )

                    # ── b) Micro-text (font size ≤ 1pt → invisible) ───────────
                    if font_size <= 1.0:
                        result.warnings.append(
                            f"Página {page_idx+1}: texto con tamaño de fuente ≤ 1pt detectado"
                        )
                        result.hidden_text_fragments.append(
                            f"[TEXTO_MICRO] {text[:200]}"
                        )

                    # ── c) Off-page text ──────────────────────────────────────
                    if (bbox[0] < -5 or bbox[1] < -5
                            or bbox[2] > page_rect.width + 5
                            or bbox[3] > page_rect.height + 5):
                        result.warnings.append(
                            f"Página {page_idx+1}: texto fuera de los límites de la página detectado"
                        )
                        result.hidden_text_fragments.append(
                            f"[TEXTO_FUERA] {text[:200]}"
                        )

    return result


def _strip_invisible_unicode(text: str) -> tuple[str, list[str]]:
    """
    Remove zero-width and direction-override Unicode characters.

    Returns (cleaned_text, warnings_list).
    Used to neutralize steganographic payloads before injection scanning.
    """
    found = [ch for ch in text if ch in _INVISIBLE_SET]
    if not found:
        return text, []
    cleaned = "".join(ch for ch in text if ch not in _INVISIBLE_SET)
    return cleaned, [
        f"Caracteres Unicode invisibles detectados ({len(found)} ocurrencias): "
        f"{', '.join(repr(ch) for ch in set(found))}"
    ]


# ── Contact recovery patterns (used after primary extraction) ────────────────
# Permissive phone regex covers most real-world CV formats:
#   - international with country code in parens or with leading +
#   - separator may be space (1+), dash, dot, or absent
#   - 7-12 total digits (after separators are removed) is the realistic range
_PHONE_PATTERNS = [
    r'\(\+?\d{1,3}\)[\s\-\.]{0,3}\d{2,4}[\s\-\.]{0,3}\d{3,4}[\s\-\.]{0,3}\d{3,4}',
    r'\+\d{1,3}[\s\-\.]{0,3}\d{2,4}[\s\-\.]{0,3}\d{3,4}[\s\-\.]{0,3}\d{3,4}',
    r'(?<!\d)9\d{2}[\s\-\.]{0,3}\d{3}[\s\-\.]{0,3}\d{3}(?!\d)',
    r'\(0\d{1,2}\)[\s\-\.]{0,3}\d{4}[\s\-\.]{0,3}\d{4}',
    r'(?<!\d)\d{2,4}[\s\-\.]\d{3,4}[\s\-\.]\d{3,4}(?!\d)',
]
_EMAIL_REGEX = re.compile(r'[\w.\-+]+@[\w.\-]+\.\w{2,}')

# Emails commonly fragment during OCR / icon-decoded extraction:
#   "user.name ° @gmail.com"  →  pattern: <local> <icon glyph> <@domain>
# Endurecido para NO fabricar un correo a partir de la palabra previa (un nombre
# propio o un encabezado, ej. "Ana Torres - @empresa.com" → "Torres@empresa.com"):
#   * el local-part debe parecer real (llevar un '.', '_' o '-' interno), lo que
#     descarta una sola palabra suelta como "Torres";
#   * el separador debe ser UN único glifo de ícono, no varios.
# Ante la duda, NO se sintetiza un email (mejor vacío que uno inventado).
_FRAGMENTED_EMAIL_REGEX = re.compile(
    r'([A-Za-z0-9]+[._\-][\w.\-+]{1,62})[ \t]*([^\w\s@])[ \t]*(@[\w.\-]+\.\w{2,})'
)


def _join_fragmented_emails(text: str) -> str:
    """Re-join emails split by icon glyphs (e.g. "user ° @gmail.com")."""
    return _FRAGMENTED_EMAIL_REGEX.sub(lambda m: f"{m.group(1)}{m.group(3)}", text)


# Profile URLs (LinkedIn, GitHub) commonly wrap to a second line in PDFs:
#   "https://www.linkedin.com/in/\n username"  →  "https://www.linkedin.com/in/username"
# The split happens after the trailing slash of the path component, so the
# regex looks for the path slash followed by whitespace and a non-empty
# username segment.
_SPLIT_URL_REGEX = re.compile(
    r'((?:https?://)?(?:www\.)?(?:linkedin\.com/in|github\.com)/)\s+([\w\-_%]+)',
    re.IGNORECASE,
)


# Encabezados de sección frecuentes: si una URL de perfil quedó sin usuario y
# justo debajo va uno de estos (o una palabra en MAYÚSCULAS), NO debemos pegarlo
# como si fuera el handle — sería un perfil inventado.
_SECTION_HEADINGS = {
    "experiencia", "educacion", "educación", "formacion", "formación",
    "habilidades", "idiomas", "referencias", "contacto", "perfil", "resumen",
    "experience", "education", "skills", "languages", "references", "summary",
}


def _join_split_profile_urls(text: str) -> str:
    """Join LinkedIn / GitHub URLs split across two lines by PDF wrapping.

    No une cuando la palabra siguiente va en MAYÚSCULAS o es un encabezado de
    sección: en esos casos la URL quedó realmente sin usuario y pegar la palabra
    de abajo fabricaría un perfil falso (``linkedin.com/in/EXPERIENCIA``).
    """
    def _repl(m: "re.Match") -> str:
        word = m.group(2)
        if word.isupper() or word.lower() in _SECTION_HEADINGS:
            return m.group(0)  # dejar la URL sin unir
        return f"{m.group(1)}{word}"

    return _SPLIT_URL_REGEX.sub(_repl, text)


def _recover_dropped_contacts(doc: pymupdf.Document, markdown_text: str) -> str:
    """Safety net: prepend email/phone visible in the raw text layer but
    missing from the primary extractor output.

    pymupdf4llm sometimes drops short header lines that pymupdf.get_text()
    keeps (icon-decorated contact boxes are the typical culprit). This helper
    is layout-agnostic and order-preserving:

    - Collects matches from raw text in their original document position.
    - Skips anything already present in the markdown (the primary extractor
      kept it, no need to duplicate).
    - Preserves reading order so the candidate's own contact (typically at
      the top of the CV header) appears before any reference / third-party
      contact further down. This matters because the downstream
      post-processor picks the first match it finds.

    Returns the markdown unchanged when nothing is missing.
    """
    raw_combined = "\n".join(page.get_text() for page in doc)
    if not raw_combined.strip():
        return markdown_text

    md_lower = markdown_text.lower()
    # Tokenizamos los números con FORMA de teléfono presentes en el markdown,
    # en vez de concatenar TODOS los dígitos del documento: así un teléfono real
    # recuperado no se descarta solo porque sus dígitos aparezcan dentro de un
    # código de proyecto o un ID concatenado más largo.
    md_phone_digits = {
        re.sub(r'\D', '', _t)
        for _t in re.findall(r'\d[\d\s\-\.\(\)+]{5,}\d', markdown_text)
    }

    # Emails — keep raw-text reading order, dedupe by lower-case form.
    missing_emails: list[str] = []
    seen_emails: set[str] = set()
    for match in _EMAIL_REGEX.finditer(raw_combined):
        email = match.group(0)
        key = email.lower()
        if key in seen_emails or key in md_lower:
            continue
        seen_emails.add(key)
        missing_emails.append(email)

    # Phones — iterate every pattern but tag each hit with its raw-text
    # position, then sort by position so candidate-header phones come first.
    candidates: list[tuple[int, str, str]] = []  # (position, normalized_digits, raw_match)
    for pattern in _PHONE_PATTERNS:
        for match in re.finditer(pattern, raw_combined):
            phone = match.group(0).strip()
            digits = re.sub(r'\D', '', phone)
            if not (7 <= len(digits) <= 15):
                continue
            if any(digits in d or d in digits for d in md_phone_digits):
                continue  # already in markdown; primary extractor kept it
            candidates.append((match.start(), digits, phone))

    candidates.sort(key=lambda c: c[0])
    missing_phones: list[str] = []
    accepted_digits: list[str] = []
    for _, digits, phone in candidates:
        # Skip if digits are a substring of, or contain, an already-kept number.
        # Handles the (+CC) prefix + bare-number duplicate ("(51) 971705123"
        # vs "971705123") where two patterns hit the same physical phone.
        if any(d in digits or digits in d for d in accepted_digits):
            continue
        accepted_digits.append(digits)
        missing_phones.append(phone)

    if not missing_emails and not missing_phones:
        return markdown_text

    recovered_lines: list[str] = ["## CONTACTO RECUPERADO"]
    for email in missing_emails:
        recovered_lines.append(f"Email: {email}")
    for phone in missing_phones:
        recovered_lines.append(f"Teléfono: {phone}")
    logger.info(
        f"Recovered contacts dropped by primary extractor: "
        f"{len(missing_emails)} email(s), {len(missing_phones)} phone(s)"
    )
    return "\n".join(recovered_lines) + "\n\n" + markdown_text


def _pdf_to_text(doc: pymupdf.Document) -> tuple[str, SecurityScanResult]:
    """
    Extract text from all PDF pages.

    Tries pymupdf4llm first for structured Markdown output (section headers,
    multi-column layout, OCR). Falls back to the custom extractor when
    pymupdf4llm is unavailable or returns very little text.

    Also runs the security scan and returns a SecurityScanResult so callers
    can pass hidden text fragments to the injection pattern scanner.
    """
    security = _scan_pdf_security(doc)

    # ── Primary: pymupdf4llm ─────────────────────────────────────────────────
    try:
        import inspect

        import pymupdf4llm

        # pymupdf4llm cambia su firma entre versiones (0.0.17 no acepta
        # header/footer/use_ocr). Un kwarg desconocido lanza TypeError, el
        # except lo atrapaba y TODOS los CVs caían en silencio al extractor
        # custom (que entrelaza columnas con '|'). Filtramos por la firma
        # real para que el extractor primario corra en cualquier versión.
        _desired_kwargs = {
            "ignore_code": True,       # Don't wrap emails/phones/URLs in ```code``` blocks
            "header": False,           # Skip repetitive page-header lines
            "footer": False,           # Skip repetitive page-footer lines
            "use_ocr": True,           # Auto-OCR scanned pages (if supported)
            "ocr_language": "spa+eng",
            "show_progress": False,    # 0.0.17 prints progress bars to stdout
        }
        _supported = set(inspect.signature(pymupdf4llm.to_markdown).parameters)
        md = pymupdf4llm.to_markdown(
            doc,
            **{k: v for k, v in _desired_kwargs.items() if k in _supported},
        )
        char_count = len(md.strip())
        min_expected = 80 * max(doc.page_count, 1)
        if char_count >= min_expected:
            logger.debug(
                f"pymupdf4llm extracted {char_count} chars "
                f"from {doc.page_count} page(s)"
            )
            md = _join_fragmented_emails(md)
            md = _join_split_profile_urls(md)
            md = _recover_dropped_contacts(doc, md)
            return md, security
        logger.warning(
            f"pymupdf4llm returned only {char_count} chars "
            f"({doc.page_count} page(s), expected ≥{min_expected}) — "
            "falling back to custom extractor"
        )
    except ImportError:
        logger.debug("pymupdf4llm not installed — using custom extractor")
    except Exception as e:
        logger.warning(f"pymupdf4llm failed ({e}) — falling back to custom extractor")

    # ── Fallback: custom hybrid extractor ────────────────────────────────────
    if _is_scanned_pdf(doc):
        logger.warning(
            f"Scanned PDF detected ({doc.page_count} page(s), "
            f"avg {sum(len(p.get_text().strip()) for p in doc) // max(doc.page_count, 1)}"
            " chars/page). Text extraction will be limited."
        )
        raw_pages = [page.get_text().strip() for page in doc]
        raw_text = "\n\n---\n\n".join(p for p in raw_pages if p)
        return (_SCANNED_WARNING + raw_text if raw_text else _SCANNED_WARNING), security

    pages = []
    for page in doc:
        page_text = _extract_page_text(page)
        if page_text:
            pages.append(page_text)
    fallback_md = "\n\n---\n\n".join(pages)
    fallback_md = _join_fragmented_emails(fallback_md)
    fallback_md = _join_split_profile_urls(fallback_md)
    fallback_md = _recover_dropped_contacts(doc, fallback_md)
    return fallback_md, security


class DocumentParsingError(Exception):
    """Raised when document parsing fails."""
    pass


class DocumentExtractor:
    """
    Parser for CV/Resume and job-profile documents.
    Fully local, no external API calls.
    """

    async def parse_bytes(
        self, content: bytes, filename: str
    ) -> Tuple[str, dict]:
        """
        Parse document from raw bytes (no temp file needed).

        For PDFs: also runs the security scan (white text, micro-font,
        off-page text, metadata, JavaScript, invisible Unicode).
        Security warnings and hidden text fragments are included in
        ``metadata_dict["security_warnings"]`` and
        ``metadata_dict["hidden_text_fragments"]`` so the caller can
        pass the hidden fragments through the injection pattern scanner.

        Args:
            content:  File content as bytes.
            filename: Original filename — used to detect format by extension.

        Returns:
            (markdown_text, metadata_dict)
        """
        suffix = Path(filename).suffix.lower()
        if suffix not in _SUPPORTED:
            raise DocumentParsingError(
                f"Unsupported format '{suffix}'. Only PDF and DOCX are accepted."
            )

        try:
            security_warnings: list[str] = []
            hidden_fragments: list[str] = []

            if suffix == ".pdf":
                logger.info(f"Parsing PDF bytes with fitz blocks: {filename}")
                doc = pymupdf.open(stream=content, filetype="pdf")
                markdown_output, sec = _pdf_to_text(doc)
                doc.close()
                engine = "fitz"
                security_warnings = sec.warnings
                hidden_fragments = sec.hidden_text_fragments
                if security_warnings:
                    logger.warning(
                        f"{filename}: {len(security_warnings)} security finding(s): "
                        + "; ".join(security_warnings[:3])
                    )
            else:
                logger.info(f"Parsing DOCX bytes with MarkItDown: {filename}")
                stream_info = StreamInfo(extension=suffix, filename=filename)
                result = _markitdown.convert_stream(
                    BytesIO(content), stream_info=stream_info
                )
                markdown_output = result.text_content
                engine = "markitdown"

            # Strip invisible Unicode from extracted text (steganographic bypass)
            markdown_output, uni_warnings = _strip_invisible_unicode(markdown_output)
            if uni_warnings:
                security_warnings.extend(uni_warnings)
                logger.warning(f"{filename}: {uni_warnings[0]}")

            return markdown_output, {
                "original_filename": filename,
                "file_size": len(content),
                "total_characters": len(markdown_output),
                "extraction_engine": engine,
                "security_warnings": security_warnings,
                "hidden_text_fragments": hidden_fragments,
            }

        except DocumentParsingError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse bytes for {filename}: {e}")
            raise DocumentParsingError(f"Conversion failed: {e}")
