"""Parse PDFs with Docling's VLM pipeline against a remote vLLM endpoint
serving granite-docling-258M.

Start the server first (on a free port — gemma is on 8000):

    vllm serve ibm-granite/granite-docling-258M \\
        --revision untied \\
        --port 8001 \\
        --limit-mm-per-prompt '{"image": 1}'

Then run this script pointing at it:

    python parse/src/parse_pdfs_granite.py path/to/pdfs/ \\
        --url http://localhost:8001/v1/chat/completions
"""

import argparse
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmPipelineOptions
from docling.datamodel.pipeline_options_vlm_model import (
    ApiVlmOptions,
    ResponseFormat,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline

EXPORTERS = {
    "markdown": ("md", lambda doc: doc.export_to_markdown()),
    "text": ("txt", lambda doc: doc.export_to_text()),
    "json": ("json", lambda doc: doc.export_to_dict()),
    "html": ("html", lambda doc: doc.export_to_html()),
}


def make_converter(url: str, model: str, timeout: int) -> DocumentConverter:
    api_vlm = ApiVlmOptions(
        url=url,
        params={"model": model},
        prompt="Convert this page to docling.",
        timeout=timeout,
        scale=1.0,
        response_format=ResponseFormat.DOCTAGS,
    )
    pipeline_options = VlmPipelineOptions(
        vlm_options=api_vlm,
        enable_remote_services=True,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=pipeline_options,
            ),
        }
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDFs by hitting a vLLM endpoint serving granite-docling"
    )
    parser.add_argument("pdf_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output directory (default: parse/output/granite_docling)",
    )
    parser.add_argument(
        "--format", default="markdown", choices=EXPORTERS.keys(),
        help="Export format (default: markdown)",
    )
    parser.add_argument(
        "--url", default="http://localhost:8001/v1/chat/completions",
        help="vLLM chat completions endpoint",
    )
    parser.add_argument(
        "--model", default="ibm-granite/granite-docling-258M",
        help="Model name as served by vLLM",
    )
    parser.add_argument(
        "--timeout", type=int, default=120,
        help="Per-page request timeout in seconds",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = Path("parse/output/granite_docling")

    ext, export_fn = EXPORTERS[args.format]

    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.pdf_dir}")
        return

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Converting {len(pdfs)} PDFs via {args.url} -> {args.format}")

    converter = make_converter(args.url, args.model, args.timeout)

    total_start = time.perf_counter()
    for i, pdf in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] {pdf.name}")
        t0 = time.perf_counter()
        try:
            result = converter.convert(str(pdf))
            content = export_fn(result.document)
            if args.format == "json":
                import json
                content = json.dumps(content, indent=2)
            out_file = args.output / f"{pdf.stem}.{ext}"
            out_file.write_text(content)
            elapsed = time.perf_counter() - t0
            print(f"  -> {out_file}  ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  ERROR: {e}")

    total = time.perf_counter() - total_start
    print(f"Done in {total:.1f}s ({total / len(pdfs):.1f}s/pdf avg)")


if __name__ == "__main__":
    main()
