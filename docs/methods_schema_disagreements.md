# Methods classifier — schema/annotator disagreements

Production classifier (V3 cat06 + prompt_variant 02, 82.0% exact match)
disagreements where reviewing the case suggests the remaining error is
schema or annotator-agreement ambiguity rather than a model failure that
prompt engineering can fix.

Source: `2026-06-09_1324_methods_v3_abstract_production`. All 12 cases
where production disagrees with annotator GT on the desc-empirical /
theoretical-conceptual / qual / unclear cluster of labels.

## Two distinct error types

Cross-referencing the 12 abstract-strategy disagreements against earlier
`sections_full` runs (which feed the model body text, not just the
abstract) sharpens the picture: **half the disagreements are
context-bounded and half are schema-bounded.**

| paper | abstract pred | sections pred | error type |
|---|---|---|---|
| Pearl River Delta | desc-emp | **quant ✓** | context-bounded |
| Circular migration | theo-conc | **qual ✓** | context-bounded |
| Centaur VGI | None (parse fail) | **theo-conc ✓** | context-bounded |
| Land ownership change | desc-emp | **mixed ✓** | context-bounded |
| Cotton District | qual | **desc-emp ✓** | context-bounded |
| Bangladesh activity space | unclear | **desc-emp ✓** | context-bounded |
| Point Roberts | qual | qual ✗ | **schema-bounded** |
| White Water Citizens | qual | qual ✗ | **schema-bounded** |
| Rural Rock Art | unclear | qual / unclear ✗ | **schema-bounded** |
| Cumulative Socionatural Displ. | theo-conc | qual ✗ | **schema-bounded** |
| Geospatial info tech | theo-conc | spatial ✗ | **schema-bounded** |
| Urban geopolitics (stale ex) | unclear | unclear ✗ | stale few-shot example |

**Context-bounded error (6 cases)**: the abstract did not contain enough
methodological detail for the model to make the call the annotator did.
The annotator had access to full text. Switching the inference strategy
to `sections` (body-text extraction via document parsing) reproduces
the annotator's label correctly. These are *not* schema or model
failures; they are an input-mismatch between what the model sees
(abstract only) and what the annotator saw (full paper).

**Schema-bounded error (5 cases + 1 stale example)**: the model and
annotator reach different conclusions even with the same full-text
context. These cluster into three recurring patterns described below.

After reading the 12 disagreements, three recurring patterns explain
the schema-bounded half of the remaining error:

1. **`qual` vs `descriptive-empirical` on archival or biographical
   single-case studies.** The current `qual` definition includes
   "archival analysis" and "single in-depth case study". Reading
   strictly, the model assigns biographical/archival case studies to
   `qual`. Annotator assigns them to `descriptive-empirical` and seems
   to reserve `qual` for papers that name interviews, ethnography, or
   focus groups explicitly.
2. **`unclear` vs `descriptive-empirical` on papers that name a
   specific case but no method.** When the abstract names a specific
   case (a place, a group, an event) but never names a data source or
   analytical method, the model assigns `unclear` (correctly per the
   definition). Annotator assigns `descriptive-empirical`, treating
   the named specific case as sufficient empirical content.
3. **`theoretical-conceptual` vs `descriptive-empirical` on papers
   where empirical material grounds a conceptual contribution.** When
   a paper says "drawing on empirical research… we develop the notion
   of X" or similar, the model reads "primary contribution is the
   conceptual notion" → `theoretical-conceptual`. Annotator reads
   "draws on empirical material" → `descriptive-empirical`. Both are
   defensible.

These patterns suggest the prompt-engineering ceiling on this task is
around 82% because beyond that, the remaining errors are cases where
two careful human annotators reading the same abstract would also
disagree. Single-shot or paired few-shot teaching cannot fix this
(P4 and P5 both confirmed); schema clarification or stricter annotator-
agreement protocols are required.

## Pattern 1 — `qual` vs `descriptive-empirical` on single-case studies

The current `qual` definition is *"qualitative methods (interviews,
ethnography, focus groups, archival analysis, discourse analysis,
single in-depth case study)"*. Single-case archival or biographical
studies fall squarely inside this definition. The annotator appears
to reserve `qual` for interviews/ethnography only.

### Case 1.1 — Borderland Lifeways in Point Roberts
- DOI: `10.1111/j.1931-0846.2016.12200.x`
- Annotator: `descriptive-empirical`
- Model: `qual`
- Model reasoning (paraphrased): "single in-depth case study of Point
  Roberts; describes its characteristics rather than the process of
  data collection; matches the qual definition's single in-depth case
  study clause."

