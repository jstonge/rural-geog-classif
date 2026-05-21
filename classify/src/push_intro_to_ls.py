"""Push a 3-header outline of each paper to LS as `intro_section_html`, rendered
as a collapsible <details> block under the "Choose topic" header in the schema
(see schemas/prompts/v3/schema.xml).

Outline = first 3 substantive section headers from the docling parse, each with
a short body preview. "Substantive" means we skip:
  - publisher / journal cover-page boilerplate ("Please scroll down…",
    "Downloaded by…", journal title headers)
  - headers that duplicate the paper title (often appears twice in docling)
  - back-matter (acknowledgments, notes, references, bibliography, appendix)
  - parent headers with no body of their own
  - sections whose body overlaps heavily with the WoS abstract (the docling
    abstract block sometimes sits under its own header)

No LLM picker — purely heuristic. Mirrors push_sections_to_ls.py for the field
plumbing.

Run `python classify/src/ls_backup.py 113` first.

Usage:
    # Dry-run on first 10 LS tasks (writes diagnostics to ~/intro_picker_diag_<ts>.txt)
    python classify/src/push_intro_to_ls.py --limit 10

    # Push everything
    python classify/src/push_intro_to_ls.py --apply

    # Clear the field on all tasks
    python classify/src/push_intro_to_ls.py --restore --apply
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import httpx
import markdown
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

from input_strategies import _load_docling, _parse_sections
from lib.intro_outline import pick_outline

PROJECT_ID = 113

DOCLING_GH_URL = (
    "https://github.com/jstonge/rural-geog-classif/blob/main/parse/output/docling/{key}.md"
)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pick_outline(sections, title, abstract, diagnostics=None):
    """Thin alias preserving the local call sites — actual picker lives in
    lib.intro_outline so input_strategies can share it.
    """
    return pick_outline(sections, title, abstract, diagnostics=diagnostics)


def _render_html(picked: list[tuple[str, str]], doi: str) -> str:
    if not picked:
        return ""
    parts = []
    for header, snippet in picked:
        snippet_html = markdown.markdown(snippet, extensions=["extra"])
        parts.append(
            f"<h4 style='margin:0.5em 0 0.2em'>{_escape(header)}</h4>"
            f"<div style='font-size:0.9em;margin:0;padding:0.5em;"
            f"background:#f7f7f7;border-radius:4px;line-height:1.45'>"
            f"{snippet_html}</div>"
        )
    gh_url = DOCLING_GH_URL.format(key=doi.replace("/", "_"))
    parts.append(
        f"<p style='margin:0.75em 0 0;font-size:0.85em'>"
        f"<a href='{_escape(gh_url)}' target='_blank' rel='noopener'>"
        f"View full parsed paper on GitHub &rarr;</a></p>"
    )
    return (
        "<details style='margin:0.5em 0'>"
        "<summary style='cursor:pointer;font-weight:600'>"
        f"Paper outline — first {len(picked)} section{'s' if len(picked) != 1 else ''} "
        "(click to expand)</summary>"
        + "".join(parts)
        + "</details>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Actually push (default: dry-run).")
    ap.add_argument("--restore", action="store_true",
                    help="Clear intro_section_html on all tasks. Ignores outline build.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N LS tasks (useful for dry-runs).")
    ap.add_argument("--diag-out", type=Path, default=None,
                    help="Write diagnostics to this path (default: ~/intro_picker_diag_<ts>.txt).")
    args = ap.parse_args()

    load_dotenv()
    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    tasks = list(client.tasks.list(project=PROJECT_ID))
    if args.limit:
        tasks = tasks[:args.limit]
    print(f"Project {PROJECT_ID}: {len(tasks)} tasks")

    if args.restore:
        to_clear = [t for t in tasks if (t.data or {}).get("intro_section_html")]
        print(f"Tasks to clear intro_section_html: {len(to_clear)}")
        if not args.apply:
            print("DRY RUN — pass --apply to clear.")
            return
        for t in to_clear:
            d = {**t.data}
            d.pop("intro_section_html", None)
            client.tasks.update(id=t.id, data=d)
        print(f"Cleared {len(to_clear)} tasks.")
        return

    patches: list[tuple[int, dict]] = []
    diag_rows: list[tuple[str, list, list]] = []  # (doi, picked_headers, diagnostics)
    for t in tasks:
        d = t.data or {}
        doi = d.get("DOI")
        if not doi:
            continue
        fulltext = _load_docling(doi)
        if not fulltext:
            continue
        sections = _parse_sections(fulltext)
        if not sections:
            continue
        diagnostics: list = []
        picked = _pick_outline(sections, d.get("Article Title") or "",
                                d.get("text") or "", diagnostics=diagnostics)
        diag_rows.append((doi, [h for h, _ in picked], diagnostics))
        html = _render_html(picked, doi)
        if not html:
            continue
        patches.append((t.id, {**d, "intro_section_html": html}))

    print(f"\nPatches to apply: {len(patches)} (of {len(diag_rows)} candidates)\n")

    if not args.apply or args.limit:
        diag_path = args.diag_out or Path.home() / (
            f"intro_picker_diag_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        with diag_path.open("w") as f:
            f.write("DIAGNOSTICS (outline build — first 3 substantive headers + preview)\n")
            f.write("=" * 80 + "\n")
            for doi, picked, diag in diag_rows:
                f.write(f"\nDOI: {doi}\n")
                f.write(f"  picked: {picked}\n")
                f.write(f"  github: {DOCLING_GH_URL.format(key=doi.replace('/', '_'))}\n")
                for h, n_or_none, info in diag:
                    if n_or_none is None:
                        f.write(f"    [{h}] {info}\n")
                    else:
                        f.write(f"    [{h}] preview ({n_or_none} chars):\n")
                        f.write(f"      {info[:200]}\n")
        print(f"Wrote diagnostics for {len(diag_rows)} candidates -> {diag_path}")

    if not args.apply:
        print("\nDRY RUN — pass --apply to push.")
        return

    for tid, new_data in patches:
        client.tasks.update(id=tid, data=new_data)
    print(f"Set intro_section_html on {len(patches)} tasks in project {PROJECT_ID}")


if __name__ == "__main__":
    main()
