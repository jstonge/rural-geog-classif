"""Score predictions against ground truth.

Works for both single-label (methods, location) and multi-label (topics) controls.
For single-label: exact-match on the first element of each list.
For multi-label:
  - strict exact_match = set(pred) == set(gt)
  - mean_jaccard      = |A ∩ B| / |A ∪ B|  averaged per-sample
  - mean_precision / mean_recall / mean_f1 = sample-averaged (each sample is
    one paper, so 16 labels per paper get one P/R/F1 then averaged across papers)
  - per_label[label] = {p, r, f1, support_gt, support_pred} for diagnostics
"""
from __future__ import annotations

from collections import Counter

import pandas as pd


def _exact_single(pred: list[str] | None, gt: list[str] | None) -> bool:
    if not pred or not gt:
        return False
    return pred[0] == gt[0]


def _jaccard(pred: list[str] | None, gt: list[str] | None) -> float:
    a, b = set(pred or []), set(gt or [])
    if not (a | b):
        return 0.0
    return len(a & b) / len(a | b)


def _prf(pred: list[str] | None, gt: list[str] | None) -> tuple[float, float, float]:
    sp, sg = set(pred or []), set(gt or [])
    if not sp and not sg:
        return 1.0, 1.0, 1.0
    tp = len(sp & sg)
    p = tp / len(sp) if sp else 0.0
    r = tp / len(sg) if sg else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def _per_label_stats(pred_lists, gt_lists) -> dict[str, dict[str, float]]:
    """Per-label precision/recall/F1 across the sample (label = positive class)."""
    labels: set[str] = set()
    for p in pred_lists:
        labels.update(p or [])
    for g in gt_lists:
        labels.update(g or [])
    out: dict[str, dict] = {}
    for lbl in sorted(labels):
        tp = fp = fn = 0
        for p, g in zip(pred_lists, gt_lists):
            sp, sg = set(p or []), set(g or [])
            if lbl in sp and lbl in sg:
                tp += 1
            elif lbl in sp:
                fp += 1
            elif lbl in sg:
                fn += 1
        sup_pred = tp + fp
        sup_gt = tp + fn
        prec = tp / sup_pred if sup_pred else 0.0
        rec = tp / sup_gt if sup_gt else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        out[lbl] = {
            "p": round(prec, 4),
            "r": round(rec, 4),
            "f1": round(f1, 4),
            "support_gt": sup_gt,
            "support_pred": sup_pred,
        }
    return out


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

    pred_lists = list(joined[pred_col])
    gt_lists = list(joined[gt_col])

    if multi_label:
        exact = sum(set(p or []) == set(g or []) for p, g in zip(pred_lists, gt_lists))
        jaccs = [_jaccard(p, g) for p, g in zip(pred_lists, gt_lists)]
        prfs = [_prf(p, g) for p, g in zip(pred_lists, gt_lists)]
        n = len(prfs)
        return {
            "n_total": int(n_total),
            "n_correct": int(exact),
            "exact_match":    round(exact / n_total, 4),
            "mean_jaccard":   round(sum(jaccs) / n, 4),
            "mean_precision": round(sum(p for p, _, _ in prfs) / n, 4),
            "mean_recall":    round(sum(r for _, r, _ in prfs) / n, 4),
            "mean_f1":        round(sum(f for _, _, f in prfs) / n, 4),
            "per_label":      _per_label_stats(pred_lists, gt_lists),
        }

    # Single-label: existing behavior
    exact = sum(_exact_single(p, g) for p, g in zip(pred_lists, gt_lists))
    return {"n_total": int(n_total), "n_correct": int(exact),
            "exact_match": round(exact / n_total, 4)}


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


def label_distribution(predictions: pd.DataFrame, pred_col: str,
                       *, multi_label: bool = False) -> dict[str, int]:
    """Distribution of predicted labels. For multi-label tasks, counts every
    label across all rows. For single-label, only the first element per row.
    """
    if multi_label:
        labels = [lbl for p in predictions[pred_col] if p for lbl in p]
    else:
        labels = [p[0] for p in predictions[pred_col] if p]
    return dict(Counter(labels).most_common())


def print_report(name: str, metrics: dict, cm: pd.DataFrame | None = None,
                  dist: dict[str, int] | None = None) -> None:
    print(f"\n=== {name} ===")
    if metrics.get("exact_match") is None:
        print("  (no GT overlap)")
        return
    line = f"  exact-match: {metrics['n_correct']}/{metrics['n_total']} = {metrics['exact_match']:.1%}"
    if "mean_jaccard" in metrics and metrics["mean_jaccard"] is not None:
        line += f"   mean-jaccard: {metrics['mean_jaccard']:.3f}"
    print(line)
    if "mean_f1" in metrics:
        print(f"  sample-avg P/R/F1: "
              f"{metrics['mean_precision']:.3f} / "
              f"{metrics['mean_recall']:.3f} / "
              f"{metrics['mean_f1']:.3f}")
    if dist:
        print("  label distribution (pred):")
        for lbl, n in dist.items():
            print(f"    {lbl}: {n}")
    pl = metrics.get("per_label")
    if pl:
        print("\n  per-label (sup_gt / sup_pred  →  P / R / F1):")
        for lbl, s in sorted(pl.items(), key=lambda kv: -kv[1]["support_gt"]):
            print(f"    {lbl:>28}  {s['support_gt']:>3} / {s['support_pred']:>3}"
                  f"   {s['p']:.2f} / {s['r']:.2f} / {s['f1']:.2f}")
    if cm is not None and not cm.empty:
        print("\n  confusion (rows=gt, cols=pred):")
        print(cm.to_string())
