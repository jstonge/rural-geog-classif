"""Append gemma-extracted methodology sections to each LS task's `text` field
(the abstract that annotators already see) so they get the section text inline
without any schema change.

Strategy:
  - On first push, the original abstract is saved into `text_original` so future
    re-pushes can restore it before re-appending (idempotent).
  - The appended content is plain markdown — LS's <Text> control shows it
    verbatim (## markers visible, but readable).
  - No label_config change. Reversible via `--restore` which writes
    `text_original` back into `text` and deletes the sentinel field.

Run `python classify/src/ls_backup.py 113` first.

Usage:
    # Dry-run (default)
    python classify/src/push_sections_to_ls.py --snapshot <sections-snapshot>

    # Actually push
    python classify/src/push_sections_to_ls.py --snapshot <sections-snapshot> --apply

    # Roll back to the original abstracts
    python classify/src/push_sections_to_ls.py --restore --apply
"""
from __future__ import annotations

import argparse
import os

import httpx
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

from lib.snapshots import load_snapshot

PROJECT_ID = 113
SECTION_PREVIEW_CHARS = 1500
SEPARATOR = "\n\n---\n\nAUTO-EXTRACTED METHODS SECTIONS (from full text):\n"


def build_sections_block(row) -> str:
    """Format picked sections as a markdown block to append to the abstract."""
    picked = row.get("picked") if hasattr(row, "get") else None
    sections = row.get("sections") if hasattr(row, "get") else None
    if not picked or not sections:
        return ""
    parts = []
    for h in picked:
        body = sections.get(h) or next(
            (v for k, v in sections.items() if k.lower() == h.lower()), None
        )
        if not body:
            continue
        parts.append(f"\n## {h}\n\n{body[:SECTION_PREVIEW_CHARS].strip()}")
    return "\n".join(parts) if parts else ""


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

    load_dotenv()
    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )

    tasks = list(client.tasks.list(project=PROJECT_ID))
    print(f"Project {PROJECT_ID}: {len(tasks)} tasks")

    # --- RESTORE branch: text = text_original; drop text_original ---
    if args.restore:
        to_restore = [t for t in tasks if (t.data or {}).get("text_original")]
        print(f"Tasks with text_original (to restore): {len(to_restore)}")
        if not args.apply:
            print("DRY RUN — pass --apply to push.")
            return
        for t in to_restore:
            d = {**t.data, "text": t.data["text_original"]}
            d.pop("text_original", None)
            client.tasks.update(id=t.id, data=d)
        print(f"Restored {len(to_restore)} tasks.")
        return

    # --- APPEND branch ---
    snap = load_snapshot(args.snapshot)
    preds = snap["predictions"]
    if "picked" not in preds.columns or "sections" not in preds.columns:
        raise SystemExit(
            f"Snapshot {args.snapshot} has no picked/sections columns (sections-strategy required)."
        )
    doi_to_block = {}
    for _, r in preds.iterrows():
        block = build_sections_block(r)
        if block:
            doi_to_block[r["doi"]] = block
    print(f"Built section blocks for {len(doi_to_block)} DOIs")

    # Build per-task patches (idempotent: restore from text_original before re-appending)
    patches = []
    for t in tasks:
        doi = (t.data or {}).get("DOI")
        block = doi_to_block.get(doi)
        if not block:
            continue
        original = t.data.get("text_original") or t.data.get("text") or ""
        new_text = original + SEPARATOR + block
        patches.append((t.id, {**t.data, "text": new_text, "text_original": original}))

    print(f"Patches to apply: {len(patches)}")
    if not args.apply:
        print("DRY RUN — pass --apply to push.")
        # Show a sample
        if patches:
            tid, sample = patches[0]
            print(f"\nSample task {tid} new text (first 600 chars after the separator):")
            idx = sample["text"].find(SEPARATOR)
            print(sample["text"][idx:idx + 600] + ("..." if len(sample["text"]) > idx + 600 else ""))
        return

    for tid, new_data in patches:
        client.tasks.update(id=tid, data=new_data)
    print(f"Augmented `text` for {len(patches)} tasks in project {PROJECT_ID}")


if __name__ == "__main__":
    main()
