<script>
  import { Search, Sun, Moon } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { ui, toggleTheme } from '../../stores/ui.svelte.js'
  import { timer, stopActiveTimer } from '../../stores/timer.svelte.js'
  import { formatElapsed } from '../../lib/formatters.js'
  import { navigate } from '../../lib/router.svelte.js'
  import { motionDuration, DUR_FAST } from '../../lib/motion.svelte.js'

  function goToActive() {
    if (timer.active?.project_id) navigate(`/projects/${timer.active.project_id}`)
  }
  async function stopActive(e) {
    e.stopPropagation()
    await stopActiveTimer()
  }
</script>

<header class="header">
  <button class="header-search" onclick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}>
    <Search size={16} />
    <span class="search-hint">Cauta...</span>
    <kbd>Ctrl+K</kbd>
  </button>

  <div class="header-actions">
    {#if timer.active}
      <div class="timer-chip" role="button" tabindex="0" title={timer.active.label || 'Cronometru activ'}
        transition:fly={{ x: 12, duration: motionDuration(DUR_FAST) }}
        onclick={goToActive} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToActive() } }}>
        <span class="tc-dot"></span>
        <span class="tc-time">{formatElapsed(timer.elapsed)}</span>
        <button class="tc-stop" title="Opreste cronometrul" onclick={stopActive}><SolidIcon name="stop" size={12} /></button>
      </div>
    {/if}
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
    margin: 0 auto;
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

  .timer-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 6px 4px 10px;
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    border: 1px solid var(--accent-ring);
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease);
  }
  .timer-chip:hover { border-color: var(--accent); }
  .tc-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    animation: tcpulse 1.5s ease-in-out infinite;
    flex-shrink: 0;
  }
  @keyframes tcpulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .tc-time {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    font-weight: var(--fw-semibold);
    color: var(--accent);
    letter-spacing: var(--tracking-wide);
  }
  .tc-stop {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-xs);
    color: var(--danger);
    cursor: pointer;
    transition: all var(--dur-fast) var(--ease);
    flex-shrink: 0;
  }
  .tc-stop:hover { background: var(--danger); color: white; }

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
    .header-search {
      min-width: 0;
      flex: 1;
    }
    kbd { display: none; }
  }
</style>
