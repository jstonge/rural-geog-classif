"""Compute the WoS → topics_viz.json funnel and write funnel.json.

Shows where papers are lost between the WoS extract and the topic-classified
corpus, AND where backfill recovered them. For each stage:
  - `count`     papers entering the next stage (after backfill)
  - `would_drop` papers that would fail this stage's gate using raw WoS data
  - `added`     papers that pass this stage's gate only because of backfill
  - `dropped`   residual = would_drop - added (genuinely lost)

Usage:
    uv run python export_funnel.py
    uv run python export_funnel.py --topic-run 2026-05-29_1719_topic_v3_abstract_cat14_all
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from extract.src.load_wos import load_wos_rows, WOS_CSV  # noqa: E402

PDF_DIR = ROOT / "extract" / "output" / "pdfs"
DOCLING_DIR = ROOT / "parse" / "output" / "docling"
DOTS_DIR = ROOT / "parse" / "output" / "dots"
RUNS_DIR = ROOT / "classify" / "output" / "runs"
BACKFILL_CSV = ROOT / "extract" / "input" / "wos_backfill.csv"
OUT = ROOT / "frontend" / "src" / "lib" / "data" / "funnel.json"

TOPIC_RUN_GLOB = "*_topic_v3_abstract_cat14_all"


def latest_topic_run() -> str:
    """Most recent cat14_all topic snapshot — the one feeding topics_viz.json.

    Run dir names start with a `YYYY-MM-DD_HHMM` timestamp, so lexicographic
    sort is chronological.
    """
    matches = sorted(d.name for d in RUNS_DIR.glob(TOPIC_RUN_GLOB) if d.is_dir())
    if not matches:
        raise FileNotFoundError(
            f"no cat14_all snapshot under {RUNS_DIR} matching {TOPIC_RUN_GLOB!r}"
        )
    return matches[-1]


def doi_to_key(doi: str) -> str:
    return doi.replace("/", "_")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def read_backfill_sources():
    """Return (doi_sources_by_title_year, abs_sources_by_doi) from the backfill CSV.

    doi_sources_by_title_year: {(norm_title, year): source_string}
    abs_sources_by_doi:        {doi: source_string}
    """
    doi_src: dict[tuple[str, str], str] = {}
    abs_src: dict[str, str] = {}
    if not BACKFILL_CSV.exists():
        return doi_src, abs_src
    with open(BACKFILL_CSV, encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    for r in csv.DictReader(lines):
        src = (r.get("source") or "").strip()
        if (r.get("match_title") or "").strip() and (r.get("doi") or "").strip():
            key = (_norm(r["match_title"]), (r.get("match_year") or "").strip())
            doi_src[key] = src
        if (r.get("match_doi") or "").strip() and (r.get("abstract") or "").strip():
            abs_src[r["match_doi"].strip()] = src
    return doi_src, abs_src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-run", default=None,
                    help=("Classify run dir whose predictions feed topics_viz.json. "
                          "Defaults to the most recent cat14_all snapshot."))
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-backfill", action="store_true",
                    help="Ignore extract/input/wos_backfill.csv")
    args = ap.parse_args()

    if args.topic_run is None:
        args.topic_run = latest_topic_run()
        print(f"Using latest cat14_all snapshot: {args.topic_run}")

    # Load WoS twice — raw (no backfill) and with backfill — so we can compute
    # at each stage both the natural drop and the backfill recovery.
    rows_raw = load_wos_rows(apply_backfill=False)
    rows_bf  = load_wos_rows(apply_backfill=not args.no_backfill)
    assert len(rows_raw) == len(rows_bf), "row order must match"
    n_wos = len(rows_bf)

    doi_sources, abs_sources = read_backfill_sources()

    def paper(r, extra: dict | None = None) -> dict:
        out = {
            "doi":      (r.get("DOI") or "").strip() or None,
            "title":    (r.get("Article Title") or "").strip(),
            "pub_year": (r.get("Pub Year") or "").strip(),
            "source":   (r.get("Source Title") or "").strip(),
        }
        if extra:
            out.update(extra)
        return out

    # Per-row: was DOI/Abstract supplied by backfill?
    bf_doi_idx: list[int] = []   # row indices where backfill supplied a DOI
    bf_abs_idx: list[int] = []   # row indices where backfill supplied an Abstract
    for i, (raw, bf) in enumerate(zip(rows_raw, rows_bf)):
        raw_doi = (raw.get("DOI") or "").strip()
        bf_doi  = (bf.get("DOI") or "").strip()
        if not raw_doi and bf_doi:
            bf_doi_idx.append(i)
        raw_abs = (raw.get("Abstract") or "").strip()
        bf_abs  = (bf.get("Abstract") or "").strip()
        if bf_doi and not raw_abs and bf_abs:
            bf_abs_idx.append(i)

    # ===== Stage: Has DOI =====
    no_doi_residual = [i for i in range(n_wos)
                       if not (rows_bf[i].get("DOI") or "").strip()]
    n_has_doi = n_wos - len(no_doi_residual)
    would_drop_doi = sum(1 for r in rows_raw if not (r.get("DOI") or "").strip())
    added_doi = len(bf_doi_idx)
    added_doi_papers = []
    doi_src_counts: Counter = Counter()
    for i in bf_doi_idx:
        bf_row = rows_bf[i]
        raw_row = rows_raw[i]
        src = doi_sources.get((_norm(raw_row.get("Article Title") or ""),
                               (raw_row.get("Pub Year") or "").strip()),
                              "unknown")
        doi_src_counts[src] += 1
        added_doi_papers.append(paper(bf_row, {"backfill_source": src}))

    # ===== Stage: Has WoS abstract =====
    # Only consider rows that already have a DOI (= passed previous gate)
    pass_doi_idx = [i for i in range(n_wos) if (rows_bf[i].get("DOI") or "").strip()]
    no_abs_residual = [i for i in pass_doi_idx
                       if not (rows_bf[i].get("Abstract") or "").strip()]
    n_has_abs = len(pass_doi_idx) - len(no_abs_residual)
    # would_drop = rows that pass the DOI gate (with backfill) but raw WoS
    # would not have given them an abstract
    would_drop_abs = sum(1 for i in pass_doi_idx
                         if not (rows_raw[i].get("Abstract") or "").strip())
    added_abs = len(bf_abs_idx)
    added_abs_papers = []
    abs_src_counts: Counter = Counter()
    for i in bf_abs_idx:
        bf_row = rows_bf[i]
        doi = (bf_row.get("DOI") or "").strip()
        src = abs_sources.get(doi, "unknown")
        abs_src_counts[src] += 1
        added_abs_papers.append(paper(bf_row, {"backfill_source": src}))

    dropped_no_doi_papers = [paper(rows_bf[i]) for i in no_doi_residual]
    dropped_no_abs_papers = [paper(rows_bf[i]) for i in no_abs_residual]

    # ===== Stage: Topic prediction =====
    pred_path = RUNS_DIR / args.topic_run / "predictions.parquet"
    preds = pd.read_parquet(pred_path)

    def nonempty(t):
        return isinstance(t, (list, tuple)) and len(t) > 0

    pred_nonempty = preds[preds["topics_pred"].apply(nonempty)]
    pred_dois = {d for d in pred_nonempty["doi"].tolist()
                 if isinstance(d, str) and d}
    all_pred_dois = {d for d in preds["doi"].dropna().tolist()
                     if isinstance(d, str) and d}

    # DOIs that survive into this stage (have DOI + abstract after backfill)
    dois_with_abs = {(rows_bf[i].get("DOI") or "").strip()
                     for i in pass_doi_idx
                     if (rows_bf[i].get("Abstract") or "").strip()}
    dois_with_pred = dois_with_abs & pred_dois
    n_final = len(dois_with_pred)

    not_yet_classified = sorted(dois_with_abs - all_pred_dois)
    classifier_empty   = sorted(dois_with_abs - pred_dois - set(not_yet_classified))

    by_doi = {(r.get("DOI") or "").strip(): r for r in rows_bf
              if (r.get("DOI") or "").strip()}
    preds_by_doi = {r["doi"]: r for _, r in preds.iterrows()
                    if isinstance(r["doi"], str)}

    dropped_topic_pred = []
    for d in not_yet_classified:
        if d in by_doi:
            dropped_topic_pred.append(paper(by_doi[d], {
                "drop_reason": "not_in_classify_run",
                "topics_reasoning": None,
            }))
    for d in classifier_empty:
        if d in by_doi:
            p = preds_by_doi.get(d, {})
            reasoning = p.get("topics_reasoning") if hasattr(p, "get") else None
            dropped_topic_pred.append(paper(by_doi[d], {
                "drop_reason": "classifier_returned_empty",
                "topics_reasoning": (reasoning if isinstance(reasoning, str) else None),
            }))

    # ===== Side branch: PDF / parse coverage =====
    pdf_stems = {p.stem for p in PDF_DIR.glob("*.pdf")} if PDF_DIR.exists() else set()
    n_with_pdf = sum(1 for r in rows_bf
                     if (d := (r.get("DOI") or "").strip())
                     and doi_to_key(d) in pdf_stems)
    docling_stems = {p.stem for p in DOCLING_DIR.glob("*.md")} if DOCLING_DIR.exists() else set()
    dots_stems = set()
    if DOTS_DIR.exists():
        dots_stems = {p.stem for p in DOTS_DIR.glob("*.md")}
        dots_stems |= {d.name for d in DOTS_DIR.iterdir()
                       if d.is_dir() and d.name != "jsonl"
                       and any(d.glob("*_page_*_nohf.md"))}
    parsed_stems = docling_stems | dots_stems
    n_parsed = sum(1 for r in rows_bf
                   if (d := (r.get("DOI") or "").strip())
                   and doi_to_key(d) in parsed_stems)

    stages = [
        {
            "key": "wos_input",
            "label": "WoS input CSV",
            "count": n_wos,
            "would_drop": 0,
            "added": 0,
            "dropped": 0,
            "drop_reason": None,
            "add_reason": None,
            "add_sources": {},
            "source": str(WOS_CSV.relative_to(ROOT)),
            "dropped_papers": [],
            "added_papers": [],
        },
        {
            "key": "has_doi",
            "label": "Has DOI",
            "count": n_has_doi,
            "would_drop": would_drop_doi,
            "added": added_doi,
            "dropped": would_drop_doi - added_doi,
            "drop_reason": "WoS row has no DOI; pipeline keys everything on DOI",
            "add_reason": ("Recovered via OpenAlex title search backfill"
                           if added_doi else None),
            "add_sources": dict(doi_src_counts),
            "source": "status.py",
            "dropped_papers": dropped_no_doi_papers,
            "added_papers": added_doi_papers,
        },
        {
            "key": "has_abstract",
            "label": "Has WoS abstract",
            "count": n_has_abs,
            "would_drop": would_drop_abs,
            "added": added_abs,
            "dropped": would_drop_abs - added_abs,
            "drop_reason": ("WoS row has no Abstract field — common for "
                            "pre-2002 papers (Professional Geographer, "
                            "Annals AAG, Geographical Review)"),
            "add_reason": ("Recovered via OpenAlex abstract_inverted_index "
                           "or manual transcription from parsed PDF"
                           if added_abs else None),
            "add_sources": dict(abs_src_counts),
            "source": "WoS Abstract column",
            "dropped_papers": dropped_no_abs_papers,
            "added_papers": added_abs_papers,
        },
        {
            "key": "topic_pred",
            "label": "Topic prediction produced",
            "count": n_final,
            "would_drop": len(dois_with_abs) - n_final,
            "added": 0,
            "dropped": len(dois_with_abs) - n_final,
            "drop_reason": (
                f"{len(not_yet_classified)} not in the classify run "
                f"(typically backfilled DOIs/abstracts added after the run); "
                f"{len(classifier_empty)} classifier returned an empty topics_pred"
            ),
            "add_reason": None,
            "add_sources": {},
            "source": f"classify/output/runs/{args.topic_run}/predictions.parquet",
            "dropped_papers": dropped_topic_pred,
            "added_papers": [],
        },
    ]

    out = {
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic_run": args.topic_run,
        "stages": stages,
        "side_branch": {
            "label": ("Full-text branch (parallel — feeds summarization, "
                      "not the abstract classifier)"),
            "with_pdf": n_with_pdf,
            "parsed": n_parsed,
            "of_total": n_has_doi,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}\n")
    print(f"{'stage':<42} {'count':>6}  {'wouldDrop':>10} "
          f"{'added':>6}  {'dropped':>8}")
    for s in stages:
        print(f"{s['label']:<42} {s['count']:>6}  {s['would_drop']:>10} "
              f"{s['added']:>6}  {s['dropped']:>8}")


if __name__ == "__main__":
    main()
