<script>
  import { fade } from 'svelte/transition'
  import Header from './components/layout/Header.svelte'
  import Dock from './components/layout/Dock.svelte'
  import Toast from './components/ui/Toast.svelte'
  import Tooltip from './components/ui/Tooltip.svelte'
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
  setPreincarcaRuta(async (cale) => {
    const m = resolveRoute(routes, (cale || '/').split('?')[0] || '/')
    if (!m || !m.component._lazy || lazyCache[m.pattern]) return
    const mod = await m.component.loader()
    lazyCache[m.pattern] = mod.default
  })

  const rawMatch = $derived(resolveRoute(routes))
  const routeKey = $derived(router.path)
  // When the browser drives the route change via the View Transitions API, let it
  // own the cross-fade; the Svelte fade only runs as a fallback (no VT support).
  // motionDuration() also zeroes this under reduced-motion regardless of VT support.
  const fadeDur = $derived(motionDuration(viewTransitionsOn() ? 0 : DUR_FAST))

  // ===== SCHIMBAREA DE PAGINA E DIRECTIONALA (contractul de miscare: 240ms,
  // „inainte din dreapta, inapoi din stanga"). Sensul vine din ORDINEA dockului:
  // mergi spre dreapta in dock -> continutul soseste din dreapta, si invers.
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
    <Header deschideCautarea={() => paleta?.deschide()} />
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
            <div class="page-loading"><Skeleton width="60%" height="24px" /><Skeleton width="100%" height="200px" /></div>
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

  <!-- Docul cheama paleta printr-o functie exportata, nu printr-o apasare de
       taste fabricata (vezi `deschide()` din CommandPalette). -->
  <Dock deschideCautarea={() => paleta?.deschide()} />
  <CommandPalette bind:this={paleta} />
  <Toast />
  <!-- Un singur tooltip pentru toata aplicatia; citeste atributele `title`. -->
  <Tooltip />
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
    /* Dock-ul pluteste peste continut la toate latimile — lasa loc dedesubt. */
    padding-bottom: calc(var(--dock-h) + var(--space-lg) + var(--safe-bottom));
  }

  /* Adresa e un COD, nu o propozitie — deci mono, si sub explicatia care o
     anunta. Butonul e acelasi obiect ca „Reîncearcă" din ErrorState: suprafata
     cu umbra, 44px, cerneala secundara. */
  .nf {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }
  .nf-adresa {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--text-secondary);
    background: var(--bg-elevated);
    padding: 3px 10px;
    border-radius: var(--radius-xs);
    max-width: 100%;
    overflow-wrap: anywhere;
  }
  .nf-inapoi {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 44px;
    padding: 0 16px;
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

  .skip-link {
    position: fixed;
    top: -100px;
    left: var(--space-md);
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
