"""
Document Extractor Adapter
Converts documents to Markdown for LLM processing.
  - PDF  → PyMuPDF4LLM (fast, fully local, no model download)
  - DOCX → MarkItDown  (Microsoft library via mammoth)
Only PDF and DOCX are supported; other formats raise DocumentParsingError.
"""
import logging
from io import BytesIO
from pathlib import Path
from typing import Tuple

import pymupdf
import pymupdf4llm
from markitdown import MarkItDown, StreamInfo

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".docx"}

# MarkItDown is stateless — one instance is enough
_markitdown = MarkItDown(enable_plugins=False)


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
                logger.info(f"Parsing PDF with PyMuPDF4LLM: {path.name}")
                markdown_output = pymupdf4llm.to_markdown(str(path))
                engine = "pymupdf4llm"
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
                logger.info(f"Parsing PDF bytes with PyMuPDF4LLM: {filename}")
                doc = pymupdf.open(stream=content, filetype="pdf")
                markdown_output = pymupdf4llm.to_markdown(doc)
                engine = "pymupdf4llm"
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
