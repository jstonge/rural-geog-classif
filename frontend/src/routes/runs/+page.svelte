<script lang="ts">
  import { SvelteSet } from 'svelte/reactivity';
  import { base } from '$app/paths';
  import data from '$lib/data/runs.json';

  type PerLabelStat = {
    p: number;
    r: number;
    f1: number;
    support_gt: number;
    support_pred: number;
  };

  type Metrics = {
    n_total: number;
    n_correct: number;
    exact_match: number | null;
    mean_jaccard?: number | null;
    mean_precision?: number | null;
    mean_recall?: number | null;
    mean_f1?: number | null;
    per_label?: Record<string, PerLabelStat>;
    label_distribution?: Record<string, number>;
    confusion_matrix?: Record<string, Record<string, number>>;
  };

  type Run = {
    run_id: string;
    task?: string | null;
    schema?: string | null;
    strategy?: string | null;
    saved_at?: string;
    model?: string;
    thinking?: boolean;
    max_tokens?: number;
    all_papers?: boolean;
    examples_used?: string[];
    examples_dir?: string;
    prompt_template?: string;
    schema_json?: string;
    prompt?: string;
    metrics?: Metrics | Record<string, unknown> | null;
    control?: string;
    label?: string;
    notes?: string;
    [key: string]: unknown;
  };

  // Be defensive: only keep entries whose metrics shape is the new flat one
  // (has `n_total` / `exact_match` at the top level) or is null/missing.
  // Legacy paired-pipeline metrics objects are coerced to null so the row still
  // renders but counts as "unvalidated".
  function isFlatMetrics(m: unknown): m is Metrics {
    if (m === null || typeof m !== 'object') return false;
    const obj = m as Record<string, unknown>;
    return 'n_total' in obj || 'exact_match' in obj;
  }

  const rawRuns: Run[] = (data as Run[]) ?? [];
  const runs: Run[] = rawRuns.map((r) => ({
    ...r,
    metrics: isFlatMetrics(r.metrics) ? (r.metrics as Metrics) : null
  }));

  type SortKey =
    | 'run_id'
    | 'task'
    | 'schema'
    | 'strategy'
    | 'examples'
    | 'saved_at'
    | 'exact_match'
    | 'jaccard';
  type SortDir = 'asc' | 'desc';

  type TaskFilter = 'all' | 'methods' | 'location' | 'topic' | 'legacy';
  type ValidationFilter = 'all' | 'validated' | 'unvalidated';

  let sortKey = $state<SortKey>('saved_at');
  let sortDir = $state<SortDir>('desc');
  let taskFilter = $state<TaskFilter>('all');
  let validationFilter = $state<ValidationFilter>('all');
  const expanded = new SvelteSet<string>();

  const taskFilters: { key: TaskFilter; label: string }[] = [
    { key: 'all', label: 'all' },
    { key: 'methods', label: 'methods' },
    { key: 'location', label: 'location' },
    { key: 'topic', label: 'topic' },
    { key: 'legacy', label: 'legacy' }
  ];

  const validationFilters: { key: ValidationFilter; label: string }[] = [
    { key: 'all', label: 'all' },
    { key: 'validated', label: 'validated' },
    { key: 'unvalidated', label: 'unvalidated' }
  ];

  function getMetrics(r: Run): Metrics | null {
    return (r.metrics as Metrics | null) ?? null;
  }

  function taskOf(r: Run): string {
    return r.task ?? 'legacy';
  }

  function formatDate(iso: string | undefined): string {
    if (!iso) return '—';
    const idx = iso.indexOf('T');
    return idx === -1 ? iso : iso.slice(0, idx);
  }

  function formatPct(v: number | null | undefined): string {
    if (v == null || Number.isNaN(v)) return '—';
    return `${(v * 100).toFixed(1)}%`;
  }

  function formatJaccard(v: number | null | undefined): string {
    if (v == null || Number.isNaN(v)) return '—';
    return v.toFixed(3);
  }

  function exampleCount(r: Run): number | null {
    if (!Array.isArray(r.examples_used)) return null;
    return r.examples_used.length;
  }

  function cmp(a: unknown, b: unknown, dir: SortDir): number {
    const aMissing = a == null;
    const bMissing = b == null;
    // Always sort missing values last regardless of direction.
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;
    let result: number;
    if (typeof a === 'number' && typeof b === 'number') {
      result = a - b;
    } else {
      result = String(a).localeCompare(String(b));
    }
    return dir === 'asc' ? result : -result;
  }

  function sortValue(r: Run, key: SortKey): unknown {
    const m = getMetrics(r);
    switch (key) {
      case 'run_id':
        return r.run_id;
      case 'task':
        return taskOf(r);
      case 'schema':
        return r.schema ?? null;
      case 'strategy':
        return r.strategy ?? null;
      case 'examples':
        return exampleCount(r);
      case 'saved_at':
        return r.saved_at ?? null;
      case 'exact_match':
        return m?.exact_match ?? null;
      case 'jaccard':
        return m?.mean_jaccard ?? null;
    }
  }

  const filtered = $derived(
    runs.filter((r) => {
      if (taskFilter !== 'all' && taskOf(r) !== taskFilter) return false;
      const validated = getMetrics(r) !== null;
      if (validationFilter === 'validated' && !validated) return false;
      if (validationFilter === 'unvalidated' && validated) return false;
      return true;
    })
  );

  const sorted = $derived(
    [...filtered].sort((a, b) => cmp(sortValue(a, sortKey), sortValue(b, sortKey), sortDir))
  );

  const totalWithMetrics = $derived(runs.filter((r) => getMetrics(r) !== null).length);

  function toggleSort(key: SortKey): void {
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      // Default to descending for date / numeric, ascending for text.
      sortDir =
        key === 'saved_at' || key === 'exact_match' || key === 'jaccard' || key === 'examples'
          ? 'desc'
          : 'asc';
    }
  }

  function toggleExpanded(id: string): void {
    if (expanded.has(id)) expanded.delete(id);
    else expanded.add(id);
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' ▲' : ' ▼';
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

  function matrixLabels(cm: Record<string, Record<string, number>>): string[] {
    const seen: Record<string, true> = {};
    for (const row of Object.keys(cm)) seen[row] = true;
    for (const row of Object.values(cm))
      for (const col of Object.keys(row)) seen[col] = true;
    return Object.keys(seen).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  }

  function hasConfusionMatrix(m: Metrics | null): boolean {
    if (!m || !m.confusion_matrix) return false;
    return Object.keys(m.confusion_matrix).length > 0;
  }

  type ConfigField = { key: string; value: string };

  function configFields(r: Run): ConfigField[] {
    const out: ConfigField[] = [];
    const push = (key: string, raw: unknown): void => {
      if (raw === undefined || raw === null || raw === '') return;
      out.push({ key, value: String(raw) });
    };
    push('task', r.task);
    push('schema', r.schema);
    push('strategy', r.strategy);
    push('model', r.model);
    push('thinking', r.thinking);
    push('max_tokens', r.max_tokens);
    push('all_papers', r.all_papers);
    push('examples_dir', r.examples_dir);
    return out;
  }
</script>

<div class="page">
  <h1>Runs</h1>
  <p class="header-links">
    <a href="{base}/compare">Compare labellers &rarr;</a>
    <a href="{base}/prompts">Prompts &rarr;</a>
    <a href="{base}/annotations">Annotations &rarr;</a>
  </p>

  <p class="count">
    {sorted.length} of {runs.length} run{runs.length === 1 ? '' : 's'}
    ({totalWithMetrics} with metrics)
  </p>

  {#if runs.length === 0}
    <p class="empty">No saved runs yet.</p>
  {:else}
    <div class="filter-row">
      <span class="filter-label">Task</span>
      <div class="filters">
        {#each taskFilters as f (f.key)}
          <button
            type="button"
            class="chip"
            class:active={taskFilter === f.key}
            onclick={() => (taskFilter = f.key)}
          >
            {f.label}
          </button>
        {/each}
      </div>
    </div>

    <div class="filter-row">
      <span class="filter-label">Validation</span>
      <div class="filters">
        {#each validationFilters as f (f.key)}
          <button
            type="button"
            class="chip"
            class:active={validationFilter === f.key}
            onclick={() => (validationFilter = f.key)}
          >
            {f.label}
          </button>
        {/each}
      </div>
    </div>

    <div class="table-scroll">
      <table class="runs">
        <thead>
          <tr>
            <th scope="col">
              <button type="button" class="th-btn" onclick={() => toggleSort('run_id')}>
                Run{sortIndicator('run_id')}
              </button>
            </th>
            <th scope="col">
              <button type="button" class="th-btn" onclick={() => toggleSort('task')}>
                Task{sortIndicator('task')}
              </button>
            </th>
            <th scope="col">
              <button type="button" class="th-btn" onclick={() => toggleSort('schema')}>
                Schema{sortIndicator('schema')}
              </button>
            </th>
            <th scope="col">
              <button type="button" class="th-btn" onclick={() => toggleSort('strategy')}>
                Strategy{sortIndicator('strategy')}
              </button>
            </th>
            <th scope="col" class="num">
              <button type="button" class="th-btn" onclick={() => toggleSort('examples')}>
                Examples{sortIndicator('examples')}
              </button>
            </th>
            <th scope="col">
              <button type="button" class="th-btn" onclick={() => toggleSort('saved_at')}>
                Saved{sortIndicator('saved_at')}
              </button>
            </th>
            <th scope="col" class="num">
              <button type="button" class="th-btn" onclick={() => toggleSort('exact_match')}>
                Exact-match{sortIndicator('exact_match')}
              </button>
            </th>
            <th scope="col" class="num">
              <button type="button" class="th-btn" onclick={() => toggleSort('jaccard')}>
                Jaccard{sortIndicator('jaccard')}
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          {#each sorted as r (r.run_id)}
            {@const m = getMetrics(r)}
            {@const isOpen = expanded.has(r.run_id)}
            {@const t = taskOf(r)}
            {@const exCount = exampleCount(r)}
            <tr
              class="row-head"
              class:open={isOpen}
              onclick={() => toggleExpanded(r.run_id)}
              tabindex="0"
              role="button"
              aria-expanded={isOpen}
              onkeydown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleExpanded(r.run_id);
                }
              }}
            >
              <td class="mono run-id">
                <span class="caret">{isOpen ? '▾' : '▸'}</span>
                <span class="run-id-text">{r.run_id}</span>
              </td>
              <td><span class="chip-static chip-task">{t}</span></td>
              <td><span class="chip-static">{r.schema ?? '—'}</span></td>
              <td class="mono">{r.strategy ?? '—'}</td>
              <td class="mono num">{exCount ?? '—'}</td>
              <td class="mono">{formatDate(r.saved_at)}</td>
              <td class="mono num">{formatPct(m?.exact_match)}</td>
              <td class="mono num">{formatJaccard(m?.mean_jaccard)}</td>
            </tr>
            {#if isOpen}
              {@const fields = configFields(r)}
              <tr class="row-body">
                <td colspan="8">
                  <div class="panel-body">
                    {#if r.notes && r.notes.trim() !== ''}
                      <section class="block">
                        <h3>Notes</h3>
                        <p class="notes">{r.notes}</p>
                      </section>
                    {/if}

                    <section class="block">
                      <h3>Config</h3>
                      {#if fields.length === 0}
                        <p class="muted">No config recorded.</p>
                      {:else}
                        <table class="kv">
                          <tbody>
                            {#each fields as f (f.key)}
                              <tr>
                                <th scope="row">{f.key}</th>
                                <td class="mono">{f.value}</td>
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      {/if}
                    </section>

                    {#if Array.isArray(r.examples_used) && r.examples_used.length > 0}
                      <section class="block">
                        <h3>Examples used</h3>
                        <span class="chip-row">
                          {#each r.examples_used as ex (ex)}
                            <span class="chip-static chip-example">{ex}</span>
                          {/each}
                        </span>
                      </section>
                    {/if}

                    {#if r.prompt && r.prompt.trim() !== ''}
                      <section class="block">
                        <h3>Prompt</h3>
                        <details class="prompt">
                          <summary>Show prompt</summary>
                          <pre class="prompt-pre">{r.prompt}</pre>
                        </details>
                      </section>
                    {/if}

                    {#if m}
                      <section class="block">
                        <h3>Metrics</h3>
                        <table class="kv kv-tight">
                          <tbody>
                            <tr>
                              <th scope="row">n</th>
                              <td class="mono">{m.n_correct} / {m.n_total}</td>
                            </tr>
                            <tr>
                              <th scope="row">exact_match</th>
                              <td class="mono">{formatPct(m.exact_match)}</td>
                            </tr>
                            {#if m.mean_jaccard != null}
                              <tr>
                                <th scope="row">mean_jaccard</th>
                                <td class="mono">{formatJaccard(m.mean_jaccard)}</td>
                              </tr>
                            {/if}
                            {#if m.mean_precision != null}
                              <tr>
                                <th scope="row">mean_precision</th>
                                <td class="mono">{formatJaccard(m.mean_precision)}</td>
                              </tr>
                            {/if}
                            {#if m.mean_recall != null}
                              <tr>
                                <th scope="row">mean_recall</th>
                                <td class="mono">{formatJaccard(m.mean_recall)}</td>
                              </tr>
                            {/if}
                            {#if m.mean_f1 != null}
                              <tr>
                                <th scope="row">mean_f1</th>
                                <td class="mono">{formatJaccard(m.mean_f1)}</td>
                              </tr>
                            {/if}
                          </tbody>
                        </table>

                        {#if m.per_label && Object.keys(m.per_label).length > 0}
                          {@const pl = m.per_label as Record<string, PerLabelStat>}
                          {@const plRows = Object.entries(pl).sort(
                            (a, b) => b[1].support_gt - a[1].support_gt
                          )}
                          <h4 class="cm-heading">Per-label P / R / F1</h4>
                          <table class="pl">
                            <thead>
                              <tr>
                                <th scope="col">label</th>
                                <th scope="col" class="num">gt</th>
                                <th scope="col" class="num">pred</th>
                                <th scope="col" class="num">P</th>
                                <th scope="col" class="num">R</th>
                                <th scope="col" class="num">F1</th>
                              </tr>
                            </thead>
                            <tbody>
                              {#each plRows as [lbl, s] (lbl)}
                                <tr>
                                  <th scope="row">{lbl}</th>
                                  <td class="num">{s.support_gt}</td>
                                  <td class="num">{s.support_pred}</td>
                                  <td class="num">{s.p.toFixed(2)}</td>
                                  <td class="num">{s.r.toFixed(2)}</td>
                                  <td class="num">{s.f1.toFixed(2)}</td>
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        {/if}

                        {#if hasConfusionMatrix(m)}
                          {@const cm = m.confusion_matrix as Record<
                            string,
                            Record<string, number>
                          >}
                          {@const labels = matrixLabels(cm)}
                          {@const maxV = matrixMax(cm)}
                          <h4 class="cm-heading">Confusion matrix</h4>
                          <table class="cm">
                            <thead>
                              <tr>
                                <th class="cm-corner" scope="col">
                                  <span class="cm-axis-row">gt</span>
                                  <span class="cm-axis-col">pred</span>
                                </th>
                                {#each labels as col (col)}
                                  <th scope="col">{col}</th>
                                {/each}
                              </tr>
                            </thead>
                            <tbody>
                              {#each labels as row, ri (row)}
                                <tr>
                                  <th scope="row">{row}</th>
                                  {#each labels as col, ci (col)}
                                    {@const count = cm[row]?.[col] ?? 0}
                                    <td
                                      class:cm-zero={count === 0}
                                      style={cellStyle(count, ri === ci, maxV)}
                                    >
                                      {count !== 0 ? count : ''}
                                    </td>
                                  {/each}
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        {/if}
                      </section>
                    {:else}
                      <section class="block">
                        <h3>Metrics</h3>
                        <p class="muted">Not validated yet.</p>
                      </section>
                    {/if}
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
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

  .chip-static {
    display: inline-block;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    padding: 2px 8px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: white;
    color: #333;
  }

  .chip-task {
    background: #eef;
    border-color: #dde;
    color: #334;
  }

  .chip-example {
    background: #f4f4f4;
  }

  .chip-row {
    display: inline-flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .table-scroll {
    overflow-x: auto;
    margin-top: 12px;
  }

  table.runs {
    border-collapse: collapse;
    font-size: 13px;
    width: 100%;
    color: #222;
  }

  table.runs th,
  table.runs td {
    border-bottom: 1px solid #eee;
    padding: 8px 10px;
    text-align: left;
    vertical-align: middle;
  }

  table.runs thead th {
    background: #fafafa;
    color: #555;
    font-weight: 500;
    border-bottom: 2px solid #e2e2e2;
    padding: 0;
  }

  table.runs thead th.num,
  table.runs tbody td.num {
    text-align: right;
  }

  .th-btn {
    appearance: none;
    background: transparent;
    border: none;
    cursor: pointer;
    width: 100%;
    text-align: inherit;
    padding: 8px 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #555;
    font-weight: 500;
  }

  .th-btn:hover {
    background: #f0f0f0;
    color: #222;
  }

  .row-head {
    cursor: pointer;
  }

  .row-head:hover {
    background: #fafafa;
  }

  .row-head.open {
    background: #f5f7fb;
  }

  .row-head:focus-visible {
    outline: 2px solid #1a4a8a;
    outline-offset: -2px;
  }

  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
  }

  .run-id {
    display: flex;
    align-items: center;
    gap: 6px;
    max-width: 320px;
  }

  .run-id-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .caret {
    color: #888;
    font-size: 11px;
    width: 12px;
    display: inline-block;
  }

  .row-body > td {
    background: #fafbfc;
    padding: 0;
    border-bottom: 1px solid #e2e2e2;
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
    width: 120px;
  }

  table.kv td {
    color: #222;
  }

  table.kv-tight th,
  table.kv-tight td {
    padding: 2px 12px 2px 0;
  }

  table.kv-tight th {
    width: 100px;
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

  .prompt-pre {
    margin: 6px 0 0;
    padding: 10px 12px;
    background: #f7f7f7;
    border: 1px solid #eee;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    line-height: 1.5;
    color: #222;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 480px;
    overflow: auto;
  }

  .cm-heading {
    margin: 12px 0 6px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  table.cm {
    border-collapse: collapse;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: #222;
    margin-top: 4px;
  }

  table.cm th,
  table.cm td {
    border: 1px solid #e2e2e2;
    width: 50px;
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

  table.pl {
    border-collapse: collapse;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: #222;
    margin-top: 4px;
  }

  table.pl th,
  table.pl td {
    border-bottom: 1px solid #eee;
    padding: 3px 10px;
    text-align: left;
  }

  table.pl thead th {
    background: #fafafa;
    color: #555;
    font-weight: 500;
    border-bottom: 2px solid #e2e2e2;
  }

  table.pl tbody th {
    color: #444;
    font-weight: 500;
  }

  table.pl th.num,
  table.pl td.num {
    text-align: right;
    min-width: 36px;
  }

  .muted {
    color: #888;
    font-size: 13px;
  }
</style>
