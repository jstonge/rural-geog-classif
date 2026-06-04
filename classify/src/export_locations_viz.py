"""Export locations_viz.json for the / (homepage) frontend.

Mirrors export_methods_viz.py but for the location classifier. Location is
multi-label — one paper can be tagged with multiple regions — so the output
has one row per (doi, region) pair. The Svelte side derives per-bucket
proportions as `papers-in-bucket-tagged-with-region / papers-in-bucket`.

Usage:
    python classify/src/export_locations_viz.py <location-snapshot-id>
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from lib.snapshots import load_snapshot
from lib.wos import load_wos_dict_rows

OUT_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/locations_viz.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", help="Location snapshot to take location_pred from.")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    snap = load_snapshot(args.snapshot)
    preds = snap["predictions"]
    doi_to_regions: dict[str, list[str]] = {}
    for _, r in preds.iterrows():
        doi = r["doi"]
        if not isinstance(doi, str):
            continue
        regions = r.get("location_pred")
        if isinstance(regions, list) and regions:
            doi_to_regions[doi] = [str(x) for x in regions if x]

    wos_rows = load_wos_dict_rows()

    out = []
    for r in wos_rows:
        doi = (r.get("DOI") or "").strip()
        if not doi or doi not in doi_to_regions:
            continue
        for region in doi_to_regions[doi]:
            out.append({
                "doi":       doi,
                "title":     (r.get("Article Title") or "").strip(),
                "authors":   (r.get("Authors") or "").strip(),
                "pub_year":  (r.get("Pub Year") or "").strip(),
                "source":    (r.get("Source Title") or "").strip(),
                "abstract":  (r.get("Abstract") or "").strip(),
                "region":    region,
            })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    n_papers = len({r["doi"] for r in out})
    print(f"Wrote {len(out)} (paper, region) rows covering {n_papers} papers -> {args.out}")
    by_region = Counter(r["region"] for r in out)
    for region, n in by_region.most_common():
        print(f"  {region:>32}: {n}")


if __name__ == "__main__":
    main()
