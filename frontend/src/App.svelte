<script>
  import { fade } from 'svelte/transition'
  import Header from './components/layout/Header.svelte'
  import Dock from './components/layout/Dock.svelte'
  import Sidebar from './components/layout/Sidebar.svelte'
  import { ecran } from './lib/ecran.svelte.js'
  import Toast from './components/ui/Toast.svelte'
  import TrageReincarca from './components/ui/TrageReincarca.svelte'
  import Tooltip from './components/ui/Tooltip.svelte'
  import Urma from './components/Urma.svelte'
  import CommandPalette from './components/layout/CommandPalette.svelte'
  import { setLucideProps, Compass, ArrowLeft } from '@lucide/svelte'
  import EmptyState from './components/ui/EmptyState.svelte'
  import ErrorState from './components/ui/ErrorState.svelte'
  import { router, resolveRoute, viewTransitionsOn, setPreincarcaRuta, link } from './lib/router.svelte.js'
  import { motionDuration, DUR_FAST, EASE, alunecare } from './lib/motion.svelte.js'

  /* ICONITELE SUNT LA 1.5, NU LA 2.
     Regula („Lucide la stroke-width 1.5") era scrisa in handoff si in sistemul de
     design, dar nu se aplicase nicaieri: 155 din cele 209 de iconite nu primeau
     deloc `strokeWidth`, deci cadeau pe implicitul bibliotecii, 2. Se vedea ca o
     interfata mai apasata decat tot restul redesignului — dar nu se vedea NICAIERI
     in cod, fiindca lipsa unei proprietati nu se poate grepa.
     Contextul lui Lucide da doar IMPLICITUL (`strokeWidth = props.strokeWidth ??
     globalProps.strokeWidth ?? 2`), deci cele 54 de locuri care cer explicit altceva
     raman neatinse — bifele de 3, care la 12px trebuie sa se vada ca un semn, nu ca
     o linie. NU se poate face din CSS: Lucide scrie `stroke-width` ca ATRIBUT, iar
     o regula CSS ar bate si suprascrierile explicite, adica exact pe cele dorite. */
  setLucideProps({ strokeWidth: 1.5 })

  import Home from './pages/Home.svelte'
  import Skeleton from './components/ui/Skeleton.svelte'

  let paleta = $state(null)

  const lazyCache = {}
  function lazy(loader) {
    return { _lazy: true, loader }
  }

  const routes = {
    '/': Home,
    '/projects': lazy(() => import('./pages/Projects.svelte')),
    '/projects/:id': lazy(() => import('./pages/ProjectDetail.svelte')),
    '/tasks': lazy(() => import('./pages/Tasks.svelte')),
    '/plan': lazy(() => import('./pages/Plan.svelte')),
    '/calendar': lazy(() => import('./pages/Calendar.svelte')),
    '/departament': lazy(() => import('./pages/Departament.svelte')),
    '/calculator': lazy(() => import('./pages/Calculator.svelte')),
  }

  // Routerul nu stie sa incarce module — `lazyCache` e aici. Deci ii dam functia
  // pe care s-o astepte inainte sa schimbe ruta, ca tranzitia sa se termine pe
  // pagina adevarata si nu pe schelet (vezi `navigate`). Cand ruta e deja in
  // cache, promisiunea e deja rezolvata si nu costa nimic.
  //
  // MODULUL ERA DOAR JUMATATE. Tranzitia se termina pe codul paginii, dar
  // cererea de date pornea abia dupa montare — adica dupa ce tranzitia se
  // incheiase — deci ateriza pe scheletul paginii. Acum fiecare pagina care are
  // ceva de adus isi exporta propriul `pregateste()` din `<script module>`:
  // acolo, langa codul care oricum construieste URL-ul, nu intr-o harta
  // ruta -> URL tinuta aici, care s-ar desparti tacut de pagini.
  //
  // Se pastreaza MODULUL intreg, nu doar `default`: `pregateste` e un export
  // frate cu componenta.
  const modCache = {}
  setPreincarcaRuta(async (cale) => {
    const brut = cale || '/'
    const m = resolveRoute(routes, brut.split('?')[0] || '/')
    if (!m || !m.component._lazy) return
    if (!modCache[m.pattern]) {
      const mod = await m.component.loader()
      modCache[m.pattern] = mod
      lazyCache[m.pattern] = mod.default
    }
    // Query-ul se parseaza din calea CERUTA, nu din `router.query`: la
    // preincarcare ruta inca nu s-a aplicat, deci starea routerului e a paginii
    // pe care esti acum.
    const qi = brut.indexOf('?')
    const query = {}
    if (qi !== -1) new URLSearchParams(brut.slice(qi + 1)).forEach((v, k) => { query[k] = v })
    // Esecul preincarcarii nu opreste navigarea: pagina isi cere singura datele
    // la montare si stie sa arate eroarea acolo, in contextul ei.
    try { await modCache[m.pattern].pregateste?.(m.params, query) } catch (_) {}
  })

  const rawMatch = $derived(resolveRoute(routes))
  const routeKey = $derived(router.path)
  // When the browser drives the route change via the View Transitions API, let it
  // own the cross-fade; the Svelte fade only runs as a fallback (no VT support).
  // motionDuration() also zeroes this under reduced-motion regardless of VT support.
  const fadeDur = $derived(motionDuration(viewTransitionsOn() ? 0 : DUR_FAST))

  // ===== SCHIMBAREA DE PAGINA E DIRECTIONALA (contractul de miscare: 240ms,
  // „inainte din dreapta, inapoi din stanga"). Sensul vine din ORDINEA
  // NAVIGATIEI — spre dreapta in dockul de telefon, mai jos in bara laterala de
  // desktop — deci continutul soseste din dreapta, si invers. Lista de mai jos e
  // sursa acelei ordini pentru amandoua; `Dock.svelte` si `Sidebar.svelte` isi
  // insira rutele in aceeasi ordine, altfel aceeasi navigare ar aluneca intr-un
  // sens pe telefon si in celalalt pe desktop.
  // Doua drumuri, acelasi sens:
  //  - fara View Transitions: `alunecare` (Svelte) pe blocul de ruta;
  //  - cu View Transitions: browserul detine tranzitia, deci sensul i se da prin
  //    variabila `--nav-sens` de pe <html>, citita de regulile
  //    `::view-transition-*(root)` din global.css.
  // `sensNav` e un $derived LENES, citit chiar de parametrii tranzitiei — asa
  // valoarea e proaspata inainte sa porneasca intro-ul (un $effect ar fi rulat
  // dupa). Navigarea in interiorul aceleiasi sectiuni (/projects -> /projects/:id,
  // adica exact morph-ul de card) are sens 0 — morph-ul nu primeste si o alunecare.
  const ORDINE_NAV = ['/', '/projects', '/tasks', '/plan', '/calendar', '/departament', '/calculator']
  const bazaRutei = (p) => '/' + ((p || '/').split('/')[1] || '')
  // Rutele al caror continut e o LISTA de randuri. Vezi scheletul de mai jos.
  const RUTE_LISTA = new Set(['/tasks', '/projects'])
  let bazaVeche = null
  const sensNav = $derived.by(() => {
    const b = bazaRutei(router.path)
    let s = 0
    if (bazaVeche !== null && b !== bazaVeche) {
      const a = ORDINE_NAV.indexOf(bazaVeche)
      const z = ORDINE_NAV.indexOf(b)
      if (a >= 0 && z >= 0 && a !== z) s = z > a ? 1 : -1
    }
    bazaVeche = b
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--nav-sens', String(s))
    }
    return s
  })

  let LoadedComponent = $state(null)
  let loadedParams = $state({})
  let loadError = $state(null)
  // Se numara reincercarile, ca efectul de mai jos sa se re-rule pe aceeasi ruta.
  // Fara ceva de care sa depinda, „Încearcă din nou" n-ar avea ce sa reporneasca:
  // `rawMatch` e neschimbat, deci efectul nu s-ar mai executa niciodata.
  let reincercare = $state(0)

  $effect(() => {
    const m = rawMatch
    reincercare
    if (!m) { LoadedComponent = null; return }

    if (m.component._lazy) {
      // Cheia e PATTERN-ul rutei, nu prefixul caii — altfel /projects si
      // /projects/:id ar imparti aceeasi intrare in cache.
      const key = m.pattern
      if (lazyCache[key]) {
        LoadedComponent = lazyCache[key]
        loadedParams = m.params
      } else {
        LoadedComponent = null
        loadError = null
        m.component.loader().then(mod => {
          // Si aici, nu doar in preincarcare: pe drumul direct (link extern,
          // notificare, reincarcare de pagina) preincarcarea nu ruleaza, iar
          // fara asta `modCache` ar ramane gol si urmatorul hover ar reimporta.
          modCache[key] = mod
          lazyCache[key] = mod.default
          LoadedComponent = mod.default
          loadedParams = m.params
        }).catch(e => { loadError = e.message })
      }
    } else {
      LoadedComponent = m.component
      loadedParams = m.params
    }
  })

  function incearcaDinNou() {
    loadError = null
    reincercare++
  }