### Case 1.2 — The Making of White Water Citizens (Deakin & Mead)
- DOI: `10.1080/24694452.2017.1420463`
- Annotator: `descriptive-empirical`
- Model: `qual`
- Model reasoning (paraphrased): "biographical study and discourse
  analysis of two historical figures' lives and works; archival/
  biographical work fits qual."

### Case 1.3 — Cotton District (Starkville, Mississippi)
- DOI: `10.1080/24694452.2023.2168247`
- Annotator: `descriptive-empirical`
- Model: `qual`
- Model reasoning (paraphrased): "single in-depth case study, historical/
  discourse analysis of the landscape; fits qual."

**Open schema question:** does archival/biographical case-study work
belong in `qual` or `descriptive-empirical`? The current definition
puts it in `qual`. The annotator's labeling puts it in
`descriptive-empirical`. **Either tighten `qual` to "interviews /
ethnography / focus groups / discourse analysis" only (move archival
and single-case studies to descriptive-empirical), or accept the
model's interpretation and have the annotator re-annotate these three
papers as `qual`.**

## Pattern 2 — `unclear` vs `descriptive-empirical` on named-case papers without methods

The current `unclear` definition is *"the abstract doesn't name a data
source, method, or case material"*. The model is strict: it requires
either a named data source or a named analytical method. The annotator
treats a named specific case (a place, a group) as sufficient.

### Case 2.1 — Female Activity Space in Rural Bangladesh
- DOI: `10.2307/215401`
- Annotator: `descriptive-empirical`
- Model: `unclear`
- Model reasoning (paraphrased): "abstract analyzes female space but
  doesn't name a data source (no 'survey of 100 women') or method
  (no 'semi-structured interviews'); falls under the unclear definition."

### Case 2.2 — Protecting a Broken Window: Rural Rock Art Sites
- DOI: `10.1080/00330124.2021.1957690`
- Annotator: `descriptive-empirical`
- Model: `unclear`
- Model reasoning (paraphrased): "abstract describes the policing
  challenges abstractly ('we hope to contribute to the discussion')
  without naming a data source or method."

**Open schema question:** is naming a specific case (rural Bangladesh,
rural Southwest rock art sites) sufficient to count as
`descriptive-empirical`, or does the abstract need to name a data
source / method too? The model reads the definition strictly; the
annotator does not. **Either loosen `descriptive-empirical` to require
*either* original empirical material *or* a specifically named case
subject (with method optional), or tighten the annotator's threshold
for `descriptive-empirical` to require a named method.**

## Pattern 3 — `theoretical-conceptual` vs `descriptive-empirical` when empirical material grounds a conceptual contribution

The most defensible disagreement. When a paper draws on empirical
material *as a means* to develop a conceptual contribution, both
labels can be argued. Schema currently does not give a tie-breaker.

### Case 3.1 — Cumulative Socionatural Displacements
- DOI: `10.1080/24694452.2021.1960144`
- Annotator: `descriptive-empirical`
- Model: `theoretical-conceptual`
- Abstract quote: *"Drawing on these theorizations, as well as empirical
  research from agrarian Southeast Asia, this article develops the
  notion of cumulative socionatural displacements as one approach for
  [reframing]…"*
- Model reasoning: "the empirical research serves as illustration; the
  primary contribution is the conceptual development of the notion."
- Equally defensible annotator reading: "the article draws on original
  empirical research from Southeast Asia → has empirical material →
  descriptive-empirical."

### Case 3.2 — Geospatial information technology paper
- DOI: `10.1111/j.1467-8306.2005.00447.x`
- Annotator: `descriptive-empirical`
- Model: `theoretical-conceptual`
- Model reasoning: "the paper argues for a framework / agenda-setting
  about integrating geospatial technologies; uses Kansas and Botswana
  as illustrative examples rather than as the empirical engine of the
  paper."

**Open schema question:** when a paper uses empirical material as
illustration but its primary contribution is a conceptual framework,
which label wins? The schema currently has no tie-breaker. **Either
add a tie-breaker rule like "if the paper develops a new framework,
model, or conceptual schema as the primary contribution, the label is
theoretical-conceptual regardless of whether empirical material is
also present", or invert it ("any paper that draws on original
empirical material is descriptive-empirical regardless of conceptual
contribution")**.

## Other notable disagreements

