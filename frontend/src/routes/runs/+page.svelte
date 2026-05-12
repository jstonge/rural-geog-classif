<script lang="ts">
  import Markdown from 'svelte-exmarkdown';
  import data from '$lib/data/runs.json';

  type PipelineMetrics = {
    n_records: number;
    n_with_gt: number;
    exact_match: number | null;
    labels: string[];
    confusion_matrix: Record<string, Record<string, number>>;
  };

  type Run = {
    run_id: string;
    label: string;
    notes: string;
    saved_at: string;
    model: string;
    temperature: number;
    thinking: boolean;
    methods_labels: string[];
    pipelines: string[];
    prompts: {
      methods?: string;
      picker?: string;
    };
    metrics: {
      abstract: PipelineMetrics;
      sections: PipelineMetrics;
      flipped_between_pipelines: number;
    };
  };

  const runs: Run[] = (data as Run[]) ?? [];

  const sortedRuns = [...runs].sort((a, b) => a.saved_at.localeCompare(b.saved_at));

  function formatDate(iso: string): string {
    if (!iso) return '—';
    const idx = iso.indexOf('T');
    return idx === -1 ? iso : iso.slice(0, idx);
  }

  function formatPct(v: number | null | undefined): string {
    if (v == null || Number.isNaN(v)) return '—';
    return `${(v * 100).toFixed(1)}%`;
  }

  function matrixMax(cm: Record<string, Record<string, number>>): number {
    let m = 0;
    for (const row of Object.values(cm)) {
      for (const v of Object.values(row)) {
        if (v > m) m = v;
      }
    }
    return m === 0 ? 1 : m;
  }

  function cellStyle(count: number, isDiag: boolean, max: number): string {
    if (count === 0) return '';
    const ratio = count / max;
    const opacity = Math.max(0.15, ratio);
    const color = isDiag ? `rgba(46, 139, 87, ${opacity})` : `rgba(214, 69, 69, ${opacity})`;
    return `background: ${color};`;
  }

  function promptEntries(prompts: Run['prompts']): { key: string; label: string; md: string }[] {
    const out: { key: string; label: string; md: string }[] = [];
    if (prompts.methods && prompts.methods.trim() !== '')
      out.push({ key: 'methods', label: 'Methods', md: prompts.methods });
    if (prompts.picker && prompts.picker.trim() !== '')
      out.push({ key: 'picker', label: 'Picker', md: prompts.picker });
    return out;
  }
</script>

