<script>
  import { onMount } from 'svelte'
  import {
    Bold, Italic, Underline, Strikethrough,
    Heading1, Heading2, Pilcrow,
    List, ListOrdered, Outdent, Indent,
    Link, Minus, Eraser, Undo2, Redo2
  } from '@lucide/svelte'

  let { value = $bindable(''), placeholder = 'Scrie aici...' } = $props()

  let editorEl = $state(null)
  let charCount = $state(0)

  onMount(() => {
    if (editorEl) {
      editorEl.innerHTML = renderStored(value)
      updateCount()
    }
  })

  function looksLikeHtml(s) {
    return /<\/?[a-z][\s\S]*>/i.test(s)
  }

  function plainToHtml(s) {
    return s.split(/\n\n+/).map(p =>
      '<p>' + p.replace(/\n/g, '<br>').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</p>'
    ).join('')
  }

  const SAFE_TAGS = new Set([
    'P','BR','DIV','H1','H2','H3','H4','H5','H6',
    'UL','OL','LI','STRONG','B','EM','I','U','A','HR','BLOCKQUOTE','SPAN'
  ])

  function sanitizeHtml(html) {
    const tmp = document.createElement('div')
    tmp.innerHTML = html
    ;(function walk(node) {
      const children = Array.from(node.childNodes)
      for (const child of children) {
        if (child.nodeType === 1) {
          if (!SAFE_TAGS.has(child.tagName)) {
            while (child.firstChild) node.insertBefore(child.firstChild, child)
            child.remove()
          } else {
            const attrs = Array.from(child.attributes)
            for (const a of attrs) {
              if (child.tagName === 'A' && a.name === 'href') continue
              child.removeAttribute(a.name)
            }
            walk(child)
          }
        }
      }
    })(tmp)
    return tmp.innerHTML
  }

  function renderStored(raw) {
    if (!raw || !raw.trim()) return ''
    return looksLikeHtml(raw) ? sanitizeHtml(raw) : plainToHtml(raw)
  }

  function exec(cmd, val) {
    if (!editorEl) return
    editorEl.focus()
    try { document.execCommand(cmd, false, val || null) } catch (_) {}
    updateCount()
  }

  function formatBlock(tag) {
    exec('formatBlock', tag)
  }

  function insertLink() {
    const url = prompt('URL:')
    if (url) exec('createLink', url)
  }

  function insertSeparator() {
    exec('insertHTML', '<hr>')
  }

  function updateCount() {
    if (editorEl) charCount = (editorEl.innerText || '').length
  }

  function onInput() {
    updateCount()
    if (editorEl) value = (editorEl.innerHTML || '').trim()
  }

  function onKeydown(e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault()
    }
  }

  export function getHtml() {
    return editorEl ? (editorEl.innerHTML || '').trim() : value
  }
</script>

