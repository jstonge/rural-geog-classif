<script lang="ts">
  import Markdown from 'svelte-exmarkdown';
  import data from '$lib/data/compare.json';

  type PredEntry = {
    label: string | null;
    reasoning: string;
    picked?: string[];
    sections?: Record<string, string>;
  };

  type CompareRecord = {
    doi: string;
    title: string;
    abstract: string;
    annotator: string[];
    preds: Record<string, PredEntry>;
    ls_task_id: number | null;
    ls_url:     string | null;
  };

  type CompareBundle = { records?: CompareRecord[] };
  type CompareData = Record<string, CompareBundle>;

  const compareData = data as CompareData;
  const schemaKeys: string[] = Object.keys(compareData).sort();

  const ANNOTATOR = 'annotator' as const;

  function computeLabellers(recs: CompareRecord[]): string[] {
    const seen: Record<string, true> = {};
    for (const r of recs) {
      for (const k of Object.keys(r.preds ?? {})) seen[k] = true;
    }
    const runIds = Object.keys(seen).sort();
    return [ANNOTATOR, ...runIds];
  }

  function defaultSelections(schema: string): { a: string; b: string; c: string } {
    const recs = compareData[schema]?.records ?? [];
    const ls = computeLabellers(recs);
    const nonAnn = ls.filter((l) => l !== ANNOTATOR);
    return {
      a: ANNOTATOR,
      b: nonAnn[0] ?? ANNOTATOR,
      c: nonAnn[1] ?? nonAnn[0] ?? ANNOTATOR
    };
  }

  // Per-schema A/B/C selections, eagerly seeded with defaults for every known schema.
  // Switching schemas re-seeds the new schema's entry via setSchema(), so selections
  // always reset to the spec-defined defaults on switch.
  function seedSelections(): Record<string, { a: string; b: string; c: string }> {
    const out: Record<string, { a: string; b: string; c: string }> = {};
    for (const k of schemaKeys) out[k] = defaultSelections(k);
    return out;
  }

  let activeSchema: string = $state(schemaKeys[0] ?? '');
  let selectionsBySchema: Record<string, { a: string; b: string; c: string }> =
    $state(seedSelections());

  type CmSelection = {
    matrixIdx: number;
    row: string;
    col: string;
    rowLabeller: string;
    colLabeller: string;
  };
  let cmSelected: CmSelection | null = $state(null);

  const currentSelections = $derived(
    selectionsBySchema[activeSchema] ?? { a: ANNOTATOR, b: ANNOTATOR, c: ANNOTATOR }
  );

  const records: CompareRecord[] = $derived(
    compareData[activeSchema]?.records ?? []
  );

  const labellers: string[] = $derived(computeLabellers(records));

  const nonAnnotator: string[] = $derived(
    labellers.filter((l) => l !== ANNOTATOR)
  );

  function setSchema(schema: string) {
    // Always reset selections for the schema on switch, per spec.
    cmSelected = null;
    selectionsBySchema[schema] = defaultSelections(schema);
    activeSchema = schema;
  }

  function toggleCell(
    matrixIdx: number,
    row: string,
    col: string,
    count: number,
    rowLabeller: string,
    colLabeller: string
  ) {
    if (count === 0) return;
    if (
      cmSelected &&
      cmSelected.matrixIdx === matrixIdx &&
      cmSelected.row === row &&
      cmSelected.col === col &&
      cmSelected.rowLabeller === rowLabeller &&
      cmSelected.colLabeller === colLabeller
    ) {
      cmSelected = null;
      return;
    }
    cmSelected = { matrixIdx, row, col, rowLabeller, colLabeller };
  }

  function resolveLabel(rec: CompareRecord, labeller: string): string | null {
    if (labeller === ANNOTATOR) {
      return rec.annotator?.[0] ?? null;
    }
    return rec.preds?.[labeller]?.label ?? null;
  }

  function resolvePred(rec: CompareRecord, labeller: string): PredEntry | null {
    if (labeller === ANNOTATOR) return null;
    return rec.preds?.[labeller] ?? null;
  }

  // Short form for matrix headers — strips the leading "YYYY-MM-DD_{control}_" prefix
  // from run_ids so e.g. "2026-05-12_methods_v1_abstract" displays as "v1_abstract".
  function displayName(labeller: string): string {
    return labeller.replace(/^\d{4}-\d{2}-\d{2}_[^_]+_/, '');
  }

  // Three pairwise selections
  const pairs = $derived([
    { title: 'A x B', a: currentSelections.a, b: currentSelections.b },
    { title: 'A x C', a: currentSelections.a, b: currentSelections.c },
    { title: 'B x C', a: currentSelections.b, b: currentSelections.c }
  ]);

  type AgreementFilter = 'all' | 'agree' | 'any-disagree' | 'triple-disagree';

  const agreementFilters: { key: AgreementFilter; label: string }[] = [
    { key: 'all', label: 'all' },
    { key: 'agree', label: 'all three agree' },
    { key: 'any-disagree', label: 'any disagree' },
    { key: 'triple-disagree', label: 'triple-way disagree' }
  ];

  let activeAgreement: AgreementFilter = $state('any-disagree');

  function classifyTriple(a: string | null, b: string | null, c: string | null): AgreementFilter {
    const vals = [a, b, c];
    const distinct = new Set(vals.filter((v) => v != null));
    // If any is null, treat each null as its own bucket conceptually:
    //   - "agree" requires non-null and all equal
    //   - "triple-disagree" requires 3 distinct non-null values
    const nullCount = vals.filter((v) => v == null).length;
    if (nullCount === 0 && distinct.size === 1) return 'agree';
    if (nullCount === 0 && distinct.size === 3) return 'triple-disagree';
    return 'any-disagree';
  }

  // Check whether the current cell selection still matches the matrix at its stored
  // index — its row/col labellers must align with the live pair labellers.
  const cmSelectedValid = $derived.by(() => {
    if (!cmSelected) return false;
    const p = pairs[cmSelected.matrixIdx];
    if (!p) return false;
    return p.a === cmSelected.rowLabeller && p.b === cmSelected.colLabeller;
  });

  const filtered = $derived(
    records.filter((r) => {
      const a = resolveLabel(r, currentSelections.a);
      const b = resolveLabel(r, currentSelections.b);
      const c = resolveLabel(r, currentSelections.c);
      const klass = classifyTriple(a, b, c);
      let agreementOk = true;
      if (activeAgreement === 'all') agreementOk = true;
      else if (activeAgreement === 'agree') agreementOk = klass === 'agree';
      else if (activeAgreement === 'triple-disagree')
        agreementOk = klass === 'triple-disagree';
      else if (activeAgreement === 'any-disagree') {
        agreementOk = !(a != null && b != null && c != null && a === b && b === c);
      }
      if (!agreementOk) return false;
      if (cmSelected && cmSelectedValid) {
        const rowVal = resolveLabel(r, cmSelected.rowLabeller);
        const colVal = resolveLabel(r, cmSelected.colLabeller);
        if (rowVal !== cmSelected.row || colVal !== cmSelected.col) return false;
      }
      return true;
    })
  );

  function buildMatrix(la: string, lb: string, recs: CompareRecord[]) {
    const seen: Record<string, true> = {};
    const included: { a: string; b: string }[] = [];
    for (const r of recs) {
      const a = resolveLabel(r, la);
      const b = resolveLabel(r, lb);
      if (a == null || b == null) continue;
      seen[a] = true;
      seen[b] = true;
      included.push({ a, b });
    }
    const labels = Object.keys(seen).sort((x, y) =>
      x.toLowerCase().localeCompare(y.toLowerCase())
    );
    const idx: Record<string, number> = {};
    labels.forEach((l, i) => (idx[l] = i));
    const n = labels.length;
    const grid: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
    for (const { a, b } of included) {
      grid[idx[a]][idx[b]] += 1;
    }
    let max = 0;
    for (const row of grid) for (const v of row) if (v > max) max = v;
    return { labels, grid, max: max === 0 ? 1 : max, total: included.length };
  }

  const matrices = $derived(
    pairs.map((p) => ({ ...p, ...buildMatrix(p.a, p.b, records) }))
  );

  function cellStyle(count: number, isDiag: boolean, max: number): string {
    if (count === 0) return '';
    const ratio = count / max;
    const opacity = Math.max(0.15, ratio);
    const color = isDiag ? `rgba(46, 139, 87, ${opacity})` : `rgba(214, 69, 69, ${opacity})`;
    return `background: ${color};`;
  }

  function wordCount(s: string): number {
    return s && s.trim() ? s.trim().split(/\s+/).length : 0;
  }

  function buildPickedMarkdown(picked: string[], sections: Record<string, string>): string {
    return picked
      .map((h) => {
        const body = sections[h] ?? '';
        return `## ${h}\n\n${body}`;
      })
      .join('\n\n');
  }

  // For a given record, find non-annotator labellers among the three selectors
  // that have picked/sections, deduped, in display order.
  function pickedBlocks(rec: CompareRecord, sels: string[]): { run: string; md: string }[] {
    const seen: Record<string, true> = {};
    const out: { run: string; md: string }[] = [];
    for (const s of sels) {
      if (s === ANNOTATOR) continue;
      if (seen[s]) continue;
      seen[s] = true;
      const p = resolvePred(rec, s);
      if (p && p.picked && p.picked.length > 0 && p.sections) {
        out.push({ run: s, md: buildPickedMarkdown(p.picked, p.sections) });
      }
    }
    return out;
  }

  // Reasoning collapsibles, one per non-annotator selector (deduped).
  function reasoningBlocks(
    rec: CompareRecord,
    sels: string[]
  ): { run: string; reasoning: string }[] {
    const seen: Record<string, true> = {};
    const out: { run: string; reasoning: string }[] = [];
    for (const s of sels) {
      if (s === ANNOTATOR) continue;
      if (seen[s]) continue;
      seen[s] = true;
      const p = resolvePred(rec, s);
      if (p && p.reasoning) {
        out.push({ run: s, reasoning: p.reasoning });
      }
    }
    return out;
  }

  // Highlight a label cell when its label differs from at least one of the others.
  function isMismatch(self: string | null, others: (string | null)[]): boolean {
    for (const o of others) {
      if (o !== self) return true;
    }
    return false;
  }
