<script>
  import { Calculator as CalcIcon, Info, BookOpen } from '@lucide/svelte'
  import { MODULES, MODULE_ORDER, SOURCES, visibleFamilies, computeModule, computeCharts, fmtNum } from '../lib/driveCalc.js'
  import Formula from '../components/ui/Formula.svelte'
  import Chart from '../components/ui/Chart.svelte'

  const families = visibleFamilies()
  let activeFamily = $state(families[0]?.id ?? 'asincron')

  // Valorile de intrare per modul, initializate din default-uri.
  let values = $state(
    Object.fromEntries(
      MODULES.map((m) => [m.id, Object.fromEntries(m.fields.map((f) => [f.key, f.default]))])
    )
  )

  const ord = (id) => { const i = MODULE_ORDER.indexOf(id); return i === -1 ? 999 : i }
  const shown = $derived(
    MODULES.filter((m) => m.family === activeFamily).sort((a, b) => ord(a.id) - ord(b.id))
  )

  function unitLabel(label, unit) {
    return unit ? `${label} [${unit}]` : label
  }

  function resetModule(m) {
    for (const f of m.fields) values[m.id][f.key] = f.default
  }
</script>

<div class="page">
  <div class="page-head">
    <CalcIcon size={24} />
    <div>
      <h1>Calculator actionari electrice</h1>
      <p class="sub">Marimi inginerești pentru motoare si convertizoare — valori orientative, verifica intotdeauna catalogul/manualul.</p>
    </div>
  </div>

  <div class="fam-tabs" role="tablist">
    {#each families as fam}
      <button
        class="fam-tab"
        class:active={activeFamily === fam.id}
        role="tab"
        aria-selected={activeFamily === fam.id}
        onclick={() => (activeFamily = fam.id)}
      >
        {fam.label}
      </button>
    {/each}
  </div>

  <div class="mod-grid">
    {#each shown as m (m.id)}
      {@const r = computeModule(m, values[m.id])}
      <div class="mod-card">
        <div class="mod-head">
          <div class="mod-title">
            <h2>{m.title}</h2>
            {#if m.subtitle}<span class="mod-sub">{m.subtitle}</span>{/if}
          </div>
          <button class="reset-btn" title="Reseteaza valorile" onclick={() => resetModule(m)}>Reset</button>
        </div>

        <div class="inputs">
          {#each m.fields as f (f.key)}
            <label class="inp">
              <span class="inp-label">{unitLabel(f.label, f.unit)}</span>
              <input
                class="inp-field"
                type="number"
                step={f.step ?? 'any'}
                min={f.min}
                bind:value={values[m.id][f.key]}
              />
            </label>
          {/each}
        </div>

        <div class="results">
          {#each m.results as res (res.key)}
            <div class="res-row">
              <div class="res-left">
                <span class="res-label">{res.label}</span>
                <Formula tex={res.tex} />
              </div>
              <div class="res-right">
                <span class="res-val">{fmtNum(r[res.key], res.dec)}</span>
                {#if res.unit}<span class="res-unit">{res.unit}</span>{/if}
              </div>
            </div>
          {/each}
        </div>

        {#each computeCharts(m, values[m.id]) as chart}
          <Chart {chart} />
        {/each}

        {#if m.note}
          <p class="mod-note"><Info size={13} /> {m.note}</p>
        {/if}
        {#if m.params}
          <p class="mod-params">{m.params}</p>
        {/if}
        {#if SOURCES[m.id]}
          <p class="mod-source"><BookOpen size={11} /> {SOURCES[m.id]}</p>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .page { padding: var(--space-lg); }

  .page-head {
    display: flex;
    align-items: flex-start;
    gap: var(--space-sm);
    margin-bottom: var(--space-lg);
    color: var(--text);
  }
  .page-head h1 { font-size: var(--font-h1); font-weight: 700; }
  .sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    margin-top: 2px;
    max-width: 70ch;
  }

  .fam-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-bottom: var(--space-lg);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-sm);
  }
  .fam-tab {
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--text-secondary);
    transition: all var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .fam-tab:hover { background: var(--bg-hover); color: var(--text); }
  .fam-tab.active { background: var(--accent-subtle); color: var(--accent); }

  .mod-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: var(--space-md);
  }

  .mod-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .mod-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-sm);
  }
  .mod-title h2 { font-size: 1rem; font-weight: 700; color: var(--text); }
  .mod-sub { font-size: var(--font-tiny); color: var(--text-dim); }
  .reset-btn {
    font-size: var(--font-tiny);
    color: var(--text-dim);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    transition: all var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .reset-btn:hover { background: var(--bg-hover); color: var(--text); }

  .inputs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: var(--space-sm);
  }
  .inp { display: flex; flex-direction: column; gap: 4px; }
  .inp-label {
    font-size: var(--font-tiny);
    font-weight: 500;
    color: var(--text-secondary);
    line-height: 1.2;
    min-height: 2.2em;
    overflow-wrap: anywhere;
  }
  .inp-field {
    margin-top: auto;
    padding: 8px 10px;
    min-height: 40px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: var(--font-body);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .inp-field:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }

  .results {
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--border);
  }
  .res-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-md);
    padding: var(--space-sm) 0;
    border-bottom: 1px solid var(--border);
  }
  .res-row:last-child { border-bottom: none; }
  .res-left { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .res-label { font-size: var(--font-small); color: var(--text); }
  .res-right {
    display: flex;
    align-items: baseline;
    gap: 4px;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .res-val {
    font-family: var(--font-mono);
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--accent);
  }
  .res-unit { font-size: var(--font-tiny); color: var(--text-dim); }

  .mod-note {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
  }
  .mod-params {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    color: var(--text-dim);
    border-top: 1px dashed var(--border);
    padding-top: var(--space-sm);
  }
  .mod-source {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
    font-style: italic;
  }

  @media (max-width: 768px) {
    .mod-grid { grid-template-columns: 1fr; }
  }
</style>
