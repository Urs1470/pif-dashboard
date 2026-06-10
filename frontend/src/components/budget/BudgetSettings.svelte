<script>
  import { Settings, Plus, Trash2 } from '@lucide/svelte'
  import { budget, markDirty, getNextBudgetId } from '../../stores/budget.svelte.js'

  const d = $derived(budget.data)
  const profil = $derived(d?.profil || {})

  function setProfilField(field, val) {
    if (!d.profil) d.profil = {}
    d.profil[field] = typeof val === 'string' ? val : parseFloat(val) || 0
    markDirty()
  }

  function addCatVar() {
    d.categoriiVar.push({ id: getNextBudgetId(d.categoriiVar), label: 'Categorie noua' })
    markDirty()
  }
  function removeCatVar(id) {
    d.categoriiVar = d.categoriiVar.filter(c => c.id !== id)
    markDirty()
  }

  function addCatVenit() {
    d.categoriiVenit.push({ id: getNextBudgetId(d.categoriiVenit), label: 'Categorie noua' })
    markDirty()
  }
  function removeCatVenit(id) {
    d.categoriiVenit = d.categoriiVenit.filter(c => c.id !== id)
    markDirty()
  }

  function addRegula() {
    d.reguliCategorizare.push({ id: getNextBudgetId(d.reguliCategorizare), pattern: '', categorie: '' })
    markDirty()
  }
  function removeRegula(id) {
    d.reguliCategorizare = d.reguliCategorizare.filter(r => r.id !== id)
    markDirty()
  }
</script>

{#if d}
  <div class="section">
    <h3 class="sec-title"><Settings size={16} /> Profil</h3>
    <div class="fields-grid">
      <label>Nume<input type="text" value={profil.nume || ''} onchange={(e) => setProfilField('nume', e.target.value)} /></label>
      <label>Salariu net (RON)<input type="number" value={profil.salariuNet || 0} onchange={(e) => setProfilField('salariuNet', e.target.value)} /></label>
      <label>Luna start<input type="month" value={profil.startMonth || '2026-05'} onchange={(e) => setProfilField('startMonth', e.target.value)} /></label>
      <label>Nr. luni vizibile<input type="number" value={profil.numarLuni || 12} min="1" max="120" onchange={(e) => setProfilField('numarLuni', e.target.value)} /></label>
      <label>Sold cont curent initial<input type="number" value={profil.soldContCurent || 0} onchange={(e) => setProfilField('soldContCurent', e.target.value)} step="0.01" /></label>
      <label>Sold bonuri initial<input type="number" value={profil.bonuriSoldInitial || 0} onchange={(e) => setProfilField('bonuriSoldInitial', e.target.value)} step="0.01" /></label>
    </div>
  </div>

  <div class="section">
    <h3 class="sec-title">Categorii cheltuieli <button class="btn-add" onclick={addCatVar}><Plus size={12} /></button></h3>
    <div class="cat-list">
      {#each d.categoriiVar as cat (cat.id)}
        <div class="cat-row">
          <input type="text" bind:value={cat.label} onchange={markDirty} />
          <button class="btn-del" onclick={() => removeCatVar(cat.id)}><Trash2 size={12} /></button>
        </div>
      {/each}
    </div>
  </div>

  <div class="section">
    <h3 class="sec-title">Categorii venituri <button class="btn-add" onclick={addCatVenit}><Plus size={12} /></button></h3>
    <div class="cat-list">
      {#each d.categoriiVenit as cat (cat.id)}
        <div class="cat-row">
          <input type="text" bind:value={cat.label} onchange={markDirty} />
          <button class="btn-del" onclick={() => removeCatVenit(cat.id)}><Trash2 size={12} /></button>
        </div>
      {/each}
    </div>
  </div>

  <div class="section">
    <h3 class="sec-title">Reguli auto-categorizare <button class="btn-add" onclick={addRegula}><Plus size={12} /></button></h3>
    <div class="rules-list">
      {#each (d.reguliCategorizare || []) as r (r.id)}
        <div class="rule-row">
          <input type="text" bind:value={r.pattern} onchange={markDirty} placeholder="Regex pattern" class="rule-pattern" />
          <span class="rule-arrow">→</span>
          <input type="text" bind:value={r.categorie} onchange={markDirty} placeholder="Categorie" class="rule-cat" />
          <button class="btn-del" onclick={() => removeRegula(r.id)}><Trash2 size={12} /></button>
        </div>
      {/each}
    </div>
  </div>

  {#if (d.importHistory || []).length > 0}
    <div class="section">
      <h3 class="sec-title">Istoric importuri</h3>
      <div class="history-list">
        {#each d.importHistory as imp}
          <div class="history-row">
            <span class="dim">{new Date(imp.ts).toLocaleDateString('ro-RO')}</span>
            <span>{imp.fileName}</span>
            <span class="dim">{imp.items} tranzactii</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
{/if}

<style>
  .section { margin-bottom: var(--space-xl); }
  .sec-title { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-small); font-weight: 600; color: var(--text); margin-bottom: var(--space-sm); }

  .fields-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--space-sm); }
  .fields-grid label { font-size: var(--font-tiny); color: var(--text-dim); display: flex; flex-direction: column; gap: 4px; }
  .fields-grid input { padding: 6px 10px; font-size: var(--font-small); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); }
  .fields-grid input:focus { border-color: var(--accent); outline: none; }

  .cat-list { display: flex; flex-direction: column; gap: 4px; }
  .cat-row { display: flex; gap: 6px; align-items: center; }
  .cat-row input { flex: 1; padding: 4px 8px; font-size: var(--font-small); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); }
  .cat-row input:focus { border-color: var(--accent); outline: none; }

  .rules-list { display: flex; flex-direction: column; gap: 4px; }
  .rule-row { display: flex; gap: 6px; align-items: center; }
  .rule-pattern { flex: 2; padding: 4px 8px; font-size: var(--font-tiny); font-family: var(--font-mono, monospace); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); }
  .rule-arrow { color: var(--text-dim); font-size: var(--font-tiny); }
  .rule-cat { flex: 1; padding: 4px 8px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); }

  .btn-add { color: var(--accent); padding: 2px 6px; }
  .btn-del { color: var(--danger); opacity: 0.4; padding: 2px 4px; }
  .btn-del:hover { opacity: 1; }

  .history-list { display: flex; flex-direction: column; gap: 4px; }
  .history-row { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-secondary); }
  .dim { color: var(--text-dim); }

  @media (max-width: 768px) {
    .fields-grid { grid-template-columns: 1fr; }
    .rule-row { flex-wrap: wrap; }
    .rule-pattern, .rule-cat { flex: none; width: 100%; }
    .rule-arrow { display: none; }
  }
</style>