<div class="page">
  <h1>Run audit</h1>
  <p class="header-links">
    <a href="/about">About the methodology &rarr;</a>
  </p>

  {#if sortedRuns.length === 0}
    <p class="empty">
      No saved runs yet. Run the <code>save_methods_run</code> cell in the notebook to capture the
      current config.
    </p>
  {:else}
    <p class="count">{sortedRuns.length} run{sortedRuns.length === 1 ? '' : 's'}</p>

    <section class="summary-section">
      <h2 class="section-title">Summary</h2>
      <div class="table-scroll">
        <table class="summary">
          <thead>
            <tr>
              <th scope="col">Run</th>
              <th scope="col">Saved</th>
              <th scope="col">Abstract exact-match</th>
              <th scope="col">Sections exact-match</th>
              <th scope="col">&Delta; flipped</th>
              <th scope="col">Pipelines</th>
            </tr>
          </thead>
          <tbody>
            {#each sortedRuns as r (r.run_id)}
              <tr>
                <td class="run-label">{r.label}</td>
                <td class="mono">{formatDate(r.saved_at)}</td>
                <td class="mono num">{formatPct(r.metrics.abstract.exact_match)}</td>
                <td class="mono num">{formatPct(r.metrics.sections.exact_match)}</td>
                <td class="mono num">{r.metrics.flipped_between_pipelines}</td>
                <td>
                  <span class="chip-row">
                    {#each r.pipelines as p (p)}
                      <span class="chip">{p}</span>
                    {/each}
                  </span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <section class="details-section">
      <h2 class="section-title">Details</h2>
      {#each sortedRuns as r (r.run_id)}
        {@const ab = r.metrics.abstract}
        {@const se = r.metrics.sections}
        {@const absMax = matrixMax(ab.confusion_matrix)}
        {@const secMax = matrixMax(se.confusion_matrix)}
        {@const prompts = promptEntries(r.prompts)}
        <details class="run-panel">
          <summary>
            <span class="summary-label">{r.label}</span>
            <span class="summary-date mono">{formatDate(r.saved_at)}</span>
            <span class="summary-metrics mono">
              abstract {formatPct(r.metrics.abstract.exact_match)} &middot; sections
              {formatPct(r.metrics.sections.exact_match)}
            </span>
          </summary>

          <div class="panel-body">
            {#if r.notes && r.notes.trim() !== ''}
              <section class="block">
                <h3>Notes</h3>
                <p class="notes">{r.notes}</p>
              </section>
            {/if}

            <section class="block">
              <h3>Config</h3>
              <table class="kv">
                <tbody>
                  <tr>
                    <th scope="row">model</th>
                    <td class="mono">{r.model}</td>
                  </tr>
                  <tr>
                    <th scope="row">temperature</th>
                    <td class="mono">{r.temperature}</td>
                  </tr>
                  <tr>
                    <th scope="row">thinking</th>
                    <td class="mono">{r.thinking}</td>
                  </tr>
                  <tr>
                    <th scope="row">pipelines</th>
                    <td class="mono">{r.pipelines.join(', ')}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section class="block">
              <h3>Methods labels</h3>
              <span class="chip-row">
                {#each r.methods_labels as m (m)}
                  <span class="chip chip-label">{m}</span>
                {/each}
              </span>
            </section>

            {#if prompts.length > 0}
              <section class="block">
                <h3>Prompts</h3>
                {#each prompts as p (p.key)}
                  <details class="prompt">
                    <summary>{p.label}</summary>
                    <div class="markdown">
                      <Markdown md={p.md} />
                    </div>
                  </details>
                {/each}
              </section>
            {/if}

            <section class="block">
              <h3>Metrics</h3>
              <div class="metrics-grid">
                <div class="metrics-block">
                  <h4>Abstract</h4>
                  <table class="kv kv-tight">
                    <tbody>
                      <tr>
                        <th scope="row">n_with_gt</th>
                        <td class="mono">{ab.n_with_gt}</td>
                      </tr>
                      <tr>
                        <th scope="row">exact_match</th>
                        <td class="mono">{formatPct(ab.exact_match)}</td>
                      </tr>
                    </tbody>
                  </table>
                  {#if ab.labels.length === 0}
                    <p class="muted">No confusion matrix.</p>
                  {:else}
                    <table class="cm">
                      <thead>
                        <tr>
                          <th class="cm-corner" scope="col">
                            <span class="cm-axis-row">annotator</span>
                            <span class="cm-axis-col">pred</span>
                          </th>
                          {#each ab.labels as col (col)}
                            <th scope="col">{col}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody>
                        {#each ab.labels as row, ri (row)}
                          <tr>
                            <th scope="row">{row}</th>
                            {#each ab.labels as col, ci (col)}
                              {@const count = ab.confusion_matrix[row]?.[col] ?? 0}
                              <td
                                class:cm-zero={count === 0}
                                style={cellStyle(count, ri === ci, absMax)}
                              >
                                {count !== 0 ? count : ''}
                              </td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  {/if}
                </div>

                <div class="metrics-block">
                  <h4>Sections</h4>
                  <table class="kv kv-tight">
                    <tbody>
                      <tr>
                        <th scope="row">n_with_gt</th>
                        <td class="mono">{se.n_with_gt}</td>
                      </tr>
                      <tr>
                        <th scope="row">exact_match</th>
                        <td class="mono">{formatPct(se.exact_match)}</td>
                      </tr>
                    </tbody>
                  </table>
                  {#if se.labels.length === 0}
                    <p class="muted">No confusion matrix.</p>
                  {:else}
                    <table class="cm">
                      <thead>
                        <tr>
                          <th class="cm-corner" scope="col">
                            <span class="cm-axis-row">annotator</span>
                            <span class="cm-axis-col">pred</span>
                          </th>
                          {#each se.labels as col (col)}
                            <th scope="col">{col}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody>
                        {#each se.labels as row, ri (row)}
                          <tr>
                            <th scope="row">{row}</th>
                            {#each se.labels as col, ci (col)}
                              {@const count = se.confusion_matrix[row]?.[col] ?? 0}
                              <td
                                class:cm-zero={count === 0}
                                style={cellStyle(count, ri === ci, secMax)}
                              >
                                {count !== 0 ? count : ''}
                              </td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  {/if}
                </div>
              </div>
              <p class="muted small">
                flipped between pipelines: {r.metrics.flipped_between_pipelines}
              </p>
            </section>
          </div>
        </details>
      {/each}
    </section>
  {/if}
</div>

<style>
  .page {
    font-family: system-ui, sans-serif;
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 16px 80px;
    color: #222;
  }

  h1 {
    font-size: 20px;
    margin: 0 0 4px;
  }

  .header-links {
    margin: 0 0 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
  }

  .header-links a {
    color: #777;
    text-decoration: none;
  }

  .header-links a:hover {
    color: #1a4a8a;
    text-decoration: underline;
  }

  .count {
    color: #777;
    font-size: 13px;
    margin: 0 0 16px;
  }

  .empty {
    border: 1px dashed #d0d0d0;
    border-radius: 8px;
    padding: 18px 20px;
    background: #fafafa;
    color: #555;
    font-size: 14px;
  }

  .empty code {
    background: #f0f0f0;
    padding: 1px 5px;
    border-radius: 3px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: #1a4a8a;
  }

  .section-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    margin: 18px 0 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  .summary-section {
    margin: 12px 0 24px;
  }

  .table-scroll {
    overflow-x: auto;
  }

  table.summary {
    border-collapse: collapse;
    font-size: 13px;
    width: 100%;
    color: #222;
  }

  table.summary th,
  table.summary td {
    border-bottom: 1px solid #eee;
    padding: 8px 10px;
    text-align: left;
    vertical-align: middle;
  }

  table.summary thead th {
    background: #fafafa;
    color: #555;
    font-weight: 500;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 2px solid #e2e2e2;
  }

  table.summary td.num {
    text-align: right;
  }

  .run-label {
    font-weight: 600;
    color: #1a4a8a;
  }

  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
  }

  .chip-row {
    display: inline-flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .chip {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    padding: 2px 8px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: white;
    color: #333;
  }

  .chip-label {
    background: #f4f4f4;
  }

  .run-panel {
    border: 1px solid #e2e2e2;
    border-radius: 8px;
    background: white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    margin-bottom: 14px;
    overflow: hidden;
  }

  .run-panel > summary {
    cursor: pointer;
    padding: 12px 16px;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 14px;
    background: #fafafa;
    border-bottom: 1px solid transparent;
    list-style: none;
  }

  .run-panel[open] > summary {
    border-bottom: 1px solid #e2e2e2;
  }

  .run-panel > summary::-webkit-details-marker {
    display: none;
  }

  .run-panel > summary::before {
    content: '\\25B8';
    color: #888;
    font-size: 11px;
    margin-right: 2px;
    transition: transform 0.15s;
    display: inline-block;
  }

  .run-panel[open] > summary::before {
    transform: rotate(90deg);
  }

  .summary-label {
    font-weight: 600;
    color: #1a4a8a;
    font-size: 14px;
  }

  .summary-date {
    color: #666;
  }

  .summary-metrics {
    color: #555;
    margin-left: auto;
  }

  .panel-body {
    padding: 14px 18px 18px;
  }

  .block {
    margin: 10px 0 18px;
  }

  .block h3 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    margin: 0 0 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  .notes {
    margin: 0;
    font-size: 14px;
    line-height: 1.55;
    color: #333;
    padding: 8px 12px;
    background: #fafafa;
    border-left: 3px solid #d0d7de;
    border-radius: 4px;
  }

  table.kv {
    border-collapse: collapse;
    font-size: 13px;
  }

  table.kv th,
  table.kv td {
    text-align: left;
    padding: 4px 12px 4px 0;
    vertical-align: top;
  }

  table.kv th {
    color: #888;
    font-weight: 500;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    width: 110px;
  }

  table.kv td {
    color: #222;
  }

  table.kv-tight th,
  table.kv-tight td {
    padding: 2px 12px 2px 0;
  }

  table.kv-tight th {
    width: 90px;
  }

  details.prompt {
    border-top: 1px solid #f0f0f0;
    padding-top: 6px;
    margin-top: 6px;
  }

  details.prompt > summary {
    cursor: pointer;
    font-size: 12px;
    color: #555;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    padding: 4px 0;
  }

  details.prompt > summary:hover {
    color: #222;
  }

  .markdown {
    font-size: 13px;
    line-height: 1.55;
    color: #333;
    padding: 6px 0 10px;
  }

  .markdown :global(h1),
  .markdown :global(h2),
  .markdown :global(h3) {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #444;
    margin: 12px 0 6px;
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
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .markdown :global(pre) {
    background: #f7f7f7;
    border: 1px solid #eee;
    border-radius: 4px;
    padding: 8px 10px;
    overflow-x: auto;
    font-size: 12px;
  }

  .markdown :global(ul),
  .markdown :global(ol) {
    margin: 6px 0;
    padding-left: 22px;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 18px;
    align-items: start;
  }

  .metrics-block {
    border: 1px solid #eee;
    border-radius: 6px;
    padding: 10px 12px;
    background: #fcfcfc;
  }

  .metrics-block h4 {
    margin: 0 0 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #555;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  table.cm {
    border-collapse: collapse;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: #222;
    margin-top: 8px;
  }

  table.cm th,
  table.cm td {
    border: 1px solid #e2e2e2;
    width: 52px;
    height: 36px;
    text-align: center;
    vertical-align: middle;
    padding: 2px 4px;
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

  table.cm td.cm-zero {
    color: #bbb;
  }

  .muted {
    color: #888;
    font-size: 13px;
  }

  .muted.small {
    font-size: 11px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    margin-top: 8px;
  }
</style>
