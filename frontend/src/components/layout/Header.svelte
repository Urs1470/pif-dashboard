<script>
  import { Sun, Moon } from '@lucide/svelte'
  import { ui, toggleTheme } from '../../stores/ui.svelte.js'
</script>

<header class="header">
  <a href="/" class="brand" title="PIF Dashboard">
    <span class="brand-dot"></span>
    <span class="brand-name">PIF<span class="brand-sep">·</span>Dashboard</span>
  </a>

  <span class="h-spacer"></span>

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
    background: color-mix(in srgb, var(--bg) 82%, transparent);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-lg);
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-heading);
    font-weight: var(--fw-bold);
    font-size: 1.02rem;
    letter-spacing: -0.02em;
    color: var(--text);
    white-space: nowrap;
  }
  .brand-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 14px var(--accent-ring);
    flex-shrink: 0;
  }
  .brand-sep { color: var(--text-faint); }

  .h-spacer { flex: 1; }

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
      flex-wrap: wrap;
      height: auto;
      min-height: var(--header-height);
      gap: var(--space-xs);
      /* Coboara sub notch/status-bar si respecta insets laterale. */
      padding-top: calc(var(--space-xs) + var(--safe-top));
      padding-bottom: var(--space-xs);
      padding-left: calc(var(--space-md) + var(--safe-left));
      padding-right: calc(var(--space-md) + var(--safe-right));
    }

  }
</style>
