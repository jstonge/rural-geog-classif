"""Export compare.json for the /compare frontend — multi-schema labeller comparison.

Usage:
    python classify/src/export_compare.py <snap1> <snap2> [<snap3> ...]

Snapshots are auto-grouped by their `config.schema` field. Each group emits its
own (annotator GT + run predictions) bundle. The page renders one schema at a
time via a switcher.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from lib.snapshots import load_snapshot
from lib.wos import load_wos

COMPARE_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/compare.json")


def _pred_entry(row):
    """Pull (label, reasoning, picked, sections) from a single row."""
    pred_col = next((c for c in row.index if c.endswith("_pred")), None)
    reason_col = next((c for c in row.index if c.endswith("_reasoning")), None)
    pred = row.get(pred_col) if pred_col else None
    label = pred[0] if isinstance(pred, list) and pred else None
    entry = {
        "label": label,
        "reasoning": (row.get(reason_col) if reason_col else "") or "",
    }
    if isinstance(row.get("picked"), list):
        entry["picked"] = list(row["picked"])
    if isinstance(row.get("sections"), dict):
        entry["sections"] = dict(row["sections"])
    return entry


def _build_schema_bundle(snaps: list[dict], title_map: dict, abstract_map: dict) -> dict:
    """Build {records: [...]} for one schema's worth of snapshots."""
    # Annotator GT — pick the first snapshot with gt.parquet (all should share schema)
    gt_df = None
    for s in snaps:
        if s.get("gt") is not None:
            gt_df = s["gt"]
            break
    if gt_df is None:
        return {"records": []}
    gt_col = next((c for c in gt_df.columns if c.endswith("_gt")), None)
    gt_by_doi = {
        row["doi"]: (list(row[gt_col]) if row[gt_col] is not None else [])
        for _, row in gt_df.iterrows()
    }

    # Union of DOIs across these snapshots
    all_dois = sorted(set().union(*(set(s["predictions"]["doi"]) for s in snaps)))

    records = []
    for doi in all_dois:
        preds = {}
        for s in snaps:
            run_id = s["path"].name
            row = s["predictions"][s["predictions"]["doi"] == doi]
            if row.empty:
                continue
            preds[run_id] = _pred_entry(row.iloc[0])
        records.append({
            "doi":       doi,
            "title":     title_map.get(doi, ""),
            "abstract":  abstract_map.get(doi, ""),
            "annotator": gt_by_doi.get(doi, []),
            "preds":     preds,
        })
    return {"records": records}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshots", nargs="+", help="Snapshot names or paths (any schemas).")
    ap.add_argument("--out", type=Path, default=COMPARE_JSON)
    args = ap.parse_args()

    snaps = [load_snapshot(s) for s in args.snapshots]

    # Group by schema field in each snapshot's config
    by_schema: dict[str, list[dict]] = defaultdict(list)
    for s in snaps:
        schema = s["config"].get("schema") or "unknown"
        by_schema[schema].append(s)

    papers = load_wos()
    title_map = dict(zip(papers["doi"], papers["title"]))
    abstract_map = dict(zip(papers["doi"], papers["abstract"]))

    out_payload = {
        schema: _build_schema_bundle(group, title_map, abstract_map)
        for schema, group in by_schema.items()
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False))

    for schema, bundle in out_payload.items():
        run_ids = [s["path"].name for s in by_schema[schema]]
        print(f"  {schema}: {len(bundle['records'])} records, runs = {run_ids}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
