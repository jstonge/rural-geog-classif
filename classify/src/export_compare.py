"""Export compare.json for the /compare frontend — multi-(task,schema) comparison.

Usage:
    python classify/src/export_compare.py <snap1> <snap2> [<snap3> ...]

Snapshots are auto-grouped by their (task, schema) — the page renders one
(task, schema) bundle at a time via two switchers (task + schema).

Output shape:
    {
      "methods": {"v1": {records: [...]}, "v3": {records: [...]}, ...},
      "location": {"v1": {records: [...]}, ...},
      ...
    }

Each bundle carries its own annotator GT + run predictions + LS deep links.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import httpx
from dotenv import load_dotenv

from lib.snapshots import load_snapshot
from lib.tasks import get_task
from lib.wos import load_wos

COMPARE_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/compare.json")
DOCLING_DIR = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/parse/output/docling")
DOCLING_GH_URL = (
    "https://github.com/jstonge/rural-geog-classif/blob/main/parse/output/docling/{key}.md"
)

# Per-schema LS project routing. Add new schemas here as they're created.
SCHEMA_LS_PROJECTS = {"v1": 110, "v3": 113}
LS_TAB = 172  # data manager view id (same as old /review export)

# Tasks whose /compare bundle should render as single-label (confusion matrix)
# even though task.multi_label_scoring is True in the registry. Annotators
# almost always pick one location, so the per-label table is overkill.
COMPARE_FORCE_SINGLE_LABEL = {"location"}


def _pred_entry(row):
    """Pull (labels, reasoning, picked, sections) from a single row.

    `labels` is the full prediction list — for single-label controls this is
    a 1-element list; for multi-label (location, topic) it can be 0+ elements.
    The frontend renders chips and decides what to do per task.
    """
    pred_col = next((c for c in row.index if c.endswith("_pred")), None)
    reason_col = next((c for c in row.index if c.endswith("_reasoning")), None)
    pred = row.get(pred_col) if pred_col else None
    labels = list(pred) if isinstance(pred, list) else []
    entry = {
        "labels": labels,
        "reasoning": (row.get(reason_col) if reason_col else "") or "",
    }
    if isinstance(row.get("picked"), list):
        entry["picked"] = list(row["picked"])
    if isinstance(row.get("sections"), dict):
        entry["sections"] = dict(row["sections"])
    return entry


def _ls_doi_to_task(project_id: int) -> dict[str, int]:
    """Fetch DOI -> task_id from a Label Studio project (one network call per schema)."""
    load_dotenv()
    base_url = (os.getenv("LABEL_STUDIO_URL") or "").rstrip("/")
    if not base_url:
        return {}
    try:
        from label_studio_sdk import LabelStudio
        client = LabelStudio(
            base_url=base_url,
            api_key=os.getenv("LABEL_STUDIO_API_KEY"),
            httpx_client=httpx.Client(verify=False),
        )
        return {t.data.get("DOI"): t.id for t in client.tasks.list(project=project_id) if t.data.get("DOI")}
    except Exception as e:
        print(f"  (skipping LS lookup for project {project_id}: {e})")
        return {}


def _build_schema_bundle(schema: str, snaps: list[dict],
                         title_map: dict, abstract_map: dict) -> dict:
    """Build {multi_label, records: [...]} for one schema's worth of snapshots."""
    # Multi-label flag for the task (drives chip rendering / set-equality
    # agreement / per-label agreement table on /compare). All snapshots in this
    # group share a task, so the first one's task is authoritative.
    # Tasks in COMPARE_FORCE_SINGLE_LABEL get the single-label confusion matrix
    # view even when the registry marks them multi-label.
    multi_label = False
    for s in snaps:
        task_name = s["config"].get("task") or s["config"].get("control")
        if task_name:
            if task_name in COMPARE_FORCE_SINGLE_LABEL:
                multi_label = False
                break
            try:
                multi_label = get_task(task_name).multi_label_scoring
                break
            except ValueError:
                continue

    # Annotator GT — pick the first snapshot with gt.parquet (all should share schema)
    gt_df = None
    for s in snaps:
        if s.get("gt") is not None:
            gt_df = s["gt"]
            break
    if gt_df is None:
        return {"multi_label": multi_label, "records": []}
    gt_col = next((c for c in gt_df.columns if c.endswith("_gt")), None)
    gt_by_doi = {
        row["doi"]: (list(row[gt_col]) if row[gt_col] is not None else [])
        for _, row in gt_df.iterrows()
    }

    # LS deep links — fetch once per schema
    ls_project = SCHEMA_LS_PROJECTS.get(schema)
    doi_to_task = _ls_doi_to_task(ls_project) if ls_project else {}
    base_url = (os.getenv("LABEL_STUDIO_URL") or "").rstrip("/")

    # Union of DOIs across these snapshots (skip null DOIs — WoS rows without DOIs
    # leak through load_wos and end up as None in --all-papers snapshots).
    all_dois = sorted(set().union(*(
        {d for d in s["predictions"]["doi"] if isinstance(d, str)} for s in snaps
    )))

    records = []
    for doi in all_dois:
        preds = {}
        for s in snaps:
            run_id = s["path"].name
            row = s["predictions"][s["predictions"]["doi"] == doi]
            if row.empty:
                continue
            preds[run_id] = _pred_entry(row.iloc[0])

        task_id = doi_to_task.get(doi)
        ls_url = (f"{base_url}/projects/{ls_project}/data?task={task_id}&tab={LS_TAB}"
                  if (base_url and ls_project and task_id is not None) else None)

        docling_key = doi.replace("/", "_")
        docling_url = (DOCLING_GH_URL.format(key=docling_key)
                       if (DOCLING_DIR / f"{docling_key}.md").exists() else None)

        records.append({
            "doi":         doi,
            "title":       title_map.get(doi, ""),
            "abstract":    abstract_map.get(doi, ""),
            "annotator":   gt_by_doi.get(doi, []),
            "preds":       preds,
            "ls_task_id":  task_id,
            "ls_url":      ls_url,
            "docling_url": docling_url,
        })
    return {"multi_label": multi_label, "records": records}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshots", nargs="+", help="Snapshot names or paths (any schemas).")
    ap.add_argument("--out", type=Path, default=COMPARE_JSON)
    args = ap.parse_args()

    snaps = [load_snapshot(s) for s in args.snapshots]

    # Group by (task, schema)
    by_ts: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in snaps:
        cfg = s["config"]
        task = cfg.get("task") or cfg.get("control") or "unknown"
        schema = cfg.get("schema") or "unknown"
        by_ts[(task, schema)].append(s)

    papers = load_wos()
    title_map = dict(zip(papers["doi"], papers["title"]))
    abstract_map = dict(zip(papers["doi"], papers["abstract"]))

    # Two-level dict: {task: {schema: bundle}}
    out_payload: dict[str, dict[str, dict]] = defaultdict(dict)
    for (task, schema), group in by_ts.items():
        out_payload[task][schema] = _build_schema_bundle(schema, group, title_map, abstract_map)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False))

    for task in sorted(out_payload):
        for schema in sorted(out_payload[task]):
            bundle = out_payload[task][schema]
            run_ids = [s["path"].name for s in by_ts[(task, schema)]]
            print(f"  {task} / {schema}: {len(bundle['records'])} records, runs = {run_ids}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
