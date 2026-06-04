"""Fetch works from OpenAlex API using DOIs from WoS CSV.

Incremental by default: only DOIs missing from the existing output file are
fetched. Use --rebuild to force a full re-fetch.
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from load_wos import WOS_CSV, load_wos_rows

OUTPUT_FILE = Path(__file__).parent.parent / "output" / "openalex_works.json"
BATCH_SIZE = 50  # keep URL length manageable
MAILTO = "jstonge1@uvm.edu"  # polite pool


def read_dois() -> list[str]:
    """Read DOIs from the canonical WoS extract with backfill applied."""
    rows = load_wos_rows()
    return [d for r in rows
            if (d := (r.get("DOI") or "").strip())]


def load_existing(path: Path) -> dict[str, dict]:
    """Return {normalized_doi: work_record} from a prior run, keyed for dedup."""
    if not path.exists():
        return {}
    works = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for w in works:
        doi = (w.get("doi") or "").lower().replace("https://doi.org/", "").strip()
        if doi:
            out[doi] = w
    return out


def fetch_batch(dois: list[str]) -> list[dict]:
    """Fetch a batch of works by DOI from OpenAlex."""
    doi_filter = "|".join(f"https://doi.org/{d}" for d in dois)
    params = urllib.parse.urlencode({
        "filter": f"doi:{doi_filter}",
        "per_page": str(len(dois)),
        "mailto": MAILTO,
    })
    url = f"https://api.openalex.org/works?{params}"
    with urllib.request.urlopen(urllib.request.Request(url)) as resp:
        data = json.loads(resp.read().decode())
    return data.get("results", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="Ignore existing output and re-fetch every DOI from OpenAlex.")
    args = ap.parse_args()

    dois = read_dois()
    print(f"Found {len(dois)} DOIs in {WOS_CSV.name} (with backfill applied)")

    existing = {} if args.rebuild else load_existing(OUTPUT_FILE)
    if existing:
        print(f"Loaded {len(existing)} works from previous run")

    missing = [d for d in dois if d.lower() not in existing]
    if not missing:
        print("Nothing to fetch — output is up to date.")
        return

    print(f"Fetching {len(missing)} missing DOIs in batches of {BATCH_SIZE}...")
    fetched: list[dict] = []
    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        print(f"  batch {i // BATCH_SIZE + 1}: {len(batch)} DOIs", end=" ... ")
        results = fetch_batch(batch)
        fetched.extend(results)
        print(f"got {len(results)}")
        time.sleep(0.5)  # polite pool

    # Merge: existing + newly fetched. Newly fetched wins on collision.
    for w in fetched:
        doi = (w.get("doi") or "").lower().replace("https://doi.org/", "").strip()
        if doi:
            existing[doi] = w

    all_works = list(existing.values())
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(all_works, indent=2), encoding="utf-8")
    print(f"\nWrote {len(all_works)} works to {OUTPUT_FILE} "
          f"(+{len(fetched)} fetched, {len(existing) - len(fetched)} reused)")


if __name__ == "__main__":
    main()
