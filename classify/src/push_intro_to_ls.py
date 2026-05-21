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
import re
from datetime import datetime
from pathlib import Path

import httpx
import markdown
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

from input_strategies import _load_docling, _parse_sections

PROJECT_ID = 113
N_HEADERS = 3
SECTION_PREVIEW_CHARS = 1200
RESCUED_PREVIEW_CHARS = 3000  # Larger window for headerless intros (rescue path)
MIN_BODY_CHARS = 200
ABSTRACT_OVERLAP_DROP = 0.4
TITLE_OVERLAP_DROP = 0.85

DOCLING_GH_URL = (
    "https://github.com/jstonge/rural-geog-classif/blob/main/parse/output/docling/{key}.md"
)

JUNK_HEADER_RE = re.compile(
    r"(?:please\s+scroll|downloaded\s+by|publication\s+details|"
    r"please\s+cite|to\s+link\s+to|terms\s+(?:and|&)\s+conditions|"
    r"acknowledg|^notes?$|^references$|^bibliography$|^appendix|"
    r"supplementary|^abstract$|^keywords?$|^disclosure|^funding$|^orcid)",
    re.IGNORECASE,
)

# Headers that mark the start of the methods/results portion of the paper.
# When we hit one of these we stop picking — everything beyond is past the
# intro/framing region. Conservative: only the clearest markers, so things
# like "Analytical Framework" (which can be either lit-review or methods)
# still flow through the normal path.
STOP_HEADER_RE = re.compile(
    r"^(?:"
    r"methodolog\w*|methods?|materials?\s+and\s+methods?|"
    r"study\s+(?:area|site|design|setting)|"
    r"data(?:\s+and)?(?:\s+(?:collection|analysis|sources?|set|description))?|"
    r"results?|findings?|discussion|conclusion"
    r")\s*$",
    re.IGNORECASE,
)

# Body-side filter: a section whose body STARTS with any of these is metadata
# (citation blurb, ISSN block, license, etc.), regardless of what the header
# happens to be. Catches journal-name headers, author bylines, and copyright
# statements without needing to enumerate every journal title.
JUNK_BODY_RE = re.compile(
    r"^\s*(?:to\s+cite\s+this\s+article|issn[:\s]|"
    r"journal\s+homepage|publication\s+details|published\s+online|"
    r"this\s+is\s+an\s+open\s+access|to\s+link\s+to|"
    r"\(c\)|©|copyright|"
    r"<!--\s*image\s*-->\s*$)",
    re.IGNORECASE,
)

IMAGE_COMMENT_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)

# Affiliation paragraph: starts with a single-letter superscript label
# ("a Kwame Nkrumah University…", "b Department of…") and names an institution.
AFFILIATION_RE = re.compile(
    r"^[a-z]\s+\w+.*\b("
    r"University|Universit[aá]|Institute|Institut|College|"
    r"School|Department|Faculty|Lab|Center|Centre|Academy"
    r")\b",
    re.IGNORECASE,
)

# Cheap English-language sniff: count occurrences of high-frequency English
# function words. Translations of the abstract (Chinese, Spanish, etc.) that
# get embedded in docling output have ~zero of these.
ENGLISH_MARKERS_RE = re.compile(
    r"\b(?:the|of|and|in|to|is|are|that|this|with|for|from|by|as)\b",
    re.IGNORECASE,
)
# English paragraphs hit these markers ~30-50 times per 1000 chars; Spanish
# (with badly-OCR'd accents creating spurious "as" matches) sits around 1-2.
MIN_ENGLISH_MARKER_DENSITY = 0.008  # 8 markers per 1000 chars


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", (text or "").lower()))


