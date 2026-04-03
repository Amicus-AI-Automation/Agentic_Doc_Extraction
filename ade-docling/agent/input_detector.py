"""
Input detection helpers for routing documents through preprocessing.

The detector classifies the input by extension and, for PDFs, inspects
the text layer to distinguish born-digital files from scanned documents.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from config import (
    PDF_SCAN_CHECK_PAGES,
    PDF_TEXT_LAYER_MIN_CHARS,
    SUPPORTED_DOC_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_PDF_EXTENSIONS,
    SUPPORTED_PPT_EXTENSIONS,
    SUPPORTED_SHEET_EXTENSIONS,
    SUPPORTED_TEXT_EXTENSIONS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InputTypeInfo:
    """Normalized input metadata used throughout the parsing pipeline."""

    detected_format: str
    extension: str
    is_scanned: bool = False
    requires_ocr: bool = False
    requires_orientation_correction: bool = False

    @property
    def complexity_profile(self) -> str:
        if self.detected_format == "PDF":
            return "PDF_SCANNED" if self.is_scanned else "PDF_NATIVE"
        if self.detected_format == "IMAGE":
            return "IMAGE"
        if self.detected_format == "PPTX":
            return "PPTX"
        return "DEFAULT"


def detect_input_type(file_path: str) -> InputTypeInfo:
    """Identify supported file type and whether preprocessing is needed."""
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension in SUPPORTED_PDF_EXTENSIONS:
        is_scanned = _is_scanned_pdf(path)
        return InputTypeInfo(
            detected_format="PDF",
            extension=extension,
            is_scanned=is_scanned,
            requires_ocr=is_scanned,
            requires_orientation_correction=is_scanned,
        )

    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        return InputTypeInfo(
            detected_format="IMAGE",
            extension=extension,
            is_scanned=True,
            requires_ocr=True,
            requires_orientation_correction=True,
        )

    if extension in SUPPORTED_PPT_EXTENSIONS:
        return InputTypeInfo(detected_format="PPTX", extension=extension)

    if extension in SUPPORTED_DOC_EXTENSIONS:
        return InputTypeInfo(detected_format="DOCX", extension=extension)

    if extension in SUPPORTED_SHEET_EXTENSIONS:
        return InputTypeInfo(detected_format="XLSX", extension=extension)

    if extension in SUPPORTED_TEXT_EXTENSIONS:
        text_format = extension.lstrip(".").upper() or "TEXT"
        return InputTypeInfo(detected_format=text_format, extension=extension)

    return InputTypeInfo(detected_format="UNKNOWN", extension=extension)


def _is_scanned_pdf(file_path: Path) -> bool:
    """Treat a PDF as scanned when it lacks a meaningful text layer."""
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not installed; assuming PDF is born-digital for %s", file_path)
        return False

    try:
        with fitz.open(file_path) as document:
            pages_to_check = min(len(document), PDF_SCAN_CHECK_PAGES)
            extracted_chars = 0

            for page_index in range(pages_to_check):
                extracted_chars += len(document[page_index].get_text("text").strip())
                if extracted_chars >= PDF_TEXT_LAYER_MIN_CHARS:
                    return False

            return True
    except Exception as exc:
        logger.warning("Failed to inspect PDF text layer for %s: %s", file_path, exc)
        return False