</script>

<div class="page">
  <h1>Compare labellers</h1>
  <p class="about-link">
    <a href="/runs">/runs &rarr;</a>
    <a href="/about">/about &rarr;</a>
  </p>

  {#if schemaKeys.length === 0}
    <p class="muted empty-state">
      No compare data &mdash; run <code>export_compare.py</code> first.
    </p>
  {:else}
    <p class="count">
      {records.length} records under schema {activeSchema} across {labellers.length} labellers
    </p>

    <div class="schema-row">
      <span class="filter-label">Schema:</span>
      <div class="filters">
        {#each schemaKeys as s (s)}
          <button
            class="chip"
            class:active={activeSchema === s}
            onclick={() => setSchema(s)}
          >
            {s}
          </button>
        {/each}
      </div>
    </div>

    <section class="selectors">
      <div class="selector">
        <label for="sel-a">A</label>
        <select id="sel-a" bind:value={currentSelections.a}>
          {#each labellers as l (l)}
            <option value={l}>{l}</option>
          {/each}
        </select>
      </div>
      <div class="selector">
        <label for="sel-b">B</label>
        <select id="sel-b" bind:value={currentSelections.b}>
          {#each labellers as l (l)}
            <option value={l}>{l}</option>
          {/each}
        </select>
      </div>
      <div class="selector">
        <label for="sel-c">C</label>
        <select id="sel-c" bind:value={currentSelections.c}>
          {#each labellers as l (l)}
            <option value={l}>{l}</option>
          {/each}
        </select>
      </div>
    </section>

  {#snippet matrixView(m: (typeof matrices)[number], mi: number)}
    <div class="matrix-wrap">
      <div class="matrix-title">{m.title}</div>
      <div class="matrix-sub">
        <span class="mono">{displayName(m.a)}</span>
        <span class="x">x</span>
        <span class="mono">{displayName(m.b)}</span>
      </div>
      {#if m.labels.length === 0}
        <p class="muted">No overlapping labelled records.</p>
      {:else}
        <table class="cm">
          <caption>n = {m.total}</caption>
          <thead>
            <tr>
              <th class="cm-corner" scope="col">
                <span class="cm-axis-row">{displayName(m.a)}</span>
                <span class="cm-axis-col">{displayName(m.b)}</span>
              </th>
              {#each m.labels as col (col)}
                <th scope="col">{col}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each m.labels as row, ri (row)}
              <tr>
                <th scope="row">{row}</th>
                {#each m.labels as col, ci (col)}
                  {@const count = m.grid[ri][ci]}
                  {@const isActive =
                    cmSelected !== null &&
                    cmSelectedValid &&
                    cmSelected.matrixIdx === mi &&
                    cmSelected.row === row &&
                    cmSelected.col === col}
                  <td
                    class:cm-zero={count === 0}
                    class:cm-active={isActive}
                    style={cellStyle(count, ri === ci, m.max)}
                  >
                    {#if count !== 0}
                      <button
                        type="button"
                        class="cm-cell-btn"
                        aria-pressed={isActive}
                        aria-label={`${displayName(m.a)} ${row} by ${displayName(m.b)} ${col}: ${count}`}
                        onclick={() => toggleCell(mi, row, col, count, m.a, m.b)}
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
    </div>
  {/snippet}

  <section class="matrices">
    {#each matrices as m, mi (m.title)}
      {@render matrixView(m, mi)}
    {/each}
  </section>

  <div class="filter-row">
    <span class="filter-label">Show</span>
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
    {#if cmSelected !== null}
      <button class="chip clear-cell" onclick={() => (cmSelected = null)}>
        Clear cell selection
      </button>
    {/if}
    <span class="filter-count">{filtered.length} / {records.length}</span>
  </div>

  {#if cmSelected !== null && cmSelectedValid}
    <p class="cell-filter-line">
      cell filter:
      <span class="mono">{displayName(cmSelected.rowLabeller)}({cmSelected.row})</span>
      <span class="x">x</span>
      <span class="mono">{displayName(cmSelected.colLabeller)}({cmSelected.col})</span>
      <span class="cell-filter-matrix">
        [matrix {pairs[cmSelected.matrixIdx]?.title ?? ''}]
      </span>
    </p>
  {/if}

  {#each filtered as r (r.doi)}
    {@const la = resolveLabel(r, currentSelections.a)}
    {@const lb = resolveLabel(r, currentSelections.b)}
    {@const lc = resolveLabel(r, currentSelections.c)}
    {@const picked = pickedBlocks(r, [currentSelections.b, currentSelections.c])}
    {@const reasonings = reasoningBlocks(r, [currentSelections.a, currentSelections.b, currentSelections.c])}
    <article class="card">
      <header class="card-header">
        <a class="title" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer noopener">
          {r.title || r.doi}
        </a>
        {#if r.ls_url}
          <a class="ls-link" href={r.ls_url} target="_blank" rel="noreferrer noopener">↗ Label Studio</a>
        {/if}
      </header>

      <div class="labels">
        <div class="label-cell" class:disagree={isMismatch(la, [lb, lc])}>
          <div class="label-key">A &middot; <span class="mono">{currentSelections.a}</span></div>
          <div class="label-val">{la ?? '—'}</div>
        </div>
        <div class="label-cell" class:disagree={isMismatch(lb, [la, lc])}>
          <div class="label-key">B &middot; <span class="mono">{currentSelections.b}</span></div>
          <div class="label-val">{lb ?? '—'}</div>
        </div>
        <div class="label-cell" class:disagree={isMismatch(lc, [la, lb])}>
          <div class="label-key">C &middot; <span class="mono">{currentSelections.c}</span></div>
          <div class="label-val">{lc ?? '—'}</div>
        </div>
      </div>

      {#if r.abstract && r.abstract.trim() !== ''}
        <section class="abstract">
          <h3>Abstract</h3>
          <p>{r.abstract}</p>
        </section>
      {/if}

      {#if picked.length > 0}
        <section class="picked">
          <h3>Picked sections</h3>
          {#each picked as p (p.run)}
            <div class="picked-block">
              <div class="picked-source mono">{p.run}</div>
              <div class="markdown">
                <Markdown md={p.md} />
              </div>
            </div>
          {/each}
        </section>
      {/if}

      {#each reasonings as rb (rb.run)}
        <details>
          <summary>
            Reasoning &middot; <span class="mono">{rb.run}</span>
            {#if wordCount(rb.reasoning) > 0}
              <span class="word-count">{wordCount(rb.reasoning)} words</span>
            {/if}
          </summary>
          <div class="markdown">
            <Markdown md={rb.reasoning} />
          </div>
        </details>
      {/each}
    </article>
  {/each}
  {/if}
</div>

<style>
  .page {
    font-family: system-ui, sans-serif;
    max-width: 1550px;
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
    font-size: 11px;
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

  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .schema-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 12px 0 12px;
    flex-wrap: wrap;
  }

  .empty-state {
    margin: 20px 0;
    font-size: 13px;
  }

  .empty-state code {
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .selectors {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 12px 0 18px;
  }

  .selector {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid #e2e2e2;
    border-radius: 6px;
    background: #fafafa;
    padding: 6px 10px;
  }

  .selector label {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #888;
  }

  .selector select {
    flex: 1;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10px;
    padding: 4px 6px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
    color: #222;
    min-width: 0;
  }

  .matrices {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin: 0 0 18px;
  }

  .matrix-wrap {
    border: 1px solid #eee;
    border-radius: 6px;
    padding: 10px;
    background: white;
    overflow-x: auto;
  }

  .matrix-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #444;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
    margin-bottom: 2px;
  }

  .matrix-sub {
    font-size: 11px;
    color: #777;
    margin-bottom: 8px;
    display: flex;
    gap: 6px;
    align-items: baseline;
    flex-wrap: wrap;
  }

  .matrix-sub .x {
    color: #aaa;
  }

  table.cm {
    border-collapse: collapse;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 9px;
    color: #222;
  }

  table.cm caption {
    caption-side: bottom;
    text-align: left;
    font-size: 9px;
    color: #777;
    padding-top: 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  table.cm th,
  table.cm td {
    border: 1px solid #e2e2e2;
    width: 44px;
    height: 32px;
    text-align: center;
    vertical-align: middle;
    padding: 2px 4px;
  }

  table.cm td {
    padding: 0;
  }

  table.cm td.cm-zero {
    cursor: default;
    padding: 2px 4px;
  }

  table.cm td.cm-active {
    outline: 2px solid #111;
    outline-offset: -2px;
    font-weight: bold;
  }

  .cm-cell-btn {
    all: unset;
    display: block;
    width: 100%;
    height: 100%;
    min-height: 32px;
    box-sizing: border-box;
    padding: 2px 4px;
    text-align: center;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }

  .cm-cell-btn:focus-visible {
    outline: 2px solid #1a4a8a;
    outline-offset: -2px;
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
    padding-right: 6px;
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
    min-width: 60px;
  }

  .filter-count {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: #888;
    margin-left: auto;
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

  .chip.clear-cell {
    border-color: #b06060;
    color: #b06060;
  }

  .chip.clear-cell:hover {
    background: #fdecec;
  }

  .cell-filter-line {
    margin: 0 0 10px;
    font-size: 11px;
    color: #555;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    display: flex;
    gap: 6px;
    align-items: baseline;
    flex-wrap: wrap;
  }

  .cell-filter-line .x {
    color: #aaa;
  }

  .cell-filter-matrix {
    color: #888;
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

  .ls-link {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    padding: 2px 8px;
    border: 1px solid #ccd;
    border-radius: 999px;
    background: #eef;
    color: #1a4a8a;
    text-decoration: none;
    white-space: nowrap;
    flex-shrink: 0;
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

  .picked-block {
    margin-bottom: 12px;
  }

  .picked-source {
    font-size: 11px;
    color: #888;
    margin-bottom: 4px;
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

  @media (max-width: 800px) {
    .selectors,
    .matrices {
      grid-template-columns: 1fr;
    }
  }
</style>
