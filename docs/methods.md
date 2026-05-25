# Methods

## Corpus

We assemble a dataset of *N* rural-geography articles from Web of Science
(1986–2025), filtered to records with English-language abstracts. PDFs are
collected where available; full-text parsing uses three parsers in parallel
(docling, olmocr, dots.ocr) and we retain whichever returns substantive
markdown.

## Annotation

A subset of 88 articles is annotated in Label Studio across three controls:

- **methods** (single-label, 7 categories: qual, quant, mixed,
  descriptive-empirical, theoretical-conceptual, spatial, unclear)
- **topic** (multi-label, 16 categories spanning agriculture/food,
  natural environment, social power, governance, identity, mobility, etc.)
- **location** (multi-label by world region, with single-region the modal case)

Most v3 records carry two or more independent annotations; when a task has
multiple annotations, the most-recently-updated annotation serves as the
ground truth, so that annotator revisions automatically propagate into
the next validation pass.

Category definitions are versioned (v1 → v3); the v3 schema tightened
boundaries in response to inter-annotator disagreement on the v1 categories.
The Label Studio labeling configuration itself is also versioned in the
repository (`schemas/prompts/v3/schema.xml`) and pushed to the project via
the LS SDK, so schema and prompt evolve in lockstep.

Two auxiliary context surfaces are pushed into Label Studio alongside the
abstract so annotators see the same extra context the model can see:

- `method_section_html` — the methodology sections picked from the docling
  parse, rendered as a collapsible block under the methods question.
- `intro_section_html` — the first 1–3 substantive body sections, rendered
  under the topic question; rescues abstract-adjacent intro paragraphs when
  the paper lacks an explicit `## Introduction` header.

Each card also carries a deep link to the rendered full-text markdown on
GitHub, so annotators can drop into the full paper without leaving LS.

## Classification

We use Gemma 4 31B served via vLLM in thinking mode. Prompts are built from
three swappable components:

- **template** — the core instruction (role, output format, decision guidelines)
- **categories** — the schema CSV injected into the `{CATEGORIES}` placeholder
- **examples** — an optional few-shot block injected into `{EXAMPLES}`

Each component is independently versioned (`--prompt-variant`, `--cat-variant`,
`--ex-variant`) so we can isolate the effect of any single change.

A second lever beyond prompt content is **how much of the paper the model
sees**. The WoS abstract is often under-specified for fine-grained
distinctions: a methods abstract may say "mixed methods" while the actual
methodology section reveals it as primarily spatial-regression; a topic
abstract may foreground policy framing while the body of the paper centers
material infrastructure. To address this we developed four **input strategies**
of increasing context:

| strategy | message body |
|---|---|
| abstract | title + WoS abstract |
| fulltext | title + first 12 K chars of docling parse |
| sections | title + abstract + methodology sections picked by a separate Gemma call |
| intro | title + abstract + first 3 substantive body headers (heuristic picker) |

The non-trivial strategies follow a three-phase pipeline:

- **Phase A — parse**: produce a docling markdown rendering of the PDF.
- **Phase B — pick**: select which section bodies to surface. For `sections`
  this is an LLM call against a dedicated picker prompt
  (`schemas/prompts/shared/picker.md`); for `intro` it is a pure-Python
  heuristic filter stack. Picker output is cached per-DOI as a parquet
  (`classify/output/picker_*_cache.parquet`) so only newly-parsed papers
  fire a fresh Phase B call.
- **Phase C — classify**: the chosen sections are concatenated with the
  title and abstract and sent through the task prompt.

Picker prompts are themselves first-class versioned artifacts under
`schemas/prompts/shared/`. The intro picker's filter stack drops boilerplate
headers, journal-name lines, sections whose body overlaps heavily with the
WoS abstract (3-shingle Jaccard), non-English paragraphs (low English-marker
density — catches embedded translated abstracts), and affiliation paragraphs
(single-letter superscript prefix + institutional keyword); it stops at the
first methods/results-style header so it never crosses into the methodology
region of the paper.

Every run is persisted as a snapshot bundle containing `config.json`,
`prompt.md`, `predictions.parquet`, `metrics.json`, and `gt.parquet`.

## Validation

For single-label tasks the ground truth is unambiguous: there is one
authoritative label per paper and disagreement is summarized by a square
confusion matrix.

