<script>
  import { onMount } from 'svelte'
  import { StickyNote, Search, FileText, Folder, FolderOpen, ChevronRight, ArrowLeft } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { toast } from '../stores/ui.svelte.js'
  import { navigate } from '../lib/router.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import Button from '../components/ui/Button.svelte'
  import MarkdownView from '../components/notes/MarkdownView.svelte'

  let notes = $state([])
  let loading = $state(true)
  let error = $state(null)
  let unconfigured = $state(false)
  let search = $state('')
  let searchResults = $state(null)
  let debounceTimer

  let activeNote = $state(null)
  let noteContent = $state('')
  let noteLoading = $state(false)
  let collapsedFolders = $state(loadCollapsed())
  let mobileShowContent = $state(false)

  function loadCollapsed() {
    try { return JSON.parse(localStorage.getItem('notes_collapsed') || '{}') } catch (_) { return {} }
  }

  function toggleFolder(folder) {
    collapsedFolders[folder] = !collapsedFolders[folder]
    try { localStorage.setItem('notes_collapsed', JSON.stringify(collapsedFolders)) } catch (_) {}
  }

  async function loadNotes() {
    loading = true
    try {
      const data = await apiJson('/api/obsidian/notes')
      notes = data.notes || []
      if (data.error && notes.length === 0) unconfigured = true
    } catch (e) { error = e.message } finally { loading = false }
  }

  function onSearch(e) {
    search = e.target.value
    clearTimeout(debounceTimer)
    if (!search.trim()) { searchResults = null; return }
    debounceTimer = setTimeout(async () => {
      try {
        const data = await apiJson(`/api/obsidian/search?q=${encodeURIComponent(search.trim())}`)
        searchResults = data.results || []
      } catch (_) { searchResults = [] }
    }, 300)
  }

  async function openNote(note) {
    activeNote = note
    noteLoading = true
    mobileShowContent = true
    try {
      const data = await apiJson(`/api/obsidian/note?path=${encodeURIComponent(note.path)}`)
      noteContent = data.content || ''
    } catch (e) {
      noteContent = ''
      toast(`Eroare la incarcarea notitei: ${e.message}`, 'error')
    } finally { noteLoading = false }
  }

  function handleWikilink(target) {
    const t = target.toLowerCase()
    const found = notes.find(n => (n.title || '').toLowerCase() === t)
      || notes.find(n => (n.path || '').toLowerCase().endsWith(t + '.md'))
      || notes.find(n => (n.title || '').toLowerCase().includes(t))
    if (found) openNote(found)
    else toast(`Notita "${target}" nu a fost gasita`, 'error')
  }

  onMount(loadNotes)

  const grouped = $derived.by(() => {
    const groups = new Map()
    for (const n of notes) {
      const folder = n.folder || '/'
      if (!groups.has(folder)) groups.set(folder, [])
      groups.get(folder).push(n)
    }
    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  })
</script>

