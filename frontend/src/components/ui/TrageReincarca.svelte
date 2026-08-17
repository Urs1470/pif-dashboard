<script>
  // ARCUL DE REINCARCARE — singurul lucru pe care il vezi din gest.
  //
  // Se randeaza O SINGURA data, in `App.svelte`, si citeste starea comuna din
  // `lib/reincarcare.svelte.js`. Motivul pentru care nu sta in fiecare pagina:
  // ar fi patru obiecte identice care se pot desincroniza, iar pe telefon
  // fiecare ar veni cu propriul strat de compozitare cat latimea ecranului.
  //
  // Doua stari, si se citesc diferit CU BUNA STIINTA:
  //   TRAGERE  — arcul se umple odata cu degetul. Spune „cat mai am": e o
  //              masura, deci merge liniar cu gestul, fara nicio curba proprie.
  //   ROTIRE   — arcul devine o portiune care se invarte. Spune „acum astept":
  //              nu mai are un capat, fiindca nici raspunsul n-are un termen.
  // Trecerea dintre ele nu se anima: sunt doua propozitii, nu una care se
  // schimba. O tranzitie intre „cat mai am" si „nu stiu cat" ar minti.
  import { reincarcare } from '../../lib/reincarcare.svelte.js'
  import { motion } from '../../lib/motion.svelte.js'

  const PRAG = 64
  const R = 9
  const CIRC = 2 * Math.PI * R

  // 0..1 — cat din prag s-a facut. Peste prag ramane 1: arcul plin inseamna
  // „daca dai drumul, se intampla", si nu se mai poate spune mai tare.
  const progres = $derived(Math.min(1, reincarcare.tras / PRAG))
  const gata = $derived(progres >= 1)
  const vizibil = $derived(reincarcare.tras > 0 || reincarcare.seRoteste)
</script>

{#if vizibil}
  <!-- `aria-hidden`: ce anunta gestul asta se anunta oricum prin continutul care
       se schimba, iar un cititor de ecran n-are cum sa traga de lista. -->
  <div class="ptr" class:roteste={reincarcare.seRoteste} aria-hidden="true"
       style:--tras="{reincarcare.tras}px" style:--p={progres}>
    <div class="ptr-disc" class:plin={gata}>
      <svg viewBox="0 0 24 24" width="20" height="20">
        <!-- Pista: spune unde ajunge arcul, deci exista de la primul milimetru.
             Fara ea, un arc scurt nu se citeste ca „inceput", ci ca „aproape gata". -->
        <circle class="ptr-pista" cx="12" cy="12" r={R} />
        <circle class="ptr-arc" cx="12" cy="12" r={R}
                stroke-dasharray={CIRC}
                stroke-dashoffset={reincarcare.seRoteste ? CIRC * 0.72 : CIRC * (1 - progres)} />
      </svg>
    </div>
  </div>
{/if}

<style>
  /* Sta DEASUPRA continutului dar SUB modale si toasturi: e un raspuns la un gest
     pe pagina, nu un strat peste ea. */
  .ptr {
    position: fixed;
    top: calc(var(--safe-top) + 6px);
    left: 50%;
    z-index: var(--z-sticky);
    pointer-events: none;
    /* Coboara odata cu degetul. `translate`, nu `transform`: aceeasi impartire ca
       la foaie — o proprietate, un stapan. */
    translate: -50% var(--tras, 0px);
    /* Cat timp degetul trage NU exista tranzitie, altfel arcul ramane in urma lui
       si se simte ca lag. La ridicare, revenirea e animata (vezi `.ptr:not(...)`). */
    transition: none;
  }
  .ptr.roteste { transition: translate var(--dur-base) var(--ease); }

  .ptr-disc {
    width: 34px; height: 34px;
    display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-full);
    background: var(--bg-overlay);
    box-shadow: var(--shadow-md);
    color: var(--text-dim);
    /* Creste odata cu gestul, dar putin: de la 0,86 la 1. Discul e o tinta care
       nu se atinge, deci marimea lui nu poarta informatie — poarta doar viata. */
    scale: calc(0.86 + 0.14 * var(--p, 0));
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease);
  }
  /* La prag, cerneala trece in accent: culoarea e STARE, nu decor — spune „dai
     drumul si se intampla". Fondul ramane suprafata: un disc plin de accent, la
     16px de marginea de sus, ar concura cu tot ce e dedesubt. */
  .ptr-disc.plin { color: var(--accent); }

  .ptr-pista { fill: none; stroke: var(--border-strong); stroke-width: 2.5; }
  .ptr-arc {
    fill: none;
    stroke: currentColor;
    stroke-width: 2.5;
    stroke-linecap: round;
    /* Pornit de sus, ca la orice indicator circular: capatul de start trebuie sa
       fie acolo unde ochiul il cauta. */
    transform: rotate(-90deg);
    transform-origin: 12px 12px;
  }

  /* Rotirea: portiunea se invarte cat timp cererea e in zbor. `linear` si fara
     capat — o curba cu accelerare ar sugera ca stie cand se termina. */
  .ptr.roteste svg { animation: ptrRoti .8s linear infinite; }
  @keyframes ptrRoti { to { transform: rotate(360deg); } }

  @media (prefers-reduced-motion: reduce) {
    /* Rotirea RAMANE: ea nu e podoaba, e singurul lucru care spune ca cererea e
       inca in zbor — la fel ca semnul bifei si plierea randului, care raman si
       ele. Doar ca mai lenta, ca sa nu palpaie. */
    .ptr.roteste svg { animation-duration: 1.4s; }
    .ptr-disc { scale: 1; }
  }
</style>
