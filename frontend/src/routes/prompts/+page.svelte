<script lang="ts">
  import { base } from '$app/paths';
  import data from '$lib/data/runs.json';

  type Run = {
    run_id: string;
    task?: string | null;
    schema?: string | null;
    strategy?: string | null;
    saved_at?: string;
    model?: string;
    thinking?: boolean;
    max_tokens?: number;
    examples_used?: string[];
    prompt?: string;
    [key: string]: unknown;
  };

  const LEGACY = 'legacy' as const;

  const rawRuns: Run[] = (data as Run[]) ?? [];

  function schemaOf(r: Run): string {
    const s = r.schema;
    if (s == null || s === '') return LEGACY;
    return s;
  }

  function compareSavedDesc(a: Run, b: Run): number {
    const av = a.saved_at ?? '';
    const bv = b.saved_at ?? '';
    if (av === bv) return 0;
    if (av === '') return 1;
    if (bv === '') return -1;
    return av < bv ? 1 : -1;
  }

  type Group = { schema: string; runs: Run[] };

  const groups: Group[] = (() => {
    const buckets: Record<string, Run[]> = {};
    for (const r of rawRuns) {
      const s = schemaOf(r);
      (buckets[s] ??= []).push(r);
    }
    const keys = Object.keys(buckets).sort((a, b) => {
      if (a === LEGACY && b !== LEGACY) return 1;
      if (b === LEGACY && a !== LEGACY) return -1;
      return a.localeCompare(b);
    });
    return keys.map((k) => ({
      schema: k,
      runs: buckets[k].slice().sort(compareSavedDesc)
    }));
  })();

  const totalRuns = rawRuns.length;
  const totalSchemas = groups.length;

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
    push('saved_at', r.saved_at);
    return out;
  }

  function exampleCount(r: Run): number {
    return Array.isArray(r.examples_used) ? r.examples_used.length : 0;
  }

  function hasPrompt(r: Run): boolean {
    return typeof r.prompt === 'string' && r.prompt.trim() !== '';
  }

  let copiedRunId: string | null = $state(null);
  let copyTimeout: ReturnType<typeof setTimeout> | null = null;

  async function copyPrompt(runId: string, prompt: string): Promise<void> {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(prompt);
      copiedRunId = runId;
      if (copyTimeout) clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => {
        copiedRunId = null;
      }, 1500);
    } catch {
      // ignore — clipboard may be unavailable
    }
  }
</script>

<div class="page">
  <h1>Prompts</h1>
  <p class="header-links">
    <a href="{base}/runs">/runs &rarr;</a>
    <a href="{base}/compare">/compare &rarr;</a>
    <a href="{base}/annotations">/annotations &rarr;</a>
  </p>

  {#if totalRuns === 0}
    <p class="empty">No runs yet.</p>
  {:else}
    <p class="count">
      {totalRuns} run{totalRuns === 1 ? '' : 's'} across {totalSchemas} schema{totalSchemas === 1 ? '' : 's'}
    </p>

    {#each groups as g (g.schema)}
      <section class="schema-block">
        <h2 class="schema-heading">
          <span class="schema-name">{g.schema}</span>
          <span class="schema-count">({g.runs.length} run{g.runs.length === 1 ? '' : 's'})</span>
        </h2>

        {#each g.runs as r, i (r.run_id)}
          {@const fields = configFields(r)}
          {@const exCount = exampleCount(r)}
          {@const hasP = hasPrompt(r)}
          <details class="run" open={i === 0}>
            <summary>
              <span class="caret" aria-hidden="true"></span>
              <span class="mono run-id">{r.run_id}</span>
              <span class="chips">
                <span class="chip-static chip-task">{r.task ?? 'legacy'}</span>
                {#if r.strategy}
                  <span class="chip-static">{r.strategy}</span>
                {/if}
                <span class="chip-static chip-examples">{exCount} example{exCount === 1 ? '' : 's'}</span>
              </span>
            </summary>

            <div class="run-body">
              {#if fields.length > 0}
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

              <div class="prompt-wrap">
                <div class="prompt-head">
                  <span class="prompt-label">Prompt</span>
                  {#if hasP}
                    <button
                      type="button"
                      class="copy-btn"
                      onclick={() => copyPrompt(r.run_id, r.prompt ?? '')}
                    >
                      {copiedRunId === r.run_id ? 'Copied' : 'Copy'}
                    </button>
                  {/if}
                </div>
                {#if hasP}
                  <pre class="prompt-pre">{r.prompt}</pre>
                {:else}
                  <p class="muted">No prompt recorded.</p>
                {/if}
              </div>
            </div>
          </details>
        {/each}
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
    margin: 0 0 20px;
  }

  .empty {
    border: 1px dashed #d0d0d0;
    border-radius: 8px;
    padding: 18px 20px;
    background: #fafafa;
    color: #555;
    font-size: 14px;
  }

  .schema-block {
    margin: 0 0 28px;
  }

  .schema-heading {
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #444;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
    margin: 0 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid #e2e2e2;
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .schema-name {
    color: #222;
  }

  .schema-count {
    color: #888;
    font-size: 12px;
    font-weight: 400;
  }

  details.run {
    border: 1px solid #e2e2e2;
    border-radius: 6px;
    background: white;
    margin-bottom: 10px;
    overflow: hidden;
  }

  details.run > summary {
    cursor: pointer;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
    list-style: none;
    flex-wrap: wrap;
    background: #fafafa;
  }

  details.run > summary::-webkit-details-marker {
    display: none;
  }

  details.run > summary:hover {
    background: #f3f5f8;
  }

  details.run[open] > summary {
    background: #f5f7fb;
    border-bottom: 1px solid #e6e6e6;
  }

  .caret {
    width: 0;
    height: 0;
    border-left: 5px solid #888;
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    transition: transform 0.12s ease;
    flex-shrink: 0;
  }

  details.run[open] > summary .caret {
    transform: rotate(90deg);
  }

  .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
  }

  .run-id {
    color: #222;
    word-break: break-all;
  }

  .chips {
    display: inline-flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-left: auto;
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

  .chip-examples {
    background: #f4f4f4;
  }

  .run-body {
    padding: 14px 18px 18px;
  }

  table.kv {
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 14px;
  }

  table.kv th,
  table.kv td {
    text-align: left;
    padding: 3px 12px 3px 0;
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

  .prompt-wrap {
    margin-top: 4px;
  }

  .prompt-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  .prompt-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
  }

  .copy-btn {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    padding: 3px 10px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: white;
    cursor: pointer;
    color: #333;
  }

  .copy-btn:hover {
    background: #f4f4f4;
  }

  .copy-btn:active {
    background: #ebebeb;
  }

  .prompt-pre {
    margin: 0;
    padding: 12px;
    background: #f8f8f8;
    border: 1px solid #eee;
    border-radius: 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    line-height: 1.5;
    color: #222;
    white-space: pre-wrap;
    word-break: break-word;
    max-width: 100%;
    overflow-x: auto;
  }

  .muted {
    color: #888;
    font-size: 13px;
    margin: 0;
  }
</style>
