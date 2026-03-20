"""
Visualization Module — renders bounding-box annotated pages.

Uses DoclingDocument.get_visualization() which draws labelled
bounding boxes on every page image that Docling generated during
parsing.  The result is a dict[page_no → PIL.Image].

Output: a folder of PNG images, one per page, showing exactly
where each text block / table / picture was detected.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional

from PIL import Image

logger = logging.getLogger(__name__)


class BoundingBoxVisualizer:
    """
    Produces bounding-box annotated page images from a parsed
    DoclingDocument.
    """

    def render(
        self,
        document,
        output_dir: str,
        base_name: str = "page",
    ) -> Dict[int, str]:
        """
        Generate bounding-box images for every page.

        Parameters
        ----------
        document : DoclingDocument
            The parsed document with page images already generated.
        output_dir : str
            Directory in which to write the output PNGs.
        base_name : str
            Prefix for individual page filenames.

        Returns
        -------
        dict mapping page number → saved file path
        """
        os.makedirs(output_dir, exist_ok=True)
        saved: Dict[int, str] = {}

        try:
            # get_visualization returns dict[Optional[int], PIL.Image]
            viz_images = document.get_visualization()
        except Exception as e:
            logger.warning(
                f"get_visualization() failed ({e}). "
                "Falling back to manual bounding-box rendering."
            )
            viz_images = self._fallback_render(document)

        if not viz_images:
            logger.warning("No page visualizations were produced.")
            return saved

        for page_no, img in viz_images.items():
            page_label = page_no if page_no is not None else 0
            fname = f"{base_name}_{page_label}.png"
            fpath = os.path.join(output_dir, fname)
            img.save(fpath)
            saved[page_label] = fpath
            logger.info(f"  Saved bbox page image → {fpath}")

        return saved

    # ------------------------------------------------------------------ #
    # Image-backed render: draw boxes on a pre-existing source image     #
    # Used when Docling didn't retain page images (scanned/image paths)  #
    # ------------------------------------------------------------------ #
    def render_from_source_image(
        self,
        document,
        source_image_path: str,
        output_dir: str,
        page_number: int,
        base_name: str = "page",
    ) -> Dict[int, str]:
        """
        Draw Docling bounding boxes on a saved source image (e.g. the
        orientation-corrected PNG produced during preprocessing).

        Handles coordinate scaling from Docling's page units to pixel space.
        """
        from PIL import Image, ImageDraw

        os.makedirs(output_dir, exist_ok=True)
        saved: Dict[int, str] = {}

        try:
            img = Image.open(source_image_path).convert("RGB")
        except Exception as exc:
            logger.warning("Could not load source image %s: %s", source_image_path, exc)
            return saved

        img_w, img_h = img.size

        # Try to read Docling's recorded page dimensions for correct scaling.
        doc_w: float = float(img_w)
        doc_h: float = float(img_h)
        if hasattr(document, "pages") and document.pages:
            for _, page_obj in document.pages.items():
                size = getattr(page_obj, "size", None)
                if size:
                    w = getattr(size, "width", None)
                    h = getattr(size, "height", None)
                    if w and h:
                        doc_w, doc_h = float(w), float(h)
                        break

        scale_x = img_w / doc_w
        scale_y = img_h / doc_h

        colour_map = {
            "title": "#FF4444",
            "section_header": "#FF8800",
            "text": "#2266FF",
            "paragraph": "#2266FF",
            "list_item": "#22AA44",
            "table": "#AA22FF",
            "picture": "#FF22AA",
            "caption": "#888888",
            "formula": "#00AAAA",
            "code": "#00AAAA",
            "form": "#AAAA00",
            "key_value_area": "#FF6600",
        }

        draw = ImageDraw.Draw(img)

        for item, _ in document.iterate_items():
            label = getattr(item, "label", None)
            if label is not None:
                label = str(label).split(".")[-1].lower()

            for prov in (getattr(item, "prov", None) or []):
                bbox = getattr(prov, "bbox", None)
                if bbox is None:
                    continue

                l = getattr(bbox, "l", None)
                t = getattr(bbox, "t", None)
                r = getattr(bbox, "r", None)
                b = getattr(bbox, "b", None)

                if None in (l, t, r, b):
                    continue

                px_l = l * scale_x
                px_r = r * scale_x
                # Docling uses PDF bottom-left origin: t > b numerically.
                # PIL uses top-left origin: y increases downward.
                # Correct transform: PIL_y = (doc_h - pdf_y) * scale.
                # Since t > b: (doc_h - t) < (doc_h - b), so top < bottom ✓
                px_t = min((doc_h - t) * scale_y, (doc_h - b) * scale_y)
                px_b = max((doc_h - t) * scale_y, (doc_h - b) * scale_y)

                colour = colour_map.get(label, "#CCCCCC")
                draw.rectangle([px_l, px_t, px_r, px_b], outline=colour, width=2)
                if label:
                    try:
                        draw.text((px_l + 2, max(px_t - 12, 0)), label, fill=colour)
                    except Exception:
                        pass

        fname = f"{base_name}_p{page_number}_viz.png"
        fpath = os.path.join(output_dir, fname)
        img.save(fpath)
        saved[page_number] = fpath
        logger.info("  Saved source-image bbox visualization → %s", fpath)
        return saved

    # ------------------------------------------------------------------ #
    # Fallback: manually draw boxes if get_visualization() is unavailable #
    # ------------------------------------------------------------------ #
    def _fallback_render(self, document) -> dict:
        """
        Walk iterate_items(), collect bounding boxes, and draw them
        onto the page images stored inside the document.
        """
        from PIL import ImageDraw, ImageFont

        pages: dict = {}

        # Collect the base page images from the document pages dict
        if not hasattr(document, "pages") or not document.pages:
            return pages

        for page_no, page_obj in document.pages.items():
            if hasattr(page_obj, "image") and page_obj.image is not None:
                img_data = page_obj.image
                if hasattr(img_data, "pil_image") and img_data.pil_image is not None:
                    pages[page_no] = img_data.pil_image.copy()

        if not pages:
            return pages

        # Colour map for different element types
        colour_map = {
            "title": "#FF4444",
            "section_header": "#FF8800",
            "text": "#2266FF",
            "paragraph": "#2266FF",
            "list_item": "#22AA44",
            "table": "#AA22FF",
            "picture": "#FF22AA",
            "caption": "#888888",
            "formula": "#00AAAA",
            "code": "#00AAAA",
            "form": "#AAAA00",
            "key_value_area": "#FF6600",
        }

        for item, level in document.iterate_items():
            label = getattr(item, "label", None)
            if label is not None:
                label = str(label).split(".")[-1].lower()

            prov_list = getattr(item, "prov", None) or []
            for prov in prov_list:
                pg = getattr(prov, "page_no", None)
                bbox = getattr(prov, "bbox", None)
                if pg is None or bbox is None or pg not in pages:
                    continue

                img = pages[pg]
                draw = ImageDraw.Draw(img)

                # bbox coords — docling uses (l, t, r, b)
                coords = None
                if hasattr(bbox, "l"):
                    coords = (bbox.l, bbox.t, bbox.r, bbox.b)
                elif hasattr(bbox, "to_tuple"):
                    coords = bbox.to_tuple()

                if coords is None:
                    continue

                colour = colour_map.get(label, "#CCCCCC")
                draw.rectangle(coords, outline=colour, width=2)
                if label:
                    try:
                        draw.text(
                            (coords[0] + 2, coords[1] - 12),
                            label,
                            fill=colour,
                        )
                    except Exception:
                        pass

        return pages
