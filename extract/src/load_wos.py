"""Read the WoS CSV with backfilled DOIs/abstracts applied.

The canonical WoS extract (Full Dataset Rur Geog WoS 1986-2025 ...csv) is
treated as immutable. Corrections — DOIs we found by title search,
abstracts we pulled from OpenAlex — live in extract/input/wos_backfill.csv
and are merged in here at read time.

Usage:
    from extract.src.load_wos import load_wos_rows
    rows = load_wos_rows()  # list[dict] same shape as csv.DictReader on the WoS file
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WOS_CSV = ROOT / "extract" / "input" / "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
BACKFILL_CSV = ROOT / "extract" / "input" / "wos_backfill.csv"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def _read_backfill(path: Path) -> tuple[dict[tuple[str, str], dict], dict[str, dict]]:
    """Return (by_title_year, by_doi) lookup maps."""
    by_title: dict[tuple[str, str], dict] = {}
    by_doi: dict[str, dict] = {}
    if not path.exists():
        return by_title, by_doi
    with open(path, encoding="utf-8") as f:
        # Skip leading provenance comment lines (lines starting with '#')
        lines = [ln for ln in f if not ln.startswith("#")]
    reader = csv.DictReader(lines)
    for r in reader:
        mt = (r.get("match_title") or "").strip()
        my = (r.get("match_year") or "").strip()
        md = (r.get("match_doi") or "").strip()
        if mt:
            by_title[(_norm(mt), my)] = r
        if md:
            by_doi[md] = r
    return by_title, by_doi


def load_wos_rows(
    wos_csv: Path = WOS_CSV,
    backfill_csv: Path = BACKFILL_CSV,
    apply_backfill: bool = True,
) -> list[dict]:
    """Read WoS rows and merge in DOIs/abstracts from the backfill file."""
    with open(wos_csv, newline="", encoding="latin-1") as f:
        rows = list(csv.DictReader(f))

    if not apply_backfill:
        return rows

    by_title, by_doi = _read_backfill(backfill_csv)

    for r in rows:
        title = (r.get("Article Title") or "").strip()
        year = (r.get("Pub Year") or "").strip()
        doi = (r.get("DOI") or "").strip()

        if not doi:
            bf = by_title.get((_norm(title), year))
            if bf and bf.get("doi"):
                r["DOI"] = bf["doi"]
                doi = bf["doi"]

        if doi and not (r.get("Abstract") or "").strip():
            bf = by_doi.get(doi)
            if bf and bf.get("abstract"):
                r["Abstract"] = bf["abstract"]

    return rows


if __name__ == "__main__":
    rows = load_wos_rows()
    n_doi = sum(1 for r in rows if (r.get("DOI") or "").strip())
    n_abs = sum(1 for r in rows if (r.get("Abstract") or "").strip())
    print(f"WoS rows: {len(rows)}")
    print(f"  with DOI:      {n_doi}")
    print(f"  with abstract: {n_abs}")
