<script lang="ts">
  import { base } from '$app/paths';
  import { scaleBand, scaleLinear, scaleOrdinal } from 'd3-scale';
  import { schemeTableau10 } from 'd3-scale-chromatic';
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

  let activeSchema: string = $state(initialSchema);

  const currentSchema: SchemaSummary | null = $derived(
    d.schemas.find((s) => s.name === activeSchema) ?? null
  );
  const controls: string[] = $derived(currentSchema?.controls ?? []);

  type Bar = { label: string; count: number };
  type Facet = { control: string; bars: Bar[]; total: number };

  const facets: Facet[] = $derived.by(() => {
    if (!currentSchema) return [];
    return currentSchema.controls.map((control) => {
      const counts = currentSchema.label_distribution[control] ?? {};
      const bars: Bar[] = Object.entries(counts)
        .map(([label, count]) => ({ label, count }))
        .sort((a, b) => b.count - a.count);
      const total = bars.reduce((s, b) => s + b.count, 0);
      return { control, bars, total };
    });
  });

  const globalMax: number = $derived.by(() => {
    let m = 0;
    for (const f of facets) {
      for (const b of f.bars) if (b.count > m) m = b.count;
    }
    return m === 0 ? 1 : m;
  });

  const color = $derived(
    scaleOrdinal<string, string>()
      .domain(controls)
      .range(schemeTableau10)
  );

  const margin = { top: 24, right: 16, bottom: 90, left: 60 } as const;
  const rowHeight = 280;
  const innerHeight = rowHeight - margin.top - margin.bottom;
  const rowWidth = 1040;
  const barStep = 30;
  const barPadding = 0.15;
  const innerWidthMax = rowWidth - margin.left - margin.right;

  const yScale = $derived(
    scaleLinear().domain([0, globalMax]).range([innerHeight, 0]).nice()
  );

  const yTicks: number[] = $derived(yScale.ticks(5));

  type Row = {
    facet: Facet;
    innerWidth: number;
    svgWidth: number;
    xScale: ReturnType<typeof scaleBand<string>>;
  };

  const rows: Row[] = $derived.by(() => {
    return facets.map((facet) => {
      const n = Math.max(1, facet.bars.length);
      const desired = n * barStep;
      const innerWidth = desired < innerWidthMax ? desired : innerWidthMax;
      const svgWidth = margin.left + innerWidth + margin.right;
      const xScale = scaleBand<string>()
        .domain(facet.bars.map((b) => b.label))
        .range([0, innerWidth])
        .padding(barPadding);
      return { facet, innerWidth, svgWidth, xScale };
    });
  });

  function formatExported(iso: string): string {
    const i = iso.indexOf('T');
    return i === -1 ? iso : iso.slice(0, i);
  }
</script>

<div class="page">
  <h1>Annotation distribution by task</h1>
  <p class="header-links">
    <a href="{base}/annotations">/annotations &rarr;</a>
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
      &middot; exported {formatExported(d.exported_at)}
    </p>

    {#if schemaNames.length > 1}
      <div class="filter-row">
        <span class="filter-label">Schema</span>
        <div class="filters">
          {#each schemaNames as s (s)}
            <button
              type="button"
              class="chip"
              class:active={activeSchema === s}
              onclick={() => (activeSchema = s)}
            >
              {s}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#each rows as row (row.facet.control)}
      <section class="block">
        <h2>
          {row.facet.control}
          <span class="mono">&middot; {row.facet.total}</span>
        </h2>
        <div class="scroll-x">
          <svg width={row.svgWidth} height={rowHeight}>
            <g transform="translate({margin.left},{margin.top})">
              {#each yTicks as t (t)}
                <line
                  x1={0}
                  x2={row.innerWidth}
                  y1={yScale(t)}
                  y2={yScale(t)}
                  stroke="#eee"
                  stroke-width="1"
                />
                <text
                  x={-8}
                  y={yScale(t) + 3}
                  text-anchor="end"
                  font-size="10"
                  fill="#888"
                >{t}</text>
              {/each}

              <text
                x={-(innerHeight / 2)}
                y={-44}
                transform="rotate(-90)"
                text-anchor="middle"
                font-size="11"
                fill="#666"
              >annotations</text>

              {#each row.facet.bars as b (b.label)}
                {@const bx = row.xScale(b.label) ?? 0}
                {@const bw = row.xScale.bandwidth()}
                {@const by = yScale(b.count)}
                {@const h = innerHeight - by}
                <rect
                  x={bx}
                  y={by}
                  width={bw}
                  height={h}
                  fill={color(row.facet.control)}
                  opacity="0.85"
                />
                {#if b.count > 0}
                  <text
                    x={bx + bw / 2}
                    y={by - 4}
                    text-anchor="middle"
                    font-size="10"
                    fill="#333"
                  >{b.count}</text>
                {/if}
                <text
                  x={bx + bw / 2}
                  y={innerHeight + 8}
                  text-anchor="end"
                  font-size="10"
                  fill="#555"
                  transform="rotate(-35,{bx + bw / 2},{innerHeight + 8})"
                >{b.label}</text>
              {/each}

              <line
                x1={0}
                x2={row.innerWidth}
                y1={innerHeight}
                y2={innerHeight}
                stroke="#bbb"
                stroke-width="1"
              />
            </g>
          </svg>
        </div>
      </section>
    {/each}
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
    font-size: 14px;
    margin: 0 0 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
    color: #333;
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

  .block {
    margin: 22px 0 28px;
    border: 1px solid #eee;
    border-radius: 8px;
    background: white;
    padding: 14px 18px 18px;
  }

  .scroll-x {
    overflow-x: auto;
  }

  svg {
    display: block;
  }
</style>
