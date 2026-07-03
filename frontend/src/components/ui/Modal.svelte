<script>
  import { tick } from 'svelte'
  import { X } from '@lucide/svelte'
  import { fade, scale } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../../lib/motion.svelte.js'

  let { open = $bindable(false), title = '', size = 'md', children, footer } = $props()
  let backdropEl = $state(null)
  let previousFocus = $state(null)

  function onBackdrop(e) {
    if (e.target === e.currentTarget) open = false
  }

  function onKey(e) {
    if (e.key === 'Escape') { open = false; return }
    if (e.key === 'Tab' && backdropEl) {
      const focusable = backdropEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
  }

  $effect(() => {
    if (open) {
      previousFocus = document.activeElement
      tick().then(() => {
        const first = backdropEl?.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        if (first) first.focus()
        else backdropEl?.focus()
      })
    } else if (previousFocus) {
      previousFocus.focus()
      previousFocus = null
    }
  })
</script>

{#if open}
  <div class="backdrop" bind:this={backdropEl} onclick={onBackdrop} onkeydown={onKey} role="dialog" aria-modal="true" aria-label={title} tabindex="-1" transition:fade={{ duration: motionDuration(DUR_FAST) }}>
    <div class="modal modal-{size}" transition:scale={{ start: 0.96, duration: motionDuration(DUR_BASE) }}>
      <div class="modal-header">
        <h2 class="modal-title">{title}</h2>
        <button class="modal-close" onclick={() => open = false} aria-label="Închide"><X size={18} /></button>
      </div>
      <div class="modal-body">
        {@render children()}
      </div>
      {#if footer}
        <div class="modal-footer">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(7px);
    -webkit-backdrop-filter: blur(7px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal);
    padding: calc(var(--space-md) + var(--safe-top)) calc(var(--space-md) + var(--safe-right)) calc(var(--space-md) + var(--safe-bottom)) calc(var(--space-md) + var(--safe-left));
  }
  .modal {
    background: var(--bg-overlay);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    width: 100%;
    max-height: 85dvh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-lg);
  }
  .modal-sm { max-width: 400px; }
  .modal-md { max-width: 560px; }
  .modal-lg { max-width: 720px; }
  .modal-xl { max-width: 960px; }
  .modal-wide { max-width: 80%; }
  .modal-zoom { max-width: 70%; }

  /* "doc" — document aproape fullscreen (editor observatii/notite).
     Body-ul nu deruleaza si nu are padding: pagina interioara (RichTextEditor
     variant="doc") isi gestioneaza singura scroll-ul si coloana de text. */
  .modal-doc { max-width: 900px; height: 92dvh; max-height: 92dvh; }
  .modal-doc .modal-body { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
  .modal-doc .modal-body > :global(*) { flex: 1; min-height: 0; display: flex; flex-direction: column; }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .modal-title {
    font-family: var(--font-heading);
    letter-spacing: -0.02em;
    font-size: var(--font-h3);
    font-weight: var(--fw-bold);
    color: var(--text);
  }
  .modal-close {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    font-size: 20px;
    transition: all var(--dur-fast) var(--ease);
  }
  .modal-close:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .modal-body {
    padding: var(--space-lg);
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .modal-footer {
    padding: var(--space-md) var(--space-lg);
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }
  /* Randul de actiuni din footer — o singura reteta partajata (global, ca sa fie
     folosita din snippet-urile footer ale tuturor modalelor). :global fiindca e
     randat in slot-ul de footer al altui component. */
  :global(.modal-footer .modal-actions) {
    display: flex;
    gap: var(--space-sm);
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
  }

  @media (max-width: 768px) {
    .modal {
      max-width: 100%;
      max-height: 90dvh;
    }
    /* doc = sheet pe tot ecranul pe mobil */
    .backdrop:has(.modal-doc) { padding: 0; }
    .modal-doc { height: 100dvh; max-height: 100dvh; border-radius: 0; border: none; }
    .modal-doc .modal-header { padding-top: calc(var(--space-md) + var(--safe-top)); }
    .modal-doc .modal-footer { padding-bottom: calc(var(--space-md) + var(--safe-bottom)); }
  }
</style>
