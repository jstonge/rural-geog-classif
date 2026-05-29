# Experiments log

Reverse-chronological. Each entry: what changed + (where it lives) +
what we learned. Keep entries terse. Commit message convention:
`<task>: <short description>` — match the entry's leading title so the
log and `git log --oneline` stay aligned.

---

## Backlog (not yet tried)

Half-formed ideas; promote to a dated entry once they ship.

- **Stack ranked prompt + tightened methods cat** (`topic_v3_abstract_ranked.yaml`
  + cat_variant `02`) — does subset coverage stay at ~72% while `methods`
  over-prediction drops?
- **Extend `topic_02.csv` anti-patterns to `governance` and
  `human-environment`** (analogous to the `methods` tightening) — both are
  currently over-predicted ~2× and inflate further on ranked.
- **Walk through `built environment`** case-by-case — 16 GT papers, volatile
  F1 across runs (0.48–0.65). Likely reveals soft boundary with
  `human-environment` and `place`.
- **Walk through `human-environment`** with annotator — `topic_02.csv` has
  the right hook (anti-pattern slot); needs domain input on what to exclude.
- **Intersection/union dual-GT** when a task has 2+ annotators — score
  against both to bound the agreement question instead of picking one
  annotator's selection as canonical (see Validation section in methods.md).
- **`review_note_html` field in LS** — structured handoff for step 6 of
  the loop. Currently we just message; an in-LS field would let the
  annotator open a task and see flagged disagreements in context.
- **Multi-tier annotations** (primary / also-defensible) — costlier
  annotation move; only worth doing on the disputed cases first.

---

## 2026-05-29 — rename `place` → `place-based study` (topic_04.csv)

- Under cat03, gemma kept over-applying `place` (pred 41 → 62 even though
  GT dropped 30 → 20 from the place/scale-location split). Hypothesis:
  the *word* "place" carries a strong broad-geography prior from
  pretraining that the v3 definition couldn't override.
- **Renamed** the label to `place-based study` in `topic_04.csv` to shift
  the prior toward the single-site / case-study sense.
- **Added cross-anti-pattern** in both definitions: `place-based study`
  explicitly excludes multi-scale / cross-place comparisons (→
  `scale/location`); `scale/location` explicitly excludes single-site
  substantive subjects (→ `place-based study`).
- **LS schema** `schema.xml`: `<Choice value="place"/>` →
  `<Choice value="place-based study"/>`; pushed to project 113.
- **Migrated** 21 existing `place` annotations to `place-based study`
  via SDK PATCH (backed up first via `ls_backup.py 113`).
- **Configs** `topic_v3_abstract_cat04.yaml`, `topic_v3_abstract_ranked_cat04.yaml`.
- **Methodological observation pending:** if the rename materially lifts
  the label F1, that's evidence that *label names carry pretraining priors
  the definition can't override* — worth recording in methods.md.

## 2026-05-25 — normalize `Scale/location` → `scale/location` in LS

- Annotator's post-split review (23 papers tagged `scale/location`) used the
  Title-S casing the LS UI had at review time. After the lowercase
  `schema.xml` push, dropdown was lowercase but stored annotations weren't.
- Backed up project 113 (`ls_backup.py 113`), then PATCHed all 23
  annotations to lowercase `scale/location` via SDK. Verified 0 Title-S
  remaining. Now consistent with `topic_03.csv` and gemma's output.

## 2026-05-25 — split `place` into `place` + `scale/location` (topic_03.csv)

- **New categories** `topic_03.csv` — 17 topic labels (was 16). `place` is
  now the case-study / place-based-experience sense; `scale/location` is
  the new label covering multi-scale analysis, rural/urban continuum,
  distance, community, borders. Definitions of `human-environment`,
  `identity`, `governance`, and `methods` also refined.
- **LS schema** `schemas/prompts/v3/schema.xml` — added
  `<Choice value="scale/location"/>` under "Choose topic"; pushed to
  project 113 via SDK.
- **Annotation impact:** existing `place`-tagged annotations remain valid
  but some may be more accurately re-tagged as `scale/location` under the
  new split. Annotator should be asked to review existing `place` tags
  with the new definition in hand.
- **Pending:** new experiment config `topic_v3_abstract_cat03.yaml`
  (and `_ranked_cat03`) to test gemma against the new category list.

## 2026-05-25 — ranked topic prompt + subset coverage metric

- **New prompt** `topic_02.md` — asks for up to 5 topics, ranked primary →
  secondary → also-defensible; no `{EXAMPLES}` placeholder so examples are
  skipped when paired with this template.
- **New metric** `ann_subset_pred` — `set(gt) ⊆ set(pred)` per paper,
  averaged. Tracks how often the model covered every annotator-picked label
  regardless of extras. Added to `score.py`.
- **New categories** `topic_02.csv` — `methods` definition tightened with
  anti-pattern excluding "this method allows us to understand X" /
  "the method can be applied to other study areas" generalizability claims.
- **Configs added** `topic_v3_abstract_ranked.yaml`, `topic_v3_abstract_cat02.yaml`.
- **Result (ranked vs bare):** subset coverage **58% → 72%**, recall 0.82 →
  0.89, exact match 0.136 → 0.011 (collapses as expected — gemma adds ~1
  extra tag/paper). Over-predicted labels (`governance`, `human-environment`,
  `methods`) got inflated further on ranked, motivating the cat-tightening
  experiment.

## 2026-05-25 — out-of-sample example set for topic (4 papers from Annals)

- **New examples** `topic_claude_01.md` — 4 papers hand-picked from Annals
  out-of-sample: methods positive (Street View China), human-environment
  restraint (Appalachia labor), natural environment positive (Ohio forest
  cover), governance restraint (Kenya water suffering).
