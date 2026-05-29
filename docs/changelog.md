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

## 2026-05-29 — narrow tie-breaker for methods topic (topic_14.csv)

- Under cat13, methods F1=0.00 (gt=2, pred=6, zero overlap). Comparison
  of gemma's reasoning across runs surfaced a pattern: ranked cat06 caught
  both GT papers (F1=0.31) by reading the methodological framing as central;
  cat10-13 read the substantive findings as central and skipped them. The
  cat10 anti-pattern was correctly filtering generalizability-boilerplate
  cases (Spain Life-Stage's "method can be applied to other study areas")
  but also filtering legitimate methods papers whose title foregrounds the
  method ("Mapping Australia Using Nighttime Satellite Imagery", "An
  Agent-Based Experiment", "A Hybrid Human-Machine Approach").
- **`topic_14.csv`** adds the same narrow-tie-breaker shape that worked
  for cat13's place-based study: a specific trigger (title-level
  foregrounding of the method as a named approach AND abstract-level
  evaluation of method properties — comparing alternative measures,
  examining parameter effects, proposing a framework as the contribution)
  with explicit negative examples ("we use regression to analyze",
  "using GIS to map" do NOT qualify).
- Tests whether the cat13 pattern generalizes: same narrow-trigger shape
  can recover under-tightening on a different label without leak.
- **Config** `topic_v3_abstract_cat14.yaml`.

## 2026-05-29 — place-based study tie-breaker (topic_12.csv)

- cat11 with abstract only kept place-based study at F1=0.44 (pred=12, gt=20),
  while cat11 with intro strategy lifted it to F1=0.51 (pred=19).
- Walk-through of gemma's abstract-only reasoning showed the cat11 def is
  causing gemma to ask the right boundary question ("substantive subject
  vs empirical setting?") — but the abstract genuinely lacks the signal
  to answer on borderline cases. The body resolves it; the abstract
  doesn't.
- **`topic_12.csv`** adds a tie-breaker clause specifically for place-based
  study: when an abstract names a specific community, village, region,
  ethnic group, or diasporic population AND analyzes that group's specific
  experiences/dynamics/trajectory, default to INCLUDING the label even
  without unambiguous "subject" signal. Other labels unchanged.
- Tests whether a prose-level inclusivity rule can substitute for body
  context on a single targeted label without paying the per-label cost
  intro context did on emotion/technology/CNH.
- **Config** `topic_v3_abstract_cat12.yaml`.

## 2026-05-29 — expand built environment definition (topic_11.csv)

- Under cat10, built environment was severely under-predicted (gt=22,
  pred=12, F1≈0.55). Walk-through of 11 annotator-only papers showed the
  annotator reads the label broadly — settler irrigation systems, rural
  electrification, plumbing, drainage stream alterations, urban gentrification,
  damaged housing — including cases where infrastructure is the medium
  through which other arguments (race, governance, social power) are made,
  not the headline topic. Gemma reads "the built object must be the central
  subject" strictly and skips these.
- This is the identity-cat07-expansion problem in reverse: a label
  whose pretraining prior is narrower than the annotator's working
  definition.
- **`topic_11.csv`** expands built environment with: positive-case lists
  for infrastructure systems (water/irrigation, electrical/energy,
  transportation, housing); positive-pattern phrasings ("irrigation
  systems", "electrification", "drinking water systems"); and an explicit
  "NOT mutually exclusive" clause with human-environment, social power,
  and governance — infrastructure mediates society-environment relations,
  drives inequality, and gets regulated.
- All prior wins preserved.
- **Config** `topic_v3_abstract_cat11.yaml`.

## 2026-05-29 — tighten agriculture/food + human-environment (topic_10.csv)

- Under cat09, both labels remained over-predicted ~2× with the same root
  cause: gemma keyword-matches vocabulary adjacent to but not central to
  the analytical contribution.
- **`agriculture/food`** patterns: (1) land-use / agrarian-law / land-reform
  as backdrop; (2) "rural" + farming mention; (3) ag-as-data-source for
  non-ag studies (Mozambique trade inequality); (4) title bait (Brazil
  Quilombolas "Nature, Agriculture").
- **`human-environment`** patterns: (1) climate/hazard impacts on humans as
  description rather than theory; (2) water access/infrastructure papers
  (usually built-env + social-power); (3) land-use change as setting;
  (4) "rural environment" / "natural setting" co-occurrence.
- **`topic_10.csv`** applies the composable playbook to both: positive
  cases, anti-pattern phrasings, transferability tests, "be selective"
  framing. ag/food transferability: "Could the paper transfer to mining,
  fisheries, tourism without losing its contribution?" H-E transferability:
  "Is the argument framed as nature-society theory or analogous?".
- All prior wins preserved (cat06 place-based softening, cat07 identity
  expansion, cat08 scale/location, cat09 governance, earlier methods).
- **Config** `topic_v3_abstract_cat10.yaml` (bare only, per current focus).
- **Expectation**: diminishing returns. Both target labels' F1 should
  improve modestly; overall headline F1 may move ±0.02.

## 2026-05-29 — tighten governance anti-pattern (topic_09.csv)

- Under cat08, governance was still over-predicted (gt=30, bare pred=38,
  ranked pred=54). Walk-through of the 12 bare over-predictions surfaced
  five lexical patterns gemma keys on: (1) "development / intervention /
  empowerment" framing; (2) institutional vocabulary as backdrop;
  (3) land/property/resource themes; (4) "sustainable development"
  framing; (5) policy-implications closers. None of these 12 papers
  centrally analyze political institutions, policy design, or collective
  action.
- **`topic_09.csv`** applies the same composable playbook to governance:
  positive cases (policy *as object of analysis*, social movements
  analyzed as collective action, conservation governance arrangements);
  five-class anti-pattern phrasings list; transferability test
  ("Could the paper transfer to a private-sector or self-organized
  analog with no state, no policy?"); "be selective" framing.
- cat07 identity expansion and cat08 scale/location tightening preserved.
- **Configs** `topic_v3_abstract_cat09.yaml`, `topic_v3_abstract_ranked_cat09.yaml`.

## 2026-05-29 — tighten scale/location anti-pattern (topic_08.csv)

- Under cat07, scale/location was still over-predicted (gt=23, bare
  pred=43, ranked pred=56). Reasoning excerpts from gemma showed it was
  keyword-matching on geographic vocabulary ("spatial", "scale",
  "rural/urban", "geographic", "different country contexts") and tagging
  scale/location for any paper that used such words descriptively.
- Walk-through showed three failure patterns: (a) papers about a
  non-geographic phenomenon where geography describes variation
  ("globalized rural crime", "voter power varies by state"); (b) papers
  whose contribution is the *system* causing the spatial asymmetry, not
  the geography itself (Electoral College); (c) methodological framings
  like "data aggregated at multiple scales" without an analytical-scale
  contribution.
- **`topic_08.csv`** applies the same playbook that worked for
  place-based study in cat06: explicit positive cases (rural-urban
  gradient as theoretical contribution, MAUP studies, cross-scale
  dynamics, distance-as-explanatory-variable); anti-pattern phrasings
  list; transferability test ("could the argument transfer to a temporal
  change, a hierarchical level, a demographic comparison?"); "be
  selective" framing rather than "do NOT".
- Identity expansion from cat07 is preserved.
- **Configs** `topic_v3_abstract_cat08.yaml`, `topic_v3_abstract_ranked_cat08.yaml`.
- **Expected dynamic**: over-correction first (cat05 → cat06 pattern). If
  scale/location pred drops below ~20, follow up with cat09 soften.

## 2026-05-29 — expand identity definition (topic_07.csv)

- Under cat06, identity was under-predicted (bare pred=28 vs gt=42; recall
  ≈ 0.67). Walk-through of the 14 misses showed 12 had `social power` in
  gemma's prediction set: gemma was reading group-experience-as-identity
  as just inequality, treating the two labels as mutually exclusive.
- The annotator's expansion of identity GT (28 → 42 in topic_03/04
  reviews) included implicit identity in group labels — peasants, hukou
  holders, "rural America" as belonging, vegetal-geography subaltern
  groups, post-Soviet Ukrainians. Gemma's prompt def listed explicit
  categories (gender, race, class) but didn't cover these implicit cases.
- **`topic_07.csv`** expands the identity definition with five new
  positive-case groups (demographic; economic/occupational; politico-
  legal status; class-based; rural-as-identity), positive-pattern
  phrasings, and an explicit note that identity and social power are
  NOT mutually exclusive.
- **Configs** `topic_v3_abstract_cat07.yaml`, `topic_v3_abstract_ranked_cat07.yaml`.

## 2026-05-29 — soften place-based study anti-pattern (topic_06.csv)

- cat05 over-corrected: `place-based study` pred dropped from 35 → 3
  (bare) and 39 → 3 (ranked) for gt=20. Anti-pattern was too aggressive
  ("CRITICAL ANTI-PATTERN" caps + "do NOT tag" + 5-phrasings list +
  transferability test all in one definition).
- **`topic_06.csv`** softens the language: "be selective" instead of "do
  NOT tag", keeps a single representative anti-phrasing, drops the
  transferability test, ends on positive framing ("Tag … when the analysis
  depends on the specifics of that location"). `scale/location` also
  loosened so it stops absorbing displaced cases.
- Hypothesis: cat05's overall metric gains (best F1 of any topic run) were
  partly collateral from the prose discipline. cat06 should preserve that
  while restoring `place-based study` to gt-comparable support (target
  pred ~ 20-25).
- **Configs** `topic_v3_abstract_cat06.yaml`, `topic_v3_abstract_ranked_cat06.yaml`.

## 2026-05-29 — tightened `place-based study` anti-pattern (topic_05.csv)

- Cat04 still over-predicted `place-based study` (35 pred vs 20 gt). Walk-
  through of the 15 extras showed gemma was triggering on any named
  location in the abstract, regardless of whether the location was the
  substantive subject or just the empirical setting (Suhum District Ghana
  / health access, Colorado River Basin / resource scarcity, West Virginia
  / flood resilience, Mt. Pleasant SC / sweetgrass, etc.).
- **New `topic_05.csv`** strengthens the place-based study def with:
  positive-case list (place-attachment, ethnography of a single community,
  sense-of-place); explicit "named location ≠ tag" anti-pattern; anti-
  pattern phrasings (*'we use the case of X to explore Y'*, *'a study of
  [phenomenon] in [country]'*, *'this article examines [phenomenon] in
  [region]'*); a transferability test (*'could the argument transfer to a
  different town with similar dynamics?'*). Mirrored adjustment to
  `scale/location` to absorb the "single location as setting for a
  phenomenon with a geographic dimension" cases.
- **Pre-check**: 0/20 GT-tagged place-based study papers fire the anti-
  pattern triggers (verified before drafting). The tightening shouldn't
  cause false negatives.
- **Caveat noted**: several GT-tagged papers (e.g. *Smart Divide in Rural
  America*, *Rural Ruins / Shishmaref*) themselves sit at the boundary —
  they're empirical-setting cases that the annotator tagged anyway. If
  cat05 surfaces these as false positives in the annotator's set, flag for
  re-review rather than further tightening; annotator inconsistency is its
  own input to the loop.
- **Configs** `topic_v3_abstract_cat05.yaml`, `topic_v3_abstract_ranked_cat05.yaml`.

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
