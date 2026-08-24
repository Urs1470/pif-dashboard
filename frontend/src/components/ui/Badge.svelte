<script>
  let { color = 'var(--text-dim)', label = '', small = false } = $props()
</script>

<span class="badge" class:small style="--badge-color: {color}">
  {label}
</span>

<style>
  /* PASTILA, si asta e forma CORECTA sub AURORA: `--radius-xs` inseamna pastila
     (999), iar cipul de stare e chiar obiectul pe care schimbarea aia il tintea.
     Pana la 2026-08-24 aici scria opusul — „CHIP CU COLTURI DE 8, NU PASTILA
     ROTUNDA" — dintr-o scara de raze care nu mai exista de la redesign. Codul era
     bun, comentariul minţea, si asta e mai rau: comentariul e singurul loc unde se
     citeste INTENTIA unei valori, deci un comentariu vechi produce defecte noi.
     Punctul colorat a plecat: fondul tentat spune deja culoarea, iar la 5px punctul
     era doar zgomot. Textul ramane cum e scris — „Finalizat", nu „FINALIZAT": e o
     stare, nu o eticheta de sectiune. */
  .badge {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 0 9px;
    border-radius: var(--radius-xs);
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    /* CERNEALA PE TENTA SE INCHIDE. Fondul e 12% din culoarea primita, iar textul
       era scris cu culoarea PLINA peste el — exact cazul pentru care exista
       treapta `-deep`. `Badge` e generic si nu stie ce rol i s-a dat, deci isi
       deriva adancul din culoarea primita, in loc sa ceara inca un parametru. */
    color: color-mix(in oklab, var(--badge-color) 72%, var(--text));
    background: color-mix(in srgb, var(--badge-color) 12%, transparent);
    white-space: nowrap;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease);
  }
  /* „small" inseamna doar mai stramt (padding si inaltime), nu alta treapta. */
  .badge.small {
    min-height: 22px;
    padding: 0 var(--space-sm);
  }
</style>
