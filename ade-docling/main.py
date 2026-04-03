"""
Main CLI — Entry point for the Agentic Document Parsing System.
"""

import logging
import argparse
import sys
import os

from agent.orchestrator import DocumentParsingAgent

# Configure logging to see the Agent's reasoning and process
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    parser = argparse.ArgumentParser(
        description="Agentic Document Parsing System using Docling",
        epilog="Converts PDFs, images, and office documents into structured JSON/Markdown with bounding-box visualizations."
    )
    parser.add_argument("file", type=str, help="Path to the source document (PDF, image, docx, etc.)")
    parser.add_argument("--format", type=str, choices=["json", "markdown"], default="markdown", 
                        help="Desired output format: 'json' or 'markdown' (default is 'markdown')")
    parser.add_argument("--no-viz", action="store_true", help="Disable bounding-box visualization")

    args = parser.parse_args()

    # Resolve input file: Support multiple input forms
    # - absolute/relative path: use as-is if exists
    # - filename only: look in input/ folder
    # - input/filename or input\filename: extract filename and look in input/
    file_arg = args.file
    
    if not os.path.exists(file_arg):
        # Extract just the filename (in case user passed input/test.pdf or input\test.pdf)
        filename_only = os.path.basename(file_arg)
        candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input", filename_only)
        if os.path.exists(candidate):
            file_arg = candidate

    # 1. Initialize the Agent orchestration system
    try:
        agent = DocumentParsingAgent()
    except Exception as e:
        print(f"\n[CRITICAL] Failed to initialize Agent: {e}")
        sys.exit(1)

    # 2. Start the automated process
    print(f"\n[+] Agent starting Document Lifecycle for: {args.file}")
    result = agent.process(
        file_path=file_arg,
        output_format=args.format,
        visualize=not args.no_viz
    )

    if result.get("status") == "success":
        print(f"\n[SUCCESS] Document processing complete!")
        print(f"  - Output Folder: {result['output_dir']}")
        print(f"  - JSON Output:   {result.get('json_output', '')}")
        print(f"  - MD Output:     {result.get('md_output', '')}")
        print(f"  - Input Type:    {result.get('input_type', 'UNKNOWN')}")
        print(f"  - Scanned PDF:   {result.get('is_scanned', False)}")
        print(f"  - Preprocessing: {result.get('preprocessing_applied', [])}")
        print(f"  - Rotated Pages: {result.get('pages_with_orientation_correction', [])}")
        print(f"  - Input File:    {file_arg}")
        img_count = result.get("image_assets_count", 0)
        if img_count:
            print(f"  - Image Assets:  {img_count} image(s) saved → {result.get('image_assets_dir', '')}")
        vizs = result.get('visualizations', [])
        if vizs:
            print(f"  - Visualizations: {len(vizs)} page(s) rendered with bounding boxes.")
            for v in vizs:
                print(f"      {v}")
    else:
        print(f"\n[FAILED] Agent encountered errors: {result.get('message')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