- **Config added** `topic_v3_abstract_claude_ex.yaml`.
- **Result:** marginally better than the 8-example set (`old 8 ex`) but
  still worse than bare. Targeted examples didn't move the over-predicted
  labels they were meant to fix.

## 2026-05-25 — topic prompt logging clarity

- `run.py` "with examples" log was misleading (printed even when the
  template lacked `{EXAMPLES}`). Now reports actual injection state.

## 2026-05-24 — methods.md draft + iterative-loop diagram

- Started `docs/methods.md` as a draft for the paper's Methods section.
- ASCII diagram of the 8-step refinement loop added; later expanded to
  call out **ADD CONTEXT** as a distinct lever alongside prompt / cat / examples.

## 2026-05-23 — examples for topic (original 8)

- **New examples** `topic_01.md` — 8 hand-picked papers, output keyed under
  `{"topic": [...]}` (later corrected to `{"topics": [...]}` to match the
  prompt's response schema).
- Added `{EXAMPLES}` placeholder to `topic_01.md` prompt template (it had
  no placeholder before, so examples had been silently dropped even when
  on disk).
- **Result:** **examples hurt** topic across the board. Exact match
  13.6 → 11.5, jaccard 0.579 → 0.543. Hypothesis: implicit distribution
  anchoring — examples teach label *frequency* as well as meaning, and an
  unbalanced example set distorts the prior.

## 2026-05-23 — schema casing fix (topic)

- v3 topic categories CSV had Title Case (`Social Power`) while LS schema
  used lowercase (`social power`). Gemma emitted both cases inconsistently
  and most predictions failed to join with GT.
- Fixed CSV to lowercase end-to-end. **Strict exact match 3.4% → 13.6%**
  with no model change. Any prompt-schema casing mismatch is now a
  first-thing-to-check signal.

## 2026-05-23 — multi-label /compare adaptation

- `export_compare.py` emits `labels: string[]` (full prediction list) and
  `multi_label: boolean` per bundle.
- `/compare`: when `multi_label = true`, the square confusion matrix is
  replaced by a per-label agreement table (`both / only A / only B`),
  clickable to filter records. Single-label confusion matrix path
  preserved for methods.
- `COMPARE_FORCE_SINGLE_LABEL = {"location"}` override so location, which
  is theoretically multi-label but mostly single in practice, keeps the
  confusion matrix UI.

## 2026-05-23 — multi-label scoring

- `score.py` `multi_label=True` path now emits strict `exact_match`
  (set equality), `mean_jaccard`, sample-avg `precision / recall / F1`,
  and `per_label` P/R/F1 with `support_gt` / `support_pred`.
- `validate.py` passes `multi_label` to `label_distribution` so all labels
  count (was first-element only).
- `/runs` page renders the per-label table and the four summary metrics
  whenever present.

## 2026-05-22 — auto-rebuild runs index on validate

- `validate.py` now calls `rebuild_runs_index.main()` at the end so
  `/runs` reflects the new metrics without a manual rebuild step.

## 2026-05-22 — most-recent-wins GT loader

- `load_gt_ls` was picking the *first* annotation per task (LS returns
  cheryl's older annotation first), so later annotator revisions were
  silently shadowed.
- Switched to most-recently-updated annotation as GT.
- **Re-validating all v3 snapshots after the fix** raised v3 methods
  scores significantly (some by 10+ percentage points). The old "v3
  underperforms v1" puzzle was partly a GT-quality artifact, not a
  prompt-quality one.

## 2026-05-22 — intro strategy for topic

- New strategy `intro` in `input_strategies.py` reusing the heuristic
  picker from `push_intro_to_ls.py` (factored into `lib/intro_outline.py`).
  Message body = title + abstract + first 1–3 substantive body sections.
- **Result:** intro context did **not** help topic (worse than bare). Same
  approach was decisive for methods; topic's decision boundary is
  apparently abstract-adequate in most cases.

## 2026-05-22 — push intro outlines + GitHub link to LS

- New script `push_intro_to_ls.py`: heuristic picker (no LLM) extracts
  first 1–3 substantive body sections, renders as collapsible HTML,
  pushed to LS as `intro_section_html` under the topic question.
- Filter stack: junk-header regex, body-side metadata regex
  (`To cite this article` / ISSN / license), abstract-overlap shingles,
  English-marker density (drops Spanish/Chinese translation blocks),
  affiliation pattern (single-letter superscript + institution keyword),
  stop-at-methods/results boundary.
- Title-duplicate rescue: when a paper's intro paragraphs sit under a
  repeated-title header (older PDFs, no `## Introduction`), strip the
  abstract-overlapping paragraphs from the body and use what remains.
- Each card carries a "View full text on GitHub" link to the docling
  parse.
- LS schema (`schemas/prompts/v3/schema.xml`) updated with
  `<HyperText value="$intro_section_html"/>` under "Choose topic"; pushed
  to project 113 via SDK.

## 2026-05-22 — methods sections in LS (parallel to intro)

- `push_sections_to_ls.py` writes `method_section_html` to LS task data;
  rendered under "Choose Methods" header.

## 2026-05-21 — frontend (/runs, /compare, /prompts, /annotations)

- SvelteKit dashboard. `/runs` lists every snapshot with metrics and
  per-label table; `/compare` is the labeller-side diagnostic surface
  (confusion matrix for single-label, per-label agreement table for
  multi-label, cell-click filtering, side-by-side cards with deep links).

## Earlier — v3 schema introduction

- v3 categories established for methods (7), topic (16), location (9 regions).
- LS project 113 set up under the v3 schema; v1 project 110 kept as
  reference. The v3 redesign was driven by inter-annotator disagreement
  on v1 boundaries.
