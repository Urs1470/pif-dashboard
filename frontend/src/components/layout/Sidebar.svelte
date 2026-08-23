<script>
  // ===== BARA LATERALA (doar desktop) =====
  //
  // Inlocuieste dockul pe ecranele late. Dockul ramane cum era pe telefon: acolo
  // bara de jos e sub degetul mare, iar un sertar cu hamburger ar face din
  // navigatie doua atingeri in loc de una, exact pe ecranul de pe teren.
  //
  // DE CE O BARA, SI NU DOCKUL DE DESKTOP. Pastila de jos se ASCUNDEA singura si
  // aparea doar cand impingeai cursorul in ultimii 48px ai ecranului: in repaus,
  // pe desktop, aplicatia nu arata NICIO navigatie. Harta aplicatiei era un
  // lucru pe care trebuia sa-l chemi. O bara laterala nu se cheama — e acolo,
  // scrie unde esti, si are loc pentru toate sapte rutele cu numele intreg, nu
  // doar cu iconita.
  //
  // ANTETUL NU MAI EXISTA PE DESKTOP. Tinea marca in stanga si butonul de tema
  // in dreapta, cu ~1200px de gol intre ele — 56px de inaltime pentru doua
  // obiecte. Amandoua au urcat aici; inaltimea castigata se duce in
  // Planificator si Calendar, care chiar au nevoie de fiecare rand.
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import ComutaTema from './ComutaTema.svelte'
  import FaraRetea from './FaraRetea.svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { apasareLunga } from '../../lib/apasareLunga.js'
  import { urmaActiva, porneste as pornesteUrma } from '../../lib/urma.js'
  import { toast } from '../../stores/ui.svelte.js'

  let { deschideCautarea = () => {} } = $props()

  // ORDINEA E CEA DIN `ORDINE_NAV` (App.svelte), fiindca din ea iese SENSUL
  // tranzitiei de pagina: mai jos in bara -> continutul soseste din dreapta.
  // Doua ordini diferite ar face ca aceeasi navigare sa alunece intr-un sens pe
  // telefon si in celalalt pe desktop.
  const items = [
    { path: '/', label: 'Acasă', icon: 'home' },
    { path: '/projects', label: 'Proiecte', icon: 'projects' },
    { path: '/tasks', label: 'Taskuri', icon: 'tasks' },
    { path: '/plan', label: 'Planificator', icon: 'plan' },
    { path: '/calendar', label: 'Calendar', icon: 'calendar' },
    { path: '/departament', label: 'Departament', icon: 'departament' },
    { path: '/calculator', label: 'Calculator', icon: 'calculator' },
  ]

  function isActive(path) {
    if (path === '/') return router.path === '/'
    return router.path.startsWith(path)
  }

  const rutaActiva = $derived(items.find((i) => isActive(i.path))?.path ?? null)

  // ===== `--dock-h` E 0 CAT TIMP EXISTA BARA LATERALA =====
  //
  // Opt locuri isi socotesc distanta de jos din `--dock-h` (butoanele plutitoare
  // „+", toastul, jurnalul Urma, inaltimile din Calculator si Departament,
  // rezerva lui `.app-content`). Pe desktop nu mai exista bara de jos, deci
  // valoarea corecta e 0 — si trebuie SCRISA, nu lasata pe implicitul de 68px
  // din tokens: fiecare dintre cele opt ar tine 68px de gol sub el.
  //
  // Se scrie de aici, nu dintr-un `@media` in tokens, din doua motive:
  //  1. `Dock.svelte` o scrie ca stil INLINE pe <html>, iar un stil inline bate
  //     orice regula de foaie. Dupa o redimensionare telefon -> desktop valoarea
  //     lui ar ramane agatata si niciun `@media` n-ar putea-o corecta.
  //  2. Un singur scriitor la un moment dat: cine tine navigatia tine si cat
  //     spatiu ocupa ea. Acelasi tipar ca `--nav-sens` (App) si `--kb` (Modal).
  //
  // La demontare se STERGE, nu se pune inapoi 68: la desktop -> telefon urmeaza
  // `Dock`, care o masoara singur, iar intre cele doua clipe implicitul din
  // tokens e raspunsul corect. Stergerea e CONDITIONATA de faptul ca valoarea de
  // pe <html> e inca a noastra: ordinea montare/desmontare intre cele doua
  // navigatii nu e garantata, iar o stergere oarba ar putea sterge exact
  // inaltimea pe care dockul tocmai a masurat-o. Aceeasi garda, simetric, in
  // `Dock.svelte`.
  $effect(() => {
    document.documentElement.style.setProperty('--dock-h', '0px')
    return () => {
      if (document.documentElement.style.getPropertyValue('--dock-h') === '0px') {
        document.documentElement.style.removeProperty('--dock-h')
      }
    }
  })

  // ===== TENTA RUTEI ACTIVE ALUNECA, NU SE APRINDE IN ALT LOC =====
  // Acelasi obiect ca in dock, rotit pe verticala. Motivul e neschimbat: un
  // fundal care se stinge intr-un rand si se aprinde in altul nu spune nimic
  // despre drumul dintre ele. Slotul care poarta tenta e MARCAT in markup
  // (`data-pilula`), nu cautat dupa `.active`.
  let barEl = $state(null)
  let pilula = $state({ y: 0, h: 0, r: '', gata: false })
  let pilulaAsezata = $state(false)
  let amMasurat = false   // NEreactiv: citit in efectul care scrie `pilula`

  function masoaraPilula() {
    const slot = barEl?.querySelector('[data-pilula]')
    if (!slot) { pilula.gata = false; return false }
    // `offsetTop` se masoara fata de cutia de PADDING a lui `offsetParent` —
    // exact reperul fata de care se aseaza si un copil absolut cu `top: 0`.
    pilula.y = slot.offsetTop
    pilula.h = slot.offsetHeight
    // Raza se CITESTE din slot: o a doua copie a regulii s-ar desincroniza.
    pilula.r = getComputedStyle(slot).borderRadius
    pilula.gata = true
    return true
  }

  $effect(() => {
    router.path
    if (!barEl) return
    const are = masoaraPilula()
    if (are && !amMasurat) {
      amMasurat = true
      // Un cadru fara tranzitie, ca PRIMA asezare sa nu alunece de sus — ar
      // arata ca o navigare care n-a avut loc.
      requestAnimationFrame(() => { pilulaAsezata = true })
    }
  })

  // Bara isi poate schimba inaltimea (chipul „Fara retea" apare si dispare in
  // picior), iar randurile de deasupra se muta odata cu ea. Fara reMasurare,
  // tenta ar ramane pe pozitia veche.
  $effect(() => {
    if (!barEl) return
    const ro = new ResizeObserver(() => masoaraPilula())
    ro.observe(barEl)
    return () => ro.disconnect()
  })

  // JURNALUL DE PE APARAT SE PORNESTE DE PE MARCA, CU APASARE LUNGA. In
  // aplicatia Android nu exista bara de adresa, deci `?urma=1` n-are unde fi
  // scris (Ion: „pe aplicatia mobila nu pot pune adresa"). Marca e singurul
  // obiect de pe toate ecranele care n-are alta apasare lunga. Vezi `lib/urma.js`.
  function comutaUrma() {
    const acum = !urmaActiva()
    pornesteUrma(acum)
    toast(acum ? 'Urmă pornită — deschide o foaie, apoi apasă „Urmă”' : 'Urmă oprită', 'success')
    // Butonul „Urmă" citeste starea la montare; un eveniment il anunta.
    window.dispatchEvent(new CustomEvent('pif-urma'))
  }
