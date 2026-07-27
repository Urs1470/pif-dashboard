<script>
  import { Sun, Moon } from '@lucide/svelte'
  import { ui, toggleTheme } from '../../stores/ui.svelte.js'
</script>

<header class="header">
  <a href="/" class="brand" title="PIF Dashboard">
    <span class="brand-dot"></span>
    <span class="brand-name">PIF<span class="brand-sep">·</span>Dashboard</span>
  </a>

  {#if ui.pageHeader.title}
    <div class="header-context">
      <h1 class="hc-title">{ui.pageHeader.title}</h1>
      {#if ui.pageHeader.subtitle}<span class="hc-sep" aria-hidden="true">·</span><span class="hc-sub">{ui.pageHeader.subtitle}</span>{/if}
    </div>
  {/if}

  <span class="h-spacer"></span>

  <div class="header-actions">
    <button class="header-btn" onclick={toggleTheme} title="Schimbă tema">
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

  /* Context de pagina (ex. salutul de pe Home) — CENTRAT in bara, separat de
     brand si actiuni prin spatiu. pointer-events:none ca sa nu blocheze clickuri. */
  .header-context {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: baseline;
    gap: 8px;
    max-width: 56%;
    pointer-events: none;
    white-space: nowrap;
  }
  .hc-title {
    font-family: var(--font-heading);
    font-weight: var(--fw-semibold);
    font-size: 1rem;
    letter-spacing: -0.02em;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hc-sep { color: var(--text-faint); align-self: center; }
  .hc-sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    text-transform: capitalize;
    flex-shrink: 0;
  }

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
    /* Pe telefon salutul centrat se suprapunea peste brand (nu incape la 390px).
       Il ascundem complet — brandul + titlul propriu al paginii sunt de ajuns. */
    .header-context { display: none; }
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
