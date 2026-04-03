"""
Formatter Module — renders the parsed DoclingDocument into structured formats.

Optimized for Docling v2:
  - Uses export_to_markdown() for high-fidelity text/tables.
  - Recursively traverses iterate_items() to build a structured JSON map.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from agent.schema import DocumentResult

logger = logging.getLogger(__name__)


class DocumentFormatter:
    """Formats the Docling document into required structured outputs."""

    def format_as_markdown(
        self,
        document,
        source_file: str = "",
        input_type_info=None,
        preprocessing_applied: Optional[List[str]] = None,
        pages_with_orientation_correction: Optional[List[int]] = None,
    ) -> str:
        """
        Converts document to high-fidelity markdown using Docling's engine.
        """
        logger.info("Formatting output as Markdown")
        metadata_header = self._build_markdown_metadata_header(
            source_file=source_file,
            input_type_info=input_type_info,
            preprocessing_applied=preprocessing_applied or [],
            pages_with_orientation_correction=pages_with_orientation_correction or [],
        )
        return metadata_header + "\n\n" + document.export_to_markdown()

    def format_as_json(
        self,
        document,
        source_file: str = "",
        input_type_info=None,
        preprocessing_applied: Optional[List[str]] = None,
        pages_with_orientation_correction: Optional[List[int]] = None,
    ) -> str:
        """
        Converts the DoclingDocument into a structured JSON representation.
        
        This traverses the semantic tree to extract:
          - Paragraphs / Titles / Sections
          - Tables (as 2D arrays)
          - Lists
          - Pictures (with basic metadata)
        """
        logger.info("Formatting output as structured JSON")
        structured_data = {
            "metadata": self._build_json_metadata(
                source_file=source_file,
                input_type_info=input_type_info,
                preprocessing_applied=preprocessing_applied or [],
                pages_with_orientation_correction=pages_with_orientation_correction or [],
            ),
            "document": {
                "document_title": self._resolve_attr(document, "name", "Extracted Document"),
                "num_pages": self._resolve_attr(document, "num_pages", 0),
                "content": self._extract_document_content(document),
            },
        }
        return json.dumps(structured_data, indent=2, ensure_ascii=False)

    def format_pages_as_markdown(
        self,
        parsed_pages: List[Dict[str, Any]],
        source_file: str = "",
        input_type_info=None,
        preprocessing_applied: Optional[List[str]] = None,
    ) -> str:
        """Combine per-page parsed image outputs into one markdown document."""
        pages_sorted = sorted(parsed_pages, key=lambda page: page.get("page_number", 0))
        corrected_pages = [
            page.get("page_number", 0)
            for page in pages_sorted
            if page.get("rotation_angle", 0) not in (None, 0)
        ]
        header = self._build_markdown_metadata_header(
            source_file=source_file,
            input_type_info=input_type_info,
            preprocessing_applied=preprocessing_applied or [],
            pages_with_orientation_correction=corrected_pages,
        )

        chunks: List[str] = [header]
        for page in pages_sorted:
            page_number = page.get("page_number", 0)
            rotation_angle = page.get("rotation_angle", 0)
            page_markdown = page["document"].export_to_markdown().strip()
            chunks.append(f"## Page {page_number}")
            chunks.append(f"<!-- orientation_correction_angle: {rotation_angle} -->")
            chunks.append(page_markdown)

        return "\n\n".join(chunks).strip() + "\n"

    def format_pages_as_json(
        self,
        parsed_pages: List[Dict[str, Any]],
        source_file: str = "",
        input_type_info=None,
        preprocessing_applied: Optional[List[str]] = None,
    ) -> str:
        """Combine per-page parsed image outputs into one JSON document."""
        pages_sorted = sorted(parsed_pages, key=lambda page: page.get("page_number", 0))
        corrected_pages = [
            page.get("page_number", 0)
            for page in pages_sorted
            if page.get("rotation_angle", 0) not in (None, 0)
        ]

        payload = {
            "metadata": self._build_json_metadata(
                source_file=source_file,
                input_type_info=input_type_info,
                preprocessing_applied=preprocessing_applied or [],
                pages_with_orientation_correction=corrected_pages,
            ),
            "pages": [],
        }

        for page in pages_sorted:
            payload["pages"].append(
                {
                    "page_number": page.get("page_number", 0),
                    "rotation_angle": page.get("rotation_angle", 0),
                    "source_image_path": page.get("source_image_path", ""),
                    "content": self._extract_document_content(page["document"]),
                }
            )

        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _extract_document_content(self, document) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = []
        try:
            for item, level in document.iterate_items():
                label = str(getattr(item, "label", "text")).split(".")[-1].lower()
                text = getattr(item, "text", "").strip()

                if label == "table":
                    rows = []
                    table_obj = getattr(item, "data", None)
                    if table_obj and hasattr(table_obj, "grid"):
                        for row in table_obj.grid:
                            rows.append([cell.text for cell in row])
                    content.append({"type": "table", "label": label, "rows": rows})
                elif label == "picture":
                    caption = ""
                    if hasattr(item, "caption"):
                        caption = getattr(item.caption, "text", "")
                    content.append(
                        {
                            "type": "image",
                            "label": label,
                            "caption": caption,
                            "description": getattr(item, "description", ""),
                        }
                    )
                elif text:
                    content.append(
                        {
                            "type": "text",
                            "label": label,
                            "content": text,
                            "level": level,
                        }
                    )
        except Exception as exc:
            logger.error("Structured extraction failed: %s", exc)
            try:
                fallback_dict = document.export_to_dict()
                return [{"type": "raw", "payload": fallback_dict}]
            except Exception:
                return [{"type": "error", "message": "Failed to serialize document"}]

        return content

    def _build_json_metadata(
        self,
        source_file: str,
        input_type_info,
        preprocessing_applied: List[str],
        pages_with_orientation_correction: List[int],
    ) -> Dict[str, Any]:
        return {
            "source_file": source_file,
            "input_type": getattr(input_type_info, "detected_format", "UNKNOWN"),
            "input_extension": getattr(input_type_info, "extension", ""),
            "is_scanned": getattr(input_type_info, "is_scanned", False),
            "preprocessing_applied": preprocessing_applied,
            "pages_with_orientation_correction": pages_with_orientation_correction,
        }

    def _resolve_attr(self, obj, attr_name: str, default):
        value = getattr(obj, attr_name, default)
        if callable(value):
            try:
                value = value()
            except Exception:
                return default
        return value

    def _build_markdown_metadata_header(
        self,
        source_file: str,
        input_type_info,
        preprocessing_applied: List[str],
        pages_with_orientation_correction: List[int],
    ) -> str:
        lines = [
            "<!-- ADE Agent Metadata",
            f"source_file: {source_file}",
            f"input_type: {getattr(input_type_info, 'detected_format', 'UNKNOWN')}",
            f"input_extension: {getattr(input_type_info, 'extension', '')}",
            f"is_scanned: {getattr(input_type_info, 'is_scanned', False)}",
            f"preprocessing_applied: {preprocessing_applied}",
            f"pages_with_orientation_correction: {pages_with_orientation_correction}",
            "-->",
        ]
        return "\n".join(lines)

    def format_structured_document_as_json(self, structured_document: DocumentResult) -> str:
        """Serialize a structured DocumentResult produced by LLM refinement."""
        return json.dumps(structured_document.model_dump(), indent=2, ensure_ascii=False)

    def format_structured_document_as_markdown(self, structured_document: DocumentResult) -> str:
        """Render a readable markdown report from a structured DocumentResult."""
        md_lines: List[str] = [
            "<!-- ADE Agent Structured Metadata",
            f"source_file: {structured_document.source_file}",
            f"input_type: {structured_document.input_type}",
            f"input_extension: {structured_document.input_extension}",
            f"is_scanned: {structured_document.is_scanned}",
            f"preprocessing_applied: {structured_document.preprocessing_applied}",
            f"pages_with_orientation_correction: {structured_document.pages_with_orientation_correction}",
            f"model_used: {structured_document.model_used}",
            "-->",
            "",
        ]

        for page in structured_document.pages:
            md_lines.append(f"## Page {page.page_number}")
            md_lines.append(f"- layout_type: {page.layout_type}")
            md_lines.append(f"- was_refined: {page.was_refined}")
            md_lines.append(f"- refinement_reason: {page.refinement_reason}")
            if page.orientation_correction_angle is not None:
                md_lines.append(f"- orientation_correction_angle: {page.orientation_correction_angle}")
            md_lines.append("")

            for element in sorted(page.elements, key=lambda e: e.reading_order):
                md_lines.append(f"### [{element.reading_order}] {element.type}")
                if element.content:
                    md_lines.append(element.content)

                if element.type == "table" and element.rows:
                    if element.headers:
                        header = " | ".join(element.headers)
                        sep = " | ".join(["---"] * len(element.headers))
                        md_lines.append("")
                        md_lines.append(f"| {header} |")
                        md_lines.append(f"| {sep} |")
                    for row in element.rows:
                        md_lines.append(f"| {' | '.join(row)} |")

                if element.type == "list" and element.items:
                    for item in element.items:
                        md_lines.append(f"- {item}")

                if element.type == "image":
                    if element.caption:
                        md_lines.append(f"- caption: {element.caption}")
                    if element.description:
                        md_lines.append(f"- description: {element.description}")

                md_lines.append("")

        return "\n".join(md_lines).strip() + "\n"
