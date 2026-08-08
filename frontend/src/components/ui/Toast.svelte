<script>
  import { X, Info, CircleCheck, CircleAlert } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { ui, closeToast, runToastAction } from '../../stores/ui.svelte.js'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'

  // TREI ROLURI, NU PATRU TIPURI.
  //
  // Erau `info` / `success` / `warning` / `error`, cu patru culori. Dar sistemul
  // are DOUA culori de stare, deci `warning` si `error` se desenau oricum la fel
  // — patru nume care produceau trei aspecte, iar al patrulea (`info`) purta
  // accentul, adica identitatea aplicatiei pusa pe un mesaj oarecare.
  //
  // Acum: facut (verde), n-a mers (rosu), si NEUTRU pentru tot ce doar te
  // informeaza. Neutru e o alegere, nu o lipsa: „Anulează" apare exact pe
  // toasturile neutre, si un buton care se intoarce dintr-o actiune n-are voie
  // sa arate ca o eroare.
  const ICO = { success: CircleCheck, error: CircleAlert, warning: CircleAlert, info: Info }
  const ROL = { success: 'facut', error: 'restant', warning: 'restant', info: 'neutru' }
</script>

{#if ui.toasts.length > 0}
  <div class="toast-container" aria-live="polite">
    {#each ui.toasts as t (t.id)}
      {@const Ico = ICO[t.type] ?? Info}
      <div class="toast rol-{ROL[t.type] ?? 'neutru'}"
           transition:fly={{ y: 16, duration: motionDuration(DUR_BASE), easing: EASE }}>
        <Ico size={17} strokeWidth={1.5} class="toast-ico" />
        <span class="toast-text">{t.message}</span>
        {#if t.actionLabel}
          <button class="toast-action" onclick={() => runToastAction(t.id)}>{t.actionLabel}</button>
        {/if}
        <button class="toast-close" onclick={() => closeToast(t.id)} aria-label="Închide">
          <X size={15} strokeWidth={1.5} />
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
    flex-direction: column;
    z-index: var(--z-toast);
  }

  /* 44px pe desktop: inaltimea unui control, nu a unui card. Toastul nu e o
     suprafata de citit, e o linie care confirma. */
  .toast {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    padding: 0 8px 0 14px;
    background: var(--bg-overlay);
    border-radius: var(--radius-sm);
    /* Se desprinde prin UMBRA, nu prin chenar — ca orice suprafata flotanta. */
    box-shadow: var(--shadow-md);
    font-size: var(--font-small);
    color: var(--text);
    min-width: 260px;
    max-width: 420px;
  }

  /* Iconita in loc de dunga: se citeste mai repede decat 3px la marginea
     ecranului si supravietuieste pe telefon, unde toastul e lat cat pagina si
     muchia ajunge in afara campului in care te uiti. */
  .toast :global(.toast-ico) { flex: none; color: var(--rol, var(--text-dim)); }
  .rol-facut   { --rol: var(--success); }
  .rol-restant { --rol: var(--danger); }
  .rol-neutru  { --rol: var(--text-dim); }

  .toast-text { flex: 1; min-width: 0; }

  /* „Anulează" are cateva secunde de trait — daca o ratezi, ai ratat-o de tot.
     Deci e chip, nu text simplu: o tinta cu margini, nu un cuvant intre altele. */
  .toast-action {
    flex: none;
    display: inline-flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    border-radius: var(--radius-xs);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    color: var(--accent-deep);
    background: var(--accent-subtle);
    white-space: nowrap;
    transition: var(--transition-pressable);
  }
  .toast-action:hover { background: var(--accent); color: var(--accent-text); }
  .toast-action:active { transform: scale(var(--press-scale)); }

  .toast-close {
    flex: none;
    width: 32px;
    height: 32px;
    display: grid;
    place-items: center;
    border-radius: var(--radius-xs);
    color: var(--text-dim);
    transition: var(--transition-colors);
  }
  .toast-close:hover { background: var(--bg-hover); color: var(--text); }

  @media (max-width: 768px) {
    /* PESTE DOCK, nu sub el: sub dock ar fi acoperit exact de bara pe care o ai
       mereu pe ecran, iar „Anulează" e butonul care nu are voie sa fie ascuns. */
    .toast-container {
      bottom: calc(var(--dock-h) + 14px + var(--safe-bottom) + var(--space-12));
      left: var(--space-md);
      right: var(--space-md);
    }
    .toast { min-height: 56px; max-width: 100%; padding: 0 8px 0 16px; font-size: var(--font-body); }
    .toast-action { height: var(--tap-min); padding: 0 16px; }
    .toast-close { width: var(--tap-min); height: var(--tap-min); }
  }
</style>
