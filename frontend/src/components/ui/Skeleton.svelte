<script>
  // SCHELETUL ARE FORMA RANDULUI REAL, altfel continutul SARE cand soseste.
  //
  // Erau dungi de latimi date pe dinafara la fiecare loc de folosire, deci
  // fiecare lista isi inventa alta forma de asteptare — iar cand raspunsul
  // sosea, randurile de 46px inlocuiau dungi de 40 sau de 120. Saritura se vede
  // exact atunci cand ochiul deja se asezase pe pagina.
  //
  // `varianta="rand"` deseneaza randul de task: cerc (bifa), titlu, termen.
  // Latimile titlurilor sunt NEREGULATE cu intentie — patru dungi identice se
  // citesc ca un tabel gol, nu ca un text care se incarca.
  let {
    width = '100%',
    height = '20px',
    rounded = false,
    varianta = '',
    /** Cate randuri, la `varianta="rand"`. Maxim patru: peste atat, asteptarea
     *  se vede mai lunga decat e, iar lista reala e oricum mai scurta uneori. */
    randuri = 4,
    /** Cat asteapta pana se arata. Vezi mai jos; 0 il face imediat, pentru
     *  locurile unde scheletul E continutul (o demonstratie, un exemplu). */
    intarziere = 110,
  } = $props()

  const LATIMI = ['62%', '78%', '48%', '70%']

  // UN SCHELET CARE CLIPESTE E MAI RAU DECAT NICIUNUL.
  //
  // Masurat pe desktop cu 150ms dus-intors, la un click rapid pe un tab: pe
  // Taskuri si pe Calendar scheletul prindea EXACT UN CADRU — apărea si dispărea
  // in 16ms. Ochiul nu apucă sa citească o forma, dar prinde schimbarea, si
  // atunci pagina se citeste ca si cum s-ar fi rupt. Asta e chiar reprosul:
  // „vad un schelet apoi apare pagina".
  //
  // Deci asteptarea se arata doar daca CHIAR e o asteptare. Pragul e sub cel de
  // la care omul observa o intarziere (~100ms), deci un schelet care trebuie sa
  // apara apare la timp; unul care n-avea ce cauta acolo nu mai apare deloc.
  //
  // Nu se poate face din CSS (o animatie de opacitate ar picta oricum spatiul si
  // ar tine locul), si nu se poate face la fiecare apelant: sunt douazeci si
  // ceva, iar regula e a scheletului, nu a paginii.
  let vizibil = $state(intarziere === 0)
  $effect(() => {
    if (vizibil) return
    const t = setTimeout(() => { vizibil = true }, intarziere)
    return () => clearTimeout(t)
  })
</script>

{#if vizibil}
  {#if varianta === 'rand'}
    <div class="sk-lista" aria-hidden="true">
      {#each Array(Math.min(randuri, 4)) as _, i}
        <div class="sk-rand">
          <span class="skeleton sk-bifa"></span>
          <span class="skeleton sk-titlu" style="width: {LATIMI[i % LATIMI.length]}"></span>
          <span class="skeleton sk-termen"></span>
        </div>
      {/each}
    </div>
  {:else}
    <div class="skeleton" class:rounded style="width: {width}; height: {height}"></div>
  {/if}
{/if}

<style>
  /* FARA DUNGA CARE MATURA (contract miscare, scris de doua ori): scheletul
     doar respira din opacitate, 1 -> .45, pe 1600ms. O dunga in miscare promite
     progres pe care nu-l masoara nimeni; pulsul spune doar „inca se incarca". */
  .skeleton {
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    animation: skel-puls 1.6s ease-in-out infinite;
  }
  .rounded {
    border-radius: var(--radius-full);
  }

  /* Aceeasi geometrie ca randul real: 46px, gap 12, padding 12, coloana de
     termen de 46. Daca se schimba acolo, se schimba si aici — de-aia numerele
     sunt scrise langa, nu imprastiate prin pagini. */
  .sk-lista { display: flex; flex-direction: column; }
  .sk-rand { display: flex; align-items: center; gap: var(--space-12);
             min-height: 46px; padding: 0 var(--space-12); }
  .sk-rand + .sk-rand { border-top: 1px solid var(--border); }
  .sk-bifa { width: 18px; height: 18px; border-radius: 50%; flex: none; }
  .sk-titlu { height: 13px; }
  .sk-termen { width: 30px; height: 11px; margin-left: auto; flex: none; }

  @media (prefers-reduced-motion: reduce) {
    .skeleton { animation: none; }
  }
  @keyframes skel-puls {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
  }
</style>
