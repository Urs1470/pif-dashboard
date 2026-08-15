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

  // O FELIE, NU UN ARC. Prima varianta desena inelul cu `r=5` si `stroke-width:
  // 2` — masurat pe machete, la 12px cele doua capete ale scarii („0/3" si
  // „5/5") aratau aproape la fel: un arc de doua puncte nu are suprafata din
  // care sa se citeasca cat e umplut.
  // Trucul: `r=3` cu `stroke-width: 6` intinde conturul cu 3px de fiecare parte,
  // deci de la centru (r=0) pana la marginea cercului (r=6) — adica pata plina a
  // unei felii de tort, desenata fara niciun `path`. La 100% devine disc plin.
  // Asta rezolva si obiectia „al doilea cerc pe rand": bifa e un CERC GOL de
  // 18px, felia e o pata de 12px. Nu se pot confunda decat la 0%, unde raman
  // amandoua goale — dar acolo felia e si mai mica, si mult mai stinsa.
  const C = 2 * Math.PI * 3   // circumferinta cercului pe care se deseneaza felia

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
      <circle class="tp-pista" cx="6" cy="6" r="5.25" />
      {#if frac > 0}
        <!-- `rotate` ca ATRIBUT SVG, nu `transform-origin` in CSS: pe elementele
             SVG originea implicita e coltul din stanga-sus al viewport-ului, si
             ar cere si `transform-box: fill-box` ca sa se poarte cum te astepti.
             Forma din atribut ia centrul explicit si merge peste tot.
             -90 muta inceputul feliei de la ora 3 la ora 12. -->
        <circle class="tp-felie" cx="6" cy="6" r="3"
                stroke-dasharray="{(frac * C).toFixed(3)} {C.toFixed(3)}"
                transform="rotate(-90 6 6)" />
      {/if}
    </svg>
    <span class="tpasi-cifre">{gata}/{total}</span>
  </span>
{/if}
