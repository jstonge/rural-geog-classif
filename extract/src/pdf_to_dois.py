"""
Map PDF files named as [Author Year Title].pdf to DOI-based filenames.

PDFs in input/OneDrive_1_2026-05-01/ use the naming convention:
    LastName Year Partial Title.pdf
    e.g. "Adu-Poku 2026 Geographical Disparities in Energy Access...pdf"

We match these against the WoS metadata CSV to find the DOI, then
copy them to extract/output/pdfs/ as {doi_with_underscores}.pdf.
"""

import csv
import re
import shutil
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "input" / "OneDrive_1_2026-05-01"
CSV_PATH = ROOT / "input" / "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
OUT_DIR = ROOT / "output" / "pdfs"


def normalize(text: str) -> str:
    """Lowercase, strip accents, and keep only alphanumeric + spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def parse_pdf_name(fname: str) -> tuple[str, str | None, str]:
    """
    Extract (author_surname, year_or_none, title_fragment) from a PDF filename.
    Handles patterns like:
      "Adu-Poku 2026 Geographical Disparities..."
      "De La Vega-Leinert Young People.pdf"  (no year)
      "Ceccato Introduction to Focus Section..."  (no year)
    """
    stem = Path(fname).stem
    # Try to split on a 4-digit year
    m = re.match(r"^(.+?)\s+((?:19|20)\d{2})\s+(.+)$", stem)
    if m:
        return m.group(1).strip(), m.group(2), m.group(3).strip()
    # No year found — first token(s) before a capitalized word = author
    # Heuristic: split on first word that looks like a title word (>= 2 chars, not a name-like token)
    # Fallback: first token is author, rest is title
    parts = stem.split(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), None, parts[1].strip()
    return stem, None, ""


def load_csv_rows(path: Path) -> list[dict]:
    with open(path, "r", encoding="latin-1") as f:
        return list(csv.DictReader(f))


def first_author_surname(authors: str) -> str:
    """Extract first author's surname from WoS Authors field like 'Adu-Poku, A; Appiah, IG'."""
    first = authors.split(";")[0].strip()
    return first.split(",")[0].strip()


def title_overlap(a: str, b: str) -> float:
    """Jaccard-like overlap of normalized word sets."""
    wa = set(normalize(a).split())
    wb = set(normalize(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _find_candidates(author_norm: str, year: str | None, title_frag: str,
                      rows: list[dict], strict_year: bool = True) -> list[tuple]:
    candidates = []
    for row in rows:
        surname = first_author_surname(row["Authors"])
        surname_norm = normalize(surname)

        # Author must match (check if one contains the other to handle multi-word surnames)
        if author_norm not in surname_norm and surname_norm not in author_norm:
            continue

        # Year filtering
        if strict_year and year and row["Pub Year"] != year:
            continue

        score = title_overlap(title_frag, row["Article Title"])
        candidates.append((row["DOI"], row["Article Title"], score))
    return candidates


def match_pdf_to_doi(pdf_name: str, rows: list[dict]) -> tuple[str | None, str | None, float]:
    """
    Return (doi, csv_title, score) for the best match, or (None, None, 0) if no match.

    Handles edge cases:
    - Year mismatch (e.g. early-access articles): retry without year filter
    - Multi-word surnames without year (e.g. "De La Vega-Leinert Young People"):
      try progressively longer author prefixes from the filename
    """
    author, year, title_frag = parse_pdf_name(pdf_name)
    author_norm = normalize(author)

    # Pass 1: strict year match
    candidates = _find_candidates(author_norm, year, title_frag, rows, strict_year=True)

    # Pass 2: relax year if strict match found nothing or only low scores
    if year and (not candidates or max(c[2] for c in candidates) < 0.1):
        candidates += _find_candidates(author_norm, year, title_frag, rows, strict_year=False)

    # Pass 3: for no-year parses, the "author" might be just the first token of a
    # multi-word surname (e.g. "De" from "De La Vega-Leinert Young People").
    # Try progressively longer author prefixes against all CSV surnames.
    if not year and (not candidates or max(c[2] for c in candidates) < 0.1):
        stem = Path(pdf_name).stem
        words = stem.split()
        for i in range(2, min(len(words), 5)):
            longer_author = " ".join(words[:i])
            longer_title = " ".join(words[i:])
            longer_author_norm = normalize(longer_author)
            extra = _find_candidates(longer_author_norm, None, longer_title, rows, strict_year=False)
            candidates += extra

    if not candidates:
        return None, None, 0.0

    best = max(candidates, key=lambda x: x[2])
    return best


def doi_to_filename(doi: str) -> str:
    return doi.replace("/", "_") + ".pdf"


def main():
    rows = load_csv_rows(CSV_PATH)
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    matched = []
    unmatched = []

    for pdf in pdfs:
        doi, csv_title, score = match_pdf_to_doi(pdf.name, rows)
        if doi and score > 0.1:
            matched.append((pdf, doi, csv_title, score))
        else:
            unmatched.append((pdf.name, doi, csv_title, score))

    print(f"\n=== Matched: {len(matched)}/{len(pdfs)} ===\n")
    for pdf, doi, title, score in matched:
        out_name = doi_to_filename(doi)
        dest = OUT_DIR / out_name
        print(f"  {pdf.name[:70]}")
        print(f"    -> {out_name}  (score={score:.2f})")

    if unmatched:
        print(f"\n=== Unmatched: {len(unmatched)} ===\n")
        for name, doi, title, score in unmatched:
            print(f"  {name}")
            if doi:
                print(f"    best candidate: {doi} (score={score:.2f}, title={title[:60]})")

    # Ask before copying
    answer = input(f"\nCopy {len(matched)} matched PDFs to {OUT_DIR}? [y/N] ")
    if answer.strip().lower() == "y":
        for pdf, doi, _, _ in matched:
            dest = OUT_DIR / doi_to_filename(doi)
            if dest.exists():
                print(f"  SKIP (already exists): {dest.name}")
            else:
                shutil.copy2(pdf, dest)
                print(f"  Copied: {dest.name}")
        print("Done.")
    else:
        print("Aborted.")


if __name__ == "__main__":
    main()
