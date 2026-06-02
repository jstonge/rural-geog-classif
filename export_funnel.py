"""Compute the WoS → topics_viz.json funnel and write funnel.json.

Mirrors the inputs of status.py and the final classify export to make explicit
where papers are lost between the WoS extract and the topic-classified corpus
that the frontend renders.

Usage:
    uv run python export_funnel.py
    uv run python export_funnel.py --topic-run 2026-05-29_1719_topic_v3_abstract_cat14_all
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
WOS_CSV = ROOT / "extract" / "input" / "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
PDF_DIR = ROOT / "extract" / "output" / "pdfs"
DOCLING_DIR = ROOT / "parse" / "output" / "docling"
DOTS_DIR = ROOT / "parse" / "output" / "dots"
RUNS_DIR = ROOT / "classify" / "output" / "runs"
OUT = ROOT / "frontend" / "src" / "lib" / "data" / "funnel.json"

DEFAULT_TOPIC_RUN = "2026-05-29_1719_topic_v3_abstract_cat14_all"


def doi_to_key(doi: str) -> str:
    return doi.replace("/", "_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-run", default=DEFAULT_TOPIC_RUN,
                    help="Classify run dir whose predictions feed topics_viz.json")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    # 1) WoS rows
    with open(WOS_CSV, newline="", encoding="latin-1") as f:
        wos_rows = list(csv.DictReader(f))
    n_wos = len(wos_rows)

    wos_dois = {(r.get("DOI") or "").strip() for r in wos_rows}
    wos_dois.discard("")
    n_with_doi = len(wos_dois)

    # Has WoS abstract — this is the actual gate for the topic classifier,
    # which runs on abstracts (run id contains "_abstract_").
    dois_with_abs = {(r.get("DOI") or "").strip() for r in wos_rows
                     if (r.get("DOI") or "").strip()
                     and (r.get("Abstract") or "").strip()}
    n_with_abs = len(dois_with_abs)

    # Topic predictions (non-empty topics_pred list, joined back to WoS)
    pred_path = RUNS_DIR / args.topic_run / "predictions.parquet"
    preds = pd.read_parquet(pred_path)

    def nonempty(t):
        return isinstance(t, (list, tuple)) and len(t) > 0

    pred_nonempty = preds[preds["topics_pred"].apply(nonempty)]
    pred_dois = {d for d in pred_nonempty["doi"].tolist() if isinstance(d, str) and d}
    dois_with_pred = wos_dois & pred_dois  # final join in export_topics_viz.py
    n_final = len(dois_with_pred)

    # Parallel branch: PDF / parse coverage (feeds full-text summarization,
    # not the abstract-based topic classifier). Reported as a side note so
    # the linear funnel above isn't confused with this independent path.
    pdf_stems = {p.stem for p in PDF_DIR.glob("*.pdf")} if PDF_DIR.exists() else set()
    n_with_pdf = sum(1 for d in wos_dois if doi_to_key(d) in pdf_stems)

    docling_stems = {p.stem for p in DOCLING_DIR.glob("*.md")} if DOCLING_DIR.exists() else set()
    dots_stems = set()
    if DOTS_DIR.exists():
        dots_stems = {p.stem for p in DOTS_DIR.glob("*.md")}
        dots_stems |= {d.name for d in DOTS_DIR.iterdir()
                       if d.is_dir() and d.name != "jsonl"
                       and any(d.glob("*_page_*_nohf.md"))}
    parsed_stems = docling_stems | dots_stems
    n_parsed = sum(1 for d in wos_dois if doi_to_key(d) in parsed_stems)

    # Stages (linear funnel — each row's `count` is what enters the next stage)
    stages = [
        {
            "key": "wos_input",
            "label": "WoS input CSV",
            "count": n_wos,
            "dropped": 0,
            "reason": None,
            "source": str(WOS_CSV.relative_to(ROOT)),
        },
        {
            "key": "has_doi",
            "label": "Has DOI",
            "count": n_with_doi,
            "dropped": n_wos - n_with_doi,
            "reason": "WoS row has no DOI; pipeline keys everything on DOI",
            "source": "status.py",
        },
        {
            "key": "has_abstract",
            "label": "Has WoS abstract",
            "count": n_with_abs,
            "dropped": n_with_doi - n_with_abs,
            "reason": (
                "WoS row has no Abstract field — common for pre-2002 papers "
                "(Professional Geographer, Annals AAG, Geographical Review). "
                "The abstract-based topic classifier has no input for these."
            ),
            "source": "WoS Abstract column",
        },
        {
            "key": "topic_pred",
            "label": "Topic prediction produced",
            "count": n_final,
            "dropped": n_with_abs - n_final,
            "reason": (
                "Classifier ran but returned an empty topics_pred list "
                "(model declined to assign any topic)"
            ),
            "source": f"classify/output/runs/{args.topic_run}/predictions.parquet",
        },
    ]

    out = {
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic_run": args.topic_run,
        "stages": stages,
        "side_branch": {
            "label": "Full-text branch (parallel — feeds summarization, not the abstract classifier)",
            "with_pdf": n_with_pdf,
            "parsed": n_parsed,
            "of_total": n_with_doi,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")
    print()
    print(f"{'stage':<42} {'count':>6}  {'dropped':>8}")
    for s in stages:
        print(f"{s['label']:<42} {s['count']:>6}  {s['dropped']:>8}")


if __name__ == "__main__":
    main()
