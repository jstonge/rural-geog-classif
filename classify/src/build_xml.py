"""Generate the LS `<Choices>` block for a control from its CSV schema.

Usage:
    python classify/src/build_xml.py classify/schemas/prompts/v3/categories/methods.csv \\
        [--name methods] [--choice single] [--to-name text]

The CSV has two columns: Value, Definition. Control name defaults to the CSV
filename stem. Prints an LS-compatible Choices block — paste into the project's
label config in LS (or into the schema XML at prompts/{schema}/schema.xml).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load_values(schema_csv: Path) -> list[str]:
    with schema_csv.open(newline="") as f:
        return [row["Value"] for row in csv.DictReader(f)]


def build_choices_block(values: list[str], *, name: str,
                         choice: str = "single", to_name: str = "text",
                         in_line: bool = True) -> str:
    showInLine = "true" if in_line else "false"
    lines = [f'<Choices name="{name}" toName="{to_name}" choice="{choice}" showInLine="{showInLine}">']
    for v in values:
        lines.append(f'  <Choice value="{v}"/>')
    lines.append("</Choices>")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schema_csv", type=Path,
                    help="CSV with columns Value, Definition (e.g. v3/categories/methods.csv).")
    ap.add_argument("--name", default=None,
                    help="LS control name (default: CSV filename stem).")
    ap.add_argument("--choice", default="single", choices=["single", "multiple"])
    ap.add_argument("--to-name", default="text")
    args = ap.parse_args()

    values = load_values(args.schema_csv)
    name = args.name or args.schema_csv.stem
    print(build_choices_block(values, name=name, choice=args.choice, to_name=args.to_name))


if __name__ == "__main__":
    main()
