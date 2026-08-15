<script>
  import { X, Info, CircleCheck, CircleAlert, ArrowDownToLine, RefreshCw } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { ui, closeToast, runToastAction } from '../../stores/ui.svelte.js'
  import { motionDuration, EASE, ARC, DUR_ARC } from '../../lib/motion.svelte.js'

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

  // ICONITELE TOASTULUI FIX. Patru stari, aceeasi forma: disponibil (sageata in
  // jos) · se descarca (chip cu procent) · eroare (cerc de alerta, in restant) ·
  // interfata (reincarcare). Numele sunt cerute explicit de apelant, nu deduse
  // din `type`: aici starea nu e „a mers / n-a mers", e „ce urmeaza sa faci".
  const ICO_FIX = { descarca: ArrowDownToLine, reload: RefreshCw, eroare: CircleAlert, info: Info }
</script>

{#if ui.toasts.length > 0}
  <div class="toast-container" aria-live="polite">
    {#each ui.toasts as t (t.id)}
      {@const Ico = (t.ico ? ICO_FIX[t.ico] : ICO[t.type]) ?? Info}
      <!-- 240 la intrare / 180 la iesire (contract miscare): sosirea se vede,
           plecarea nu se lasa asteptata. -->
      <div class="toast rol-{t.rol ?? ROL[t.type] ?? 'neutru'}"
           in:fly={{ y: 16, duration: motionDuration(DUR_ARC), easing: ARC }}
           out:fly={{ y: 16, duration: motionDuration(180), easing: EASE }}>
        <Ico size={17} strokeWidth={1.5} class="toast-ico" />
        <span class="toast-text">{t.message}</span>
        {#if t.progres != null}
          <!-- CHIPUL CARE POARTA PROCENT. Acelasi obiect ca butonul de langa el —
               aceeasi inaltime, aceeasi raza, aceeasi tenta — doar ca nu se apasa
               si are o umplere in spatele cifrei. Procentul e in mono fiindca se
               schimba de zeci de ori pe secunda: cu latimi de cifra inegale,
               chipul ar pulsa. -->
          <span class="toast-action toast-progres" style="--p: {t.progres}%"
                role="progressbar" aria-valuenow={t.progres} aria-valuemin="0" aria-valuemax="100">
            <span class="toast-umplere" aria-hidden="true"></span>
            <span class="toast-procent">{t.progres}%</span>
          </span>
        {:else if t.actionLabel}
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
    gap: var(--space-sm);
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
  /* Cat timp se intampla ceva, iconita e in accentul ADANC: e singurul semn ca
     lucrarea merge, cand chipul de langa arata doar o cifra. */
  .rol-accent  { --rol: var(--accent-deep); }

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
  button.toast-action:hover { background: var(--accent); color: var(--accent-text); }
  button.toast-action:active { transform: scale(var(--press-scale)); }

  /* Umplerea sta SUB cifra, nu in locul chipului: chipul isi pastreaza forma si
     tenta, iar progresul e un strat peste ea. Altfel bara ar creste de la zero
     si primul procent ar arata ca un chip pe jumatate desenat. */
  .toast-progres { position: relative; overflow: hidden; justify-content: center; min-width: 58px; }
  .toast-umplere {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: var(--p, 0%);
    background: color-mix(in srgb, var(--accent) 26%, transparent);
    transition: width var(--dur-fast) linear;
  }
  /* `linear`, nu `--ease`: procentul creste monoton si des, iar o curba cu
     acceleratie l-ar face sa para ca se opreste si porneste. */
  .toast-procent { position: relative; font-family: var(--font-mono); }

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

  @media (prefers-reduced-motion: reduce) {
    .toast-umplere { transition: none; }
  }

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
    .toast-progres { min-width: 66px; }
    .toast-close { width: var(--tap-min); height: var(--tap-min); }
  }
</style>
