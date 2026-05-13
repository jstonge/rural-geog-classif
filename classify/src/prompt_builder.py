"""Build a final prompt by injecting categories + examples into a template.

Templates live at `prompts/{schema}/core/{task}_{variant}.md` and use two
placeholders (both optional):
  {CATEGORIES} — replaced by a bulleted list of (Value, Definition) from a schema CSV
  {EXAMPLES}   — replaced by concatenated example bodies

The schema CSV (`prompts/{schema}/categories/{task}.csv`) has columns Value
and Definition. Example bodies live in `prompts/{schema}/examples/{task}/`.

The CSV is the single source of truth for the category set. The same CSV
can be used by `build_xml.py` to derive the LS `<Choices>` block.
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
    Rows with empty Definition are rendered as `- value` (no trailing colon).
    """
    lines = []
    for c in categories:
        definition = (c.get("definition") or "").strip()
        lines.append(f"- {c['value']}: {definition}" if definition else f"- {c['value']}")
    return "\n".join(lines)


def list_examples(examples_dir: Path) -> list[str]:
    return sorted(p.stem for p in examples_dir.glob("*.md"))


def load_examples(examples_dir: Path, names: list[str] | None = None) -> list[str]:
    if names is None:
        files = sorted(examples_dir.glob("*.md"))
    else:
        files = []
        for name in names:
            p = examples_dir / f"{name}.md"
            if not p.exists():
                raise FileNotFoundError(f"example not found: {p}")
            files.append(p)
    return [p.read_text().strip() for p in files]


def build_prompt(template_path: Path,
                 schema_path: Path | None,
                 examples_dir: Path | None,
                 example_names: list[str] | None = None) -> str:
    """Inject {CATEGORIES} (from schema CSV) and {EXAMPLES} (from example files)
    into the template. Both placeholders are optional — if a template doesn't
    contain one, the corresponding substitution is skipped.
    """
    template = template_path.read_text()

    if "{CATEGORIES}" in template:
        if schema_path is None or not Path(schema_path).exists():
            raise ValueError(f"{template_path} uses {{CATEGORIES}} but no schema CSV provided")
        template = template.replace("{CATEGORIES}", render_categories(load_categories(schema_path)))

    if "{EXAMPLES}" in template:
        if examples_dir is None or not Path(examples_dir).exists():
            examples = ""
        else:
            examples = "\n\n".join(load_examples(examples_dir, example_names))
        template = template.replace("{EXAMPLES}", examples)

    return template
