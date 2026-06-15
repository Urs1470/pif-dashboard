<script>
  import { StickyNote, Settings, Menu } from '@lucide/svelte'
  import { link } from '../lib/router.svelte.js'

  const items = [
    { path: '/notes', label: 'Notite', icon: StickyNote },
    { path: '/admin', label: 'Admin', icon: Settings },
  ]
</script>

<div class="page">
  <div class="page-header">
    <Menu size={24} />
    <h1>Mai mult</h1>
  </div>

  <div class="more-grid">
    {#each items as item}
      <a href={item.path} use:link class="more-card">
        <item.icon size={24} />
        <span>{item.label}</span>
      </a>
    {/each}
  </div>
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-lg);
    color: var(--text);
  }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }

  .more-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: var(--space-md);
  }

  .more-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-xl) var(--space-md);
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    transition: all var(--dur-fast) var(--ease);
  }
  .more-card:hover {
    background: var(--bg-hover);
    color: var(--text);
    border-color: var(--accent);
  }
  .more-card span {
    font-size: var(--font-small);
    font-weight: 500;
  }
</style>
