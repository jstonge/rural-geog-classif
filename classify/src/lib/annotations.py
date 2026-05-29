"""Annotation (ground-truth) loaders — rural-geog-specific glue.

Two sources:
  - parquet  (v1 annotations exported from LS project 110 via
              transform/src/align_annotations.py)
  - LS API   (v3 live fetch from LS project 113)

The LS-API path delegates to lib.labelstudio.load_gt; this file just
adds the rural-geog conventions (DOI as task key, lowercase "doi" column,
parquet path, v1-vs-v3 schema dispatch).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from lib.labelstudio import load_gt, make_client

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


def load_gt_ls(project_id: int, control: str, *, ls_client=None) -> pd.DataFrame:
    """Fetch ground truth for a given control from a live LS project.

    Rural-geog convention: task key field is "DOI", output column lowercase "doi".
    Most-recently-updated annotation wins (handled in lib.labelstudio.load_gt).
    """
    client = ls_client or make_client()
    df = load_gt(client, project_id, control, key_field="DOI")
    return df.rename(columns={"DOI": "doi"})


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