<div class="page">
  <div class="page-header"><StickyNote size={22} /><h1>Notite</h1><span class="count">{notes.length}</span></div>

  {#if loading}
    <div class="panes"><div>{#each Array(6) as _}<div class="skel"><Skeleton width="80%" height="14px" /></div>{/each}</div><Skeleton width="100%" height="300px" /></div>
  {:else if unconfigured}
    <EmptyState icon={StickyNote} title="Vault neconfigurat" description="Configureaza calea catre vault-ul Obsidian in pagina Admin.">
      <Button size="sm" variant="secondary" onclick={() => navigate('/admin')}>Mergi la Admin</Button>
    </EmptyState>
  {:else if error}
    <p class="error-text">Eroare: {error}</p>
  {:else if notes.length === 0}
    <EmptyState icon={StickyNote} title="Nicio notita" description="Vault-ul Obsidian e gol." />
  {:else}
    <div class="panes" class:show-content={mobileShowContent}>
      <aside class="sidebar">
        <div class="search-box">
          <Search size={14} />
          <input type="text" placeholder="Cauta in continut..." value={search} oninput={onSearch} />
        </div>

        {#if searchResults}
          <div class="list-meta">{searchResults.length} rezultate</div>
          <div class="note-list">
            {#each searchResults as r (r.path)}
              <button class="note-item" class:active={activeNote?.path === r.path} onclick={() => openNote(r)}>
                <FileText size={14} />
                <div class="note-item-main">
                  <span class="note-title">{r.title}</span>
                  {#if r.snippet}<span class="note-snippet">{r.snippet}</span>{/if}
                </div>
              </button>
            {/each}
          </div>
        {:else}
          <div class="note-list">
            {#each grouped as [folder, items] (folder)}
              <button class="folder-row" onclick={() => toggleFolder(folder)}>
                {#if collapsedFolders[folder]}<Folder size={14} />{:else}<FolderOpen size={14} />{/if}
                <span>{folder === '/' ? 'Radacina' : folder}</span>
                <span class="folder-count">{items.length}</span>
              </button>
              {#if !collapsedFolders[folder]}
                {#each items as note (note.path)}
                  <button class="note-item indent" class:active={activeNote?.path === note.path} onclick={() => openNote(note)}>
                    <FileText size={14} />
                    <span class="note-title">{note.title}</span>
                  </button>
                {/each}
              {/if}
            {/each}
          </div>
        {/if}
      </aside>

      <section class="content">
        {#if activeNote}
          <button class="back-mobile" onclick={() => mobileShowContent = false}><ArrowLeft size={14} /> Lista</button>
          <div class="note-head">
            <h2>{activeNote.title}</h2>
            <span class="note-path">{activeNote.path}</span>
          </div>
          {#if noteLoading}
            <Skeleton width="100%" height="240px" />
          {:else}
            <MarkdownView content={noteContent} onwikilink={handleWikilink} />
          {/if}
        {:else}
          <div class="placeholder">
            <ChevronRight size={28} />
            <p>Selecteaza o notita din lista.</p>
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .panes { display: grid; grid-template-columns: 300px 1fr; gap: var(--space-md); align-items: start; }

  .sidebar { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-sm); position: sticky; top: var(--space-md); max-height: calc(100dvh - 140px); display: flex; flex-direction: column; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-dim); margin-bottom: var(--space-sm); }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; min-width: 0; }
  .search-box input:focus { box-shadow: none; }
  .search-box:focus-within { border-color: var(--accent); }
  .list-meta { font-size: var(--font-tiny); color: var(--text-dim); padding: 0 var(--space-xs) var(--space-xs); }

  .note-list { overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
  .folder-row { display: flex; align-items: center; gap: var(--space-xs); padding: 6px var(--space-xs); font-size: var(--font-small); font-weight: 600; color: var(--text-secondary); cursor: pointer; border-radius: var(--radius-xs); text-align: left; }
  .folder-row:hover { background: var(--bg-hover); color: var(--text); }
  .folder-count { margin-left: auto; font-size: var(--font-tiny); color: var(--text-dim); font-weight: 400; }

  .note-item { display: flex; align-items: flex-start; gap: var(--space-xs); padding: 6px var(--space-xs); font-size: var(--font-small); color: var(--text-secondary); cursor: pointer; border-radius: var(--radius-xs); border-left: 2px solid transparent; text-align: left; width: 100%; }
  .note-item.indent { padding-left: var(--space-lg); }
  .note-item:hover { background: var(--bg-hover); color: var(--text); }
  .note-item.active { background: var(--accent-subtle); color: var(--accent); border-left-color: var(--accent); }
  .note-item-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .note-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .note-snippet { font-size: var(--font-tiny); color: var(--text-dim); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; white-space: normal; }

  .content { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-lg); min-height: 400px; }
  .note-head { padding-bottom: var(--space-sm); border-bottom: 1px solid var(--border); margin-bottom: var(--space-md); }
  .note-head h2 { font-size: var(--font-h2); font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
  .note-path { font-size: var(--font-tiny); color: var(--text-dim); font-family: var(--font-mono); }
  .placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-sm); min-height: 300px; color: var(--text-dim); font-size: var(--font-small); }

  .back-mobile { display: none; }
  .skel { padding: 6px; }
  .error-text { color: var(--danger); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .panes { grid-template-columns: 1fr; }
    .sidebar { position: static; max-height: none; }
    .panes.show-content .sidebar { display: none; }
    .panes:not(.show-content) .content { display: none; }
    .back-mobile { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-sm); cursor: pointer; min-height: 44px; }
  }
</style>
