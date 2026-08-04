<script>
  import { Search, FolderKanban, FileText, CalendarCheck, Users, CheckSquare } from '@lucide/svelte'
  import { fade, scale } from 'svelte/transition'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { navigate, router } from '../../lib/router.svelte.js'
  import { focusHref } from '../../lib/focus.js'
  import { apiJson } from '../../lib/api.js'
  import { motionDuration, DUR_FAST } from '../../lib/motion.svelte.js'

  let open = $state(false)
  let query = $state('')
  let selected = $state(0)
  let inputEl = $state(null)
  let searchResults = $state([])
  let searching = $state(false)
  let searchTimer = null

  const commands = [
    { label: 'Acasă', path: '/', solid: 'home', keywords: 'home dashboard acasa' },
    { label: 'Proiecte', path: '/projects', solid: 'projects', keywords: 'projects lista' },
    { label: 'Taskuri', path: '/tasks', solid: 'tasks', keywords: 'tasks todo munca' },
    // Vederea personala nu are loc in Dock (plin la cinci pe telefon) — paleta
    // e drumul ei de rezerva, pe langa comutatorul de pe /tasks.
    { label: 'Taskuri personale', path: '/tasks?sfera=personal', solid: 'tasks', keywords: 'personal acasa cumparaturi in afara jobului' },
    { label: 'Planificator', path: '/plan', solid: 'plan', keywords: 'plan gantt planificator perioade' },
    { label: 'Calendar', path: '/calendar', solid: 'calendar', keywords: 'calendar unde sunt deplasare perioade zile teren replanifica' },
    // Departament lipsea de aici. Pe desktop nu se vedea, fiindca era in Dock;
    // pe telefon Dock-ul tine acum doar cinci lucruri, deci paleta e SINGURUL
    // drum catre ea. O ruta scoasa din navigatie fara sa fie si in paleta e o
    // ruta pe care nu o mai poti deschide de pe telefon.
    { label: 'Departament', path: '/departament', solid: 'departament', keywords: 'departament echipa plan cine e unde powerpoint' },
    { label: 'Calculator', path: '/calculator', solid: 'calculator', keywords: 'calculator actionari motor cuplu putere afinitate drive' },
  ]

  const TYPE_META = {
    proiect:     { label: 'Proiecte', icon: FolderKanban },
    observatie:  { label: 'Observații', icon: FileText },
    task:        { label: 'Taskuri', icon: CheckSquare },
    global_task: { label: 'Taskuri zilnice', icon: CalendarCheck },
    client:      { label: 'Clienți', icon: Users },
  }

  // Scoase din scopul aplicatiei (v28): parametri, fault codes, echipamente,
  // atasamente si browserul de vault. Backend-ul le mai poate returna pana la
  // migratie — le filtram aici ca sa nu mai apara in paleta.
  const DROPPED_TYPES = new Set(['parametru', 'fault_code', 'echipament', 'atasament', 'obsidian'])

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
    // PAGINILE INTAI, si in modul de cautare.
    // Pana acum lista de rute disparea de indata ce scriai a doua litera, deci
    // `keywords` de pe comenzi nu se putea folosi niciodata: cautand „calculator"
    // primeai note si proiecte, dar nu si PAGINA Calculator. Se vedea putin cat
    // timp toate rutele stateau in Dock; de cand pe telefon Dock-ul tine cinci,
    // paleta e singurul drum spre celelalte — iar reflexul e sa scrii unde vrei
    // sa ajungi, nu sa cauti ruta intr-o lista.
    if (navFiltered.length) {
      items.push({ _group: true, type: 'ruta', label: 'Pagini' })
      for (const c of navFiltered) items.push({ ...c, _nav: true })
    }
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
          searchResults = (data.results || []).filter(r => !DROPPED_TYPES.has(r.type))
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
    let item = flatResults[selected]
    // selectia initiala (0) cade pe header-ul de grup — Enter activeaza
    // primul rezultat real de sub el
    if (item?._group) item = flatResults[selected + 1]
    if (!item || item._group) return
    activateResult(item)
  }

  function activateResult(r) {
    // O ruta din grupul „Pagini" nu e un rezultat de cautare: nu are id si nu se
    // deschide, se NAVIGHEAZA la ea.
    if (r._nav) { go(r); return }
    close()
    switch (r.type) {
      case 'proiect':
      case 'task':
      case 'observatie':
        navigate(`/tasks${r.id ? `?focus=global:${r.id}` : ''}`)
        break
      case 'global_task': {
        // Un task personal aterizeaza in VEDEREA lui de pe /tasks; focusHref
        // stie sa lipeasca `focus` cu `&` cand calea are deja query.
        const base = r.sfera === 'personal' ? '/tasks?sfera=personal' : '/tasks'
        navigate(r.id ? focusHref(base, 'global', r.id) : base)
        break
      }
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
    const plain = String(text)
      .replace(/<[^>]*>/g, ' ')
      .replace(/&nbsp;/gi, ' ')
      .replace(/&lt;/gi, '<').replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"').replace(/&#39;/gi, "'")
      .replace(/&amp;/gi, '&')
      .replace(/\s+/g, ' ').trim()
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
  <div class="palette-backdrop" onclick={close} role="presentation" transition:fade={{ duration: motionDuration(DUR_FAST) }}>
    <div class="palette" onclick={(e) => e.stopPropagation()} onkeydown={handleKey} role="listbox" tabindex="-1" transition:scale={{ start: 0.96, duration: motionDuration(DUR_FAST) }}>
      <div class="palette-search">
        <Search size={16} />
        <input
          bind:this={inputEl}
          type="text"
          bind:value={query}
          placeholder="Caută în tot dashboardul..."
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
              <SolidIcon name={cmd.solid} size={16} />
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
          <div class="palette-empty">Se caută...</div>
        {:else if flatResults.length === 0}
          <div class="palette-empty">Niciun rezultat pentru „{query.trim()}"</div>
        {:else}
          {#each flatResults as item, i (item._group ? 'g:' + item.type : item._nav ? 'n:' + item.path : item.type + ':' + item.id)}
            {#if item._group}
              {@const Icon = TYPE_META[item.type]?.icon || Search}
              <div class="group-label">
                <Icon size={12} />
                {item.label}
              </div>
            {:else if item._nav}
              <button
                class="palette-item"
                class:selected={i === selected}
                onclick={() => go(item)}
                onmouseenter={() => selected = i}
                role="option"
                aria-selected={i === selected}
              >
                <SolidIcon name={item.solid} size={16} />
                <span>{item.label}</span>
                {#if router.path === item.path || (item.path !== '/' && router.path.startsWith(item.path))}
                  <span class="current">curent</span>
                {/if}
              </button>
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
      backdrop-filter: blur(7px);
    -webkit-backdrop-filter: blur(7px);
  }

  .palette {
    background: var(--bg-overlay);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 560px;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
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
    min-height: 38px;
    padding: 6px 14px;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--radius-full);
    outline: none;
    color: var(--text);
    font-size: var(--font-body);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .palette-search input:focus,
  .palette-search input:focus-visible {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
  }
  .palette-search input::placeholder { color: var(--text-dim); }
  .palette-search kbd {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    padding: 2px 6px;
    background: var(--bg-input);
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
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
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

  @media (max-width: 768px) {
    .palette-backdrop { padding-top: calc(var(--space-lg) + var(--safe-top)); padding-left: calc(var(--space-md) + var(--safe-left)); padding-right: calc(var(--space-md) + var(--safe-right)); }
    /* Paleta ramane SUS, nu devine sheet: aici se deschide tastatura imediat, iar
       tastatura ocupa jumatatea de jos. Un sheet ar fi impins direct sub ea.
       Ce se schimba e cat loc are lista si cat de mari sunt randurile. */
    .palette-search { padding: var(--space-12) var(--space-md); }
    .palette-search input { min-height: var(--tap-min); }
    /* Sugestia de scurtatura nu are ce cauta pe un ecran fara tastatura fizica. */
    .palette-search kbd { display: none; }
    .palette-list { max-height: min(400px, 52dvh); overscroll-behavior: contain; }
    .palette-item { min-height: var(--tap-min); }
  }
</style>
