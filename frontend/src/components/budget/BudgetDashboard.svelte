<script>
  import { TrendingUp, TrendingDown, Wallet, PiggyBank, Landmark, CreditCard, CalendarClock } from '@lucide/svelte'
  import { budget } from '../../stores/budget.svelte.js'
  import {
    formatRON, round2, calcMediiVenituri, calcMediiCheltuieli,
    luniReprezentative, investitiiLuna, surplusLuna,
    soldDisponibilCurent, totalFondAzi, getSoldCurent, calcLuniRamase,
    getLuniKeys, getLuniLabels, todayIso, getScadentar, platiViitoare, parseRON
  } from '../../lib/budget-calc.js'
  import Card from '../ui/Card.svelte'

  const d = $derived(budget.data)
  const mediiV = $derived(d ? calcMediiVenituri(d) : null)
  const mediiC = $derived(d ? calcMediiCheltuieli(d) : null)
  const repLuni = $derived(d ? luniReprezentative(d) : [])

  const mediiInv = $derived(repLuni.length
    ? round2(repLuni.reduce((s, l) => s + investitiiLuna(d, l), 0) / repLuni.length) : 0)
  const surplus = $derived(mediiV && mediiC ? round2(mediiV.total - mediiC.total - mediiInv) : 0)
  const soldDisp = $derived(d ? soldDisponibilCurent(d) : 0)
  const totalFond = $derived(d ? round2(totalFondAzi(d)) : 0)
  const totalTezaur = $derived(d ? round2((d.tezaur || []).reduce((s, t) => s + (parseRON(t.suma) || 0), 0)) : 0)
  const soldCredit = $derived(d ? round2(getSoldCurent(d)) : 0)
  const luniRamase = $derived(d ? calcLuniRamase(d) : 0)
  const netWorth = $derived(round2(soldDisp + totalFond + totalTezaur - soldCredit))

  const nextPayment = $derived(() => {
    if (!d) return null
    const viitoare = platiViitoare(getScadentar(d), todayIso())
    if (viitoare.length === 0) return null
    const p = viitoare[0]
    const days = Math.max(0, Math.round((new Date(p.data + 'T00:00:00') - new Date()) / 86400000))
    return { data: p.data, suma: round2((p.suma || 0) + (p.asigurare || 0)), days }
  })

  const surplusData = $derived(() => {
    if (!d) return []
    const keys = getLuniKeys(d)
    const labels = getLuniLabels(d)
    return keys.map((k, i) => ({
      label: labels[i],
      value: surplusLuna(d, k)
    })).filter(r => r.value !== 0)
  })

  const cheltuieliBreakdown = $derived(() => {
    if (!mediiC) return []
    const items = []
    if (mediiC.rataCreditMedie > 0) items.push({ label: 'Rata credit', value: mediiC.rataCreditMedie })
    if (mediiC.bonuriMedie > 0) items.push({ label: 'Bonuri masa', value: mediiC.bonuriMedie })
    mediiC.categorii.forEach(c => {
      const v = mediiC.variabile[c.label] || 0
      if (v > 0) items.push({ label: c.label, value: round2(v) })
    })
    return items.sort((a, b) => b.value - a.value)
  })
</script>

