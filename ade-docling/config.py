"""
Central Configuration for ADE Agent System.
Loads API keys from .env and defines system-wide settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_PPT_EXTENSIONS = {".ppt", ".pptx"}
SUPPORTED_DOC_EXTENSIONS = {".docx"}
SUPPORTED_SHEET_EXTENSIONS = {".xlsx"}
SUPPORTED_TEXT_EXTENSIONS = {".html", ".htm", ".csv", ".md"}

# ─── Groq / LLM Configuration ─────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

# ─── Input Detection / Preprocessing ─────────────────────────────────
PDF_TEXT_LAYER_MIN_CHARS = 25
PDF_SCAN_CHECK_PAGES = 3
PREPROCESSING_DPI = 300

# ─── Complexity Detection Thresholds ──────────────────────────────────
COLUMN_WIDTH_RATIO = 0.65       # Elements wider than page_width * this are "full-width"
MIN_COLUMN_ELEMENTS = 3         # Need at least this many elements per column to detect multi-column
GARBLED_TEXT_THRESHOLD = 0.15   # If > 15% of words look garbled, trigger LLM refinement
COMPLEXITY_THRESHOLDS = {
	"PDF_NATIVE": {
		"column_width_ratio": 0.65,
		"garbled_text_threshold": 0.12,
	},
	"PDF_SCANNED": {
		"column_width_ratio": 0.65,
		"garbled_text_threshold": 0.20,
	},
	"IMAGE": {
		"column_width_ratio": 0.65,
		"garbled_text_threshold": 0.22,
	},
	"PPTX": {
		"column_width_ratio": 0.55,
		"garbled_text_threshold": 0.15,
	},
	"DEFAULT": {
		"column_width_ratio": COLUMN_WIDTH_RATIO,
		"garbled_text_threshold": GARBLED_TEXT_THRESHOLD,
	},
}

# ─── LLM Refinement ──────────────────────────────────────────────────
MAX_ELEMENTS_PER_LLM_CALL = 100  # Max elements to send per page (truncate if more)
LLM_TEMPERATURE = 0.1            # Low temp for deterministic layout reasoning
LLM_MAX_TOKENS = 4096            # Max output tokens per page

# ─── VLM Image Processing (Groq) ─────────────────────────────────────
VLM_MODEL = os.getenv("VLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
VLM_MAX_TOKENS = int(os.getenv("VLM_MAX_TOKENS", "1024"))
VLM_TEMPERATURE = float(os.getenv("VLM_TEMPERATURE", "1"))
