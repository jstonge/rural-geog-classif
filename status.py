"""Generate a pipeline status CSV from the WoS metadata.

For every row in the WoS CSV, checks whether the PDF exists,
whether Docling has parsed it, whether it has been summarized,
and whether it matched an OpenAlex record.

Usage:
    uv run python status.py              # prints to stdout
    uv run python status.py -o status.csv
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WOS_CSV = ROOT / "extract" / "input" / "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
PDF_DIR = ROOT / "extract" / "output" / "pdfs"
DOCLING_DIR = ROOT / "parse" / "output" / "docling"
SUMMARY_DIR = ROOT / "summarize" / "output"
OPENALEX_JSON = ROOT / "extract" / "output" / "openalex_works.json"


def doi_to_key(doi: str) -> str:
    return doi.replace("/", "_")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline status report")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output CSV path (default: stdout)")
    parser.add_argument("--missing", action="store_true",
                        help="Print DOI links for papers without PDFs")
    args = parser.parse_args()

    # Load OpenAlex DOIs
    oa_dois = set()
    if OPENALEX_JSON.exists():
        with open(OPENALEX_JSON, encoding="utf-8") as f:
            for w in json.load(f):
                if w.get("doi"):
                    oa_dois.add(w["doi"].replace("https://doi.org/", "").lower())

    # Collect existing files as sets for fast lookup
    pdf_stems = {p.stem for p in PDF_DIR.glob("*.pdf")} if PDF_DIR.exists() else set()
    docling_stems = {p.stem for p in DOCLING_DIR.glob("*.md")} if DOCLING_DIR.exists() else set()
    summary_stems = {p.stem for p in SUMMARY_DIR.glob("*.md")} if SUMMARY_DIR.exists() else set()

    # Read WoS CSV
    with open(WOS_CSV, newline="", encoding="latin-1") as f:
        rows = list(csv.DictReader(f))

    # Build output
    fieldnames = ["doi", "has_pdf", "docling_parsed", "summarized",
                  "pub_year", "article_title", "match_oa"]

    out = open(args.output, "w", newline="") if args.output else sys.stdout
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()

    counts = {"total": 0, "has_pdf": 0, "docling_parsed": 0,
              "summarized": 0, "match_oa": 0}

    for row in rows:
        doi = row.get("DOI", "").strip()
        if not doi:
            continue

        key = doi_to_key(doi)
        has_pdf = key in pdf_stems
        docling_parsed = key in docling_stems
        summarized = key in summary_stems
        match_oa = doi.lower() in oa_dois

        counts["total"] += 1
        counts["has_pdf"] += has_pdf
        counts["docling_parsed"] += docling_parsed
        counts["summarized"] += summarized
        counts["match_oa"] += match_oa

        done = has_pdf and docling_parsed and summarized
        if not done:
            writer.writerow({
                "doi": doi,
                "has_pdf": has_pdf,
                "docling_parsed": docling_parsed,
                "summarized": summarized,
                "pub_year": row.get("Pub Year", "").strip(),
                "article_title": row.get("Article Title", "").strip(),
                "match_oa": match_oa,
            })

    if args.output:
        out.close()

    # List missing PDFs as clickable DOI links
    if args.missing:
        missing = [r for r in rows if r.get("DOI", "").strip()
                   and doi_to_key(r["DOI"].strip()) not in pdf_stems]
        print(f"\n--- {len(missing)} DOIs without PDFs ---", file=sys.stderr)
        for r in missing:
            doi = r["DOI"].strip()
            title = r.get("Article Title", "").strip()
            year = r.get("Pub Year", "").strip()
            print(f"  https://doi.org/{doi}  ({year}) {title}", file=sys.stderr)

    # Print summary to stderr so it shows even when piping to file
    total = counts["total"]
    print(f"\n{'':>20} count    pct", file=sys.stderr)
    print(f"{'total':>20} {total:>5}", file=sys.stderr)
    for key in ["has_pdf", "docling_parsed", "summarized", "match_oa"]:
        n = counts[key]
        pct = n / total * 100 if total else 0
        print(f"{key:>20} {n:>5}  {pct:5.1f}%", file=sys.stderr)

    if args.output:
        print(f"\nWrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
