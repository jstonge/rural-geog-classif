"""Input strategies for the classifier — different ways to build the user message.

Three strategies:
  abstract  — title + abstract (default; what locations / topics use)
  fulltext  — title + first N chars of docling-parsed text
  sections  — title + abstract + methodology sections picked by gemma (Phase A+B)

Each strategy has two parts:
  prepare(papers)       — add columns the strategy needs (fulltext / sections / picked)
  build_message(row)    — return the user message string for one paper
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from lib.llm import classify_batch

DOCLING_DIR    = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/parse/output/docling")
PICKER_PROMPT  = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/schemas/prompts/shared/picker.md").read_text()

FULLTEXT_MAX_CHARS = 12000
SECTION_MAX_CHARS  = 4000

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


# ---------- helpers ----------

def _load_docling(doi: str) -> str | None:
    if not isinstance(doi, str):
        return None
    p = DOCLING_DIR / (doi.replace("/", "_") + ".md")
    return p.read_text() if p.exists() else None


def _parse_sections(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    matches = list(_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(2).strip()] = text[body_start:body_end].strip()
    return out


def _build_picker_prompt(title: str, abstract: str, headers: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": PICKER_PROMPT},
        {"role": "user", "content": (
            f"Title: {title}\nAbstract: {abstract}\n\n"
            "Available section headers:\n" + "\n".join(f"- {h}" for h in headers)
        )},
    ]


def _parse_picked(text: str) -> list[str]:
    m = re.search(r"\{.*\}", (text or "").strip(), re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group()).get("sections", [])
    except json.JSONDecodeError:
        return []


# ---------- strategy: abstract ----------

def _prepare_abstract(papers: pd.DataFrame) -> pd.DataFrame:
    return papers


def _msg_abstract(row) -> str:
    return f"Title: {row['title']}\n\nAbstract: {row['abstract']}"


# ---------- strategy: fulltext ----------

def _prepare_fulltext(papers: pd.DataFrame) -> pd.DataFrame:
    out = papers.copy()
    out["fulltext"] = out["doi"].map(_load_docling)
    n = out["fulltext"].notna().sum()
    print(f"  fulltext: {n}/{len(out)} papers loaded from docling")
    return out


def _msg_fulltext(row) -> str:
    text = row.get("fulltext")
    if not text:
        return _msg_abstract(row)
    return f"Title: {row['title']}\n\nFull text (truncated):\n{text[:FULLTEXT_MAX_CHARS]}"


# ---------- strategy: sections ----------

def _prepare_sections(papers: pd.DataFrame) -> pd.DataFrame:
    out = _prepare_fulltext(papers)
    out["sections"] = out["fulltext"].map(lambda t: _parse_sections(t) if t else {})

    pick_msgs = [
        _build_picker_prompt(r["title"], r["abstract"], list(r["sections"].keys()))
        for _, r in out.iterrows()
    ]
    fire = out["sections"].map(len) > 0
    picked: list[str | None] = [None] * len(out)
    fire_idx  = [i for i, f in enumerate(fire) if f]
    fire_msgs = [pick_msgs[i] for i in fire_idx]
    fire_texts = classify_batch(fire_msgs, max_tokens=256)
    for i, t in zip(fire_idx, fire_texts):
        picked[i] = t
    out["picked"] = [_parse_picked(t) if t else [] for t in picked]
    n = (out["picked"].map(len) > 0).sum()
    print(f"  picker: {n}/{len(out)} papers got methodology headers")
    return out


def _msg_sections(row) -> str:
    if not row.get("picked"):
        return _msg_abstract(row)
    parts = [f"Title: {row['title']}", f"Abstract: {row['abstract']}"]
    sections = row.get("sections", {})
    for h in row["picked"]:
        body = sections.get(h) or next(
            (v for k, v in sections.items() if k.lower() == h.lower()), None
        )
        if body:
            parts.append(f"\n## {h}\n{body[:SECTION_MAX_CHARS]}")
    return "\n\n".join(parts)


# ---------- dispatcher ----------

_REGISTRY = {
    "abstract": (_prepare_abstract, _msg_abstract),
    "fulltext": (_prepare_fulltext, _msg_fulltext),
    "sections": (_prepare_sections, _msg_sections),
}

STRATEGIES = list(_REGISTRY)


def prepare(papers: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if strategy not in _REGISTRY:
        raise ValueError(f"unknown strategy {strategy!r}; choices: {STRATEGIES}")
    return _REGISTRY[strategy][0](papers)


def build_message(row, strategy: str) -> str:
    return _REGISTRY[strategy][1](row)
