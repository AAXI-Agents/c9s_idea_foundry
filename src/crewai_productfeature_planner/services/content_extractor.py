"""Content extractor service.

Extracts readable text from uploaded files based on content type.
Supports plain text, PDF, and DOCX. Returns None for unsupported binary formats.
"""

from __future__ import annotations

import io

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Content types that can be decoded directly as UTF-8
_TEXT_CONTENT_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/html",
        "text/xml",
        "application/json",
        "application/xml",
        "application/x-yaml",
        "application/yaml",
    }
)

# File extensions that are safe to decode as UTF-8
_TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".html",
        ".htm",
        ".log",
        ".ini",
        ".cfg",
        ".toml",
        ".rst",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".rb",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".sh",
        ".sql",
    }
)


def extract_text(
    contents: bytes,
    *,
    filename: str = "",
    content_type: str = "application/octet-stream",
) -> str | None:
    """Extract readable text from file contents.

    Args:
        contents: Raw file bytes.
        filename: Original filename (used for extension-based detection).
        content_type: MIME type of the uploaded file.

    Returns:
        Extracted text string, or None if format is unsupported.
    """
    ext = _get_extension(filename)

    # Plain text formats — decode directly
    if content_type in _TEXT_CONTENT_TYPES or ext in _TEXT_EXTENSIONS:
        return _extract_plain_text(contents)

    # PDF
    if content_type == "application/pdf" or ext == ".pdf":
        return _extract_pdf(contents)

    # DOCX
    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or ext == ".docx"
    ):
        return _extract_docx(contents)

    # Legacy .doc — not supported without heavy deps
    if content_type == "application/msword" or ext == ".doc":
        logger.warning(
            "[ContentExtractor] Legacy .doc format not supported: %s", filename
        )
        return None

    # Fallback: try UTF-8 decode — if it produces mostly readable chars, use it
    return _try_text_fallback(contents, filename)


def _get_extension(filename: str) -> str:
    """Extract lowercase file extension."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _extract_plain_text(contents: bytes) -> str:
    """Decode bytes as UTF-8 text."""
    return contents.decode("utf-8", errors="replace")


def _extract_pdf(contents: bytes) -> str | None:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contents))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        if not pages_text:
            logger.warning("[ContentExtractor] PDF has no extractable text (possibly scanned/image-only)")
            return None
        return "\n\n".join(pages_text)
    except ImportError:
        logger.error("[ContentExtractor] pypdf not installed — cannot extract PDF")
        return None
    except Exception as exc:
        logger.error("[ContentExtractor] PDF extraction failed: %s", exc, exc_info=True)
        return None


def _extract_docx(contents: bytes) -> str | None:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(contents))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            logger.warning("[ContentExtractor] DOCX has no extractable text")
            return None
        return "\n\n".join(paragraphs)
    except ImportError:
        logger.error("[ContentExtractor] python-docx not installed — cannot extract DOCX")
        return None
    except Exception as exc:
        logger.error("[ContentExtractor] DOCX extraction failed: %s", exc, exc_info=True)
        return None


def _try_text_fallback(contents: bytes, filename: str) -> str | None:
    """Try decoding as text; reject if too many replacement characters."""
    text = contents.decode("utf-8", errors="replace")
    # If more than 10% of characters are replacement chars, it's binary
    replacement_ratio = text.count("\ufffd") / max(len(text), 1)
    if replacement_ratio > 0.10:
        logger.warning(
            "[ContentExtractor] File appears to be unsupported binary: %s (%.1f%% replacement chars)",
            filename,
            replacement_ratio * 100,
        )
        return None
    return text
