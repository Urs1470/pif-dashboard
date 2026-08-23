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
    /** Cat asteapta pana se arata, in ms. Vezi mai jos de ce implicitul e 0. */
    intarziere = 0,
  } = $props()

  const LATIMI = ['62%', '78%', '48%', '70%']

  // INTARZIEREA A FOST O REPARATIE GRESITA, SI MERITA SCRIS DE CE.
  //
  // Pornise de la o masuratoare buna: la un click rapid pe un tab, scheletul
  // prindea EXACT UN CADRU — apărea si dispărea in 16ms, iar ochiul nu citea o
  // forma, doar o zvacnire. Asa ca l-am facut sa astepte 110ms, ca sa nu mai
  // apara cand nu e nevoie.
  //
  // Masurat la incarcarea LA RECE pe o ruta, a iesit invers: cand asteptarea
  // chiar exista, intarzierea ADAUGA o stare. Cadrul paginii se randa la 611ms,
  // scheletul aparea la 727 (adica dupa cele 110), continutul la 800 — trei
  // forme in loc de doua, si cea din mijloc exista doar din cauza mea.
  //
  // Reparatia adevarata nu era la schelet, era la DATE: de cand memoria
  // supravietuieste repornirii (`lib/cache.js`), pe o ruta vazuta vreodata nu
  // mai exista asteptare, deci nici schelet. Ce ramane e prima intalnire cu o
  // pagina — acolo asteptarea e reala si se arata IMEDIAT, cu forma paginii si
  // cu o sosire (vezi `.page-loading` din App si `.skel` din Plan).
  //
  // Parametrul ramane pentru cazul in care un apelant stie ca asteptarea lui e
  // sub prag; niciunul nu-l foloseste azi.
  // svelte-ignore state_referenced_locally
  // INTENTIONAT: `intarziere` se citeste O DATA, la montare. E pragul de sub
  // care nu se arata schelet deloc, nu o valoare care se schimba in viata
  // componentei; un `$derived` l-ar reporni la fiecare schimbare de parametru.
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
