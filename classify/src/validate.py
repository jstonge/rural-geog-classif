"""Generic validate: load a snapshot, score against the task's GT, attach metrics.

The task is read from the snapshot's config.json (`control` field), so you don't
pass --task — it's resolved automatically. Use --schema only to override the
schema recorded in the snapshot (rarely needed).

Usage:
    python classify/src/validate.py <run-name-or-path>
"""
from __future__ import annotations

import argparse

from lib.snapshots import load_snapshot, save_validation
from lib.tasks import get_task
import score as score_mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="Snapshot name (e.g. 2026-05-12_methods_v1_abstract) or path.")
    ap.add_argument("--schema", default=None,
                    help="Override schema from the snapshot's config (rarely needed).")
    args = ap.parse_args()

    snap = load_snapshot(args.run)
    cfg = snap["config"]
    control = cfg.get("control") or cfg.get("task")
    task = get_task(control)
    schema = args.schema or cfg.get("schema")
    print(f"Validating {snap['path']} (task={task.name}, schema={schema}, strategy={cfg.get('strategy')})")

    gt = task.gt_loader(schema)
    print(f"GT: {len(gt)} annotations")

    pred_col = f"{task.response_key}_pred"
    metrics = score_mod.score(snap["predictions"], gt,
                              pred_col=pred_col, gt_col=task.gt_col,
                              multi_label=task.multi_label_scoring)
    dist = score_mod.label_distribution(snap["predictions"], pred_col)

    cm = None
    if not task.multi_label_scoring:
        cm = score_mod.confusion_matrix(snap["predictions"], gt,
                                         pred_col=pred_col, gt_col=task.gt_col)

    title = f"{task.name}" + (f" {schema}" if schema else "") + (f" / {cfg.get('strategy')}" if cfg.get("strategy") else "")
    score_mod.print_report(title, metrics, cm, dist)

    full_metrics = {
        **metrics,
        "label_distribution": dist,
        "confusion_matrix": cm.to_dict() if cm is not None and not cm.empty else {},
    }
    save_validation(snap["path"], metrics=full_metrics, gt=gt)
    print(f"Wrote metrics + gt -> {snap['path']}")


if __name__ == "__main__":
    main()
