"""Backup Label Studio projects to local JSON files before any modification.

Usage:
    python classify/src/ls_backup.py 110 113

For each project id, writes to classify/output/ls_backups/{timestamp}/{project_id}/:
  - project.json   — id, title, description, label_config XML
  - tasks.json     — every task with its data, annotations, predictions

Restore (manual, if needed): use `client.projects.update(id, label_config=...)`
for the schema, and `client.tasks.update(id, data=...)` for per-task data fields.
Annotations are not auto-restored; recreate via `client.annotations.create(...)`.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

BACKUPS_ROOT = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/output/ls_backups")


def _to_jsonable(obj):
    """Best-effort conversion of LS SDK pydantic-ish objects to plain dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return obj.dict()
        except TypeError:
            pass
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def backup_project(client: LabelStudio, project_id: int, out_dir: Path) -> int:
    """Dump one project to {out_dir}/. Returns task count."""
    out_dir.mkdir(parents=True, exist_ok=True)

    project = client.projects.get(id=project_id)
    project_meta = {
        "id":           project.id,
        "title":        getattr(project, "title", None),
        "description":  getattr(project, "description", None),
        "label_config": project.label_config,
        "created_at":   str(getattr(project, "created_at", "")),
    }
    (out_dir / "project.json").write_text(json.dumps(project_meta, indent=2, ensure_ascii=False))

    tasks_out = []
    for t in client.tasks.list(project=project_id, fields="all"):
        tasks_out.append({
            "id":          t.id,
            "data":        t.data,
            "annotations": _to_jsonable(getattr(t, "annotations", []) or []),
            "predictions": _to_jsonable(getattr(t, "predictions", []) or []),
        })
    (out_dir / "tasks.json").write_text(json.dumps(tasks_out, indent=2, ensure_ascii=False, default=str))

    return len(tasks_out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_ids", nargs="+", type=int,
                    help="LS project ids to back up (e.g. 110 113).")
    args = ap.parse_args()

    load_dotenv()
    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = BACKUPS_ROOT / stamp
    print(f"Backup root: {root}")
    for pid in args.project_ids:
        out_dir = root / f"project_{pid}"
        n = backup_project(client, pid, out_dir)
        print(f"  project {pid}: {n} tasks  →  {out_dir}")


if __name__ == "__main__":
    main()
