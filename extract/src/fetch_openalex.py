"""Fetch works from OpenAlex API using DOIs from WoS CSV."""

import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

INPUT_CSV = Path(__file__).parent.parent / "input" / "Coded Rural Geog All 1986-2025 WoS List 4-7-2026(savedrecs).csv"
OUTPUT_FILE = Path(__file__).parent.parent / "output" / "openalex_works.json"
BATCH_SIZE = 50  # keep URL length manageable
MAILTO = "jstonge1@uvm.edu"  # polite pool; replace with your email


def read_dois(path: Path) -> list[str]:
    dois = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = row.get("DOI", "").strip()
            if doi:
                dois.append(doi)
    return dois


def fetch_batch(dois: list[str]) -> list[dict]:
    """Fetch a batch of works by DOI from OpenAlex."""
    doi_filter = "|".join(f"https://doi.org/{d}" for d in dois)
    params = urllib.parse.urlencode({
        "filter": f"doi:{doi_filter}",
        "per_page": str(len(dois)),
        "mailto": MAILTO,
    })
    url = f"https://api.openalex.org/works?{params}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data.get("results", [])


def main():
    dois = read_dois(INPUT_CSV)
    print(f"Found {len(dois)} DOIs")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_works = []
    for i in range(0, len(dois), BATCH_SIZE):
        batch = dois[i : i + BATCH_SIZE]
        print(f"Fetching batch {i // BATCH_SIZE + 1} ({len(batch)} DOIs)...")
        results = fetch_batch(batch)
        all_works.extend(results)
        print(f"  Got {len(results)} works")
        time.sleep(0.5)  # be polite

    print(f"\nTotal works fetched: {len(all_works)} / {len(dois)} DOIs")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_works, f, indent=2)
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
