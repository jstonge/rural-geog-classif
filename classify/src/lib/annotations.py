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

import csv
from pathlib import Path

import pandas as pd

from lib.labelstudio import load_gt, make_client

ANNOTATIONS_PARQUET = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/transform/output/annotations.parquet")

# Annotators tag in the granular cat14 taxonomy. When scoring against a
# collapsed cat (cat15+), we map granular GT labels to their parent before
# comparison. Single source of truth: the `parent` column on topic_14.csv.
TOPIC_GRANULAR_CSV = Path(
    "/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/schemas/prompts/v3/categories/topic_14.csv"
)


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


def load_topic_collapse_map(csv_path: Path = TOPIC_GRANULAR_CSV) -> dict[str, str]:
    """Build {granular_label -> this_row's_Value} from a cat-variant CSV.

    Two encodings supported (older CSVs use the first, newer use the second):

      1. `parent` column on the GRANULAR CSV (topic_14.csv). Each granular row
         names its cat15+ parent (or empty = identity). The cat15+ CSV does not
         need its own collapse declaration because every cat15+ run uses the
         same 12-bucket taxonomy.

      2. `legacy_values` column on the COLLAPSED CSV (topic_19+.csv). Each
         cat19+ row names the comma-separated granular labels it absorbs.
         This lets each cat variant declare its own collapse independently,
         which is what we want when iterating on a partial collapse (e.g. cat19
         = "only fold recreation into HE, leave other granular labels alone").

    The two encodings express the same fact and can't coexist on one CSV.
    Returns an empty dict if neither column is present.
    """
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if "legacy_values" in fields:
            cmap: dict[str, str] = {}
            for row in reader:
                v = row["Value"]
                cmap.setdefault(v, v)
                legacy = (row.get("legacy_values") or "").strip()
                if not legacy:
                    continue
                for lbl in (s.strip() for s in legacy.split(",")):
                    if lbl:
                        cmap[lbl] = v
            return cmap
        if "parent" in fields:
            return {row["Value"]: (row["parent"] or row["Value"]) for row in reader}
        return {}


def apply_collapse_map(labels: list[str], mapping: dict[str, str]) -> list[str]:
    """Map each granular label to its parent (or itself), dedup, preserve order."""
    if not mapping:
        return list(labels)
    out: list[str] = []
    seen: set[str] = set()
    for lbl in labels:
        m = mapping.get(lbl, lbl)
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


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
