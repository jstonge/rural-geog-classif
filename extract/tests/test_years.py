"""Compare publication years across WoS (Pub Year, Publication Year) and OpenAlex."""

import csv
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent

WOS_CSV = DATA_DIR / "input" / "Coded Rural Geog All 1986-2025 WoS List 4-7-2026(savedrecs).csv"
OPENALEX_JSON = DATA_DIR / "output" / "openalex_works.json"


@pytest.fixture(scope="module")
def wos_rows():
    with open(WOS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def openalex_by_doi():
    with open(OPENALEX_JSON, encoding="utf-8") as f:
        works = json.load(f)
    return {w["doi"].replace("https://doi.org/", "").lower(): w for w in works}


def test_wos_pub_year_vs_publication_year(wos_rows):
    """Check whether Pub Year and Publication Year agree in the WoS data."""
    mismatches = []
    for i, row in enumerate(wos_rows, start=2):  # line 2 = first data row
        pub_year = row.get("Pub Year", "").strip()
        publication_year = row.get("Publication Year", "").strip()
        if pub_year and publication_year and pub_year != publication_year:
            doi = row.get("DOI", "").strip()
            mismatches.append(
                f"row {i}: Pub Year={pub_year}, Publication Year={publication_year} (DOI={doi})"
            )
    if mismatches:
        detail = "\n".join(mismatches)
        pytest.fail(f"{len(mismatches)} WoS rows where Pub Year != Publication Year:\n{detail}")


def test_openalex_year_vs_wos_pub_year(wos_rows, openalex_by_doi):
    """Check whether OpenAlex publication_year matches WoS Pub Year."""
    mismatches = []
    matched = 0
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip().lower()
        pub_year = row.get("Pub Year", "").strip()
        if not doi or doi not in openalex_by_doi:
            continue
        matched += 1
        oa_year = str(openalex_by_doi[doi].get("publication_year", ""))
        if pub_year and oa_year and pub_year != oa_year:
            mismatches.append(
                f"row {i}: WoS Pub Year={pub_year}, OpenAlex={oa_year} (DOI={doi})"
            )
    print(f"\nMatched {matched} DOIs between WoS and OpenAlex")
    if mismatches:
        detail = "\n".join(mismatches)
        pytest.fail(
            f"{len(mismatches)}/{matched} works where OpenAlex year != WoS Pub Year:\n{detail}"
        )


def test_openalex_year_vs_wos_publication_year(wos_rows, openalex_by_doi):
    """Check whether OpenAlex publication_year matches WoS Publication Year."""
    mismatches = []
    matched = 0
    for i, row in enumerate(wos_rows, start=2):
        doi = row.get("DOI", "").strip().lower()
        publication_year = row.get("Publication Year", "").strip()
        if not doi or doi not in openalex_by_doi:
            continue
        matched += 1
        oa_year = str(openalex_by_doi[doi].get("publication_year", ""))
        if publication_year and oa_year and publication_year != oa_year:
            mismatches.append(
                f"row {i}: WoS Publication Year={publication_year}, OpenAlex={oa_year} (DOI={doi})"
            )
    print(f"\nMatched {matched} DOIs between WoS and OpenAlex")
    if mismatches:
        detail = "\n".join(mismatches)
        pytest.fail(
            f"{len(mismatches)}/{matched} works where OpenAlex year != WoS Publication Year:\n{detail}"
        )
