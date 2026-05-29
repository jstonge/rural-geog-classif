"""Backup Label Studio projects to local JSON files before any modification.

Usage:
    python classify/src/ls_backup.py 110 113

For each project id, writes to classify/output/ls_backups/{timestamp}/project_{id}/:
  - project.json   — id, title, description, label_config XML
  - tasks.json     — every task with its data, annotations, predictions

Restore (manual, if needed): use `client.projects.update(id, label_config=...)`
for the schema, and `client.tasks.update(id, data=...)` for per-task data fields.
Annotations are not auto-restored; recreate via `client.annotations.create(...)`.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from lib.labelstudio import backup_project, make_client

BACKUPS_ROOT = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/output/ls_backups")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_ids", nargs="+", type=int,
                    help="LS project ids to back up (e.g. 110 113).")
    args = ap.parse_args()

    client = make_client()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = BACKUPS_ROOT / stamp
    print(f"Backup root: {root}")
    for pid in args.project_ids:
        out_dir = root / f"project_{pid}"
        n = backup_project(client, pid, out_dir)
        print(f"  project {pid}: {n} tasks  →  {out_dir}")


if __name__ == "__main__":
    main()
