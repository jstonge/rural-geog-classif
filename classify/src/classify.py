"""Generic paper classifier.

Three knobs:
  prompt       — system prompt text (what task the model is doing)
  response_key — JSON key the model returns (e.g. "method", "topics", "location")
  strategy     — how to build the user message (abstract / fulltext / sections)

Plus flags: thinking, max_tokens.

Label cardinality (single vs multi) is determined by the prompt itself ("choose
exactly one" vs "select all that apply") and recovered from the response JSON
shape — not a separate flag at classify time. Single-vs-multi scoring is a
validation-time choice (see score.py).
"""
from __future__ import annotations

import json
import re

import pandas as pd

from input_strategies import prepare, build_message
from lib.llm import classify_batch, classify_batch_thinking


def _parse(text: str, response_key: str) -> list[str] | None:
    """Auto-detect single- vs multi-label from the JSON response shape.
    Always returns list[str] (or None for unparsed). The prompt is the source
    of truth for cardinality; this parser is permissive — it accepts either shape.
    """
    m = re.search(r"\{.*\}", (text or "").strip(), re.DOTALL)
    if not m:
        return None
    try:
        val = json.loads(m.group()).get(response_key)
    except json.JSONDecodeError:
        return None
    if val is None:
        return None
    if isinstance(val, list):
        return list(val)
    if isinstance(val, str):
        return [val]
    return None


def classify(
    papers: pd.DataFrame,
    prompt: str,
    response_key: str,
    *,
    strategy: str = "abstract",
    thinking: bool = True,
    max_tokens: int | None = None,
) -> pd.DataFrame:
    """Classify each paper with the given prompt + strategy.

    Label cardinality (single vs multi) is determined by the prompt itself
    and recovered from the response JSON shape — not a separate flag.

    Returns a DataFrame with [doi, {response_key}_pred, {response_key}_reasoning].
    For strategy="sections" the DataFrame also carries the `picked` and `sections`
    columns (so downstream code — /compare export — can show them).
    """
    if max_tokens is None:
        max_tokens = 2048 if thinking else 256

    prepared = prepare(papers, strategy)

    messages = [
        [{"role": "system", "content": prompt},
         {"role": "user", "content": build_message(row, strategy)}]
        for _, row in prepared.iterrows()
    ]

    if thinking:
        results = classify_batch_thinking(messages, max_tokens=max_tokens)
        preds = [_parse(c, response_key) for c, _ in results]
        reasons = [r for _, r in results]
    else:
        results = classify_batch(messages, max_tokens=max_tokens)
        preds = [_parse(c, response_key) for c in results]
        reasons = [None] * len(results)

    n_parsed = sum(p is not None for p in preds)
    print(f"  classify[{response_key}, strategy={strategy}]: {n_parsed}/{len(preds)} parsed")

    out = pd.DataFrame({
        "doi": prepared["doi"].values,
        f"{response_key}_pred": preds,
        f"{response_key}_reasoning": reasons,
    })
    # Preserve strategy-specific columns so downstream /compare can show them.
    for col in ("picked", "sections", "fulltext"):
        if col in prepared.columns:
            out[col] = prepared[col].values
    return out
