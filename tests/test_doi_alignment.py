"""Validate that DOIs are correctly aligned with their row metadata.

The old WoS export had DOIs shifted by one or more rows, so the DOI for
paper A was sitting on the row for paper B.  These tests catch that class
of bug by cross-checking the DOI column against:
  1. the DOI Link column (internal consistency),
  2. OpenAlex metadata (external consistency — title + author match).
"""

import csv
import json
import re
import unicodedata
from pathlib import Path

import pytest

EXTRACT_DIR = Path(__file__).parent.parent / "extract"

WOS_CSV = EXTRACT_DIR / "input" / "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
OPENALEX_JSON = EXTRACT_DIR / "output" / "openalex_works.json"

DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s]+$")


@pytest.fixture(scope="module")
def wos_rows():
    with open(WOS_CSV, newline="", encoding="latin-1") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def openalex_by_doi():
    with open(OPENALEX_JSON, encoding="utf-8") as f:
        works = json.load(f)
    return {w["doi"].replace("https://doi.org/", "").lower(): w for w in works if w.get("doi")}


# ── internal consistency ────────────────────────────────────────────


def test_doi_column_is_valid_format(wos_rows):
    """Every non-empty DOI should look like a real DOI (10.XXXX/...)."""
    bad = []
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip()
        if doi and not DOI_RE.match(doi):
            bad.append(f"row {i}: '{doi}'")
    if bad:
        pytest.fail(f"{len(bad)} rows with malformed DOI:\n" + "\n".join(bad[:20]))


def test_no_duplicate_dois(wos_rows):
    """Each DOI should appear at most once."""
    seen = {}
    dupes = []
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip()
        if not doi:
            continue
        if doi in seen:
            dupes.append(f"'{doi}' in rows {seen[doi]} and {i}")
        else:
            seen[doi] = i
    if dupes:
        pytest.fail(f"{len(dupes)} duplicate DOIs:\n" + "\n".join(dupes[:20]))


def test_doi_matches_doi_link(wos_rows):
    """The DOI Link column should embed the same DOI value.

    This catches row-shift bugs where the DOI drifted to a different row
    but DOI Link stayed in place (or vice versa).
    """
    mismatches = []
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip()
        doi_link = row.get("DOI Link", "").strip()
        if not doi or not doi_link:
            continue
        # DOI Link is typically http://dx.doi.org/10.xxx or https://doi.org/10.xxx
        extracted = (
            doi_link
            .replace("http://dx.doi.org/", "")
            .replace("https://doi.org/", "")
        )
        if extracted != doi:
            mismatches.append(
                f"row {i}: DOI='{doi}' but DOI Link contains '{extracted}'"
            )
    if mismatches:
        pytest.fail(
            f"{len(mismatches)} rows where DOI != DOI Link:\n"
            + "\n".join(mismatches[:20])
        )


# ── external consistency (cross-check with OpenAlex) ───────────────


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace, strip punctuation."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


def _first_surname(authors: str) -> str:
    return authors.split(";")[0].split(",")[0].strip().lower()


def test_doi_row_matches_openalex_title(wos_rows, openalex_by_doi):
    """For each WoS row whose DOI exists in OpenAlex, the titles should overlap.

    A row-shift bug would pair the wrong DOI with a title, so the OpenAlex
    title (looked up by DOI) would not match the WoS title on the same row.
    """
    mismatches = []
    matched = 0
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip().lower()
        if not doi or doi not in openalex_by_doi:
            continue
        matched += 1

        wos_title = _normalize(row["Article Title"])
        oa_title = _normalize(openalex_by_doi[doi].get("title", ""))

        # Check word overlap — aligned rows share most title words
        wos_words = set(wos_title.split())
        oa_words = set(oa_title.split())
        if not wos_words or not oa_words:
            continue
        overlap = len(wos_words & oa_words) / len(wos_words | oa_words)
        if overlap < 0.5:
            mismatches.append(
                f"row {i} (DOI={doi}): overlap={overlap:.2f}\n"
                f"  WoS:      {row['Article Title'][:80]}\n"
                f"  OpenAlex: {openalex_by_doi[doi].get('title', '')[:80]}"
            )

    assert matched > 0, "No DOIs matched between WoS CSV and OpenAlex — check files"
    if mismatches:
        pytest.fail(
            f"{len(mismatches)}/{matched} rows where WoS title doesn't match "
            f"OpenAlex title for the same DOI (possible row shift):\n"
            + "\n".join(mismatches[:20])
        )


def test_doi_row_matches_openalex_author(wos_rows, openalex_by_doi):
    """First-author surname in WoS should appear in the OpenAlex authorships."""
    mismatches = []
    matched = 0
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip().lower()
        if not doi or doi not in openalex_by_doi:
            continue
        matched += 1

        wos_surname = _normalize(_first_surname(row["Authors"]))
        oa_authors = openalex_by_doi[doi].get("authorships", [])
        oa_names = _normalize(" ".join(
            a.get("author", {}).get("display_name", "") for a in oa_authors
        ))

        # Check if any word of the surname appears in the OpenAlex names.
        # Handles compound surnames (e.g. "bustos gallardo" when OA has "beatriz bustos").
        surname_words = set(wos_surname.split())
        oa_words = set(oa_names.split())
        if wos_surname and not (surname_words & oa_words):
            mismatches.append(
                f"row {i} (DOI={doi}): WoS first author '{wos_surname}' "
                f"not found in OpenAlex authors '{oa_names[:80]}'"
            )

    assert matched > 0, "No DOIs matched between WoS CSV and OpenAlex — check files"
    if mismatches:
        pytest.fail(
            f"{len(mismatches)}/{matched} rows where WoS first author not in "
            f"OpenAlex authorships (possible row shift):\n"
            + "\n".join(mismatches[:20])
        )
