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
  import { motionDuration, DUR_FAST } from '../../lib/motion.svelte.js'

  // variant: 'box' = caseta clasica cu chenar; 'doc' = pagina de document
  // (folosit in modalul fullscreen de observatii/notite — toolbar pill plutitor,
  // coloana de text centrata pe latime de citit, scroll pe toata pagina).
  let { value = $bindable(''), placeholder = 'Scrie aici...', variant = 'box' } = $props()

  let editorEl = $state(null)
  let charCount = $state(0)

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
  const blockLabel = $derived(BLOCK_STYLES.find((s) => s.value === fmt.block)?.label || 'Paragraf')

  function pickStyle(v) {
    styleOpen = false
    setBlock(v === 'p' ? 'p' : v)
  }
  function onDocClick(e) {
    if (styleOpen && styleEl && !styleEl.contains(e.target)) styleOpen = false
  }

  // Bara de formule (insert / editare chip existent)
  let mathOpen = $state(false)
  let mathTex = $state('')
  let mathDisplay = $state(false)
  let mathInputEl = $state(null)
  let editingChip = null
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
      updateCount()
    }
    const onSel = () => syncToolbar()
    document.addEventListener('selectionchange', onSel)
    return () => document.removeEventListener('selectionchange', onSel)
  })

  function updateCount() {
    if (editorEl) charCount = (editorEl.innerText || '').length
  }

  function onInput() {
    convertTextMath(editorEl, true)
    updateCount()
    value = serialize()
  }

  function onKeydown(e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) e.preventDefault()
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
    updateCount()
    value = serialize()
    closeMathBar()
  }

  function removeMath() {
    if (editingChip) {
      editingChip.remove()
      updateCount()
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
    else if (e.key === 'Escape') { e.preventDefault(); closeMathBar() }
  }

  // butoanele nu fura selectia din editor
  function keepSel(e) { e.preventDefault() }
</script>

<svelte:document onclick={onDocClick} />

<div class="rte" class:doc={variant === 'doc'}>
  <div class="rte-toolbar" role="toolbar" aria-label="Instrumente de formatare">
    <button type="button" class="tbtn" title="Anuleaza (Ctrl+Z)" onmousedown={keepSel} onclick={() => cmd('undo')}><Undo2 size={15} /></button>
    <button type="button" class="tbtn" title="Refa (Ctrl+Y)" onmousedown={keepSel} onclick={() => cmd('redo')}><Redo2 size={15} /></button>

    <span class="tsep" aria-hidden="true"></span>

    <span class="tstyle-wrap" bind:this={styleEl}>
      <button type="button" class="tstyle" class:on={styleOpen} title="Stil paragraf"
        onmousedown={keepSel} onclick={() => (styleOpen = !styleOpen)}>
        {blockLabel} <ChevronDown size={12} />
      </button>
      {#if styleOpen}
        <div class="tstyle-menu" transition:fly={{ y: -4, duration: motionDuration(DUR_FAST) }}>
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

    <button type="button" class="tbtn" class:on={fmt.bold} title="Bold (Ctrl+B)" onmousedown={keepSel} onclick={() => cmd('bold')}><Bold size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.italic} title="Italic (Ctrl+I)" onmousedown={keepSel} onclick={() => cmd('italic')}><Italic size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.underline} title="Subliniat (Ctrl+U)" onmousedown={keepSel} onclick={() => cmd('underline')}><Underline size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.strike} title="Taiat" onmousedown={keepSel} onclick={() => cmd('strikeThrough')}><Strikethrough size={15} /></button>

    <span class="tsep" aria-hidden="true"></span>

    <button type="button" class="tbtn" class:on={fmt.ul} title="Lista cu puncte" onmousedown={keepSel} onclick={() => cmd('insertUnorderedList')}><List size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.ol} title="Lista numerotata" onmousedown={keepSel} onclick={() => cmd('insertOrderedList')}><ListOrdered size={15} /></button>
    <button type="button" class="tbtn" class:on={fmt.block === 'blockquote'} title="Citat" onmousedown={keepSel} onclick={() => setBlock(fmt.block === 'blockquote' ? 'p' : 'blockquote')}><TextQuote size={15} /></button>
    <button type="button" class="tbtn" title="Linie orizontala" onmousedown={keepSel} onclick={() => cmd('insertHorizontalRule')}><Minus size={15} /></button>

    <span class="tsep" aria-hidden="true"></span>

    <button type="button" class="tbtn tmath" class:on={mathOpen} title="Formula LaTeX" onmousedown={keepSel} onclick={() => (mathOpen ? closeMathBar() : openMathBar())}><Sigma size={15} /></button>
    <button type="button" class="tbtn" title="Curata formatarea" onmousedown={keepSel} onclick={clearFmt}><RemoveFormatting size={15} /></button>
  </div>

  {#if mathOpen}
    <div class="math-bar" transition:slide={{ duration: motionDuration(DUR_FAST) }}>
      <div class="math-row">
        <input
          class="math-inp"
          type="text"
          placeholder={'LaTeX — ex: P = \\sqrt{3} \\cdot U \\cdot I \\cdot \\cos\\varphi'}
          bind:value={mathTex}
          bind:this={mathInputEl}
          onkeydown={onMathKeydown}
        />
        <label class="math-disp" title="Formula pe rand separat, centrata">
          <input type="checkbox" bind:checked={mathDisplay} /> Bloc
        </label>
        <button type="button" class="math-btn primary" onclick={saveMath}>{editingChip ? 'Salveaza' : 'Insereaza'}</button>
        {#if editingChip}
          <button type="button" class="math-btn danger" onclick={removeMath}>Sterge</button>
        {/if}
        <button type="button" class="math-btn" title="Inchide" onclick={closeMathBar}><X size={14} /></button>
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
    aria-multiline="true"
    aria-label="Continut"
    spellcheck="true"
    data-placeholder={placeholder}
    bind:this={editorEl}
    oninput={onInput}
    onkeydown={onKeydown}
    onclick={onEditorClick}
  ></div>

  {#if variant !== 'doc'}
    <div class="rte-footer">
      <span class="rte-counter">{charCount} caractere</span>
      <span class="rte-hint"><code>$...$</code> devine formula automat</span>
    </div>
  {/if}
</div>

<style>
  .rte {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--bg-elevated);
  }

  /* ===== toolbar (headbar ca la Word) ===== */
  .rte-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap; /* pe ecrane inguste trece pe doua randuri (nu scroll —
                        meniul de stil e pozitionat absolut si ar fi taiat) */
    gap: 2px;
    row-gap: 4px;
    padding: 6px var(--space-sm);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
  }

  .tbtn {
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    flex-shrink: 0;
    transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
  }
  .tbtn:hover { background: var(--bg-hover); color: var(--text); }
  .tbtn.on { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .tbtn.tmath { font-weight: var(--fw-bold); }

  .tsep { width: 1px; height: 18px; background: var(--border); margin: 0 4px; flex-shrink: 0; }

  .tstyle-wrap { position: relative; flex-shrink: 0; }
  .tstyle {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 30px;
    padding: 0 10px;
    font-size: var(--font-tiny);
    font-weight: var(--fw-semibold);
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease);
  }
  .tstyle:hover { border-color: var(--text-dim); }
  .tstyle.on { border-color: var(--accent); background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .tstyle-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 6;
    min-width: 150px;
    background: var(--bg-overlay);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    padding: 4px;
  }
  .topt {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-sm);
    width: 100%;
    padding: 7px 10px;
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
  .topt-label.t-h1 { font-family: var(--font-heading); font-weight: var(--fw-bold); font-size: 1.05rem; }
  .topt-label.t-h2 { font-weight: var(--fw-bold); color: var(--accent); }
  .topt-label.t-h3 { font-weight: var(--fw-semibold); }
  .topt-label.t-blockquote { font-style: italic; }

  /* ===== bara de formule ===== */
  .math-bar {
    padding: var(--space-xs) var(--space-sm);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }
  .math-row { display: flex; align-items: center; gap: var(--space-xs); flex-wrap: wrap; }
  .math-inp {
    flex: 1;
    min-width: 160px;
    min-height: 34px;
    padding: 6px 10px;
    font-family: var(--font-mono);
    font-size: var(--font-small);
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .math-inp:focus { outline: none; border-color: var(--accent); box-shadow: var(--focus-ring); }
  .math-disp {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: var(--font-tiny);
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .math-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    min-height: 30px;
    padding: 0 12px;
    font-size: var(--font-tiny);
    font-weight: var(--fw-semibold);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    background: var(--bg-input);
    color: var(--text-secondary);
    cursor: pointer;
    flex-shrink: 0;
    transition: all var(--dur-fast) var(--ease);
  }
  .math-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .math-btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
  .math-btn.primary:hover { background: var(--accent-hover); }
  .math-btn.danger:hover { color: var(--danger); border-color: var(--danger); background: var(--danger-subtle); }
  .math-prev {
    padding: 4px 10px;
    color: var(--text);
    overflow-x: auto;
  }

  /* ===== editor ===== */
  .rte-editor {
    flex: 1;
    min-height: 280px;
    max-height: 60vh;
    overflow-y: auto;
    padding: var(--space-md);
    font-size: var(--font-body);
    color: var(--text);
    line-height: 1.6;
    outline: none;
    cursor: text;
  }
  .rte-editor:focus { box-shadow: inset 0 0 0 2px var(--accent-ring); }
  .rte-editor:empty::before {
    content: attr(data-placeholder);
    color: var(--text-faint);
    font-style: italic;
    pointer-events: none;
  }

  .rte-editor :global(h1) { color: var(--text); font-family: var(--font-heading); font-size: 1.45rem; margin: 16px 0 8px; font-weight: var(--fw-bold); letter-spacing: -0.02em; }
  .rte-editor :global(h2) { color: var(--accent); font-size: 1.25rem; margin: 14px 0 8px; font-weight: var(--fw-bold); }
  .rte-editor :global(h3) { color: var(--text); font-size: 1.05rem; margin: 12px 0 6px; font-weight: var(--fw-semibold); }
  .rte-editor :global(p) { margin: 6px 0; }
  .rte-editor :global(ul), .rte-editor :global(ol) { padding-left: 26px; margin: 6px 0; }
  .rte-editor :global(li) { margin: 3px 0; }
  .rte-editor :global(a) { color: var(--accent); text-decoration: underline; }
  .rte-editor :global(hr) { border: none; border-top: 1px solid var(--border); margin: 12px 0; }
  .rte-editor :global(blockquote) { border-left: 3px solid var(--accent); padding: 4px 14px; color: var(--text-secondary); margin: 8px 0; background: var(--bg-surface); }
  .rte-editor :global(table) { border-collapse: collapse; margin: 10px 0; max-width: 100%; border: 1px solid var(--border); }
  .rte-editor :global(th), .rte-editor :global(td) { border: 1px solid var(--border); padding: 6px 11px; text-align: left; vertical-align: top; }
  .rte-editor :global(th) { background: var(--bg-elevated); color: var(--text-secondary); font-weight: var(--fw-semibold); }

  /* chip formula — click pentru editare */
  .rte-editor :global(.mchip) {
    display: inline-block;
    padding: 0 4px;
    border-radius: var(--radius-xs);
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .rte-editor :global(.mchip:hover) { background: var(--accent-subtle); box-shadow: 0 0 0 1px var(--accent-ring); }
  .rte-editor :global(.mchip[data-display="1"]) {
    display: block;
    text-align: center;
    margin: 10px 0;
    padding: 6px 8px;
  }

  .rte-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-sm);
    padding: var(--space-xs) var(--space-sm);
    border-top: 1px solid var(--border);
    background: var(--bg-surface);
  }
  .rte-counter, .rte-hint { font-size: var(--font-tiny); color: var(--text-dim); }
  .rte-hint code { font-family: var(--font-mono); background: var(--bg); padding: 1px 5px; border-radius: var(--radius-xs); color: var(--text-secondary); }

  @media (max-width: 768px) {
    .tbtn { width: 34px; height: 34px; }
    .rte-editor { min-height: 220px; max-height: 52vh; }
    .rte-hint { display: none; }
  }

  /* ===== varianta "doc" — pagina de document (V1) ===== */
  .rte.doc {
    border: none;
    border-radius: 0;
    background: transparent;
    flex: 1;
    min-height: 0;
    overflow-y: auto; /* un singur scroller: pilula ramane sticky sus */
  }
  .rte.doc .rte-toolbar {
    position: sticky;
    top: 10px;
    z-index: 3;
    align-self: center;
    width: max-content;
    max-width: calc(100% - 24px);
    margin: 10px auto 0;
    padding: 5px 8px;
    border: 1px solid var(--border-strong);
    border-bottom: 1px solid var(--border-strong);
    border-radius: var(--radius-full);
    background: color-mix(in srgb, var(--bg-overlay) 88%, transparent);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: var(--shadow-lg);
  }
  .rte.doc .tbtn { border-radius: var(--radius-full); }
  .rte.doc .tstyle { border-radius: var(--radius-full); }
  .rte.doc .math-bar {
    position: sticky;
    top: 58px;
    z-index: 3;
    width: min(680px, calc(100% - 24px));
    margin: 8px auto 0;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--bg-overlay) 92%, transparent);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: var(--shadow-md);
  }
  .rte.doc .rte-editor {
    max-height: none;
    min-height: calc(100% - 62px);
    max-width: 74ch;
    margin: 0 auto;
    padding: 22px 28px 90px;
    font-size: 0.98rem;
    line-height: 1.65;
  }
  .rte.doc .rte-editor:focus { box-shadow: none; }

  @media (max-width: 768px) {
    .rte.doc .rte-toolbar { top: 6px; max-width: calc(100% - 12px); }
    .rte.doc .math-bar { top: 56px; width: calc(100% - 12px); }
    .rte.doc .rte-editor { padding: 16px 16px 80px; min-height: calc(100% - 58px); }
  }
</style>
