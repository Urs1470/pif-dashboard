<script>
  import { renderMarkdown } from '../../lib/markdown.js'

  let { content = '', onwikilink } = $props()

  const html = $derived(renderMarkdown(content))

  function onClick(e) {
    const link = e.target.closest('.md-wikilink')
    if (link) {
      const target = link.getAttribute('data-wikilink')
      if (target) onwikilink?.(target)
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="md-rendered" onclick={onClick}>
  {@html html}
</div>

<style>
  .md-rendered { font-size: 0.92rem; line-height: 1.65; color: var(--text); }
  .md-rendered :global(h1), .md-rendered :global(h2), .md-rendered :global(h3) {
    margin: 1em 0 0.4em; font-weight: 700; color: var(--text); letter-spacing: -0.015em;
  }
  .md-rendered :global(h1) { font-size: 1.3rem; }
  .md-rendered :global(h2) { font-size: 1.12rem; }
  .md-rendered :global(h3) { font-size: 1rem; color: var(--text-secondary); }
  .md-rendered :global(p) { margin: 0.55em 0; }
  .md-rendered :global(ul), .md-rendered :global(ol) { margin: 0.5em 0; padding-left: 1.5em; }
  .md-rendered :global(li) { margin: 0.2em 0; }
  .md-rendered :global(a) { color: var(--accent); text-decoration: none; }
  .md-rendered :global(a:hover) { text-decoration: underline; }
  .md-rendered :global(code) {
    background: var(--bg-elevated); padding: 1px 6px; border-radius: var(--radius-xs);
    font-size: 0.85em; font-family: var(--font-mono); color: var(--accent);
  }
  .md-rendered :global(pre) {
    background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: var(--space-md); overflow-x: auto; margin: 0.7em 0;
  }
  .md-rendered :global(pre code) { background: none; padding: 0; color: var(--text); }
  .md-rendered :global(blockquote) {
    border-left: 3px solid var(--border); margin: 0.7em 0; padding: 2px 0 2px 14px;
    color: var(--text-secondary);
  }
  .md-rendered :global(hr) { border: none; border-top: 1px solid var(--border-subtle); margin: 1.2em 0; }
  .md-rendered :global(table) { border-collapse: collapse; margin: 0.7em 0; width: 100%; }
  .md-rendered :global(th), .md-rendered :global(td) {
    border: 1px solid var(--border); padding: 6px 10px; font-size: 0.85rem; text-align: left;
  }
  .md-rendered :global(th) { background: var(--bg-elevated); font-weight: 600; }
  .md-rendered :global(img) { max-width: 100%; border-radius: var(--radius-xs); }
  .md-rendered :global(mark) { background: var(--warning-subtle); color: var(--warning); border-radius: 2px; padding: 0 2px; }
  .md-rendered :global(input[type="checkbox"]) { margin-right: 4px; accent-color: var(--accent); }

  .md-rendered :global(.md-wikilink) {
    color: var(--purple); cursor: pointer; border-bottom: 1px dashed var(--purple);
    border-radius: 2px; padding: 0 1px; transition: background var(--dur-fast) var(--ease);
  }
  .md-rendered :global(.md-wikilink:hover) { background: var(--purple-subtle); }
  .md-rendered :global(.md-tag) {
    color: var(--info); background: var(--info-subtle); border-radius: var(--radius-full);
    padding: 0 7px; font-size: 0.82em;
  }

  .md-rendered :global(.md-callout) {
    border-left: 3px solid var(--accent); background: var(--accent-subtle);
    border-radius: var(--radius-xs); padding: 10px 14px; margin: 0.7em 0;
  }
  .md-rendered :global(.md-callout-title) { font-weight: 700; font-size: 0.9rem; color: var(--accent); }
  .md-rendered :global(.md-callout-body) { margin-top: 4px; }
  .md-rendered :global(.md-callout-body > *:first-child) { margin-top: 0; }
  .md-rendered :global(.md-callout-body > *:last-child) { margin-bottom: 0; }
  .md-rendered :global(.md-callout-note) { border-left-color: var(--accent); background: var(--accent-subtle); }
  .md-rendered :global(.md-callout-note .md-callout-title) { color: var(--accent); }
  .md-rendered :global(.md-callout-tip) { border-left-color: var(--success); background: var(--success-subtle); }
  .md-rendered :global(.md-callout-tip .md-callout-title) { color: var(--success); }
  .md-rendered :global(.md-callout-success) { border-left-color: var(--success); background: var(--success-subtle); }
  .md-rendered :global(.md-callout-success .md-callout-title) { color: var(--success); }
  .md-rendered :global(.md-callout-question) { border-left-color: var(--purple); background: var(--purple-subtle); }
  .md-rendered :global(.md-callout-question .md-callout-title) { color: var(--purple); }
  .md-rendered :global(.md-callout-warning) { border-left-color: var(--warning); background: var(--warning-subtle); }
  .md-rendered :global(.md-callout-warning .md-callout-title) { color: var(--warning); }
  .md-rendered :global(.md-callout-danger) { border-left-color: var(--danger); background: var(--danger-subtle); }
  .md-rendered :global(.md-callout-danger .md-callout-title) { color: var(--danger); }
  .md-rendered :global(.md-callout-example) { border-left-color: var(--purple); background: var(--purple-subtle); }
  .md-rendered :global(.md-callout-example .md-callout-title) { color: var(--purple); }
  .md-rendered :global(.md-callout-quote) { border-left-color: var(--text-dim); background: var(--bg-elevated); }
  .md-rendered :global(.md-callout-quote .md-callout-title) { color: var(--text-secondary); }
</style>
