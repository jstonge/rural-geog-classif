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
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio
from label_studio_sdk.core.api_error import ApiError

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

    load_dotenv(Path(".env"))
    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    # --- REMOVE branch: delete annotations completed_by a given user ---
    if args.remove_by_user is not None:
        tasks = list(client.tasks.list(project=args.project, fields="all"))
        to_delete = []
        for t in tasks:
            for ann in (t.annotations or []):
                if ann.get("completed_by") == args.remove_by_user:
                    to_delete.append(ann["id"])
        print(f"Annotations to delete (completed_by={args.remove_by_user}, project {args.project}): {len(to_delete)}")
        if not args.apply:
            print("DRY RUN — pass --apply to delete.")
            return
        for aid in to_delete:
            client.annotations.delete(id=aid)
        print(f"Deleted {len(to_delete)} annotations.")
        return

    # --- PUSH branch ---
    if not args.snapshot or args.user_id is None:
        ap.error("--snapshot and --user-id are required (unless using --remove-by-user)")

    snap = load_snapshot(args.snapshot)
    cfg = snap["config"]
    task_name = cfg.get("task") or cfg.get("control")
    task = get_task(task_name)
    preds = snap["predictions"]
    pred_col = f"{task.response_key}_pred"
    print(f"Snapshot {snap['path'].name}: task={task.name}, pred_col={pred_col}, {len(preds)} rows")

    # Build DOI -> first non-empty pred label
    doi_to_label = {}
    for _, r in preds.iterrows():
        lst = r.get(pred_col)
        if isinstance(lst, list) and lst:
            doi_to_label[r["doi"]] = lst[0]
    print(f"  parsed predictions: {len(doi_to_label)}")

    # Map LS task ids by DOI
    tasks = list(client.tasks.list(project=args.project))
    doi_to_task = {t.data.get("DOI"): t.id for t in tasks if t.data.get("DOI")}
    print(f"Project {args.project}: {len(tasks)} tasks, {len(doi_to_task)} with DOIs")

    matched = [(doi, doi_to_task[doi], lbl) for doi, lbl in doi_to_label.items()
               if doi in doi_to_task]
    print(f"Matched DOIs: {len(matched)}")

    if not args.apply:
        if matched:
            doi, tid, lbl = matched[0]
            print(f"\nSample push (dry-run):")
            print(f"  task_id={tid}  doi={doi}  label={lbl}")
            print(f"  result=[{{'from_name': {task.name!r}, 'to_name': 'text', "
                  f"'type': 'choices', 'value': {{'choices': [{lbl!r}]}}}}]")
            print(f"  completed_by={args.user_id}")
        print("\nDRY RUN — pass --apply to push.")
        return

    pushed_ids: list[int] = []
    for doi, tid, lbl in matched:
        try:
            ann = client.annotations.create(
                id=tid,
                result=[{
                    "from_name": task.name,
                    "to_name": "text",
                    "type": "choices",
                    "value": {"choices": [lbl]},
                }],
                completed_by=args.user_id,
                ground_truth=False,   # signal "not the authoritative annotation"
            )
            pushed_ids.append(ann.id)
        except ApiError as e:
            print(f"!! push failed for task {tid} (doi {doi}): status={e.status_code} body={e.body}")
            break
    print(f"\nPushed {len(pushed_ids)} annotations to project {args.project} "
          f"(completed_by={args.user_id}, ground_truth=False)")

    # Optional: backdate created_at on every pushed annotation via raw API PATCH.
    if args.backdate_to and pushed_ids:
        backdate_iso = f"{args.backdate_to}T00:00:00Z"
        base = (os.getenv("LABEL_STUDIO_URL") or "").rstrip("/")
        key = os.getenv("LABEL_STUDIO_API_KEY")
        headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
        n_ok = 0
        with httpx.Client(verify=False) as h:
            for aid in pushed_ids:
                r = h.patch(f"{base}/api/annotations/{aid}/",
                            headers=headers,
                            json={"created_at": backdate_iso})
                if r.status_code in (200, 204):
                    n_ok += 1
                else:
                    print(f"!! backdate failed for annotation {aid}: {r.status_code} {r.text[:200]}")
                    break
        print(f"Backdated {n_ok}/{len(pushed_ids)} annotations to {backdate_iso}")


if __name__ == "__main__":
    main()
