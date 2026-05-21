"""Generic classify runner. Picks the right prompt / GT / defaults from the task registry.

Usage:
    python classify/src/run.py --task methods --schema v3 --strategy abstract
    python classify/src/run.py --config classify/experiments/methods_v1_abstract.yaml

Prompt layout:
    prompts/{schema}/core/{task}_{variant}.md         — template (with {CATEGORIES} / {EXAMPLES})
    prompts/{schema}/categories/{task}_{variant}.csv  — label set (Value, Definition)
    prompts/{schema}/examples/{task}_{variant}.md     — example block (Input/Output, blank-line separated)
    prompts/shared/picker.md                          — strategy-specific (sections), schema-agnostic

Variants let you swap any of the three pieces independently. Default variant = "01".
Use --variant NN to bump all three in lockstep, or --prompt-variant / --cat-variant
/ --ex-variant to mix.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from classify import classify
from input_strategies import STRATEGIES
from lib.config import merge_yaml_into_args
from lib.snapshots import make_run_id, save_classify_snapshot
from lib.tasks import TASKS, get_task
from lib.wos import load_wos
from prompt_builder import build_prompt

PROMPTS_ROOT = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/schemas/prompts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=list(TASKS), default=None,
                    help="Which control to classify (methods / location / topic).")
    ap.add_argument("--schema", default=None,
                    help="Schema version (e.g. v1, v3). Required for tasks with versioning.")
    ap.add_argument("--variant", default=None,
                    help="Revision NN for prompt/categories/examples (default: 01). "
                         "Acts as the default for all three; per-piece overrides below.")
    ap.add_argument("--prompt-variant", default=None,
                    help="Override prompt-template revision only (else uses --variant).")
    ap.add_argument("--cat-variant", default=None,
                    help="Override categories CSV revision only (else uses --variant).")
    ap.add_argument("--ex-variant", default=None,
                    help="Override examples revision only (else uses --variant).")
    ap.add_argument("--strategy", default=None, choices=STRATEGIES,
                    help="Input strategy (default: abstract).")
    ap.add_argument("--name", default=None,
                    help="Short tag for the snapshot (default: derived from schema/variant/strategy).")
    ap.add_argument("--all-papers", action="store_true",
                    help="Classify ALL WoS papers (default: only papers with GT for this task/schema).")
    ap.add_argument("--thinking", default=None,
                    help="Override task default for thinking mode.")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="Override task default for max output tokens.")
    ap.add_argument("--config", type=Path, default=None,
                    help="YAML config; keys override CLI defaults.")
    args = ap.parse_args()
    args = merge_yaml_into_args(args, args.config, ap)

    if args.task is None:
        ap.error("--task is required (or set 'task: ...' in YAML config)")
    task = get_task(args.task)

    # --- resolve prompt / schema / examples paths ---
    if task.supports_schema and not args.schema:
        ap.error(f"task {task.name!r} requires --schema (e.g. v1, v3)")
    schema = args.schema
    base_variant   = args.variant or "01"
    prompt_variant = args.prompt_variant or base_variant
    cat_variant    = args.cat_variant or base_variant
    ex_variant     = args.ex_variant or base_variant

    schema_root   = PROMPTS_ROOT / schema if schema else PROMPTS_ROOT
    template_path = schema_root / "core" / f"{task.name}_{prompt_variant}.md"
    schema_path   = schema_root / "categories" / f"{task.name}_{cat_variant}.csv"
    examples_path = schema_root / "examples" / f"{task.name}_{ex_variant}.md"

    # --- resolve runtime knobs ---
    strategy = args.strategy or "abstract"
    if not task.supports_strategy and strategy != "abstract":
        ap.error(f"task {task.name!r} doesn't support strategy {strategy!r}")
    thinking = task.default_thinking if args.thinking is None else bool(args.thinking)
    max_tokens = args.max_tokens or task.default_max_tokens(strategy)

    # --- build prompt ---
    prompt = build_prompt(
        template_path,
        schema_path if schema_path.exists() else None,
        examples_path if examples_path.exists() else None,
    )
    has_examples = examples_path.exists() and bool(examples_path.read_text().strip())
    print(f"Prompt: {template_path.name} + cat/{schema_path.name} + ex/{examples_path.name} "
          f"({'with examples' if has_examples else 'no examples'})")

    # --- load + filter papers ---
    papers = load_wos()
    print(f"WoS: {len(papers)} papers with abstract")
    if not args.all_papers:
        gt = task.gt_loader(schema)
        before = len(papers)
        papers = papers[papers["doi"].isin(set(gt["doi"]))].reset_index(drop=True)
        print(f"Restricted to {len(papers)} annotated papers (from {before}; --all-papers to keep all)")

    # --- classify ---
    preds = classify(
        papers,
        prompt=prompt,
        response_key=task.response_key,
        strategy=strategy,
        thinking=thinking,
        max_tokens=max_tokens,
    )

    # --- snapshot ---
    default_name_parts = [p for p in (schema, base_variant, strategy) if p]
    name = args.name or "_".join(default_name_parts) or "run"
    run_id = make_run_id(task.name, name)
    config = {
        "task":             task.name,
        "schema":           schema,
        "variant":          base_variant,
        "prompt_variant":   prompt_variant,
        "cat_variant":      cat_variant,
        "ex_variant":       ex_variant,
        "strategy":         strategy,
        "prompt_template":  str(template_path),
        "schema_csv":       str(schema_path) if schema_path.exists() else None,
        "examples_path":    str(examples_path) if examples_path.exists() else None,
        "max_tokens":       max_tokens,
        "thinking":         thinking,
        "all_papers":       args.all_papers,
        "model":            "google/gemma-4-31B-it",
        "temperature":      0.0,
    }
    run_dir = save_classify_snapshot(run_id, control=task.name,
                                      config=config, prompt=prompt, predictions=preds)
    print(f"Snapshot -> {run_dir}")


if __name__ == "__main__":
    main()
