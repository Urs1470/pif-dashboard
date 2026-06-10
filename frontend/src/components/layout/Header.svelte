<script>
  import { Search, Sun, Moon, Square } from '@lucide/svelte'
  import { ui, toggleTheme } from '../../stores/ui.svelte.js'
  import { timer, stopProjectTimer, stopTaskTimer, stopGlobalTaskTimer, loadActiveTimer } from '../../stores/timer.svelte.js'

  const kindLabels = { project: 'Proiect', task: 'Task', global_task: 'Task global' }

  function formatElapsed(sec) {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  async function stopActive() {
    const a = timer.active
    if (!a) return
    if (a.kind === 'project' && a.project_id) await stopProjectTimer(a.project_id)
    else if (a.kind === 'task' && a.task_id) await stopTaskTimer(a.task_id)
    else if (a.kind === 'global_task' && a.global_task_id) await stopGlobalTaskTimer(a.global_task_id)
    await loadActiveTimer()
  }
</script>

<header class="header">
  {#if timer.active}
    <div class="gtb">
      <div class="gtb-dot"></div>
      <div class="gtb-main">
        <span class="gtb-label">{timer.active.label || '—'}</span>
        <span class="gtb-kind">{kindLabels[timer.active.kind] || 'Timer'}</span>
      </div>
      <span class="gtb-elapsed">{formatElapsed(timer.elapsed)}</span>
      <button class="gtb-stop" title="Opreste timerul" onclick={stopActive}><Square size={14} /></button>
    </div>
  {/if}

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

  .gtb {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: 4px var(--space-md);
    background: var(--accent-subtle);
    border: 1px solid var(--accent);
    border-radius: var(--radius-sm);
    flex-shrink: 0;
  }
  .gtb-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.5s ease-in-out infinite;
    flex-shrink: 0;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .gtb-main {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }
  .gtb-label {
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }
  .gtb-kind {
    font-size: var(--font-tiny);
    color: var(--accent);
    font-weight: 500;
  }
  .gtb-elapsed {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--accent);
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }
  .gtb-stop {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--danger);
    cursor: pointer;
    transition: all var(--dur-fast) var(--ease);
    flex-shrink: 0;
  }
  .gtb-stop:hover {
    background: var(--danger);
    color: white;
  }

  @media (max-width: 768px) {
    .header {
      padding: 0 var(--space-md);
      flex-wrap: wrap;
      height: auto;
      min-height: var(--header-height);
      gap: var(--space-xs);
      padding-top: var(--space-xs);
      padding-bottom: var(--space-xs);
    }
    .header-search {
      min-width: 0;
      flex: 1;
    }
    kbd { display: none; }
    .gtb {
      order: -1;
      width: 100%;
    }
    .gtb-label { max-width: none; }
  }
</style>
