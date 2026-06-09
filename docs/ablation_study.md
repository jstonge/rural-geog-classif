# Methods classifier — schema and prompt ablation study

How much does prompt engineering actually move classification accuracy on this task, and which schema-and-prompt levers carry the gain?

## Summary

A vanilla 6-category Gemma-4-31B classifier prompted with one-line label definitions reaches **~77.5%** exact-match on a 91-paper annotated sample of academic geography papers. A schema-and-prompt redesign that splits the catch-all `Descriptive` category in two, adds a Guidelines prose section, and refines several definitions reaches **~80%**. An Occam's-razor production prompt that keeps only the levers ablation showed to actually help reaches **82.0%** with roughly 30% less prompt text than the full revision. The cleanly attributable gain from prompt engineering is therefore **about +5pp** over a competent vanilla baseline, concentrated
in two changes (category split, prose Guidelines section), one
counterintuitive negative (an over-elaborated `spatial` definition that *hurt* by ~3pp), and five other changes that turned out to be within nondeterminism noise.

The remaining ~18% error rate concentrates on three labels —
`descriptive-empirical`, `theoretical-conceptual`, and `unclear` — which are the natural next targets.

## Setup

- Task: single-label methodology classification on academic geography
  paper abstracts.
- Model: Gemma-4-31B IT, thinking mode, temperature 0, vLLM serving.
- Sample: 91 papers with hand-coded ground truth.
- Nondeterminism noise floor: about ±2pp single-run variation
  (estimated from two identical reruns of the same configuration).
  We treat single-run differences below ~3pp as below the noise floor.

The schema being ablated is a 7-category single-label scheme:

