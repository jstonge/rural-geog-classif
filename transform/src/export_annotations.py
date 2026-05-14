"""Export Label Studio annotation distributions for the frontend.

Pulls every task + annotation from each schema's Label Studio project (same
client setup as align_annotations.py / upload_to_labelstudio.py) and, per
schema, computes:

  - per-control label totals
  - per-(control, annotator) label breakdowns
  - per-annotator throughput (n_annotations, n_tasks, controls covered)
  - distribution of annotations-per-task

Writes a single JSON to transform/output/annotations.json that the
/annotations page consumes via $lib/data/annotations.json.

Schemas are mapped to project IDs in PROJECTS — add more as new schemas
ship (e.g. {"v1": 110, "v3": 113, "v4": 120}).
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

PROJECTS: dict[str, int] = {
    "v1": 110,
    "v3": 113,
}
OUTPUT_PATH = Path(
    "/gpfs1/home/j/s/jstonge1/rural-geog-classif/transform/output/annotations.json"
)


def annotator_label(u) -> str:
    name = " ".join(
        s for s in [getattr(u, "first_name", None), getattr(u, "last_name", None)] if s
    ).strip()
    return name or getattr(u, "email", None) or f"user_{u.id}"


def summarize_project(client: LabelStudio, project_id: int, users_by_id: dict) -> dict:
    tasks = list(client.tasks.list(project=project_id))

    label_totals: dict[str, Counter] = defaultdict(Counter)
    by_annotator: dict[str, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    annotator_stats: dict[int, dict] = defaultdict(
        lambda: {"n_annotations": 0, "tasks": set(), "controls": set()}
    )
    annotations_per_task = Counter()
    n_annotated = 0

    for t in tasks:
        if not t.annotations:
            annotations_per_task[0] += 1
            continue
        n_annotated += 1
        annotations_per_task[len(t.annotations)] += 1

        for ann in t.annotations:
            uid = ann.get("completed_by")
            stats = annotator_stats[uid]
            stats["n_annotations"] += 1
            stats["tasks"].add(t.id)
            for r in ann.get("result", []):
                if r.get("type") != "choices":
                    continue
                control = r["from_name"]
                stats["controls"].add(control)
                for choice in r["value"]["choices"]:
                    label_totals[control][choice] += 1
                    by_annotator[control][uid][choice] += 1

    controls = sorted(label_totals.keys())

    annotators = []
    for uid, stats in annotator_stats.items():
        u = users_by_id.get(uid, {"id": uid, "email": None, "name": f"user_{uid}"})
        annotators.append({
            "id": uid,
            "name": u["name"],
            "email": u["email"],
            "n_annotations": stats["n_annotations"],
            "n_tasks": len(stats["tasks"]),
            "controls": sorted(stats["controls"]),
        })
    annotators.sort(key=lambda a: a["n_annotations"], reverse=True)

    return {
        "project_id": project_id,
        "n_tasks_total": len(tasks),
        "n_tasks_annotated": n_annotated,
        "controls": controls,
        "annotators": annotators,
        "label_distribution": {
            c: dict(sorted(label_totals[c].items(), key=lambda kv: -kv[1]))
            for c in controls
        },
        "by_annotator": {
            c: {
                str(uid): dict(sorted(by_annotator[c][uid].items(), key=lambda kv: -kv[1]))
                for uid in by_annotator[c]
            }
            for c in controls
        },
        "annotations_per_task": dict(sorted(annotations_per_task.items())),
    }


def main():
    load_dotenv()

    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    users_by_id = {
        u.id: {"id": u.id, "email": getattr(u, "email", None), "name": annotator_label(u)}
        for u in client.users.list()
    }
    print(f"Users: {len(users_by_id)}")

    schemas = []
    for name, project_id in PROJECTS.items():
        print(f"\nSchema {name!r} → project {project_id}")
        summary = summarize_project(client, project_id, users_by_id)
        schemas.append({"name": name, **summary})
        print(f"  {summary['n_tasks_annotated']}/{summary['n_tasks_total']} tasks annotated")
        print(f"  {len(summary['annotators'])} distinct annotators")
        print(f"  controls: {summary['controls']}")

    out = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schemas": schemas,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