<div class="rte">
  <div class="rte-toolbar">
    <div class="rte-group">
      <button type="button" class="rte-tool" title="Bold (Ctrl+B)" onclick={() => exec('bold')}><Bold size={14} /></button>
      <button type="button" class="rte-tool" title="Italic (Ctrl+I)" onclick={() => exec('italic')}><Italic size={14} /></button>
      <button type="button" class="rte-tool" title="Subliniat (Ctrl+U)" onclick={() => exec('underline')}><Underline size={14} /></button>
      <button type="button" class="rte-tool" title="Taiat" onclick={() => exec('strikeThrough')}><Strikethrough size={14} /></button>
    </div>
    <span class="rte-divider"></span>
    <div class="rte-group">
      <button type="button" class="rte-tool" title="Titlu mare" onclick={() => formatBlock('h2')}><Heading1 size={14} /></button>
      <button type="button" class="rte-tool" title="Titlu mic" onclick={() => formatBlock('h3')}><Heading2 size={14} /></button>
      <button type="button" class="rte-tool" title="Paragraf" onclick={() => formatBlock('p')}><Pilcrow size={14} /></button>
    </div>
    <span class="rte-divider"></span>
    <div class="rte-group">
      <button type="button" class="rte-tool" title="Lista cu puncte" onclick={() => exec('insertUnorderedList')}><List size={14} /></button>
      <button type="button" class="rte-tool" title="Lista numerotata" onclick={() => exec('insertOrderedList')}><ListOrdered size={14} /></button>
      <button type="button" class="rte-tool" title="Scade indent" onclick={() => exec('outdent')}><Outdent size={14} /></button>
      <button type="button" class="rte-tool" title="Creste indent" onclick={() => exec('indent')}><Indent size={14} /></button>
    </div>
    <span class="rte-divider"></span>
    <div class="rte-group">
      <button type="button" class="rte-tool" title="Link" onclick={insertLink}><Link size={14} /></button>
      <button type="button" class="rte-tool" title="Linie separator" onclick={insertSeparator}><Minus size={14} /></button>
    </div>
    <span class="rte-divider"></span>
    <div class="rte-group">
      <button type="button" class="rte-tool" title="Curata formatare" onclick={() => exec('removeFormat')}><Eraser size={14} /></button>
      <button type="button" class="rte-tool" title="Undo (Ctrl+Z)" onclick={() => exec('undo')}><Undo2 size={14} /></button>
      <button type="button" class="rte-tool" title="Redo (Ctrl+Y)" onclick={() => exec('redo')}><Redo2 size={14} /></button>
    </div>
  </div>

  <div
    class="rte-editor"
    contenteditable="true"
    spellcheck="true"
    data-placeholder={placeholder}
    bind:this={editorEl}
    oninput={onInput}
    onkeydown={onKeydown}
  ></div>

  <div class="rte-footer">
    <span class="rte-counter">{charCount} caractere</span>
  </div>
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

  .rte-toolbar {
    display: flex;
    gap: var(--space-xs);
    padding: var(--space-xs) var(--space-sm);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
    align-items: center;
  }

  .rte-group {
    display: inline-flex;
    gap: 2px;
  }

  .rte-divider {
    width: 1px;
    height: 20px;
    background: var(--border);
    margin: 0 2px;
  }

  .rte-tool {
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-xs);
    color: var(--text-secondary);
    cursor: pointer;
    background: transparent;
    border: 1px solid transparent;
    transition: all var(--dur-fast) var(--ease);
  }
  .rte-tool:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-subtle);
  }

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
  .rte-editor:focus {
    box-shadow: inset 0 0 0 2px var(--accent-ring);
  }
  .rte-editor:empty::before {
    content: attr(data-placeholder);
    color: var(--text-faint);
    font-style: italic;
    pointer-events: none;
  }

  .rte-editor :global(h2) { color: var(--accent); font-size: 1.25rem; margin: 14px 0 8px; font-weight: 700; }
  .rte-editor :global(h3) { color: var(--text); font-size: 1.05rem; margin: 12px 0 6px; font-weight: 600; }
  .rte-editor :global(p) { margin: 6px 0; }
  .rte-editor :global(ul), .rte-editor :global(ol) { padding-left: 26px; margin: 6px 0; }
  .rte-editor :global(li) { margin: 3px 0; }
  .rte-editor :global(a) { color: var(--accent); text-decoration: underline; }
  .rte-editor :global(hr) { border: none; border-top: 1px solid var(--border); margin: 12px 0; }
  .rte-editor :global(blockquote) { border-left: 3px solid var(--accent); padding: 4px 14px; color: var(--text-secondary); margin: 8px 0; background: var(--bg-surface); }

  .rte-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: var(--space-xs) var(--space-sm);
    border-top: 1px solid var(--border);
    background: var(--bg-surface);
  }

  .rte-counter {
    font-size: var(--font-tiny);
    color: var(--text-dim);
  }
</style>
