<script>
  // ===== ANTETUL — DOAR PE TELEFON =====
  //
  // Peste 768px nu se mai randeaza deloc (`App.svelte`): acolo marca, tema si
  // starea retelei stau in bara laterala, iar o bara de 56px care ar mai tine
  // doar gol nu e un cadru, e o margine. Ce a ramas aici e antetul de telefon,
  // neschimbat: marca, chipul de retea, cautarea si tema.
  import { Search } from '@lucide/svelte'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { apasareLunga } from '../../lib/apasareLunga.js'
  import { urmaActiva, porneste as pornesteUrma } from '../../lib/urma.js'
  import { toast } from '../../stores/ui.svelte.js'
  import ComutaTema from './ComutaTema.svelte'
  import FaraRetea from './FaraRetea.svelte'

  // JURNALUL DE PE APARAT SE PORNESTE DE PE MARCA, CU APASARE LUNGA. In aplicatia
  // Android nu exista bara de adresa, deci `?urma=1` n-are unde fi scris (Ion:
  // „pe aplicatia mobila nu pot pune adresa"). Marca e singurul obiect de pe
  // toate ecranele care n-are alta apasare lunga. Vezi `lib/urma.js`.
  function comutaUrma() {
    const acum = !urmaActiva()
    pornesteUrma(acum)
    toast(acum ? 'Urmă pornită — deschide o foaie, apoi apasă „Urmă”' : 'Urmă oprită', 'success')
    // Butonul „Urmă" citeste starea la montare; un eveniment il anunta.
    window.dispatchEvent(new CustomEvent('pif-urma'))
  }

  let { deschideCautarea = () => {} } = $props()

  // CAT E DE INALT ANTETUL, ca fapt disponibil in CSS.
  //
  // Pe telefon nu e o constanta: regula are `height: auto`, `min-height` si
  // `flex-wrap: wrap`, deci bara se poate rupe pe doua randuri, iar decupajul
  // ecranului (`--safe-top`) intra si el in padding. Cine are nevoie de
  // marginea ei de JOS nu o poate calcula din tokenuri fara sa se insele.
  //
  // Are nevoie arcul de trage-sa-reincarci: el porneste ascuns exact sub
  // antet si iese de acolo odata cu degetul. Inainte pornea de la 6px si urca
  // PESTE titlu — un disc care traverseaza un text viu.
  //
  // Se scrie pe <html>, ca `--nav-sens` (App) si `--kb` (Modal): acelasi tipar,
  // un singur scriitor per variabila.
  //
  // SE SI STERGE LA DEMONTARE, si asta conteaza de cand antetul e doar al
  // telefonului: dupa o largire a ferestrei componenta dispare, dar un stil
  // INLINE pe <html> nu dispare cu ea. Arcul ar porni de sub un antet care nu
  // mai exista, cu 56px mai jos decat trebuie. Fara valoare, cititorul cade pe
  // `var(--header-height)`, care pe desktop e chiar 0.
  let inaltime = $state(0)
  $effect(() => {
    document.documentElement.style.setProperty('--h-antet', inaltime + 'px')
    return () => document.documentElement.style.removeProperty('--h-antet')
  })
</script>

