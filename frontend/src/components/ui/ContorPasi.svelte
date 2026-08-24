<script>
  /** Contorul de pasi al unui task: un inel de progres plus fractia („2/5").
   *
   *  O COMPONENTA, NU MARKUP COPIAT. Acelasi task apare in patru liste (/tasks,
   *  boardul „Astăzi", tabul Taskuri al proiectului, randul mobil din
   *  Planificator); un SVG scris de patru ori s-ar fi despartit tacut la prima
   *  ajustare de raza. Reteta de culoare si asezare sta in `.tpasi`, in
   *  `global.css`; aici sta doar forma.
   *
   *  Randeaza NIMIC daca taskul n-are pasi — garda e aici, ca apelantii sa nu
   *  repete acelasi `{#if}` de patru ori.
   */
  let { gata = 0, total = 0 } = $props()

  // UN INEL, CU GAURA — si a fost nevoie de doua incercari ca sa ramana inel.
  //
  // Prima varianta: `r=5` cu `stroke-width: 2`. NU SE CITEA — la 12px o banda de
  // doua puncte n-are suprafata din care sa vezi cat e umplut; pe macheta „0/3"
  // si „5/5" aratau aproape la fel.
  // A doua: `r=3` cu `stroke-width: 6`, adica un contur intins de la centru pana
  // la marginea cercului. Se citea, dar era o PLACINTA (Ion: „acum e disc, nu
  // inel"). Directia aleasa se numea „inel", iar un inel are gaura.
  //
  // Raspunsul corect nu e sa umpli discul, ci sa INGROSI BANDA, pastrand golul:
  // `r=4.5` cu `stroke-width: 3` deseneaza intre r=3 si r=6 — banda de 3px (cu
  // 50% mai groasa decat la prima incercare, deci vizibila) si gaura de 6px in
  // mijloc, deci forma ramane inel la orice umplere, inclusiv la 5/5.
  // Bifa de la capatul randului e tot un cerc, dar de 18px si mereu goala, cu
  // contur de 1.5; inelul are 12, banda de 3, si se umple. Nu se confunda.
  const R = 4.5
  const C = 2 * Math.PI * R   // circumferinta benzii pe care se deseneaza arcul

  const frac = $derived(total > 0 ? Math.min(1, Math.max(0, gata / total)) : 0)
</script>

{#if total > 0}
  <!-- `role="img"` + eticheta: pe rand, contorul sta INTR-UN BUTON (titlul), deci
       eticheta lui intra in numele accesibil al butonului — „Comandă piese de
       schimb, 2 din 5 subtaskuri făcute". Fara ea s-ar citi „2 slash 5". -->
  <span class="tpasi" role="img"
        aria-label="{gata} din {total} subtaskuri făcute"
        title="{gata} din {total} subtaskuri făcute">
    <svg class="tpasi-inel" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      <!-- Pista si arcul stau pe ACEEASI raza si aceeasi grosime: altfel n-ar fi
           acelasi inel, ar fi doua cercuri concentrice. -->
      <circle class="tp-pista" cx="6" cy="6" r={R} />
      <!-- `rotate` ca ATRIBUT SVG, nu `transform-origin` in CSS: pe elementele
           SVG originea implicita e coltul din stanga-sus al viewport-ului, si
           ar cere si `transform-box: fill-box` ca sa se poarte cum te astepti.
           Forma din atribut ia centrul explicit si merge peste tot.
           -90 muta inceputul arcului de la ora 3 la ora 12. -->
      <!-- SE RANDEAZA MEREU, INCLUSIV LA ZERO. Era sub `{#if frac > 0}`, si atunci
           trecerea de la 0 la primul subtask bifat CREA elementul — deci nu exista
           nimic de la ce sa se anime, arcul aparea din nimic. Fara `stroke-linecap`
           (vezi `.tp-arc` in global.css) un dash de lungime zero nu deseneaza
           nimic, deci la 0 arata exact la fel ca inainte. -->
      <circle class="tp-arc" cx="6" cy="6" r={R}
              stroke-dasharray="{(frac * C).toFixed(3)} {C.toFixed(3)}"
              transform="rotate(-90 6 6)" />
    </svg>
    <span class="tpasi-cifre">{gata}/{total}</span>
  </span>
{/if}
