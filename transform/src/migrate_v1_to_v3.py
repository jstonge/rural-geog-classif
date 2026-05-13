"""Pre-annotate project 113 (v3 schema) from project 110 (v1 schema).

Migrated:
- methods: v1 -> v3 via classify/schemas/mappings/v1_to_v3.json.
  Ambiguous entries (descriptive*) are dropped — annotator picks
  descriptive-empirical vs theoretical-conceptual on the new project.
- Location: "Australia" -> "Australia/New Zealand/Pacific". Other values pass through.

NOT migrated:
- topic: annotators redo this on the new project (v3 added scale/place/culture
  and lowercased several labels).

One annotation per target task (de-duped on DOI from the parquet, last wins).
Requires project 113 to already have tasks imported with a "DOI" data field.
"""
import json
import os
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio
from label_studio_sdk.core.api_error import ApiError

DRY_RUN = False

TARGET_PROJECT = 113
ANNOTATIONS_PARQUET = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/transform/output/annotations.parquet")
MAPPING_PATH = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/schemas/mappings/v1_to_v3.json")

# Attribute every migrated annotation to this user so the annotator opens
# their own pre-populated annotation rather than someone else's work.
COMPLETED_BY = 54  # cheryl.morse@uvm.edu

LOCATION_RENAMES = {"Australia": "Australia/New Zealand/Pacific"}
# v3 schema in project 113 uses "theoretical-conceptual" rather than the
# "theoretical/essay" placeholder we had in the offline v3.xml. Translate.
METHODS_V3_RENAMES = {"theoretical/essay": "theoretical-conceptual"}


def main():
    load_dotenv()

    df = pd.read_parquet(ANNOTATIONS_PARQUET)
    df = df.dropna(subset=["doi"]).drop_duplicates(subset=["doi"], keep="last")
    print(f"v1 annotations: {len(df)} unique DOIs")

    methods_map = json.loads(MAPPING_PATH.read_text())
    print(f"methods v1->v3: {methods_map}")

    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    tasks = list(client.tasks.list(project=TARGET_PROJECT))
    doi_to_task = {t.data.get("DOI"): t.id for t in tasks if t.data.get("DOI")}
    print(f"target project {TARGET_PROJECT}: {len(tasks)} tasks  ({len(doi_to_task)} with DOIs)")

    if not tasks:
        print(f"ERROR: project {TARGET_PROJECT} has no tasks. Import the WoS CSV first.")
        return

    annotations = []
    stats = {
        "with_methods": 0,
        "methods_dropped_ambiguous": 0,
        "no_v1_methods": 0,
        "australia_renamed": 0,
        "no_target_task": 0,
    }

    for _, row in df.iterrows():
        doi = row["doi"]
        task_id = doi_to_task.get(doi)
        if task_id is None:
            stats["no_target_task"] += 1
            continue

        result = []

        v1_methods = list(row.get("label_methods") or [])
        if not v1_methods:
            stats["no_v1_methods"] += 1
        else:
            v1_label = v1_methods[0]
            v3_label = methods_map.get(v1_label)
            if v3_label is None:
                stats["methods_dropped_ambiguous"] += 1
            else:
                v3_label = METHODS_V3_RENAMES.get(v3_label, v3_label)
                result.append({
                    "from_name": "methods", "to_name": "text", "type": "choices",
                    "value": {"choices": [v3_label]},
                })
                stats["with_methods"] += 1

        v1_locs = list(row.get("label_Location") or [])
        if v1_locs:
            mapped = [LOCATION_RENAMES.get(l, l) for l in v1_locs]
            if mapped != v1_locs:
                stats["australia_renamed"] += 1
            result.append({
                "from_name": "Location", "to_name": "text", "type": "choices",
                "value": {"choices": mapped},
            })

        # topic is intentionally NOT migrated — annotators will redo it on the
        # new project (v3 added scale/place/culture and lowercased several labels).

        if result:
            annotations.append({"task_id": task_id, "result": result})

    print()
    print(f"Annotations to push:           {len(annotations)}")
    print(f"  with methods auto-mapped:    {stats['with_methods']}")
    print(f"  methods left blank (review): {stats['methods_dropped_ambiguous']}")
    print(f"  no v1 methods at all:        {stats['no_v1_methods']}")
    print(f"  Australia renamed (NZ/Pac):  {stats['australia_renamed']}")
    print(f"  DOIs not in target project:  {stats['no_target_task']}")

    if DRY_RUN:
        print("\nDRY RUN — set DRY_RUN=False to actually push.")
        return

    pushed = 0
    for ann in annotations:
        try:
            client.annotations.create(
                id=ann["task_id"],
                result=ann["result"],
                completed_by=COMPLETED_BY,
            )
            pushed += 1
        except ApiError as e:
            print(f"!! push failed for task {ann['task_id']}: status={e.status_code} body={e.body}")
            break
    print(f"\nPushed {pushed} annotations to project {TARGET_PROJECT} (completed_by={COMPLETED_BY})")


if __name__ == "__main__":
    main()
