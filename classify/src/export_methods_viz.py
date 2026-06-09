"""Export methods_viz.json for the / (homepage) frontend.

Emits a multi-model JSON so the homepage can let readers toggle between
classifier configurations — e.g. the historical sections-strategy run vs
the ablation-pruned production-abstract run.

The shape mirrors the topics-side export (export_topics_viz.py):

    {
      "models": [
        {key, label, description, categories: [{value, definition}, ...]},
        ...
      ],
      "papers": [
        {doi, title, authors, pub_year, source, keywords, abstract,
         methods: {model_key: <label>, ...}},
        ...
      ]
    }

Each entry in `methods` is a single label string (methods is single-label,
unlike topics which is multi-label).

Usage:
    # one model (back-compat with single-snapshot use)
    python classify/src/export_methods_viz.py 2026-05-20_1458_methods_v3_sections_full

    # baseline + production
    python classify/src/export_methods_viz.py \\
        2026-05-20_1458_methods_v3_sections_full \\
        --new-model <production_all_snapshot>
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from lib.snapshots import load_snapshot
from lib.wos import load_wos_dict_rows

OUT_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/methods_viz.json")
CATEGORIES_DIR = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/schemas/prompts/v3/categories")


def _first(x):
    return x[0] if isinstance(x, list) and x else None


def _load_categories(csv_path: Path) -> list[dict]:
    """Read [{value, definition}] from a categories CSV."""
    with open(csv_path, newline="") as f:
        return [
            {"value": row["Value"], "definition": row.get("Definition", "") or ""}
            for row in csv.DictReader(f)
        ]


def _order_by_frequency(cats: list[dict], counter: Counter) -> list[dict]:
    """Most-predicted categories first (better palette assignment downstream)."""
    return sorted(cats, key=lambda c: (-counter.get(c["value"], 0), c["value"]))


def _model_view(key: str, label: str, description: str, snap: dict) -> tuple[dict, dict[str, str]]:
    preds = snap["predictions"]
    doi_to_method: dict[str, str] = {}
    for _, r in preds.iterrows():
        doi = r["doi"]
        if not isinstance(doi, str):
            continue
        m = _first(r.get("method_pred"))
        if m:
            doi_to_method[doi] = m

    cat_csv = Path(snap["config"]["schema_csv"])
    cats = _load_categories(cat_csv) if cat_csv.exists() else []
    counter = Counter(doi_to_method.values())
    cats = _order_by_frequency(cats, counter)

    return {
        "key":         key,
        "label":       label,
        "description": description,
        "categories":  cats,
    }, doi_to_method


def _label_from_snap(snap: dict, fallback_key: str) -> tuple[str, str]:
    """Build a key + display label from a snapshot's name/config."""
    snap_name = snap["path"].name
    # Snapshot dir name carries the experiment name after the timestamp.
    m = re.match(r"\d{4}-\d{2}-\d{2}_\d{4}_(.+)", snap_name)
    label = m.group(1) if m else snap_name
    return fallback_key, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline_snapshot",
                    help="Methods snapshot for the baseline model view (typically the sections_full all-papers run).")
    ap.add_argument("--baseline-label", default="sections-strategy (historical)",
                    help="Display label for the baseline model view.")
    ap.add_argument("--baseline-description",
                    default="Methods classifier run with sections (full-text) input strategy on all WoS papers.",
                    help="Description shown under the model selector.")
    ap.add_argument("--new-model", default=None,
                    help="Optional second snapshot (typically the production-abstract all-papers run).")
    ap.add_argument("--new-model-label", default="abstract-strategy production (Occam's razor)",
                    help="Display label for the second model view.")
    ap.add_argument("--new-model-description",
                    default="Ablation-pruned production prompt running on abstracts only; 82% exact-match on the 91-paper annotated sample.",
                    help="Description for the second model view.")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    models: list[dict] = []
    per_model_method: dict[str, dict[str, str]] = {}

    baseline_snap = load_snapshot(args.baseline_snapshot)
    m_base, t_base = _model_view(
        key="sections_baseline",
        label=args.baseline_label,
        description=args.baseline_description,
        snap=baseline_snap,
    )
    models.append(m_base)
    per_model_method["sections_baseline"] = t_base

    if args.new_model:
        new_snap = load_snapshot(args.new_model)
        m_new, t_new = _model_view(
            key="abstract_production",
            label=args.new_model_label,
            description=args.new_model_description,
            snap=new_snap,
        )
        models.append(m_new)
        per_model_method["abstract_production"] = t_new

    # Union of DOIs across all models
    all_dois: set[str] = set()
    for tbl in per_model_method.values():
        all_dois.update(tbl.keys())

    wos_rows = load_wos_dict_rows()
    papers = []
    for r in wos_rows:
        doi = (r.get("DOI") or "").strip()
        if not doi or doi not in all_dois:
            continue
        methods_by_model = {k: per_model_method[k].get(doi) for k in per_model_method}
        # Drop the paper if it has no prediction in any model
        if not any(methods_by_model.values()):
            continue
        papers.append({
            "doi":       doi,
            "title":     (r.get("Article Title") or "").strip(),
            "authors":   (r.get("Authors") or "").strip(),
            "pub_year":  (r.get("Pub Year") or "").strip(),
            "source":    (r.get("Source Title") or "").strip(),
            "keywords":  (r.get("Author Keywords") or "").strip(),
            "abstract":  (r.get("Abstract") or "").strip(),
            "methods":   methods_by_model,
        })

    payload = {"models": models, "papers": papers}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {len(papers)} papers x {len(models)} model views -> {args.out}")
    for m in models:
        n = sum(1 for p in papers if p["methods"].get(m["key"]))
        by_label = Counter(p["methods"].get(m["key"]) for p in papers if p["methods"].get(m["key"]))
        print(f"\n  [{m['key']}] {m['label']}: {n} papers")
        for cat, count in by_label.most_common():
            print(f"      {cat:>25s}: {count}")


if __name__ == "__main__":
    main()
