import os
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

from config import PREPROCESSING_DPI
from preprocessing.orientation_corrector import correct_orientation


def preprocess_image(image_path: str, output_dir: str) -> Dict[str, object]:
    """Apply orientation correction to a single image input."""
    os.makedirs(output_dir, exist_ok=True)
    source_path = Path(image_path)
    image = cv2.imread(str(source_path))
    if image is None:
        raise ValueError(f"Could not load image for preprocessing: {image_path}")

    corrected_image, rotation = correct_orientation(image)
    output_path = Path(output_dir) / f"{source_path.stem}_corrected.png"
    cv2.imwrite(str(output_path), corrected_image)

    return {
        "page_number": 1,
        "rotation_angle": rotation,
        "image_path": str(output_path),
    }


def preprocess_pdf(pdf_path: str, output_dir: str, dpi: int = PREPROCESSING_DPI) -> List[Dict[str, object]]:
    """Rasterize a PDF page-by-page and apply orientation correction to each page."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for scanned PDF preprocessing") from exc

    os.makedirs(output_dir, exist_ok=True)
    processed_pages: List[Dict[str, object]] = []

    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            pix = page.get_pixmap(dpi=dpi)
            image = _pixmap_to_cv2(pix)
            corrected_image, rotation = correct_orientation(image)

            output_path = Path(output_dir) / f"page_{page_index}.png"
            cv2.imwrite(str(output_path), corrected_image)

            processed_pages.append({
                "page_number": page_index,
                "rotation_angle": rotation,
                "image_path": str(output_path),
            })

    return processed_pages


def _pixmap_to_cv2(pixmap):
    channels = 4 if pixmap.alpha else 3
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.h, pixmap.w, channels)
    if channels == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)