<script>
  // Editor WYSIWYG unic (fara moduri edit/preview) pentru observatii si notite:
  // toolbar ca la Word + formule LaTeX randate LIVE in text (KaTeX).
  //
  // Formulele traiesc in editor ca "chip"-uri necontenteditable (.mchip) cu
  // sursa in data-tex; la serializare devin la loc text `$...$` / `$$...$$`,
  // deci formatul stocat ramane HTML + delimitatori KaTeX — 100% compatibil cu
  // continutul existent, cu RichText (afisare) si cu exporturile.
  import { onMount } from 'svelte'
  import { slide } from 'svelte/transition'
  import {
    Undo2, Redo2, Bold, Italic, Underline, Strikethrough,
    List, ListOrdered, TextQuote, Minus, RemoveFormatting, Sigma, X,
    ChevronDown, Check
  } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import katex from 'katex'
  import 'katex/dist/katex.min.css'
  import { renderStoredText, sanitizeHtml } from '../../lib/storedText.js'
  import { motionDuration, DUR_FAST, EASE } from '../../lib/motion.svelte.js'

  // O SINGURA FORMA: pagina de document — bara de unelte in capul suprafetei,
  // coloana de text la stanga plafonata la latime de citit, scroll pe toata pagina.
  // Exista si o varianta `box` (caseta cu chenar, cu numarator de caractere in
  // subsol), dar dupa ce toate cele patru campuri lungi au intrat in acelasi shell
  // (`EditorLung`) nu mai avea niciun consumator — iar un al doilea desen pe care
  // nu-l poate cere nimeni nu e o optiune, e cod care se strica in tacere.
  //
  // `tools`: 'complet' (document — observatii de proiect, wiki) sau 'nota'.
  // Acelasi editor servea DOUA suprafete cu aceeasi bara de treisprezece butoane.
  // Intr-o observatie tehnica de proiect au toate sens; intr-o notita de task nu:
  // Undo/Redo dubleaza Ctrl+Z, „Titlu 1/2/3" presupune ca notita e un document cu
  // structura, iar Citat / Linie orizontala / Curata formatarea sunt moscenire de
  // la Word. Ce chiar folosesti pe teren: accentuare, o lista, si formula.
  //
  // `stare`: textul de stare din capatul din dreapta al barei („salvat", „se
  // salvează…"). Editorul NU-l calculeaza singur — el nu stie nimic despre
  // salvare, aceea e a shell-ului care il deschide (`EditorLung`). Gol => randul
  // nu se randeaza deloc, ca sa nu ramana o coloana goala in bara.
  let { value = $bindable(''), placeholder = 'Scrie aici...', tools = 'complet', stare = '', onsave = undefined } = $props()
  const compact = $derived(tools === 'nota')

  let editorEl = $state(null)

  // Starea butoanelor din toolbar (sincronizata cu selectia)
  let fmt = $state({ bold: false, italic: false, underline: false, strike: false, ul: false, ol: false, block: 'p' })

  // Dropdown-ul de stil (meniu custom, pe tema — nu popup-ul nativ de <select>)
  const BLOCK_STYLES = [
    { value: 'p', label: 'Paragraf' },
    { value: 'h1', label: 'Titlu 1' },
    { value: 'h2', label: 'Titlu 2' },
    { value: 'h3', label: 'Titlu 3' },
    { value: 'blockquote', label: 'Citat' },
  ]
  let styleOpen = $state(false)
  let styleEl = $state(null)
  let styleMenuEl = $state(null)
  let stylePos = $state('')
  const blockLabel = $derived(BLOCK_STYLES.find((s) => s.value === fmt.block)?.label || 'Paragraf')

  // MENIUL DE STIL PLEACA IN `body`, si de-aia se poate deruleaza bara.
  //
  // Era `position: absolute` in interiorul barei, deci bara nu putea deveni un
  // scroller: `overflow-x: auto` implica si `overflow-y`, iar meniul ar fi fost
  // retezat exact la deschidere. Cat timp meniul statea inauntru, singura forma
  // posibila pe telefon era o bara care se rupe pe doua randuri — adica taman
  // ce desenul nu cerea. Mutat afara, constrangerea dispare de tot.
  //
  // Aceeasi tehnica pe care `DatePicker` o foloseste deja pentru popover.
  function portal(node) {
    document.body.appendChild(node)
    return { destroy() { node.remove() } }
  }

  /** Coordonate de viewport, luate din declansator. `fixed` + `getBoundingClientRect`
   *  raman corecte si daca bara e derulata lateral. */
  function asazaMeniu() {
    if (!styleEl) return
    const r = styleEl.getBoundingClientRect()
    const jos = window.innerHeight - r.bottom
    const H = 200   // plafonul meniului; sub el se deschide in sus
    const susit = jos < H && r.top > jos
    stylePos = susit
      ? `left:${Math.round(r.left)}px; bottom:${Math.round(window.innerHeight - r.top + 6)}px`
      : `left:${Math.round(r.left)}px; top:${Math.round(r.bottom + 6)}px`
  }

  function comutaStil() {
    if (!styleOpen) asazaMeniu()
    styleOpen = !styleOpen
  }

  function pickStyle(v) {
    styleOpen = false
    setBlock(v === 'p' ? 'p' : v)
  }
  function onDocClick(e) {
    // Meniul nu mai e copil al `styleEl` (a plecat in `body`), deci inchiderea
    // trebuie sa-l intrebe si pe el — altfel primul clic pe o optiune ar inchide
    // meniul inainte ca `onclick`-ul optiunii sa apuce sa se execute.
    if (!styleOpen) return
    if (styleEl?.contains(e.target)) return
    if (styleMenuEl?.contains(e.target)) return
    styleOpen = false
  }

  // Bara de formule (insert / editare chip existent)
  let mathOpen = $state(false)
  let mathTex = $state('')
  let mathDisplay = $state(false)
  let mathInputEl = $state(null)
  let editingChip = $state(null)
  let savedRange = null

  const mathPreview = $derived.by(() => {
    if (!mathTex.trim()) return ''
    try { return katex.renderToString(mathTex, { throwOnError: false, displayMode: mathDisplay }) }
    catch (_) { return '' }
  })

  // ---- chips ----
  function chipEl(tex, display) {
    const span = document.createElement('span')
    span.className = 'mchip'
    span.setAttribute('contenteditable', 'false')
    span.dataset.tex = tex
    span.dataset.display = display ? '1' : '0'
    try { span.innerHTML = katex.renderToString(tex, { throwOnError: false, displayMode: display }) }
    catch (_) { span.textContent = tex }
    return span
  }

  const MATH_RE = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g

  // Inlocuieste perechile $...$ / $$...$$ din nodurile text cu chip-uri.
  // `withCaret`: repozitioneaza cursorul dupa chip-ul creat (tastare live).
  function convertTextMath(root, withCaret = false) {
    const sel = window.getSelection()
    const caretNode = withCaret && sel && sel.rangeCount ? sel.getRangeAt(0).startContainer : null
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (n.parentElement && n.parentElement.closest('.mchip')) return NodeFilter.FILTER_REJECT
        MATH_RE.lastIndex = 0 // regex global — reseteaza inainte de test
        return MATH_RE.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP
      }
    })
    const nodes = []
    while (walker.nextNode()) nodes.push(walker.currentNode)
    let converted = false
    for (const tn of nodes) {
      const text = tn.nodeValue
      MATH_RE.lastIndex = 0
      let m, last = 0, lastChip = null
      const frag = document.createDocumentFragment()
      while ((m = MATH_RE.exec(text))) {
        const display = m[1] != null
        const tex = (display ? m[1] : m[2]).trim()
        // anti-"22$ costa 10$": inline doar fara spatii la margini si cu continut
        if (!display && (/^\s|\s$/.test(display ? m[1] : m[2]) || !tex)) continue
        if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)))
        lastChip = chipEl(tex, display)
        frag.appendChild(lastChip)
        last = m.index + m[0].length
      }
      if (!lastChip) continue
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)))
      const hadCaret = caretNode === tn
      tn.replaceWith(frag)
      converted = true
      if (hadCaret && sel) {
        const r = document.createRange()
        r.setStartAfter(lastChip)
        r.collapse(true)
        sel.removeAllRanges()
        sel.addRange(r)
      }
    }
    return converted
  }

  function serialize() {
    if (!editorEl) return value
    const clone = editorEl.cloneNode(true)
    clone.querySelectorAll('.mchip').forEach((ch) => {
      const tex = ch.dataset.tex || ''
      const disp = ch.dataset.display === '1'
      ch.replaceWith(document.createTextNode(disp ? `$$${tex}$$` : `$${tex}$`))
    })
    return sanitizeHtml(clone.innerHTML).trim()
  }

  export function getHtml() { return serialize() }

  // ---- lifecycle ----
  onMount(() => {
    if (editorEl) {
      editorEl.innerHTML = renderStoredText(value)
      convertTextMath(editorEl)
    }
    const onSel = () => syncToolbar()
    document.addEventListener('selectionchange', onSel)
    return () => document.removeEventListener('selectionchange', onSel)
  })

  function onInput() {
    convertTextMath(editorEl, true)
    value = serialize()
  }

  function onKeydown(e) {
    const mod = e.ctrlKey || e.metaKey
    // Ctrl+S (reflexul de salvare) si Ctrl+Enter -> salveaza, daca parintele a dat onsave.
    if (mod && (e.key === 's' || e.key === 'S' || e.key === 'Enter')) {
      e.preventDefault()
      if (onsave) { value = serialize(); onsave() }
    }
  }

  // ---- toolbar ----
  function selectionInEditor() {
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount || !editorEl) return false
    return editorEl.contains(sel.getRangeAt(0).startContainer)
  }

  function syncToolbar() {
    if (!selectionInEditor()) return
    try {
      const blockRaw = (document.queryCommandValue('formatBlock') || 'p').toLowerCase().replace(/[<>]/g, '')
      fmt = {
        bold: document.queryCommandState('bold'),
        italic: document.queryCommandState('italic'),
        underline: document.queryCommandState('underline'),
        strike: document.queryCommandState('strikeThrough'),
        ul: document.queryCommandState('insertUnorderedList'),
        ol: document.queryCommandState('insertOrderedList'),
        block: ['h1', 'h2', 'h3', 'blockquote'].includes(blockRaw) ? blockRaw : 'p',
      }
    } catch (_) { /* queryCommand* poate arunca pe selectii exotice */ }
  }

  function cmd(name, arg = null) {
    editorEl?.focus()
    try { document.execCommand(name, false, arg) } catch (_) {}
    onInput()
    syncToolbar()
  }

  function setBlock(tag) { cmd('formatBlock', `<${tag.toUpperCase()}>`) }

  function clearFmt() {
    cmd('removeFormat')
    cmd('formatBlock', '<P>')
  }

  // ---- bara de formule ----
  function openMathBar(chip = null) {
    // pastreaza selectia curenta ca sa stim unde inseram
    const sel = window.getSelection()
    savedRange = sel && sel.rangeCount && selectionInEditor() ? sel.getRangeAt(0).cloneRange() : null
    editingChip = chip
    mathTex = chip ? (chip.dataset.tex || '') : ''
    mathDisplay = chip ? chip.dataset.display === '1' : false
    mathOpen = true
    queueMicrotask(() => mathInputEl?.focus())
  }

  function closeMathBar() {
    mathOpen = false
    editingChip = null
    savedRange = null
  }

  function saveMath() {
    const tex = mathTex.trim()
    if (!tex) { removeMath(); return }
    if (editingChip) {
      const fresh = chipEl(tex, mathDisplay)
      editingChip.replaceWith(fresh)
    } else {
      editorEl?.focus()
      const sel = window.getSelection()
      if (savedRange && sel) { sel.removeAllRanges(); sel.addRange(savedRange) }
      const chip = chipEl(tex, mathDisplay)
      try {
        document.execCommand('insertHTML', false, chip.outerHTML + '&nbsp;')
      } catch (_) {
        editorEl?.appendChild(chip)
      }
    }
    value = serialize()
    closeMathBar()
  }

  function removeMath() {
    if (editingChip) {
      editingChip.remove()
      value = serialize()
    }
    closeMathBar()
  }

  function onEditorClick(e) {
    const chip = e.target?.closest?.('.mchip')
    if (chip && editorEl?.contains(chip)) {
      e.preventDefault()
      openMathBar(chip)
    }
  }

  function onMathKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveMath() }
    // `stopPropagation`: editorul sta de obicei intr-un Modal (notitele), iar
    // fara ea Escape inchidea si bara de formule, si modalul de deasupra ei.
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeMathBar() }
  }

  // butoanele nu fura selectia din editor
  function keepSel(e) { e.preventDefault() }

  // Aici se masura `visualViewport` a doua oara (prima e in `Modal`), ca sa se
  // fixeze bara de unelte la `bottom: kb`. A plecat: foaia „doc" urca intreaga
  // deasupra tastaturii, iar bara sta sub text, in flux (vezi CSS-ul de telefon).
