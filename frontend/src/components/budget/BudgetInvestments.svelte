<script>
  import { RefreshCw, Briefcase, PiggyBank, Landmark, TrendingUp } from '@lucide/svelte'
  import { budget, markDirty, getNextBudgetId, refreshVwcePrice } from '../../stores/budget.svelte.js'
  import { formatRON, round2, parseRON, vwceTotals, fondMetrics, tezaurMetrics, totalFondAzi, todayIso } from '../../lib/budget-calc.js'

  const d = $derived(budget.data)
  const v = $derived(d?.vwce || {})
  const totals = $derived(vwceTotals(v))
  const fondItems = $derived((d?.fondUrgenta || []).map(f => ({ ...f, m: fondMetrics(f) })))
  const tezaurItems = $derived((d?.tezaur || []).map(t => ({ ...t, m: tezaurMetrics(t) })))
  const totalFond = $derived(d ? round2(totalFondAzi(d)) : 0)
  const totalTezaur = $derived(round2(tezaurItems.reduce((s, t) => s + t.m.valoareAzi, 0)))

  let refreshing = $state(false)
  async function doRefresh() {
    refreshing = true
    await refreshVwcePrice()
    refreshing = false
  }

  function addTranzactie() {
    d.vwce.tranzactii.push({ id: getNextBudgetId(d.vwce.tranzactii), data: todayIso(), cantitate: 0, pretAchizitie: 0, comision: 0 })
    markDirty()
  }

  function addFond() {
    d.fondUrgenta.push({ id: getNextBudgetId(d.fondUrgenta), cont: '', suma: 0, dobanda: 0, lichid: 'Da', dataStart: todayIso() })
    markDirty()
  }

  function addTezaur() {
    const em = d.emisiuniTezaur?.[0]?.label || 'Tezaur 1 an'
    d.tezaur.push({ id: getNextBudgetId(d.tezaur), emisiune: em, dataSubscriere: todayIso(), suma: 0, dobanda: 6.30, maturitate: '1 an' })
    markDirty()
  }

  function removeFond(id) { d.fondUrgenta = d.fondUrgenta.filter(f => f.id !== id); markDirty() }
  function removeTezaur(id) { d.tezaur = d.tezaur.filter(t => t.id !== id); markDirty() }
  function removeTranzactie(id) { d.vwce.tranzactii = d.vwce.tranzactii.filter(t => t.id !== id); markDirty() }
</script>

