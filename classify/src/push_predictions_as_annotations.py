"""Push a gemma snapshot's predictions to LS project 113 as ANNOTATIONS
attributed to a specified user.

Mirrors the pattern from migrate_v1_to_v3.py (where v1 annotations were
re-pushed as v3 annotations under cheryl/user_id=54). This script lets you
add an additional "fake annotator" view — e.g. gemma's best run as if it
were a human — so you can compare against real annotators in the LS UI.

Run `python classify/src/ls_backup.py 113` first.

Usage:
    # Dry-run
    python classify/src/push_predictions_as_annotations.py \\
        --snapshot 2026-05-13_2152_methods_v3_abstract_cat03 --user-id 32

    # Push for real
    python classify/src/push_predictions_as_annotations.py \\
        --snapshot ... --user-id 32 --apply
"""
from __future__ import annotations

import argparse

from lib.labelstudio import make_client, push_annotations, remove_annotations_by_user
from lib.snapshots import load_snapshot
from lib.tasks import get_task

PROJECT_ID = 113


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None,
                    help="Snapshot to take predictions from. Required unless --remove-by-user.")
    ap.add_argument("--user-id", type=int, default=None,
                    help="LS user id to attribute the annotations to.")
    ap.add_argument("--project", type=int, default=PROJECT_ID)
    ap.add_argument("--apply", action="store_true",
                    help="Actually push (default: dry-run).")
    ap.add_argument("--backdate-to", default=None,
                    help="Optional ISO date (YYYY-MM-DD). PATCHes created_at on each pushed "
                         "annotation so it sorts older than the human annotators. "
                         "Use e.g. 2024-01-01 to push gemma's annotations behind cheryl's.")
    ap.add_argument("--remove-by-user", type=int, default=None,
                    help="Delete every annotation in --project that was completed_by this user id. "
                         "Use to back out a previous push. Ignores --snapshot.")
    args = ap.parse_args()

    client = make_client()

    if args.remove_by_user is not None:
        remove_annotations_by_user(client, args.project, args.remove_by_user,
                                    apply=args.apply)
        return

    if not args.snapshot or args.user_id is None:
        ap.error("--snapshot and --user-id are required (unless using --remove-by-user)")

    snap = load_snapshot(args.snapshot)
    cfg = snap["config"]
    task_name = cfg.get("task") or cfg.get("control")
    task = get_task(task_name)
    preds = snap["predictions"]
    pred_col = f"{task.response_key}_pred"
    print(f"Snapshot {snap['path'].name}: task={task.name}, pred_col={pred_col}, {len(preds)} rows")

    # Build DOI -> first non-empty pred label (wrapped in a 1-element list for the lib API)
    doi_to_labels: dict[str, list[str]] = {}
    for _, r in preds.iterrows():
        lst = r.get(pred_col)
        if isinstance(lst, list) and lst:
            doi_to_labels[r["doi"]] = [lst[0]]
    print(f"  parsed predictions: {len(doi_to_labels)}")

    backdate_iso = f"{args.backdate_to}T00:00:00Z" if args.backdate_to else None
    push_annotations(
        client, args.project, doi_to_labels, control=task.name,
        user_id=args.user_id, to_name="text", key_field="DOI",
        ground_truth=False, apply=args.apply, backdate_iso=backdate_iso,
    )


if __name__ == "__main__":
    main()
