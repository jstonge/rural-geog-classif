"""Parse PDFs to structured output using Docling."""

import argparse
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    AcceleratorDevice,
    AcceleratorOptions,
)

EXPORTERS = {
    "markdown": ("md", lambda doc: doc.export_to_markdown()),
    "text": ("txt", lambda doc: doc.export_to_text()),
    "json": ("json", lambda doc: doc.export_to_dict()),
}


def make_converter(device: str = "auto") -> DocumentConverter:
    accel = AcceleratorDevice.AUTO if device == "auto" else AcceleratorDevice.CPU
    pipeline_opts = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=accel),
    )
    converter = DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_opts)}
    )
    return converter


def main():
    parser = argparse.ArgumentParser(description="Convert PDFs with Docling")
    parser.add_argument("pdf_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output directory (default: parse/output/<parser>)",
    )
    parser.add_argument(
        "--format", default="markdown", choices=EXPORTERS.keys(),
        help="Export format (default: markdown)",
    )
    parser.add_argument(
        "--device", default="auto", choices=["auto", "cpu"],
        help="Accelerator device (default: auto, detects GPU)",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = Path("parse/output/docling")

    ext, export_fn = EXPORTERS[args.format]

    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.pdf_dir}")
        return

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Converting {len(pdfs)} PDFs to {args.format} (device={args.device})...")

    converter = make_converter(args.device)

    for i, pdf in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] {pdf.name}")
        try:
            result = converter.convert(str(pdf))
            content = export_fn(result.document)
            if args.format == "json":
                import json
                content = json.dumps(content, indent=2)
            out_file = args.output / f"{pdf.stem}.{ext}"
            out_file.write_text(content)
            print(f"  -> {out_file}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
