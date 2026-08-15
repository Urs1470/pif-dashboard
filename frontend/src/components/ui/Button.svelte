<script>
  import { scale } from 'svelte/transition'
  import { motionDuration, DUR_FAST, EASE } from '../../lib/motion.svelte.js'

  let { variant = 'primary', size = 'md', disabled = false, loading = false, onclick, children, ...rest } = $props()
</script>

<button
  class="btn btn-{variant} btn-{size}"
  class:is-loading={loading}
  disabled={disabled || loading}
  aria-busy={loading}
  {onclick}
  {...rest}
>
  {#if loading}
    <span class="spinner" transition:scale={{ start: 0.5, duration: motionDuration(DUR_FAST), easing: EASE }}></span>
  {/if}
  <span class="btn-label">{@render children()}</span>
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-xs);
    font-weight: var(--fw-semibold);
    /* RAZA DE CONTROL (10), NU DE SUPRAFATA (14).
       Scara are patru trepte cu roluri scrise: 8 chip · 10 control si rand ·
       14 suprafata · 20 foaie. Butonul e un control, si asa il arata toate
       desenele; la 14 avea aceeasi rotunjire ca un card, deci se citea ca o
       suprafata mica in loc de o tinta. */
    border-radius: var(--radius-sm);
    transition: background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), transform var(--dur-press) var(--ease), box-shadow var(--dur-fast) var(--ease), opacity var(--dur-fast) var(--ease);
    white-space: nowrap;
    cursor: pointer;
    position: relative;
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  /* Loading: pastreaza latimea (label ascuns dar prezent), spinner centrat — zero salt */
  .btn-label { display: inline-flex; align-items: center; gap: var(--space-xs); }
  .is-loading .btn-label { visibility: hidden; }
  .spinner {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 14px;
    height: 14px;
    margin: -7px 0 0 -7px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .btn-sm { padding: 6px 14px; font-size: var(--font-small); min-height: 38px; }
  .btn-md { padding: 10px 20px; font-size: var(--font-body); min-height: 46px; }
  .btn-lg { padding: 12px 24px; font-size: var(--font-body); min-height: 50px; }

  .btn-primary {
    background: var(--accent);
    color: var(--accent-text);
  }
  /* Fara glow colorat (interzis explicit). Hoverul merge spre `--accent-deep`:
     pe intuneric asta inseamna mai deschis, pe lumina mai inchis — in ambele,
     mai mult contrast, care e chiar raspunsul cerut. */
  .btn-primary:hover:not(:disabled) {
    background: var(--accent-deep);
  }
  .btn-primary:active:not(:disabled) {
    transform: scale(var(--press-scale));
    box-shadow: none;
    transition-duration: var(--dur-press);
  }

  .btn-secondary {
    background: var(--bg-elevated);
    color: var(--text);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover:not(:disabled) {
    background: var(--bg-hover);
    border-color: var(--text-dim);
  }
  .btn-secondary:active:not(:disabled) {
    background: var(--bg-active);
    transform: scale(var(--press-scale));
    transition-duration: var(--dur-press);
  }

  .btn-ghost {
    background: transparent;
    color: var(--text-secondary);
  }
  .btn-ghost:hover:not(:disabled) {
    background: var(--bg-hover);
    color: var(--text);
  }
  .btn-ghost:active:not(:disabled) {
    background: var(--bg-active);
    transform: scale(var(--press-scale));
    transition-duration: var(--dur-press);
  }

  .btn-danger {
    background: var(--danger);
    color: var(--on-color);
  }
  /* Ca la `.btn-primary`: hoverul merge spre varianta ADANCA, nu pe opacitate —
     care s-ar inmulti peste cerneala si ar scoate textul sub prag. */
  .btn-danger:hover:not(:disabled) {
    background: var(--danger-deep);
  }
  .btn-danger:active:not(:disabled) {
    transform: scale(var(--press-scale));
    transition-duration: var(--dur-press);
  }

  /* `sm` inseamna „compact intr-o bara de unelte", nu „mai greu de atins". Pe
     telefon 38px e sub prag, iar `btn-sm` e exact varianta folosita in barele de
     actiuni ale paginilor (Proiect Nou, Edit, PDF, MD). */
  @media (max-width: 768px) {
    .btn-sm { min-height: var(--tap-min); }
  }
</style>