{#if d}
  <!-- VWCE -->
  <div class="section">
    <div class="section-header">
      <Briefcase size={16} />
      <h3>{v.symbol || 'VWCE.DE'}</h3>
      <span class="dim">{v.exchange || 'XETRA'}</span>
      <button class="btn-sm" onclick={doRefresh} disabled={refreshing}><RefreshCw size={12} class={refreshing ? 'spin' : ''} /> Pret</button>
    </div>

    <div class="price-row">
      <span class="price">{formatRON(totals.pretCurent)} EUR</span>
      {#if v.changePct}
        <span class:pos={v.changePct >= 0} class:neg={v.changePct < 0}>{v.changePct >= 0 ? '+' : ''}{parseFloat(v.changePct).toFixed(2)}%</span>
      {/if}
      {#if v.lastUpdateLocal}
        <span class="dim tiny">Actualizat: {new Date(v.lastUpdateLocal).toLocaleString('ro-RO', { dateStyle: 'short', timeStyle: 'short' })}</span>
      {/if}
    </div>

    <div class="stats-grid">
      <div class="stat-mini"><span class="sl">Unitati</span><span class="sv">{totals.cantitate}</span></div>
      <div class="stat-mini"><span class="sl">Investit</span><span class="sv">{formatRON(totals.investitEur)} EUR</span></div>
      <div class="stat-mini"><span class="sl">Valoare</span><span class="sv">{formatRON(totals.valoareEur)} EUR</span></div>
      <div class="stat-mini"><span class="sl">P/L</span><span class="sv" class:pos={totals.plEur >= 0} class:neg={totals.plEur < 0}>{totals.plEur >= 0 ? '+' : ''}{formatRON(totals.plEur)} EUR ({totals.plPct.toFixed(1)}%)</span></div>
    </div>

    <div class="sub-section">
      <h4>Tranzactii <button class="btn-add" onclick={addTranzactie}>+ Adauga</button></h4>
      {#each d.vwce.tranzactii as t (t.id)}
        <div class="inline-row">
          <input type="date" bind:value={t.data} onchange={markDirty} />
          <input type="number" bind:value={t.cantitate} onchange={markDirty} placeholder="Qty" />
          <input type="number" bind:value={t.pretAchizitie} onchange={markDirty} placeholder="Pret EUR" step="0.01" />
          <input type="number" bind:value={t.comision} onchange={markDirty} placeholder="Com." step="0.01" />
          <button class="btn-del" onclick={() => removeTranzactie(t.id)}>x</button>
        </div>
      {/each}
    </div>
  </div>

  <!-- Fond urgenta -->
  <div class="section">
    <div class="section-header"><PiggyBank size={16} /><h3>Fond urgenta</h3><span class="dim">{formatRON(totalFond)} RON</span><button class="btn-add" onclick={addFond}>+ Adauga</button></div>
    {#each fondItems as f (f.id)}
      <div class="inv-card">
        <div class="inv-header">
          <input type="text" bind:value={f.cont} onchange={markDirty} placeholder="Cont" class="inv-name" />
          <button class="btn-del" onclick={() => removeFond(f.id)}>x</button>
        </div>
        <div class="inv-fields">
          <label>Suma<input type="number" bind:value={f.suma} onchange={markDirty} step="0.01" /></label>
          <label>Dobanda %<input type="number" bind:value={f.dobanda} onchange={markDirty} step="0.01" /></label>
          <label>Data start<input type="date" bind:value={f.dataStart} onchange={markDirty} /></label>
        </div>
        <div class="inv-metrics">
          <span>Valoare azi: <b>{formatRON(f.m.valoareAzi)}</b></span>
          <span>+{formatRON(f.m.dobandaAcumulata)} dobanda</span>
          <span class="dim">La 1 an: {formatRON(f.m.la1an)} | La 5 ani: {formatRON(f.m.la5ani)}</span>
        </div>
      </div>
    {/each}
  </div>

  <!-- Tezaur -->
  <div class="section">
    <div class="section-header"><Landmark size={16} /><h3>Titluri de stat</h3><span class="dim">{formatRON(totalTezaur)} RON</span><button class="btn-add" onclick={addTezaur}>+ Adauga</button></div>
    {#each tezaurItems as t (t.id)}
      <div class="inv-card">
        <div class="inv-header">
          <span class="inv-name">{t.emisiune || 'Tezaur'}</span>
          <button class="btn-del" onclick={() => removeTezaur(t.id)}>x</button>
        </div>
        <div class="inv-fields">
          <label>Suma<input type="number" bind:value={t.suma} onchange={markDirty} step="0.01" /></label>
          <label>Dobanda %<input type="number" bind:value={t.dobanda} onchange={markDirty} step="0.01" /></label>
          <label>Subscriere<input type="date" bind:value={t.dataSubscriere} onchange={markDirty} /></label>
          <label>Maturitate
            <select bind:value={t.maturitate} onchange={markDirty}>
              <option value="6 luni">6 luni</option><option value="1 an">1 an</option>
              <option value="2 ani">2 ani</option><option value="3 ani">3 ani</option><option value="5 ani">5 ani</option>
            </select>
          </label>
        </div>
        <div class="inv-metrics">
          <span>Valoare azi: <b>{formatRON(t.m.valoareAzi)}</b></span>
          <span>Dobanda acumulata: {formatRON(t.m.dobandaAcumulata)}</span>
          <span>La scadenta ({t.m.dataScad}): {formatRON(t.m.valoareLaScadenta)}</span>
          {#if t.m.matur}<span class="badge-done">Maturat</span>
          {:else if t.m.neinceput}<span class="dim">Programat</span>
          {:else}<span class="dim">{t.m.progres}% — {t.m.zileRamase} zile ramase</span>{/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .section { margin-bottom: var(--space-xl); }
  .section-header { display: flex; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-sm); color: var(--text); flex-wrap: wrap; }
  .section-header h3 { font-size: var(--font-base); font-weight: 600; }
  .dim { color: var(--text-dim); font-size: var(--font-tiny); }
  .tiny { font-size: 0.65rem; }

  .price-row { display: flex; align-items: baseline; gap: var(--space-sm); margin-bottom: var(--space-sm); flex-wrap: wrap; }
  .price { font-size: var(--font-h2); font-weight: 700; color: var(--accent); font-family: var(--font-mono, inherit); }
  .pos { color: var(--success); }
  .neg { color: var(--danger); }

  .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: var(--space-xs); margin-bottom: var(--space-md); }
  .stat-mini { padding: var(--space-xs) var(--space-sm); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .sl { display: block; font-size: var(--font-tiny); color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.03em; }
  .sv { font-size: var(--font-small); font-weight: 600; color: var(--text); font-family: var(--font-mono, inherit); }

  .sub-section { margin-top: var(--space-sm); }
  .sub-section h4 { font-size: var(--font-small); font-weight: 500; color: var(--text-secondary); margin-bottom: var(--space-xs); display: flex; align-items: center; gap: var(--space-sm); }

  .inline-row { display: flex; gap: 6px; align-items: center; margin-bottom: 4px; }
  .inline-row input { padding: 4px 6px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); width: 100px; }
  .inline-row input[type="date"] { width: 130px; }
  .inline-row input[type="number"] { width: 80px; text-align: right; }

  .inv-card { padding: var(--space-sm) var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: var(--space-sm); }
  .inv-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-xs); }
  .inv-name { font-size: var(--font-small); font-weight: 500; color: var(--text); background: transparent; border: none; }
  input.inv-name { border-bottom: 1px solid var(--border); padding: 2px 0; }
  .inv-fields { display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-sm); margin-bottom: var(--space-xs); }
  .inv-fields label { font-size: var(--font-tiny); color: var(--text-dim); display: flex; flex-direction: column; gap: 2px; }
  .inv-fields input, .inv-fields select { padding: 4px 6px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); width: 110px; }
  .inv-metrics { display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-md); font-size: var(--font-tiny); color: var(--text-secondary); }
  .inv-metrics b { color: var(--text); }

  .btn-sm { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text-secondary); margin-left: auto; }
  .btn-sm:hover { color: var(--text); }
  .btn-add { font-size: var(--font-tiny); color: var(--accent); padding: 2px 8px; }
  .btn-del { font-size: var(--font-tiny); color: var(--danger); padding: 2px 6px; opacity: 0.5; }
  .btn-del:hover { opacity: 1; }

  .badge-done { padding: 2px 8px; background: rgba(52,211,153,0.15); color: var(--success); border-radius: var(--radius-full); font-size: 0.6rem; }

  :global(.spin) { animation: spin 1s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .inline-row { flex-wrap: wrap; }
    .inv-fields { flex-direction: column; }
    .inv-fields input, .inv-fields select { width: 100%; }
  }
</style>
