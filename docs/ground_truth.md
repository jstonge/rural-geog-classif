# What counts as "ground truth" here

A short conceptual note. Companion to [`methods.md`](methods.md) (the iterative loop) and [`prompt_anatonomy.md`](prompt_anatonomy.md) (the prompt artifacts the loop mutates). This doc exists because both
of those use the term "ground truth" in passing, and the term, on inspection, doesn't quite mean what conventional ML framing would suggest.

## The problem with the conventional framing

In standard supervised-ML vocabulary, "ground truth" is the per-example annotator label, and the question is how close a model gets to it. Score functions assume the label is correct; modeling work consists of moving the model closer.

That framing breaks here, because every artifact a comparison touches is itself revisable:

- **Annotator labels can be wrong.** The reviewer-changes-her-mind path (steps 5 → 7 in the methods.md loop diagram) is real: in several cases the annotator updated her label after reading the model's reasoning. The most-recent-wins GT loader exists recisely so those revisions propagate into the next validation pass.
- **Categories can be wrong.** The v1 → v3 schema revision was driven by *inter-annotator disagreement on v1 boundaries*, not by model error. The `methods` topic tightening (`topic_02.csv`) was driven by  *model–annotator disagreement* that, on case-by-case reading, indicted the v3 definition rather than the annotator.
- **Examples can be wrong.** The 8-example block empirically hurt topic scores — a sign that the exemplars distorted the model's prior rather than anchoring it correctly.
- **Templates can be wrong.** A template that asks for a set when the task is genuinely ranked is asking the wrong question.

Three labellers (the annotator, the model, the schema-author) are inthe room, and at any point any one of them can turn out to be the one who needs to update. Nothing is fixed by construction.

## The schema CSV as the closest thing to a referent

If anything in the system is "ground truth" in the sense of a negotiated reference that grounds the other revisions, it is the **categories CSV** — the codified, domain-expert-authored definition of what each label
means.

It is the closest thing to a fixed referent precisely because, when an annotator and a model disagree, the first question is *"does the CSV's definition actually disambiguate this case?"*

- If yes → one of them misread the spec. Either fix the annotation (if  the annotator misapplied a clear definition) or revise the prompt /
  add an example (if the model is misapplying a clear definition).
- If no → the CSV is the thing that needs revising. This is the hardest case to spot from metrics alone — it requires reading the disagreeing papers and asking whether the definition really resolves them.

Even then the CSV is not immutable — v1 → v3, then `topic_01.csv` → `topic_02.csv`, are real revisions. But it is the artifact whose changes are made *deliberately, by domain-expert decision*, rather than per-paper adjudication. Calling annotator labels "ground truth" in code (which [`score.py`](../classify/src/score.py) does, because the metric loop needs something concrete to compare against) is an implementation convenience. The conceptual referent is the schema.

## What this implies for the levers in the loop

The methods.md loop names four levers (prompt content, add context, revise category definitions, annotation revision). The reframing above gives them a natural cost ordering:

- Revising the **categories CSV** is the heaviest move, because it changes the referent that annotators, models, and future revisions all measure against. A CSV revision usually warrants re-validating *all* prior snapshots — their scores were computed under a different spec.
- Revising the **template** or **examples** is lighter: it changes how the model is *taught* the categories, not the categories themselves. Re-validation only needs to cover the affected task.
- Revising an **annotation** is the lightest of all: a single per-paper fix that the most-recent-wins loader picks up on the next run, with no need to re-run the model.

These costs are not just bookkeeping. They tell you which lever to reach for *last*, after cheaper interventions have been ruled out: prefer fixing an annotation over rewriting an example, prefer rewriting
an example over revising the CSV, and only revise the CSV when the disagreement reveals a genuine gap in the spec rather than a misapplication of it.

## What "validation" measures, then

Given the above, the metric numbers in
[`metrics.json`](../classify/output/runs/) should be read as:

> Under the *current* schema version, the *current* annotation pass, and the *current* prompt assembly, the model agrees with the annotator at rate X.

All three qualifiers can move between runs, and the loop is precisely the activity of moving them — toward higher agreement, but also toward a better-specified schema and a more carefully-annotated set. A score delta between two runs is informative only if you can name which of
the three qualifiers changed; that's what the snapshot bundle's `config.json` is for.

## TL;DR

The prompt anatomy isn't a delivery mechanism for a fixed specification; it's a co-design surface where domain experts, annotators, and the model negotiate what the specification should be. The categories CSV is the negotiated artifact. Annotator labels are working hypotheses about its correct application. The model's disagreements are the most useful signal we have for *which kind* of revision is overdue.