### Stale few-shot example (the most concerning case)
- DOI: `10.1080/24694452.2025.2522840` — *Resituating Urban Geopolitics*
- Annotator: `theoretical-conceptual`
- Model: `unclear`
- **Why this matters:** This paper's abstract is the text we use as the
  `unclear` few-shot example in production. Gemma's reasoning trace
  explicitly compares the input to the example, sees they are byte-
  identical, and matches the example's expected output (`unclear`).
  The annotator has revised the GT to `theoretical-conceptual`, but
  the few-shot example still teaches `unclear`. **The example is now
  training the model against the current GT.** Action: either remove
  this example from the few-shot block or update its expected output
  to `theoretical-conceptual`.

### Pearl River Delta — quant vs descriptive-empirical
- DOI: `10.1111/0033-0124.00269`
- Annotator: `quant`
- Model (abstract): `descriptive-empirical`
- Model (sections): **`quant`** ← context-bounded; resolved by sections
- Abstract: "This case study of spatial transformation in China's
  Pearl River Delta analyzes with greater precision the geographic
  extent and functional attributes…"
- Confirmed context-bounded: the annotator had full-text access; the
  abstract simply did not name the quantitative methods used. Switching
  to `sections` strategy gives the model the same context and it
  correctly produces `quant`.

### Circular migration — qual vs theoretical-conceptual
- DOI: `10.1111/1467-8306.93112`
- Annotator: `qual`
- Model: `theoretical-conceptual`
- Abstract opens: *"Harnessing primary and secondary evidence from
  India, our essay conceptualizes the cultural dynamics of migration."*
- The model's reading: this is an essay that conceptualizes; primary/
  secondary evidence is input not output. Annotator's reading: the
  paper uses primary evidence from India, so qual.

### Centaur VGI — model failed to parse
- DOI: `10.1080/24694452.2020.1768822`
- Annotator: `theoretical-conceptual`
- Model: `None` (no valid prediction parsed)
- Model reasoning shows it deliberating between `spatial`, `theoretical-
  conceptual`, and `descriptive-empirical` without settling. This is a
  parse failure unrelated to the schema confusion.

### Land Ownership Change — mixed vs descriptive-empirical
- DOI: `10.1080/00330124.2023.2194367`
- Annotator: `mixed`
- Model: `descriptive-empirical`
- Abstract mentions "Appalachian Land Study" (a participatory action
  research project). The model treats this as a named project → desc-
  empirical. The annotator's `mixed` label suggests they know the
  project combines qualitative and quantitative work; this is not
  determinable from the abstract alone.

## Two distinct routes to raise the production ceiling

The 12 disagreements split roughly in half between two error types,
and each error type has a distinct fix.

### To resolve context-bounded errors (~6 cases): switch to `sections`

These six cases (Pearl River Delta, Circular migration, Centaur VGI,
Land ownership change, Cotton District, Bangladesh activity space) are
correctly classified by the model when it has access to the full paper
body. They are not schema or annotation failures — they are an
input-channel mismatch between annotator (full text) and model
(abstract). Switching the strategy to `sections` in the production
pipeline would resolve them. Earlier `methods_v3_sections_full` runs
have scored ~84–88% exact-match versus production-abstract's 82%,
broadly consistent with this 6/91 ≈ 6.6pp lift available from the
input-channel switch.

### To resolve schema-bounded errors (~5 cases + 1 stale example): revise the schema

These cases will not be fixed by any prompt-engineering or input-
strategy change. They require the schema or annotation team to make
explicit decisions:

1. **Resolve the `qual` vs `descriptive-empirical` boundary on
   archival / biographical case-study work.** Either remove "archival
   analysis, single in-depth case study" from the `qual` definition,
   or relabel the affected papers (Point Roberts, White Water Citizens,
   plus Rural Rock Art under sections) as `qual`.
2. **Add a tie-breaker rule for the empirical-grounded-conceptual
   pattern** (Cumulative Socionatural Displacements, Geospatial info
   tech). Without one, model and annotator will continue to legitimately
   disagree.
3. **Update or remove the stale "Urban Geopolitics" few-shot example.**
   The example currently teaches against the current GT.
4. **Decide whether a named specific case (without method) is sufficient
   for `descriptive-empirical`.** Affects Pattern 2 cases.

## Appendix — proposed revised schema (v4) for the annotator team

