<script lang="ts">
  import { base } from '$app/paths';
  import { scaleLinear } from 'd3-scale';
  import data from '$lib/data/funnel.json';

  type Paper = {
    doi: string | null;
    title: string;
    pub_year: string;
    source: string;
    topics_reasoning?: string | null;
    backfill_source?: string;
  };

  type Stage = {
    key: string;
    label: string;
    count: number;
    would_drop: number;
    added: number;
    dropped: number;
    drop_reason: string | null;
    add_reason: string | null;
    add_sources: Record<string, number>;
    source: string;
    dropped_papers: Paper[];
    added_papers: Paper[];
  };

  type SideBranch = {
    label: string;
    with_pdf: number;
    parsed: number;
    of_total: number;
  };

  type FunnelData = {
    computed_at: string;
    topic_run: string;
    stages: Stage[];
    side_branch?: SideBranch;
  };

  const d = data as unknown as FunnelData;

  const margin = { top: 20, right: 120, bottom: 20, left: 16 } as const;
  const barAreaWidth = 700;
  const rowHeight = 50;
  const gapHeight = 60;
  const svgWidth = margin.left + barAreaWidth + margin.right;

  type Row = {
    stage: Stage;
    y: number;
    barWidth: number;
    pctOfInput: number;
    gapY: number | null;
  };

  let activeKey: string | null = $state(null);

  const maxCount: number = $derived.by(() => {
    let m = 0;
    for (const s of d.stages) if (s.count > m) m = s.count;
    return m === 0 ? 1 : m;
  });

  const inputCount: number = $derived(d.stages[0]?.count ?? 0);

  const xScale = $derived(
    scaleLinear().domain([0, maxCount]).range([0, barAreaWidth])
  );

  function hasGap(stage: Stage): boolean {
    return stage.dropped > 0 || stage.added > 0;
  }

  function isClickable(stage: Stage): boolean {
    return stage.dropped > 0 || stage.added > 0;
  }

  const rows: Row[] = $derived.by(() => {
    let y = 0;
    const out: Row[] = [];
    for (let i = 0; i < d.stages.length; i++) {
      const stage = d.stages[i];
      const pct = inputCount > 0 ? (stage.count / inputCount) * 100 : 0;
      const next = i < d.stages.length - 1 ? d.stages[i + 1] : null;
      const gapY: number | null =
        next !== null && hasGap(next) ? y + rowHeight : null;
      out.push({
        stage,
        y,
        barWidth: xScale(stage.count),
        pctOfInput: pct,
        gapY
      });
      y += rowHeight + (gapY !== null ? gapHeight : 0);
    }
    return out;
  });

  const svgHeight: number = $derived.by(() => {
    let h = margin.top + margin.bottom;
    for (let i = 0; i < d.stages.length; i++) {
      h += rowHeight;
      if (i < d.stages.length - 1 && hasGap(d.stages[i + 1])) {
        h += gapHeight;
      }
    }
    return h;
  });

  const activeStage: Stage | null = $derived(
    activeKey === null
      ? null
      : (d.stages.find((s) => s.key === activeKey) ?? null)
  );

  function formatComputed(iso: string): string {
    const i = iso.indexOf('T');
    return i === -1 ? iso : iso.slice(0, i);
  }

  function formatPct(p: number): string {
    return `${p.toFixed(1)}% of WoS`;
  }

  function formatSourceBreakdown(sources: Record<string, number>): string {
    const entries = Object.entries(sources);
    if (entries.length === 0) return '';
    return entries.map(([k, v]) => `${v} ${k}`).join(', ');
  }

  function formatSourceSummary(sources: Record<string, number>): string {
    const entries = Object.entries(sources);
    if (entries.length === 0) return '';
    return entries.map(([k, v]) => `${v} via ${k}`).join(' · ');
  }

  function toggleStage(stage: Stage): void {
    if (!isClickable(stage)) return;
    activeKey = activeKey === stage.key ? null : stage.key;
  }

  function onRowKeydown(e: KeyboardEvent, stage: Stage): void {
    if (!isClickable(stage)) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleStage(stage);
    }
  }
