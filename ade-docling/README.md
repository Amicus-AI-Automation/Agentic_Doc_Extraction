# ADE Agent — Agentic Document Extraction

A document parsing pipeline that extracts structured content from PDFs, scanned documents, and images using [Docling](https://github.com/DS4SD/docling) for layout analysis, with automatic image cropping, OCR text extraction, and Groq VLM image descriptions.

---

## Features

- **Multi-format input** — native PDFs, scanned PDFs, images (PNG, JPG, TIFF, BMP, WebP), DOCX, PPTX, XLSX, HTML, CSV, Markdown
- **Automatic input type detection** — distinguishes native PDFs from scanned ones, triggers appropriate preprocessing path
- **Orientation correction** — EasyOCR-based rotation detection and correction for skewed scanned pages
- **Image asset extraction** — crops detected picture regions from pages, saves as PNG files
- **OCR enrichment** — extracts Docling-detected text overlapping each cropped image region
- **VLM image descriptions** — sends each cropped image to Groq's `meta-llama/llama-4-scout-17b-16e-instruct` vision model for a concise visual description
- **Bounding-box visualizations** — renders detected element bounding boxes on top of pages (optional)
- **Dual output format** — JSON and Markdown, both including image enrichment metadata

---

## Project Structure

```
ADE_AGENTold/
├── main.py                        # CLI entry point
├── config.py                      # All configuration and constants
├── requirements.txt               # Python dependencies
├── .env                           # API keys (not committed)
│
├── input/                         # Place your documents here
│   ├── test_pdf.pdf
│   ├── test2.pdf
│   └── test3.pdf
│
├── output/                        # All outputs land here, one folder per document
│   └── <document_stem>/
│       ├── extracted_content.json           # Structured extraction (JSON)
│       ├── extracted_content.md             # Structured extraction (Markdown)
│       ├── image_assets/                    # Cropped image regions
│       │   └── page_0001_image_001.png
│       └── visualizations/                  # Bounding-box debug renders (optional)
│           └── <stem>_page_1.png
│
├── agent/
│   ├── orchestrator.py            # Pipeline orchestration (main workflow)
│   ├── parser.py                  # Docling parsing wrapper
│   ├── formatter.py               # JSON / Markdown renderer
│   ├── image_cropper.py           # Image asset extraction + OCR + VLM enrichment
│   ├── input_detector.py          # Input type detection (PDF/IMAGE/DOCX/...)
│   ├── visualizer.py              # Bounding-box visualization renderer
│   ├── storage.py                 # File save utility
│   ├── schema.py                  # Pydantic data models
│   └── __init__.py
│
└── preprocessing/
    ├── preprocessing_pipeline.py  # Scanned PDF / image preprocessing orchestration
    ├── orientation_corrector.py   # EasyOCR-based rotation detection
    └── __init__.py
```

---

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd ADE_AGENTold
```

### 2. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `easyocr` will download model weights (~200 MB) on first run. `docling` downloads layout and OCR models on first run as well.

### 4. Configure API keys

Copy `.env.example` to `.env` and add your Groq API key:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

Optional overrides (defaults shown):

```env
VLM_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
VLM_MAX_TOKENS=1024
VLM_TEMPERATURE=1
```

---

## Usage

Place your document in the `input/` folder and run:

```bash
python main.py <filename>
```

The filename can be:
- Just the name (e.g., `document.pdf`) — auto-resolved from `input/`
- A full or relative path to any file anywhere on disk

### Examples

```bash
# Default output (Markdown), with bounding-box visualizations
python main.py test_pdf.pdf

# JSON output, skip visualizations (faster)
python main.py test2.pdf --format json --no-viz

# Full path to a file outside input/ (use forward slashes in bash/Git Bash)
python main.py /path/to/report.pdf --format json

# On Windows PowerShell, backslashes work naturally
python main.py C:\Documents\report.pdf --format json
```

**Note for bash/Git Bash users:** Use forward slashes (`/`) for paths, not backslashes. These work on all platforms:
```bash
python main.py input/test2.pdf      # preferred
python main.py test2.pdf            # also works (auto-resolved from input/)
```

### CLI Arguments

| Argument | Description | Default |
|---|---|---|
| `file` | Document to process (filename or path) | *(required)* |
| `--format` | Output format: `json` or `markdown` | `markdown` |
| `--no-viz` | Disable bounding-box visualization renders | off |

---

## Output Files

For a document named `report.pdf`, outputs are written to `output/report/`:

| File | Description |
|---|---|
| `extracted_content.json` | Full structured extraction as JSON with image metadata |
| `extracted_content.md` | Full structured extraction as Markdown with `## Image Insights` section |
| `image_assets/page_NNNN_image_NNN.png` | Cropped image regions extracted from each page |
| `visualizations/<stem>_page_N.png` | Bounding-box debug renders (only when `--no-viz` is not set) |

### Image Enrichment Fields

Each detected image in the JSON output includes:

```json
{
  "type": "image",
  "asset_id": "p1_img1",
  "crop_path": "output/report/image_assets/page_0001_image_001.png",
  "ocr_text": "Figure 1. Revenue growth by quarter.",
  "vlm_description": "A bar chart showing quarterly revenue from Q1 to Q4 2024...",
  "image_context": "Figure 1. Revenue growth by quarter.\n\nA bar chart showing...",
  "enrichment_status": "ocr_vlm"
}
```

`enrichment_status` values:

| Value | Meaning |
|---|---|
| `ocr_vlm` | Both OCR text and VLM description available |
| `ocr_only` | OCR text only (VLM call failed or API key missing) |
| `vlm_only` | VLM description only (no OCR text found near the image) |
| `empty` | No enrichment available |

---

## Pipeline Overview

```
Input Document
     │
     ▼
Input Detection ──► Is it scanned? ──► Orientation Correction (EasyOCR)
     │                                         │
     │◄────────────────────────────────────────┘
     ▼
Docling Parsing (layout, OCR, tables, pictures)
     │
     ▼
Image Asset Extraction
  ├─ Crop picture regions from page images
  ├─ Extract overlapping OCR text (Docling text items)
  └─ Send cropped images to Groq VLM for visual description
     │
     ▼
Format as JSON + Markdown
  └─ Inject image_assets into JSON
  └─ Append ## Image Insights to Markdown
     │
     ▼
Save to output/<document_stem>/
```

---

## Configuration Reference (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(from .env)* | Groq API key for VLM image descriptions |
| `VLM_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq vision model |
| `VLM_MAX_TOKENS` | `1024` | Max tokens for VLM response per image |
| `VLM_TEMPERATURE` | `1` | Sampling temperature for VLM |
| `PREPROCESSING_DPI` | `300` | DPI used when converting scanned PDF pages to images |
| `PDF_TEXT_LAYER_MIN_CHARS` | `25` | Minimum characters to classify a PDF as "native" (not scanned) |
| `PDF_SCAN_CHECK_PAGES` | `3` | Number of pages to sample when deciding if PDF is scanned |

---

## Supported File Types

| Category | Extensions |
|---|---|
| PDF | `.pdf` (native and scanned) |
| Images | `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp` |
| Office | `.docx`, `.pptx`, `.ppt`, `.xlsx` |
| Text/Web | `.html`, `.htm`, `.csv`, `.md` |

---

## Notes

- **CPU-only systems:** EasyOCR and Docling both run on CPU but are significantly slower than GPU. Scanned PDFs with many pages can take several minutes per page.
- **First run:** Expect model weight downloads (EasyOCR CRAFT detector + recognition model, Docling layout/table models). Subsequent runs use cached weights.
- **No GROQ_API_KEY:** The pipeline still runs fully — image assets are extracted and OCR text is populated, but `vlm_description` will be empty and `enrichment_status` will be `ocr_only` or `empty`.
