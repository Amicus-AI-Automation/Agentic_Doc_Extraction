"""
Image Asset Extractor — crops Docling-detected picture regions from source page images.

Saves each cropped region as a PNG under {output_dir}/image_assets/ and returns
metadata suitable for downstream embedding pipelines.
"""

import logging
import os
import re
import base64
from pathlib import Path
from typing import Any, Dict, List

from groq import Groq
from PIL import Image

from config import GROQ_API_KEY, VLM_MODEL, VLM_MAX_TOKENS, VLM_TEMPERATURE

logger = logging.getLogger(__name__)


class ImageAssetExtractor:
    """Extracts and saves cropped image assets from Docling picture regions.

    Coordinate conversion: Docling uses PDF bottom-left origin (y increases upward).
    PIL uses top-left origin (y increases downward). The Y-flip formula is:
        px_top    = min((doc_h - t) * scale_y, (doc_h - b) * scale_y)
        px_bottom = max((doc_h - t) * scale_y, (doc_h - b) * scale_y)
    where t > b numerically in PDF space.
    """

    def __init__(self):
        self.vlm_model = VLM_MODEL
        self.vlm_client = None
        if GROQ_API_KEY:
            try:
                self.vlm_client = Groq(api_key=GROQ_API_KEY)
            except Exception as exc:
                logger.warning("VLM Groq client init failed: %s", exc)

    def extract_and_save_assets(
        self,
        source_image_path: str,
        document,
        output_dir: str,
        page_number: int,
    ) -> Dict[str, Any]:
        """
        For each 'picture' item in `document` on `page_number`, crop the region
        from `source_image_path` and save to `{output_dir}/image_assets/`.

        Args:
            source_image_path: Absolute path to the source page image (PNG/JPG).
            document:          Docling DoclingDocument for this page.
            output_dir:        Base output directory (image_assets/ subdir created here).
            page_number:       External page number (1-based) used for naming and prov lookup.

        Returns:
            dict with:
              - image_assets: list of asset metadata dicts
              - image_assets_count: int
        """
        assets: List[Dict[str, Any]] = []

        if not source_image_path or not os.path.isfile(source_image_path):
            logger.warning(
                "Image asset extraction skipped — source image not found: %s",
                source_image_path,
            )
            return {"image_assets": assets, "image_assets_count": 0}

        assets_dir = Path(output_dir) / "image_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        try:
            pil_img = Image.open(source_image_path)
        except Exception as exc:
            logger.error("Cannot open source image for asset extraction: %s", exc)
            return {"image_assets": assets, "image_assets_count": 0}

        img_width, img_height = pil_img.size

        # Resolve document page dimensions — fall back to first available page key
        # (needed when a scanned page is parsed as a standalone 1-page doc whose
        # internal page key is always 1, even if the external page number is > 1)
        page_obj = None
        internal_page_number = page_number
        if hasattr(document, "pages") and document.pages:
            page_obj = document.pages.get(page_number)
            if page_obj is None:
                first_key = next(iter(document.pages), None)
                if first_key is not None:
                    page_obj = document.pages[first_key]
                    internal_page_number = first_key

        doc_w = (
            float(getattr(getattr(page_obj, "size", None), "width", img_width))
            if page_obj
            else float(img_width)
        )
        doc_h = (
            float(getattr(getattr(page_obj, "size", None), "height", img_height))
            if page_obj
            else float(img_height)
        )

        if doc_w == 0 or doc_h == 0:
            pil_img.close()
            logger.warning(
                "Zero-dimension page detected — skipping asset extraction for page %d",
                page_number,
            )
            return {"image_assets": assets, "image_assets_count": 0}

        scale_x = img_width / doc_w
        scale_y = img_height / doc_h

        counter = 1
        for item, _ in document.iterate_items():
            label = str(getattr(item, "label", "")).split(".")[-1].lower()
            if label != "picture":
                continue

            # Try exact page match first, then first available prov
            prov = self._first_matching_prov(item, internal_page_number)
            if prov is None:
                provs = getattr(item, "prov", None) or []
                prov = provs[0] if provs else None
            if prov is None:
                continue

            bbox = getattr(prov, "bbox", None)
            if bbox is None:
                continue

            l = float(getattr(bbox, "l", 0.0))
            t = float(getattr(bbox, "t", 0.0))
            r = float(getattr(bbox, "r", 0.0))
            b = float(getattr(bbox, "b", 0.0))

            # PDF bottom-left → PIL top-left Y-flip
            px_left   = int(l * scale_x)
            px_right  = int(r * scale_x)
            px_top    = int(min((doc_h - t) * scale_y, (doc_h - b) * scale_y))
            px_bottom = int(max((doc_h - t) * scale_y, (doc_h - b) * scale_y))

            # Clamp to image bounds
            px_left   = max(0, min(px_left,   img_width))
            px_right  = max(0, min(px_right,  img_width))
            px_top    = max(0, min(px_top,    img_height))
            px_bottom = max(0, min(px_bottom, img_height))

            if px_right <= px_left or px_bottom <= px_top:
                logger.warning(
                    "Skipping degenerate crop on page %d image %d (box: %d,%d → %d,%d)",
                    page_number, counter, px_left, px_top, px_right, px_bottom,
                )
                counter += 1
                continue

            asset_id       = f"p{page_number}_img{counter}"
            asset_filename = f"page_{page_number:04d}_image_{counter:03d}.png"
            asset_path     = assets_dir / asset_filename

            try:
                cropped = pil_img.crop((px_left, px_top, px_right, px_bottom))
                cropped.save(str(asset_path))
                logger.info("Saved image asset: %s", asset_path)
            except Exception as exc:
                logger.error("Failed to crop/save asset %s: %s", asset_id, exc)
                counter += 1
                continue

            ocr_text = self._extract_ocr_text_for_picture(
                document=document,
                picture_bbox=bbox,
                page_number=internal_page_number,
                item=item,
            )
            vlm_description = self._describe_with_vlm(str(asset_path))
            image_context = self._build_image_context(ocr_text, vlm_description)

            assets.append(
                {
                    "asset_id": asset_id,
                    "page_number": page_number,
                    "source_image_path": str(source_image_path),
                    "crop_path": str(asset_path),
                    "bbox_pdf": {"l": l, "t": t, "r": r, "b": b},
                    "crop_pixels": {
                        "left":   px_left,
                        "top":    px_top,
                        "right":  px_right,
                        "bottom": px_bottom,
                    },
                    "caption":     getattr(item, "caption",     "") or "",
                    "description": getattr(item, "description", "") or "",
                    "ocr_text": ocr_text,
                    "vlm_description": vlm_description,
                    "image_context": image_context,
                    "enrichment_status": self._resolve_status(ocr_text, vlm_description),
                }
            )
            counter += 1

        pil_img.close()
        return {"image_assets": assets, "image_assets_count": len(assets)}

    def _first_matching_prov(self, item, page_number: int):
        for prov in (getattr(item, "prov", None) or []):
            if getattr(prov, "page_no", None) == page_number:
                return prov
        return None

    def _extract_ocr_text_for_picture(self, document, picture_bbox, page_number: int, item=None) -> str:
        """Extract OCR-like text near/inside a picture region from Docling text elements."""
        tokens: List[tuple] = []
        nearby_tokens: List[tuple] = []

        for other_item, _ in document.iterate_items():
            label = str(getattr(other_item, "label", "")).split(".")[-1].lower()
            if label in ("picture", "table"):
                continue

            text = self._normalize_text(getattr(other_item, "text", ""))
            if not text:
                continue

            prov = self._first_matching_prov(other_item, page_number)
            if prov is None:
                provs = getattr(other_item, "prov", None) or []
                prov = provs[0] if provs else None
            if prov is None or getattr(prov, "bbox", None) is None:
                continue

            top = float(getattr(prov.bbox, "t", 0.0))
            left = float(getattr(prov.bbox, "l", 0.0))

            if self._bboxes_intersect(picture_bbox, prov.bbox):
                tokens.append((top, left, text))
            elif self._is_near_picture_region(picture_bbox, prov.bbox):
                nearby_tokens.append((top, left, text))

        # Keep a deterministic reading order approximation in PDF coords.
        tokens.sort(key=lambda it: (-it[0], it[1]))
        ocr_text = " ".join([t[2] for t in tokens]).strip()

        if not ocr_text and nearby_tokens:
            nearby_tokens.sort(key=lambda it: (-it[0], it[1]))
            ocr_text = " ".join([t[2] for t in nearby_tokens[:4]]).strip()

        # Fallback to picture-caption text when no in-box text was captured.
        if not ocr_text and item is not None:
            caption_obj = getattr(item, "caption", None)
            caption_text = ""
            if isinstance(caption_obj, str):
                caption_text = caption_obj
            elif caption_obj is not None:
                caption_text = getattr(caption_obj, "text", "") or ""
            ocr_text = self._normalize_text(caption_text)

        return ocr_text

    def _bboxes_intersect(self, a, b, min_overlap_ratio: float = 0.03) -> bool:
        al, ar = float(getattr(a, "l", 0.0)), float(getattr(a, "r", 0.0))
        ab, at = float(getattr(a, "b", 0.0)), float(getattr(a, "t", 0.0))
        bl, br = float(getattr(b, "l", 0.0)), float(getattr(b, "r", 0.0))
        bb, bt = float(getattr(b, "b", 0.0)), float(getattr(b, "t", 0.0))

        inter_w = max(0.0, min(ar, br) - max(al, bl))
        inter_h = max(0.0, min(at, bt) - max(ab, bb))
        inter = inter_w * inter_h
        if inter <= 0:
            return False

        area_a = max(0.0, ar - al) * max(0.0, at - ab)
        area_b = max(0.0, br - bl) * max(0.0, bt - bb)
        smaller = max(1e-6, min(area_a, area_b))
        return (inter / smaller) >= min_overlap_ratio

    def _is_near_picture_region(self, pic_bbox, txt_bbox) -> bool:
        """Heuristic fallback: include OCR text blocks near picture edges (e.g., captions)."""
        pl, pr = float(getattr(pic_bbox, "l", 0.0)), float(getattr(pic_bbox, "r", 0.0))
        pb, pt = float(getattr(pic_bbox, "b", 0.0)), float(getattr(pic_bbox, "t", 0.0))
        tl, tr = float(getattr(txt_bbox, "l", 0.0)), float(getattr(txt_bbox, "r", 0.0))
        tb, tt = float(getattr(txt_bbox, "b", 0.0)), float(getattr(txt_bbox, "t", 0.0))

        # Horizontal overlap ratio w.r.t. text block width
        inter_w = max(0.0, min(pr, tr) - max(pl, tl))
        txt_w = max(1e-6, tr - tl)
        horiz_overlap_ratio = inter_w / txt_w

        # Vertical gap (0 means touching/overlapping)
        if tt < pb:
            v_gap = pb - tt
        elif tb > pt:
            v_gap = tb - pt
        else:
            v_gap = 0.0

        return horiz_overlap_ratio >= 0.25 and v_gap <= 120.0

    def _normalize_text(self, text: str) -> str:
        text = text or ""
        return re.sub(r"\s+", " ", text).strip()

    def _describe_with_vlm(self, image_path: str) -> str:
        """Generate a concise visual description (chart/trend/object summary) using Groq VLM."""
        if self.vlm_client is None:
            return ""
        if not image_path or not os.path.isfile(image_path):
            return ""

        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            completion = self.vlm_client.chat.completions.create(
                model=self.vlm_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Describe this document image region concisely. "
                                    "If it is a chart/graph, mention axes, trend direction, "
                                    "and key takeaway in 2-4 sentences."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                temperature=VLM_TEMPERATURE,
                max_completion_tokens=VLM_MAX_TOKENS,
                top_p=1,
                stream=False,
                stop=None,
            )

            content = completion.choices[0].message.content
            if not content:
                return ""
            return self._normalize_text(str(content))
        except Exception as exc:
            logger.warning("VLM description failed for %s: %s", image_path, exc)
            return ""

    def _build_image_context(self, ocr_text: str, vlm_description: str) -> str:
        parts = []
        if vlm_description:
            parts.append(f"Visual summary: {vlm_description}")
        if ocr_text:
            parts.append(f"OCR text: {ocr_text}")
        return "\n".join(parts).strip()

    def _resolve_status(self, ocr_text: str, vlm_description: str) -> str:
        if ocr_text and vlm_description:
            return "ocr_vlm"
        if ocr_text:
            return "ocr_only"
        if vlm_description:
            return "vlm_only"
        return "empty"
