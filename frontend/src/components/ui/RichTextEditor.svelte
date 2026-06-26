<script>
  import { onMount } from 'svelte'
  import { Eye } from '@lucide/svelte'
  import SolidIcon from './SolidIcon.svelte'
  import RichText from './RichText.svelte'
  import { renderStoredText } from '../../lib/storedText.js'

  let { value = $bindable(''), placeholder = 'Scrie aici...' } = $props()

  let editorEl = $state(null)
  let charCount = $state(0)
  let previewMode = $state(false)

  function togglePreview() {
    // sync the latest HTML out of the contenteditable before previewing
    if (!previewMode && editorEl) value = (editorEl.innerHTML || '').trim()
    previewMode = !previewMode
  }

  onMount(() => {
    if (editorEl) {
      editorEl.innerHTML = renderStoredText(value)
      updateCount()
    }
  })

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
    <span class="rte-hint">Lipeste text, tabele si formule LaTeX — <code>$...$</code> sau <code>$$...$$</code></span>
    <button type="button" class="rte-tool" class:active={previewMode} title={previewMode ? 'Inapoi la editare' : 'Previzualizare finala'} onclick={togglePreview}>
      {#if previewMode}<SolidIcon name="pencil" size={14} /> Editeaza{:else}<Eye size={14} /> Previzualizare{/if}
    </button>
  </div>

  <div
    class="rte-editor"
    class:rte-hidden={previewMode}
    contenteditable="true"
    spellcheck="true"
    data-placeholder={placeholder}
    bind:this={editorEl}
    oninput={onInput}
    onkeydown={onKeydown}
  ></div>

  {#if previewMode}
    <div class="rte-preview">
      {#if value && value.trim()}
        <RichText value={value} />
      {:else}
        <p class="rte-preview-empty">Nimic de previzualizat.</p>
      {/if}
    </div>
  {/if}

  <div class="rte-footer">
    <span class="rte-counter">{previewMode ? 'Previzualizare' : charCount + ' caractere'}</span>
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
    gap: var(--space-sm);
    padding: var(--space-xs) var(--space-sm);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
  }

  .rte-hint { font-size: var(--font-tiny); color: var(--text-dim); }
  .rte-toolbar code { font-family: var(--font-mono); background: var(--bg); padding: 1px 5px; border-radius: var(--radius-xs); color: var(--text-secondary); }

  .rte-tool {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 30px;
    padding: 0 10px;
    font-size: var(--font-tiny);
    border-radius: var(--radius-xs);
    color: var(--text-secondary);
    cursor: pointer;
    background: transparent;
    border: 1px solid var(--border);
    transition: all var(--dur-fast) var(--ease);
    flex-shrink: 0;
  }
  .rte-tool:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-subtle);
  }
  .rte-tool.active {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-subtle);
  }

  .rte-hidden { display: none; }

  .rte-preview {
    min-height: 280px;
    max-height: 60vh;
    overflow-y: auto;
    padding: var(--space-md);
    font-size: var(--font-body);
    color: var(--text);
    line-height: 1.6;
  }
  .rte-preview-empty { color: var(--text-faint); font-style: italic; }
  .rte-preview :global(h2) { color: var(--accent); font-size: 1.25rem; margin: 14px 0 8px; font-weight: 700; }
  .rte-preview :global(h3) { color: var(--text); font-size: 1.05rem; margin: 12px 0 6px; font-weight: 600; }
  .rte-preview :global(p) { margin: 6px 0; }
  .rte-preview :global(ul), .rte-preview :global(ol) { padding-left: 26px; margin: 6px 0; }
  .rte-preview :global(li) { margin: 3px 0; }
  .rte-preview :global(a) { color: var(--accent); text-decoration: underline; }
  .rte-preview :global(hr) { border: none; border-top: 1px solid var(--border); margin: 12px 0; }
  .rte-preview :global(blockquote) { border-left: 3px solid var(--accent); padding: 4px 14px; color: var(--text-secondary); margin: 8px 0; background: var(--bg-surface); }

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
  .rte-editor :global(table) { border-collapse: collapse; margin: 10px 0; max-width: 100%; border: 1px solid var(--border); }
  .rte-editor :global(th), .rte-editor :global(td) { border: 1px solid var(--border); padding: 6px 11px; text-align: left; vertical-align: top; }
  .rte-editor :global(th) { background: var(--bg-elevated); color: var(--text-secondary); font-weight: 600; }

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
