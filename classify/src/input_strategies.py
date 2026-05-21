"""Input strategies for the classifier — different ways to build the user message.

Four strategies:
  abstract  — title + abstract (default; what locations / topics use)
  fulltext  — title + first N chars of docling-parsed text
  sections  — title + abstract + methodology sections picked by gemma (Phase A+B)
  intro     — title + abstract + heuristic intro outline (first 3 substantive
              body headers + previews, via lib.intro_outline.pick_outline)

Each strategy has two parts:
  prepare(papers)       — add columns the strategy needs (fulltext / sections / picked)
  build_message(row)    — return the user message string for one paper
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from lib.intro_outline import pick_outline
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

PICKER_CACHE_PATH = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/output/picker_cache.parquet")


def _load_picker_cache() -> dict[str, list[str]]:
    """Read DOI -> picked-headers cache. Empty dict if file missing."""
    if not PICKER_CACHE_PATH.exists():
        return {}
    df = pd.read_parquet(PICKER_CACHE_PATH)
    return {row["doi"]: list(row["picked"]) for _, row in df.iterrows()}


def _save_picker_cache(cache: dict[str, list[str]]) -> None:
    PICKER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"doi": d, "picked": p} for d, p in cache.items()])
    df.to_parquet(PICKER_CACHE_PATH)


def _prepare_sections(papers: pd.DataFrame) -> pd.DataFrame:
    """Phase A (parse docling sections) + Phase B (LLM picks methodology headers).

    Phase B output is cached per-DOI at classify/output/picker_cache.parquet.
    DOIs already in cache skip the LLM call. Delete the cache file if you
    edit the picker prompt (it's schema-agnostic so doesn't usually need it).
    """
    out = _prepare_fulltext(papers)
    out["sections"] = out["fulltext"].map(lambda t: _parse_sections(t) if t else {})

    cache = _load_picker_cache()
    fire_idx = [
        i for i, r in enumerate(out.itertuples())
        if r.doi not in cache and len(r.sections) > 0
    ]

    if fire_idx:
        fire_msgs = [
            _build_picker_prompt(out.iloc[i]["title"],
                                  out.iloc[i]["abstract"],
                                  list(out.iloc[i]["sections"].keys()))
            for i in fire_idx
        ]
        fire_texts = classify_batch(fire_msgs, max_tokens=256)
        for i, t in zip(fire_idx, fire_texts):
            cache[out.iloc[i]["doi"]] = _parse_picked(t)
        _save_picker_cache(cache)

    out["picked"] = [cache.get(d, []) for d in out["doi"]]
    n = (out["picked"].map(len) > 0).sum()
    print(f"  picker: {n}/{len(out)} have picked headers "
          f"({len(out) - len(fire_idx)} from cache, {len(fire_idx)} fresh)")
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


# ---------- strategy: intro ----------
# Heuristic outline (no LLM picker). Reuses the docling parse already done in
# _prepare_fulltext + _parse_sections, then runs lib.intro_outline.pick_outline.
# The picker is deterministic so we don't cache.

def _prepare_intro(papers: pd.DataFrame) -> pd.DataFrame:
    out = _prepare_fulltext(papers)
    full_sections = out["fulltext"].map(lambda t: _parse_sections(t) if t else {})
    outlines: list[list[tuple[str, str]]] = []
    for i in range(len(out)):
        sec = full_sections.iloc[i]
        if not sec:
            outlines.append([])
            continue
        outlines.append(pick_outline(sec,
                                     out.iloc[i].get("title") or "",
                                     out.iloc[i].get("abstract") or ""))
    out["intro_outline"] = outlines
    # `picked` + `sections` mirror the methods-sections strategy so the snapshot
    # carries exactly what gemma saw and /compare's pickedBlocks renders it
    # without any strategy-specific code on the frontend.
    out["picked"] = [[h for h, _ in o] for o in outlines]
    out["sections"] = [{h: s for h, s in o} for o in outlines]
    n = sum(1 for o in outlines if o)
    print(f"  intro: {n}/{len(out)} papers have a picked outline")
    return out


def _msg_intro(row) -> str:
    outline = row.get("intro_outline") or []
    if not outline:
        return _msg_abstract(row)
    parts = [f"Title: {row['title']}", f"Abstract: {row['abstract']}",
             "\nIntroduction / framing sections (auto-extracted from full text):"]
    for header, snippet in outline:
        parts.append(f"\n## {header}\n{snippet}")
    return "\n\n".join(parts)


# ---------- dispatcher ----------

_REGISTRY = {
    "abstract": (_prepare_abstract, _msg_abstract),
    "fulltext": (_prepare_fulltext, _msg_fulltext),
    "sections": (_prepare_sections, _msg_sections),
    "intro":    (_prepare_intro,    _msg_intro),
}

STRATEGIES = list(_REGISTRY)


def prepare(papers: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if strategy not in _REGISTRY:
        raise ValueError(f"unknown strategy {strategy!r}; choices: {STRATEGIES}")
    return _REGISTRY[strategy][0](papers)


def build_message(row, strategy: str) -> str:
    return _REGISTRY[strategy][1](row)
