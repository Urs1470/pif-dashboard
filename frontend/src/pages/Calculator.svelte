<script>
  import { tick } from 'svelte'
  import { Calculator as CalcIcon, Info, BookOpen, Maximize2, Search, X, ChevronRight, Star, Clock } from '@lucide/svelte'
  import { MODULES, MODULE_ORDER, SOURCES, CATEGORIES, MOTOR_FAMS, APPLICATIONS, APP_OF, catOf, docsForModule, symTeX, descLabel, computeModule, computeCharts, fmtNum } from '../lib/driveCalc.js'
  import Formula from '../components/ui/Formula.svelte'
  import MathText from '../components/ui/MathText.svelte'
  import Chart from '../components/ui/Chart.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import { lookupTerm } from '../lib/driveGlossary.js'
  import { runtime } from '../lib/runtime.svelte.js'

  let activeCat = $state('aplicatii')
  let activeMotorFam = $state('asincron')
  let activeApp = $state('pompe-vent')
  let query = $state('')

  // Valorile de intrare per modul, initializate din default-uri.
  let values = $state(
    Object.fromEntries(
      MODULES.map((m) => [m.id, Object.fromEntries(m.fields.map((f) => [f.key, f.default]))])
    )
  )

  const ord = (id) => { const i = MODULE_ORDER.indexOf(id); return i === -1 ? 999 : i }
  const catLabel = (id) => CATEGORIES.find((c) => c.id === id)?.label ?? id

  // Cautare in titlu / subtitlu / etichete & chei (campuri si rezultate).
  function matchQ(m, q) {
    if (m.title.toLowerCase().includes(q)) return true
    if (m.subtitle && m.subtitle.toLowerCase().includes(q)) return true
    for (const f of m.fields) if (f.label.toLowerCase().includes(q) || f.key.toLowerCase().includes(q)) return true
    for (const r of m.results) if (r.label.toLowerCase().includes(q) || r.key.toLowerCase().includes(q)) return true
    return false
  }
  // Lista din tab-ul curent (cautarea NU mai inlocuieste lista — vezi autocomplete-ul acResults).
  const shown = $derived.by(() => {
    if (activeCat === 'aplicatii') return MODULES.filter((m) => APP_OF[m.id] === activeApp).sort((a, b) => ord(a.id) - ord(b.id))
    if (activeCat === 'motoare') return MODULES.filter((m) => catOf(m) === 'motoare' && m.family === activeMotorFam).sort((a, b) => ord(a.id) - ord(b.id))
    return MODULES.filter((m) => catOf(m) === activeCat).sort((a, b) => ord(a.id) - ord(b.id))
  })
  // Autocomplete cautare: max 8 potriviri, doar de la 2 caractere.
  const acResults = $derived.by(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return MODULES.filter((m) => matchQ(m, q)).sort((a, b) => ord(a.id) - ord(b.id)).slice(0, 8)
  })

  // Segmenteaza un text in potriviri/nepotriviri pentru evidentiere la cautare.
  function highlightParts(text, q) {
    const needle = (q || '').trim()
    if (!needle) return [{ text, hit: false }]
    const parts = []; const low = text.toLowerCase(); const nl = needle.toLowerCase()
    let i = 0
    while (i < text.length) {
      const j = low.indexOf(nl, i)
      if (j === -1) { parts.push({ text: text.slice(i), hit: false }); break }
      if (j > i) parts.push({ text: text.slice(i, j), hit: false })
      parts.push({ text: text.slice(j, j + needle.length), hit: true })
      i = j + needle.length
    }
    return parts
  }
  function selectCat(id) { query = ''; activeCat = id }

  // Extrasele de carti (protected) au drept de autor -> vizibile cand esti logat (dashboard mereu;
  // pe /calc doar dupa verificarea autentificarii). runtime.docsOk e reactiv (vezi runtime.svelte.js).
  const docsFor = (m) => docsForModule(m).filter((d) => runtime.docsOk || !d.protected)

  function resetModule(m) {
    for (const f of m.fields) values[m.id][f.key] = f.default
  }

  // Zoom grafic in modal (70%)
  let zoomOpen = $state(false)
  let zoomRef = $state(null)
  function openZoom(m, index) { zoomRef = { mod: m, index }; zoomOpen = true }
  const zoomChart = $derived(zoomRef ? computeCharts(zoomRef.mod, values[zoomRef.mod.id])[zoomRef.index] : null)

  // Definitie marime (glosar) la click pe eticheta
  let termOpen = $state(false)
  let term = $state(null)
  function openTerm(item, m, isResult) {
    term = {
      label: item.label,
      unit: item.unit,
      tex: isResult ? item.tex : null,
      g: lookupTerm(item.key, m.family),
      source: isResult ? (SOURCES[m.id] || null) : null,
      docs: docsFor(m),
    }
    termOpen = true
  }

  // ---- Acordeon: ce module sunt deschise (pe mobil doar unul) ----
  let expanded = $state(new Set())
  let isMobile = $state(false)
  $effect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const upd = () => (isMobile = mq.matches)
    upd(); mq.addEventListener('change', upd)
    return () => mq.removeEventListener('change', upd)
  })
  function isOpen(id) { return expanded.has(id) }
  function toggle(id) {
    const open = expanded.has(id)
    let next
    if (isMobile) next = open ? new Set() : new Set([id])
    else { next = new Set(expanded); if (open) next.delete(id); else next.add(id) }
    if (!open) pushRecent(id)
    expanded = next
  }
  function openModule(id) {
    expanded = isMobile ? new Set([id]) : new Set(expanded).add(id)
    pushRecent(id)
  }

  // ---- Favorite + Recente (localStorage, partajat dashboard + /calc) ----
  function loadLS(k, def) { try { const v = JSON.parse(localStorage.getItem(k)); return Array.isArray(v) ? v : def } catch { return def } }
  let favorites = $state(loadLS('pif-calc-fav', []))
  let recents = $state(loadLS('pif-calc-recent', []))
  $effect(() => { try { localStorage.setItem('pif-calc-fav', JSON.stringify(favorites)) } catch {} })
  $effect(() => { try { localStorage.setItem('pif-calc-recent', JSON.stringify(recents)) } catch {} })
  function isFav(id) { return favorites.includes(id) }
  function toggleFav(id) { favorites = favorites.includes(id) ? favorites.filter((x) => x !== id) : [...favorites, id] }
  function pushRecent(id) { recents = [id, ...recents.filter((x) => x !== id)].slice(0, 5) }
  const byId = (id) => MODULES.find((m) => m.id === id)
  const favMods = $derived(favorites.map(byId).filter(Boolean))
  const recentMods = $derived(recents.map(byId).filter(Boolean))

  // ---- Navigare la un modul (din chip / autocomplete / prev-next) ----
  function locate(m) {
    const cat = catOf(m)
    activeCat = cat
    if (cat === 'aplicatii') activeApp = APP_OF[m.id]
    else if (cat === 'motoare') activeMotorFam = m.family
  }
  async function goTo(id) {
    const m = byId(id); if (!m) return
    locate(m); openModule(id)
    await tick()
    document.getElementById('acc-' + id)?.scrollIntoView({ block: 'start' })
  }
  function step(m, dir) {
    const i = shown.findIndex((x) => x.id === m.id)
    const t = shown[i + dir]; if (!t) return
    const next = new Set(isMobile ? [] : expanded)
    next.delete(m.id); next.add(t.id)
    expanded = next; pushRecent(t.id)
    tick().then(() => document.getElementById('acc-' + t.id)?.scrollIntoView({ block: 'start' }))
  }
  const keyResult = (m, r) => {
    if (!m.results || !m.results.length) return null
    const res = m.results[0]; const val = r[res.key]
    if (val == null) return null
    return { label: res.label, val: fmtNum(val, res.dec), unit: res.unit }
  }

  // ---- Autocomplete cautare: navigare cu tastatura ----
  let acIndex = $state(-1)
  function acSelect(i) {
    const m = acResults[i] ?? acResults[0]; if (!m) return
    query = ''; acIndex = -1
    goTo(m.id)
  }
  function onSearchKey(e) {
    if (!acResults.length) return
    if (e.key === 'ArrowDown') { e.preventDefault(); acIndex = (acIndex + 1) % acResults.length }
    else if (e.key === 'ArrowUp') { e.preventDefault(); acIndex = (acIndex - 1 + acResults.length) % acResults.length }
    else if (e.key === 'Enter') { e.preventDefault(); acSelect(acIndex < 0 ? 0 : acIndex) }
    else if (e.key === 'Escape') { query = ''; acIndex = -1 }
  }
