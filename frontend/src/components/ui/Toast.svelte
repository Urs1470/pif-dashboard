<script>
  import { X, Info, CircleCheck, TriangleAlert, CircleX } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { ui, closeToast, runToastAction } from '../../stores/ui.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../../lib/motion.svelte.js'

  // Toastul e SINGURUL loc din aplicatie unde dunga de 3px chiar purta
  // informatie: n-are nici iconita, nici fill, deci nimic altceva nu spunea ce
  // fel de mesaj e. O ia iconita, in capul randului.
  const ICO = { info: Info, success: CircleCheck, warning: TriangleAlert, error: CircleX }
</script>

{#if ui.toasts.length > 0}
  <div class="toast-container" aria-live="polite">
    {#each ui.toasts as t (t.id)}
      {@const Ico = ICO[t.type] ?? Info}
      <div class="toast toast-{t.type}" transition:fly={{ x: 20, duration: motionDuration(DUR_BASE) }} animate:flip={{ duration: motionDuration(DUR_FAST) }}>
        <Ico size={15} class="toast-ico" />
        <span>{t.message}</span>
        {#if t.actionLabel}
          <button class="toast-action" onclick={() => runToastAction(t.id)}>{t.actionLabel}</button>
        {/if}
        <button class="toast-close" onclick={() => closeToast(t.id)}>
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

  /* Iconita in loc de dunga: se citeste mai repede decat 3px la marginea
     ecranului si supravietuieste pe telefon, unde toastul e lat cat pagina si
     muchia ajunge in afara campului in care te uiti. */
  .toast :global(.toast-ico) { flex: none; color: var(--toast-col, var(--text-dim)); }
  .toast-info    { --toast-col: var(--info); }
  .toast-success { --toast-col: var(--success); }
  .toast-warning { --toast-col: var(--warning); }
  .toast-error   { --toast-col: var(--danger); }

  .toast-action {
    flex-shrink: 0;
    margin-left: auto;
    padding: 4px 10px;
    border-radius: var(--radius-xs);
    font-size: var(--font-small);
    font-weight: var(--fw-semibold);
    color: var(--accent);
    background: var(--bg-hover);
    white-space: nowrap;
  }
  .toast-action:hover { background: var(--accent); color: var(--bg); }

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
    /* „Anulează" dintr-un toast are cateva secunde de trait — daca o ratezi, ai
       ratat-o de tot. Deci e printre butoanele care merita cel mai mult 44px. */
    .toast-action { display: inline-flex; align-items: center; min-height: var(--tap-min); padding: 0 14px; }
    .toast-close { width: var(--tap-min); height: var(--tap-min); }
    .toast { max-width: 100%; }
  }
</style>