</script>

<svelte:document onclick={onDocClick} />
<svelte:window onresize={() => styleOpen && asazaMeniu()} />

<div class="rte">
  <div class="rte-toolbar" role="toolbar" aria-label="Instrumente de formatare">
    {#if !compact}
    <button type="button" class="tbtn" title="Anulează (Ctrl+Z)" onmousedown={keepSel} onclick={() => cmd('undo')}><Undo2 size={15} /></button>
    <button type="button" class="tbtn" title="Refă (Ctrl+Y)" onmousedown={keepSel} onclick={() => cmd('redo')}><Redo2 size={15} /></button>

    <span class="tsep" aria-hidden="true"></span>

    <span class="tstyle-wrap" bind:this={styleEl} onkeydown={(e) => { if (e.key === 'Escape' && styleOpen) { e.stopPropagation(); styleOpen = false } }} role="presentation">
      <button type="button" class="tstyle" class:on={styleOpen} title="Stil paragraf"
        onmousedown={keepSel} onclick={comutaStil}>
        {blockLabel} <ChevronDown size={12} />
      </button>
      <!-- INTRAREA E O ANIMATIE CSS, NU O TRANZITIE SVELTE — si asta nu e o
           preferinta, e o conditie ca meniul sa dispara.
           Masurat: cu `transition:fly` pe un nod mutat in `body`, iesirea se joaca
           pana la `opacity: 0` si nodul RAMANE acolo — Svelte il scoate relativ la
           ancora blocului, iar ancora nu mai e parintele lui. Rezultatul erau
           150x182px invizibili, cu `pointer-events: auto`, peste editor. Nu se
           acumulau (unul singur), dar inghiteau clicuri.
           Fara tranzitie de iesire, `{#if}` scoate nodul pe loc si `destroy`-ul
           actiunii `portal` il sterge din `body`. Iesirea instantanee e oricum
           corecta pentru un meniu: alegi o optiune, meniul nu mai are ce spune. -->
      {#if styleOpen}
        <div class="tstyle-menu" use:portal bind:this={styleMenuEl} style={stylePos}>
          {#each BLOCK_STYLES as s (s.value)}
            <button type="button" class="topt" class:sel={fmt.block === s.value}
              onmousedown={keepSel} onclick={() => pickStyle(s.value)}>
              <span class="topt-label t-{s.value}">{s.label}</span>
              {#if fmt.block === s.value}<Check size={13} />{/if}
            </button>
          {/each}
        </div>
      {/if}
    </span>

    <span class="tsep" aria-hidden="true"></span>
    {/if}

    <button type="button" class="tbtn" class:on={fmt.bold} title="Bold (Ctrl+B)" onmousedown={keepSel} onclick={() => cmd('bold')}><Bold size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.italic} title="Italic (Ctrl+I)" onmousedown={keepSel} onclick={() => cmd('italic')}><Italic size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.underline} title="Subliniat (Ctrl+U)" onmousedown={keepSel} onclick={() => cmd('underline')}><Underline size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.strike} title="Tăiat" onmousedown={keepSel} onclick={() => cmd('strikeThrough')}><Strikethrough size={15} /></button>

    <span class="tsep" aria-hidden="true"></span>

    <button type="button" class="tbtn" class:on={fmt.ul} title="Listă cu puncte" onmousedown={keepSel} onclick={() => cmd('insertUnorderedList')}><List size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.ol} title="Listă numerotată" onmousedown={keepSel} onclick={() => cmd('insertOrderedList')}><ListOrdered size={15} /></button>
    {#if !compact}
    <button type="button" class="tbtn" class:on={fmt.block === 'blockquote'} title="Citat" onmousedown={keepSel} onclick={() => setBlock(fmt.block === 'blockquote' ? 'p' : 'blockquote')}><TextQuote size={15} /></button>
    <button type="button" class="tbtn" title="Linie orizontală" onmousedown={keepSel} onclick={() => cmd('insertHorizontalRule')}><Minus size={15} /></button>
    {/if}

    <span class="tsep" aria-hidden="true"></span>

    <button type="button" class="tbtn tmath" class:on={mathOpen} title="Formulă LaTeX — sau scrie direct $x$ în text" onmousedown={keepSel} onclick={() => (mathOpen ? closeMathBar() : openMathBar())}><Sigma size={15} /></button>
    {#if !compact}
    <button type="button" class="tbtn" title="Curăță formatarea" onmousedown={keepSel} onclick={clearFmt}><RemoveFormatting size={15} /></button>
    {/if}

    {#if stare}
      <span class="tspatiu" aria-hidden="true"></span>
      <span class="tstare" aria-live="polite">{stare}</span>
    {/if}
  </div>

  {#if mathOpen}
    <div class="math-bar" transition:slide={{ duration: motionDuration(DUR_FAST), easing: EASE }}>
      <div class="math-row">
        <input
          class="math-inp"
          type="text"
          placeholder={'LaTeX — ex: P = \\sqrt{3} \\cdot U \\cdot I \\cdot \\cos\\varphi'}
          bind:value={mathTex}
          bind:this={mathInputEl}
          onkeydown={onMathKeydown}
        />
        <label class="math-disp" title="Formulă pe rând separat, centrată">
          <input type="checkbox" bind:checked={mathDisplay} /> Bloc
        </label>
        <button type="button" class="math-btn primary" onclick={saveMath}>{editingChip ? 'Salvează' : 'Inserează'}</button>
        {#if editingChip}
          <button type="button" class="math-btn danger" onclick={removeMath}>Șterge</button>
        {/if}
        <button type="button" class="math-btn" title="Închide" onclick={closeMathBar}><X size={14} /></button>
      </div>
      {#if mathPreview}
        <div class="math-prev">{@html mathPreview}</div>
      {/if}
    </div>
  {/if}

  <div
    class="rte-editor"
    contenteditable="true"
    role="textbox"
    tabindex="0"
    aria-multiline="true"
    aria-label="Conținut"
    spellcheck="true"
    data-placeholder={placeholder}
    bind:this={editorEl}
    oninput={onInput}
    onkeydown={onKeydown}
    onclick={onEditorClick}
  ></div>
</div>

<style>
  /* Pagina de document: fara chenar si fara fond propriu — cutia e modalul.
     Un singur scroller, ca pilula de unelte sa ramana sticky sus. */
  .rte {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  /* ===== bara editorului — UN RAND, NU O PILULA =====
     Era o pastila plutitoare, centrata, care statea PESTE textul pe care il
     editezi: primul rand al notitei trebuia impins cu 64px de padding ca sa nu
     intre pe sub ea, iar starea „salvat" n-avea unde sa stea „la dreapta" intr-un
     obiect de latime `max-content`.
     Acum e capul suprafetei: un rand pe toata latimea, cu o linie sub el.
     Butoanele sunt discrete (32px, fara chenar), grupate cu separatoare de 1px,
     iar cel activ ia SUPRAFATA A DOUA — nu tenta de accent: intr-o bara de
     formatare „bold e pornit" e o stare a textului, nu a aplicatiei, iar accentul
     ramane rezervat. */
  .rte-toolbar {
    position: sticky;
    top: 0;
    z-index: 3;
    align-self: stretch;
    display: flex;
    align-items: center;
    flex-wrap: wrap;   /* vezi nota de la blocul de telefon */
    gap: var(--space-2xs);
    row-gap: var(--space-xs);
    padding: var(--space-sm) var(--space-10);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
  }

  .tbtn {
    width: 32px;
    height: var(--ctrl-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-xs);
    color: var(--text-dim);
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
  }
  .tbtn:hover { background: var(--bg-hover); color: var(--text); }
  .tbtn.on { background: var(--bg-elevated); color: var(--text-secondary); }
  .tbtn.tmath { font-weight: var(--fw-semibold); }

  .tsep { width: 1px; height: 20px; background: var(--border); margin: 0 var(--space-6); flex-shrink: 0; }

  /* Impinge starea la dreapta. Cand `stare` e gol nu se randeaza nimic, deci
     spatiul nu ramane rezervat degeaba. */
  .tspatiu { flex: 1; min-width: 0; }
  .tstare {
    flex: none;
    padding-right: var(--space-xs);
    font-family: var(--font-mono);
    font-size: var(--font-label);
    color: var(--text-dim);
  }

  .tstyle-wrap { position: relative; flex-shrink: 0; }
  .tstyle {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: var(--ctrl-sm);
    padding: 0 var(--space-10);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-xs);
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
  }
  .tstyle:hover { color: var(--text); }
  .tstyle.on { background: var(--bg-elevated); color: var(--text); }
  /* Suprafata flotanta: umbra, nu chenar. `fixed`, fiindca traieste in `body` —
     coordonatele vin din declansator (`asazaMeniu`). Stilurile raman SCOPATE:
     `portal` muta nodul, nu-i sterge clasa de scope, iar elementul e in sablon,
     deci Svelte nu taie nici regula. */
  .tstyle-menu {
    position: fixed;
    z-index: var(--z-tooltip);
    min-width: 150px;
    max-height: 200px;
    overflow-y: auto;
    background: var(--bg-overlay);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    padding: var(--space-xs);
    animation: tstyle-intra var(--dur-fast) var(--ease);
  }
  @keyframes tstyle-intra {
    from { opacity: 0; transform: translateY(-4px); }
  }
  .topt {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-sm);
    width: 100%;
    padding: 7px var(--space-10);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
  }
  .topt:hover { background: var(--bg-hover); color: var(--text); }
  .topt.sel { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .topt-label { font-size: var(--font-small); }
  /* Eticheta unei optiuni de meniu arata CE PRODUCE optiunea — deci greutate si
     marime, nu culoare: „Titlu 2" nu e o stare, iar accentul e rezervat starii. */
  .topt-label.t-h1 { font-weight: var(--fw-semibold); font-size: var(--font-body); }
  .topt-label.t-h2 { font-weight: var(--fw-semibold); }
  .topt-label.t-h3 { font-weight: var(--fw-semibold); }
  .topt-label.t-blockquote { font-style: italic; }

  /* ===== bara de formule — sub bara de unelte, tot plutitoare ===== */
  .math-bar {
    position: sticky;
    top: 50px;
    z-index: 3;
    width: min(680px, calc(100% - 24px));
    margin: var(--space-sm) auto 0;
    padding: var(--space-xs) var(--space-sm);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
  }
  .math-row { display: flex; align-items: center; gap: var(--space-xs); flex-wrap: wrap; }
  /* Aceeasi reteta de camp ca `.field-input` (Input.svelte), la scara barei. */
  .math-inp {
    flex: 1;
    min-width: 160px;
    min-height: var(--ctrl-md);
    padding: var(--space-6) var(--space-10);
    font-family: var(--font-mono);
    font-size: var(--font-small);
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text);
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .math-inp:focus { outline: none; box-shadow: inset 0 0 0 1.5px var(--accent); }
  .math-disp {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: var(--font-small);
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .math-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    min-height: var(--ctrl-sm);
    padding: 0 var(--space-12);
    font-size: var(--font-small);
    font-weight: var(--fw-semibold);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--bg-input);
    color: var(--text-secondary);
    cursor: pointer;
    flex-shrink: 0;
    transition: var(--transition-colors);
  }
  .math-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .math-btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
  .math-btn.primary:hover { background: var(--accent-hover); }
  .math-btn.danger:hover { color: var(--danger); border-color: var(--danger); background: var(--danger-subtle); }
  .math-prev {
    padding: var(--space-xs) var(--space-10);
    color: var(--text);
    overflow-x: auto;
  }

  /* ===== editor =====
     COLOANA DE SCRIS INCEPE DIN STANGA, SI ARE LATIME PROPRIE.
     Ion: „editarea imi incepe la mijlocul modalului, vreau sa inceapa maxim din
     stanga."
     Erau doua lucruri, nu unul. `margin: 0 auto` centra coloana — dar `.rte` e un
     container flex pe COLOANA, iar o margine `auto` pe axa transversala ANULEAZA
     intinderea (`align-items: stretch`). Deci editorul nu era o coloana de 82ch
     centrata: se stransese pe latimea CONTINUTULUI. Masurat pe o notita goala,
     intr-un modal de 1018px: 408px de editor si 316px de margine moarta de fiecare
     parte. Textul incepea la jumatate, iar dreapta modalului nici macar nu era
     zona editabila — dadeai click acolo si nu se intampla nimic.
     `width: 100%` reda intinderea (auto-marginile nu mai exista ca s-o anuleze),
     `max-width` pastreaza masura de citit, iar fara `margin` coloana se aseaza la
     inceputul randului.
     Padding-ul de sus nu mai rezerva inaltimea unei pilule plutitoare: bara e
     acum in FLUX, deasupra, deci textul incepe de unde incepe suprafata. */
  .rte-editor {
    flex: 1;
    min-height: calc(100% - 50px);
    width: 100%;
    max-width: 82ch;
    padding: var(--space-20) var(--space-xl) 90px;
    font-size: var(--font-body);
    color: var(--text);
    line-height: var(--lh-normal);
    outline: none;
    cursor: text;
  }
  .rte-editor:empty::before {
    content: attr(data-placeholder);
    color: var(--text-dim);
    font-style: italic;
    pointer-events: none;
  }

  /* ACEEASI SCARA CA NOTA CITITA (`MarkdownView`): titlu de sectiune 21/600,
     corp 15/1,55, cod si valori mono 13, tabel cu doar linii de rand. Ce scrii si
     ce citesti sunt acelasi text — daca se despart, editorul minte despre cum va
     arata. `h2` era pe `--accent`: culoarea e stare in sistemul asta, iar un
     subtitlu de notita nu e o stare. */
  .rte-editor :global(h1) { color: var(--text); font-size: var(--font-h2); margin: var(--space-md) 0 var(--space-sm); font-weight: var(--fw-semibold); letter-spacing: var(--tracking-tight); }
  .rte-editor :global(h2) { color: var(--text); font-size: var(--font-h3); margin: var(--space-14) 0 var(--space-sm); font-weight: var(--fw-semibold); }
  .rte-editor :global(h3) { color: var(--text-secondary); font-size: var(--font-h3); margin: var(--space-12) 0 var(--space-6); font-weight: var(--fw-semibold); }
  .rte-editor :global(p) { margin: var(--space-6) 0; }
  /* MARCATORII TREBUIE REAFIRMATI: `reset.css` sterge `list-style` de pe TOATE
     ul/ol din aplicatie. `insertUnorderedList` chiar insera lista — dar fara
     bulina/cifra si fara text pe rand, o `<li>` goala e invizibila, deci butonul
     parea ca nu face nimic („nu se pune, ramane doar gol"). */
  .rte-editor :global(ul), .rte-editor :global(ol) { padding-left: 26px; margin: var(--space-6) 0; }
  .rte-editor :global(ul) { list-style: disc outside; }
  .rte-editor :global(ul ul) { list-style: circle outside; }
  .rte-editor :global(ol) { list-style: decimal outside; }
  .rte-editor :global(li) { margin: 3px 0; }
  .rte-editor :global(a) { color: var(--accent); text-decoration: underline; }
  .rte-editor :global(hr) { border: none; border-top: 1px solid var(--border); margin: var(--space-12) 0; }
  /* Muchia ramane, dar fara fond: un citat nu e o alta suprafata, e o alta voce. */
  .rte-editor :global(blockquote) { border-left: 3px solid var(--border); padding: var(--space-2xs) 0 var(--space-2xs) var(--space-14); color: var(--text-secondary); margin: var(--space-sm) 0; }
  .rte-editor :global(table) { border-collapse: collapse; margin: var(--space-10) 0; max-width: 100%; }
  .rte-editor :global(th), .rte-editor :global(td) { border-bottom: 1px solid var(--border); padding: var(--space-sm) var(--space-2xs); text-align: left; vertical-align: top; }
  .rte-editor :global(th) {
    font-size: var(--font-label); font-weight: var(--fw-semibold);
    text-transform: uppercase; letter-spacing: var(--tracking-label);
    color: var(--text-dim); padding-bottom: 7px;
  }
  .rte-editor :global(code) {
    background: var(--bg-elevated); padding: 1px var(--space-6); border-radius: var(--radius-xs);
    font-family: var(--font-mono); font-size: var(--font-small); color: var(--accent-deep);
  }

  /* chip formula — click pentru editare */
  .rte-editor :global(.mchip) {
    display: inline-block;
    padding: 0 var(--space-xs);
    border-radius: var(--radius-xs);
    cursor: pointer;
    transition: background-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .rte-editor :global(.mchip:hover) { background: var(--accent-subtle); box-shadow: 0 0 0 1px var(--accent-ring); }
  .rte-editor :global(.mchip[data-display="1"]) {
    display: block;
    text-align: center;
    margin: var(--space-10) 0;
    padding: var(--space-6) var(--space-sm);
  }

  @media (max-width: 768px) {
    /* Butoanele de formatare stau lipite unul de altul intr-o bara — cea mai
       densa insiruire de tinte din aplicatie. La 44px nu mai apesi „italic" cand
       vrei „bold". */
    .tbtn { width: var(--tap-min); height: var(--tap-min); }
    .tstyle { height: var(--tap-min); }

    /* UN SINGUR RAND, CARE DERULEAZA, SUB TEXT — NU PESTE EL.
       Era `position: fixed; bottom: var(--kb)`: bara plutea peste ultimul rand
       al textului, peste „Salvează" din subsolul foii (masurat: butonul statea
       ASCUNS sub bara, la foaia deschisa fara tastatura) si isi masura singura
       tastatura, a doua oara dupa `Modal`. Acum foaia „doc" urca deasupra
       tastaturii cu totul (`Modal` ii ridica podeaua cu `--kb`), deci bara n-are
       de ce sa se mai fixeze pe nimic: sta ULTIMA in coloana, textul deruleaza
       deasupra ei, iar subsolul cu „Salvează" vine sub ea, in fluxul normal.
       `nowrap` + `overflow-x` se pot, fiindca meniul de stil s-a mutat in
       `body` si nu mai e taiat de scroller. */
    .rte { overflow: hidden; }
    .rte-toolbar {
      position: static;
      order: 2;
      flex: none;
      gap: 3px;
      flex-wrap: nowrap;
      overflow-x: auto;
      overscroll-behavior-x: contain;
      scrollbar-width: none;
      border-bottom: none;
      border-top: 1px solid var(--border);
      padding: var(--space-6) var(--space-10);
    }
    .rte-toolbar::-webkit-scrollbar { display: none; }
    /* Randul e o pista: separatoarele si eticheta de stare n-au voie sa se
       stranga sub degetul care deruleaza. */
    .tsep, .tstare { flex: none; }
    /* Spatiul care impingea starea la dreapta n-are ce cauta intr-un rand care
       deruleaza: ar fi intins bara la infinit. Starea vine dupa ultimul buton. */
    .tspatiu { display: none; }

    .math-btn { min-height: var(--tap-min); }
    .math-inp { min-height: var(--tap-min); }
    .math-bar { top: 8px; width: calc(100% - 12px); }
    /* Textul e scrollerul, bara sta sub el: nimic nu mai pluteste peste ultimul
       rand, deci nici nu mai e nevoie de 96-152px de padding ca sa-l ridici. */
    .rte-editor {
      order: 1;
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      padding: var(--space-md) var(--space-md) var(--space-xl);
    }
  }
</style>
