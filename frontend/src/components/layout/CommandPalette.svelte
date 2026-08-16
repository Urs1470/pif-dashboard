<script>
  import { Search, FolderKanban, FileText, CalendarCheck, Users, CheckSquare } from '@lucide/svelte'
  import { fade } from 'svelte/transition'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { navigate, router } from '../../lib/router.svelte.js'
  import { focusHref } from '../../lib/focus.js'
  import { apiJson } from '../../lib/api.js'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'
  import { nivelNou, nivelInchis } from '../ui/Modal.svelte'

  // 6px + scale(.985) intr-o singura tranzitie: `fly` si `scale` nu se pot pune
  // pe acelasi nod (fiecare ar rescrie `transform`-ul celeilalte).
  function paletaIn(node) {
    return {
      duration: motionDuration(DUR_BASE), easing: EASE,
      css: (t, u) => `opacity: ${t}; transform: translateY(${u * 6}px) scale(${0.985 + t * 0.015});`,
    }
  }

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
        } finally {
          searching = false
          if (flatResults[selected]?._group) {
            const next = nextSelectable(selected, 1)
            if (next !== selected) selected = next
          }
        }
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
    else if (e.key === 'Tab') { e.preventDefault() }
    else if (e.key === 'Home') { e.preventDefault(); selected = nextSelectable(-1, 1) }
    else if (e.key === 'End') { e.preventDefault(); selected = nextSelectable(flatResults.length, -1) }
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

  /** Deschide paleta din afara (docul de pe telefon).
   *
   *  Exista fiindca butonul de cautare din doc trimitea un `KeyboardEvent`
   *  SINTETIC catre fereastra si spera ca paleta il asculta — adica lega un
   *  buton de o scurtatura de tastatura, pe un ecran unde nu exista Ctrl. Mergea,
   *  dar daca paleta si-ar fi schimbat vreodata ascultatorul, butonul s-ar fi
   *  stins fara nicio eroare nicaieri. */
  export function deschide() {
    open = true
    requestAnimationFrame(() => inputEl?.focus())
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

  // PALETA INTRA IN STIVA DE MODALE (T14).
  // Statea pe `--z-modal` fix, deci Ctrl+K peste o foaie deschisa punea doua
  // voaluri la ACELASI nivel: ordinea de pictare venea din ordinea din DOM, iar
  // cele doua opacitati se inmulteau. Anuntandu-se, foaia de dedesubt isi stinge
  // voalul si paleta se aseaza deasupra, cu z-index calculat din nivel.
  let nivel = $state(0)
  $effect(() => {
    if (!open) return
    nivel = nivelNou()
    return () => { nivelInchis(); nivel = 0 }
  })
</script>

{#if open}
  <!-- Contractul de miscare: paleta soseste pe 220, cu 6px de coborare si o
       scalare abia simtita (.985) — nu 120 cu .96, care o facea sa pocneasca. -->
  <div class="palette-backdrop" onclick={close} role="presentation"
       style:--nivel={nivel} style:z-index="calc(var(--z-modal) + (var(--nivel) - 1) * 10)"
       transition:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
    <div class="palette" onclick={(e) => e.stopPropagation()} onkeydown={handleKey} role="dialog" aria-label="Paletă de comenzi" tabindex="-1"
         transition:paletaIn>
      <!-- RANDUL DE SUS *ESTE* CAMPUL.
           Era o pastila cu chenar si fundal propriu, asezata INAUNTRUL panoului:
           doua cutii concentrice, si a doua nu adauga nimic — nu poti scrie
           altundeva in paleta, deci nu e nevoie sa marchezi unde se scrie.
           Acum inputul n-are nici chenar, nici fundal; il delimiteaza randul. -->
      <div class="palette-search">
        <Search size={17} strokeWidth={1.5} />
        <input
          bind:this={inputEl}
          type="text"
          bind:value={query}
          role="combobox"
          aria-expanded="true"
          aria-controls="cp-results"
          aria-autocomplete="list"
          placeholder="Caută în tot dashboardul..."
          autocomplete="off"
          spellcheck="false"
        />
        <kbd>Esc</kbd>
      </div>
      <div class="palette-list" id="cp-results" role="listbox">
        {#if !isSearchMode}
          {#each navFiltered as cmd, i (cmd.path)}
            <button
              class="palette-item"
              class:selected={i === selected}
              onclick={() => go(cmd)}
              role="option"
              aria-selected={i === selected}
            >
              <SolidIcon name={cmd.solid} size={16} />
              <span class="pi-eticheta">{cmd.label}</span>
              {#if router.path === cmd.path || (cmd.path !== '/' && router.path.startsWith(cmd.path))}
                <span class="current">curent</span>
              {/if}
              {#if i === selected}<span class="enter" aria-hidden="true">⏎</span>{/if}
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
                  role="option"
                aria-selected={i === selected}
              >
                <SolidIcon name={item.solid} size={16} />
                <span class="pi-eticheta">{item.label}</span>
                {#if router.path === item.path || (item.path !== '/' && router.path.startsWith(item.path))}
                  <span class="current">curent</span>
                {/if}
                {#if i === selected}<span class="enter" aria-hidden="true">⏎</span>{/if}
              </button>
            {:else}
              <button
                class="palette-item result"
                class:selected={i === selected}
                onclick={() => activateResult(item)}
                  role="option"
                aria-selected={i === selected}
              >
                <div class="result-body">
                  <span class="result-title">{@html highlight(item.title, query.trim())}</span>
                  {#if item.subtitle}<span class="result-sub">{item.subtitle}</span>{/if}
                  {#if item.snippet}<span class="result-snippet">{@html highlight(item.snippet, query.trim())}</span>{/if}
                </div>
                {#if i === selected}<span class="enter" aria-hidden="true">⏎</span>{/if}
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
    background: var(--scrim);
    z-index: var(--z-modal);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
    /* FARA BLUR. Paleta se desprinde prin UMBRA — la fel ca modalul, toastul si
       docul. Sticla era singurul loc unde separarea se facea altfel, si costa:
       `backdrop-filter` forteaza un strat de compozitare cat ecranul, animat
       la fiecare deschidere, exact cand se asteapta si raspunsul tastaturii. */
  }

  .palette {
    background: var(--bg-overlay);
    border-radius: var(--radius-md);
    width: 100%;
    max-width: 592px;
    box-shadow: var(--shadow-md);
    overflow: hidden;
  }

  /* Randul de cautare E campul: inputul n-are chenar, fundal sau raza proprie. */
  .palette-search {
    display: flex;
    align-items: center;
    gap: var(--space-12);
    height: 56px;
    padding: 0 var(--space-md);
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
  }
  .palette-search input {
    flex: 1;
    min-width: 0;
    height: 100%;
    padding: 0;
    background: none;
    border: none;
    outline: none;
    color: var(--text);
    font-family: inherit;
    font-size: var(--font-body);
  }
  .palette-search input:focus,
  .palette-search input:focus-visible {
    outline: none;
    border: none;
    box-shadow: none;
  }
  .palette-search input::placeholder { color: var(--text-dim); }
  .palette-search kbd {
    font-family: var(--font-mono);
    font-size: var(--font-label);
    padding: 3px 7px;
    background: var(--bg-elevated);
    border-radius: var(--radius-xs);
    color: var(--text-dim);
  }

  .palette-list {
    max-height: 400px;
    overflow-y: auto;
    padding: 6px;
  }

  .palette-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 40px;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--font-body);
    text-align: left;
    cursor: pointer;
    transition: background-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
  }
  .pi-eticheta { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* SELECTIA E UN CURSOR DE TASTATURA, NU UN HOVER.
     Pana acum `mouseenter` muta `selected`, deci plimbarea mouse-ului peste
     lista schimba ce face Enter — iar Enter e tot rostul paletei. Acum hoverul
     spune doar „esti peste", si numai cursorul poarta tenta de accent si `⏎`.
     Asa Enter se invata din desen si nu mai e nevoie de o bara de ajutor jos. */
  .palette-item:hover { background: var(--bg-hover); color: var(--text); }
  .palette-item.selected {
    background: var(--accent-subtle);
    color: var(--accent-deep);
    font-weight: var(--fw-medium);
  }
  .enter {
    flex: none;
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--accent-deep);
    margin-left: 8px;
  }

  /* „curent" e o eticheta, nu un accent: pe o suprafata neutra, cu text estompat.
     Era accentul la `opacity: .7` — adica accentul stins, care nu e nici accent
     (nu mai are contrastul lui) nici neutru (isi pastreaza nuanta). */
  .current {
    flex: none;
    padding: 2px 8px;
    border-radius: var(--radius-xs);
    background: var(--bg-elevated);
    color: var(--text-dim);
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
  }

  .group-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    padding: var(--space-sm) 10px 2px;
    margin-top: var(--space-xs);
  }
  .group-label:first-child { margin-top: 0; }

  .palette-item.result {
    align-items: flex-start;
    gap: 8px;
    padding: 7px 10px;
  }
  .result-body {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
    width: 100%;
  }
  .result-title {
    font-size: var(--font-body);
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .palette-item.result.selected .result-title { color: var(--accent-deep); }
  .result-sub {
    font-size: var(--font-small);
    color: var(--text-dim);
  }
  .result-snippet {
    font-size: var(--font-small);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .palette-item.result :global(mark) {
    background: var(--accent-subtle);
    color: var(--accent-deep);
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
    /* Paleta ramane SUS, nu devine foaie: aici se deschide tastatura imediat, iar
       tastatura ocupa jumatatea de jos. O foaie ar fi impinsa direct sub ea. */
    .palette-search { height: 56px; padding: 0 var(--space-md); }
    /* Sugestia de scurtatura n-are ce cauta pe un ecran fara tastatura fizica. */
    .palette-search kbd { display: none; }
    /* `--kb`: cu tastatura sus, `52dvh` ramanea inaltimea ecranului INTREG in
       WebView-ul Capacitor, deci lista se intindea pe sub tastatura si vedeai
       un singur rezultat. Variabila o scrie `Modal.svelte` din `visualViewport`. */
    .palette-list { max-height: min(400px, calc(52dvh - var(--kb, 0px))); overscroll-behavior: contain; }
    .palette-item { min-height: var(--tap-min); }
    /* `⏎` presupune o tasta Enter. Pe telefon randul se atinge. */
    .enter { display: none; }
  }
</style>
