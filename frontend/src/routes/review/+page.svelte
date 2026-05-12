<script lang="ts">
  import Markdown from 'svelte-exmarkdown';
  import data from '$lib/data/flipped.json';

  type Direction =
    | 'agree-correct'
    | 'agree-wrong'
    | 'flip-ok-bad'
    | 'flip-bad-ok'
    | 'flip-lateral'
    | 'no-gt';

  type FlippedRecord = {
    doi: string;
    title: string;
    direction: Direction;
    flipped: boolean;
    has_gt: boolean;
    correct_abstract: boolean | null;
    correct_sections: boolean | null;
    annotator: string[];
    pred_abstract: string | null;
    pred_sections: string | null;
    picked: string[];
    sections: Record<string, string>;
    abstract: string;
    reasoning_abstract: string;
    reasoning_sections: string;
    ls_task_id: number | null;
    ls_url: string | null;
  };

  const records: FlippedRecord[] = data as FlippedRecord[];

  type AgreementFilter = 'all' | 'agree' | 'flipped' | 'no-gt';
  type OutcomeFilter = 'all' | 'correct' | 'wrong';

  const agreementFilters: { key: AgreementFilter; label: string }[] = [
    { key: 'all', label: 'all' },
    { key: 'agree', label: 'agree' },
    { key: 'flipped', label: 'flipped' },
    { key: 'no-gt', label: 'no-gt' }
  ];

  const outcomeFilters: { key: OutcomeFilter; label: string }[] = [
    { key: 'all', label: 'all' },
    { key: 'correct', label: 'correct' },
    { key: 'wrong', label: 'wrong' }
  ];

  let activeAgreement: AgreementFilter = $state('all');
  let activeOutcome: OutcomeFilter = $state('all');
  let cmSelected: { row: string; col: string } | null = $state(null);

  const filtered = $derived(
    records.filter((r) => {
      if (activeAgreement === 'agree' && !r.direction.startsWith('agree-')) return false;
      if (activeAgreement === 'flipped' && !r.direction.startsWith('flip-')) return false;
      if (activeAgreement === 'no-gt' && r.direction !== 'no-gt') return false;

      if (activeOutcome === 'correct' && r.correct_sections !== true) return false;
      if (activeOutcome === 'wrong' && r.correct_sections !== false) return false;

      if (cmSelected !== null) {
        if (r.annotator[0] !== cmSelected.row) return false;
        if (r.pred_sections !== cmSelected.col) return false;
      }

      return true;
    })
  );

  // Confusion matrix: annotator (rows) vs pred_sections (cols)
  const cmRecords = $derived(
    records.filter((r) => r.has_gt && r.pred_sections != null && r.annotator.length > 0)
  );

  const cmLabels = $derived.by(() => {
    const seen: Record<string, true> = {};
    for (const r of cmRecords) {
      const a = r.annotator[0];
      if (a) seen[a] = true;
      if (r.pred_sections) seen[r.pred_sections] = true;
    }
    return Object.keys(seen).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  });

  const cmGrid = $derived.by(() => {
    const idx: Record<string, number> = {};
    cmLabels.forEach((l, i) => (idx[l] = i));
    const n = cmLabels.length;
    const grid: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
    for (const r of cmRecords) {
      const a = r.annotator[0];
      const p = r.pred_sections;
      if (a == null || p == null) continue;
      const ri = idx[a];
      const ci = idx[p];
      if (ri == null || ci == null) continue;
      grid[ri][ci] += 1;
    }
    return grid;
  });

  const cmMax = $derived.by(() => {
    let m = 0;
    for (const row of cmGrid) for (const v of row) if (v > m) m = v;
    return m === 0 ? 1 : m;
  });

  const cmTotal = $derived(cmRecords.length);

  function cellStyle(count: number, isDiag: boolean): string {
    if (count === 0) return '';
    const ratio = count / cmMax;
    const opacity = Math.max(0.15, ratio);
    const color = isDiag ? `rgba(46, 139, 87, ${opacity})` : `rgba(214, 69, 69, ${opacity})`;
    return `background: ${color};`;
  }

  function toggleCell(row: string, col: string, count: number): void {
    if (count === 0) return;
    if (cmSelected !== null && cmSelected.row === row && cmSelected.col === col) {
      cmSelected = null;
    } else {
      cmSelected = { row, col };
    }
  }

  function directionLabel(d: Direction): string {
    if (d === 'agree-correct') return '✓ agree';
    if (d === 'agree-wrong') return '✗ agree';
    if (d === 'flip-ok-bad') return 'OK→BAD';
    if (d === 'flip-bad-ok') return 'BAD→OK';
    if (d === 'flip-lateral') return 'BAD→BAD';
    return 'no label';
  }

  function directionColor(d: Direction): string {
    if (d === 'agree-correct') return '#2e8b57';
    if (d === 'agree-wrong') return '#d59f3a';
    if (d === 'flip-ok-bad') return '#d64545';
    if (d === 'flip-bad-ok') return '#2e8b57';
    if (d === 'flip-lateral') return '#888';
    return '#5a7a99';
  }

  function buildPickedMarkdown(picked: string[], sections: Record<string, string>): string {
    return picked
      .map((h) => {
        const body = sections[h] ?? '';
        return `## ${h}\n\n${body}`;
      })
      .join('\n\n');
  }

  function wordCount(s: string): number {
    return s.trim() ? s.trim().split(/\s+/).length : 0;
  }
