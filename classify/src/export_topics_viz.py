"""Export topics_viz.json for the / (homepage) frontend.

One row per paper with its model-predicted topic LIST (multi-label) plus
enough metadata to render a stacked-bar-by-decade + drill-down table.
Source: a topic classify snapshot (typically the --all-papers cat14 run).

Usage:
    python classify/src/export_topics_viz.py 2026-05-29_1719_topic_v3_abstract_cat14_all
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.snapshots import load_snapshot
from lib.wos import load_wos_dict_rows

OUT_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/topics_viz.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", help="Topic snapshot to take topics_pred from.")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    snap = load_snapshot(args.snapshot)
    preds = snap["predictions"]
    doi_to_topics = {}
    for _, r in preds.iterrows():
        doi = r["doi"]
        if not isinstance(doi, str):
            continue
        t = r.get("topics_pred")
        if isinstance(t, list) and t:
            doi_to_topics[doi] = list(t)

    # Load WoS for metadata, joined by DOI
    wos_rows = load_wos_dict_rows()

    out = []
    for r in wos_rows:
        doi = (r.get("DOI") or "").strip()
        if not doi or doi not in doi_to_topics:
            continue
        out.append({
            "doi":       doi,
            "title":     (r.get("Article Title") or "").strip(),
            "authors":   (r.get("Authors") or "").strip(),
            "pub_year":  (r.get("Pub Year") or "").strip(),
            "source":    (r.get("Source Title") or "").strip(),
            "keywords":  (r.get("Author Keywords") or "").strip(),
            "abstract":  (r.get("Abstract") or "").strip(),
            "topics":    doi_to_topics[doi],
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote {len(out)} rows -> {args.out}")

    # Topic-instance breakdown for sanity check
    from collections import Counter
    c = Counter()
    for p in out:
        for t in p["topics"]:
            c[t] += 1
    print(f"\nTopic-instance counts ({sum(c.values())} total across {len(out)} papers, "
          f"avg {sum(c.values()) / len(out):.2f}/paper):")
    for t, n in c.most_common():
        print(f"  {t:>25}: {n}")


if __name__ == "__main__":
    main()
