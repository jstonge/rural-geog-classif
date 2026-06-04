"""Import unannotated papers into LS project 113 as new tasks, each with the
gemma methods classifier's output attached as a *prediction* (not annotation).

Predictions are the right LS primitive for model output: they don't show up in
`load_gt_ls`, they sort separately from human annotations, and you can convert
them to annotations one-by-one as you judge. Annotations would be confused with
human GT.

Strategy:
  1. Load a snapshot whose run was `--all-papers` (so predictions cover the
     full WoS corpus, not just the originally-annotated 88).
  2. Diff against existing LS tasks in --project; only create tasks for DOIs
     not yet imported.
  3. Build each new task's `data` from the WoS CSV row (same field shape as
     the originally-imported tasks), plus `text` (abstract) and
     `method_section_html` (collapsible picked-sections block).
  4. Push the model's first method_pred as a prediction, tagged with
     model_version=<snapshot run_id>.

Run `python classify/src/ls_backup.py 113` first.

Usage:
    # Dry-run
    python classify/src/import_predictions_to_ls.py \\
        --snapshot 2026-05-20_1458_methods_v3_sections_full

    # Push
    python classify/src/import_predictions_to_ls.py \\
        --snapshot 2026-05-20_1458_methods_v3_sections_full --apply
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio
from label_studio_sdk.core.api_error import ApiError

from lib.snapshots import load_snapshot
from lib.tasks import get_task
from lib.wos import load_wos_dict_rows
from push_sections_to_ls import build_sections_html

PROJECT_ID = 113

# WoS columns that are LS-data fields on the originally-imported tasks.
# Everything except "Abstract" (which becomes `text`).
WOS_DATA_COLS_EXCLUDE = {"Abstract"}


def _wos_row_to_data(row: pd.Series) -> dict:
    """Convert one WoS DataFrame row into an LS task `data` dict."""
    out = {}
    for col, val in row.items():
        if col in WOS_DATA_COLS_EXCLUDE:
            continue
        # Skip NaN / empty (LS stores nulls as None — leave keys absent instead).
        if val is None:
            continue
        if isinstance(val, float) and math.isnan(val):
            continue
        if isinstance(val, str) and not val.strip():
            continue
        out[col] = val
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True,
                    help="Snapshot to take predictions from (should be an --all-papers run).")
    ap.add_argument("--project", type=int, default=PROJECT_ID)
    ap.add_argument("--apply", action="store_true",
                    help="Actually create tasks + predictions (default: dry-run).")
    ap.add_argument("--model-version", default=None,
                    help="model_version label on each prediction (default: snapshot run_id).")
    args = ap.parse_args()

    load_dotenv(Path(".env"))
    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    snap = load_snapshot(args.snapshot)
    cfg = snap["config"]
    task_spec = get_task(cfg.get("control") or cfg.get("task"))
    preds = snap["predictions"]
    pred_col = f"{task_spec.response_key}_pred"
    model_version = args.model_version or snap["path"].name
    print(f"Snapshot {snap['path'].name}: task={task_spec.name}, pred_col={pred_col}, "
          f"{len(preds)} rows; model_version={model_version}")

    # Load WoS once (with DOI/abstract backfill applied), index by DOI
    wos_rows = load_wos_dict_rows()
    wos_by_doi = {(r.get("DOI") or "").strip(): r for r in wos_rows
                  if (r.get("DOI") or "").strip()}
    print(f"WoS: {len(wos_by_doi)} rows with DOI")

    # Existing LS tasks
    existing_tasks = list(client.tasks.list(project=args.project))
    existing_dois = {(t.data or {}).get("DOI") for t in existing_tasks
                     if (t.data or {}).get("DOI")}
    print(f"Project {args.project}: {len(existing_tasks)} tasks, "
          f"{len(existing_dois)} with DOIs")

    # Build set of new (doi, label, html) to create
    new_rows = []
    skipped_no_wos = 0
    skipped_no_pred = 0
    skipped_already = 0
    for _, r in preds.iterrows():
        doi = r["doi"]
        if doi in existing_dois:
            skipped_already += 1
            continue
        lst = r.get(pred_col)
        if not (isinstance(lst, list) and lst):
            skipped_no_pred += 1
            continue
        wos_row = wos_by_doi.get(doi)
        if wos_row is None:
            skipped_no_wos += 1
            continue
        new_rows.append((doi, lst[0], r, wos_row))

    print(f"  to create:       {len(new_rows)}")
    print(f"  skipped (already in LS): {skipped_already}")
    print(f"  skipped (no model pred): {skipped_no_pred}")
    print(f"  skipped (no WoS row):    {skipped_no_wos}")

    if not new_rows:
        print("Nothing to do.")
        return

    if not args.apply:
        doi, label, pred_row, wos_row = new_rows[0]
        sample_data = _wos_row_to_data(pd.Series(wos_row))
        sample_data["text"] = wos_row.get("Abstract") or ""
        sample_data["method_section_html"] = build_sections_html(pred_row) or ""
        sample_data["intro_section_html"] = ""
        print("\nSample task (dry-run):")
        print(f"  DOI: {doi}")
        print(f"  data keys: {sorted(sample_data.keys())}")
        print(f"  abstract preview: {sample_data['text'][:160]}...")
        print(f"  method_section_html present: {bool(sample_data['method_section_html'])}")
        print(f"  intro_section_html stubbed (run push_intro_to_ls.py later)")
        print(f"  prediction: {task_spec.name}={label}")
        print("\nDRY RUN — pass --apply to create.")
        return

    n_tasks = 0
    n_preds = 0
    for doi, label, pred_row, wos_row in new_rows:
        data = _wos_row_to_data(pd.Series(wos_row))
        data["text"] = wos_row.get("Abstract") or ""
        data["method_section_html"] = build_sections_html(pred_row) or ""
        data["intro_section_html"] = ""
        try:
            new_task = client.tasks.create(data=data, project=args.project)
        except ApiError as e:
            print(f"!! task create failed for doi {doi}: {e.status_code} {e.body}")
            break
        n_tasks += 1
        try:
            client.predictions.create(
                task=new_task.id,
                model_version=model_version,
                result=[{
                    "from_name": task_spec.name,
                    "to_name": "text",
                    "type": "choices",
                    "value": {"choices": [label]},
                }],
            )
            n_preds += 1
        except ApiError as e:
            print(f"!! prediction create failed for task {new_task.id} (doi {doi}): "
                  f"{e.status_code} {e.body}")
            break

    print(f"\nCreated {n_tasks} tasks and {n_preds} predictions in project {args.project} "
          f"(model_version={model_version})")


if __name__ == "__main__":
    main()