</script>

<div class="page">
  <div class="page-head">
    <div class="head-row">
      <CalcIcon size={26} />
      <h1>Calculator actionari electrice</h1>
    </div>
    <p class="sub">Marimi inginerești pentru motoare si convertizoare — valori orientative, verifica intotdeauna catalogul/manualul.</p>
  </div>

  <div class="search-wrap">
    <div class="search-row">
      <span class="search-ic"><Search size={16} /></span>
      <input class="search-inp" type="search" autocomplete="off"
        placeholder="Cauta un calcul — titlu, simbol sau marime (ex. NPSH, cuplu, U_dc)..."
        bind:value={query} onkeydown={onSearchKey} />
      {#if query}<button class="search-clear" title="Sterge cautarea" onclick={() => { query = ''; acIndex = -1 }}><X size={15} /></button>{/if}
    </div>
    {#if acResults.length}
      <ul class="ac-list" role="listbox">
        {#each acResults as m, i (m.id)}
          <li>
            <button class="ac-item" class:active={i === acIndex} role="option" aria-selected={i === acIndex}
              onmouseenter={() => (acIndex = i)} onclick={() => acSelect(i)}>
              <span class="ac-title">{#each highlightParts(m.title, query) as p}{#if p.hit}<mark>{p.text}</mark>{:else}{p.text}{/if}{/each}{#if m.subtitle}<span class="ac-sub"> — <MathText text={m.subtitle} /></span>{/if}</span>
              <span class="cat-badge">{catLabel(catOf(m))}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="fam-tabs" role="tablist">
    {#each CATEGORIES as c}
      <button class="fam-tab" class:active={activeCat === c.id} role="tab" aria-selected={activeCat === c.id} onclick={() => selectCat(c.id)}>{c.label}</button>
    {/each}
  </div>
  {#if activeCat === 'motoare'}
    <div class="subfam-tabs" role="tablist">
      {#each MOTOR_FAMS as f}
        <button class="subfam-tab" class:active={activeMotorFam === f.id} role="tab" aria-selected={activeMotorFam === f.id} onclick={() => (activeMotorFam = f.id)}>{f.label}</button>
      {/each}
    </div>
  {:else if activeCat === 'aplicatii'}
    <div class="subfam-tabs" role="tablist">
      {#each APPLICATIONS as a}
        <button class="subfam-tab" class:active={activeApp === a.id} role="tab" aria-selected={activeApp === a.id} onclick={() => (activeApp = a.id)}>{a.label}</button>
      {/each}
    </div>
  {/if}

  {#if favMods.length || recentMods.length}
    <div class="quick-rows">
      {#if favMods.length}
        <div class="quick-row">
          <span class="quick-h"><Star size={13} /> Favorite</span>
          {#each favMods as m (m.id)}<button class="chip" onclick={() => goTo(m.id)}>{m.title}</button>{/each}
        </div>
      {/if}
      {#if recentMods.length}
        <div class="quick-row">
          <span class="quick-h"><Clock size={13} /> Recente</span>
          {#each recentMods as m (m.id)}<button class="chip" onclick={() => goTo(m.id)}>{m.title}</button>{/each}
        </div>
      {/if}
    </div>
  {/if}

  <div class="acc-list">
    {#each shown as m (m.id)}
      {@const r = computeModule(m, values[m.id])}
      {@const k = keyResult(m, r)}
      {@const open = isOpen(m.id)}
      <div class="acc-item" id={'acc-' + m.id} class:open>
        <div class="acc-head" role="button" tabindex="0"
          onclick={() => toggle(m.id)}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(m.id) } }}>
          <span class="acc-chev" class:open><ChevronRight size={16} /></span>
          <span class="acc-title">{m.title}{#if m.subtitle}<span class="acc-sub"><MathText text={m.subtitle} /></span>{/if}</span>
          {#if k}<span class="acc-key"><MathText text={k.label} /> = <b>{k.val}</b>{#if k.unit}&nbsp;{k.unit}{/if}</span>{/if}
          <button class="star-btn" class:on={isFav(m.id)} title="Adauga la favorite" aria-label="Favorit"
            onclick={(e) => { e.stopPropagation(); toggleFav(m.id) }}><Star size={15} /></button>
        </div>

        {#if open}
          {@const charts = computeCharts(m, values[m.id])}
          <div class="acc-body">
            <div class="acc-body-head">
              <span class="cat-badge">{catLabel(catOf(m))}</span>
              <button class="reset-btn" title="Reseteaza valorile" onclick={() => resetModule(m)}>Reset</button>
            </div>

            {#if m.fields.length}
              <div class="inputs">
                {#each m.fields as f (f.key)}
                  <div class="inp">
                    <button type="button" class="inp-label" title="Definitie / de unde se ia" onclick={() => openTerm(f, m, false)}><Formula tex={symTeX(f.key)} inline /> {f.unit ? `[${f.unit}] ` : ''}{descLabel(f.label, f.key)}</button>
                    <input class="inp-field" type="number" step={f.step ?? 'any'} min={f.min} bind:value={values[m.id][f.key]} />
                  </div>
                {/each}
              </div>
            {/if}

            {#if m.results.length}
              <div class="results">
                {#each m.results as res (res.key)}
                  <div class="res-row">
                    <div class="res-head">
                      <button type="button" class="res-label" title="Definitie / cum se calculeaza" onclick={() => openTerm(res, m, true)}><MathText text={res.label} /></button>
                      <span class="res-right">
                        <span class="res-val">{fmtNum(r[res.key], res.dec)}</span>
                        {#if res.unit}<span class="res-unit">{res.unit}</span>{/if}
                      </span>
                    </div>
                    <Formula tex={res.tex} />
                  </div>
                {/each}
              </div>
            {/if}

            {#if charts.length}
              <div class="charts">
                {#each charts as chart, ci}
                  <div class="chart-zoom" role="button" tabindex="0" title="Click pentru marire"
                    onclick={() => openZoom(m, ci)}
                    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openZoom(m, ci) } }}>
                    <Chart {chart} />
                    <span class="zoom-hint"><Maximize2 size={14} /></span>
                  </div>
                {/each}
              </div>
            {/if}

            {#if m.note}<p class="mod-note"><Info size={13} /><span class="note-body"><MathText text={m.note} /></span></p>{/if}
            {#if m.params}<p class="mod-params"><MathText text={m.params} /></p>{/if}
            {#if SOURCES[m.id]}<p class="mod-source"><BookOpen size={11} /><span class="note-body"><MathText text={SOURCES[m.id]} /></span></p>{/if}
            {#if docsFor(m).length}
              <div class="mod-docs">
                <span class="docs-h">Documentatie:</span>
                {#each docsFor(m) as d}<a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>{/each}
              </div>
            {/if}

            <div class="acc-nav">
              <button class="nav-btn" disabled={shown[0]?.id === m.id} onclick={() => step(m, -1)}>‹ Anterior</button>
              <button class="nav-btn" disabled={shown[shown.length - 1]?.id === m.id} onclick={() => step(m, 1)}>Urmator ›</button>
            </div>
          </div>
        {/if}
      </div>
    {/each}
    <p class="acc-status">{shown.length} {shown.length === 1 ? 'modul' : 'module'} • {[...expanded].filter((id) => shown.some((m) => m.id === id)).length} deschise</p>
  </div>

  <Modal bind:open={zoomOpen} title={zoomRef ? zoomRef.mod.title : ''} size="zoom">
    {#if zoomChart}
      <div class="zoom-body"><Chart chart={zoomChart} /></div>
    {/if}
  </Modal>

  <Modal bind:open={termOpen} title={term ? term.label : ''} size="md">
    {#if term}
      <div class="term">
        {#if term.unit}<div class="term-unit">Unitate: <b>{term.unit}</b></div>{/if}
        {#if term.tex}
          <div class="term-sec"><span class="term-h">Cum se calculeaza</span><Formula tex={term.tex} display /></div>
        {/if}
        {#if term.g?.def}<div class="term-sec"><span class="term-h">Definitie</span><p><MathText text={term.g.def} /></p></div>{/if}
        {#if term.g?.ia}<div class="term-sec"><span class="term-h">De unde se ia</span><p><MathText text={term.g.ia} /></p></div>{/if}
        {#if term.g?.practic}<div class="term-sec"><span class="term-h">In practica</span><p><MathText text={term.g.practic} /></p></div>{/if}
        {#if term.g?.teorie}<div class="term-sec"><span class="term-h">Principiu / teorie</span><p><MathText text={term.g.teorie} /></p></div>{/if}
        {#if term.source}<div class="term-sec"><span class="term-h">Sursa</span><p class="term-src"><MathText text={term.source} /></p></div>{/if}
        {#if term.docs?.length}
          <div class="term-sec"><span class="term-h">Documentatie</span>
            <div class="term-docs">
              {#each term.docs as d}
                <a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>
              {/each}
            </div>
          </div>
        {/if}
        {#if !term.g && !term.tex}<p class="term-empty">Marime fara definitie detaliata inca. Vezi sursa modulului si formulele asociate.</p>{/if}
      </div>
    {/if}
  </Modal>
</div>

<style>
  .page { padding: var(--space-lg); }

  .page-head {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: var(--space-lg);
  }
  .head-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    color: var(--text);
  }
  .head-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    margin-top: 2px;
    max-width: 70ch;
  }

  .fam-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-bottom: var(--space-lg);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-sm);
  }
  .fam-tab {
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--text-secondary);
    transition: all var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .fam-tab:hover { background: var(--bg-hover); color: var(--text); }
  .fam-tab.active { background: var(--accent-subtle); color: var(--accent); }

  /* sub-taburi pentru Motoare (pe tip) */
  .subfam-tabs { display: flex; flex-wrap: wrap; gap: var(--space-xs); margin: calc(-1 * var(--space-md)) 0 var(--space-lg); }
  .subfam-tab {
    padding: 4px 13px; border-radius: 999px; font-size: var(--font-tiny); font-weight: 600;
    color: var(--text-dim); border: 1px solid var(--border); background: var(--bg-surface);
    cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .subfam-tab:hover { color: var(--text); border-color: var(--text-dim); }
  .subfam-tab.active { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }

  /* caseta de cautare */
  .search-row { position: relative; display: flex; align-items: center; margin-bottom: var(--space-md); }
  .search-ic { position: absolute; left: 12px; display: flex; color: var(--text-dim); pointer-events: none; }
  .search-inp {
    width: 100%; padding: 9px 38px; border: 1px solid var(--border); border-radius: var(--radius-md);
    background: var(--bg-elevated); color: var(--text); font-size: var(--font-body);
  }
  .search-inp:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .search-clear { position: absolute; right: 8px; display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; }
  .search-clear:hover { background: var(--bg-hover); color: var(--text); }
  .cat-badge { display: inline-block; margin-top: 4px; width: fit-content; font-size: var(--font-tiny); color: var(--text-dim); background: var(--bg-hover); border-radius: 999px; padding: 1px 9px; }

  /* === Acordeon === */
  .acc-list { display: flex; flex-direction: column; gap: 8px; }
  .acc-item {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    transition: border-color var(--dur-fast) var(--ease);
    scroll-margin-top: 16px; /* la navigare cardul incepe de sus, cu putin spatiu */
  }
  .acc-item.open { border-color: var(--accent); }
  .acc-head {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; cursor: pointer; user-select: none;
    transition: background var(--dur-fast) var(--ease);
  }
  .acc-head:hover { background: var(--bg-hover); }
  .acc-chev { display: flex; flex-shrink: 0; color: var(--text-dim); transition: transform var(--dur-fast) var(--ease); }
  .acc-chev.open { transform: rotate(90deg); color: var(--accent); }
  .acc-title {
    flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 8px;
    font-size: var(--font-body); font-weight: 700; color: var(--text);
  }
  .acc-sub { font-size: var(--font-tiny); font-weight: 400; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .acc-key {
    flex-shrink: 0; max-width: 42%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    font-size: var(--font-small); color: var(--text-secondary);
  }
  .acc-key b { color: var(--accent); font-weight: 700; }
  .star-btn { display: flex; flex-shrink: 0; padding: 4px; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; }
  .star-btn:hover { background: var(--bg-hover); color: var(--text); }
  .star-btn.on { color: var(--warning); }
  .star-btn.on :global(svg) { fill: var(--warning); }
  .acc-body {
    padding: var(--space-md); border-top: 1px solid var(--border);
    display: flex; flex-direction: column; gap: var(--space-md); min-width: 0;
  }
  .acc-body-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); }
  .acc-nav { display: flex; justify-content: space-between; gap: var(--space-sm); border-top: 1px dashed var(--border); padding-top: var(--space-sm); }
  .nav-btn {
    font-size: var(--font-tiny); font-weight: 600; color: var(--text-secondary);
    padding: 5px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-surface); cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .nav-btn:hover:not(:disabled) { background: var(--bg-hover); color: var(--text); border-color: var(--text-dim); }
  .nav-btn:disabled { opacity: 0.4; cursor: default; }
  .acc-status { text-align: center; font-size: var(--font-tiny); color: var(--text-dim); padding-top: var(--space-sm); }

  /* === Autocomplete cautare === */
  .search-wrap { position: relative; margin-bottom: var(--space-md); }
  .search-wrap .search-row { margin-bottom: 0; }
  .ac-list {
    position: absolute; z-index: 30; top: calc(100% + 4px); left: 0; right: 0;
    background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25); padding: 4px;
  }
  .ac-item {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%;
    padding: 8px 10px; border-radius: var(--radius-sm); cursor: pointer; text-align: left;
  }
  .ac-item.active { background: var(--accent-subtle); }
  .ac-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-small); color: var(--text); }
  .ac-sub { color: var(--text-dim); }
  .ac-item .cat-badge { margin-top: 0; flex-shrink: 0; }
  .ac-title :global(mark) { background: var(--accent-subtle); color: var(--accent); border-radius: 3px; padding: 0 2px; }

  /* === Favorite / Recente === */
  .quick-rows { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-md); }
  .quick-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .quick-h { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-tiny); font-weight: 700; color: var(--text-dim); margin-right: 2px; }
  .chip {
    font-size: var(--font-tiny); font-weight: 600; color: var(--text-secondary);
    padding: 3px 11px; border-radius: 999px; border: 1px solid var(--border); background: var(--bg-surface);
    cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .chip:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .reset-btn {
    font-size: var(--font-tiny);
    color: var(--text-dim);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    transition: all var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .reset-btn:hover { background: var(--bg-hover); color: var(--text); }

  .inputs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: var(--space-sm);
  }
  .inp { display: flex; flex-direction: column; gap: 4px; }
  .inp-label {
    font-size: var(--font-tiny);
    font-weight: 500;
    color: var(--text-secondary);
    line-height: 1.2;
    min-height: 2.2em;
    overflow-wrap: anywhere;
    text-align: left;
    background: none;
    border: none;
    padding: 0;
    width: 100%;
    cursor: help;
    transition: color var(--dur-fast) var(--ease);
  }
  .inp-label:hover { color: var(--text); text-decoration: underline dotted; }
  /* titlul = un singur link uniform: simbol, [u.m.], text — acelasi font si culoare */
  .inp-field {
    margin-top: auto;
    padding: 8px 10px;
    min-height: 40px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: var(--font-body);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .inp-field:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }

  .results {
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--border);
  }
  .res-row {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: var(--space-sm) 0;
    border-bottom: 1px solid var(--border);
  }
  .res-row:last-child { border-bottom: none; }
  .res-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-md);
  }
  .res-label {
    font-size: var(--font-small);
    color: var(--text);
    background: none;
    border: none;
    padding: 0;
    text-align: left;
    cursor: help;
    transition: color var(--dur-fast) var(--ease);
  }
  .res-label:hover { color: var(--accent); text-decoration: underline dotted; }
  .res-right {
    display: flex;
    align-items: baseline;
    gap: 4px;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .res-val {
    font-family: var(--font-mono);
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--accent);
  }
  .res-unit { font-size: var(--font-tiny); color: var(--text-dim); }

  .mod-note {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
  }
  /* iconul ramane fix sus; textul + formulele KaTeX curg ca un paragraf normal in note-body */
  .mod-note > :global(svg),
  .mod-source > :global(svg) {
    flex-shrink: 0;
    margin-top: 2px;
  }
  .note-body {
    flex: 1;
    min-width: 0;
    line-height: 1.45;
  }
  .mod-params {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    color: var(--text-dim);
    border-top: 1px dashed var(--border);
    padding-top: var(--space-sm);
  }
  .mod-source {
    display: flex;
    align-items: flex-start;
    gap: 5px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
    font-style: italic;
  }
  .mod-docs {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
  }
  .docs-h { font-size: var(--font-tiny); color: var(--text-dim); }
  .doc-link {
    display: inline-flex;
    align-items: center;
    font-size: var(--font-tiny);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    border: 1px solid var(--border);
    color: var(--accent);
    text-decoration: none;
    line-height: 1.4;
  }
  .doc-link:hover { background: var(--bg-surface); border-color: var(--accent); }
  .term-docs { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }

  .charts { display: flex; flex-wrap: wrap; gap: var(--space-md); }
  .chart-zoom {
    position: relative;
    cursor: zoom-in;
    border-radius: var(--radius-sm);
    transition: background var(--dur-fast) var(--ease);
    flex: 1 1 360px;     /* 2 grafice stau alaturat; unul singur nu se intinde peste */
    max-width: 560px;
  }
  .chart-zoom:hover { background: var(--bg-hover); }
  .chart-zoom:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-subtle);
  }
  .zoom-hint {
    position: absolute;
    top: 4px;
    right: 4px;
    color: var(--text-dim);
    opacity: 0;
    transition: opacity var(--dur-fast) var(--ease);
    pointer-events: none;
  }
  .chart-zoom:hover .zoom-hint { opacity: 0.8; }
  .zoom-body { padding: var(--space-xs); }

  .term { display: flex; flex-direction: column; gap: var(--space-md); }
  .term-unit { font-size: var(--font-small); color: var(--text-secondary); }
  .term-unit b { font-family: var(--font-mono); color: var(--text); }
  .term-sec { display: flex; flex-direction: column; gap: 4px; }
  .term-h {
    font-size: var(--font-tiny);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--accent);
  }
  .term-sec p { font-size: var(--font-body); color: var(--text); line-height: 1.5; }
  .term-src { font-family: var(--font-mono); font-size: var(--font-tiny) !important; color: var(--text-dim) !important; }
  .term-empty { font-size: var(--font-small); color: var(--text-dim); }

  @media (max-width: 768px) {
    .acc-sub { display: none; }
    .acc-key { max-width: 50%; font-size: var(--font-tiny); }
    .acc-head { padding: 10px 12px; gap: 8px; }
  }
</style>
