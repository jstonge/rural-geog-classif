<script lang="ts">
  import { base } from '$app/paths';
  import data from '$lib/data/annotations.json';

  type Annotator = {
    id: number;
    name: string;
    email: string | null;
    n_annotations: number;
    n_tasks: number;
    controls: string[];
  };

  type SchemaSummary = {
    name: string;
    project_id: number;
    n_tasks_total: number;
    n_tasks_annotated: number;
    controls: string[];
    annotators: Annotator[];
    label_distribution: Record<string, Record<string, number>>;
    by_annotator: Record<string, Record<string, Record<string, number>>>;
    annotations_per_task: Record<string, number>;
  };

  type AnnotationsData = {
    exported_at: string;
    schemas: SchemaSummary[];
  };

  const d = data as unknown as AnnotationsData;

  const schemaNames: string[] = d.schemas.map((s) => s.name);
  const initialSchema: string = schemaNames[0] ?? '';

  function firstControl(name: string): string {
    return d.schemas.find((s) => s.name === name)?.controls[0] ?? '';
  }

  let activeSchema: string = $state(initialSchema);
  let activeControl: string = $state(firstControl(initialSchema));

  function setSchema(name: string) {
    activeSchema = name;
    activeControl = firstControl(name);
  }

  const currentSchema: SchemaSummary | null = $derived(
    d.schemas.find((s) => s.name === activeSchema) ?? null
  );
  const controls: string[] = $derived(currentSchema?.controls ?? []);

  const annotatorsById: Record<string, Annotator> = $derived.by(() => {
    const out: Record<string, Annotator> = {};
    for (const a of currentSchema?.annotators ?? []) out[String(a.id)] = a;
    return out;
  });

  type Bar = { label: string; count: number };

  function sortedBars(counts: Record<string, number>): Bar[] {
    return Object.entries(counts)
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
  }

  function maxCount(counts: Record<string, number>): number {
    let m = 0;
    for (const v of Object.values(counts)) if (v > m) m = v;
    return m === 0 ? 1 : m;
  }

  const totalBars: Bar[] = $derived(
    sortedBars(currentSchema?.label_distribution[activeControl] ?? {})
  );
  const totalMax: number = $derived(
    maxCount(currentSchema?.label_distribution[activeControl] ?? {})
  );
  const controlTotal: number = $derived(totalBars.reduce((s, b) => s + b.count, 0));

  type AnnotatorBreakdown = {
    annotator: Annotator;
    bars: Bar[];
    total: number;
  };

  const perAnnotator: AnnotatorBreakdown[] = $derived.by(() => {
    const byUid = currentSchema?.by_annotator[activeControl] ?? {};
    const out: AnnotatorBreakdown[] = [];
    for (const [uid, counts] of Object.entries(byUid)) {
      const annotator = annotatorsById[uid] ?? {
        id: Number(uid),
        name: `user_${uid}`,
        email: null,
        n_annotations: 0,
        n_tasks: 0,
        controls: []
      };
      const bars = sortedBars(counts);
      const total = bars.reduce((s, b) => s + b.count, 0);
      out.push({ annotator, bars, total });
    }
    out.sort((a, b) => b.total - a.total);
    return out;
  });

  const controlLabels: string[] = $derived(totalBars.map((b) => b.label));

  function pctOfMax(count: number, max: number): number {
    if (max <= 0) return 0;
    return Math.round((count / max) * 100);
  }

  function pctOfTotal(count: number, total: number): string {
    if (total <= 0) return '0.0%';
    return `${((count / total) * 100).toFixed(1)}%`;
  }

  function annotatorCount(uid: string | number, label: string): number {
    return currentSchema?.by_annotator[activeControl]?.[String(uid)]?.[label] ?? 0;
  }

  type AnnPerTask = { n: number; tasks: number };
  const annPerTaskRows: AnnPerTask[] = $derived(
    Object.entries(currentSchema?.annotations_per_task ?? {})
      .map(([n, tasks]) => ({ n: Number(n), tasks }))
      .sort((a, b) => a.n - b.n)
  );
  const annPerTaskMax: number = $derived(
    annPerTaskRows.reduce((m, r) => (r.tasks > m ? r.tasks : m), 0) || 1
  );

  function formatExported(iso: string): string {
    const i = iso.indexOf('T');
    return i === -1 ? iso : iso.slice(0, i);
  }
</script>