After P6 confirmed that loosening the descriptive-empirical / unclear
boundary at the prompt level causes splash damage on the qual label
(-12pp on qual F1 in exchange for fixing the targeted unclear cases),
the cleanest path to raising the ceiling above 82% is schema revision,
not further prompt engineering. The revisions below are framed as a
proposal to take to the annotator team; they would require ~10-15
papers to be re-annotated to update the GT.

### Proposed v4 label definitions

| label | revised definition |
|---|---|
| `qual` | **Primary evidence is interviews, focus groups, ethnography, or discourse analysis of a small number of cases.** The paper is built on conversations the researchers had with people, or on systematic interpretive coding of a small textual / visual corpus. NOT for archival research or single-case studies without explicit interview / ethnographic data. |
| `quant` | non-spatial quantitative analysis (regression, surveys, modeling) — unchanged |
| `mixed` | qualitative AND quantitative carry comparable weight — unchanged |
| `spatial` | spatial-statistical methods or GIS-based inferential claim — unchanged (V1 short version) |
| `descriptive-empirical` | **Original empirical work that examines or describes specific named cases, archives, sites, communities, or historical events, without inferential testing or systematic interpretive coding.** Includes archival analysis, biographical case studies, site descriptions, and case studies that name a specific country/region + cultural / institutional / historical context. NOT for purely conceptual essays without original empirical material. |
| `theoretical-conceptual` | **Conceptual essay or position paper whose primary contribution is a new framework, model, or conceptual schema.** May draw on existing literature or empirical work as illustration, but does not present original first-hand empirical material as the basis of its claims. |
| `unclear` | The abstract does not name a specific country/region/cultural-institutional context AND does not name a data source or analytical method. Position papers, agenda-setters, and "invitation to engage" papers with no concrete subject go here. |

### What changes in practice

- **The three Pattern 1 archival/biographical case studies (Cotton District,
  Point Roberts, White Water Citizens) move from a defensible-but-disputed
  `qual` label to a clean `descriptive-empirical` label.** The model and
  annotator would converge.
- **The two Pattern 2 named-context-no-method cases (Bangladesh activity
  space, Rural Rock Art) become unambiguously `descriptive-empirical`.**
- **The two Pattern 3 empirically-grounded-conceptual cases (Cumulative
  Socionatural Displacements, Geospatial info tech) get a tie-breaker
  rule** — the conceptual-primacy rule that says original empirical
  material as illustration → `theoretical-conceptual`, original
  empirical material as the basis of the claim → `descriptive-empirical`.
- **The Urban Geopolitics few-shot example is updated** to its current
  GT (`theoretical-conceptual`) so it stops teaching against the
  ground truth.

### Estimated post-revision ceiling

Predicted: production exact-match against the updated GT would land
~87-90% (an additional ~5-8pp over current production). The qual
F1 collapse seen in P6 disappears because the qual label is narrowed
to interview / ethnographic / focus-group work, removing the coupling
with descriptive-empirical that broke when we loosened the desc-emp
side. This is a prediction, not a finding — running it requires the
annotator team to commit to the revision and re-label the affected
papers.

### What this is not

This is not a recommendation to drop labels, restructure the task as
multi-label classification, or move to a hierarchy. Those are all
defensible designs but represent bigger commitments. The revision above
keeps the 7-category structure and only sharpens the boundaries
that the current 91-paper sample shows are fuzzy.

### Action items if the annotator team accepts the revision

1. The annotator team reviews the revised definitions and either
   accepts, modifies, or rejects each.
2. For each accepted revision, the annotator team re-labels the ~10-15
   affected papers in the v3 project on Label Studio (project 113).
3. We re-run the current production prompt against the updated GT and
   report the new ceiling.
4. If the revision is rejected, document why in this file as a
   permanent record of the boundary decision.

## Methodological note

Both P4 (single targeted example) and P5 (paired examples) failed to
move the F1 needle on the affected labels. The pattern was consistent:
each intervention flipped which side of the boundary was over-predicted
without reducing total error. This is the empirical signature of a
model at its operating point given a fuzzy underlying boundary — prompt
engineering can move the boundary but cannot sharpen it.

The dual finding above is therefore the actionable summary: prompt
engineering hit its ceiling at 82%, but **the ceiling has two
components**, and each can be raised by a different intervention:

- **Switch input strategy (abstract → sections):** likely raises the
  ceiling by ~6pp without any schema or annotation work, just by
  matching the model's input channel to the annotator's.
- **Revise the schema** to disambiguate the four open questions above:
  raises the ceiling by an additional ~5–6pp, but requires annotator-
  team coordination and re-annotation of affected cases.
