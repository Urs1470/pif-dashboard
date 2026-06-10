<script>
  import { CreditCard } from '@lucide/svelte'
  import { budget } from '../../stores/budget.svelte.js'
  import { formatRON, round2, getScadentar, getSoldCurent, platiTrecute, platiViitoare, todayIso, calcLuniRamase } from '../../lib/budget-calc.js'

  const d = $derived(budget.data)
  const scad = $derived(d ? getScadentar(d) : [])
  const today = todayIso()
  const soldCurent = $derived(d ? round2(getSoldCurent(d)) : 0)
  const luniRamase = $derived(d ? calcLuniRamase(d) : 0)
  const trecute = $derived(platiTrecute(scad, today))
  const viitoare = $derived(platiViitoare(scad, today))
  const totalRamas = $derived(round2(viitoare.reduce((s, p) => s + (p.suma || 0) + (p.asigurare || 0), 0)))
  const totalDobandaRamasa = $derived(round2(viitoare.reduce((s, p) => s + (p.dobanda || 0), 0)))

  let showAll = $state(false)
  const displayScad = $derived(showAll ? scad : viitoare)
</script>

{#if d}
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Sold curent</div>
      <div class="stat-value">{formatRON(soldCurent)} RON</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Rate ramase</div>
      <div class="stat-value">{luniRamase}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total de plata</div>
      <div class="stat-value">{formatRON(totalRamas)} RON</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Dobanda ramasa</div>
      <div class="stat-value">{formatRON(totalDobandaRamasa)} RON</div>
    </div>
  </div>

  <div class="credit-info">
    <span>Contract: {d.credit.contract || '—'}</span>
    <span>Suma: {formatRON(d.credit.suma)} RON</span>
    <span>Dobanda: {d.credit.dobanda}%</span>
    <span>DAE: {d.credit.dae}%</span>
    <span>Durata: {d.credit.durata} luni</span>
  </div>

  <div class="controls">
    <label class="toggle">
      <input type="checkbox" bind:checked={showAll} />
      <span>Arata toate ratele ({scad.length})</span>
    </label>
  </div>

  <div class="table-wrap">
    <table class="scad-table">
      <thead>
        <tr>
          <th>Data</th>
          <th>Rata</th>
          <th>Principal</th>
          <th>Dobanda</th>
          <th>Asig.</th>
          <th>Sold final</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {#each displayScad as p}
          {@const isPast = p.data <= today}
          {@const isNext = !isPast && viitoare[0]?.data === p.data}
          <tr class:past={isPast} class:next={isNext}>
            <td>{p.data}</td>
            <td class="num">{formatRON(p.suma)}</td>
            <td class="num">{formatRON(p.principal)}</td>
            <td class="num">{formatRON(p.dobanda)}</td>
            <td class="num">{formatRON(p.asigurare)}</td>
            <td class="num">{formatRON(p.soldFinal)}</td>
            <td>
              {#if isPast}<span class="badge paid">Platit</span>
              {:else if isNext}<span class="badge next-badge">Urmatoarea</span>
              {:else}<span class="badge future">Viitoare</span>{/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: var(--space-sm); margin-bottom: var(--space-md); }
  .stat-card { padding: var(--space-sm) var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); }
  .stat-label { font-size: var(--font-tiny); color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.04em; }
  .stat-value { font-size: var(--font-base); font-weight: 700; color: var(--text); font-family: var(--font-mono, inherit); }

  .credit-info { display: flex; flex-wrap: wrap; gap: var(--space-sm) var(--space-md); font-size: var(--font-tiny); color: var(--text-dim); margin-bottom: var(--space-md); }

  .controls { margin-bottom: var(--space-sm); }
  .toggle { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-small); color: var(--text-secondary); cursor: pointer; }

  .table-wrap { overflow-x: auto; }
  .scad-table { width: 100%; border-collapse: collapse; font-size: var(--font-tiny); }
  .scad-table th { text-align: left; padding: 6px 8px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); border-bottom: 1px solid var(--border); white-space: nowrap; }
  .scad-table td { padding: 5px 8px; border-bottom: 1px solid var(--bg-elevated); color: var(--text-secondary); white-space: nowrap; }
  .scad-table .num { text-align: right; font-family: var(--font-mono, inherit); }
  .scad-table tr.past td { color: var(--text-dim); }
  .scad-table tr.next td { color: var(--text); font-weight: 500; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: var(--radius-full); font-size: 0.6rem; font-weight: 500; }
  .badge.paid { background: var(--accent-subtle); color: var(--accent); }
  .badge.next-badge { background: var(--warning-subtle); color: var(--warning); }
  .badge.future { background: var(--bg-elevated); color: var(--text-dim); }

  @media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