For multi-label tasks the notion of "agreement" is genuinely more
complicated, and we are transparent about this. A paper's *defensible set*
of labels is typically wider than any single annotator's pick, and two
annotators (or a model and an annotator) can both make reasonable but
non-identical selections from that set. Treating one selection as the
single ground truth and measuring strict equality therefore underestimates
agreement that is meaningful in practice. We report a panel of metrics that
together characterize where, and how badly, two labellers diverge:

- **strict exact_match** — `set(pred) == set(gt)`. Useful as a floor: high
  exact match means strong consensus, but moderate exact match does not
  necessarily mean poor classification (it often means the model picked a
  defensible but different selection from the same wider set).
- **annotator ⊆ pred** — fraction of papers where the model's set contains
  every label the annotator picked, possibly plus extras. Treats the
  annotator's selection as a high-bar must-include subset of a wider
  defensible-set hypothesis.
- **Jaccard** — `|A ∩ B| / |A ∪ B|`, averaged per paper. Symmetric, gentle
  to small disagreements.
- **sample-averaged P / R / F1** — per-paper precision, recall, F1, then
  averaged across papers. Surfaces the precision/recall trade.
- **per-label P / R / F1** with `gt_n` and `pred_n` support counts.
  Localizes which labels the model systematically over- or under-predicts.
- *(planned)* **intersection vs. union ground truth** — when a paper has
  two or more independent annotations, the *intersection* gives a
  high-precision "definitely true" GT and the *union* gives a high-recall
  "defensible" GT. Scoring against both bounds the agreement question
  without committing to one annotator's selection as canonical.

Models can also be asked to **rank** their multi-label output (primary
topic first, then secondary, etc.), which lets downstream analysis
distinguish a paper's central theme from its also-defensible secondary
themes. Strict equality cannot capture this; subset coverage plus a
preserved rank order can.

## Diagnostic surfaces

A small frontend (SvelteKit) provides the surfaces against which the loop is
actually run:

- `/runs` — every snapshot with its config, prompt text, summary metrics,
  and (for multi-label tasks) the per-label P / R / F1 table.
- `/compare` — side-by-side labeller comparison. For single-label tasks it
  renders a square confusion matrix; for multi-label tasks a per-label
  agreement table (`both / only A / only B`). Cells are clickable and filter
  the records list to the matching disagreements. Each record card shows the
  abstract, picked sections, model reasoning, and deep links to both the LS
  task and the GitHub-rendered docling parse.
- `/prompts` — full prompt text per snapshot (template + injected categories
  + examples).
- `/annotations` — annotator overview.

These surfaces are what implements steps 3, 5, and 6 of the loop below in
practice; the loop is doable on raw CSVs but tractable on the dashboard.

## Iterative refinement loop

Classification is treated as a co-design loop between model behavior and
annotation quality. Per-label diagnostics surface disagreements, which we
adjudicate case by case:

```
 ┌──────────────────────────────────┐
 │ 1. annotated set (in-sample)     │
 │    88 papers in Label Studio     │
 └──────────────┬───────────────────┘
                ▼
 ┌──────────────────────────────────┐
 │ 2. baseline run                  │
 │    gemma + abstract prompt       │
 │    → metrics + per-label table   │
 └──────────────┬───────────────────┘
                ▼
 ┌──────────────────────────────────┐
 │ 3. examine discrepancies         │
 │    per-label table → click cell  │
 │    → records w/ abstract + intro │
 │       + reasoning + LS / GitHub  │
 └──────┬──────────────┬────────────┘
        ▼              ▼
 ┌─────────────────┐  ┌──────────────────-───┐
 │ 4. iterate      │  │ 5. reconsider:       │
 │    (model side) │  │    is annotator      │
 │  ─ prompt text  │  │    wrong?            │
 │  ─ cat defs     │  └──────────┬──────────-┘
 │  ─ examples     │             ▼
 │  ─ ADD CONTEXT  │  ┌─────────────────────-┐
 │    (abs → intro │  │ 6. flag for review   │
 │     → sections  │  └──────────┬────────-──┘
 │     → fulltext) │             ▼
 │                 │  ┌───────────────────-──┐
 │                 │  │ 7. annotator edits   │
 │                 │  │    GT auto-refreshes │
 │                 │  └──────────┬────────-──┘
 └──────┬──────────┘             │
        └─────────┬──────────────┘
                  ▼
 ┌──────────────────────────────────┐
 │ 8. recompute metrics             │
 │    repeat from step 3            │
 └──────────────────────────────────┘
```

1. Identify a label with poor F1 or imbalanced support (`pred ≫ gt` or
   `pred ≪ gt`).
