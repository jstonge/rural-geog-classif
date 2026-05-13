"""Rebuild frontend/src/lib/data/runs.json from every snapshot under
classify/output/runs/. One row per snapshot — the /runs page renders this.

Run after a new `validate.py` invocation, or any time you want the /runs
audit table to reflect the latest snapshots.
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.snapshots import list_snapshots

OUT = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/runs.json")


def main():
    records = []
    for d in list_snapshots():
        cfg = json.loads((d / "config.json").read_text())
        prompt = (d / "prompt.md").read_text() if (d / "prompt.md").exists() else ""
        metrics = (json.loads((d / "metrics.json").read_text())
                   if (d / "metrics.json").exists() else None)
        records.append({
            "run_id":  d.name,
            "prompt":  prompt,
            "metrics": metrics,
            **cfg,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, indent=2, ensure_ascii=False, default=str))
    print(f"Wrote {len(records)} runs to {OUT}")


if __name__ == "__main__":
    main()
