<script>
  import { onMount } from 'svelte'
  import { fade, slide } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { StickyNote, Search, Folder, FolderOpen, ChevronRight, ChevronDown, ArrowLeft } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
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

  function toggleFolder(folderPath) {
    collapsedFolders[folderPath] = !collapsedFolders[folderPath]
    try { localStorage.setItem('notes_collapsed', JSON.stringify(collapsedFolders)) } catch (_) {}
  }

  function buildNoteTree(noteList) {
    const root = { folders: {}, notes: [] }
    for (const n of noteList) {
      const parts = n.path.split('/')
      parts.pop()
      let node = root
      for (const p of parts) {
        if (!node.folders[p]) node.folders[p] = { folders: {}, notes: [] }
        node = node.folders[p]
      }
      node.notes.push(n)
    }
    return root
  }

  function countTreeNotes(node) {
    let c = node.notes.length
    for (const k in node.folders) c += countTreeNotes(node.folders[k])
    return c
  }

  const noteTree = $derived(buildNoteTree(notes))

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
    else toast(`Notița "${target}" nu a fost găsită`, 'error')
  }

  onMount(loadNotes)
</script>

{#snippet treeNode(node, depth, prefix)}
  {#each Object.keys(node.folders).sort((a, b) => a.localeCompare(b, 'ro')) as fname}
    {@const fullPath = prefix ? prefix + '/' + fname : fname}
    {@const child = node.folders[fname]}
    {@const isCollapsed = collapsedFolders[fullPath]}
    <button class="folder-row" style="padding-left: {12 + depth * 14}px" onclick={() => toggleFolder(fullPath)}>
      {#if isCollapsed}<Folder size={14} />{:else}<FolderOpen size={14} />{/if}
      <span>{fname}</span>
      <span class="folder-count">{countTreeNotes(child)}</span>
    </button>
    {#if !isCollapsed}
      <div transition:slide|local={{ duration: motionDuration(DUR_BASE) }}>
        {@render treeNode(child, depth + 1, fullPath)}
      </div>
    {/if}
  {/each}
  {#each node.notes.slice().sort((a, b) => (a.title || '').localeCompare(b.title || '', 'ro')) as note (note.path)}
    <button class="note-item" style="padding-left: {12 + depth * 14}px" class:active={activeNote?.path === note.path} onclick={() => openNote(note)}>
      <SolidIcon name="file" size={14} />
      <span class="note-title">{note.title}</span>
    </button>
  {/each}
{/snippet}

<div class="page">
  <div class="page-header"><SolidIcon name="notes" size={22} /><h1>Notițe</h1><span class="count">{notes.length}</span></div>

  {#if loading}
    <div class="panes"><div>{#each Array(6) as _}<div class="skel"><Skeleton width="80%" height="14px" /></div>{/each}</div><Skeleton width="100%" height="300px" /></div>
  {:else if unconfigured}
    <EmptyState icon={StickyNote} title="Vault neconfigurat" description="Configurează calea către vault-ul Obsidian în pagina Admin.">
      <Button size="sm" variant="secondary" onclick={() => navigate('/admin')}>Mergi la Admin</Button>
    </EmptyState>
  {:else if error}
    <p class="error-text">Eroare: {error}</p>
  {:else if notes.length === 0}
    <EmptyState icon={StickyNote} title="Nicio notiță" description="Vault-ul Obsidian e gol." />
  {:else}
    <div class="panes" class:show-content={mobileShowContent}>
      <aside class="sidebar cell-in">
        <div class="search-box">
          <Search size={14} />
          <input type="text" placeholder="Caută în conținut..." value={search} oninput={onSearch} />
        </div>

        {#if searchResults}
          <div class="list-meta">{searchResults.length} rezultate</div>
          <div class="note-list">
            {#each searchResults as r (r.path)}
              <button class="note-item" class:active={activeNote?.path === r.path} onclick={() => openNote(r)}>
                <SolidIcon name="file" size={14} />
                <div class="note-item-main">
                  <span class="note-title">{r.title}</span>
                  {#if r.snippet}<span class="note-snippet">{r.snippet}</span>{/if}
                </div>
              </button>
            {/each}
          </div>
        {:else}
          <div class="note-list">
            {@render treeNode(noteTree, 0, '')}
          </div>
        {/if}
      </aside>

      <section class="content cell-in">
        {#key activeNote?.path}
        <div class="note-pane" in:fade={{ duration: motionDuration(DUR_FAST) }}>
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
            <p>Selectează o notiță din listă.</p>
          </div>
        {/if}
        </div>
        {/key}
      </section>
    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); }
  .count { display: inline-flex; align-items: center; justify-content: center; min-width: 19px; height: 19px; padding: 0 5px; font-family: var(--font-mono); font-size: var(--font-micro); font-weight: var(--fw-semibold); line-height: 1; font-variant-numeric: tabular-nums; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent-on-subtle); border: 1px solid var(--accent-ring); }

  .panes { display: grid; grid-template-columns: 300px 1fr; gap: var(--space-md); align-items: start; }

  .sidebar { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-sm); position: sticky; top: var(--space-md); max-height: calc(100dvh - 140px); display: flex; flex-direction: column; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-dim); margin-bottom: var(--space-sm); }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; min-width: 0; }
  .search-box input:focus { box-shadow: none; }
  .search-box:focus-within { border-color: var(--accent); box-shadow: var(--focus-ring); }
  .list-meta { font-size: var(--font-tiny); color: var(--text-dim); padding: 0 var(--space-xs) var(--space-xs); }

  .note-list { overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
  .folder-row { display: flex; align-items: center; gap: var(--space-xs); padding: 6px var(--space-xs); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); cursor: pointer; border-radius: var(--radius-sm); text-align: left; }
  .folder-row:hover { background: var(--bg-panel); color: var(--text); }
  .folder-count { margin-left: auto; font-size: var(--font-tiny); color: var(--text-dim); font-weight: var(--fw-normal); }

  .note-item { display: flex; align-items: flex-start; gap: var(--space-xs); padding: 6px var(--space-xs); font-size: var(--font-small); color: var(--text-secondary); cursor: pointer; border-radius: var(--radius-sm); text-align: left; width: 100%; transition: background-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
  .note-item:hover { background: var(--bg-panel); color: var(--text); }
  .note-item.active { background: var(--accent-subtle); color: var(--accent); }
  .note-item-main { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .note-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .note-snippet { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-snug); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; white-space: normal; }

  .content { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-lg); min-height: 400px; }
  .note-head { padding-bottom: var(--space-sm); border-bottom: 1px solid var(--border); margin-bottom: var(--space-md); }
  .note-head h2 { font-family: var(--font-heading); font-size: var(--font-h2); font-weight: var(--fw-bold); color: var(--text); letter-spacing: -0.02em; }
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
