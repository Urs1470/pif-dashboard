<script>
  import { Sun, Sunrise, CalendarSearch, X } from '@lucide/svelte'
  import DatePicker from './DatePicker.svelte'
  import { zilePanaLa } from '../../lib/formatters.js'

  // ACELASI SET IN ORICE FOAIE SAU PANOU CARE REPLANIFICA.
  //
  // Existau trei variante scrise separat: pe /tasks („Azi / Mâine / Alege /
  // Scoate", text simplu), pe „Astăzi" (patru iconite mute) si in pagina de
  // proiect (doar un DatePicker). Aceeasi intrebare — CE ZI? — cu trei
  // raspunsuri diferite, deci se invata de trei ori.
  //
  // ICONITELE NU SUNT DECOR: „Azi" si „Mâine" sunt amandoua doua cuvinte scurte
  // care incep la fel pe un ecran ingust, iar soarele sus vs. soarele care
  // rasare e diferenta pe care ochiul o prinde inainte sa citeasca.
  //
  // „Scoate" sta DEDESUBT, nu al patrulea in rand: primele trei ASEAZA taskul
  // pe o zi, al patrulea il scoate din calendar cu totul. Un rand de patru
  // butoane egale ar spune ca sunt patru zile.
  let {
    value = '',
    onalege,          // (iso|null) — null inseamna „fara termen"
    aratScoate = true,
  } = $props()

  function ziPeste(n) {
    const d = new Date()
    d.setHours(12, 0, 0, 0)          // amiaza: fara surprize la ora de vara
    d.setDate(d.getDate() + n)
    const p = (x) => String(x).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
  }

  // CE ZI E ACUM PUSA, ca sa se vada pe pastila (handoff „hold·1a": ziua curenta
  // e aprinsa). Nu e un mod nou, e doar oglinda lui `value` — orice foaie de
  // replanificare beneficiaza sa arate unde e taskul acum. Azi/Mâine se aprind cand
  // termenul cade pe ele; „Alege" preia orice alta zi (inclusiv restant), fiindca
  // ea e singura care poate ajunge acolo.
  const k = $derived(zilePanaLa(value))
  const aziActiv = $derived(k === 0)
  const maineActiv = $derived(k === 1)
  const alegeActiv = $derived(k !== null && k !== 0 && k !== 1)
</script>

<div class="sz">
  <div class="sz-rand">
    <button type="button" class="sz-optiune" class:activ={aziActiv} onclick={() => onalege?.(ziPeste(0))}>
      <Sun size={15} strokeWidth={1.5} /> Azi
    </button>
    <button type="button" class="sz-optiune" class:activ={maineActiv} onclick={() => onalege?.(ziPeste(1))}>
      <Sunrise size={15} strokeWidth={1.5} /> Mâine
    </button>
    <span class="sz-optiune sz-dp" class:activ={alegeActiv}>
      <CalendarSearch size={15} strokeWidth={1.5} />
      <DatePicker {value} eticheta="Alege" onchange={(v) => onalege?.(v || null)} />
    </span>
  </div>
  {#if aratScoate && value}
    <button type="button" class="sz-scoate" onclick={() => onalege?.(null)}>
      <X size={14} strokeWidth={1.5} /> Scoate din calendar
    </button>
  {/if}
</div>

<style>
  .sz { display: flex; flex-direction: column; gap: var(--space-6); }
  .sz-rand { display: flex; gap: var(--space-6); }

  .sz-optiune {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-height: var(--tap-min);
    padding: 0 var(--space-10);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    color: var(--text-secondary);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    white-space: nowrap;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .sz-optiune:hover { background: var(--accent-subtle); color: var(--accent-deep); }
  .sz-optiune:active { transform: scale(var(--press-scale)); }
  /* ZIUA CURENTA E APRINSA — fill de accent, ca ziua aleasa din calendar
     (`.dp-day.selected`): acelasi inteles („asta e ziua"), deci acelasi semn.
     Iconita si textul iau cerneala de pe fill. Bate hoverul (vine dupa el). */
  .sz-optiune.activ,
  .sz-optiune.activ:hover { background: var(--accent); color: var(--accent-text); }

  /* Al treilea slot poarta iconita LUI si imprumuta declansatorul lui DatePicker
     pentru text — deci calendarul se deschide de pe tot butonul, nu doar de pe
     colturi. */
  .sz-dp { position: relative; padding: 0; }
  .sz-dp :global(.dp) { width: auto; }
  .sz-dp :global(.dp-trigger) {
    min-height: var(--tap-min);
    padding: 0 var(--space-10) 0 var(--space-xs);
    gap: 0;
    background: none;
    border: none;
    box-shadow: none;
    color: inherit;
    font-family: inherit;
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
  }
  /* Iconita de calendar a declansatorului ar fi a doua pe acelasi buton, langa
     lupa noastra — doua calendare unul langa altul nu spun de doua ori. */
  .sz-dp :global(.dp-trigger svg) { display: none; }
  .sz-dp :global(.dp-trigger:hover) { background: none; color: inherit; }

  .sz-scoate {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-height: var(--ctrl-md);
    border-radius: var(--radius-sm);
    background: none;
    color: var(--text-dim);
    font-size: var(--font-control);
    font-weight: var(--fw-medium);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .sz-scoate:hover { background: var(--danger-subtle); color: var(--danger-deep); }

  /* IN FOAIE, 48. Componenta asta traieste in foi si in panouri de replanificare,
     iar foaia exista doar pe telefon (Modal devine sheet sub 768px) — deci pragul
     de foaie se aplica exact aici, nu peste tot. „Scoate" ramane mai scund cu
     bunastiinta: e actiunea din care pierzi ceva, si nu are voie sa fie la fel de
     usor de nimerit ca cele trei care aseaza taskul pe o zi. */
  @media (max-width: 768px) {
    .sz-optiune,
    .sz-dp :global(.dp-trigger) { min-height: var(--tap-sheet); }
    .sz-scoate { min-height: var(--tap-min); }
  }
</style>
