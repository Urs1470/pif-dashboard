<script>
  import { Search, Home, FolderKanban, ListTodo, Cpu, StickyNote, Wallet, Settings, FileText, NotebookPen, CalendarCheck, Users, AlertTriangle, BookOpen, CheckSquare } from '@lucide/svelte'
  import { navigate, router } from '../../lib/router.svelte.js'
  import { apiJson } from '../../lib/api.js'

  let open = $state(false)
  let query = $state('')
  let selected = $state(0)
  let inputEl = $state(null)
  let searchResults = $state([])
  let searching = $state(false)
  let searchTimer = null

  const commands = [
    { label: 'Acasa', path: '/', icon: Home, keywords: 'home dashboard' },
    { label: 'Proiecte', path: '/projects', icon: FolderKanban, keywords: 'projects lista' },
    { label: 'Taskuri', path: '/tasks', icon: ListTodo, keywords: 'tasks todo' },
    { label: 'Parametri', path: '/params', icon: Cpu, keywords: 'params drive fault' },
    { label: 'Notite', path: '/notes', icon: StickyNote, keywords: 'notes obsidian' },
    { label: 'Budget', path: '/budget', icon: Wallet, keywords: 'budget cheltuieli' },
    { label: 'Admin', path: '/admin', icon: Settings, keywords: 'admin stats export' },
  ]

  const TYPE_META = {
    proiect:     { label: 'Proiecte', icon: FolderKanban },
    observatie:  { label: 'Observatii', icon: FileText },
    task:        { label: 'Taskuri', icon: CheckSquare },
    global_task: { label: 'Taskuri zilnice', icon: CalendarCheck },
    jurnal:      { label: 'Jurnal', icon: NotebookPen },
    echipament:  { label: 'Echipamente', icon: Cpu },
    client:      { label: 'Clienti', icon: Users },
    parametru:   { label: 'Parametri', icon: Cpu },
    fault_code:  { label: 'Coduri eroare', icon: AlertTriangle },
    obsidian:    { label: 'Notite', icon: BookOpen },
  }

  const isSearchMode = $derived(query.trim().length >= 2)

  const navFiltered = $derived(
    query.trim()
      ? commands.filter(c =>
          (c.label + ' ' + c.keywords).toLowerCase().includes(query.toLowerCase())
        )
      : commands
  )

  const flatResults = $derived.by(() => {
    if (!isSearchMode) return []
    const items = []
    let lastType = null
    for (const r of searchResults) {
      if (r.type !== lastType) {
        items.push({ _group: true, type: r.type, label: TYPE_META[r.type]?.label || r.type })
        lastType = r.type
      }
      items.push(r)
    }
    return items
  })

  const totalItems = $derived(isSearchMode ? flatResults.length : navFiltered.length)

  function selectableIndex(idx) {
    if (!isSearchMode) return true
    return idx < flatResults.length && !flatResults[idx]._group
  }

  function nextSelectable(from, dir) {
    let i = from + dir
    while (i >= 0 && i < totalItems) {
      if (selectableIndex(i)) return i
      i += dir
    }
    return from
  }

  $effect(() => {
    if (isSearchMode) {
      clearTimeout(searchTimer)
      const q = query.trim()
      searching = true
      searchTimer = setTimeout(async () => {
        try {
          const data = await apiJson(`/api/search?q=${encodeURIComponent(q)}`)
          searchResults = data.results || []
        } catch (_) {
          searchResults = []
        } finally { searching = false }
      }, 200)
    } else {
      searchResults = []
      searching = false
    }
    selected = 0
  })

  function handleKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); selected = nextSelectable(selected, 1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); selected = nextSelectable(selected, -1) }
    else if (e.key === 'Enter') { activateSelected() }
    else if (e.key === 'Escape') { close() }
  }

  function activateSelected() {
    if (!isSearchMode) {
      if (navFiltered[selected]) go(navFiltered[selected])
      return
    }
    const item = flatResults[selected]
    if (!item || item._group) return
    activateResult(item)
  }

  function activateResult(r) {
    close()
    switch (r.type) {
      case 'proiect':
      case 'task':
      case 'observatie':
      case 'jurnal':
      case 'echipament':
        if (r.proiect_id) navigate(`/projects/${r.proiect_id}`)
        else if (r.id) navigate(`/projects/${r.id}`)
        break
      case 'global_task':
        navigate('/tasks')
        break
      case 'parametru':
        navigate('/params')
        break
      case 'fault_code':
        navigate('/params')
        break
      case 'obsidian':
        navigate('/notes')
        break
      case 'client':
        navigate('/projects')
        break
      default:
        break
    }
  }

  function go(cmd) {
    navigate(cmd.path)
    close()
  }

  function close() {
    open = false
    query = ''
    searchResults = []
    selected = 0
  }

  function onGlobalKey(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      open = !open
      if (open) requestAnimationFrame(() => inputEl?.focus())
    }
  }

  const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

  function highlight(text, q) {
    if (!text) return ''
    // snippets from /api/search can contain raw HTML (WYSIWYG observatii) — strip
    // tags and collapse whitespace so results stay one line, then escape the rest
    const plain = String(text).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
    const escaped = plain.replace(/[&<>"']/g, ch => ESC_MAP[ch])
    if (!q) return escaped
    const safe = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return escaped.replace(new RegExp(`(${safe})`, 'gi'), '<mark>$1</mark>')
  }

  $effect(() => {
    window.addEventListener('keydown', onGlobalKey)
    return () => window.removeEventListener('keydown', onGlobalKey)
  })
</script>

{#if open}
  <div class="palette-backdrop" onclick={close} role="presentation">
    <div class="palette" onclick={(e) => e.stopPropagation()} onkeydown={handleKey} role="listbox" tabindex="-1">
      <div class="palette-search">
        <Search size={16} />
        <input
          bind:this={inputEl}
          type="text"
          bind:value={query}
          placeholder="Cauta in tot dashboardul..."
          autocomplete="off"
          spellcheck="false"
        />
        <kbd>Esc</kbd>
      </div>
      <div class="palette-list">
        {#if !isSearchMode}
          {#each navFiltered as cmd, i (cmd.path)}
            <button
              class="palette-item"
              class:selected={i === selected}
              onclick={() => go(cmd)}
              onmouseenter={() => selected = i}
              role="option"
              aria-selected={i === selected}
            >
              <cmd.icon size={16} />
              <span>{cmd.label}</span>
              {#if router.path === cmd.path || (cmd.path !== '/' && router.path.startsWith(cmd.path))}
                <span class="current">curent</span>
              {/if}
            </button>
          {/each}
          {#if navFiltered.length === 0}
            <div class="palette-empty">Niciun rezultat</div>
          {/if}
        {:else if searching}
          <div class="palette-empty">Se cauta...</div>
        {:else if flatResults.length === 0}
          <div class="palette-empty">Niciun rezultat pentru „{query.trim()}"</div>
        {:else}
          {#each flatResults as item, i}
            {#if item._group}
              {@const Icon = TYPE_META[item.type]?.icon || Search}
              <div class="group-label">
                <Icon size={12} />
                {item.label}
              </div>
            {:else}
              <button
                class="palette-item result"
                class:selected={i === selected}
                onclick={() => activateResult(item)}
                onmouseenter={() => selected = i}
                role="option"
                aria-selected={i === selected}
              >
                <div class="result-body">
                  <span class="result-title">{@html highlight(item.title, query.trim())}</span>
                  {#if item.subtitle}<span class="result-sub">{item.subtitle}</span>{/if}
                  {#if item.snippet}<span class="result-snippet">{@html highlight(item.snippet, query.trim())}</span>{/if}
                </div>
              </button>
            {/if}
          {/each}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .palette-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: var(--z-modal);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
    animation: fadeIn var(--dur-fast) var(--ease);
  }

  .palette {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 560px;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    animation: slideUp var(--dur-fast) var(--ease);
  }

  .palette-search {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
  }
  .palette-search input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text);
    font-size: var(--font-body);
  }
  .palette-search input::placeholder { color: var(--text-dim); }
  .palette-search kbd {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    padding: 2px 6px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-xs);
    color: var(--text-dim);
  }

  .palette-list {
    max-height: 400px;
    overflow-y: auto;
    padding: var(--space-xs);
  }

  .palette-item {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    width: 100%;
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--font-small);
    text-align: left;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease);
  }
  .palette-item:hover,
  .palette-item.selected {
    background: var(--bg-hover);
    color: var(--text);
  }
  .current {
    margin-left: auto;
    font-size: var(--font-tiny);
    color: var(--accent);
    opacity: 0.7;
  }

  .group-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-tiny);
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: .04em;
    padding: var(--space-sm) var(--space-md) 2px;
    margin-top: var(--space-xs);
  }
  .group-label:first-child { margin-top: 0; }

  .palette-item.result {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 6px var(--space-md);
  }
  .result-body {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
    width: 100%;
  }
  .result-title {
    font-size: var(--font-small);
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-sub {
    font-size: var(--font-tiny);
    color: var(--text-dim);
  }
  .result-snippet {
    font-size: var(--font-tiny);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .palette-item.result :global(mark) {
    background: var(--accent-subtle);
    color: var(--accent);
    border-radius: 2px;
    padding: 0 1px;
  }

  .palette-empty {
    padding: var(--space-lg);
    text-align: center;
    color: var(--text-dim);
    font-size: var(--font-small);
  }

  @keyframes fadeIn { from { opacity: 0; } }
  @keyframes slideUp { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }

  @media (max-width: 768px) {
    .palette-backdrop { padding-top: var(--space-lg); padding-left: var(--space-md); padding-right: var(--space-md); }
  }
</style>
