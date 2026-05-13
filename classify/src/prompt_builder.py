"""Build a final prompt by injecting categories + examples into a template.

Templates live at `prompts/{schema}/core/{task}_{variant}.md` and use two
placeholders (both optional):
  {CATEGORIES} — replaced by a bulleted list of (Value, Definition) from a schema CSV
  {EXAMPLES}   — replaced verbatim by the content of an examples file

Categories: `prompts/{schema}/categories/{task}_{variant}.csv` (Value, Definition).
Examples:   `prompts/{schema}/examples/{task}_{variant}.md` — one file per revision,
            containing the full example block (Input/Output pairs, blank-line
            separated).
"""
from __future__ import annotations

import csv
from pathlib import Path


def load_categories(schema_path: Path) -> list[dict]:
    """Read [{value, definition}, ...] from a schema CSV (columns: Value, Definition)."""
    with Path(schema_path).open(newline="") as f:
        return [
            {"value": row["Value"], "definition": row.get("Definition") or ""}
            for row in csv.DictReader(f)
        ]


def render_categories(categories: list[dict]) -> str:
    """Format categories as a markdown bullet list for {CATEGORIES} injection.
    Rows with empty Definition render as `- value` (no trailing colon).
    """
    lines = []
    for c in categories:
        definition = (c.get("definition") or "").strip()
        lines.append(f"- {c['value']}: {definition}" if definition else f"- {c['value']}")
    return "\n".join(lines)


def build_prompt(template_path: Path,
                 schema_path: Path | None,
                 examples_path: Path | None) -> str:
    """Inject {CATEGORIES} (from schema CSV) and {EXAMPLES} (from a single .md file)
    into the template. Both placeholders are optional — if a template doesn't
    contain one, the corresponding substitution is skipped.
    """
    template = template_path.read_text()

    if "{CATEGORIES}" in template:
        if schema_path is None or not Path(schema_path).exists():
            raise ValueError(f"{template_path} uses {{CATEGORIES}} but no schema CSV provided")
        template = template.replace("{CATEGORIES}", render_categories(load_categories(schema_path)))

    if "{EXAMPLES}" in template:
        if examples_path is None or not Path(examples_path).exists():
            examples = ""
        else:
            examples = Path(examples_path).read_text().strip()
        template = template.replace("{EXAMPLES}", examples)

    return template
