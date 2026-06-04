"""Compute the WoS → topics_viz.json funnel and write funnel.json.

Mirrors the inputs of status.py and the final classify export to make explicit
where papers are lost between the WoS extract and the topic-classified corpus
that the frontend renders.

Usage:
    uv run python export_funnel.py
    uv run python export_funnel.py --topic-run 2026-05-29_1719_topic_v3_abstract_cat14_all
"""
import argparse
import json
import sys
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
OUT = ROOT / "frontend" / "src" / "lib" / "data" / "funnel.json"

DEFAULT_TOPIC_RUN = "2026-05-29_1719_topic_v3_abstract_cat14_all"


def doi_to_key(doi: str) -> str:
    return doi.replace("/", "_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-run", default=DEFAULT_TOPIC_RUN,
                    help="Classify run dir whose predictions feed topics_viz.json")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-backfill", action="store_true",
                    help="Ignore extract/input/wos_backfill.csv")
    args = ap.parse_args()

    # 1) WoS rows (with backfilled DOIs / abstracts merged in)
    wos_rows = load_wos_rows(apply_backfill=not args.no_backfill)
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

    # Per-stage drop lists for the clickable detail panel
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

    by_doi = {(r.get("DOI") or "").strip(): r for r in wos_rows
              if (r.get("DOI") or "").strip()}

    dropped_no_doi = [paper(r) for r in wos_rows if not (r.get("DOI") or "").strip()]
    dropped_no_abs = [paper(by_doi[d]) for d in sorted(wos_dois - dois_with_abs)]

    # Drop at topic_pred stage = (has abstract) − (in final).
    # Split into:
    #   (a) "not yet classified" — DOI absent from this classify run entirely
    #       (typical after a backfill that added papers post-run)
    #   (b) "classifier returned empty" — DOI present in predictions parquet
    #       but topics_pred is empty
    all_pred_dois = {d for d in preds["doi"].dropna().tolist()
                     if isinstance(d, str) and d}
    not_yet_classified = sorted(dois_with_abs - all_pred_dois)
    classifier_empty   = sorted(dois_with_abs - pred_dois - set(not_yet_classified))

    preds_by_doi = {r["doi"]: r for _, r in preds.iterrows()
                    if isinstance(r["doi"], str)}
    dropped_topic_pred = []
    for d in not_yet_classified:
        wos = by_doi.get(d)
        if wos is None:
            continue
        dropped_topic_pred.append(paper(wos, {
            "drop_reason": "not_in_classify_run",
            "topics_reasoning": None,
        }))
    for d in classifier_empty:
        wos = by_doi.get(d)
        if wos is None:
            continue
        p = preds_by_doi.get(d, {})
        reasoning = p.get("topics_reasoning") if hasattr(p, "get") else None
        dropped_topic_pred.append(paper(wos, {
            "drop_reason": "classifier_returned_empty",
            "topics_reasoning": (reasoning if isinstance(reasoning, str) else None),
        }))

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
            "dropped_papers": [],
        },
        {
            "key": "has_doi",
            "label": "Has DOI",
            "count": n_with_doi,
            "dropped": n_wos - n_with_doi,
            "reason": "WoS row has no DOI; pipeline keys everything on DOI",
            "source": "status.py",
            "dropped_papers": dropped_no_doi,
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
            "dropped_papers": dropped_no_abs,
        },
        {
            "key": "topic_pred",
            "label": "Topic prediction produced",
            "count": n_final,
            "dropped": n_with_abs - n_final,
            "reason": (
                f"{len(not_yet_classified)} not in the classify run "
                f"(typically backfilled DOIs/abstracts added after the run); "
                f"{len(classifier_empty)} classifier returned an empty topics_pred"
            ),
            "source": f"classify/output/runs/{args.topic_run}/predictions.parquet",
            "dropped_papers": dropped_topic_pred,
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