{#if d}
  <div class="stats-grid">
    <div class="stat-card">
      <TrendingUp size={16} />
      <div class="stat-label">Venituri medii</div>
      <div class="stat-value accent">{formatRON(mediiV?.total)} RON</div>
    </div>
    <div class="stat-card">
      <TrendingDown size={16} />
      <div class="stat-label">Cheltuieli medii</div>
      <div class="stat-value danger">{formatRON(mediiC?.total)} RON</div>
    </div>
    <div class="stat-card">
      <PiggyBank size={16} />
      <div class="stat-label">Investitii medii</div>
      <div class="stat-value">{formatRON(mediiInv)} RON</div>
    </div>
    <div class="stat-card">
      <Wallet size={16} />
      <div class="stat-label">Surplus mediu</div>
      <div class="stat-value" class:accent={surplus >= 0} class:danger={surplus < 0}>{surplus >= 0 ? '+' : ''}{formatRON(surplus)} RON</div>
    </div>
  </div>

  <div class="stats-grid secondary">
    <div class="stat-card small">
      <div class="stat-label">Sold disponibil</div>
      <div class="stat-value">{formatRON(soldDisp)} RON</div>
    </div>
    <div class="stat-card small">
      <div class="stat-label">Fond urgenta</div>
      <div class="stat-value">{formatRON(totalFond)} RON</div>
    </div>
    <div class="stat-card small">
      <div class="stat-label">Tezaur</div>
      <div class="stat-value">{formatRON(totalTezaur)} RON</div>
    </div>
    <div class="stat-card small">
      <div class="stat-label">Valoare neta</div>
      <div class="stat-value" class:accent={netWorth >= 0} class:danger={netWorth < 0}>{formatRON(netWorth)} RON</div>
    </div>
  </div>

  {#if nextPayment()}
    <Card>
      <div class="next-payment">
        <CalendarClock size={18} />
        <div>
          <div class="np-label">Urmatoarea rata: {nextPayment().data}</div>
          <div class="np-value">{formatRON(nextPayment().suma)} RON <span class="np-days">in {nextPayment().days} zile</span></div>
        </div>
      </div>
    </Card>
  {/if}

  {#if surplusData().length > 0}
    <div class="section">
      <h3 class="section-title">Surplus lunar</h3>
      <div class="bar-chart">
        {#each surplusData() as bar}
          {@const maxVal = Math.max(...surplusData().map(b => Math.abs(b.value)), 1)}
          <div class="bar-row">
            <span class="bar-label">{bar.label}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                class:positive={bar.value >= 0}
                class:negative={bar.value < 0}
                style="width: {Math.min(100, Math.abs(bar.value) / maxVal * 100)}%"
              ></div>
            </div>
            <span class="bar-value" class:accent={bar.value >= 0} class:danger={bar.value < 0}>{formatRON(bar.value)}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  {#if cheltuieliBreakdown().length > 0}
    <div class="section">
      <h3 class="section-title">Distributie cheltuieli (medie)</h3>
      <div class="breakdown">
        {#each cheltuieliBreakdown() as item}
          {@const total = cheltuieliBreakdown().reduce((s, i) => s + i.value, 0)}
          <div class="breakdown-row">
            <span class="breakdown-label">{item.label}</span>
            <div class="breakdown-bar">
              <div class="breakdown-fill" style="width: {total > 0 ? (item.value / total * 100) : 0}%"></div>
            </div>
            <span class="breakdown-value">{formatRON(item.value)}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  {#if repLuni.length > 0}
    <p class="footnote">* Medii calculate pe {repLuni.length} {repLuni.length === 1 ? 'luna' : 'luni'} cu date</p>
  {/if}
{/if}

<style>
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-sm); margin-bottom: var(--space-md); }
  .stats-grid.secondary { margin-bottom: var(--space-lg); }
  .stat-card {
    padding: var(--space-md);
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: var(--text-dim);
  }
  .stat-card.small { padding: var(--space-sm) var(--space-md); }
  .stat-label { font-size: var(--font-tiny); font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; }
  .stat-value { font-size: var(--font-h2); font-weight: 700; color: var(--text); font-family: var(--font-mono, inherit); }
  .stat-card.small .stat-value { font-size: var(--font-base); }
  .stat-value.accent { color: var(--accent); }
  .stat-value.danger { color: var(--danger); }

  .next-payment { display: flex; align-items: center; gap: var(--space-sm); color: var(--text-dim); }
  .np-label { font-size: var(--font-small); color: var(--text-secondary); }
  .np-value { font-size: var(--font-base); font-weight: 600; color: var(--text); }
  .np-days { font-size: var(--font-tiny); color: var(--text-dim); font-weight: 400; }

  .section { margin-top: var(--space-lg); }
  .section-title { font-size: var(--font-small); font-weight: 600; color: var(--text); margin-bottom: var(--space-sm); }

  .bar-chart { display: flex; flex-direction: column; gap: 6px; }
  .bar-row { display: grid; grid-template-columns: 60px 1fr 90px; gap: var(--space-xs); align-items: center; }
  .bar-label { font-size: var(--font-tiny); color: var(--text-dim); text-align: right; }
  .bar-track { height: 16px; background: var(--bg-elevated); border-radius: var(--radius-xs); overflow: hidden; }
  .bar-fill { height: 100%; border-radius: var(--radius-xs); transition: width var(--dur-base) var(--ease); }
  .bar-fill.positive { background: var(--accent); opacity: 0.7; }
  .bar-fill.negative { background: var(--danger); opacity: 0.7; }
  .bar-value { font-size: var(--font-tiny); font-family: var(--font-mono, inherit); text-align: right; }
  .bar-value.accent { color: var(--accent); }
  .bar-value.danger { color: var(--danger); }

  .breakdown { display: flex; flex-direction: column; gap: 4px; }
  .breakdown-row { display: grid; grid-template-columns: 1fr 120px 80px; gap: var(--space-xs); align-items: center; }
  .breakdown-label { font-size: var(--font-tiny); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .breakdown-bar { height: 10px; background: var(--bg-elevated); border-radius: var(--radius-xs); overflow: hidden; }
  .breakdown-fill { height: 100%; background: var(--accent); opacity: 0.5; border-radius: var(--radius-xs); }
  .breakdown-value { font-size: var(--font-tiny); font-family: var(--font-mono, inherit); text-align: right; color: var(--text-dim); }

  .footnote { font-size: var(--font-tiny); color: var(--text-dim); margin-top: var(--space-lg); }

  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .bar-row { grid-template-columns: 50px 1fr 70px; }
    .breakdown-row { grid-template-columns: 1fr 80px 70px; }
  }
</style>
