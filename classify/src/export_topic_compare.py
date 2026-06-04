"""Export topic_compare.json: per-label F1 delta between two topic snapshots,
both scored in the SAME label space (the new run's space) on the INTERSECTION
of DOIs.

When the new run uses the collapsed cat15+ taxonomy, the base run's predictions
and GT both get mapped through the granular->parent collapse map before scoring,
so cat14's "natural environment"/"weather"/"climate and natural hazards" predictions
are compared as "physical geography" against equally-collapsed GT.

Usage:
    python classify/src/export_topic_compare.py <base-snapshot> <new-snapshot>
    # default: cat14 vs cat16
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import score as score_mod
from lib.annotations import apply_collapse_map, load_topic_collapse_map
from lib.snapshots import load_snapshot

OUT_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/topic_compare.json")

DEFAULT_BASE = "2026-05-29_1447_topic_v3_abstract_cat14"
DEFAULT_NEW = "2026-06-04_0926_topic_v3_abstract_cat16"


def _score_with_collapse(snap: dict, dois: set[str], cmap: dict[str, str], collapse_preds: bool):
    """Score this snapshot's preds against its gt, restricted to `dois`,
    optionally collapsing preds (always collapses GT when cmap is non-empty)."""
    preds = snap["predictions"]
    gt_df = pd.read_parquet(snap["path"] / "gt.parquet")
    preds = preds[preds["doi"].isin(dois)].copy()
    gt_df = gt_df[gt_df["doi"].isin(dois)].copy()
    if cmap:
        gt_df["topic_gt"] = gt_df["topic_gt"].apply(lambda x: apply_collapse_map(x or [], cmap))
    if collapse_preds and cmap:
        preds["topics_pred"] = preds["topics_pred"].apply(lambda x: apply_collapse_map(x or [], cmap))
    return score_mod.score(preds, gt_df, pred_col="topics_pred", gt_col="topic_gt", multi_label=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default=DEFAULT_BASE)
    ap.add_argument("new", nargs="?", default=DEFAULT_NEW)
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    base = load_snapshot(args.base)
    new = load_snapshot(args.new)
    base_dois = set(base["predictions"]["doi"])
    new_dois = set(new["predictions"]["doi"])
    shared = base_dois & new_dois
    print(f"base: {args.base} ({len(base_dois)} preds)")
    print(f"new:  {args.new} ({len(new_dois)} preds)")
    print(f"shared DOIs: {len(shared)}")

    # Decide whether to collapse: any GT label appears in cmap (granular -> parent
    # that differs from itself) AND the new run's snapshot was configured with collapse_gt.
    cmap = load_topic_collapse_map()
    new_uses_collapse = bool(new["config"].get("collapse_gt"))
    # Collapse BASE preds because they're in the granular space; NEW preds are
    # already in the collapsed space if its config says so (no second collapse).
    collapse_base_preds = new_uses_collapse
    print(f"collapse base preds: {collapse_base_preds}  (new run collapse_gt={new_uses_collapse})")

    base_metrics = _score_with_collapse(base, shared, cmap if collapse_base_preds else {}, collapse_base_preds)
    new_metrics = _score_with_collapse(new, shared, cmap if new_uses_collapse else {}, False)

    bpl = base_metrics["per_label"]
    npl = new_metrics["per_label"]
    labels = sorted(set(bpl) | set(npl))
    rows = []
    for lbl in labels:
        b = bpl.get(lbl) or {"p": None, "r": None, "f1": None, "support_gt": 0, "support_pred": 0}
        n = npl.get(lbl) or {"p": None, "r": None, "f1": None, "support_gt": 0, "support_pred": 0}
        delta = None
        if b["f1"] is not None and n["f1"] is not None:
            delta = round(n["f1"] - b["f1"], 4)
        rows.append({
            "label":        lbl,
            "support_gt":   int(n["support_gt"] or b["support_gt"]),
            "base": {
                "p":  b["p"], "r": b["r"], "f1": b["f1"],
                "support_pred": int(b["support_pred"]),
            },
            "new": {
                "p":  n["p"], "r": n["r"], "f1": n["f1"],
                "support_pred": int(n["support_pred"]),
            },
            "delta_f1": delta,
        })

    payload = {
        "base_run":    args.base,
        "new_run":     args.new,
        "n_shared":    len(shared),
        "base_jaccard":     base_metrics.get("mean_jaccard"),
        "new_jaccard":      new_metrics.get("mean_jaccard"),
        "base_exact_match": base_metrics.get("exact_match"),
        "new_exact_match":  new_metrics.get("exact_match"),
        "collapsed_label_space": new_uses_collapse,
        "per_label":   rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {args.out}")
    print(f"\n{'label':30s}  {'base F1':>8s}  {'new F1':>8s}  {'Δ':>7s}  {'sup_gt':>7s}")
    print("-" * 70)
    for r in sorted(rows, key=lambda x: (x["delta_f1"] is None, x["delta_f1"] or 0)):
        bf = f"{r['base']['f1']:.2f}" if r['base']['f1'] is not None else "—"
        nf = f"{r['new']['f1']:.2f}" if r['new']['f1'] is not None else "—"
        df = f"{r['delta_f1']:+.2f}" if r['delta_f1'] is not None else "—"
        print(f"{r['label']:30s}  {bf:>8s}  {nf:>8s}  {df:>7s}  {r['support_gt']:>7d}")


if __name__ == "__main__":
    main()
