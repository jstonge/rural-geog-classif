"""Export topics_viz.json for the / (homepage) frontend.

Emits a multi-model JSON so the homepage can let readers toggle between:
  - cat14 in its native 17-category space (the original granular run)
  - cat14 post-collapsed to the collaborators' 12-category hierarchy
    (simple deterministic mapping from cat14 predictions via topic_14.csv's
    `parent` column — no separate inference)
  - any cat15+ all-papers run, taking its predictions as-is (already in the
    collapsed 12-category space; the snapshot's own cat CSV declares which
    legacy values it absorbs).

The cat14 collapse is mechanical, not a separate model: it just re-labels
cat14's granular predictions so collaborators see the 12-category view of the
same underlying inference. This is useful as a "free" comparison against a
genuine 12-category prompt run.

Usage:
    # one model: cat14 native (back-compat with the original single-snapshot use)
    python classify/src/export_topics_viz.py 2026-05-29_1719_topic_v3_abstract_cat14_all

    # cat14 native + cat14 collapsed to 12 (two model views, same inference)
    python classify/src/export_topics_viz.py \
        2026-05-29_1719_topic_v3_abstract_cat14_all --include-cat14-collapsed

    # cat14 native + cat14 collapsed + a separately-run 12-category model
    python classify/src/export_topics_viz.py \
        2026-05-29_1719_topic_v3_abstract_cat14_all --include-cat14-collapsed \
        --new-model <cat22_all_or_cat23_all_snapshot>

Output shape:
    {
      "models": [
        {key, label, description, categories: [{value, definition}, ...]},
        ...
      ],
      "papers": [
        {doi, title, authors, pub_year, source, keywords, abstract,
         topics: {model_key: [labels], ...}},
        ...
      ]
    }
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from lib.annotations import apply_collapse_map, load_topic_collapse_map
from lib.snapshots import load_snapshot
from lib.wos import load_wos_dict_rows

OUT_JSON = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/frontend/src/lib/data/topics_viz.json")
CATEGORIES_DIR = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/schemas/prompts/v3/categories")


def _load_categories(csv_path: Path) -> list[dict]:
    """Read [{value, definition}] from a categories CSV. Tolerates extra columns
    (legacy_values, parent) — we only care about Value/Definition for the UI."""
    with open(csv_path, newline="") as f:
        return [
            {"value": row["Value"], "definition": row.get("Definition", "") or ""}
            for row in csv.DictReader(f)
        ]


def _order_categories_by_frequency(cats: list[dict], counter: Counter) -> list[dict]:
    """Re-order categories so the most-predicted ones come first. The frontend
    colour palette has more distinct hues at the start, so popular categories
    get the most distinguishable colours."""
    cats_by_value = {c["value"]: c for c in cats}
    # Sort by count desc, then alpha
    ordered = sorted(cats, key=lambda c: (-counter.get(c["value"], 0), c["value"]))
    # If any category had zero predictions, keep it but push to the end (above).
    return ordered


def _model_view(key: str, label: str, description: str, snap: dict,
                 cat_csv: Path, collapse_map: dict[str, str] | None) -> tuple[dict, dict[str, list[str]]]:
    """Build one model entry + its per-DOI topic predictions."""
    preds = snap["predictions"]
    doi_to_topics: dict[str, list[str]] = {}
    for _, r in preds.iterrows():
        doi = r["doi"]
        if not isinstance(doi, str):
            continue
        t = r.get("topics_pred")
        if not isinstance(t, list) or not t:
            continue
        labs = list(t)
        if collapse_map:
            labs = apply_collapse_map(labs, collapse_map)
        if labs:
            doi_to_topics[doi] = labs

    cats = _load_categories(cat_csv)
    if collapse_map:
        # Categories presented to the user should be the FULL collapsed taxonomy,
        # not just the renamed parents. topic_20.csv is the canonical 12-bucket
        # CSV (cat14-style minimal-merge); use it as the label source so all
        # passthrough labels (social power, identity, etc.) appear alongside
        # the renamed merged parents (physical geography, etc.).
        collapsed_csv = CATEGORIES_DIR / "topic_20.csv"
        if collapsed_csv.exists():
            cats = _load_categories(collapsed_csv)
        else:
            # Fall back: keep granular labels with the merged parents renamed
            renamed_values = sorted({collapse_map.get(c["value"], c["value"]) for c in cats})
            cats = [{"value": v, "definition": ""} for v in renamed_values]

    # Order categories by empirical frequency on this model
    counter = Counter()
    for labs in doi_to_topics.values():
        counter.update(labs)
    cats = _order_categories_by_frequency(cats, counter)

    return {
        "key":         key,
        "label":       label,
        "description": description,
        "categories":  cats,
    }, doi_to_topics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cat14_snapshot",
                    help="Cat14 all-papers snapshot (granular 17-category baseline).")
    ap.add_argument("--include-cat14-collapsed", action="store_true",
                    help="Also include a 'cat14 collapsed to 12 categories' model view, "
                         "computed by applying topic_14.csv's parent map to cat14's predictions.")
    ap.add_argument("--new-model", default=None,
                    help="Optional snapshot of a genuine 12-category model run "
                         "(cat22_all, cat23_all, etc.) to include as a third view.")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    cat14_snap = load_snapshot(args.cat14_snapshot)
    cat14_csv = Path(cat14_snap["config"]["schema_csv"])

    models: list[dict] = []
    per_model_topics: dict[str, dict[str, list[str]]] = {}

    # Always include cat14 native
    m_native, t_native = _model_view(
        key="cat14_granular",
        label="cat14 — 17 granular categories",
        description="cat14 inference; the original 17-category prompt as run on all WoS papers.",
        snap=cat14_snap,
        cat_csv=cat14_csv,
        collapse_map=None,
    )
    models.append(m_native)
    per_model_topics["cat14_granular"] = t_native

    if args.include_cat14_collapsed:
        # Apply topic_14.csv's parent map to cat14's predictions
        cmap = load_topic_collapse_map(cat14_csv)
        if not cmap:
            ap.error(f"topic_14.csv has no `parent` column — can't collapse cat14 to 12.")
        # Strip identity entries so collapse only renames the merged labels
        cmap_nontrivial = {k: v for k, v in cmap.items() if k != v}
        m_coll, t_coll = _model_view(
            key="cat14_collapsed",
            label="cat14 — 12 categories (simple mapping)",
            description=("Same cat14 inference as above, with the 5 granular labels that "
                         "fold into the collaborators' 12-category hierarchy renamed via the "
                         "parent map (recreation -> human-environment, weather / natural environment / "
                         "climate and natural hazards -> physical geography, technology / energy -> "
                         "built environment). No separate inference — just a re-labeling of the "
                         "same predictions."),
            snap=cat14_snap,
            cat_csv=cat14_csv,
            collapse_map=cmap_nontrivial,
        )
        models.append(m_coll)
        per_model_topics["cat14_collapsed"] = t_coll

    if args.new_model:
        import re
        new_snap = load_snapshot(args.new_model)
        new_csv = Path(new_snap["config"]["schema_csv"])
        # Extract experiment label (e.g. "cat22") from the snapshot directory name,
        # since the config's cat_variant only names the categories CSV — cat22 uses
        # cat_variant=20 + prompt_variant=05, so the directory name is the canonical
        # source of which experiment this snapshot belongs to.
        snap_name = new_snap["path"].name
        m = re.search(r"cat\d+(?=_all|_|$)", snap_name)
        cat_label = m.group(0) if m else (
            f"cat{new_snap['config'].get('cat_variant', '??')}"
        )
        m_new, t_new = _model_view(
            key=f"{cat_label}_new",
            label=f"{cat_label} — 12 categories (new model)",
            description=(f"Separate inference run of {cat_label} on all WoS papers, "
                         "using the collaborators' 12-category prompt directly."),
            snap=new_snap,
            cat_csv=new_csv,
            collapse_map=None,  # already in 12-bucket space
        )
        models.append(m_new)
        per_model_topics[m_new["key"]] = t_new

    # Build the per-paper payload — only include papers with at least one topic
    # in at least one model view, to keep the JSON tight.
    all_dois: set[str] = set()
    for topics in per_model_topics.values():
        all_dois.update(topics.keys())

    wos_rows = load_wos_dict_rows()
    papers = []
    for r in wos_rows:
        doi = (r.get("DOI") or "").strip()
        if not doi or doi not in all_dois:
            continue
        topics_by_model = {k: per_model_topics[k].get(doi, []) for k in per_model_topics}
        papers.append({
            "doi":       doi,
            "title":     (r.get("Article Title") or "").strip(),
            "authors":   (r.get("Authors") or "").strip(),
            "pub_year":  (r.get("Pub Year") or "").strip(),
            "source":    (r.get("Source Title") or "").strip(),
            "keywords":  (r.get("Author Keywords") or "").strip(),
            "abstract":  (r.get("Abstract") or "").strip(),
            "topics":    topics_by_model,
        })

    payload = {"models": models, "papers": papers}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {len(papers)} papers x {len(models)} model views -> {args.out}")

    # Sanity report per model
    for m in models:
        topics = per_model_topics[m["key"]]
        n_papers = sum(1 for d in all_dois if topics.get(d))
        n_instances = sum(len(v) for v in topics.values())
        print(f"\n  [{m['key']}] {m['label']}")
        print(f"    {n_papers} papers, {n_instances} topic instances, "
              f"avg {n_instances/max(n_papers,1):.2f}/paper")
        counter = Counter()
        for labs in topics.values():
            counter.update(labs)
        for cat, n in counter.most_common():
            print(f"      {cat:>30s}: {n}")


if __name__ == "__main__":
    main()