<header class="header" bind:clientHeight={inaltime}>
  <a href="/" class="brand" title="TORQA" use:apasareLunga={{ actiune: comutaUrma }} oncontextmenu={(e) => e.preventDefault()}>
    <!-- ACEEASI MARCA CA IN `BaraSus.svelte`, si asta e chiar rostul notei:
         pana la AURORA, antetul de telefon si bara de desktop desenau semne
         DIFERITE. Semnul ia `--accent`, deci urmeaza tema; coordonatele sunt cele
         canonice din `design/handoff-aurora/assets/torqa-logomark.svg`.
         Fara cuvantul „TORQA" langa el (handoff: marca singura in antet). -->
    <svg class="brand-semn" width="42" height="42" viewBox="0 0 64 64" aria-hidden="true">
      <g fill="none" stroke="var(--accent)" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 32a18 18 0 1 0 36 0 18 18 0 1 0-36 0" stroke-width="5" />
        <path d="M20 32c4-11.33 8-11.33 12 0s8 11.33 12 0" stroke-width="4.2" />
      </g>
    </svg>
  </a>

  <!-- `.header-context` (titlul paginii in bara) A PLECAT: era singurul titlu
       care nu statea in pagina — „sus pe mijloc", la alta inaltime decat restul,
       si invizibil pe telefon. Acum FIECARE ruta isi scrie h1-ul in continut,
       in aceeasi pozitie; bara tine doar marca si actiunile globale. -->
  <span class="h-spacer"></span>

  <FaraRetea />

  <div class="header-actions">
    <!-- CAUTAREA TRAIESTE INTR-UN SINGUR LOC: in navigatie.
         Pe telefon dockul nu o are (cele patru sloturi plus „Mai mult" sunt
         pline), deci acolo — si numai acolo — ramane in cap. Pe desktop e un
         rand cu numele ei in bara laterala. -->
    {#if ecran.telefon}
      <button class="h-btn" onclick={deschideCautarea} aria-label="Caută" title="Caută">
        <Search size={17} strokeWidth={1.5} />
      </button>
    {/if}
    <ComutaTema varianta="buton" sens="jos" />
  </div>
</header>

<style>
  .header {
    /* CADRUL NU CLIPESTE CAND SE SCHIMBA CONTINUTUL.
       Fara nume propriu, bara intra in instantaneul `root` al tranzitiei de
       ruta — deci se stingea si se reaprindea la fiecare schimbare de tab, si
       lua si cei ±10px de alunecare, desi e identica inainte si dupa. Cu nume,
       browserul o trateaza ca element persistent: ramane pe loc, iar
       cross-fadeul e doar pe ce se schimba efectiv, adica pagina.
       Pe iOS bara de navigatie nu se misca niciodata cand schimbi tabul; asta
       e perechea ei pe web. */
    view-transition-name: cadru-antet;
    height: var(--header-height);
    /* STICLA, DAR NU CEA DE ATUNCI (AURORA, 2026-08-23).
       Prima incercare era `blur(14px)` peste un fond semi-transparent, si
       continutul care trecea pe dedesubt se vedea ca o pata care se misca — pe o
       pagina cu carduri albe, exact acolo unde te uiti intai. Materialul AURORA
       rezolva chiar asta: 26px de blur APLATIZEAZA ce e dedesubt in loc sa-l
       tarasca. De aceea blurul nu coboara sub ~20px fara sa se reverifice
       contrastul — el e singurul motiv pentru care textul de aici se citeste.

       Antetul ia doar DOUA straturi din material, nu cele patru ale barelor
       plutitoare: e lipit de marginea de sus, deci n-are patru muchii de aratat.
       Rama completa (`--glass-rim`) e inlocuita de o singura linie jos. */
    background: var(--glass-sheen), var(--glass-bg);
    -webkit-backdrop-filter: var(--glass-filter);
            backdrop-filter: var(--glass-filter);
    box-shadow: inset 0 -1px 0 var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-lg);
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
  }

  /* Marca: un singur font, o greutate, fara separator. 18px e singura treapta
     din afara scarii de text — e logotip, nu continut. */
  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-10);
    font-weight: var(--fw-semibold);
    font-size: var(--font-brand);
    letter-spacing: var(--tracking-tight);
    color: var(--text);
    white-space: nowrap;
  }
  .brand-semn { flex: none; display: block; }

  .h-spacer { flex: 1; }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .h-btn {
    width: var(--ctrl-md);
    height: var(--ctrl-md);
    display: grid;
    place-items: center;
    border-radius: var(--radius-sm);
    background: var(--bg-surface);
    box-shadow: var(--shadow-sm);
    color: var(--text-secondary);
    transition: var(--transition-pressable);
  }
  .h-btn:hover { color: var(--text); }
  .h-btn:active { transform: scale(var(--press-scale)); }

  /* REZERVA, cand `backdrop-filter` lipseste: aceeasi culoare, alfa mai mare.
     Fara ea tenta ramane la .55 peste continut nefiltrat si textul devine ilizibil. */
  @supports not ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
    .header { background: var(--bar-bg); }
  }

  @media (max-width: 768px) {
    .header {
      flex-wrap: wrap;
      height: auto;
      min-height: var(--header-height);
      gap: var(--space-xs);
      padding-top: calc(var(--space-xs) + var(--safe-top));
      padding-bottom: var(--space-xs);
      padding-left: calc(var(--space-md) + var(--safe-left));
      padding-right: calc(var(--space-md) + var(--safe-right));
    }
    .brand { min-height: var(--tap-min); }
    .h-btn { width: var(--tap-min); height: var(--tap-min); }
  }
</style>
