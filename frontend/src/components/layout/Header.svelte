<script>
  import { Search, Sun, Moon } from '@lucide/svelte'
  import { ui, toggleTheme } from '../../stores/ui.svelte.js'
</script>

<header class="header">
  <button class="header-search" onclick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}>
    <Search size={16} />
    <span class="search-hint">Cauta...</span>
    <kbd>Ctrl+K</kbd>
  </button>

  <div class="header-actions">
    <button class="header-btn" onclick={toggleTheme} title="Schimba tema">
      {#if ui.theme === 'dark'}
        <Sun size={18} />
      {:else}
        <Moon size={18} />
      {/if}
    </button>
  </div>
</header>

<style>
  .header {
    height: var(--header-height);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-lg);
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
  }

  .header-search {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-xs) var(--space-md);
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease);
    min-width: 240px;
  }
  .header-search:hover {
    border-color: var(--text-dim);
  }

  .search-hint {
    flex: 1;
    font-size: var(--font-small);
  }

  kbd {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    padding: 2px 6px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-xs);
    color: var(--text-dim);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .header-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    transition: all var(--dur-fast) var(--ease);
  }
  .header-btn:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  @media (max-width: 768px) {
    .header {
      padding: 0 var(--space-md);
    }
    .header-search {
      min-width: 0;
      flex: 1;
    }
    kbd { display: none; }
  }
</style>
