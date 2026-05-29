# Starter template — LLM-assisted coding project

A skeleton for a new project shaped like rural-geog-classif: domain
experts negotiate a codebook, an LLM applies it, disagreements feed
back into either the model side or the annotation side. Designed
around Patrick Ball's PDP (one task per top-level folder, file-path
contracts, Makefile orchestration).

Worked example assumes the Instagram + images use case discussed in
chat; the structure ports unchanged to any multi-modal content-analysis
project.

## Folder tree

```
new-project/
├── extract/                # acquire raw posts + image URLs + comments
│   ├── src/                #   fetch_ig.py, parse_export.py
│   ├── input/              #   account lists, search queries, date ranges
│   ├── hand/               #   curated training-set picks, ambiguous cases
│   └── output/             #   posts.parquet, comments.parquet, images/urls.csv
├── media/                  # image preprocessing (parallel to parse/ in old repo)
│   ├── src/                #   download.py, resize.py, ocr_overlay.py
│   ├── input/              #   (symlinked from extract/output/images/urls.csv)
│   └── output/             #   images/<post_id>.jpg, ocr/<post_id>.txt
├── annotate/               # LS push/pull, GT loader, most-recent-wins
│   ├── src/
│   │   ├── lib/labelstudio.py    # COPY from rural-geog-classif's
│   │   │                         #   classify/src/lib/labelstudio.py
│   │   │                         #   — generic, portable, no domain logic
│   │   ├── push_predictions.py   # wraps push_annotations()
│   │   ├── push_context.py       # wraps push_task_data()
│   │   ├── pull_gt.py            # wraps load_gt()
│   │   ├── backup.py             # wraps backup_project()
│   │   └── bootstrap_project.py  # wraps create_project_from_df()
│   ├── input/              #   posts + media + comment context to push
│   ├── hand/               #   reviewer notes, manual GT overrides
│   └── output/             #   gt.parquet, ls_backups/<ts>/
├── classify/               # the iterative loop
│   ├── coding/             # was 'schemas/' in old repo — see naming note
│   │   ├── scheme/
│   │   │   ├── v1/
│   │   │   │   ├── core/{task}_{NN}.md          # template w/ {CATEGORIES}/{EXAMPLES}
│   │   │   │   ├── categories/{task}_{NN}.csv   # codebook (Value, Definition)
│   │   │   │   ├── examples/{task}_{NN}.md      # few-shot Input/Output pairs
│   │   │   │   └── input_render/{task}_{NN}.md  # NEW: per-modality formatting spec
│   │   │   └── shared/picker.md                 # auxiliary content-prep prompts
│   │   ├── labelstudio_config.xml               # was schema.xml
│   │   └── migrations/v1_to_v2.json
│   ├── experiments/        # YAML configs, one per named experiment
│   ├── src/
│   │   ├── run.py
│   │   ├── classify.py
│   │   ├── prompt_builder.py
│   │   ├── input_strategies.py
│   │   ├── score.py
│   │   ├── validate.py
│   │   └── lib/
│   └── output/
│       ├── runs/<id>/      # snapshot bundles: config + prompt + preds + metrics + gt
│       └── caches/
├── active_learning/        # NEW vs old repo — rank posts for annotation queue
│   ├── src/                #   uncertainty.py, label_balance.py, queue.py
│   ├── input/              #   (symlinked from classify/output/runs/)
│   └── output/             #   next_to_annotate.parquet
├── frontend/               # SvelteKit dashboard — defer until you have something to look at
├── docs/
│   ├── methods.md
│   ├── changelog.md
│   ├── prompt_anatonomy.md
│   └── ground_truth.md
├── tests/                  # start with prompt_builder.py tests on day one
├── Makefile
├── README.md
└── pyproject.toml
```

## What's different from rural-geog-classif

Five deliberate departures, each motivated:

1. **`coding/` instead of `schemas/`.** Honors the qualitative-research
   lineage; primes readers to treat the LLM as a coder applying a
   codebook, not an oracle. See the conversation that produced this
   template for the renaming logic.
2. **`labelstudio_config.xml` instead of `schema.xml`.** Removes the
   "schema" overload at its source. The LS file is a labeling-tool
   config, not a data schema.
3. **`annotate/` as a peer task.** In the old repo annotation tooling
   is split across `classify/` and `transform/`. This was the single
   biggest stress point; splitting it out from day one avoids the
   later refactor.
4. **`media/` as a peer task** (parallel to `parse/` in the old repo)
   handles image-side preprocessing. Keep text and media preprocessing
   in different tasks so a broken image pipeline doesn't block text
   work.
5. **`active_learning/` from day one.** IG corpora are large enough
   that annotating randomly wastes annotator time. Even a trivial
   "rank by model entropy" task in week two will pay off.
6. **A fourth prompt-anatomy piece — `input_render/`.** Multi-modal
   prompts have non-trivial decisions about how to interleave
   image/caption/comments in the user message. Lift this out as a
   versioned text artifact so changes show up in snapshot diffs,
   instead of buried in `input_strategies.py` code.

## Skeleton file contents

