<script lang="ts">
  import { scaleLinear, scaleOrdinal, scaleBand } from 'd3-scale';
  import { extent } from 'd3-array';
  import { schemeTableau10 } from 'd3-scale-chromatic';
  import data from '$lib/data/viz.json';

  type Point = {
    doi: string;
    title: string;
    abstract: string;
    authors: string;
    pub_year: string;
    source: string;
    keywords: string;
    cluster: number;
    x: number;
    y: number;
  };

  const points: Point[] = data as Point[];

  const width = 800;
  const height = 600;
  const margin = { top: 20, right: 20, bottom: 30, left: 40 };

  const xExtent = extent(points, (d) => d.x) as [number, number];
  const yExtent = extent(points, (d) => d.y) as [number, number];

  const xScale = scaleLinear()
    .domain(xExtent)
    .range([margin.left, width - margin.right]);

  const yScale = scaleLinear()
    .domain(yExtent)
    .range([height - margin.bottom, margin.top]);

  const clusters = [...new Set(points.map((d) => d.cluster))].sort((a, b) => a - b);
  const color = scaleOrdinal<number, string>().domain(clusters).range(schemeTableau10);

  // Bar chart dimensions
  const barWidth = 350;
  const barHeight = 600;
  const barMargin = { top: 20, right: 20, bottom: 40, left: 50 };

  // Decade bucketing
  const decades = ['1980–1990', '1990–2000', '2000–2010', '2010–2020'] as const;

  function getDecade(year: string): string {
    const y = parseInt(year, 10);
    if (y < 1990) return '1980–1990';
    if (y < 2000) return '1990–2000';
    if (y < 2010) return '2000–2010';
    return '2010–2020';
  }

  // Filter out noise cluster (-1) for bar chart
  const nonNoiseClusters = clusters.filter((c) => c !== -1);

  // Compute proportions: for each decade, fraction of papers in each cluster
  type DecadeData = {
    decade: string;
    segments: { cluster: number; y0: number; y1: number; proportion: number }[];
  };

  const decadeProportions: DecadeData[] = decades.map((decade) => {
    const decadePoints = points.filter((d) => d.cluster !== -1 && getDecade(d.pub_year) === decade);
    const total = decadePoints.length;
    let cumulative = 0;
    const segments = nonNoiseClusters.map((cluster) => {
      const count = decadePoints.filter((d) => d.cluster === cluster).length;
      const proportion = total > 0 ? count / total : 0;
      const y0 = cumulative;
      cumulative += proportion;
      return { cluster, y0, y1: cumulative, proportion };
    });
    return { decade, segments };
  });

  // Bar chart scales
  const xBand = scaleBand<string>()
    .domain([...decades])
    .range([barMargin.left, barWidth - barMargin.right])
    .padding(0.2);

  const yBar = scaleLinear()
    .domain([0, 1])
    .range([barHeight - barMargin.bottom, barMargin.top]);

  let hovered: Point | null = $state(null);
  let tooltipX = $state(0);
  let tooltipY = $state(0);
  let selectedCluster: number | null = $state(null);

  const filteredPoints = $derived(
    selectedCluster !== null ? points.filter((d) => d.cluster === selectedCluster) : []
  );

  function onPointerMove(e: PointerEvent) {
    const svg = (e.currentTarget as SVGSVGElement);
    const rect = svg.getBoundingClientRect();
    tooltipX = e.clientX - rect.left;
    tooltipY = e.clientY - rect.top;

    const target = e.target as SVGElement;
    const idx = target.dataset.idx;
    if (idx != null) {
      hovered = points[+idx];
    } else {
      hovered = null;
    }
  }

  function onClick(e: MouseEvent) {
    const target = e.target as SVGElement;
    const idx = target.dataset.idx;
    if (idx != null) {
      const cluster = points[+idx].cluster;
      selectedCluster = selectedCluster === cluster ? null : cluster;
    }
  }

  function onBarClick(cluster: number) {
    selectedCluster = selectedCluster === cluster ? null : cluster;
  }
</script>

<h1>Rural Geography Methodology Clusters</h1>

