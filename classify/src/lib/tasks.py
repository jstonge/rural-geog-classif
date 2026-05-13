"""Task registry — per-control specs that drive run.py and validate.py.

Each control (methods / location / topic) is a TaskSpec describing:
  - response_key       — JSON key the prompt expects the model to return
  - supports_schema    — does this control have versioned prompts/categories (v1, v3, ...)?
  - supports_strategy  — does input_strategy apply (sections only meaningful for methods)?
  - max_tokens_by_strategy — defaults per strategy
  - default_thinking   — thinking-mode default for this control
  - gt_loader          — callable that returns DataFrame[doi, {gt_col}]
  - gt_col             — column name of the GT labels list
  - multi_label_scoring — True for multi-label (Jaccard); False for single-label (exact-match)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from lib.annotations import load_gt_ls, load_gt_parquet, load_methods_gt


@dataclass
class TaskSpec:
    name: str
    response_key: str
    supports_schema: bool
    supports_strategy: bool
    default_thinking: bool
    max_tokens_by_strategy: dict[str, int]
    gt_loader: Callable[[str | None], pd.DataFrame]
    gt_col: str
    multi_label_scoring: bool

    def default_max_tokens(self, strategy: str | None) -> int:
        if strategy and strategy in self.max_tokens_by_strategy:
            return self.max_tokens_by_strategy[strategy]
        # Fallback: first entry
        return next(iter(self.max_tokens_by_strategy.values()))


def _topic_gt(schema):
    # v1 -> annotations.parquet; v3 -> LS project 113 (topic control)
    if schema == "v3":
        return load_gt_ls(project_id=113, control="topic")
    return load_gt_parquet("topic")


def _location_gt(schema):
    # v1 -> annotations.parquet; v3 -> LS project 113 (Location control)
    if schema == "v3":
        return load_gt_ls(project_id=113, control="Location")
    return load_gt_parquet("Location")


TASKS: dict[str, TaskSpec] = {
    "methods": TaskSpec(
        name="methods",
        response_key="method",
        supports_schema=True,
        supports_strategy=True,
        default_thinking=True,
        max_tokens_by_strategy={"abstract": 2048, "fulltext": 2048, "sections": 4096},
        gt_loader=load_methods_gt,
        gt_col="methods_gt",
        multi_label_scoring=False,
    ),
    "location": TaskSpec(
        name="location",
        response_key="location",
        supports_schema=True,
        supports_strategy=False,
        default_thinking=False,
        max_tokens_by_strategy={"abstract": 64},
        gt_loader=_location_gt,
        gt_col="Location_gt",
        multi_label_scoring=True,
    ),
    "topic": TaskSpec(
        name="topic",
        response_key="topics",
        supports_schema=True,
        supports_strategy=False,
        default_thinking=True,
        max_tokens_by_strategy={"abstract": 4096},
        gt_loader=_topic_gt,
        gt_col="topic_gt",
        multi_label_scoring=True,
    ),
}


def get_task(name: str) -> TaskSpec:
    if name not in TASKS:
        raise ValueError(f"unknown task {name!r}; choices: {list(TASKS)}")
    return TASKS[name]
