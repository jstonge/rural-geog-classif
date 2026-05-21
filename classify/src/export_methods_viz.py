"""Export methods_viz.json for the / (homepage) frontend.

One row per paper with its model-predicted method category plus enough metadata
to render a stacked-bar-by-decade + drill-down table. Source: a methods
classify snapshot (typically an --all-papers sections_full run).

Usage:
    python classify/src/export_methods_viz.py 2026-05-20_1458_methods_v3_sections_full
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from lib.snapshots import load_snapshot
from lib.wos import WOS_CSV

OUT_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/methods_viz.json")


def _first(x):
    return x[0] if isinstance(x, list) and x else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", help="Methods snapshot to take method_pred from.")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    snap = load_snapshot(args.snapshot)
    preds = snap["predictions"]
    doi_to_method = {}
    for _, r in preds.iterrows():
        doi = r["doi"]
        if not isinstance(doi, str):
            continue
        m = _first(r.get("method_pred"))
        if m:
            doi_to_method[doi] = m

    # Load WoS for metadata, joined by DOI
    with open(WOS_CSV, encoding="latin-1") as f:
        wos_rows = list(csv.DictReader(f))

    out = []
    for r in wos_rows:
        doi = (r.get("DOI") or "").strip()
        if not doi or doi not in doi_to_method:
            continue
        out.append({
            "doi":       doi,
            "title":     (r.get("Article Title") or "").strip(),
            "authors":   (r.get("Authors") or "").strip(),
            "pub_year":  (r.get("Pub Year") or "").strip(),
            "source":    (r.get("Source Title") or "").strip(),
            "keywords":  (r.get("Author Keywords") or "").strip(),
            "abstract":  (r.get("Abstract") or "").strip(),
            "method":    doi_to_method[doi],
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote {len(out)} rows -> {args.out}")
    # Category breakdown for sanity check
    from collections import Counter
    by_m = Counter(p["method"] for p in out)
    for m, n in by_m.most_common():
        print(f"  {m:>25}: {n}")


if __name__ == "__main__":
    main()