<div class="container">
  <div class="scatter-wrapper">
    <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
    <svg
      {width}
      {height}
      onpointermove={onPointerMove}
      onpointerleave={() => (hovered = null)}
      onclick={onClick}
    >
      {#each points as point, i (point.doi)}
        <circle
          cx={xScale(point.x)}
          cy={yScale(point.y)}
          r={hovered === point ? 7 : 4}
          fill={point.cluster === -1 ? '#ccc' : color(point.cluster)}
          opacity={selectedCluster !== null && point.cluster !== selectedCluster ? 0.15 : hovered && hovered !== point ? 0.3 : 0.8}
          data-idx={i}
        />
      {/each}
    </svg>

    {#if hovered}
      <div
        class="tooltip"
        style="left: {tooltipX > width / 2 ? tooltipX - 315 : tooltipX + 15}px; top: {tooltipY + 15}px;"
      >
        <strong>{hovered.title || hovered.doi}</strong>
        <div class="meta">
          <span class="cluster">Cluster {hovered.cluster}</span>
          {#if hovered.pub_year}<span class="tag">{hovered.pub_year}</span>{/if}
        </div>
        {#if hovered.authors}<div class="authors">{hovered.authors}</div>{/if}
        {#if hovered.source}<div class="source">{hovered.source}</div>{/if}
        {#if hovered.keywords}<div class="keywords">{hovered.keywords}</div>{/if}
        <p>{hovered.abstract.slice(0, 650)}...</p>
      </div>
    {/if}
  </div>

  <svg
    width={barWidth}
    height={barHeight}
    class="bar-chart"
  >
    <!-- Y-axis label -->
    <text
      x={-(barHeight / 2)}
      y={14}
      transform="rotate(-90)"
      text-anchor="middle"
      font-size="12"
      fill="#666"
    >Proportion</text>

    <!-- Y-axis ticks -->
    {#each [0, 0.25, 0.5, 0.75, 1.0] as tick (tick)}
      <line
        x1={barMargin.left}
        x2={barWidth - barMargin.right}
        y1={yBar(tick)}
        y2={yBar(tick)}
        stroke="#e0e0e0"
        stroke-width="1"
      />
      <text
        x={barMargin.left - 6}
        y={yBar(tick) + 4}
        text-anchor="end"
        font-size="11"
        fill="#666"
      >{tick}</text>
    {/each}

    <!-- Stacked bars -->
    {#each decadeProportions as { decade, segments } (decade)}
      {#each segments as seg (seg.cluster)}
        {#if seg.proportion > 0}
          <rect
            x={xBand(decade)}
            y={yBar(seg.y1)}
            width={xBand.bandwidth()}
            height={yBar(seg.y0) - yBar(seg.y1)}
            fill={color(seg.cluster)}
            opacity={selectedCluster !== null && seg.cluster !== selectedCluster ? 0.15 : 0.85}
            role="button"
            tabindex="-1"
            aria-label="Cluster {seg.cluster}, {decade}"
            onclick={() => onBarClick(seg.cluster)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') onBarClick(seg.cluster); }}
            style="cursor: pointer;"
          />
        {/if}
      {/each}
    {/each}

    <!-- X-axis decade labels -->
    {#each decades as decade (decade)}
      <text
        x={(xBand(decade) ?? 0) + xBand.bandwidth() / 2}
        y={barHeight - barMargin.bottom + 20}
        text-anchor="middle"
        font-size="12"
        fill="#333"
      >{decade}</text>
    {/each}

    <!-- X-axis label -->
    <text
      x={(barMargin.left + barWidth - barMargin.right) / 2}
      y={barHeight - 4}
      text-anchor="middle"
      font-size="12"
      fill="#666"
    >Decade</text>
  </svg>
</div>

{#if selectedCluster !== null}
  <div class="table-section">
    <h2>
      Cluster {selectedCluster}
      <span class="count">({filteredPoints.length} papers)</span>
      <button onclick={() => (selectedCluster = null)}>Clear</button>
    </h2>
    <table>
      <thead>
        <tr>
          <th>Year</th>
          <th>Title</th>
          <th>Authors</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredPoints as p (p.doi)}
          <tr>
            <td>{p.pub_year}</td>
            <td>{p.title || p.doi}</td>
            <td>{p.authors}</td>
            <td>{p.source}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .container {
    display: flex;
    gap: 24px;
    align-items: flex-start;
    font-family: system-ui, sans-serif;
  }

  .scatter-wrapper {
    position: relative;
  }

  svg {
    display: block;
  }

  .bar-chart rect {
    transition: opacity 0.15s;
  }

  circle {
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .tooltip {
    position: absolute;
    pointer-events: none;
    width: 300px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 12px;
    font-size: 13px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .tooltip strong {
    display: block;
    margin-bottom: 4px;
  }

  .meta {
    display: flex;
    gap: 4px;
    margin-bottom: 6px;
  }

  .cluster, .tag {
    display: inline-block;
    font-size: 11px;
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
  }

  .authors {
    font-size: 12px;
    color: #333;
    margin-bottom: 4px;
  }

  .source {
    font-size: 11px;
    font-style: italic;
    color: #666;
    margin-bottom: 4px;
  }

  .keywords {
    font-size: 11px;
    color: #888;
    margin-bottom: 4px;
  }

  .tooltip p {
    margin: 6px 0 0;
    color: #555;
    line-height: 1.4;
    font-size: 12px;
  }

  .table-section {
    margin-top: 24px;
    font-family: system-ui, sans-serif;
  }

  .table-section h2 {
    font-size: 16px;
    margin-bottom: 8px;
  }

  .count {
    font-weight: normal;
    color: #888;
    font-size: 14px;
  }

  .table-section button {
    margin-left: 8px;
    font-size: 12px;
    padding: 2px 8px;
    cursor: pointer;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  th, td {
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid #eee;
  }

  th {
    font-weight: 600;
    border-bottom: 2px solid #ccc;
  }

  tbody tr:hover {
    background: #f8f8f8;
  }
</style>
