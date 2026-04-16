"""Parse PDFs to structured markdown using Docling."""

import argparse
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    AcceleratorDevice,
    AcceleratorOptions,
)


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
    parser = argparse.ArgumentParser(description="Convert PDFs to markdown with Docling")
    parser.add_argument("pdf_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("parse/output/markdown"),
        help="Output directory for markdown files (default: parse/output/markdown)",
    )
    parser.add_argument(
        "--device", default="auto", choices=["auto", "cpu"],
        help="Accelerator device (default: auto, detects GPU)",
    )
    args = parser.parse_args()

    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.pdf_dir}")
        return

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Converting {len(pdfs)} PDFs to markdown (device={args.device})...")

    converter = make_converter(args.device)

    for i, pdf in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] {pdf.name}")
        try:
            result = converter.convert(str(pdf))
            md = result.document.export_to_markdown()
            out_file = args.output / f"{pdf.stem}.md"
            out_file.write_text(md)
            print(f"  -> {out_file}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