</script>

<a class="skip-link" href="#main-content">Sari la continut</a>

<div class="app-layout">
  <div class="app-main">
    <!-- ANTETUL E DOAR AL TELEFONULUI. Pe desktop marca, tema si starea retelei
         stau in bara laterala, iar o bara de 56px care ar mai tine doar gol nu e
         un cadru, e o margine. -->
    {#if ecran.telefon}
      <Header deschideCautarea={() => paleta?.deschide()} />
    {/if}
    <main class="app-content" id="main-content">
      {#key routeKey}
        <!-- `sensNav` se citeste NEconditionat (si pe ramura View Transitions):
             cititul e cel care il recalculeaza si scrie `--nav-sens` pe <html>. -->
        {@const sens = sensNav}
        <div class="content-width"
             in:alunecare={{ sens: viewTransitionsOn() ? 0 : sens, duration: 240 }}
             out:fade={{ duration: fadeDur, easing: EASE }}>
          <!-- DOUA LUCRURI DIFERITE, DOUA FORME.
               O ADRESA GRESITA NU E O EROARE: patratul ramane neutru, ca la orice
               stare goala, si primesti drumul inapoi. O pagina care n-a putut fi
               INCARCATA chiar a picat: patrat in tenta de restant si un buton care
               reincearca. Amandoua erau text simplu intr-un `<div>` — singurele
               doua ecrane din aplicatie care nu foloseau componentele desenate
               pentru exact situatiile astea. -->
          {#if loadError}
            <ErrorState title="Pagina nu s-a încărcat"
                        message="Probabil s-a pierdut rețeaua în timpul încărcării. ({loadError})"
                        onretry={incearcaDinNou} />
          {:else if LoadedComponent}
            <LoadedComponent params={loadedParams}></LoadedComponent>
          {:else if rawMatch}
            <!-- SCHELETUL DE RUTA ARE FORMA PAGINII CATRE CARE MERGI.
                 Masurat la prima deschidere pe telefon (4G, CPU 4x): blocul
                 generic „bara de 60% + caseta de 200px" statea pe ecran 731ms,
                 iar dupa el venea lista — deci vedeai DOUA forme diferite, si
                 niciuna nu semana cu pagina. Aterizarea pe telefon e chiar o
                 lista (`/tasks?sfera=personal`), la fel /projects si pagina de
                 proiect: pe ele scheletul de RANDURI e exact ce urmeaza, deci
                 umplerea de dupa e o inlocuire, nu o schimbare de forma.
                 Doua forme, nu sapte: o harta ruta -> schelet ar fi a doua sursa
                 de adevar despre cum arata fiecare pagina. -->
            {#if RUTE_LISTA.has(bazaRutei(router.path))}
              <div class="page-loading rand asteptare"><Skeleton varianta="rand" randuri={6} /></div>
            {:else}
              <div class="page-loading asteptare"><Skeleton width="60%" height="24px" /><Skeleton width="100%" height="200px" /></div>
            {/if}
          {:else}
            <EmptyState icon={Compass} title="Aici nu e nimic"
                        description="Adresa asta nu duce nicăieri în aplicație.">
              <div class="nf">
                <code class="nf-adresa">{router.path}</code>
                <a class="nf-inapoi" href="/" use:link><ArrowLeft size={15} strokeWidth={1.5} />Înapoi la Astăzi</a>
              </div>
            </EmptyState>
          {/if}
        </div>
      {/key}
    </main>
  </div>

  <!-- DOUA NAVIGATII, NICIODATA AMANDOUA. Pe telefon dockul de jos, sub degetul
       mare; pe desktop bara laterala, mereu la vedere. Nu se randeaza ambele cu
       una ascunsa din CSS, fiindca fiecare SCRIE `--dock-h` pe <html> — doi
       scriitori pe aceeasi variabila inseamna ca ultimul montat castiga, la
       intamplare.
       Amandoua cheama paleta printr-o functie exportata, nu printr-o apasare de
       taste fabricata (vezi `deschide()` din CommandPalette). -->
  {#if ecran.telefon}
    <Dock deschideCautarea={() => paleta?.deschide()} />
  {:else}
    <Sidebar deschideCautarea={() => paleta?.deschide()} />
  {/if}
  <CommandPalette bind:this={paleta} />
  <Toast />
  <!-- Arcul de „trage sa reincarci". Randat O SINGURA data, aici: gestul e al
       cadrului, nu al paginii — vezi `lib/reincarcare.svelte.js`. -->
  <TrageReincarca />
  <!-- Un singur tooltip pentru toata aplicatia; citeste atributele `title`. -->
  <Tooltip />
  <!-- Jurnalul de pe aparat (`#/?urma=1`) — vezi lib/urma.js. -->
  <Urma />
</div>

<style>
  .app-layout {
    min-height: 100dvh;
  }

  /* `overflow-x: clip`, NU `overflow: hidden`.
     `hidden` face din .app-main un container de derulare, iar un `position: sticky`
     dinauntru se lipeste de scrollportul LUI (care nu deruleaza niciodata) — adica
     de nimic. Headerul se declara sticky de la inceput si nu s-a lipit nici o data:
     scrolleaza 400px si pleaca cu 400px. `clip` taie la fel pe orizontala, dar nu
     creeaza container de derulare, deci sticky-ul se raporteaza iar la viewport.
     Conteaza cel mai mult pe telefon, unde listele sunt lungi si drumul inapoi sus
     e lung. */
  .app-main {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
    overflow-x: clip;
    /* BARA LATERALA IMPINGE, NU ACOPERA. E `position: fixed` (deci iese din
       flux) tocmai ca sa nu deruleze cu pagina; rezerva o tine coloana de
       continut. Pe telefon `--sidebar-w` e 0, deci regula nu face nimic acolo.
       Pe `.app-main`, nu pe `.app-content`: si antetul de telefon, daca ecranul
       s-ar largi cat sa aiba amandoua, trebuie sa inceapa dupa bara.
       PADDING, nu `margin-left`: cu margin, `overflow-x: clip` ar taia de la
       marginea ferestrei si ultimii 220px de continut ar disparea sub taietura. */
    padding-left: var(--sidebar-w);
    transition: padding-left var(--dur-base) var(--ease);
  }

  /* FARA `overflow-y: auto` AICI.
     A doua oara aceeasi capcana ca la `.app-main` de mai sus. `overflow: auto`
     face din `.app-content` un container de derulare, deci ORICE `position: sticky`
     dintr-o pagina se raporteaza la scrollportul LUI. Iar el nu deruleaza
     niciodata: `.app-main` are `min-height: 100dvh` si creste cu continutul, deci
     fereastra e cea care deruleaza (verificat cu Playwright inca din 2026-07-03:
     wheel -> `window.scrollY` se schimba, `#main-content.scrollTop` ramane 0).
     Sticky-ul murea in tacere peste tot: antetul de zile din Planificator, bara
     laterala din pagina de proiect, capul de tabel, navigarea din Calculator.
     Taierea pe orizontala ramane la `.app-main` (`overflow-x: clip`), care nu
     creeaza container de derulare. */
  .app-content {
    flex: 1;
    /* Dockul pluteste peste continut pe telefon — lasa loc dedesubt. Pe desktop
       `--dock-h` e 0 (o scrie `Sidebar.svelte` la montare), deci ramane doar
       aerul de la capatul paginii. */
    padding-bottom: calc(var(--dock-h) + var(--space-lg) + var(--safe-bottom));
    transition: padding-right var(--dur-base) var(--ease);
  }
  /* PANOUL DESCHIS IMPINGE LISTA, NU O ACOPERA (T6).
     Clasa o pune `Modal.svelte`, ca `are-modal`, si doar pentru `size="panou"`
     peste 1100px — sub atat coloana n-are ce ceda. Perechea vizuala e voalul
     slab (0,18) de pe panou: amandoua spun acelasi lucru, ca ce e dedesubt
     ramane context de citit, nu fundal. */
  :global(html.are-panou) .app-content {
    padding-right: var(--panou-w);
  }

  /* Adresa e un COD, nu o propozitie — deci mono, si sub explicatia care o
     anunta. Butonul e acelasi obiect ca „Reîncearcă" din ErrorState: suprafata
     cu umbra, 44px, cerneala secundara. */
  .nf {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-12);
  }
  .nf-adresa {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--text-secondary);
    background: var(--bg-elevated);
    padding: 3px var(--space-10);
    border-radius: var(--radius-xs);
    max-width: 100%;
    overflow-wrap: anywhere;
  }
  .nf-inapoi {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: var(--tap-min);
    padding: 0 var(--space-md);
    border-radius: var(--radius-sm);
    background: var(--bg-surface);
    box-shadow: var(--shadow-sm);
    color: var(--text-secondary);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    text-decoration: none;
    transition: var(--transition-pressable);
  }
  .nf-inapoi:hover { background: var(--bg-hover); color: var(--text); }
  .nf-inapoi:active { transform: scale(var(--press-scale)); }

  .page-loading {
    padding: var(--space-lg);
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    max-width: 600px;
  }
  /* Varianta „randuri" isi tine singura distantele (`Skeleton varianta="rand"`),
     iar latimea nu se plafoneaza: listele curg pe toata coloana, deci un maxim
     de 600px ar face scheletul mai ingust decat continutul care il inlocuieste. */
  .page-loading.rand {
    max-width: none;
    gap: 0;
    padding: var(--space-lg) var(--space-md);
  }

  .skip-link {
    position: fixed;
    top: -100px;
    /* Dupa bara laterala, nu peste ea: e `position: fixed`, deci se raporteaza
       la ecran si n-ar sti singura de rezerva din `.app-main`. */
    left: calc(var(--sidebar-w) + var(--space-md));
    /* Se vede doar la Tab, dar cand se vede e un buton ca oricare altul —
       deci are caseta unui buton, nu 36px. */
    display: inline-flex;
    align-items: center;
    min-height: var(--tap-min);
    padding: var(--space-sm) var(--space-md);
    background: var(--accent);
    color: var(--accent-text);
    border-radius: var(--radius-sm);
    z-index: var(--z-tooltip);
    font-size: var(--font-small);
    font-weight: var(--fw-semibold);
    transition: top var(--dur-fast) var(--ease);
  }
  .skip-link:focus {
    top: var(--space-md);
  }

</style>
