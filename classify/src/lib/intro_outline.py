"""Heuristic intro / framing picker for docling-parsed papers.

Pure-Python — no LLM, no LS, no I/O. Given:
  - sections: {header: body} as returned by input_strategies._parse_sections
  - title:    the paper's WoS title (for de-duping title-repeat headers)
  - abstract: the WoS abstract (for stripping redundant abstract paragraphs)

Returns up to N_HEADERS (default 3) (header, snippet) tuples, filtered to skip
cover-page boilerplate, journal-name/byline/citation/license metadata, abstract
duplicates, affiliations, non-English (Chinese/Spanish/etc. translation blocks),
and stopping at the methods/results boundary. When the first real intro lives
under a title-duplicate header (no separate ## Introduction), one rescue path
extracts the intro paragraphs from that body and labels them "Introduction".

Consumed by:
  - push_intro_to_ls.py (renders HTML for LS)
  - input_strategies.py "intro" strategy (builds classifier input)
"""
from __future__ import annotations

import re

N_HEADERS = 3
SECTION_PREVIEW_CHARS = 1200
RESCUED_PREVIEW_CHARS = 3000
MIN_BODY_CHARS = 200
MIN_PARA_CHARS = 100
ABSTRACT_OVERLAP_DROP = 0.4
TITLE_OVERLAP_DROP = 0.85
MIN_ENGLISH_MARKER_DENSITY = 0.008

JUNK_HEADER_RE = re.compile(
    r"(?:please\s+scroll|downloaded\s+by|publication\s+details|"
    r"please\s+cite|to\s+link\s+to|terms\s+(?:and|&)\s+conditions|"
    r"acknowledg|^notes?$|^references$|^bibliography$|^appendix|"
    r"supplementary|^abstract$|^keywords?$|^disclosure|^funding$|^orcid)",
    re.IGNORECASE,
)

STOP_HEADER_RE = re.compile(
    r"^(?:"
    r"methodolog\w*|methods?|materials?\s+and\s+methods?|"
    r"study\s+(?:area|site|design|setting)|"
    r"data(?:\s+and)?(?:\s+(?:collection|analysis|sources?|set|description))?|"
    r"results?|findings?|discussion|conclusion"
    r")\s*$",
    re.IGNORECASE,
)

JUNK_BODY_RE = re.compile(
    r"^\s*(?:to\s+cite\s+this\s+article|issn[:\s]|"
    r"journal\s+homepage|publication\s+details|published\s+online|"
    r"this\s+is\s+an\s+open\s+access|to\s+link\s+to|"
    r"\(c\)|©|copyright|"
    r"<!--\s*image\s*-->\s*$)",
    re.IGNORECASE,
)

IMAGE_COMMENT_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)

AFFILIATION_RE = re.compile(
    r"^[a-z]\s+\w+.*\b("
    r"University|Universit[aá]|Institute|Institut|College|"
    r"School|Department|Faculty|Lab|Center|Centre|Academy"
    r")\b",
    re.IGNORECASE,
)

ENGLISH_MARKERS_RE = re.compile(
    r"\b(?:the|of|and|in|to|is|are|that|this|with|for|from|by|as)\b",
    re.IGNORECASE,
)


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


def _strip_abstract_paragraphs(body: str, abs_shingles: set) -> str:
    """Drop short paragraphs (author names, affiliations, captions), abstract
    duplicates, citation/license metadata, and non-English (translated abstract)
    blocks. Returns the remaining intro paragraphs joined by blank lines.
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


def pick_outline(sections: dict[str, str], title: str, abstract: str,
                 diagnostics: list | None = None) -> list[tuple[str, str]]:
    """Pick up to N_HEADERS substantive (header, snippet) pairs that frame the
    paper. See module docstring for the full filter stack.
    """
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