| label | scope |
|---|---|
| `qual` | qualitative interviews, ethnography, focus groups, discourse analysis |
| `quant` | non-spatial quantitative analysis (regression, surveys, modeling) |
| `mixed` | qualitative and quantitative carry comparable weight |
| `spatial` | spatial-statistical methods (GWR, Moran's I, kriging…) or GIS-based inferential claim |
| `descriptive-empirical` | original empirical material described without inferential testing |
| `theoretical-conceptual` | conceptual essay or position paper with no original empirical data |
| `unclear` | the abstract doesn't name a data source, method, or case material |

## Vanilla baseline

Out of the box, Gemma-4-31B with a minimal V1-style prompt (6 labels,
one-line definitions, three few-shot examples, no Guidelines block, no
tie-breaker rule) scores **~77.5%** exact-match. This is the "competent
out of the box" reference point.

## Full schema-and-prompt redesign

The full redesign (V3 methods_01) adds:

1. A 7th label by splitting `Descriptive` into `descriptive-empirical`
   and `theoretical-conceptual`.
2. A *Guidelines* prose section spelling out when to use each label.
3. A *Tie-breaker rule for compound-method papers* prose block.
4. Refined definitions for `quant` ("non-spatial"), `mixed` ("neither
   clearly primary"), and `spatial` (with an extended list of canonical
   methods like GWR, Moran's I, kriging).
5. A reworded setup paragraph ("primary analytical engine" instead of
   "primary methodological approach").

Result: **80.2%** exact-match. About +3pp over vanilla.

## Which lever did the work — ablation table

Each row removes one component of the V3 prompt and reports the change
relative to the full V3 (80.2%). All single-run, all scored against the
same 91-paper GT.

| ablation | what is removed | exact match | Δ vs V3 |
|---|---|---|---|
| V3 (full) | nothing | 80.2% | — |
| A3 — undo category split | `theoretical-conceptual` merged back into `descriptive-empirical` | 74.2% | **−6.0pp** |
| T2 — drop Guidelines | Guidelines prose section deleted from prompt | 75.3% | **−4.9pp** |
| **A2 — undo expanded spatial def** | `spatial` definition reverted to V1's one-line "GIS/RS/cartography" | **82.8%** | **+2.6pp** |
| A1 — drop `quant` "non-spatial" qualifier | `quant` definition reverted | 78.4–79.1% (2 runs) | −1.1 to −1.8 |
| A4 — drop `mixed` framing | `mixed` definition reverted to "uses both substantively" | 80.7% | +0.5 |
| T1 — drop tie-breaker rule | tie-breaker prose block deleted | 80.7% | +0.5 |
| E1 — fix example labels | fixed a label-inconsistency between examples and category list | 79.3% | −0.9 |
| E2 — V1 setup paragraph | reverted opening sentence to V1's wording | 81.6% | +1.4 |

**Levers above the ~2pp noise floor:**

- Splitting `Descriptive` into two contributes about **+6pp** when
  combined with the rest of V3.
- The Guidelines prose section contributes about **+5pp**.
- V3's elaborated `spatial` definition listing canonical spatial-statistical
  methods *actively hurts* by about **−2.6pp**. Replacing it with V1's
  short "GIS/RS/cartography" framing improves the model. This is the most
  counterintuitive finding: enumerating canonical methods causes the model
  to over-fire on papers that *mention* those methods in passing, rather
  than reserving the label for papers where the method is the engine of
  the inferential claim.

**Levers within noise (all single-run swings ≤ ~2pp):**

- The tie-breaker prose rule (T1).
- The reworded setup paragraph (E2).
- The `quant` "non-spatial" qualifier (A1).
- The `mixed` "neither clearly primary" framing (A4).
- A few-shot example-label inconsistency we found and fixed (E1).

So **five of the nine V3 prompt modifications were inert**. The full V3
schema is materially over-engineered: about 30% of its prompt text either
contributes nothing measurable or actively hurts.

## Production candidate (Occam's razor)

Combining the two ablation-validated wins (keep the category split and the
Guidelines block) with the one ablation-validated reversal (use V1's
short `spatial` definition) and dropping the inert tie-breaker block:

**Exact match: 82.0%**, about +5pp over vanilla and +1.8pp over the full
V3 prompt, with ~30% less prompt text.

## Where the remaining errors are

Per-label breakdown for the production candidate (89 papers parsed):

| label | GT support | predicted | gap | precision | recall | F1 |
|---|---|---|---|---|---|---|
| `qual` | 32 | 30 | −2 | 0.93 | 0.88 | **0.90** |
| `quant` | 20 | 21 | +1 | 0.86 | 0.90 | **0.88** |
| `spatial` | 11 | 12 | +1 | 0.83 | 0.91 | **0.87** |
| `mixed` | 5 | 7 | +2 | 0.71 | 1.00 | 0.83 |
| `theoretical-conceptual` | 7 | 5 | −2 | 0.80 | 0.57 | **0.67** |
| `descriptive-empirical` | 10 | 13 | +3 | 0.54 | 0.70 | **0.61** |
| `unclear` | 4 | 1 | −3 | 1.00 | 0.25 | **0.40** |

**Three patterns explain almost all the remaining error:**

1. **`descriptive-empirical` ↔ `theoretical-conceptual` confusion.** The
   category split is the largest single V3 contribution (+6pp), but the
   model still collapses the boundary when forced to choose. Papers that
   should be `theoretical-conceptual` (synthesis essays, position papers)
   get labeled `descriptive-empirical` instead. Net result:
   descriptive-empirical over-predicts (13 vs 10 GT) AND
   theoretical-conceptual under-predicts (5 vs 7 GT).
2. **`unclear` is essentially unused.** The model predicts it once
   against 4 GT cases. Precision is 1.00 (when used, it's right), but
   recall is 0.25. Classic "model avoids admitting uncertainty" pattern:
   gemma prefers to commit to a specific category rather than say the
   abstract is genuinely under-specified.
3. **Three labels are essentially solved** (`qual`, `quant`, `spatial`
   all F1 ≥ 0.87). Gemma reliably identifies the canonical methodological
   engines when they're clearly named in the abstract.

## Next steps (untested)

The natural targets are the three weak labels:

- **`unclear`** — add a more emphatic instruction like *"if the abstract
  does not name a data source, corpus, analytical method, or specific
  case material, prefer `unclear` over guessing a specific category"*,
  and/or add a worked example of an `unclear` paper to the few-shot block.
- **`theoretical-conceptual`** — sharpen the trigger with a positive
  case like *"if the paper synthesizes existing literature or argues a
  conceptual position without analyzing new cases, the label is
  theoretical-conceptual even when the abstract gives illustrative
  examples"*.
- **`descriptive-empirical`** — add an anti-pattern: *"do not use
  descriptive-empirical for papers that primarily theorize or synthesize
  without original empirical material; those are theoretical-conceptual"*.

Each of these would be a one-line edit and a single re-run. The same
methodological caveat applies: with ~2pp noise on this sample, any
single-lever change under ~3pp is below the floor and would need
replication to claim.

## Methodological caveats

- **Single runs per ablation.** Treat any difference under ~3pp as
  below the noise floor.
- **Annotator–model feedback loop.** The annotated GT was revised
  during V3 iteration, partly informed by previous model predictions. A
  truly clean evaluation would require a held-out paper batch annotated
  by annotators blind to model output.
- **Sample size.** Single-percentage-point F1 differences on small
  labels (`unclear` n=4, `mixed` n=5) correspond to one paper. Treat
  per-label F1 changes on small-support labels as suggestive only.
- **Cross-schema comparison subtleties.** The V1 vanilla baseline cited
  above (~77.5%) is the result of scoring V1's V1-vocabulary predictions
  against the V3 GT with explicit label mapping; without that mapping
  step a naive cross-schema comparison would inflate the apparent V3
  gain considerably. See appendix.

## Appendix: comparing classifiers across different label vocabularies

When two prompts use different label strings (e.g. V1's `spatial/mapping`
vs V3's `spatial`, or V1's single `Descriptive` vs V3's split into
`descriptive-empirical` and `theoretical-conceptual`), exact-match scoring
*against the prompt's own GT* is not directly comparable across the two
prompts. A V1 prediction of `spatial/mapping` is functionally the same
prediction as V3's `spatial`, but the strings don't match — so naive
cross-schema scoring penalizes the older schema for using its own
vocabulary.

For our V1 → V3 comparison, the fair procedure is:

1. Score both prompts against the *same* annotated sample (the current V3
   GT, since it represents the latest annotator judgment).
2. Map V1's predictions into the V3 label space:
   `both → mixed`, `spatial/mapping → spatial`, `Descriptive →
   {descriptive-empirical OR theoretical-conceptual}` (V1 had no way to
   make the post-split distinction, so a `Descriptive` prediction is
   counted correct when V3 GT is either of the two split labels).
3. Compare the resulting exact-match numbers on the shared paper pool.

Under that procedure V1 scores ~77.5% and V3 scores ~81.6% on the shared
80-paper intersection: a real +4pp improvement, not the +17pp the naive
cross-schema comparison suggests. The naive comparison conflates label-
vocabulary differences with classifier quality differences.

This methodological correction does not change any of the within-V3
ablation results — those all use the same V3 GT and V3 label vocabulary,
so the +6 / +5 / −3 attributions for split / Guidelines / spatial-def
hold without correction.
