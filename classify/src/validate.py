"""Generic validate: load a snapshot, score against the task's GT, attach metrics.

The task is read from the snapshot's config.json (`control` field), so you don't
pass --task — it's resolved automatically. Use --schema only to override the
schema recorded in the snapshot (rarely needed).

Usage:
    python classify/src/validate.py <run-name-or-path>
"""
from __future__ import annotations

import argparse

import rebuild_runs_index
import score as score_mod
from lib.annotations import apply_collapse_map, load_topic_collapse_map
from lib.snapshots import load_snapshot, save_validation
from lib.tasks import get_task


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

    # Annotators tag in the granular cat14 topic taxonomy. When the run was
    # configured with `collapse_gt: true`, map granular GT labels to their
    # parent bucket (per the `parent` column on topic_14.csv) before scoring
    # so predictions on the collapsed label set compare against a collapsed GT.
    if task.name == "topic" and cfg.get("collapse_gt"):
        cmap = load_topic_collapse_map()
        if cmap:
            gt[task.gt_col] = gt[task.gt_col].apply(lambda labs: apply_collapse_map(labs or [], cmap))
            n_collapsed = sum(1 for labs in gt[task.gt_col] if labs)
            print(f"Collapsed topic GT via parent map ({n_collapsed} rows non-empty after dedup)")

    pred_col = f"{task.response_key}_pred"
    metrics = score_mod.score(snap["predictions"], gt,
                              pred_col=pred_col, gt_col=task.gt_col,
                              multi_label=task.multi_label_scoring)
    dist = score_mod.label_distribution(snap["predictions"], pred_col,
                                         multi_label=task.multi_label_scoring)

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
    rebuild_runs_index.main()


if __name__ == "__main__":
    main()
