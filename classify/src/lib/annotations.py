"""Annotation (ground-truth) loaders.

Two sources:
  - parquet  (annotations exported from LS, e.g. project 110 via align_annotations.py)
  - LS API   (live fetch from a Label Studio project, e.g. project 113)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pandas as pd
from dotenv import load_dotenv

if TYPE_CHECKING:
    from label_studio_sdk import LabelStudio

ANNOTATIONS_PARQUET = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/transform/output/annotations.parquet")


def load_gt_parquet(control: str, *, parquet_path: Path = ANNOTATIONS_PARQUET) -> pd.DataFrame:
    """Load ground truth for a given control from the annotations parquet.

    control: "methods" / "Location" / "topic" (matches the LS control name & column suffix).
    Returns DataFrame with [doi, {control}_gt] where the gt column is list[str].
    """
    col = f"label_{control}"
    df = pd.read_parquet(parquet_path)
    df = df.dropna(subset=["doi"]).drop_duplicates(subset=["doi"], keep="last")
    if col not in df.columns:
        raise KeyError(f"column {col!r} not in {parquet_path}; available: {list(df.columns)}")
    df = df[df[col].apply(lambda x: isinstance(x, list) and len(x) > 0)].copy()
    return df[["doi", col]].rename(columns={col: f"{control}_gt"}).reset_index(drop=True)


def load_gt_ls(project_id: int, control: str, *,
                ls_client: "LabelStudio | None" = None) -> pd.DataFrame:
    """Fetch ground truth for a given control from a live LS project.

    control: "methods" / "Location" / "topic" — matches the LS `<Choices name="...">`.
    Picks the first annotation per task; if a task has multiple annotators, takes the first.
    Returns DataFrame with [doi, {control}_gt].
    """
    if ls_client is None:
        load_dotenv()
        from label_studio_sdk import LabelStudio
        ls_client = LabelStudio(
            base_url=os.getenv("LABEL_STUDIO_URL"),
            api_key=os.getenv("LABEL_STUDIO_API_KEY"),
            httpx_client=httpx.Client(verify=False),
        )

    records = []
    for t in ls_client.tasks.list(project=project_id, fields="all"):
        doi = (t.data or {}).get("DOI")
        if not doi:
            continue
        for ann in (t.annotations or []):
            found = False
            for r in ann.get("result", []):
                if r.get("from_name") == control and r.get("type") == "choices":
                    choices = r.get("value", {}).get("choices", [])
                    if choices:
                        records.append({"doi": doi, f"{control}_gt": list(choices)})
                        found = True
                        break
            if found:
                break

    return pd.DataFrame(records) if records else pd.DataFrame(columns=["doi", f"{control}_gt"])


def load_methods_gt(schema: str) -> pd.DataFrame:
    """Convenience: load methods GT for the given schema.
      v1 -> annotations.parquet (project 110 export), single-label only
      v3 -> LS project 113 (live)
    Returns DataFrame with [doi, methods_gt].
    """
    if schema == "v1":
        gt = load_gt_parquet("methods")
        return gt[gt["methods_gt"].apply(lambda x: len(x) == 1)].copy()
    if schema == "v3":
        return load_gt_ls(project_id=113, control="methods")
    raise ValueError(f"unknown methods schema: {schema!r}")