</script>

<div class="page">
  <h1>Methods classifier &mdash; review</h1>
  <p class="about-link">
    <a href="/about">About the methodology &rarr;</a>
    <a href="/runs">Run audit &rarr;</a>
  </p>
  <p class="count">{filtered.length} of {records.length} records</p>

  <section class="cm-section">
    <h2 class="cm-title">Confusion matrix (sections pred vs annotator; click to see papers)</h2>
    {#if cmLabels.length === 0}
      <p class="muted">No ground-truth records with predictions to display.</p>
    {:else}
      <table class="cm">
        <caption>
          Diagonal = agreement; off-diagonal = disagreement. N = {cmTotal}
          {#if cmSelected !== null}
            <button class="clear-cell" onclick={() => (cmSelected = null)}>
              Clear cell selection
            </button>
          {/if}
        </caption>
        <thead>
          <tr>
            <th class="cm-corner" scope="col">
              <span class="cm-axis-row">annotator</span>
              <span class="cm-axis-col">pred</span>
            </th>
            {#each cmLabels as col (col)}
              <th scope="col">{col}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each cmLabels as row, ri (row)}
            <tr>
              <th scope="row">{row}</th>
              {#each cmLabels as col, ci (col)}
                {@const count = cmGrid[ri][ci]}
                {@const isSelected =
                  cmSelected !== null && cmSelected.row === row && cmSelected.col === col}
                <td
                  class:cm-zero={count === 0}
                  class:cm-selected={isSelected}
                  style={cellStyle(count, ri === ci)}
                >
                  {#if count !== 0}
                    <button
                      type="button"
                      class="cm-cell-btn"
                      class:cm-cell-selected={isSelected}
                      aria-pressed={isSelected}
                      aria-label={`annotator ${row}, pred ${col}, count ${count}`}
                      onclick={() => toggleCell(row, col, count)}
                    >
                      {count}
                    </button>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <div class="filter-row">
    <span class="filter-label">Agreement</span>
    <div class="filters">
      {#each agreementFilters as f (f.key)}
        <button
          class="chip"
          class:active={activeAgreement === f.key}
          onclick={() => (activeAgreement = f.key)}
        >
          {f.label}
        </button>
      {/each}
    </div>
  </div>

  <div class="filter-row">
    <span class="filter-label">Outcome</span>
    <div class="filters">
      {#each outcomeFilters as f (f.key)}
        <button
          class="chip"
          class:active={activeOutcome === f.key}
          onclick={() => (activeOutcome = f.key)}
        >
          {f.label}
        </button>
      {/each}
    </div>
  </div>

  {#each filtered as r (r.doi)}
    <article class="card">
      <header class="card-header">
        <a class="title" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer noopener">
          {r.title || r.doi}
        </a>
        <span class="header-right">
          <span class="badge" style="background: {directionColor(r.direction)};">
            {directionLabel(r.direction)}
          </span>
          {#if r.ls_url}
            <a class="ls-link" href={r.ls_url} target="_blank" rel="noreferrer noopener">
              ↗ Label Studio
            </a>
          {/if}
        </span>
      </header>

      <div class="labels">
        <div class="label-cell">
          <div class="label-key">Annotator</div>
          <div class="label-val">{r.annotator.join(', ') || '—'}</div>
        </div>
        <div class="label-cell">
          <div class="label-key">Abstract pred</div>
          <div class="label-val">{r.pred_abstract ?? '—'}</div>
        </div>
        <div
          class="label-cell"
          class:disagree={r.annotator.length > 0 && r.pred_sections !== (r.annotator[0] ?? null)}
        >
          <div class="label-key">Sections pred</div>
          <div class="label-val">{r.pred_sections ?? '—'}</div>
        </div>
      </div>

      {#if r.abstract && r.abstract.trim() !== ''}
        <section class="abstract">
          <h3>Abstract</h3>
          <p>{r.abstract}</p>
        </section>
      {/if}

      <section class="picked">
        <h3>Picked sections</h3>
        {#if r.picked.length === 0}
          <p class="muted"><em>(no sections picked &mdash; model used abstract only)</em></p>
        {:else}
          <div class="markdown">
            <Markdown md={buildPickedMarkdown(r.picked, r.sections)} />
          </div>
        {/if}
      </section>

      <details>
        <summary>
          Reasoning (abstract-only run)
          {#if wordCount(r.reasoning_abstract) > 0}
            <span class="word-count">{wordCount(r.reasoning_abstract)} words</span>
          {/if}
        </summary>
        <div class="markdown">
          <Markdown md={r.reasoning_abstract} />
        </div>
      </details>

      <details>
        <summary>
          Reasoning (section-picking run)
          {#if wordCount(r.reasoning_sections) > 0}
            <span class="word-count">{wordCount(r.reasoning_sections)} words</span>
          {/if}
        </summary>
        <div class="markdown">
          <Markdown md={r.reasoning_sections} />
        </div>
      </details>
    </article>
  {/each}
</div>

<style>
  .page {
    font-family: system-ui, sans-serif;
    max-width: 960px;
    margin: 0 auto;
    padding: 24px 16px 80px;
    color: #222;
  }

  h1 {
    font-size: 20px;
    margin: 0 0 4px;
  }

  .count {
    color: #777;
    font-size: 13px;
    margin: 0 0 16px;
  }

  .about-link {
    margin: 0 0 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
  }

  .about-link a {
    color: #777;
    text-decoration: none;
  }

  .about-link a:hover {
    color: #1a4a8a;
    text-decoration: underline;
  }

  .cm-section {
    margin: 12px 0 18px;
  }

  .cm-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    margin: 0 0 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  table.cm {
    border-collapse: collapse;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: #222;
  }

  table.cm caption {
    caption-side: bottom;
    text-align: left;
    font-size: 11px;
    color: #777;
    padding-top: 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  table.cm th,
  table.cm td {
    border: 1px solid #e2e2e2;
    width: 56px;
    height: 40px;
    text-align: center;
    vertical-align: middle;
    padding: 2px 4px;
  }

  table.cm td.cm-zero {
    cursor: default;
  }

  table.cm td.cm-selected {
    outline: 2px solid #111;
    outline-offset: -2px;
    font-weight: bold;
  }

  .cm-cell-btn {
    appearance: none;
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
    width: 100%;
    height: 100%;
    font: inherit;
    color: inherit;
    cursor: pointer;
    text-align: center;
  }

  .cm-cell-btn:focus-visible {
    outline: 2px solid #1a4a8a;
    outline-offset: -2px;
  }

  .cm-cell-btn.cm-cell-selected {
    font-weight: bold;
  }

  .clear-cell {
    margin-left: 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    padding: 2px 8px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: white;
    cursor: pointer;
    color: #333;
  }

  .clear-cell:hover {
    background: #f4f4f4;
  }

  table.cm thead th {
    background: #fafafa;
    color: #555;
    font-weight: 500;
  }

  table.cm tbody th {
    background: #fafafa;
    color: #555;
    font-weight: 500;
    text-align: right;
    padding-right: 8px;
  }

  table.cm .cm-corner {
    background: #f4f4f4;
    color: #888;
    font-size: 10px;
    line-height: 1.2;
    position: relative;
  }

  table.cm .cm-axis-row,
  table.cm .cm-axis-col {
    display: block;
  }

  table.cm .cm-axis-row {
    text-align: left;
  }

  table.cm .cm-axis-col {
    text-align: right;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }

  .filter-label {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #888;
    min-width: 78px;
  }

  .filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .chip {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    padding: 4px 10px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: white;
    cursor: pointer;
    color: #333;
  }

  .chip:hover {
    background: #f4f4f4;
  }

  .chip.active {
    background: #222;
    color: white;
    border-color: #222;
  }

  .card {
    border: 1px solid #e2e2e2;
    border-radius: 8px;
    background: white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    padding: 16px 20px;
    margin-bottom: 20px;
    margin-top: 20px;
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .title {
    font-size: 15px;
    font-weight: 600;
    color: #1a4a8a;
    text-decoration: none;
    line-height: 1.35;
  }

  .title:hover {
    text-decoration: underline;
  }

  .badge {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .header-right {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .ls-link {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: #334;
    background: #eef;
    border: 1px solid #dde;
    padding: 2px 8px;
    border-radius: 999px;
    text-decoration: none;
    white-space: nowrap;
  }

  .ls-link:hover {
    background: #dde;
    text-decoration: underline;
  }

  .labels {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 16px;
  }

  .label-cell {
    border: 1px solid #eee;
    border-radius: 6px;
    padding: 8px 10px;
    background: #fafafa;
  }

  .label-cell.disagree {
    background: #fff4e5;
    border-color: #f0c674;
  }

  .label-key {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #888;
    margin-bottom: 2px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .label-val {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    color: #222;
  }

  .picked {
    margin-bottom: 12px;
  }

  .picked h3 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    margin: 8px 0;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .abstract {
    margin-bottom: 12px;
    padding: 8px 12px;
    background: #fafafa;
    border-left: 3px solid #d0d7de;
    border-radius: 4px;
  }

  .abstract h3 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    margin: 4px 0 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .abstract p {
    margin: 0;
    font-size: 14px;
    line-height: 1.55;
    color: #333;
  }

  .muted {
    color: #888;
    font-size: 13px;
  }

  .markdown {
    font-size: 14px;
    line-height: 1.55;
    color: #333;
  }

  .markdown :global(h2) {
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #444;
    margin: 16px 0 6px;
    border-bottom: 1px solid #eee;
    padding-bottom: 4px;
  }

  .markdown :global(p) {
    margin: 6px 0;
  }

  .markdown :global(code) {
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
  }

  details {
    margin-top: 8px;
    border-top: 1px solid #f0f0f0;
    padding-top: 8px;
  }

  summary {
    cursor: pointer;
    font-size: 13px;
    color: #555;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    padding: 4px 0;
  }

  summary:hover {
    color: #222;
  }

  .word-count {
    display: inline;
    margin-left: 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: #999;
  }
</style>
