<script>
  import { X, Upload, Check } from '@lucide/svelte'
  import { budget, markDirty, getNextBudgetId } from '../../stores/budget.svelte.js'
  import { parseIngCsv, categorizeAuto, specialCatLabel, IMPORT_SPECIAL_CATS, parseRON } from '../../lib/budget-calc.js'

  let { onclose } = $props()

  let fileText = $state('')
  let fileName = $state('')
  let transactions = $state([])
  let applied = $state(false)

  const d = $derived(budget.data)
  const allCats = $derived(() => {
    const expense = (d?.categoriiVar || []).map(c => c.label)
    const income = (d?.categoriiVenit || []).map(c => c.label)
    return [...IMPORT_SPECIAL_CATS, ...expense, ...income]
  })

  function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    fileName = file.name
    const reader = new FileReader()
    reader.onload = () => {
      fileText = reader.result
      const txns = parseIngCsv(fileText)
      const existing = new Set(d?.importedRefs || [])
      transactions = txns
        .filter(t => !existing.has(t.ref))
        .map(t => ({
          ...t,
          categorie: categorizeAuto(t, d?.reguliCategorizare) || (t.sense === 'credit' ? 'Alte venituri' : 'Alte'),
        }))
    }
    reader.readAsText(file, 'UTF-8')
  }

  function applyImport() {
    if (!d || transactions.length === 0) return
    const refs = []
    transactions.forEach(t => {
      if (t.categorie === '__SKIP__') { refs.push(t.ref); return }
      const lk = t.data.substring(0, 7)
      const suma = Math.abs(t.suma)

      if (t.categorie === '__TEZAUR__') {
        d.tezaur.push({ id: getNextBudgetId(d.tezaur), emisiune: 'Tezaur 1 an', dataSubscriere: t.data, suma, dobanda: 6.30, maturitate: '1 an' })
        refs.push(t.ref)
        return
      }
      if (t.categorie === '__TRADEVILLE__') {
        d.vwce.alimentari.push({ data: t.data, suma, ref: t.ref })
        refs.push(t.ref)
        return
      }

      if (t.sense === 'credit') {
        if (!d.venituri[lk]) d.venituri[lk] = {}
        d.venituri[lk][t.categorie] = (d.venituri[lk][t.categorie] || 0) + suma
      } else {
        if (!d.cheltuieli[lk]) d.cheltuieli[lk] = {}
        d.cheltuieli[lk][t.categorie] = (d.cheltuieli[lk][t.categorie] || 0) + suma
      }
      refs.push(t.ref)
    })

    d.importedRefs = [...(d.importedRefs || []), ...refs]
    d.importHistory = [...(d.importHistory || []), {
      id: getNextBudgetId(d.importHistory),
      ts: new Date().toISOString(),
      fileName,
      items: transactions.length,
      summary: `${refs.length} tranzactii importate`
    }]
    markDirty()
    applied = true
  }
</script>

<div class="modal-backdrop" onclick={onclose} role="presentation">
  <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog">
    <div class="modal-header">
      <h3>Import ING CSV</h3>
      <button onclick={onclose}><X size={18} /></button>
    </div>

    {#if applied}
      <div class="modal-body">
        <div class="success-msg"><Check size={20} /> Import finalizat — {transactions.length} tranzactii procesate.</div>
      </div>
    {:else if transactions.length > 0}
      <div class="modal-body">
        <p class="info">{transactions.length} tranzactii noi din {fileName}</p>
        <div class="txn-list">
          {#each transactions as txn, i}
            <div class="txn-row">
              <span class="txn-date">{txn.data}</span>
              <span class="txn-desc" title={txn.detalii}>{txn.detalii.substring(0, 50)}</span>
              <span class="txn-suma" class:credit={txn.sense === 'credit'} class:debit={txn.sense === 'debit'}>
                {txn.sense === 'credit' ? '+' : '-'}{Math.abs(txn.suma).toFixed(2)}
              </span>
              <select bind:value={txn.categorie}>
                {#each allCats() as cat}
                  <option value={cat}>{IMPORT_SPECIAL_CATS.includes(cat) ? specialCatLabel(cat) : cat}</option>
                {/each}
              </select>
            </div>
          {/each}
        </div>
        <button class="btn-apply" onclick={applyImport}><Check size={14} /> Aplica import</button>
      </div>
    {:else}
      <div class="modal-body">
        <label class="file-picker">
          <Upload size={20} />
          <span>Selecteaza fisier CSV (ING Home'Bank export)</span>
          <input type="file" accept=".csv" onchange={handleFile} hidden />
        </label>
        {#if fileName && transactions.length === 0 && fileText}
          <p class="info dim">Nicio tranzactie noua gasita in {fileName}.</p>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    z-index: var(--z-modal); display: flex; align-items: flex-start; justify-content: center;
    padding-top: 10vh; padding-left: var(--space-md); padding-right: var(--space-md);
  }
  .modal {
    background: var(--bg-surface); border: 1px solid var(--border);
    border-radius: var(--radius-lg); width: 100%; max-width: 700px;
    max-height: 70vh; display: flex; flex-direction: column;
    box-shadow: var(--shadow-lg);
  }
  .modal-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
  }
  .modal-header h3 { font-size: var(--font-base); font-weight: 600; color: var(--text); }
  .modal-header button { color: var(--text-dim); }
  .modal-body { padding: var(--space-lg); overflow-y: auto; }

  .file-picker {
    display: flex; flex-direction: column; align-items: center; gap: var(--space-sm);
    padding: var(--space-xl); border: 2px dashed var(--border); border-radius: var(--radius-md);
    color: var(--text-dim); cursor: pointer; text-align: center; font-size: var(--font-small);
    transition: border-color var(--dur-fast) var(--ease);
  }
  .file-picker:hover { border-color: var(--accent); }

  .info { font-size: var(--font-small); color: var(--text-secondary); margin-bottom: var(--space-sm); }
  .info.dim { color: var(--text-dim); margin-top: var(--space-sm); }

  .txn-list { display: flex; flex-direction: column; gap: 4px; max-height: 350px; overflow-y: auto; margin-bottom: var(--space-md); }
  .txn-row { display: grid; grid-template-columns: 80px 1fr 80px 160px; gap: 6px; align-items: center; padding: 4px 0; font-size: var(--font-tiny); }
  .txn-date { color: var(--text-dim); font-family: var(--font-mono, inherit); }
  .txn-desc { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .txn-suma { font-family: var(--font-mono, inherit); text-align: right; }
  .txn-suma.credit { color: var(--accent); }
  .txn-suma.debit { color: var(--danger); }
  .txn-row select { padding: 3px 6px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); }

  .btn-apply {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px; font-size: var(--font-small); font-weight: 500;
    background: var(--accent); color: var(--bg); border-radius: var(--radius-sm);
  }
  .btn-apply:hover { opacity: 0.85; }

  .success-msg { display: flex; align-items: center; gap: var(--space-sm); color: var(--success); font-size: var(--font-small); }

  @media (max-width: 768px) {
    .txn-row { grid-template-columns: 70px 1fr 70px; }
    .txn-row select { grid-column: 1 / -1; }
  }
</style>
