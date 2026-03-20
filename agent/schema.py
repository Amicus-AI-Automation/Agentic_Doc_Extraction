"""
Schema Module — Pydantic models defining the structured document JSON.

These models validate and enforce the output format for both
direct Docling passthrough and LLM-refined results.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box coordinates (left, top, right, bottom)."""
    l: float = 0.0
    t: float = 0.0
    r: float = 0.0
    b: float = 0.0


class DocumentElement(BaseModel):
    """A single document element (heading, paragraph, table, image, list, etc.)."""
    id: str = ""
    type: str = "paragraph"          # heading, paragraph, table, image, list, caption, formula, footer, header
    content: str = ""                # Text content
    level: Optional[int] = None      # Heading level (1-6), or nesting level
    column: Optional[int] = None     # Column number (1, 2, ...) or None for full-width
    reading_order: int = 0           # Correct reading order within the page
    bbox: Optional[BBox] = None      # Bounding box on the page
    confidence: Optional[float] = None
    corrections: List[str] = Field(default_factory=list)  # What the LLM fixed

    # ─── Table-specific fields ───
    headers: Optional[List[str]] = None
    rows: Optional[List[List[str]]] = None

    # ─── Image-specific fields ───
    description: Optional[str] = None
    caption: Optional[str] = None

    # ─── List-specific fields ───
    items: Optional[List[str]] = None
    style: Optional[str] = None      # "bulleted" or "numbered"


class PageResult(BaseModel):
    """Structured result for a single page."""
    page_number: int = 0
    layout_type: str = "single_column"   # single_column, two_column, multi_column, mixed
    width: float = 595.0
    height: float = 842.0
    was_refined: bool = False            # True if LLM was used
    refinement_reason: str = ""          # Why LLM was called (or "clean")
    orientation_correction_angle: Optional[int] = None
    elements: List[DocumentElement] = Field(default_factory=list)


class DocumentResult(BaseModel):
    """The final structured document output."""
    source_file: str = ""
    total_pages: int = 0
    processed_at: str = ""
    model_used: str = ""
    input_type: str = ""
    input_extension: str = ""
    is_scanned: bool = False
    preprocessing_applied: List[str] = Field(default_factory=list)
    pages_with_orientation_correction: List[int] = Field(default_factory=list)
    pages: List[PageResult] = Field(default_factory=list)