2. Filter the comparison view to the disagreeing papers (`only annotator` or
   `only model` for that label).
3. Read each paper alongside the model's reasoning and the picked sections;
   decide whether the model is wrong, the annotator is wrong, or the category
   definition is ambiguous.
4. Apply the appropriate intervention. We choose among four classes of lever,
   roughly in order of cost:
    - **prompt content** — tighten template language, add or revise targeted
      examples (cheap; re-runs immediately).
    - **add context** — switch input strategy (abstract → intro → sections →
      fulltext) so the model sees the parts of the paper that resolve the
      ambiguity. This was decisive for the methods task, where a discipline
      like "spatial regression" is rarely identifiable from the abstract alone
      and annotators reached their final judgment only after reading the
      methodology section.
    - **revise category definitions** — when a label's boundary is itself
      unclear, revise the schema CSV (new version) and re-run. The v3 schema
      came from this move on v1. Definitions are first-class artifacts and
      can be revisited at any iteration.
    - **annotation revision** — when the disagreement reflects an annotator
      mistake (not a schema ambiguity), flag the specific task for review;
      once the annotator edits it in Label Studio the most-recent-wins
      loader picks up the change on the next validate run.
5. Re-validate. Metrics on the affected labels move; iterate.

This loop runs against the same 88-paper annotated set throughout —
the categories and prompts evolve, the corpus is fixed.

### Worked example: tightening the `methods` topic label

To illustrate the loop in action: on the bare v3 topic run the model
over-predicted the `methods` label by roughly 9× (19 predictions for only
2 ground-truth tags). Filtering the `/compare` per-label view to the
disagreement cases surfaced a recurring pattern — papers whose abstracts
ended with a generalizability claim like *"this methodological approach
allows us to understand…"* or *"the method can be applied to other study
areas at different spatial and temporal scales."* The model read these
phrasings as methodological contribution claims and tagged `methods`; the
annotator read them as boilerplate appendages to substantively domain-driven
papers and did not. Reading a single such paper alongside the model's
reasoning made the decision boundary explicit: it was not an annotator
mistake but a definition that left room for the over-broad reading.

The v3 `methods` definition was therefore revised (`topic_02.csv`) to add
an explicit anti-pattern excluding "this method allows us to understand…"
and "the method can be applied to other study areas" phrasings, with the
clarifying rule that *the paper's title and abstract should be primarily
about the method, not the substantive domain it is applied to*. The
definition change isolates the schema lever from prompt or example
changes, and the per-label F1 / support shift on the next run measures
whether the tightened boundary actually closed the gap.

## Reproducibility

All experiments are described by YAML configs under `classify/experiments/`.
Each run produces a snapshot directory named `YYYY-MM-DD_HHMM_<name>/`
containing `config.json`, `prompt.md`, `predictions.parquet`, `metrics.json`,
and `gt.parquet` — sufficient to reproduce both the predictions and the
score. Validation auto-rebuilds the `/runs` index after writing metrics,
so the dashboard reflects the latest state without a manual rebuild step.
The `/compare` view regenerates from any combination of snapshots via
`export_compare.py`.

## Empirical observations on the loop itself

Three findings from running this loop have shaped the methodology:

- **Adding context decisively helped methods but not topic.** Switching from
  abstract-only to the `sections` strategy raised v3 methods exact-match
  from ~87% to 89%. The same move on topic (via the `intro` strategy)
  produced no gain. We read this as a property of the decision boundary:
  methods classification often turns on body-only signal (the exact
  analytical technique), whereas topic identification is usually adequately
  encoded in the abstract.
- **Few-shot examples can hurt multi-label tasks.** A curated 8-example
  block for topic dropped strict exact-match from 13.6% to 11.5% and
  Jaccard from 0.579 to 0.543; a smaller, targeted 4-example block did not
  recover the gap. The mechanism appears to be implicit distribution
  anchoring — examples teach the *frequency* of each label as well as its
  meaning, and an unbalanced example set distorts the prior.
- **Prompt / schema casing must match.** An early topic run scored 3.4%
  exact-match because the categories CSV used Title Case while the LS
  schema and ground truth used lowercase; the model emitted both cases
  inconsistently and most predictions failed to join with the GT. Fixing
  the CSV to lowercase end-to-end lifted the score to 13.6% — a 10× jump
  with no model change. Any prompt-schema mismatch is now a first thing
  to check when results look pathological.