def _shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    toks = re.findall(r"\w+", (text or "").lower())
    if len(toks) < n:
        return set()
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _truncate_at_paragraph(body: str, max_chars: int) -> str:
    """Cut at the last paragraph break (\\n\\n) before max_chars; if none found
    in the back half of the window, fall back to last single \\n, then last
    sentence end, then a hard cut. Avoids slicing mid-sentence in the snippet.
    """
    if len(body) <= max_chars:
        return body.strip()
    cut = body[:max_chars]
    half = max_chars // 2
    for boundary in ("\n\n", "\n"):
        idx = cut.rfind(boundary)
        if idx >= half:
            return cut[:idx].strip()
    for end in (". ", "? ", "! "):
        idx = cut.rfind(end)
        if idx >= half:
            return cut[:idx + 1].strip()
    return cut.strip()


MIN_PARA_CHARS = 100


def _strip_abstract_paragraphs(body: str, abs_shingles: set) -> str:
    """For a body block that contains [authors / affiliations / abstract / intro],
    drop the abstract paragraph(s), very-short paragraphs (author names,
    affiliations, captions), and metadata paragraphs (citation blurbs / ISSN /
    license blocks). Returns whatever intro paragraphs remain.
    """
    paras = re.split(r"\n{2,}", body)
    kept = []
    for p in paras:
        s = p.strip()
        if len(s) < MIN_PARA_CHARS:
            continue
        if JUNK_BODY_RE.match(s):
            continue
        if AFFILIATION_RE.match(s):
            continue
        if len(ENGLISH_MARKERS_RE.findall(s)) / max(len(s), 1) < MIN_ENGLISH_MARKER_DENSITY:
            continue
        if _jaccard(_shingles(s), abs_shingles) >= ABSTRACT_OVERLAP_DROP:
            continue
        kept.append(s)
    return "\n\n".join(kept)


def _pick_outline(sections: dict[str, str], title: str, abstract: str,
                  diagnostics: list | None = None) -> list[tuple[str, str]]:
    abs_shingles = _shingles(abstract)
    picked: list[tuple[str, str]] = []
    rescued_once = False

    def log(header, info):
        if diagnostics is not None:
            diagnostics.append((header, None, info))

    for header, body in sections.items():
        if len(picked) >= N_HEADERS:
            break

        if STOP_HEADER_RE.match(header.strip()):
            log(header, "stopped: reached methods/results boundary")
            break

        if JUNK_HEADER_RE.search(header):
            log(header, "skipped: boilerplate/back-matter")
            continue
        if JUNK_BODY_RE.match(body or ""):
            log(header, "skipped: metadata body (citation/license/ISSN)")
            continue

        cleaned = IMAGE_COMMENT_RE.sub("", body or "").strip()

        h_words, t_words = _word_set(header), _word_set(title)
        title_j = (len(h_words & t_words) / len(h_words | t_words)
                   if h_words and t_words else 0.0)

        if title_j >= TITLE_OVERLAP_DROP:
            if rescued_once:
                log(header, f"skipped: title duplicate (jaccard={title_j:.2f})")
                continue
            rescued = _strip_abstract_paragraphs(cleaned, abs_shingles)
            if len(rescued) < MIN_BODY_CHARS:
                log(header, f"skipped: title duplicate (jaccard={title_j:.2f}), "
                            f"no intro paragraphs to rescue")
                continue
            snippet = _truncate_at_paragraph(rescued, RESCUED_PREVIEW_CHARS)
            if diagnostics is not None:
                diagnostics.append(
                    (header, len(snippet),
                     f"RESCUED intro from title-duplicate body: {snippet[:200]}"))
            picked.append(("Introduction", snippet))
            rescued_once = True
            continue

        if len(cleaned) < MIN_BODY_CHARS:
            log(header, f"skipped: body too short ({len(cleaned)} chars)")
            continue

        overlap = _jaccard(_shingles(cleaned), abs_shingles)
        if overlap >= ABSTRACT_OVERLAP_DROP:
            log(header, f"skipped: abstract overlap (jaccard={overlap:.2f})")
            continue

        snippet = _truncate_at_paragraph(cleaned, SECTION_PREVIEW_CHARS)
        if diagnostics is not None:
            diagnostics.append((header, len(snippet), snippet[:200]))
        picked.append((header, snippet))
    return picked


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
