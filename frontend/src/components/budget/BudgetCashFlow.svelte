<script>
  import { Upload } from '@lucide/svelte'
  import { budget, markDirty } from '../../stores/budget.svelte.js'
  import {
    formatRON, parseRON, round2, getLuniKeys, getLuniLabels,
    totalVenituriLuna, totalCheltuieliLuna, surplusLuna, investitiiLuna,
    rataCredituluiLuna, cheltuieliBonuriLuna
  } from '../../lib/budget-calc.js'
  import BudgetImport from './BudgetImport.svelte'

  const d = $derived(budget.data)
  const luniKeys = $derived(d ? getLuniKeys(d) : [])
  const luniLabels = $derived(d ? getLuniLabels(d) : [])

  let selectedMonth = $state(0)
  let showImport = $state(false)

  const lk = $derived(luniKeys[selectedMonth] || '')
  const venituriLuna = $derived(d?.venituri?.[lk] || {})
  const cheltuieliLuna = $derived(d?.cheltuieli?.[lk] || {})
  const cats = $derived(d?.categoriiVar || [])
  const catsVenit = $derived(d?.categoriiVenit || [])

  function setVenit(label, val) {
    if (!d.venituri[lk]) d.venituri[lk] = {}
    d.venituri[lk][label] = parseRON(val)
    markDirty()
  }

  function setCheltuiala(label, val) {
    if (!d.cheltuieli[lk]) d.cheltuieli[lk] = {}
    d.cheltuieli[lk][label] = parseRON(val)
    markDirty()
  }

  function setBonuriSold(val) {
    if (!d.bonuriSold) d.bonuriSold = {}
    d.bonuriSold[lk] = val === '' ? null : parseRON(val)
    markDirty()
  }
</script>

<div class="controls">
  <select bind:value={selectedMonth}>
    {#each luniLabels as label, i}
      <option value={i}>{label}</option>
    {/each}
  </select>
  <button class="btn-import" onclick={() => showImport = true}><Upload size={14} /> Import ING CSV</button>
</div>

{#if d}
  <div class="section">
    <h3 class="sec-title">Venituri — {luniLabels[selectedMonth]}</h3>
    <table class="data-table">
      <thead><tr><th>Categorie</th><th>Suma (RON)</th></tr></thead>
      <tbody>
        <tr class="fixed-row">
          <td>Salariu net</td>
          <td class="num">{formatRON(d.profil.salariuNet)}</td>
        </tr>
        {#each catsVenit as cat}
          <tr>
            <td>{cat.label}</td>
            <td><input type="text" class="cell-input" value={venituriLuna[cat.label] || ''} onchange={(e) => setVenit(cat.label, e.target.value)} /></td>
          </tr>
        {/each}
        <tr class="total-row">
          <td>Total venituri</td>
          <td class="num accent">{formatRON(totalVenituriLuna(d, lk))}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h3 class="sec-title">Cheltuieli — {luniLabels[selectedMonth]}</h3>
    <table class="data-table">
      <thead><tr><th>Categorie</th><th>Suma (RON)</th></tr></thead>
      <tbody>
        {#if rataCredituluiLuna(d, lk) > 0}
          <tr class="fixed-row">
            <td>Rata credit + asig.</td>
            <td class="num">{formatRON(rataCredituluiLuna(d, lk))}</td>
          </tr>
        {/if}
        <tr class="meal-row">
          <td>Bonuri masa (sold final)</td>
          <td><input type="text" class="cell-input" value={d.bonuriSold?.[lk] ?? ''} onchange={(e) => setBonuriSold(e.target.value)} placeholder="Sold final" /></td>
        </tr>
        {#if cheltuieliBonuriLuna(d, lk) > 0}
          <tr class="derived-row">
            <td class="dim">↳ Cheltuit bonuri</td>
            <td class="num dim">{formatRON(cheltuieliBonuriLuna(d, lk))}</td>
          </tr>
        {/if}
        {#each cats as cat}
          <tr>
            <td>{cat.label}</td>
            <td><input type="text" class="cell-input" value={cheltuieliLuna[cat.label] || ''} onchange={(e) => setCheltuiala(cat.label, e.target.value)} /></td>
          </tr>
        {/each}
        <tr class="total-row">
          <td>Total cheltuieli</td>
          <td class="num danger">{formatRON(totalCheltuieliLuna(d, lk))}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="summary">
    <div class="summary-row">
      <span>Investitii luna</span>
      <span class="num">{formatRON(investitiiLuna(d, lk))} RON</span>
    </div>
    <div class="summary-row highlight">
      <span>Surplus luna</span>
      {#if true}{@const s = surplusLuna(d, lk)}
      <span class="num" class:accent={s >= 0} class:danger={s < 0}>{s >= 0 ? '+' : ''}{formatRON(s)} RON</span>
      {/if}
    </div>
  </div>
{/if}

{#if showImport}
  <BudgetImport onclose={() => showImport = false} />
{/if}

<style>
  .controls { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .controls select {
    padding: 6px 12px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: var(--font-small);
  }
  .btn-import {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 14px; font-size: var(--font-small); font-weight: 500;
    background: var(--accent); color: var(--bg); border-radius: var(--radius-sm);
    transition: opacity var(--dur-fast) var(--ease);
  }
  .btn-import:hover { opacity: 0.85; }

  .section { margin-bottom: var(--space-lg); }
  .sec-title { font-size: var(--font-small); font-weight: 600; color: var(--text); margin-bottom: var(--space-xs); }

  .data-table { width: 100%; border-collapse: collapse; font-size: var(--font-small); }
  .data-table th { text-align: left; padding: 6px 8px; font-size: var(--font-tiny); font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); border-bottom: 1px solid var(--border); }
  .data-table th:last-child { text-align: right; width: 140px; }
  .data-table td { padding: 4px 8px; border-bottom: 1px solid var(--bg-elevated); color: var(--text-secondary); }
  .data-table .num { text-align: right; font-family: var(--font-mono, inherit); }
  .data-table .accent { color: var(--accent); }
  .data-table .danger { color: var(--danger); }
  .data-table .dim { color: var(--text-dim); font-size: var(--font-tiny); }
  .fixed-row td { color: var(--text-dim); font-style: italic; }
  .meal-row td:first-child { color: var(--text-dim); }
  .derived-row td { border-bottom: none; }
  .total-row td { font-weight: 600; color: var(--text); border-top: 1px solid var(--border); }

  .cell-input {
    width: 100%;
    padding: 4px 6px;
    background: var(--bg-elevated);
    border: 1px solid transparent;
    border-radius: var(--radius-xs);
    color: var(--text);
    font-size: var(--font-small);
    font-family: var(--font-mono, inherit);
    text-align: right;
    transition: border-color var(--dur-fast) var(--ease);
  }
  .cell-input:focus { border-color: var(--accent); outline: none; }

  .summary { margin-top: var(--space-md); display: flex; flex-direction: column; gap: var(--space-xs); }
  .summary-row { display: flex; justify-content: space-between; padding: var(--space-xs) var(--space-sm); font-size: var(--font-small); color: var(--text-secondary); }
  .summary-row.highlight { background: var(--bg-surface); border-radius: var(--radius-sm); font-weight: 600; }
  .summary-row .accent { color: var(--accent); }
  .summary-row .danger { color: var(--danger); }

  @media (max-width: 768px) {
    .data-table th:last-child { width: 110px; }
  }
</style>
