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
  } = $props()

  const LATIMI = ['62%', '78%', '48%', '70%']
</script>

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

<style>
  .skeleton {
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    position: relative;
    overflow: hidden;
  }
  .skeleton::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent 0%, var(--bg-hover) 50%, transparent 100%);
    animation: shimmer 1.4s var(--ease) infinite;
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
    .skeleton::after { animation: none; }
  }
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
</style>
