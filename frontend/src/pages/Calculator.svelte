<script>
  import { Calculator as CalcIcon, Info, BookOpen, Maximize2, Search, X } from '@lucide/svelte'
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
  const searching = $derived(query.trim().length > 0)
  const shown = $derived.by(() => {
    const q = query.trim().toLowerCase()
    if (q) return MODULES.filter((m) => matchQ(m, q)).sort((a, b) => ord(a.id) - ord(b.id))
    if (activeCat === 'aplicatii') return MODULES.filter((m) => APP_OF[m.id] === activeApp).sort((a, b) => ord(a.id) - ord(b.id))
    if (activeCat === 'motoare') return MODULES.filter((m) => catOf(m) === 'motoare' && m.family === activeMotorFam).sort((a, b) => ord(a.id) - ord(b.id))
    return MODULES.filter((m) => catOf(m) === activeCat).sort((a, b) => ord(a.id) - ord(b.id))
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
</script>

<div class="page">
  <div class="page-head">
    <div class="head-row">
      <CalcIcon size={26} />
      <h1>Calculator actionari electrice</h1>
    </div>
    <p class="sub">Marimi inginerești pentru motoare si convertizoare — valori orientative, verifica intotdeauna catalogul/manualul.</p>
  </div>

  <div class="search-row">
    <span class="search-ic"><Search size={16} /></span>
    <input class="search-inp" type="search" placeholder="Cauta un calcul — titlu, simbol sau marime (ex. NPSH, cuplu, U_dc)..." bind:value={query} />
    {#if searching}<button class="search-clear" title="Sterge cautarea" onclick={() => (query = '')}><X size={15} /></button>{/if}
  </div>

  {#if !searching}
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
  {:else}
    <p class="search-info">{shown.length} {shown.length === 1 ? 'rezultat' : 'rezultate'} pentru „{query.trim()}"</p>
  {/if}

  <div class="mod-grid">
    {#each shown as m (m.id)}
      {@const r = computeModule(m, values[m.id])}
      <div class="mod-card">
        <div class="mod-head">
          <div class="mod-title">
            <h2>{#if searching}{#each highlightParts(m.title, query) as p}{#if p.hit}<mark>{p.text}</mark>{:else}{p.text}{/if}{/each}{:else}{m.title}{/if}</h2>
            {#if m.subtitle}<span class="mod-sub"><MathText text={m.subtitle} /></span>{/if}
            {#if searching}<span class="cat-badge">{catLabel(catOf(m))}</span>{/if}
          </div>
          <button class="reset-btn" title="Reseteaza valorile" onclick={() => resetModule(m)}>Reset</button>
        </div>

        <div class="inputs">
          {#each m.fields as f (f.key)}
            <div class="inp">
              <button type="button" class="inp-label" title="Definitie / de unde se ia" onclick={() => openTerm(f, m, false)}><Formula tex={symTeX(f.key)} inline /> {f.unit ? `[${f.unit}] ` : ''}{descLabel(f.label, f.key)}</button>
              <input
                class="inp-field"
                type="number"
                step={f.step ?? 'any'}
                min={f.min}
                bind:value={values[m.id][f.key]}
              />
            </div>
          {/each}
        </div>

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

        {#each computeCharts(m, values[m.id]) as chart, ci}
          <div
            class="chart-zoom"
            role="button"
            tabindex="0"
            title="Click pentru marire"
            onclick={() => openZoom(m, ci)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openZoom(m, ci) } }}
          >
            <Chart {chart} />
            <span class="zoom-hint"><Maximize2 size={14} /></span>
          </div>
        {/each}

        {#if m.note}
          <p class="mod-note"><Info size={13} /> <MathText text={m.note} /></p>
        {/if}
        {#if m.params}
          <p class="mod-params"><MathText text={m.params} /></p>
        {/if}
        {#if SOURCES[m.id]}
          <p class="mod-source"><BookOpen size={11} /> <MathText text={SOURCES[m.id]} /></p>
        {/if}
        {#if docsFor(m).length}
          <div class="mod-docs">
            <span class="docs-h">Documentatie:</span>
            {#each docsFor(m) as d}
              <a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
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
  .search-info { font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-md); }
  h2 :global(mark) { background: var(--accent-subtle); color: var(--accent); border-radius: 3px; padding: 0 2px; }
  .cat-badge { display: inline-block; margin-top: 4px; width: fit-content; font-size: var(--font-tiny); color: var(--text-dim); background: var(--bg-hover); border-radius: 999px; padding: 1px 9px; }

  .mod-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: var(--space-md);
  }

  .mod-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    min-width: 0;
  }

  .mod-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-sm);
  }
  .mod-title h2 { font-size: 1rem; font-weight: 700; color: var(--text); }
  .mod-sub { font-size: var(--font-tiny); color: var(--text-dim); }
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
    align-items: center;
    gap: 6px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
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
    align-items: center;
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

  .chart-zoom {
    position: relative;
    cursor: zoom-in;
    border-radius: var(--radius-sm);
    transition: background var(--dur-fast) var(--ease);
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
    .mod-grid { grid-template-columns: 1fr; }
  }
</style>