Bare bones. Fill out as the project takes shape; the goal here is to
have *the right empty files in the right places* on day one so the
loop's habits form correctly.

### `Makefile`

```make
# Pipeline orchestration. Each target is a task's primary entrypoint.
# Inter-task contracts are file paths under <task>/output/.

.PHONY: extract media annotate classify rank all clean help

help:
	@echo "extract   — fetch raw posts + comments + image URLs"
	@echo "media     — download + preprocess images"
	@echo "annotate  — push to / pull from Label Studio"
	@echo "classify  — run the iterative classification loop"
	@echo "rank      — active-learning queue for next annotation batch"

extract:
	uv run python extract/src/fetch_ig.py

media: extract/output/images/urls.csv
	uv run python media/src/download.py
	uv run python media/src/resize.py

annotate-push:
	uv run python annotate/src/push_to_ls.py

annotate-pull:
	uv run python annotate/src/pull_from_ls.py

classify:
	uv run python classify/src/run.py --config $(CONFIG)

rank:
	uv run python active_learning/src/queue.py
```

### `pyproject.toml`

```toml
[project]
name = "ig-content-analysis"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pandas",
  "pyarrow",
  "pyyaml",
  "requests",
  "label-studio-sdk",
  # vision/LLM deps depend on serving choice
]

[tool.uv]
managed = true
```

### `README.md`

```markdown
# IG content analysis

LLM-assisted content coding of Instagram posts + comments.
See [docs/methods.md](docs/methods.md) for what this does and why.
See [docs/project_layout.md](docs/project_layout.md) once the structure
stabilizes (currently follows the rural-geog-classif starter template).

## Run

    make extract
    make media
    make annotate-push           # push a batch to Label Studio
    # ... annotators do their thing ...
    make annotate-pull           # pull GT back
    make classify CONFIG=classify/experiments/baseline.yaml
    make rank                    # see what to annotate next
```

### `docs/methods.md` (skeleton)

```markdown
# Methods

## Corpus
TODO — sourcing, time range, filtering criteria, ethics/consent notes.

## Annotation
TODO — how many posts, by whom, in what tool, with what codebook
version. Note the most-recent-wins GT loader.

## Classification
TODO — model choice (Gemma N B), serving setup, prompt anatomy
(see [prompt_anatonomy.md](prompt_anatonomy.md)).

## Validation
TODO — single-label vs multi-label metrics, exact-match,
sample-averaged P/R/F1, per-label table.

## Iterative refinement loop
TODO — ASCII diagram of the 8-step loop. Copy from rural-geog-classif
methods.md as a starting point.

## Reproducibility
TODO — snapshot bundle contents, named experiments under
classify/experiments/.
```

### `docs/changelog.md` (header only)

```markdown
# Experiments log

Reverse-chronological. Each entry: what changed + (where it lives) +
what we learned. Keep entries terse.

---

## Backlog (not yet tried)
- Baseline run on N hand-labeled posts
- Multi-modal vs caption-only A/B
- Active-learning queue vs random batch

---

## YYYY-MM-DD — first run
TODO.
```

### `docs/prompt_anatonomy.md` (skeleton)

```markdown
# Prompt anatomy

Companion to methods.md. Describes the prompt artifact the loop
mutates and the moves the file layout permits.

## Dependency graph
TODO — paste DAG once the first pipeline runs end-to-end.

## The four pieces
- core/{task}_{NN}.md — template + {CATEGORIES} + {EXAMPLES} placeholders
- categories/{task}_{NN}.csv — codebook
- examples/{task}_{NN}.md — few-shot
- input_render/{task}_{NN}.md — per-modality formatting spec (multi-modal)

## Variant axis
TODO — --prompt-variant / --cat-variant / --ex-variant / --render-variant

## The picker / content-prep prompts
TODO — if/when shared/picker.md gains a job.

## Irregularities
TODO — fill as warts appear.
```

### `docs/ground_truth.md` (one-paragraph stub)

```markdown
# What counts as "ground truth" here

The categories CSV (the codebook) is the conceptual referent, not the
per-paper annotator labels. Annotators, the LLM, and the schema-author
are three labellers in the room; any of them can be the one that needs
to update on a given disagreement. See rural-geog-classif's
ground_truth.md for the long form.
```

### `annotate/src/lib/labelstudio.py` (copy from rural-geog-classif)

Don't rewrite. Copy [`classify/src/lib/labelstudio.py`](../classify/src/lib/labelstudio.py)
from rural-geog-classif as-is — it has no domain logic, no hardcoded
keys, no project-specific paths. The module exposes:

| function | what it does |
|---|---|
| `make_client()` | LS SDK client from `.env` |
| `load_gt(project, control, *, key_field)` | most-recent-wins GT pull |
| `summarize_project(project)` | per-control + per-annotator stats |
| `backup_project(project, out_dir)` | dump project + tasks to JSON |
| `push_annotations(project, key_to_labels, control, *, user_id, ...)` | push one annotation per key |
| `remove_annotations_by_user(project, user_id)` | backout for the above |
| `push_task_data(project, key_to_updates, *, key_field)` | merge into task.data |
| `create_project_from_df(df, *, title, label_config, predictions=...)` | bulk-create + optional preds |

