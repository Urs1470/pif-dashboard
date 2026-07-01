<script>
  import { Search, Plus, FolderKanban, ListTodo } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import { loadCandidates, scheduleForToday } from '../stores/agenda.svelte.js'
  import { priorityColor, priorityLabel, formatDate } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'

  let { open = $bindable(false) } = $props()

  let q = $state('')
  let items = $state([])
  let loading = $state(false)
  let addingKey = $state(null)
  let searchTimer = null

  async function runSearch() {
    loading = true
    try {
      items = await loadCandidates(q)
    } catch (e) {
      items = []
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      loading = false
    }
  }

  // Load on open and on (debounced) query change. The modal stays mounted, so
  // this effect re-runs whenever `open` or `q` changes.
  $effect(() => {
    if (!open) return
    const query = q
    clearTimeout(searchTimer)
    searchTimer = setTimeout(runSearch, query ? 200 : 0)
    return () => clearTimeout(searchTimer)
  })

  const groups = $derived.by(() => {
    const g = []
    const globals = items.filter(i => i.tip === 'global')
    if (globals.length) g.push({ key: 'global', label: 'Taskuri globale', icon: ListTodo, rows: globals })
    const byProj = new Map()
    for (const it of items.filter(i => i.tip === 'proiect')) {
      const k = it.proiect_id || '—'
      if (!byProj.has(k)) byProj.set(k, { key: k, label: it.proiect_nume || 'Proiect', icon: FolderKanban, rows: [] })
      byProj.get(k).rows.push(it)
    }
    for (const v of byProj.values()) g.push(v)
    return g
  })

  async function pick(it) {
    const key = it.tip + ':' + it.id
    addingKey = key
    try {
      // scheduleForToday reloads the board store, so it updates live behind the modal.
      await scheduleForToday(it.tip, it.id)
      items = items.filter(x => (x.tip + ':' + x.id) !== key)
      toast('Adăugat în Astăzi', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      addingKey = null
    }
  }
</script>

<Modal bind:open title="Adaugă task în Astăzi" size="md">
  <div class="picker">
    <div class="search-box">
      <Search size={15} />
      <input type="text" placeholder="Caută în taskuri..." bind:value={q} />
    </div>

    {#if loading}
      <div class="pk-hint">Se caută...</div>
    {:else if items.length === 0}
      <div class="pk-hint">{q ? 'Niciun task găsit.' : 'Niciun task disponibil de adăugat.'}</div>
    {:else}
      <div class="pk-list">
        {#each groups as grp (grp.key)}
          <div class="pk-group">
            <div class="pk-group-head">
              <grp.icon size={13} />
              <span>{grp.label}</span>
              <span class="pk-group-count">{grp.rows.length}</span>
            </div>
            {#each grp.rows as it (it.tip + ':' + it.id)}
              <button class="pk-row" disabled={addingKey === (it.tip + ':' + it.id)} onclick={() => pick(it)}>
                <span class="pk-prio" style="background: {priorityColor(it.prioritate || 'normal')}"></span>
                <span class="pk-title">{it.titlu}</span>
                {#if it.data_scadenta}<span class="pk-scad">termen {formatDate(it.data_scadenta)}</span>{/if}
                <span class="pk-add"><Plus size={15} /></span>
              </button>
            {/each}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</Modal>

<style>
  .picker { display: flex; flex-direction: column; gap: var(--space-md); }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }

  .pk-hint { font-size: var(--font-small); color: var(--text-dim); padding: var(--space-lg); text-align: center; }
  .pk-list { display: flex; flex-direction: column; gap: var(--space-md); max-height: 52dvh; overflow-y: auto; scrollbar-width: thin; }
  .pk-group { display: flex; flex-direction: column; }
  .pk-group-head { display: flex; align-items: center; gap: 6px; font-size: var(--font-tiny); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-dim); padding: 4px 2px; }
  .pk-group-count { margin-left: auto; padding: 0 7px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); }

  .pk-row { display: flex; align-items: center; gap: var(--space-sm); padding: 8px 10px; border-radius: var(--radius-sm); text-align: left; cursor: pointer; transition: background var(--dur-fast) var(--ease); }
  .pk-row:hover:not(:disabled) { background: var(--bg-hover); }
  .pk-row:disabled { opacity: 0.5; cursor: default; }
  .pk-prio { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .pk-title { flex: 1; min-width: 0; font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pk-scad { font-size: var(--font-micro); color: var(--text-dim); white-space: nowrap; }
  .pk-add { display: inline-flex; align-items: center; justify-content: center; color: var(--text-faint); flex-shrink: 0; }
  .pk-row:hover .pk-add { color: var(--accent); }
</style>
