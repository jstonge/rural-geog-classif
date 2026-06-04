"""Build extract/input/wos_backfill.csv from external sources.

For each WoS row that's missing a DOI or an abstract, look it up:
  - DOI:      OpenAlex title+year search (high-confidence matches only)
  - Abstract: OpenAlex abstract_inverted_index by DOI

Writes a CSV that the pipeline consumes via load_wos.apply_backfill().
Rerun this script when the WoS extract changes.

Usage:
    uv run python extract/src/build_backfill.py
    uv run python extract/src/build_backfill.py --no-fetch   # rebuild from existing
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WOS_CSV = ROOT / "extract" / "input" / "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
OUT_CSV = ROOT / "extract" / "input" / "wos_backfill.csv"
MAILTO = "jstonge1@uvm.edu"
TITLE_SIM_THRESHOLD = 0.85
YEAR_TOLERANCE = 2  # OpenAlex year may differ from WoS by ±2 (online vs print)

# Manual DOI overrides for papers OpenAlex's fuzzy title search misses
# (typically punctuation/hyphenation differences between WoS and OpenAlex).
# Raw WoS title + pub_year; normalized at lookup time.
MANUAL_DOI: list[tuple[str, str, str]] = [
    ("LANDSCAPE, SYSTEM, AND IDENTITY IN THE POSTCONQUEST ANDES", "1992",
     "10.1111/j.1467-8306.1992.tb01970.x"),
]

# Hand-written abstracts for papers that have no abstract in any external
# source (OpenAlex / Crossref / Semantic Scholar) — usually older essay-style
# Geographical Review pieces. Derived from the opening sections of the
# parsed PDF and intended to give the topic classifier a usable input.
MANUAL_ABSTRACT: dict[str, str] = {
    "10.2307/3250830": (
        "Reports on doctoral fieldwork investigating NGO-sponsored programs "
        "to reduce conflicts around Muraviovka Nature Park in Amur Province, "
        "Russia — the first private nature reserve created in post-Soviet "
        "Russia, established in 1992 in a strategic, militarized border "
        "region near China. Reflects on the methodological challenges of "
        "conducting research in rural Russia where heavy alcohol consumption "
        "shapes the reliability of interviews about poaching and resistance "
        "to the park. Examines how environmental education programs, "
        "jointly run by local teachers and visiting Americans, have shifted "
        "local attitudes toward the park despite widespread suspicion of "
        "foreign motives and accusations of having 'sold out the motherland.'"
    ),
    "10.2307/3250862": (
        "Revisits John Fraser Hart and Ennis Chestang's 1978 claim of a "
        "'rural revolution' in eastern North Carolina, in which "
        "mechanization of flue-cured tobacco production released a large "
        "agricultural labor force that in turn attracted decentralized "
        "manufacturing into the Coastal Plain. Tracks whether the "
        "reconfiguration of the thirty-eight rural counties of the Coastal "
        "Plain into an industry-based economy continued through the 1980s "
        "and 1990s, and finds that the hard-earned manufacturing gains of "
        "the early 1990s have been eroded by post-Fordist globalization — "
        "particularly in textiles and apparel — as American blue-collar "
        "workers increasingly compete with cheaper overseas labor."
    ),
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def search_doi(title: str, year_wos: int | None) -> tuple[str | None, float, str | None]:
    url = ("https://api.openalex.org/works?search="
           + urllib.parse.quote(title)
           + f"&per-page=5&mailto={MAILTO}")
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"  search err: {e}", file=sys.stderr)
        return None, 0.0, None
    nt = norm(title)
    best: tuple[float, int | None, str | None, str] | None = None
    for h in data.get("results", []):
        cand = h.get("display_name") or h.get("title") or ""
        sim = difflib.SequenceMatcher(None, nt, norm(cand)).ratio()
        yr_oa = h.get("publication_year")
        year_ok = (year_wos is None or yr_oa is None
                   or abs(yr_oa - year_wos) <= YEAR_TOLERANCE)
        score = sim + (0.1 if year_ok else -0.3)
        doi = h.get("doi")
        if best is None or score > best[0]:
            best = (score, yr_oa, doi, cand)
    if best is None:
        return None, 0.0, None
    score, _, doi, cand = best
    return doi, score - 0.1 if doi else 0.0, cand  # report raw sim, not adjusted


def inv_to_text(inv: dict | None) -> str | None:
    if not inv:
        return None
    n = sum(len(v) for v in inv.values())
    out: list[str | None] = [None] * n
    for tok, positions in inv.items():
        for p in positions:
            if 0 <= p < n:
                out[p] = tok
    text = " ".join(t for t in out if t is not None).strip()
    return text or None


def fetch_abstract(doi: str) -> str | None:
    url = (f"https://api.openalex.org/works/doi:"
           + urllib.parse.quote(doi, safe="")
           + f"?mailto={MAILTO}")
    try:
        w = fetch_json(url)
    except Exception as e:
        print(f"  abstract err for {doi}: {e}", file=sys.stderr)
        return None
    return inv_to_text(w.get("abstract_inverted_index"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true",
                    help="Skip network calls; only rebuild file from on-disk state")
    args = ap.parse_args()

    with open(WOS_CSV, newline="", encoding="latin-1") as f:
        rows = list(csv.DictReader(f))

    no_doi = [r for r in rows if not (r.get("DOI") or "").strip()]
    with_doi_no_abs = [r for r in rows
                       if (r.get("DOI") or "").strip()
                       and not (r.get("Abstract") or "").strip()]
    print(f"WoS: {len(rows)} rows, {len(no_doi)} missing DOI, "
          f"{len(with_doi_no_abs)} have DOI but no abstract", file=sys.stderr)

    entries: list[dict] = []

    manual_lookup = {(norm(t), y): d for t, y, d in MANUAL_DOI}

    # 1) Find DOIs for no-DOI papers
    for r in no_doi:
        title = (r.get("Article Title") or "").strip()
        pub_year = (r.get("Pub Year") or "").strip()
        year_int = int(pub_year) if pub_year.isdigit() else None

        doi = None
        sim = 0.0
        matched_title = None
        source = "openalex_title_search"

        manual = manual_lookup.get((norm(title), pub_year))
        if manual:
            doi = manual
            sim = 1.0
            source = "manual_override"
        elif not args.no_fetch:
            doi, sim, matched_title = search_doi(title, year_int)
            time.sleep(0.15)

        if doi and sim >= TITLE_SIM_THRESHOLD:
            doi_clean = doi.replace("https://doi.org/", "")
            abstract = fetch_abstract(doi_clean) if not args.no_fetch else None
            if not args.no_fetch:
                time.sleep(0.15)
            entries.append({
                "match_doi": "",
                "match_title": title,
                "match_year": pub_year,
                "doi": doi_clean,
                "abstract": abstract or "",
                "source": source,
                "title_sim": f"{sim:.3f}",
            })
            print(f"  doi  [{sim:.2f}]  {doi_clean}  ({pub_year}) {title[:60]}",
                  file=sys.stderr)
        else:
            print(f"  doi  MISS    ({pub_year}) {title[:60]}", file=sys.stderr)

    # 2) Fill abstracts for DOI-but-no-abstract papers
    for r in with_doi_no_abs:
        doi = (r.get("DOI") or "").strip()
        title = (r.get("Article Title") or "").strip()
        pub_year = (r.get("Pub Year") or "").strip()
        abstract = fetch_abstract(doi) if not args.no_fetch else None
        source = "openalex_abstract"
        if not abstract and doi in MANUAL_ABSTRACT:
            abstract = MANUAL_ABSTRACT[doi]
            source = "manual_abstract"
        if not abstract:
            source = "missing"
        if not args.no_fetch:
            time.sleep(0.15)
        entries.append({
            "match_doi": doi,
            "match_title": "",
            "match_year": pub_year,
            "doi": "",
            "abstract": abstract or "",
            "source": source,
            "title_sim": "",
        })
        marker = {"openalex_abstract": "abs ",
                  "manual_abstract":   "abs*",
                  "missing":           "abs  MISS"}[source]
        print(f"  {marker}  {doi}  ({pub_year}) {title[:60]}", file=sys.stderr)

    fieldnames = ["match_doi", "match_title", "match_year",
                  "doi", "abstract", "source", "title_sim"]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        # Provenance comment row (so the file isn't anonymous)
        f.write(f"# generated by extract/src/build_backfill.py at "
                f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for e in entries:
            w.writerow(e)

    print(f"\nWrote {OUT_CSV}  ({len(entries)} rows)", file=sys.stderr)


if __name__ == "__main__":
    main()
