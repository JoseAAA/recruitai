"""
Document Extractor Adapter
Converts documents to plain text for LLM processing.
  - PDF  → Hybrid extraction (PyMuPDF/fitz):
             · Tables   → find_tables() for correct row-cell grouping in multi-column grids
             · Narrative → word-level bounding boxes, y-bucketed into visual lines
  - DOCX → MarkItDown  (Microsoft library via mammoth)
Only PDF and DOCX are supported; other formats raise DocumentParsingError.
"""
import logging
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

    words = page.get_text("words")   # (x0, y0, x1, y1, word, block_no, line_no, word_no)
    line_map: dict[int, list[tuple[float, str, float]]] = {}
    for x0, y0, x1, y1, word, *_ in words:
        if table_bboxes and _in_table(x0, y0, x1, y1):
            continue
        y_mid = (y0 + y1) / 2
        bucket = round(y_mid / LINE_TOL) * LINE_TOL
        line_map.setdefault(bucket, []).append((x0, word, y0))

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
            para_y0 = min(w[2] for w in line_map[bucket])
        ordered = sorted(line_map[bucket], key=lambda w: w[0])
        para_lines.append(" ".join(w[1] for w in ordered))
        prev_bucket = bucket

    if para_lines:
        text_segments.append((para_y0, "\n".join(para_lines)))

    # ── 3. Merge all segments in reading order (top → bottom) ────────────────
    all_segments = text_segments + table_segments
    all_segments.sort(key=lambda s: s[0])

    if not all_segments:
        return ""

    return "\n\n".join(text for _, text in all_segments).strip()


def _pdf_to_text(doc: pymupdf.Document) -> str:
    """Extract text from all pages; separate pages with a horizontal rule."""
    pages = []
    for page in doc:
        page_text = _extract_page_text(page)
        if page_text:
            pages.append(page_text)
    return "\n\n---\n\n".join(pages)


class DocumentParsingError(Exception):
    """Raised when document parsing fails."""
    pass


class DocumentExtractor:
    """
    Parser for CV/Resume and job-profile documents.
    Fully local, no external API calls.
    """

    async def extract_to_markdown(self, file_path: str) -> Tuple[str, dict]:
        """
        Convert a document file to Markdown.

        Args:
            file_path: Absolute path to the local file.

        Returns:
            (markdown_text, metadata_dict)
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentParsingError(f"File not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED:
            raise DocumentParsingError(f"Unsupported format '{suffix}'. Only PDF and DOCX are accepted.")

        try:
            if suffix == ".pdf":
                logger.info(f"Parsing PDF with fitz blocks: {path.name}")
                doc = pymupdf.open(str(path))
                markdown_output = _pdf_to_text(doc)
                doc.close()
                engine = "fitz"
            else:
                logger.info(f"Parsing DOCX with MarkItDown: {path.name}")
                result = _markitdown.convert(str(path))
                markdown_output = result.text_content
                engine = "markitdown"

            return markdown_output, {
                "file_path": str(path),
                "file_name": path.name,
                "file_size": path.stat().st_size,
                "total_characters": len(markdown_output),
                "extraction_engine": engine,
            }

        except DocumentParsingError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            raise DocumentParsingError(f"Conversion failed: {e}")

    async def parse_bytes(self, content: bytes, filename: str) -> Tuple[str, dict]:
        """
        Parse document from raw bytes (no temp file needed).

        Args:
            content:  File content as bytes.
            filename: Original filename — used to detect format by extension.

        Returns:
            (markdown_text, metadata_dict)
        """
        suffix = Path(filename).suffix.lower()
        if suffix not in _SUPPORTED:
            raise DocumentParsingError(f"Unsupported format '{suffix}'. Only PDF and DOCX are accepted.")

        try:
            if suffix == ".pdf":
                logger.info(f"Parsing PDF bytes with fitz blocks: {filename}")
                doc = pymupdf.open(stream=content, filetype="pdf")
                markdown_output = _pdf_to_text(doc)
                doc.close()
                engine = "fitz"
            else:
                logger.info(f"Parsing DOCX bytes with MarkItDown: {filename}")
                stream_info = StreamInfo(extension=suffix, filename=filename)
                result = _markitdown.convert_stream(BytesIO(content), stream_info=stream_info)
                markdown_output = result.text_content
                engine = "markitdown"

            return markdown_output, {
                "original_filename": filename,
                "file_size": len(content),
                "total_characters": len(markdown_output),
                "extraction_engine": engine,
            }

        except DocumentParsingError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse bytes for {filename}: {e}")
            raise DocumentParsingError(f"Conversion failed: {e}")
