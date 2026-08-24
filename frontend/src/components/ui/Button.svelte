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
    /* RAZA DE RAND SI CAMP (14), NU DE SUPRAFATA (24).
       Scara de AZI, cea din AURORA: `--radius-xs` pastila (cip si control MIC) ·
       `--radius-sm` 14 (rand si camp) · `--radius-md` 24 (suprafata) ·
       `--radius-lg` 30 (dock si foaie). Butonul plin sta pe treapta campului,
       fiindca cel mai des sta LANGA un camp, intr-un formular, si cele doua trebuie
       sa aiba aceeasi cutie. Pastila e a controlului mic (`.btn-sm`, cipuri), nu a
       acestuia.
       Argumentul de dinainte se pastreaza, doar ca numerele s-au mutat: la raza de
       SUPRAFATA butonul se citeste ca un card mic, nu ca o tinta. Pana la
       2026-08-24 randurile astea recitau scara dinaintea redesignului („8 chip ·
       10 control · 14 suprafata") si spuneau „NU 14" deasupra unei linii care
       tocmai asta cerea. */
    border-radius: var(--radius-sm);
    /* CHENAR TRANSPARENT PE TOATE VARIANTELE, ca sa aiba aceeasi cutie.
       Doar `.btn-secondary` are chenar vizibil. Fara linia asta, el iesea cu 2px
       mai inalt decat perechea lui: masurat intr-un rand de actiuni, „Anulează"
       46,80 si „Exportă" 46,00. Se vede ca o pereche usor nealiniata, si nu se
       poate repara din `min-height` — continutul plus chenarul depaseau oricum
       minimul. Vezi `audit_ferestre.py`, regula „acelasi rand, aceeasi inaltime". */
    border: 1px solid transparent;
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

  .btn-sm { padding: var(--space-6) var(--space-14); font-size: var(--font-small); min-height: var(--ctrl-md); }
  .btn-md { padding: var(--space-10) var(--space-20); font-size: var(--font-body); min-height: var(--ctrl-lg); }
  .btn-lg { padding: var(--space-12) var(--space-lg); font-size: var(--font-body); min-height: 50px; }

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
    color: var(--accent-text);
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
