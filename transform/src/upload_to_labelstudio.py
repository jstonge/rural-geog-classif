"""Re-upload the WoS CSV to a fresh Label Studio project with correctly
aligned metadata, and attach prior annotations (from align_annotations.py)
as predictions on the subset we already have."""
import json
import os
import time
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio
from label_studio_sdk.core.api_error import ApiError

CSV_PATH = "/gpfs1/home/j/s/jstonge1/rural-geog-classif/extract/input/Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
ANNOTATIONS_PARQUET = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/transform/output/annotations.parquet")
SOURCE_PROJECT_ID = 100
NEW_PROJECT_TITLE = "Rural Geog Annotation v2 (clean metadata)"
TO_NAME = "text"  # the <Text name="text" value="$text"/> control in the View


def main():
    load_dotenv()

    df = pd.read_csv(CSV_PATH, encoding="latin").rename(columns={"Abstract": "text"})
    before = len(df)
    df = df[df["text"].notna() & df["text"].astype(str).str.strip().astype(bool)]
    print(f"WoS: {len(df)} rows  (dropped {before - len(df)} with empty text)")

    matched = pd.read_parquet(ANNOTATIONS_PARQUET)
    label_cols = [c for c in matched.columns if c.startswith("label_")]
    matched = matched.dropna(subset=["doi"]).drop_duplicates(subset=["doi"], keep="last")
    ann_by_doi = matched.set_index("doi")[label_cols].to_dict(orient="index")
    print(f"Prior annotations: {len(matched)} tasks  ({label_cols})")

    records = json.loads(df.to_json(orient="records"))

    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    src = client.projects.get(id=SOURCE_PROJECT_ID)
    new = client.projects.create(
        title=NEW_PROJECT_TITLE,
        label_config=src.label_config,
    )
    print(f"Created project {new.id}: {NEW_PROJECT_TITLE!r}")

    # --- Phase 1: bulk-import tasks (flat records, no "data" wrapper) ---
    try:
        response = client.projects.import_tasks(
            id=new.id,
            request=records,
            commit_to_project=True,
        )
        print(f"Import response: {response}")
    except ApiError as e:
        print(f"!!! ApiError status={e.status_code}\n!!! body={e.body}")
        raise

    expected = len(records)
    for _ in range(20):
        n = len(list(client.tasks.list(project=new.id)))
        if n >= expected:
            break
        print(f"  waiting for tasks to commit... {n}/{expected}")
        time.sleep(2)
    tasks = list(client.tasks.list(project=new.id))
    print(f"Tasks visible in project: {len(tasks)}")

    # --- Phase 2: bulk-import predictions, one per task (choices unioned across annotators) ---
    doi_to_task = {t.data.get("DOI"): t.id for t in tasks if t.data.get("DOI")}
    preds = []
    for doi, labels in ann_by_doi.items():
        task_id = doi_to_task.get(doi)
        if task_id is None:
            continue
        result = []
        for col, choices in labels.items():
            if choices is None or len(choices) == 0:
                continue
            result.append({
                "from_name": col.removeprefix("label_"),
                "to_name": TO_NAME,
                "type": "choices",
                "value": {"choices": list(choices)},
            })
        if result:
            preds.append({
                "task": task_id,
                "result": result,
                "model_version": "recovered-from-project-100",
            })

    if preds:
        pred_response = client.projects.import_predictions(id=new.id, request=preds)
        print(f"Predictions response: {pred_response}")
        print(f"Attached {len(preds)} predictions")
    else:
        print("No predictions to import")


if __name__ == "__main__":
    main()