<div class="page">
  <h1>Annotations</h1>
  <p class="header-links">
    <a href="{base}/runs">/runs &rarr;</a>
    <a href="{base}/compare">/compare &rarr;</a>
    <a href="{base}/prompts">/prompts &rarr;</a>
    <a href="{base}/about">/about &rarr;</a>
  </p>

  {#if d.schemas.length === 0}
    <p class="count">exported {formatExported(d.exported_at)}</p>
    <p class="muted empty">
      No annotation data &mdash; run <code>export_annotations.py</code> first.
    </p>
  {:else if currentSchema}
    <p class="count">
      Schema <span class="mono">{currentSchema.name}</span> &middot; project {currentSchema.project_id}
      &middot; {currentSchema.n_tasks_annotated} / {currentSchema.n_tasks_total} tasks annotated
      &middot; {currentSchema.annotators.length} annotators &middot; exported {formatExported(d.exported_at)}
    </p>

    <div class="filter-row">
      <span class="filter-label">Schema</span>
      <div class="filters">
        {#each schemaNames as s (s)}
          <button
            type="button"
            class="chip"
            class:active={activeSchema === s}
            onclick={() => setSchema(s)}
          >
            {s}
          </button>
        {/each}
      </div>
    </div>

    <div class="filter-row">
      <span class="filter-label">Control</span>
      <div class="filters">
        {#each controls as c (c)}
          <button
            type="button"
            class="chip"
            class:active={activeControl === c}
            onclick={() => (activeControl = c)}
          >
            {c}
          </button>
        {/each}
      </div>
    </div>

    <section class="block">
      <h2>Label distribution &middot; <span class="mono">{activeControl}</span></h2>
      <p class="muted small">{controlTotal} label selections across all annotators (choices unioned per task).</p>
      {#if totalBars.length === 0}
        <p class="muted">No labels recorded for this control.</p>
      {:else}
        <table class="bars">
          <tbody>
            {#each totalBars as b (b.label)}
              <tr>
                <th scope="row" class="bar-label">{b.label}</th>
                <td class="bar-cell">
                  <div class="bar" style="width: {pctOfMax(b.count, totalMax)}%;"></div>
                </td>
                <td class="bar-num mono">{b.count}</td>
                <td class="bar-pct mono">{pctOfTotal(b.count, controlTotal)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    <section class="block">
      <h2>Per annotator &middot; <span class="mono">{activeControl}</span></h2>
      {#if perAnnotator.length === 0}
        <p class="muted">No annotators have labelled this control.</p>
      {:else}
        <div class="table-scroll">
          <table class="grid">
            <thead>
              <tr>
                <th scope="col">Annotator</th>
                <th scope="col" class="num">n</th>
                {#each controlLabels as l (l)}
                  <th scope="col" class="num">{l}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each perAnnotator as row (row.annotator.id)}
                <tr>
                  <th scope="row" class="annot">
                    <div class="annot-name">{row.annotator.name}</div>
                    {#if row.annotator.email}
                      <div class="annot-email mono">{row.annotator.email}</div>
                    {/if}
                  </th>
                  <td class="num mono">{row.total}</td>
                  {#each controlLabels as l (l)}
                    {@const c = annotatorCount(row.annotator.id, l)}
                    <td class="num mono" class:zero={c === 0}>
                      {c === 0 ? '—' : c}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>

    <section class="block">
      <h2>Annotator throughput</h2>
      <div class="table-scroll">
        <table class="grid">
          <thead>
            <tr>
              <th scope="col">Annotator</th>
              <th scope="col" class="num">tasks</th>
              <th scope="col" class="num">annotations</th>
              <th scope="col">controls</th>
            </tr>
          </thead>
          <tbody>
            {#each currentSchema.annotators as a (a.id)}
              <tr>
                <th scope="row" class="annot">
                  <div class="annot-name">{a.name}</div>
                  {#if a.email}
                    <div class="annot-email mono">{a.email}</div>
                  {/if}
                </th>
                <td class="num mono">{a.n_tasks}</td>
                <td class="num mono">{a.n_annotations}</td>
                <td>
                  <span class="chip-row">
                    {#each a.controls as c (c)}
                      <span class="chip-static">{c}</span>
                    {/each}
                  </span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <section class="block">
      <h2>Annotations per task</h2>
      <p class="muted small">How many annotators independently labelled each task.</p>
      <table class="bars">
        <tbody>
          {#each annPerTaskRows as r (r.n)}
            <tr>
              <th scope="row" class="bar-label mono">{r.n}</th>
              <td class="bar-cell">
                <div class="bar bar-neutral" style="width: {pctOfMax(r.tasks, annPerTaskMax)}%;"></div>
              </td>
              <td class="bar-num mono">{r.tasks}</td>
            </tr>
          {/each}
        </tbody>
      </table>
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

  h2 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #555;
    margin: 0 0 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
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
    font-size: 12px;
    margin: 0 0 16px;
  }

  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .muted {
    color: #888;
    font-size: 13px;
  }

  .small {
    font-size: 12px;
    margin: 0 0 8px;
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
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .filter-label {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #888;
    min-width: 70px;
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

  .chip-row {
    display: inline-flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .block {
    margin: 22px 0 28px;
    border: 1px solid #eee;
    border-radius: 8px;
    background: white;
    padding: 14px 18px 18px;
  }

  table.bars {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  table.bars td,
  table.bars th {
    padding: 4px 8px;
    vertical-align: middle;
    border-bottom: 1px solid #f4f4f4;
  }

  .bar-label {
    text-align: left;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: #333;
    width: 140px;
    font-weight: 500;
  }

  .bar-cell {
    width: auto;
  }

  .bar {
    height: 14px;
    background: rgba(46, 139, 87, 0.55);
    border-radius: 2px;
    min-width: 1px;
  }

  .bar.bar-neutral {
    background: rgba(80, 100, 140, 0.5);
  }

  .bar-num {
    width: 60px;
    text-align: right;
    font-size: 12px;
    color: #222;
  }

  .bar-pct {
    width: 64px;
    text-align: right;
    font-size: 12px;
    color: #888;
  }

  .table-scroll {
    overflow-x: auto;
  }

  table.grid {
    border-collapse: collapse;
    font-size: 13px;
    width: 100%;
    color: #222;
  }

  table.grid th,
  table.grid td {
    border-bottom: 1px solid #eee;
    padding: 8px 10px;
    text-align: left;
    vertical-align: top;
  }

  table.grid thead th {
    background: #fafafa;
    color: #555;
    font-weight: 500;
    border-bottom: 2px solid #e2e2e2;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  table.grid th.num,
  table.grid td.num {
    text-align: right;
    font-size: 12px;
  }

  td.zero {
    color: #ccc;
  }

  .annot {
    width: 220px;
    text-align: left;
    font-weight: 500;
  }

  .annot-name {
    font-size: 13px;
    color: #222;
  }

  .annot-email {
    font-size: 11px;
    color: #888;
    margin-top: 2px;
  }
</style>
