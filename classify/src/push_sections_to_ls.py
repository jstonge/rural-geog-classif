"""Push gemma-extracted methodology sections to each LS task as a separate
`method_section_html` field, rendered as a collapsible <details> block under
the "Choose Methods" header in the schema (see schemas/prompts/v3/schema.xml).

This replaces the older behavior of appending the sections onto `text`. The
sections now live as their own task field, so annotators see them attached to
the methods question rather than mixed into the abstract.

Strategy:
  - Push HTML directly into `data.method_section_html`; the schema's
    <HyperText value="$method_section_html"/> renders it inline.
  - `text` is left untouched.
  - --restore clears `method_section_html` and, for tasks pushed under the
    older "append to text" scheme, also writes `text_original` back into
    `text` and drops the sentinel.

Run `python classify/src/ls_backup.py 113` first.

Usage:
    # Dry-run (default)
    python classify/src/push_sections_to_ls.py --snapshot <sections-snapshot>

    # Actually push
    python classify/src/push_sections_to_ls.py --snapshot <sections-snapshot> --apply

    # Clear the field (and restore any legacy text_original)
    python classify/src/push_sections_to_ls.py --restore --apply
"""
from __future__ import annotations

import argparse

import markdown

from lib.labelstudio import make_client
from lib.snapshots import load_snapshot

PROJECT_ID = 113
SECTION_PREVIEW_CHARS = 1500


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_sections_html(row) -> str:
    """Format picked sections as a collapsible HTML <details> block.
    Section bodies are docling markdown — converted to HTML so headers, lists,
    emphasis render properly instead of showing literal `##` etc.
    """
    picked = row.get("picked") if hasattr(row, "get") else None
    sections = row.get("sections") if hasattr(row, "get") else None
    if not picked or not sections:
        return ""
    body_parts = []
    for h in picked:
        body = sections.get(h) or next(
            (v for k, v in sections.items() if k.lower() == h.lower()), None
        )
        if not body:
            continue
        snippet_md = body[:SECTION_PREVIEW_CHARS].strip()
        snippet_html = markdown.markdown(snippet_md, extensions=["extra"])
        body_parts.append(
            f"<h4 style='margin:0.5em 0 0.2em'>{_escape(h)}</h4>"
            f"<div style='font-size:0.9em;margin:0;padding:0.5em;"
            f"background:#f7f7f7;border-radius:4px;line-height:1.45'>"
            f"{snippet_html}</div>"
        )
    if not body_parts:
        return ""
    return (
        "<details style='margin:0.5em 0'>"
        "<summary style='cursor:pointer;font-weight:600'>"
        "Auto-extracted method sections (click to expand)"
        "</summary>"
        + "".join(body_parts)
        + "</details>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None,
                    help="Snapshot with picked sections (sections-strategy run).")
    ap.add_argument("--apply", action="store_true",
                    help="Actually push (default: dry-run).")
    ap.add_argument("--restore", action="store_true",
                    help="Restore original abstracts from text_original. Ignores --snapshot.")
    args = ap.parse_args()

    if not args.restore and not args.snapshot:
        ap.error("--snapshot is required (unless using --restore)")

    client = make_client()

    tasks = list(client.tasks.list(project=PROJECT_ID))
    print(f"Project {PROJECT_ID}: {len(tasks)} tasks")

    # --- RESTORE branch: drop method_section_html; restore legacy text_original ---
    if args.restore:
        to_restore = [
            t for t in tasks
            if (t.data or {}).get("method_section_html")
            or (t.data or {}).get("text_original")
        ]
        print(f"Tasks to clean (method_section_html or text_original): {len(to_restore)}")
        if not args.apply:
            print("DRY RUN — pass --apply to push.")
            return
        for t in to_restore:
            d = {**t.data}
            if d.get("text_original"):
                d["text"] = d["text_original"]
                d.pop("text_original", None)
            d.pop("method_section_html", None)
            client.tasks.update(id=t.id, data=d)
        print(f"Cleaned {len(to_restore)} tasks.")
        return

    # --- PUSH branch ---
    snap = load_snapshot(args.snapshot)
    preds = snap["predictions"]
    if "picked" not in preds.columns or "sections" not in preds.columns:
        raise SystemExit(
            f"Snapshot {args.snapshot} has no picked/sections columns (sections-strategy required)."
        )
    doi_to_html = {}
    for _, r in preds.iterrows():
        html = build_sections_html(r)
        if html:
            doi_to_html[r["doi"]] = html
    print(f"Built section HTML for {len(doi_to_html)} DOIs")

    # Build per-task patches. If a task was previously augmented via the old
    # "append to text" path, restore text from text_original first.
    patches = []
    for t in tasks:
        doi = (t.data or {}).get("DOI")
        html = doi_to_html.get(doi)
        if not html:
            continue
        new_data = {**t.data, "method_section_html": html}
        if new_data.get("text_original"):
            new_data["text"] = new_data["text_original"]
            new_data.pop("text_original", None)
        patches.append((t.id, new_data))

    print(f"Patches to apply: {len(patches)}")
    if not args.apply:
        print("DRY RUN — pass --apply to push.")
        if patches:
            tid, sample = patches[0]
            print(f"\nSample task {tid} method_section_html (first 500 chars):")
            print(sample["method_section_html"][:500] + "...")
        return

    for tid, new_data in patches:
        client.tasks.update(id=tid, data=new_data)
    print(f"Set method_section_html on {len(patches)} tasks in project {PROJECT_ID}")


if __name__ == "__main__":
    main()
