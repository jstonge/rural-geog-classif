<script lang="ts">
  import Markdown from 'svelte-exmarkdown';
  import { base } from '$app/paths';
  import data from '$lib/data/compare.json';

  type PredEntry = {
    labels: string[];
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
    docling_url: string | null;
  };

  type CompareBundle = { multi_label?: boolean; records?: CompareRecord[] };
  type CompareData = Record<string, Record<string, CompareBundle>>;

  const compareData = data as unknown as CompareData;
  const taskKeys: string[] = Object.keys(compareData).sort();

  const ANNOTATOR = 'annotator' as const;

  function schemasFor(task: string): string[] {
    return Object.keys(compareData[task] ?? {}).sort();
  }

  function computeLabellers(recs: CompareRecord[]): string[] {
    const seen: Record<string, true> = {};
    for (const r of recs) {
      for (const k of Object.keys(r.preds ?? {})) seen[k] = true;
    }
    const runIds = Object.keys(seen).sort();
    return [ANNOTATOR, ...runIds];
  }

  function defaultSelections(task: string, schema: string): { a: string; b: string; c: string } {
    const recs = compareData[task]?.[schema]?.records ?? [];
    const ls = computeLabellers(recs);
    const nonAnn = ls.filter((l) => l !== ANNOTATOR);
    return {
      a: ANNOTATOR,
      b: nonAnn[0] ?? ANNOTATOR,
      c: nonAnn[1] ?? nonAnn[0] ?? ANNOTATOR
    };
  }

  // Per-(task,schema) A/B/C selections, eagerly seeded with defaults for every known
  // task/schema combo. Switching tasks or schemas re-seeds the entry via setTask/setSchema,
  // so selections always reset to the spec-defined defaults on switch.
  function seedSelections(): Record<string, Record<string, { a: string; b: string; c: string }>> {
    const out: Record<string, Record<string, { a: string; b: string; c: string }>> = {};
    for (const t of taskKeys) {
      out[t] = {};
      for (const s of schemasFor(t)) {
        out[t][s] = defaultSelections(t, s);
      }
    }
    return out;
  }

  const initialTask: string = taskKeys[0] ?? '';
  const initialSchema: string = schemasFor(initialTask)[0] ?? '';

  let activeTask: string = $state(initialTask);
  let activeSchema: string = $state(initialSchema);
  let selectionsByTaskSchema: Record<string, Record<string, { a: string; b: string; c: string }>> =
    $state(seedSelections());

  type CmSelection = {
    matrixIdx: number;
    row: string;
    col: string;
    rowLabeller: string;
    colLabeller: string;
  };
  let cmSelected: CmSelection | null = $state(null);

  // Multi-label cell selection: clicking a label in the per-label table filters
  // to papers where that label is in the chosen bucket (both, onlyA, onlyB).
  type MlSelection = {
    matrixIdx: number;
    label: string;
    bucket: 'both' | 'onlyA' | 'onlyB';
    rowLabeller: string;
    colLabeller: string;
  };
  let mlSelected: MlSelection | null = $state(null);

  const schemaKeys: string[] = $derived(schemasFor(activeTask));

  const currentSelections = $derived(
    selectionsByTaskSchema[activeTask]?.[activeSchema] ?? {
      a: ANNOTATOR,
      b: ANNOTATOR,
      c: ANNOTATOR
    }
  );

  const records: CompareRecord[] = $derived(
    compareData[activeTask]?.[activeSchema]?.records ?? []
  );

  const multiLabel: boolean = $derived(
    compareData[activeTask]?.[activeSchema]?.multi_label === true
  );

  const labellers: string[] = $derived(computeLabellers(records));

  const nonAnnotator: string[] = $derived(
    labellers.filter((l) => l !== ANNOTATOR)
  );

  function setSchema(schema: string) {
    // Always reset selections for the schema on switch, per spec.
    cmSelected = null;
    if (!selectionsByTaskSchema[activeTask]) selectionsByTaskSchema[activeTask] = {};
    selectionsByTaskSchema[activeTask][schema] = defaultSelections(activeTask, schema);
    activeSchema = schema;
  }

  function setTask(newTask: string) {
    // Switching tasks resets the schema to the first one under the new task,
    // which in turn re-seeds A/B/C defaults and clears cmSelected via setSchema.
    activeTask = newTask;
    const firstSchema = schemasFor(newTask)[0] ?? '';
    setSchema(firstSchema);
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

  function resolveLabels(rec: CompareRecord, labeller: string): string[] {
    if (labeller === ANNOTATOR) {
      return rec.annotator ?? [];
    }
    return rec.preds?.[labeller]?.labels ?? [];
  }

  function resolveLabel(rec: CompareRecord, labeller: string): string | null {
    return resolveLabels(rec, labeller)[0] ?? null;
  }

  function setsEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    const sa = new Set(a);
    for (const x of b) if (!sa.has(x)) return false;
    return true;
  }

  function resolvePred(rec: CompareRecord, labeller: string): PredEntry | null {
    if (labeller === ANNOTATOR) return null;
    return rec.preds?.[labeller] ?? null;
  }

  // Short form for matrix headers — strips the leading date (and optional HHMM)
  // plus the control name, so e.g. "2026-05-13_1508_methods_v1_abstract"
  // (or the older "2026-05-12_methods_v1_abstract") displays as "v1_abstract".
  function displayName(labeller: string): string {
    return labeller.replace(/^\d{4}-\d{2}-\d{2}(_\d{4})?_[^_]+_/, '');
  }

  // Pairwise matrices — drop pairs where both selectors point at the same
  // labeller AND dedupe identical (a, b) pairs that arise when C falls back
  // to B (e.g. one-model schemas where only annotator + one run exist).
  const pairs = $derived.by(() => {
    const all = [
      { title: 'A x B', a: currentSelections.a, b: currentSelections.b },
      { title: 'A x C', a: currentSelections.a, b: currentSelections.c },
      { title: 'B x C', a: currentSelections.b, b: currentSelections.c }
    ];
    const seen = new Set<string>();
    return all.filter((p) => {
      if (p.a === p.b) return false;
      const key = `${p.a}${p.b}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  });

  type AgreementFilter = 'all' | 'agree' | 'any-disagree' | 'triple-disagree';

  const agreementFilters: { key: AgreementFilter; label: string }[] = [
    { key: 'all', label: 'all' },
    { key: 'agree', label: 'all three agree' },
    { key: 'any-disagree', label: 'any disagree' },
    { key: 'triple-disagree', label: 'triple-way disagree' }
  ];

  let activeAgreement: AgreementFilter = $state('any-disagree');

  // Set-based agreement classifier — works for both single-label (length-1
  // arrays) and multi-label (length-0+) tasks. An empty array is treated as
  // "missing" and forces 'any-disagree' so we don't claim agreement when one
  // labeller has no data.
  function classifyTriple(a: string[], b: string[], c: string[]): AgreementFilter {
    if (!a.length || !b.length || !c.length) return 'any-disagree';
    const ab = setsEqual(a, b);
    const ac = setsEqual(a, c);
    const bc = setsEqual(b, c);
    if (ab && ac && bc) return 'agree';
    if (!ab && !ac && !bc) return 'triple-disagree';
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

  const mlSelectedValid = $derived.by(() => {
    if (!mlSelected) return false;
    const p = pairs[mlSelected.matrixIdx];
    if (!p) return false;
    return p.a === mlSelected.rowLabeller && p.b === mlSelected.colLabeller;
  });

  const filtered = $derived(
    records.filter((r) => {
      const a = resolveLabels(r, currentSelections.a);
      const b = resolveLabels(r, currentSelections.b);
      const c = resolveLabels(r, currentSelections.c);
      const klass = classifyTriple(a, b, c);
      let agreementOk = true;
      if (activeAgreement === 'all') agreementOk = true;
      else if (activeAgreement === 'agree') agreementOk = klass === 'agree';
      else if (activeAgreement === 'triple-disagree')
        agreementOk = klass === 'triple-disagree';
      else if (activeAgreement === 'any-disagree') {
        agreementOk = !(a.length && b.length && c.length && setsEqual(a, b) && setsEqual(b, c));
      }
      if (!agreementOk) return false;
      // Cell-click filter (single-label confusion matrix only).
      if (!multiLabel && cmSelected && cmSelectedValid) {
        const rowVal = resolveLabel(r, cmSelected.rowLabeller);
        const colVal = resolveLabel(r, cmSelected.colLabeller);
        if (rowVal !== cmSelected.row || colVal !== cmSelected.col) return false;
      }
      // Per-label disagree filter (multi-label).
      if (multiLabel && mlSelected && mlSelectedValid) {
        const sa = new Set(resolveLabels(r, mlSelected.rowLabeller));
        const sb = new Set(resolveLabels(r, mlSelected.colLabeller));
        const inA = sa.has(mlSelected.label);
        const inB = sb.has(mlSelected.label);
        if (mlSelected.bucket === 'both' && !(inA && inB)) return false;
        if (mlSelected.bucket === 'onlyA' && !(inA && !inB)) return false;
        if (mlSelected.bucket === 'onlyB' && !(inB && !inA)) return false;
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

  // Per-label agreement table for multi-label tasks. For each label that
  // appears in either labeller's predictions across the dataset, count:
  //   both  — papers where A and B both picked it
  //   onlyA — A picked but B didn't
  //   onlyB — B picked but A didn't
  // Rows are sorted by support (both + onlyA + onlyB) descending.
  function buildPerLabel(la: string, lb: string, recs: CompareRecord[]) {
    const counts: Record<string, { both: number; onlyA: number; onlyB: number }> = {};
    let n = 0;
    for (const r of recs) {
      const sa = new Set(resolveLabels(r, la));
      const sb = new Set(resolveLabels(r, lb));
      if (sa.size === 0 && sb.size === 0) continue;
      n++;
      const all = new Set<string>([...sa, ...sb]);
      for (const l of all) {
        if (!counts[l]) counts[l] = { both: 0, onlyA: 0, onlyB: 0 };
        if (sa.has(l) && sb.has(l)) counts[l].both++;
        else if (sa.has(l)) counts[l].onlyA++;
        else counts[l].onlyB++;
      }
    }
    const rows = Object.entries(counts).map(([label, c]) => ({
      label,
      both: c.both,
      onlyA: c.onlyA,
      onlyB: c.onlyB,
      total: c.both + c.onlyA + c.onlyB
    }));
    rows.sort((x, y) => y.total - x.total || x.label.localeCompare(y.label));
    let max = 0;
    for (const row of rows) {
      max = Math.max(max, row.both, row.onlyA, row.onlyB);
    }
    return { rows, total: n, max: max === 0 ? 1 : max };
  }

  const mlMatrices = $derived(
    pairs.map((p) => ({ ...p, ...buildPerLabel(p.a, p.b, records) }))
  );

  function toggleMlCell(
    matrixIdx: number,
    label: string,
    bucket: 'both' | 'onlyA' | 'onlyB',
    count: number,
    rowLabeller: string,
    colLabeller: string
  ): void {
    if (count === 0) return;
    if (
      mlSelected &&
      mlSelected.matrixIdx === matrixIdx &&
      mlSelected.label === label &&
      mlSelected.bucket === bucket &&
      mlSelected.rowLabeller === rowLabeller &&
      mlSelected.colLabeller === colLabeller
    ) {
      mlSelected = null;
      return;
    }
    mlSelected = { matrixIdx, label, bucket, rowLabeller, colLabeller };
  }

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

  function isMismatchSet(self: string[], others: string[][]): boolean {
    for (const o of others) {
      if (!setsEqual(self, o)) return true;
    }
    return false;
  }
</script>

<div class="page">
  <h1>Compare labellers</h1>
  <p class="about-link">
    <a href="{base}/runs">/runs &rarr;</a>
    <a href="{base}/prompts">/prompts &rarr;</a>
    <a href="{base}/annotations">/annotations &rarr;</a>
    <a href="{base}/about">/about &rarr;</a>
  </p>

  {#if taskKeys.length === 0}
    <p class="muted empty-state">
      No compare data &mdash; run <code>export_compare.py</code> first.
    </p>
  {:else}
    <p class="count">
      {records.length} records under {activeTask} / {activeSchema} across {labellers.length} labellers
    </p>

    <div class="schema-row">
      <span class="filter-label">Task:</span>
      <div class="filters">
        {#each taskKeys as t (t)}
          <button
            class="chip"
            class:active={activeTask === t}
            onclick={() => setTask(t)}
          >
            {t}
          </button>
        {/each}
      </div>
    </div>

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

  {#snippet perLabelView(m: (typeof mlMatrices)[number], mi: number)}
    <div class="matrix-wrap">
      <div class="matrix-title">{m.title}</div>
      <div class="matrix-sub">
        <span class="mono">{displayName(m.a)}</span>
        <span class="x">x</span>
        <span class="mono">{displayName(m.b)}</span>
      </div>
      {#if m.rows.length === 0}
        <p class="muted">No overlapping labelled records.</p>
      {:else}
        <table class="cm pl">
          <caption>n = {m.total}</caption>
          <thead>
            <tr>
              <th scope="col" class="pl-label-col">label</th>
              <th scope="col" class="pl-num">both</th>
              <th scope="col" class="pl-num">only A</th>
              <th scope="col" class="pl-num">only B</th>
            </tr>
          </thead>
          <tbody>
            {#each m.rows as row (row.label)}
              {@const bothActive =
                mlSelected !== null &&
                mlSelectedValid &&
                mlSelected.matrixIdx === mi &&
                mlSelected.label === row.label &&
                mlSelected.bucket === 'both'}
              {@const onlyAActive =
                mlSelected !== null &&
                mlSelectedValid &&
                mlSelected.matrixIdx === mi &&
                mlSelected.label === row.label &&
                mlSelected.bucket === 'onlyA'}
              {@const onlyBActive =
                mlSelected !== null &&
                mlSelectedValid &&
                mlSelected.matrixIdx === mi &&
                mlSelected.label === row.label &&
                mlSelected.bucket === 'onlyB'}
              <tr>
                <th scope="row" class="pl-label-col">{row.label}</th>
                <td
                  class:cm-zero={row.both === 0}
                  class:cm-active={bothActive}
                  style={cellStyle(row.both, true, m.max)}
                >
                  {#if row.both !== 0}
                    <button
                      type="button"
                      class="cm-cell-btn"
                      aria-pressed={bothActive}
                      onclick={() => toggleMlCell(mi, row.label, 'both', row.both, m.a, m.b)}
                    >
                      {row.both}
                    </button>
                  {/if}
                </td>
                <td
                  class:cm-zero={row.onlyA === 0}
                  class:cm-active={onlyAActive}
                  style={cellStyle(row.onlyA, false, m.max)}
                >
                  {#if row.onlyA !== 0}
                    <button
                      type="button"
                      class="cm-cell-btn"
                      aria-pressed={onlyAActive}
                      onclick={() => toggleMlCell(mi, row.label, 'onlyA', row.onlyA, m.a, m.b)}
                    >
                      {row.onlyA}
                    </button>
                  {/if}
                </td>
                <td
                  class:cm-zero={row.onlyB === 0}
                  class:cm-active={onlyBActive}
                  style={cellStyle(row.onlyB, false, m.max)}
                >
                  {#if row.onlyB !== 0}
                    <button
                      type="button"
                      class="cm-cell-btn"
                      aria-pressed={onlyBActive}
                      onclick={() => toggleMlCell(mi, row.label, 'onlyB', row.onlyB, m.a, m.b)}
                    >
                      {row.onlyB}
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  {/snippet}

  <section class="matrices">
    {#if multiLabel}
      {#each mlMatrices as m, mi (m.title)}
        {@render perLabelView(m, mi)}
      {/each}
    {:else}
      {#each matrices as m, mi (m.title)}
        {@render matrixView(m, mi)}
      {/each}
    {/if}
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
    {#if !multiLabel && cmSelected !== null}
      <button class="chip clear-cell" onclick={() => (cmSelected = null)}>
        Clear cell selection
      </button>
    {/if}
    {#if multiLabel && mlSelected !== null}
      <button class="chip clear-cell" onclick={() => (mlSelected = null)}>
        Clear cell selection
      </button>
    {/if}
    <span class="filter-count">{filtered.length} / {records.length}</span>
  </div>

  {#if !multiLabel && cmSelected !== null && cmSelectedValid}
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

  {#if multiLabel && mlSelected !== null && mlSelectedValid}
    <p class="cell-filter-line">
      label filter:
      <span class="mono">{mlSelected.label}</span>
      <span class="cell-filter-matrix">
        — {mlSelected.bucket === 'both'
          ? `both ${displayName(mlSelected.rowLabeller)} and ${displayName(mlSelected.colLabeller)}`
          : mlSelected.bucket === 'onlyA'
            ? `only ${displayName(mlSelected.rowLabeller)}`
            : `only ${displayName(mlSelected.colLabeller)}`}
        [matrix {pairs[mlSelected.matrixIdx]?.title ?? ''}]
      </span>
    </p>
  {/if}

  {#each filtered as r (r.doi)}
    {@const la = resolveLabels(r, currentSelections.a)}
    {@const lb = resolveLabels(r, currentSelections.b)}
    {@const lc = resolveLabels(r, currentSelections.c)}
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
        {#if r.docling_url}
          <a class="ls-link" href={r.docling_url} target="_blank" rel="noreferrer noopener">↗ Full text</a>
        {/if}
      </header>

      <div class="labels">
        <div class="label-cell" class:disagree={isMismatchSet(la, [lb, lc])}>
          <div class="label-key">A &middot; <span class="mono">{currentSelections.a}</span></div>
          <div class="label-val">
            {#if la.length === 0}
              —
            {:else}
              {#each la as v (v)}<span class="label-chip">{v}</span>{/each}
            {/if}
          </div>
        </div>
        <div class="label-cell" class:disagree={isMismatchSet(lb, [la, lc])}>
          <div class="label-key">B &middot; <span class="mono">{currentSelections.b}</span></div>
          <div class="label-val">
            {#if lb.length === 0}
              —
            {:else}
              {#each lb as v (v)}<span class="label-chip">{v}</span>{/each}
            {/if}
          </div>
        </div>
        <div class="label-cell" class:disagree={isMismatchSet(lc, [la, lb])}>
          <div class="label-key">C &middot; <span class="mono">{currentSelections.c}</span></div>
          <div class="label-val">
            {#if lc.length === 0}
              —
            {:else}
              {#each lc as v (v)}<span class="label-chip">{v}</span>{/each}
            {/if}
          </div>
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
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .label-chip {
    display: inline-block;
    padding: 1px 7px;
    background: #fff;
    border: 1px solid #d8d8d8;
    border-radius: 999px;
    font-size: 11px;
    color: #333;
  }

  table.cm.pl .pl-label-col {
    text-align: left;
    padding: 4px 10px;
    font-weight: 500;
    color: #444;
    min-width: 160px;
  }

  table.cm.pl td.pl-num,
  table.cm.pl th.pl-num {
    text-align: right;
    padding-right: 10px;
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
