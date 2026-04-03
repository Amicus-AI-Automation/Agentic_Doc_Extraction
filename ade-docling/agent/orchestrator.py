"""
Orchestrator Module — The brains of the Document Parsing Agent.

Manages the lifecycle:
  1. Analyze Request
  2. Parse (via DoclingParser)
  3. Visualize (via BoundingBoxVisualizer)
  4. Format (via DocumentFormatter)
  5. Storage (via OutputStorage)
"""

import json
import os
import logging
import re
import shutil
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path

from .parser import DoclingParser
from .formatter import DocumentFormatter
from .storage import OutputStorage
from .visualizer import BoundingBoxVisualizer
from .input_detector import detect_input_type
from .image_cropper import ImageAssetExtractor
from preprocessing.preprocessing_pipeline import preprocess_image, preprocess_pdf

logger = logging.getLogger(__name__)

class DocumentParsingAgent:
    """
    Agentic Orchestrator that manages document processing.
    """
    
    def __init__(self):
        self.parser = DoclingParser()
        self.formatter = DocumentFormatter()
        self.storage = OutputStorage()
        self.visualizer = BoundingBoxVisualizer()
        self.image_extractor = ImageAssetExtractor()
        logger.info("DocumentParsingAgent initialized.")

    def process(
        self, 
        file_path: str, 
        output_format: str = "markdown", 
        visualize: bool = True
    ) -> Dict[str, Any]:
        """
        Main workflow execution.
        """
        logger.info(f"==== Agent parsing process initiated for: {file_path} ====")
        
        preprocessing_temp_dir = None
        try:
            # 1. Validation & Setup
            input_path = Path(file_path).resolve()
            if not input_path.exists():
                raise FileNotFoundError(f"Document not found: {input_path}")

            project_root = Path(__file__).resolve().parent.parent
            base_output_dir = project_root / "output" / input_path.stem
            os.makedirs(base_output_dir, exist_ok=True)

            input_type_info = detect_input_type(str(input_path))
            logger.info(
                "Detected input type=%s extension=%s scanned=%s",
                input_type_info.detected_format,
                input_type_info.extension,
                input_type_info.is_scanned,
            )

            preprocessing_applied = []
            pages_with_orientation_correction = []
            viz_paths = {}
            all_image_assets = []

            fmt = output_format.lower()
            logger.info(f"--> Agent rendering to target format: {fmt}")

            if input_type_info.detected_format == "IMAGE" and input_type_info.requires_orientation_correction:
                logger.info("--> Running image orientation preprocessing")
                preprocessing_temp_dir = tempfile.mkdtemp(prefix="ade_preprocess_")
                processed = preprocess_image(str(input_path), preprocessing_temp_dir)
                parsed_page = self.parser.extract_single_page_data(
                    conversion_result=self.parser.parse(processed["image_path"]),
                    page_number=processed["page_number"],
                    rotation_angle=processed.get("rotation_angle", 0),
                    source_image_path=processed["image_path"],
                )
                parsed_pages = [parsed_page]
                preprocessing_applied.append("orientation_correction")
                pages_with_orientation_correction = [
                    page["page_number"]
                    for page in parsed_pages
                    if page.get("rotation_angle", 0) not in (None, 0)
                ]

                if visualize:
                    viz_dir = base_output_dir / "visualizations"
                    page_viz = self.visualizer.render_from_source_image(
                        document=parsed_page["document"],
                        source_image_path=processed["image_path"],
                        output_dir=str(viz_dir),
                        page_number=parsed_page["page_number"],
                        base_name=input_path.stem,
                    )
                    viz_paths.update(page_viz)

                for pp in parsed_pages:
                    _assets = self.image_extractor.extract_and_save_assets(
                        source_image_path=pp.get("source_image_path", ""),
                        document=pp["document"],
                        output_dir=str(base_output_dir),
                        page_number=pp["page_number"],
                    )
                    all_image_assets.extend(_assets["image_assets"])

                json_data = self.formatter.format_pages_as_json(
                    parsed_pages=parsed_pages,
                    source_file=str(input_path),
                    input_type_info=input_type_info,
                    preprocessing_applied=preprocessing_applied,
                )
                md_data = self.formatter.format_pages_as_markdown(
                    parsed_pages=parsed_pages,
                    source_file=str(input_path),
                    input_type_info=input_type_info,
                    preprocessing_applied=preprocessing_applied,
                )

            elif input_type_info.detected_format == "PDF" and input_type_info.is_scanned:
                logger.info("--> Running scanned PDF preprocessing and page-wise parsing")
                preprocessing_temp_dir = tempfile.mkdtemp(prefix="ade_preprocess_")
                processed_pages = preprocess_pdf(str(input_path), preprocessing_temp_dir)
                parsed_pages = []
                preprocessing_applied.append("orientation_correction")

                for processed_page in processed_pages:
                    conversion_result = self.parser.parse(processed_page["image_path"])
                    parsed_pages.append(
                        self.parser.extract_single_page_data(
                            conversion_result=conversion_result,
                            page_number=processed_page["page_number"],
                            rotation_angle=processed_page.get("rotation_angle", 0),
                            source_image_path=processed_page["image_path"],
                        )
                    )

                pages_with_orientation_correction = [
                    page["page_number"]
                    for page in parsed_pages
                    if page.get("rotation_angle", 0) not in (None, 0)
                ]

                if visualize:
                    viz_dir = base_output_dir / "visualizations"
                    for page, proc in zip(parsed_pages, processed_pages):
                        page_viz = self.visualizer.render_from_source_image(
                            document=page["document"],
                            source_image_path=proc["image_path"],
                            output_dir=str(viz_dir),
                            page_number=page["page_number"],
                            base_name=input_path.stem,
                        )
                        viz_paths.update(page_viz)

                for pp in parsed_pages:
                    _assets = self.image_extractor.extract_and_save_assets(
                        source_image_path=pp.get("source_image_path", ""),
                        document=pp["document"],
                        output_dir=str(base_output_dir),
                        page_number=pp["page_number"],
                    )
                    all_image_assets.extend(_assets["image_assets"])

                json_data = self.formatter.format_pages_as_json(
                    parsed_pages=parsed_pages,
                    source_file=str(input_path),
                    input_type_info=input_type_info,
                    preprocessing_applied=preprocessing_applied,
                )
                md_data = self.formatter.format_pages_as_markdown(
                    parsed_pages=parsed_pages,
                    source_file=str(input_path),
                    input_type_info=input_type_info,
                    preprocessing_applied=preprocessing_applied,
                )

            else:
                logger.info("--> Running direct Docling parsing path")
                result = self.parser.parse(str(input_path))
                document = result.document

                if visualize:
                    logger.info("--> Agent generating bounding-box visualizations")
                    viz_dir = base_output_dir / "visualizations"
                    viz_paths = self.visualizer.render(
                        document=document,
                        output_dir=str(viz_dir),
                        base_name=input_path.stem,
                    )

                json_data = self.formatter.format_as_json(
                    document,
                    source_file=str(input_path),
                    input_type_info=input_type_info,
                    preprocessing_applied=preprocessing_applied,
                    pages_with_orientation_correction=pages_with_orientation_correction,
                )
                md_data = self.formatter.format_as_markdown(
                    document,
                    source_file=str(input_path),
                    input_type_info=input_type_info,
                    preprocessing_applied=preprocessing_applied,
                    pages_with_orientation_correction=pages_with_orientation_correction,
                )

            # Inject collected image assets into outputs.
            json_data = self._inject_image_assets_into_json(json_data, all_image_assets)
            md_data = self._append_image_insights_to_markdown(md_data, all_image_assets)

            # 5. Save outputs
            json_file = base_output_dir / "extracted_content.json"
            md_file = base_output_dir / "extracted_content.md"
            self.storage.save(json_data, str(json_file))
            self.storage.save(md_data, str(md_file))

            logger.info("==== Agent parsing process completed successfully ====")
            return {
                "status": "success",
                "output_dir": str(base_output_dir),
                "json_output": str(json_file),
                "md_output": str(md_file),
                "main_output": str(json_file if fmt == "json" else md_file),
                "visualizations": list(viz_paths.values()),
                "format": fmt,
                "input_type": input_type_info.detected_format,
                "input_extension": input_type_info.extension,
                "is_scanned": input_type_info.is_scanned,
                "preprocessing_applied": preprocessing_applied,
                "pages_with_orientation_correction": pages_with_orientation_correction,
                "image_assets_count": len(all_image_assets),
                "image_assets_dir": str(base_output_dir / "image_assets") if all_image_assets else "",
            }
            
        except Exception as e:
            logger.error(f"Agent experienced an error: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            if preprocessing_temp_dir and os.path.isdir(preprocessing_temp_dir):
                shutil.rmtree(preprocessing_temp_dir, ignore_errors=True)

    def _inject_image_assets_into_json(self, json_text: str, image_assets: list) -> str:
        if not image_assets:
            return json_text
        try:
            payload = json.loads(json_text)
        except Exception as exc:
            logger.warning("Could not parse JSON output for image asset injection: %s", exc)
            return json_text

        payload["image_assets"] = image_assets
        self._inject_image_context_in_pages(payload, image_assets)

        try:
            return json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Could not serialize JSON output after image asset injection: %s", exc)
            return json_text

    def _inject_image_context_in_pages(self, payload: dict, image_assets: list) -> None:
        by_id = {asset.get("asset_id", ""): asset for asset in image_assets if asset.get("asset_id")}
        by_page = {}
        for asset in image_assets:
            page_no = int(asset.get("page_number", 0) or 0)
            by_page.setdefault(page_no, []).append(asset)

        for page_no in by_page:
            by_page[page_no].sort(key=lambda a: self._asset_sort_key(a.get("asset_id", "")))

        pages = payload.get("pages", [])
        if not isinstance(pages, list):
            return

        for page in pages:
            if not isinstance(page, dict):
                continue
            page_no = int(page.get("page_number", 0) or 0)
            page_assets = by_page.get(page_no, [])

            # Path A: pre-LLM pages with "content" image items.
            content = page.get("content")
            if isinstance(content, list):
                img_index = 0
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "image":
                        continue
                    asset = page_assets[img_index] if img_index < len(page_assets) else None
                    if asset:
                        self._merge_asset_fields(block, asset)
                    img_index += 1

            # Path B: post-LLM pages with "elements" image items and ids.
            elements = page.get("elements")
            if isinstance(elements, list):
                used_assets = set()
                fallback_idx = 0
                for elem in elements:
                    if not isinstance(elem, dict) or elem.get("type") != "image":
                        continue
                    elem_id = elem.get("id", "")
                    asset = by_id.get(elem_id)
                    if asset is None:
                        while fallback_idx < len(page_assets) and page_assets[fallback_idx].get("asset_id") in used_assets:
                            fallback_idx += 1
                        if fallback_idx < len(page_assets):
                            asset = page_assets[fallback_idx]
                            fallback_idx += 1
                    if asset:
                        used_assets.add(asset.get("asset_id", ""))
                        self._merge_asset_fields(elem, asset)

    def _merge_asset_fields(self, target: dict, asset: dict) -> None:
        target["asset_id"] = asset.get("asset_id", "")
        target["crop_path"] = asset.get("crop_path", "")
        target["ocr_text"] = asset.get("ocr_text", "")
        target["vlm_description"] = asset.get("vlm_description", "")
        target["image_context"] = asset.get("image_context", "")
        target["enrichment_status"] = asset.get("enrichment_status", "")

    def _asset_sort_key(self, asset_id: str) -> int:
        match = re.search(r"img(\d+)$", asset_id or "")
        return int(match.group(1)) if match else 10**9

    def _append_image_insights_to_markdown(self, md_text: str, image_assets: list) -> str:
        if not image_assets:
            return md_text
        if "## Image Insights" in md_text:
            return md_text

        assets_sorted = sorted(
            image_assets,
            key=lambda a: (int(a.get("page_number", 0) or 0), self._asset_sort_key(a.get("asset_id", ""))),
        )

        lines = ["## Image Insights", ""]
        for asset in assets_sorted:
            page_no = int(asset.get("page_number", 0) or 0)
            asset_id = asset.get("asset_id", "")
            status = asset.get("enrichment_status", "")
            vlm_description = (asset.get("vlm_description", "") or "").strip()
            image_context = (asset.get("image_context", "") or "").strip()
            if not image_context:
                image_context = "(no OCR text extracted)"
            lines.append(f"- page {page_no} | {asset_id} | status={status}")
            if vlm_description:
                lines.append(f"  - visual: {vlm_description}")
            lines.append(f"  - text: {image_context}")

        return md_text.rstrip() + "\n\n" + "\n".join(lines) + "\n"
