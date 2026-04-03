"""
Docling Parser Module — uses ALL available Docling tools for maximum extraction.

Configures:
  - OCR (for scanned docs / images)
  - Table structure recognition
  - Picture classification & description
  - Page image generation (for bounding-box visualization)
  - High-resolution image scale
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict

from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    ImageFormatOption,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

logger = logging.getLogger(__name__)


def _build_pdf_pipeline_options() -> PdfPipelineOptions:
    """Build a PdfPipelineOptions with every useful tool enabled."""
    opts = PdfPipelineOptions()

    # --- OCR ---
    opts.do_ocr = True                        # Enable OCR for scanned pages

    # --- Tables ---
    opts.do_table_structure = True             # Enable table-structure recognition
    opts.generate_table_images = True          # Save cropped table images

    # --- Pictures ---
    opts.do_picture_classification = True      # Classify pictures
    opts.do_picture_description = True         # Describe pictures via VLM

    # --- Page-level outputs ---
    opts.generate_page_images = True           # Save full page images (needed for bbox viz)
    opts.generate_picture_images = True        # Save cropped picture images
    opts.generate_parsed_pages = True          # Generate parsed page data

    # --- Image scale (higher = better quality, slower) ---
    opts.images_scale = 2.0

    return opts


class DoclingParser:
    """
    High-fidelity Docling document parser.

    Exposes separate pipelines for PDF and image inputs so every
    format is converted with the richest set of options available.
    """

    def __init__(self):
        pdf_opts = _build_pdf_pipeline_options()

        # Build the converter with explicit format-specific options
        self.converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.HTML,
                InputFormat.XLSX,
                InputFormat.CSV,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pdf_opts,
                ),
                InputFormat.IMAGE: ImageFormatOption(),
            },
        )
        logger.info("DoclingParser initialized with full pipeline options.")

    # -------------------------------------------------------------- #
    # Public API
    # -------------------------------------------------------------- #
    def parse(self, file_path: str):
        """
        Parse a document (PDF, image, docx, …) and return the
        DoclingDocument object.
        """
        abs_path = str(Path(file_path).resolve())
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Source file not found: {abs_path}")

        logger.info(f"Parsing document: {abs_path}")
        result = self.converter.convert(abs_path)
        logger.info("Docling parsing completed successfully.")
        return result

    def extract_single_page_data(
        self,
        conversion_result,
        page_number: int,
        rotation_angle: int = 0,
        source_image_path: str = "",
    ) -> Dict[str, Any]:
        """
        Normalize per-page parse output for scanned-PDF image loops.
        """
        return {
            "page_number": page_number,
            "rotation_angle": rotation_angle,
            "source_image_path": source_image_path,
            "document": conversion_result.document,
        }

    def build_page_data_from_document(self, document, page_number: int) -> Dict[str, Any]:
        """
        Build a refiner-ready per-page payload from a DoclingDocument.
        """
        page_obj = None
        # For scanned PDFs, each page is parsed as a standalone 1-page document
        # whose internal page key is always 1, even when the external page_number is > 1.
        # Fall back to the first available key so element extraction still works.
        internal_page_number = page_number
        if hasattr(document, "pages") and document.pages:
            page_obj = document.pages.get(page_number)
            if page_obj is None:
                first_key = next(iter(document.pages), None)
                if first_key is not None:
                    page_obj = document.pages[first_key]
                    internal_page_number = first_key

        width = float(getattr(getattr(page_obj, "size", None), "width", 595.0)) if page_obj else 595.0
        height = float(getattr(getattr(page_obj, "size", None), "height", 842.0)) if page_obj else 842.0

        payload: Dict[str, Any] = {
            "page_number": page_number,
            "width": width,
            "height": height,
            "elements": [],
            "tables": [],
            "pictures": [],
        }

        elem_id = 1
        table_id = 1
        picture_id = 1

        for item, _ in document.iterate_items():
            prov = self._first_matching_prov(item, internal_page_number)
            if prov is None:
                continue

            label = str(getattr(item, "label", "text")).split(".")[-1].lower()
            bbox_dict = self._bbox_to_dict(getattr(prov, "bbox", None))

            if label == "table":
                rows = []
                table_obj = getattr(item, "data", None)
                if table_obj and hasattr(table_obj, "grid"):
                    for row in table_obj.grid:
                        rows.append([getattr(cell, "text", "") for cell in row])
                payload["tables"].append(
                    {
                        "id": f"p{page_number}_t{table_id}",
                        "bbox": bbox_dict,
                        "grid": rows,
                    }
                )
                table_id += 1
                continue

            if label == "picture":
                payload["pictures"].append(
                    {
                        "id": f"p{page_number}_img{picture_id}",
                        "bbox": bbox_dict,
                        "classification": "picture",
                        "description": getattr(item, "description", ""),
                    }
                )
                picture_id += 1
                continue

            text = getattr(item, "text", "")
            if not text:
                continue

            payload["elements"].append(
                {
                    "id": f"p{page_number}_e{elem_id}",
                    "type": label,
                    "text": text,
                    "level": None,
                    "bbox": bbox_dict,
                }
            )
            elem_id += 1

        return payload

    def _first_matching_prov(self, item, page_number: int):
        for prov in (getattr(item, "prov", None) or []):
            if getattr(prov, "page_no", None) == page_number:
                return prov
        return None

    def _bbox_to_dict(self, bbox) -> Dict[str, float]:
        if bbox is None:
            return {"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.0}
        return {
            "l": float(getattr(bbox, "l", 0.0)),
            "t": float(getattr(bbox, "t", 0.0)),
            "r": float(getattr(bbox, "r", 0.0)),
            "b": float(getattr(bbox, "b", 0.0)),
        }
