"""Score predictions against ground truth.

Works for both single-label (methods, location) and multi-label (topics) controls.
For single-label: exact-match on the first element of each list.
For multi-label: Jaccard similarity on the set of labels.
"""
from __future__ import annotations

from collections import Counter

import pandas as pd


def _exact(pred: list[str] | None, gt: list[str] | None) -> bool:
    if not pred or not gt:
        return False
    return pred[0] == gt[0]


def _jaccard(pred: list[str] | None, gt: list[str] | None) -> float:
    if not pred or not gt:
        return 0.0
    a, b = set(pred), set(gt)
    return len(a & b) / len(a | b) if (a | b) else 0.0


def score(predictions: pd.DataFrame, gt: pd.DataFrame, *,
          pred_col: str, gt_col: str, multi_label: bool) -> dict:
    """Join predictions and gt on doi, compute metrics on the overlap.

    pred_col: e.g. "method_pred"
    gt_col:   e.g. "methods_gt"
    """
    joined = predictions.merge(gt, on="doi", how="inner").dropna(subset=[pred_col])
    n_total = len(joined)
    if n_total == 0:
        return {"n_total": 0, "exact_match": None, "mean_jaccard": None}

    exact = sum(_exact(p, g) for p, g in zip(joined[pred_col], joined[gt_col]))
    out = {"n_total": int(n_total), "n_correct": int(exact),
           "exact_match": round(exact / n_total, 4)}
    if multi_label:
        jaccs = [_jaccard(p, g) for p, g in zip(joined[pred_col], joined[gt_col])]
        out["mean_jaccard"] = round(sum(jaccs) / len(jaccs), 4)
    return out


def confusion_matrix(predictions: pd.DataFrame, gt: pd.DataFrame, *,
                      pred_col: str, gt_col: str) -> pd.DataFrame:
    """Single-label confusion matrix: rows = gt[0], cols = pred[0]."""
    joined = predictions.merge(gt, on="doi", how="inner").dropna(subset=[pred_col])
    rows = [(g[0], p[0]) for p, g in zip(joined[pred_col], joined[gt_col])
            if p and g]
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows, columns=["gt", "pred"])
            .groupby(["gt", "pred"]).size().unstack(fill_value=0))


def label_distribution(predictions: pd.DataFrame, pred_col: str) -> dict[str, int]:
    """Distribution of predicted labels (first element per row)."""
    labels = [p[0] for p in predictions[pred_col] if p]
    return dict(Counter(labels).most_common())


def print_report(name: str, metrics: dict, cm: pd.DataFrame | None = None,
                  dist: dict[str, int] | None = None) -> None:
    print(f"\n=== {name} ===")
    if metrics.get("exact_match") is None:
        print("  (no GT overlap)")
        return
    line = f"  exact-match: {metrics['n_correct']}/{metrics['n_total']} = {metrics['exact_match']:.1%}"
    if "mean_jaccard" in metrics:
        line += f"   mean-jaccard: {metrics['mean_jaccard']:.3f}"
    print(line)
    if dist:
        print("  label distribution:")
        for lbl, n in dist.items():
            print(f"    {lbl}: {n}")
    if cm is not None and not cm.empty:
        print("\n  confusion (rows=gt, cols=pred):")
        print(cm.to_string())