</script>

<aside class="bara" bind:this={barEl} aria-label="Navigație principală">
  <a href="/" class="brand" use:link title="TORQA"
     use:apasareLunga={{ actiune: comutaUrma }} oncontextmenu={(e) => e.preventDefault()}>
    <!-- Marca „Unda" — semnal dreptunghiular (PWM). Aceleasi coordonate ca
         `frontend/public/favicon.svg`, dar aici tila ia `--accent` si cerneala
         `--accent-text`, deci marca URMEAZA TEMA; fisierul .svg e un asset si nu
         stie de tokenuri, deci acolo hexul e scris. -->
    <svg class="brand-tile" width="26" height="26" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="var(--accent)" />
      <path d="M10 42 H21.5 V22 H32 V42 H42.5 V22 H54" fill="none" stroke="var(--accent-text)"
            stroke-width="6.4" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <span class="brand-name">TORQA</span>
  </a>

  <!-- CAUTAREA E UN RAND, NU O LUPA. In dock era o iconita fara nume, langa
       sapte alte iconite; aici are loc sa spuna ce face si sa-si arate scurtatura
       — singurul loc din aplicatie unde Ctrl+K e SCRIS undeva. -->
  <button class="cauta" onclick={deschideCautarea} aria-label="Caută (Ctrl+K)">
    <Search size={17} strokeWidth={1.5} />
    <span class="cauta-et">Caută</span>
    <kbd class="cauta-scurt">Ctrl K</kbd>
  </button>

  <nav class="rute">
    <!-- Tenta rutei active. Primul copil, ca sa fie clar ca sta DEDESUBT; e
         absoluta, deci nu intra in flexul listei. -->
    <span class="pilula" class:gata={pilula.gata} class:asezata={pilulaAsezata}
          style="--py:{pilula.y}px; --ph:{pilula.h}px; --pr:{pilula.r}"
          aria-hidden="true"></span>
    {#each items as item (item.path)}
      <a
        href={item.path}
        use:link
        onclick={(e) => e.currentTarget.blur()}
        class="ruta"
        class:active={isActive(item.path)}
        data-pilula={rutaActiva === item.path ? '' : undefined}
        aria-current={isActive(item.path) ? 'page' : undefined}
      >
        <SolidIcon name={item.icon} size={19} />
        <span class="ruta-et">{item.label}</span>
      </a>
    {/each}
  </nav>

  <div class="picior">
    <FaraRetea varianta="rand" />
    <ComutaTema varianta="rand" sens="sus" />
  </div>
</aside>

<style>
  .bara {
    /* Perechea lui `cadru-doc` de la dock: bara de navigatie e CADRU, nu
       continut, deci nu intra in instantaneul `root` si nu ia alunecarea de
       ±10px la fiecare schimbare de ruta. Ce se schimba in ea e tenta rutei
       active, iar aceea trece dintr-un rand in altul pe durata tranzitiei. */
    view-transition-name: cadru-lateral;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: var(--sidebar-w);
    z-index: var(--z-sticky);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    /* Safe-area la STANGA: pe un laptop nu inseamna nimic, dar bara e lipita de
       marginea ferestrei si un decupaj (sau o bara de sistem verticala) ar
       taia din randuri. Costa o functie si acopera cazul. */
    /* Sus `--space-lg`, ca marca sa inceapa la ACEEASI inaltime cu primul obiect
       din continut. Masurat pe toate sapte rutele: continutul incepe la 24px de
       marginea ferestrei, marca pornea de la 16 — opt pixeli de decalaj intre
       singurele doua lucruri de pe primul rand al ecranului, adica exact genul de
       nepotrivire pe care o vezi fara s-o poti numi. */
    padding: var(--space-lg) var(--space-10) var(--space-10) calc(var(--space-10) + var(--safe-left));
    /* ACELASI TRATAMENT CA ANTETUL DE DINAINTE, ROTIT: fondul paginii plus o
       linie. NU `--bg-surface`: aceea e materialul CARDURILOR din continut, iar
       o bara din acelasi material s-ar citi ca inca un card, doar mai lung.
       Bara nu e ridicata deasupra paginii — e o alta regiune a ei, si asta se
       spune printr-o linie, nu printr-o umbra. */
    background: var(--bg);
    border-right: 1px solid var(--border);
  }

  /* Marca: un singur font, o greutate, fara separator. 18px e singura treapta
     din afara scarii de text — e logotip, nu continut. */
  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-10);
    height: var(--ctrl-md);
    padding: 0 var(--space-6);
    margin-bottom: var(--space-2xs);
    font-weight: var(--fw-semibold);
    font-size: var(--font-brand);
    letter-spacing: var(--tracking-tight);
    color: var(--text);
    white-space: nowrap;
    text-decoration: none;
  }
  .brand-tile { flex: none; display: block; }

  .cauta {
    display: flex;
    align-items: center;
    gap: var(--space-10);
    width: 100%;
    height: var(--ctrl-md);
    padding: 0 var(--space-10);
    margin-bottom: var(--space-2xs);
    border: none;
    border-radius: var(--radius-sm);
    /* Campul, nu suprafata: cautarea e o INTRARE, si asa arata orice intrare din
       aplicatie (`--bg-input` e alias pentru `--bg-elevated`). */
    background: var(--bg-elevated);
    color: var(--text-dim);
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .cauta:hover { color: var(--text-secondary); background: var(--bg-hover); }
  .cauta-et { flex: 1; }
  .cauta-scurt {
    flex: none;
    font-family: var(--font-mono);
    font-size: var(--font-label);
    color: var(--text-dim);
    letter-spacing: var(--tracking-normal);
  }

  .rute {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
    /* Sapte randuri incap pe orice ecran de desktop. `min-height: 0` +
       `overflow-y: auto` sunt plasa pentru ferestre scunde (un laptop de 13"
       cu bara de sarcini si consola deschisa): lista se deruleaza, piciorul
       ramane la locul lui. */
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
  }

  /* TENTA E UN SINGUR OBIECT CARE ALUNECA, NU UN FUNDAL CARE SE APRINDE PE ALT
     ELEMENT. Sta SUB randuri, deci fiecare rand are nevoie de context propriu ca
     sa picteze deasupra (vezi `.ruta`). */
  .pilula {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: var(--ph, 38px);
    border-radius: var(--pr, var(--radius-sm));
    background: var(--accent-subtle);
    transform: translateY(var(--py, 0px));
    opacity: 0;
    pointer-events: none;
    z-index: 0;
  }
  /* Vizibila abia dupa prima masuratoare — pana atunci ar fi lipita de marginea
     de sus, adica exact de unde n-are voie sa alunece. */
  .pilula.gata { opacity: 1; }
  /* ELAN. Tenta traverseaza o distanta pe care O VEZI — de la un rand la altul —
     deci are voie sa arate ca a avut viteza: depaseste cu ~4% si revine.
     Doar `transform`: OPACITATEA ramane pe curba de vopsea. O depasire pe
     opacitate se citeste ca palpait, si e chiar regula scrisa in tokens
     („effects — NICIODATA"). */
  .pilula.asezata {
    transition: transform var(--dur-arc-elan) var(--ease-arc-elan), opacity var(--dur-fast) var(--ease);
  }

  .ruta {
    /* Peste pastila. Vezi nota de la `.pilula`. */
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: var(--space-10);
    height: var(--ctrl-md);
    padding: 0 var(--space-10);
    border-radius: var(--radius-sm);
    /* `--text-secondary`, nu `--text-dim`: un drum inactiv trebuie sa se poata
       CITI, nu doar ghici — e singura harta a aplicatiei. Estompatul e pentru
       text care insoteste. */
    color: var(--text-secondary);
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    text-decoration: none;
    white-space: nowrap;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease),
      transform var(--dur-press) var(--ease);
  }
  .ruta :global(svg) { flex: none; }
  .ruta-et { overflow: hidden; text-overflow: ellipsis; }
  /* Fara ridicare la hover: „translateY" nu e in setul de miscare — el are trei
     durate si o apasare, nu o plutire. Hoverul schimba doar cerneala si fondul. */
  @media (hover: hover) {
    .ruta:hover { color: var(--text); background: var(--bg-hover); }
  }
  .ruta:active { color: var(--text); transform: scale(var(--press-scale)); }
  /* Activ = TENTA de accent cu cerneala adanca, nu accentul plin. Fillul plin ar
     face din randul curent lucrul cel mai tare colorat de pe ecran — mai tare
     decat orice buton de actiune — desi el nu e o actiune, e o informatie despre
     unde esti. Fondul il poarta `.pilula`; aici ramane doar cerneala. */
  .ruta.active { color: var(--accent-deep); font-weight: var(--fw-semibold); }
  /* Hoverul si apasarea nu mai pot picta peste tenta: fondul lor ar sta DEASUPRA
     pastilei (randul e z-index 1) si s-ar citi ca un gri peste accent. */
  .ruta.active:hover, .ruta.active:active { background: transparent; }
  .ruta.active:hover { transform: none; }

  .picior {
    /* `margin-top: auto` impinge piciorul la fund fara sa fixeze inaltimea
       listei — deci cand chipul „Fara retea" apare, randurile de deasupra nu se
       misca, doar piciorul creste in sus. */
    margin-top: auto;
    padding-top: var(--space-sm);
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
  }

  /* Bara nu exista pe telefon — acolo navigatia e dockul de jos. Regula e o
     PLASA: `App.svelte` oricum nu randeaza componenta sub 768px (`ecran.telefon`),
     dar intre schimbarea mediei si re-randare exista un cadru, iar in cadrul ala
     bara ar acoperi un sfert din latimea telefonului. */
  @media (max-width: 768px) {
    .bara { display: none; }
  }
</style>
