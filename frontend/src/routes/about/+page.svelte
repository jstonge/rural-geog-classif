<script lang="ts">
  import Markdown from 'svelte-exmarkdown';

  const md = `# Methodology

This page explains how the predictions on the [Review page](./review) are generated and what each label means.

## Pipeline

We classify ~360 rural geography papers with **Gemma 4 31B**, served locally via vLLM with thinking mode (\`--reasoning-parser gemma4\`). Each paper gets three Label Studio controls — \`Location\`, \`topic\`, \`methods\` — but the Review page focuses on \`methods\`.

Every paper is classified **twice**, producing two predictions per record:

### Abstract pred (\`pred_abstract\`)

The model reads only the **title + abstract** and returns one methods label. This mirrors what human annotators see — annotators were given title + abstract only, even when full-text summaries were available.

### Sections pred (\`pred_sections\`)

A 3-phase pipeline that gives the model access to the **full paper text**:

1. **Phase A — Parse.** Regex-split the docling-extracted markdown of the paper into \`# Header → body\` chunks.
2. **Phase B — Pick.** Ask the model which section headers are most relevant to identifying the paper's methodology (e.g. *Data and Methods*, *Study Site and Methods*, *Methodology*). Returns 0–N header names.
3. **Phase C — Classify.** Re-run the methods classifier with the picked section bodies appended to the title + abstract context.

When Phase B returns no headers (full text not available, or no methodology-relevant header found), Phase C falls back to abstract-only context. In that case Sections pred ≈ Abstract pred.

## Methods labels

- **qual** — qualitative methods (interviews, ethnography, focus groups, archival, discourse analysis).
- **quant** — quantitative methods (statistical analysis, regression, large-N surveys, modelling).
- **both** — mixed methods (qualitative + quantitative used jointly).
- **Descriptive** — descriptive empirical work, or theoretical / essay papers without inferential statistics.
- **spatial/mapping** — GIS, remote sensing, spatial analysis as the primary methodology.
- **unclear** — methods cannot be determined from available text.

## Direction tags

Each card on the Review page is tagged with one of:

- **agree-correct** — both runs match the annotator label.
- **agree-wrong** — both runs return the same value, but neither matches the annotator.
- **flip-ok-bad** — abstract was right, sections wrong (regression introduced by reading full text).
- **flip-bad-ok** — abstract was wrong, sections right (upgrade — full text surfaced methods the abstract hid).
- **flip-lateral** — runs disagree, both wrong.
- **no-gt** — no annotator label exists for this paper.

## Caveat on disagreements

Annotators only had access to title + abstract. When *Sections pred* surfaces qualitative fieldwork (interviews, focus groups, ethnography) that the abstract doesn't mention, the disagreement isn't necessarily a model error — the model has read information the annotator couldn't see. Inspect the **Picked sections** block on each Review card to judge.
`;
</script>

<div class="page">
  <div class="markdown">
    <Markdown {md} />
  </div>
</div>

<style>
  .page {
    font-family: system-ui, sans-serif;
    max-width: 760px;
    margin: 0 auto;
    padding: 32px 20px 96px;
    color: #222;
  }

  .markdown {
    font-size: 15px;
    line-height: 1.65;
    color: #333;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
  }

  .markdown :global(h1) {
    font-size: 24px;
    font-weight: 600;
    color: #222;
    margin: 0 0 18px;
    line-height: 1.25;
  }

  .markdown :global(h2) {
    font-size: 17px;
    font-weight: 600;
    color: #222;
    margin: 32px 0 10px;
    line-height: 1.3;
    border-bottom: 1px solid #eee;
    padding-bottom: 6px;
  }

  .markdown :global(h3) {
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #555;
    margin: 22px 0 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  .markdown :global(p) {
    margin: 10px 0;
  }

  .markdown :global(ul),
  .markdown :global(ol) {
    margin: 10px 0;
    padding-left: 24px;
  }

  .markdown :global(li) {
    margin: 6px 0;
  }

  .markdown :global(a) {
    color: #1a4a8a;
    text-decoration: none;
  }

  .markdown :global(a:hover) {
    text-decoration: underline;
  }

  .markdown :global(strong) {
    color: #222;
    font-weight: 600;
  }

  .markdown :global(em) {
    color: #444;
  }

  .markdown :global(code) {
    background: #f4f4f4;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 13px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    color: #1a4a8a;
  }
</style>
