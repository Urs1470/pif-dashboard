<script>
  import { onMount } from 'svelte'
  import { StickyNote, Search, FileText } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'

  let notes = $state([])
  let loading = $state(true)
  let error = $state(null)
  let search = $state('')

  async function loadNotes() {
    loading = true
    try {
      const data = await apiJson('/api/obsidian/notes')
      notes = Array.isArray(data) ? data : data.notes || []
    } catch (e) { error = e.message } finally { loading = false }
  }

  const filtered = $derived(
    search ? notes.filter(n => (n.title || n.name || '').toLowerCase().includes(search.toLowerCase())) : notes
  )

  onMount(loadNotes)
</script>

<div class="page">
  <div class="page-header"><StickyNote size={22} /><h1>Notite</h1><span class="count">{notes.length}</span></div>

  <div class="toolbar">
    <div class="search-box"><Search size={14} /><input type="text" placeholder="Cauta notite..." bind:value={search} /></div>
  </div>

  {#if loading}
    <div class="list">{#each Array(4) as _}<Skeleton height="60px" />{/each}</div>
  {:else if error}
    <p class="error-text">Eroare: {error}</p>
  {:else if filtered.length === 0}
    <EmptyState icon={StickyNote} title="Nicio notita" description="Vault-ul Obsidian e gol sau nu e conectat." />
  {:else}
    <div class="list">
      {#each filtered as note}
        <div class="note-card">
          <FileText size={16} />
          <div class="note-content">
            <div class="note-title">{note.title || note.name || '—'}</div>
            {#if note.excerpt || note.preview}<div class="note-excerpt">{note.excerpt || note.preview}</div>{/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }
  .toolbar { margin-bottom: var(--space-md); }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-dim); max-width: 400px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; }
  .search-box:focus-within { border-color: var(--accent); }
  .list { display: flex; flex-direction: column; gap: var(--space-sm); }
  .note-card { display: flex; gap: var(--space-sm); padding: var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); }
  .note-card:hover { border-color: var(--text-dim); }
  .note-content { flex: 1; min-width: 0; }
  .note-title { font-size: var(--font-small); font-weight: 500; color: var(--text); }
  .note-excerpt { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .error-text { color: var(--danger); }

  @media (max-width: 768px) { .page { padding: var(--space-md); } .search-box { max-width: none; } }
</style>
