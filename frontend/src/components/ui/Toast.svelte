<script>
  import { X } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { ui, dismissToast } from '../../stores/ui.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../../lib/motion.svelte.js'
</script>

{#if ui.toasts.length > 0}
  <div class="toast-container">
    {#each ui.toasts as t (t.id)}
      <div class="toast toast-{t.type}" transition:fly={{ x: 20, duration: motionDuration(DUR_BASE) }} animate:flip={{ duration: motionDuration(DUR_FAST) }}>
        <span>{t.message}</span>
        <button class="toast-close" onclick={() => dismissToast(t.id)}>
          <X size={14} />
        </button>
      </div>
    {/each}
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    bottom: var(--space-lg);
    right: var(--space-lg);
    display: flex;
    flex-direction: column-reverse;
    gap: var(--space-sm);
    z-index: var(--z-toast);
  }

  .toast {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    background: var(--bg-overlay);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    font-size: var(--font-small);
    color: var(--text);
    min-width: 240px;
    max-width: 400px;
  }

  .toast-info { border-left: 3px solid var(--info); }
  .toast-success { border-left: 3px solid var(--success); }
  .toast-warning { border-left: 3px solid var(--warning); }
  .toast-error { border-left: 3px solid var(--danger); }

  .toast-close {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-xs);
    color: var(--text-dim);
  }
  .toast-close:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  @media (max-width: 768px) {
    .toast-container {
      bottom: calc(var(--dock-h) + 14px + var(--safe-bottom) + var(--space-md));
      left: var(--space-md);
      right: var(--space-md);
    }
    .toast { max-width: 100%; }
  }
</style>
