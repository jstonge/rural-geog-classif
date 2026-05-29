# Prompt anatomy

This doc is a companion to [`methods.md`](methods.md). Methods describes the
iterative loop in the abstract; this one describes the artifact the loop
mutates — the prompt — and the moves the file layout permits. The reason
to write it down separately is that the loop only works because the prompt
is *decomposed* into independently revisable pieces. Without the
decomposition, every revision is a copy-paste of the whole prompt and the
ablation question ("did the new examples help, or did I also change the
template?") becomes unanswerable.

Scope note: this doc stays structural — what the pieces are, how they
wire together, and the moves the layout permits. The separate epistemic
question — *what do we mean by "ground truth" in a loop where every
artifact is itself revisable?* — lives in
[`ground_truth.md`](ground_truth.md).

## Dependency graph

```
   ┌── classifier prompt pieces (per task, per schema) ──┐    ┌── picker prompt ──┐
   │   core/{task}_{NN}.md                               │    │ shared/picker.md  │
   │   categories/{task}_{NN}.csv  ──► {CATEGORIES}      │    └─────────┬─────────┘
   │   examples/{task}_{NN}.md     ──► {EXAMPLES}        │              │
   └──────────────────────┬──────────────────────────────┘              ▼
                          │ prompt_builder.py             ┌────────────────────┐
                          │                               │  PICKER LLM call   │
                          │                               │ (sections only)    │
                          ▼                               └─────────┬──────────┘
                    assembled                                       ▼
                    classifier                            picker_cache.parquet
                      prompt                                        │
                          │                                         ▼
                          │                            picked methodology sections
                          │                                         │
                          │             ┌───────────────────────────┘
                          │             ▼
                          │   user message body (per --strategy):
                          │     abstract = title + abstract
                          │     fulltext = + docling[:12k]
                          │     intro    = + heuristic outline   (lib/intro_outline.py)
                          │     sections = + picked-section bodies
                          │             │
                          └──────┬──────┘
                                 ▼
                       CLASSIFIER LLM call (per paper)
                                 │
                                 ▼
                         predictions.parquet
                                 │
                                 ▼
                           metrics.json
                      (score.py / validate.py)
```

Read top-to-bottom: each row is an artifact or step that depends on the
row above it. Two parallel subtrees on the left and right feed the same
final classifier call:

- **Left**: the three classifier-prompt pieces are merged by
  `prompt_builder.py` into one assembled prompt. This subtree fires for
  every strategy.
- **Right**: the picker prompt fires only when `--strategy sections` is chosen. Its output is cached per-DOI, then folded into the user  message body as picked-section bodies.

The four strategy branches in the middle are mutually exclusive — exactly one fires per run, set by `--strategy`. Everything below the classifier call (predictions, metrics) is the same regardless of which strategy
fed it.

## The three pieces

A *classifier* prompt is assembled at runtime from three files living in
parallel folders under `classify/schemas/prompts/{schema}/`:

| piece | folder | format | what it carries |
|---|---|---|---|
| template | `core/{task}_{NN}.md` | markdown w/ placeholders | role, output schema, decision guidelines |
| categories | `categories/{task}_{NN}.csv` | `Value, Definition` | the label set and its definitions |
| examples | `examples/{task}_{NN}.md` | `Input:` / `Output:` blocks | few-shot demonstrations |

`{schema}` is the prompt-set version (`v1`, `v3`), not the JSON output schema — overloaded vocabulary worth flagging up front. `{task}` is one of `methods` / `topic` / `location`. `{NN}` is a two-digit revision per piece;
the three pieces version independently.

The assembler is [`prompt_builder.py`](../classify/src/prompt_builder.py):
the template is loaded, `{CATEGORIES}` is replaced by a bullet-rendered version of the CSV, and `{EXAMPLES}` is replaced verbatim by the examples file. Both placeholders are optional — a template with no `{EXAMPLES}`
marker simply ships without few-shot. This is what permits the
"prompt-only" / "prompt + categories" / "prompt + categories + examples"
configurations to all share the same machinery.

A *fourth* prompt artifact, the **section picker**, lives in a separate shared folder and only fires under certain input strategies. It's treated on its own below because it doesn't share the per-task / per-variant layout of the three pieces above — it is a cross-task, single-revision prompt that *prepares* the classifier's input rather than producing the
final label.

## Composition rules and their failure modes

Three subtleties about the placeholder substitution are worth
internalizing, because all three have caused real bugs:

- **Placeholder present, file absent → blank injection, no error.** The
  prompt still renders; the model just sees an empty examples block. Useful   for `topic_v3_abstract` (no examples on purpose); dangerous if you forgot to author the file.
- **File present, placeholder absent → silently dropped.** Sat as a real bug for one iteration of the topic prompt: `topic_01.md` examples were on disk but the template had no `{EXAMPLES}` marker. The [`run.py`](../classify/src/run.py) "with examples" log line was added specifically because this failure mode is invisible at the prompt level.
- **Schema casing must match end-to-end.** `Social Power` in the CSV vs `social power` in Label Studio and the ground truth cost a 10× drop in strict exact-match (3.4% → 13.6% after the fix). The model emits whichever case the prompt teaches; mismatch with the GT join key wrecks scoring without any model-quality signal.

The single principle behind these is that the assembler is intentionally permissive — it doesn't error on missing files or absent placeholders — so the *intended* prompt and the *actual* prompt can diverge silently. The mitigation is logging at assembly time, not stricter validation: the permissiveness is what lets us mix-and-match revisions cheaply.

## The variant axis

The CLI in [`run.py`](../classify/src/run.py) exposes four version knobs:

```
--variant NN           # default for all three pieces
--prompt-variant NN    # override template only
--cat-variant NN       # override categories CSV only
--ex-variant NN        # override examples file only
```

Each knob picks the `_{NN}` suffix on its respective file. The grid this opens up is what makes the loop's "which lever?" question answerable:
because the three pieces version independently, the diff between two runs is exactly one piece, and the metric delta is attributable to that piece.

YAML experiments in [`classify/experiments/`](../classify/experiments/)
freeze a configuration as a named bundle. The bundle is the unit of
discussion in [`changelog.md`](changelog.md); the entries there are
effectively "what does this point in the grid teach us?"

## The grid we actually ran (topic task)

| experiment | template | categories | examples | what it isolates |
|---|---|---|---|---|
| `topic_v3_abstract` | `topic_01` (set output) | `topic_01` | — | baseline |
| `topic_v3_abstract_ex` | `topic_01` | `topic_01` | `topic_01` (8 in-sample) | examples effect (in-sample) |
| `topic_v3_abstract_claude_ex` | `topic_01` | `topic_01` | `topic_claude_01` (4 out-of-sample, targeted) | examples effect (targeted) |
| `topic_v3_abstract_cat02` | `topic_01` | `topic_02` (tightened `methods`) | — | category-definition effect |
| `topic_v3_abstract_ranked` | `topic_02` (ranked output) | `topic_01` | — | output-shape effect |

Each row changes exactly one piece relative to baseline. The findings
already filed in [`changelog.md`](changelog.md) — examples hurt topic;
ranked output trades exact-match for subset coverage; `cat_02` targets the
`methods` over-prediction — are only attributable *because* the rows
differ in a single piece. A monolithic prompt with all-or-nothing edits
would have left every result confounded.

## The section picker — a prompt that prepares the prompt

The `sections` input strategy is a two-call pipeline: a first LLM call
picks which methodology headers to surface, and a second LLM call (the
classifier proper) sees title + abstract + the picked section bodies.
The first call has its own prompt at
[`schemas/prompts/shared/picker.md`](../classify/schemas/prompts/shared/picker.md):

```
You are helping classify the methodology of an academic geography paper.
Given the paper's title, abstract, and the list of section headers in its full text,
identify which sections (by header name, verbatim) describe the methodology, data, study area,
research design, or analytical approach.

Respond with a JSON object: {"sections": ["<header>", ...]}
- Pick at most 4 headers, in order of priority.
...
```

A few things differentiate the picker from the three classifier pieces:

- **Cross-task, not per-task.** It lives in `shared/` because the
  picking-methodology-headers job is the same regardless of which v3
  classifier ends up consuming the result. There is no `methods_01.md`
  vs `topic_01.md` split — one file.
- **Not versioned with the NN suffix.** It's just `picker.md`. In
  practice we've revised it rarely; if we start ablating picker prompt
  changes we'll want to either bump it to `picker_{NN}.md` or keep a
  separate notes trail.
- **Cached, not recomputed.** Picker outputs are stored per-DOI in
  `classify/output/picker_cache.parquet`. Only DOIs not in the cache fire
  a fresh call — see
  [`input_strategies.py:_prepare_sections`](../classify/src/input_strategies.py).
  Editing the picker prompt requires deleting the cache to take effect on
  already-processed papers. This is a real footgun: a picker-prompt
  revision will silently no-op on cached papers.
- **Has a parallel sibling that's currently dormant.**
  [`picker_intro.md`](../classify/schemas/prompts/shared/picker_intro.md)
  was an LLM-picker version of the `intro` strategy, eventually superseded
  by the pure-Python heuristic in
  [`lib/intro_outline.py`](../classify/src/lib/intro_outline.py). The
  artifact still sits in `shared/` as a record of the alternative path —
  worth either deleting or wiring back in as an A/B against the heuristic,
  but worth knowing about either way.

Conceptually the picker is a *content-preparation prompt*: it shapes what
the classifier sees, not what the classifier decides. That makes it a
fourth lever the loop can pull — distinct from the three classifier pieces
because a picker revision changes the input distribution to every
downstream task, whereas a categories or examples revision only affects
the task whose CSV/MD was bumped.

## A further axis: input strategies

The four pieces above describe the prompt artifacts; the input strategy
chooses *which* artifacts fire and *what context they assemble*. The four
strategies (`abstract` / `intro` / `sections` / `fulltext`) are defined in
[`input_strategies.py`](../classify/src/input_strategies.py) and pulled in
via the `--strategy` flag.

The strategy is mostly-orthogonal to the classifier prompt — the same
`{prompt_variant, cat_variant, ex_variant}` triple can in principle run
against any strategy — but it is *not fully* orthogonal:

- `abstract` and `fulltext` use no auxiliary prompt; the message body is
  assembled directly.
- `sections` invokes the picker prompt as a separate LLM call before the
  classifier (the case described above).
- `intro` uses a deterministic Python heuristic
  ([`lib.intro_outline.pick_outline`](../classify/src/lib/intro_outline.py))
  instead of an LLM picker, so no auxiliary prompt fires — but the
  dormant `picker_intro.md` shows this was once an LLM-picker strategy
  and could be again.

So "ADD CONTEXT" in the loop diagram is in fact two latent moves: pick a
strategy, *and* — if that strategy is `sections` — accept that the picker
prompt is now part of the experimental surface even if no classifier
piece changed. Detailed empirical treatment of which strategy worked for
which task lives in [`methods.md`](methods.md#classification).

## When to bump what

The loop in [`methods.md`](methods.md#iterative-refinement-loop) names
four levers: prompt content, add context, revise category definitions,
annotation revision. The first and third map onto the prompt anatomy
directly. A rough heuristic for which piece to touch:

- **Template** — bump when the *task framing* is off: output schema wrong
  shape, decision guidelines too loose or contradicting themselves,
  output should rank rather than enumerate. `topic_02.md` is the canonical
  template bump (set → ranked).
- **Categories CSV** — bump when a *single label's boundary* is the
  problem: model is over- or under-firing a specific tag in a way the
  per-label P/R/F1 table localizes. The `topic_02.csv` tightening of
  `methods` (anti-pattern for "this method allows us to understand X")
  is the canonical case. The change is narrow — one row in the CSV — and
  the metric delta is read off the affected label's column.
- **Examples MD** — bump when the model needs *demonstrations* of a hard
  call, typically restraint cases (don't fire label X for boilerplate
  generalizability claims) or rare positives (do fire label X for the
  Y-shaped paper). With the caveat that on topic this lever has so far
  hurt more than helped.

The heuristic is not a contract — sometimes the right move is to bump two
pieces together (a new ranked template *and* a tightened category
definition, for instance) — but the cost of doing them as two runs
rather than one is small, and the interpretability gain is large.

## Irregularities

Places where the anatomy as described above leaks. All are honest warts
in the current state of the repo; all are worth fixing or documenting
around, not papering over:

- **`location_01.md` hardcodes its examples inline** rather than using a
  separate `examples/location_01.md` file with an `{EXAMPLES}` placeholder.
  The three-piece split is not yet universal — location predates the
  examples mechanism. Either factor the inline examples into a separate
  file (preserving substance, gaining the variant lever) or note that
  location bypasses the examples axis on purpose. Right now it's the
  former by accident.
- **The picker has no version suffix.** `picker.md` is one file, with no
  `picker_01.md` / `picker_02.md` precedent. A picker-prompt ablation
  today would have to live in `git log` rather than in the filename. Bump
  to `picker_{NN}.md` whenever the first real picker revision lands.
- **`picker_intro.md` is orphaned.** It exists in `shared/` but no input
  strategy currently reads it; the intro strategy uses the Python
  heuristic instead. Either delete or wire back in.
- **Picker cache invalidation is manual.** Editing `picker.md` doesn't
  invalidate `picker_cache.parquet`, so previously-processed papers will
  silently keep their old picks. A content hash of the picker prompt as
  part of the cache key would close this loop.
- **`{schema}` is overloaded.** In the directory layout it's a
  prompt-set version (`v3`); in talking about the JSON the model emits we
  also say "schema". The two move on different cadences. Worth a rename
  pass eventually — `promptset_version` or similar — even if it just
  surfaces in the docs first.

## What the anatomy enables, restated

The reason for the three-piece split, and for keeping the assembler
deliberately permissive, is that the loop in `methods.md` only converges
if each iteration's metric delta is attributable to a single decision.
Modular prompts make single-decision iterations cheap; monolithic prompts
collapse every revision into "the new prompt did/didn't help" with no way
to apportion credit. The anatomy is not aesthetics — it's the precondition
for the loop being a loop rather than a sequence of correlated guesses.