Pass `key_field="post_id"` (or whatever) instead of the rural-geog `"DOI"`
when calling. That's the only customization needed.

### `classify/src/prompt_builder.py` (the 20 LoC, ported)

```python
"""Build a final prompt by injecting categories + examples + input rendering
into a template. Each placeholder is optional — a template that doesn't
reference a piece simply ships without it."""
from __future__ import annotations

import csv
from pathlib import Path


def load_categories(schema_path: Path) -> list[dict]:
    with Path(schema_path).open(newline="") as f:
        return [{"value": r["Value"], "definition": r.get("Definition") or ""}
                for r in csv.DictReader(f)]


def render_categories(cats: list[dict]) -> str:
    return "\n".join(
        f"- {c['value']}: {c['definition'].strip()}" if c['definition'].strip()
        else f"- {c['value']}" for c in cats)


def build_prompt(template_path: Path,
                 schema_path: Path | None,
                 examples_path: Path | None,
                 render_path: Path | None = None) -> str:
    template = template_path.read_text()
    if "{CATEGORIES}" in template and schema_path and schema_path.exists():
        template = template.replace("{CATEGORIES}",
                                    render_categories(load_categories(schema_path)))
    if "{EXAMPLES}" in template:
        examples = examples_path.read_text().strip() if examples_path and examples_path.exists() else ""
        template = template.replace("{EXAMPLES}", examples)
    if "{INPUT_RENDER}" in template:
        render = render_path.read_text().strip() if render_path and render_path.exists() else ""
        template = template.replace("{INPUT_RENDER}", render)
    return template
```

### `classify/experiments/baseline.yaml`

```yaml
# Day-one baseline. Caption-only, no examples, fixed categories.
task: content_type
schema: v1
strategy: caption_only
name: v1_baseline
all_papers: false
thinking: true
max_tokens: 2048
```

### `classify/coding/scheme/v1/core/content_type_01.md` (template)

```markdown
You are an expert at coding Instagram posts for {content category}.

Given a post's caption{ and image when present}, identify which of the
following content types the post primarily falls into. This is a
single-label task — pick exactly one.

Categories:
{CATEGORIES}

Guidelines:
- TODO — fill in domain-specific decision rules.
- TODO — anti-patterns and edge cases.

Respond with a JSON object:
{"content_type": "<label>"}
```

### `classify/coding/scheme/v1/categories/content_type_01.csv`

```csv
Value,Definition
TODO_label_1,TODO definition
TODO_label_2,TODO definition
unclear,Use when the post is ambiguous, garbled, or contains insufficient signal.
```

## Bootstrap order

Week-by-week priorities. The order matters: each step's output is
the next step's input, and skipping early steps is what produces the
"40 snapshots, no memory" failure mode.

### Day one

1. Initialize the repo with this folder tree (empty files OK).
2. Write the **first entry in `changelog.md`** before any code runs.
   "YYYY-MM-DD — repo initialized" with the original codebook draft
   pasted in. This trains the habit.
3. Write a 5-line **`README.md`** with how to run.
4. Stub out the **codebook** in
   `classify/coding/scheme/v1/categories/{task}_01.csv` — even with 3
   TODO labels. The codebook is the conceptual referent; everything
   else is in service of it.

### Week one

5. Get **`extract/`** working end-to-end on a tiny sample (~20 posts).
6. Get **`media/`** working on the same sample.
7. Hand-annotate the sample yourself or with one domain expert
   (it's faster than spinning up LS for 20 items).
8. Get **`classify/src/run.py`** + `prompt_builder.py` running. First
   baseline result.
9. Write a `methods.md` paragraph for each section, even if 2 lines
   each. You're not writing a paper; you're capturing what's true now.

### Month one

10. **`annotate/`** with LS, real annotators, ~100 posts.
11. First real iteration of the loop: baseline → disagreements →
    decide whether to revise codebook / prompt / annotation / add
    context.
12. **`active_learning/`** queue ranking, even if just "rank by model
    output entropy."
13. Frontend `/runs` + `/compare` views — only worth building once you
    have >5 runs to compare.

## Things to defer (don't build day-one)

- **The frontend.** Build it only when raw `metrics.json` reading
  becomes the friction.
- **Multiple input strategies.** Start with one (caption_only), add a
  second only when you have an actual hypothesis that more context
  helps.
- **`prompt_anatonomy.md` and `ground_truth.md` in full.** Stubs now,
  flesh them out once the actual irregularities and ambiguities
  appear. Writing them too early produces fiction.
- **`project_layout.md`.** Write only once the structure has been
  stable for a couple of months. Premature layout docs ossify
  decisions that should still be fluid.

## The single most important habit

Write the `changelog.md` entry **before** running the experiment, not
after. Force yourself to articulate what you expect and why; then the
result either confirms or surprises you, and "surprise" is the
information-bearing signal. After-the-fact changelogs degrade into
descriptions of what happened, which is rarely what you need to
remember later.