</script>

<div class="page">
  <h1>Paper coverage funnel</h1>
  <p class="header-links">
    <a href="{base}/annotations">/annotations &rarr;</a>
    <a href="{base}/runs">/runs &rarr;</a>
    <a href="{base}/compare">/compare &rarr;</a>
    <a href="{base}/prompts">/prompts &rarr;</a>
    <a href="{base}/about">/about &rarr;</a>
  </p>

  <p class="count">
    computed {formatComputed(d.computed_at)} &middot; topic run:
    <span class="mono">{d.topic_run}</span>
  </p>

  <section class="block">
    <h2>
      pipeline stages
      <span class="mono"
        >&middot; {d.stages[0]?.count ?? 0} &rarr; {d.stages[d.stages.length - 1]
          ?.count ?? 0}</span
      >
    </h2>
    <div class="scroll-x">
      <svg width={svgWidth} height={svgHeight}>
        <g transform="translate({margin.left},{margin.top})">
          {#each rows as row, rowIdx (row.stage.key)}
            {@const clickable = isClickable(row.stage)}
            {@const isActive = activeKey === row.stage.key}
            {@const hasAddedBadge = row.stage.added > 0 && row.stage.dropped === 0}
            {#if clickable}
              <g
                transform="translate(0,{row.y})"
                class="row-clickable"
                class:row-active={isActive}
                role="button"
                tabindex="0"
                aria-pressed={isActive}
                aria-label={`${row.stage.label}, ${row.stage.dropped} dropped, ${row.stage.added} recovered, toggle details`}
                onclick={() => toggleStage(row.stage)}
                onkeydown={(e) => onRowKeydown(e, row.stage)}
              >
                <rect
                  x={-margin.left}
                  y={0}
                  width={barAreaWidth + margin.left + margin.right}
                  height={rowHeight}
                  fill={isActive ? '#eaf1fa' : 'transparent'}
                />
                <rect
                  x={0}
                  y={8}
                  width={row.barWidth}
                  height={rowHeight - 22}
                  fill={isActive ? '#1a4a8a' : '#3b6fa8'}
                  opacity={isActive ? 0.95 : 0.82}
                  rx="2"
                />
                <text x={6} y={4} font-size="12" fill="#222" font-weight="600">
                  <tspan class="chevron" class:chevron-open={isActive}
                    >&#9656;</tspan
                  >
                  {row.stage.label}
                  <tspan fill="#666" font-weight="400"
                    >&middot; {row.stage.count}</tspan
                  >
                  {#if hasAddedBadge}
                    <tspan fill="#3a8a4a" font-weight="600">
                      &nbsp;+{row.stage.added}</tspan
                    >
                  {/if}
                </text>
                <text
                  x={row.barWidth + 8}
                  y={rowHeight / 2 + 4}
                  font-size="11"
                  fill="#666"
                  class="mono"
                >
                  {formatPct(row.pctOfInput)}
                </text>
              </g>
            {:else}
              <g transform="translate(0,{row.y})">
                <rect
                  x={0}
                  y={8}
                  width={row.barWidth}
                  height={rowHeight - 22}
                  fill="#3b6fa8"
                  opacity="0.82"
                  rx="2"
                />
                <text x={6} y={4} font-size="12" fill="#222" font-weight="600">
                  {row.stage.label}
                  <tspan fill="#666" font-weight="400"
                    >&middot; {row.stage.count}</tspan
                  >
                </text>
                <text
                  x={row.barWidth + 8}
                  y={rowHeight / 2 + 4}
                  font-size="11"
                  fill="#666"
                  class="mono"
                >
                  {formatPct(row.pctOfInput)}
                </text>
              </g>
            {/if}

            {#if row.gapY !== null}
              {@const nextStage = d.stages[rowIdx + 1]}
              <g transform="translate(0,{row.gapY})">
                {#if nextStage.dropped > 0}
                  <line
                    x1={12}
                    x2={12}
                    y1={2}
                    y2={gapHeight - 4}
                    stroke="#c97070"
                    stroke-width="1.5"
                    stroke-dasharray="3,3"
                  />
                  <text
                    x={22}
                    y={14}
                    font-size="11"
                    fill="#b04a4a"
                    font-weight="600"
                    class="mono"
                  >
                    &minus;{nextStage.dropped}
                  </text>
                  {#if nextStage.drop_reason}
                    <text x={22} y={30} font-size="11" fill="#888">
                      {nextStage.drop_reason}
                    </text>
                  {/if}
                {/if}

                {#if nextStage.added > 0}
                  {@const addX = barAreaWidth - 12}
                  <line
                    x1={addX}
                    x2={addX}
                    y1={2}
                    y2={gapHeight - 4}
                    stroke="#3a8a4a"
                    stroke-width="1.5"
                  />
                  <text
                    x={addX - 10}
                    y={14}
                    font-size="11"
                    fill="#3a8a4a"
                    font-weight="600"
                    class="mono"
                    text-anchor="end"
                  >
                    +{nextStage.added}
                  </text>
                  {#if nextStage.add_reason}
                    <text
                      x={addX - 10}
                      y={30}
                      font-size="11"
                      fill="#888"
                      text-anchor="end"
                    >
                      {nextStage.add_reason}
                    </text>
                  {/if}
                  {#if Object.keys(nextStage.add_sources).length > 0}
                    <text
                      x={addX - 10}
                      y={44}
                      font-size="10"
                      fill="#999"
                      text-anchor="end"
                      class="mono"
                    >
                      ({formatSourceBreakdown(nextStage.add_sources)})
                    </text>
                  {/if}
                {/if}
              </g>
            {/if}
          {/each}
        </g>
      </svg>
    </div>

    {#if activeStage && (activeStage.dropped_papers.length > 0 || activeStage.added_papers.length > 0)}
      <div class="detail-panel">
        <div class="detail-header">
          <span class="detail-title">{activeStage.label}</span>
        </div>

        {#if activeStage.added_papers.length > 0}
          <div class="detail-section">
            <h3 class="section-header added-header">
              Recovered ({activeStage.added_papers.length})
            </h3>
            {#if activeStage.add_reason}
              <div class="section-reason muted">{activeStage.add_reason}</div>
            {/if}
            {#if Object.keys(activeStage.add_sources).length > 0}
              <div class="section-summary mono">
                {formatSourceSummary(activeStage.add_sources)}
              </div>
            {/if}
            <ul class="paper-list">
              {#each activeStage.added_papers as paper, i (paper.doi ?? `${activeStage.key}-add-${i}`)}
                <li class="paper">
                  <div class="paper-title">
                    {paper.title}
                    {#if paper.backfill_source}
                      <span class="badge added-badge mono"
                        >via {paper.backfill_source}</span
                      >
                    {/if}
                  </div>
                  <div class="paper-meta mono">
                    <span>{paper.pub_year}</span>
                    <span class="sep">&middot;</span>
                    <span>{paper.source}</span>
                    <span class="sep">&middot;</span>
                    {#if paper.doi}
                      <a
                        class="doi-link"
                        href={`https://doi.org/${paper.doi}`}
                        target="_blank"
                        rel="noopener noreferrer">{paper.doi}</a
                      >
                    {:else}
                      <span class="muted">no DOI</span>
                    {/if}
                  </div>
                  {#if paper.topics_reasoning}
                    <details class="reasoning">
                      <summary>model reasoning</summary>
                      <pre>{paper.topics_reasoning}</pre>
                    </details>
                  {/if}
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if activeStage.dropped_papers.length > 0}
          <div class="detail-section">
            <h3 class="section-header dropped-header">
              Lost ({activeStage.dropped_papers.length})
            </h3>
            {#if activeStage.drop_reason}
              <div class="section-reason muted">{activeStage.drop_reason}</div>
            {/if}
            <ul class="paper-list">
              {#each activeStage.dropped_papers as paper, i (paper.doi ?? `${activeStage.key}-drop-${i}`)}
                <li class="paper">
                  <div class="paper-title">{paper.title}</div>
                  <div class="paper-meta mono">
                    <span>{paper.pub_year}</span>
                    <span class="sep">&middot;</span>
                    <span>{paper.source}</span>
                    <span class="sep">&middot;</span>
                    {#if paper.doi}
                      <a
                        class="doi-link"
                        href={`https://doi.org/${paper.doi}`}
                        target="_blank"
                        rel="noopener noreferrer">{paper.doi}</a
                      >
                    {:else}
                      <span class="muted">no DOI</span>
                    {/if}
                  </div>
                  {#if paper.topics_reasoning}
                    <details class="reasoning">
                      <summary>model reasoning</summary>
                      <pre>{paper.topics_reasoning}</pre>
                    </details>
                  {/if}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    {/if}
  </section>

  {#if d.side_branch}
    <section class="block">
      <h2>side branch &middot; full-text coverage</h2>
      <p class="side-note">{d.side_branch.label}</p>
      <table class="side-table">
        <tbody>
          <tr>
            <td>PDF fetched</td>
            <td class="num mono">{d.side_branch.with_pdf}</td>
            <td class="muted mono">/ {d.side_branch.of_total} with DOI</td>
          </tr>
          <tr>
            <td>Parsed to markdown</td>
            <td class="num mono">{d.side_branch.parsed}</td>
            <td class="muted mono">/ {d.side_branch.of_total} with DOI</td>
          </tr>
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

  .row-clickable {
    cursor: pointer;
  }

  .row-clickable:focus {
    outline: none;
  }

  .row-clickable:focus-visible :global(rect:first-of-type) {
    stroke: #1a4a8a;
    stroke-width: 1.5;
  }

  .chevron {
    fill: #888;
    font-size: 10px;
  }

  .chevron-open {
    fill: #1a4a8a;
  }

  .detail-panel {
    margin-top: 18px;
    border-top: 1px solid #eee;
    padding-top: 14px;
  }

  .detail-header {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 10px;
  }

  .detail-title {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    font-weight: 600;
    color: #333;
  }

  .detail-section {
    margin-top: 16px;
  }

  .detail-section:first-of-type {
    margin-top: 0;
  }

  .section-header {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    font-weight: 600;
    margin: 0 0 4px;
  }

  .added-header {
    color: #3a8a4a;
  }

  .dropped-header {
    color: #b04a4a;
  }

  .section-reason {
    margin-bottom: 6px;
  }

  .section-summary {
    color: #555;
    font-size: 12px;
    margin-bottom: 8px;
  }

  .paper-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .paper {
    padding: 10px 0;
    border-top: 1px solid #eee;
    font-size: 13px;
  }

  .paper:first-child {
    border-top: none;
  }

  .paper-title {
    font-weight: 600;
    color: #222;
    margin-bottom: 4px;
  }

  .badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: 6px;
    vertical-align: middle;
  }

  .added-badge {
    background: #e8f3ea;
    color: #3a8a4a;
    border: 1px solid #c7e0cc;
  }

  .paper-meta {
    color: #777;
    font-size: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: baseline;
  }

  .paper-meta .sep {
    color: #bbb;
  }

  .doi-link {
    color: #777;
    text-decoration: none;
  }

  .doi-link:hover {
    color: #1a4a8a;
    text-decoration: underline;
  }

  .reasoning {
    margin-top: 8px;
    font-size: 12px;
  }

  .reasoning summary {
    cursor: pointer;
    color: #777;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    user-select: none;
  }

  .reasoning summary:hover {
    color: #1a4a8a;
  }

  .reasoning pre {
    margin: 8px 0 0;
    padding: 10px 12px;
    background: #fafafa;
    border: 1px solid #eee;
    border-radius: 4px;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 400px;
    overflow-y: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: #333;
    line-height: 1.5;
  }

  .side-note {
    color: #777;
    font-size: 12px;
    margin: 0 0 10px;
  }

  .side-table {
    border-collapse: collapse;
    font-size: 13px;
  }

  .side-table td {
    padding: 4px 14px 4px 0;
  }

  .side-table td.num {
    text-align: right;
    color: #222;
  }

  .muted {
    color: #999;
    font-size: 12px;
  }
</style>
