<script>
  import { onMount } from 'svelte'
  import { fly, fade } from 'svelte/transition'
  import { Search, MoreHorizontal, Download } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE, EASE } from '../../lib/motion.svelte.js'

  let { deschideCautarea = () => {} } = $props()

  // ===== `--dock-h` SE MASOARA, NU SE PRESUPUNE (T5) =====
  // Tokenul spunea 68px — inaltimea pastilei de pe DESKTOP. Pe telefon dockul e
  // o bara lipita jos: 8 + 56 + 8 + safe ≈ 72+. Din cei 68 isi socoteau distanta
  // butonul plutitor din /tasks si /projects, toastul, si rezerva de jos a
  // continutului — deci fiecare dintre ele statea cu cativa pixeli mai jos decat
  // credea, si ultimul rand din lista ajungea sub butonul „+".
  // `ResizeObserver`, nu o citire la montare: bara isi schimba inaltimea cand
  // roteste telefonul si cand apare/dispare safe-area.
  // CUTIA DE BORDURA, NU CEA DE CONTINUT. `contentRect` scade paddingul, iar
  // bara are 8px sus si 8 jos: masurat, dadea 56 pentru o bara de 72 — adica
  // exact genul de eroare pe care task-ul o repara, doar cu alt numar. Cu 56,
  // butonul plutitor ramanea la 12px de dock in loc de 28.
  // `borderBoxSize` e drumul corect; `getBoundingClientRect` e rezerva pentru
  // browserele care nu-l raporteaza.
  let dockEl = $state(null)
  $effect(() => {
    if (!dockEl) return
    const scrie = (e) => {
      const h = e?.borderBoxSize?.[0]?.blockSize ?? dockEl.getBoundingClientRect().height
      document.documentElement.style.setProperty('--dock-h', Math.round(h) + 'px')
    }
    const ro = new ResizeObserver(([e]) => scrie(e))
    ro.observe(dockEl)
    scrie(null)
    return () => ro.disconnect()
  })

  // Vizibilitate dock:
  //  - DESKTOP (autohide v4): ascuns by default; apare DOAR cat timp cursorul e
  //    impins in marginea de jos (unde sta dock-ul) si se ascunde cand iesi.
  //    Manerul "peek" ramane vizibil ca linie de prezenta.
  //  - MOBIL: FIX, jos de tot, mereu la vedere (cerinta Ion, 2026-08-10 —
  //    RASTOARNA cerinta lui din 2026-07-31, „urmareste derularea ca bara de
  //    adresa": cu etichetele sub iconite dockul e acum harta aplicatiei, iar o
  //    harta care fuge de sub deget cand derulezi e mai scumpa decat cei ~72px
  //    de ecran pe care ii elibera). Singura ascundere ramasa pe telefon e
  //    tastatura: peste ea navigatia nu ajuta si spatiul chiar lipseste.
  //    `onScroll` de mai jos ramane scris dar nu mai are efect pe mobil —
  //    `hidden` nu mai citeste `scrollHidden` acolo.
  // `hidden` e DERIVAT, nu setat de mana dintr-un `apply()`.
  // Varianta imperativa a produs un bug greu de vazut: efectul care readuce
  // dock-ul la schimbarea rutei chema `apply()`, iar `apply()` CITEA `scrollHidden`
  // — deci efectul devenea dependent de el si se re-rula de fiecare data cand
  // ascunderea se activa, punandu-l imediat inapoi pe `false`. Dock-ul nu se
  // ascundea niciodata, fara nicio eroare nicaieri. Cu o valoare derivata nu mai
  // exista „cine cheama recalcularea", deci nici cercul.
  let kbLocked = $state(false)
  let scrollHidden = $state(false)
  let inZone = $state(false)      // desktop: cursorul e in banda de jos
  let peekReveal = $state(false)  // desktop: aratat temporar din maner
  let peekTimer = 0

  // Citit IMEDIAT, nu dupa montare: pe telefon o valoare initiala gresita
  // inseamna ca dock-ul porneste ascuns si sare la vedere dupa primul paint.
  let isMobile = $state(
    typeof window !== 'undefined' &&
      ((window.matchMedia?.('(pointer: coarse)')?.matches ?? false) || window.innerWidth <= 768)
  )

  // Cat timp foaia „Mai mult" e deschisa dockul NU se ascunde: foaia e ancorata
  // de marginea lui (`bottom: 100%`), deci ar cobori odata cu el si ar iesi din
  // ecran sub degetul care tocmai a deschis-o.
  const hidden = $derived(
    foaieDeschisa
      ? false
      : isMobile
        ? kbLocked
        : kbLocked || !(inZone || peekReveal)
  )

  // Iconite mai mari pe telefon: dock-ul tine cinci lucruri in loc de opt, iar
  // spatiul castigat se duce in TINTA, nu in aer.
  const marimeIcon = $derived(ecran.telefon ? 24 : 20)

  // Nota (desktop): NU ascundem la schimbarea rutei — cursorul ramane jos dupa
  // click pe un tab, deci un hide pe ruta ar produce flicker.

  // Manerul e doar pe desktop (pe telefon e `display: none` — acolo dock-ul se
  // cheama inapoi deruland in sus, ca bara de adresa). Tap pe el -> apare ~4s.
  function revealFromPeek() {
    if (kbLocked || isMobile) return
    peekReveal = true
    clearTimeout(peekTimer)
    peekTimer = setTimeout(() => { peekReveal = false }, 4000)
  }

  onMount(() => {
    // Desktop: cursorul in banda de jos -> apare. Prag ridicat de la 6px la 48px
    // (cerut de Ion): la 6px trebuia sa ajungi in taskbar-ul Windows si dadeai peste
    // el din inertie; la 48px dock-ul apare inainte sa atingi marginea sistemului.
    const REVEAL_EDGE = 48  // px de la marginea de jos -> apare
    const HIDE_ZONE = 150   // px: odata aparut, se ascunde cand treci peste atat

    const mq = window.matchMedia('(pointer: coarse)')
    const computeMobile = () => { isMobile = mq.matches || window.innerWidth <= 768 }
    computeMobile()

    // ---- MOBIL: dock-ul urmeaza derularea, ca bara de adresa -----------------
    // Pagina deruleaza pe FEREASTRA (`.app-content`/`.app-main` nu au overflow-y,
    // intentionat — vezi App.svelte), deci `scrollY` e reperul corect.
    const PRAG_SCROLL = 8    // px acumulati pana reactionam: sub atat e tremur de deget
    const ZONA_SUS = 60      // px de la varf in care dock-ul sta mereu afara
    const ZONA_JOS = 24      // px de la capat: la finalul listei nu-l mai ascundem
    let ultimY = window.scrollY

    function onScroll() {
      if (!isMobile) return
      const y = window.scrollY
      const dy = y - ultimY
      // NU actualizam `ultimY` sub prag: asa micile miscari se aduna si un gest
      // lent tot ajunge sa conteze, in loc sa fie ignorat la nesfarsit.
      if (Math.abs(dy) < PRAG_SCROLL) return
      ultimY = y
      const laCapat = y + window.innerHeight >= document.documentElement.scrollHeight - ZONA_JOS
      // Urcarea il aduce inapoi IMEDIAT (dy < 0), fara prag de revenire: cand
      // vrei navigatia, o vrei acum, nu dupa inca o jumatate de ecran.
      scrollHidden = y <= ZONA_SUS || laCapat ? false : dy > 0
    }

    let mmTick = 0
    function onMove(e) {
      if (isMobile) return
      const now = performance.now()
      if (now - mmTick < 16) return
      mmTick = now
      const fromBottom = window.innerHeight - e.clientY
      if (inZone) {
        if (fromBottom > HIDE_ZONE) inZone = false
      } else if (fromBottom <= REVEAL_EDGE) {
        inZone = true
      }
    }

    function onResize() { computeMobile() }

    // tastatura mobila: focus pe camp editabil -> dock blocat ascuns
    const isEditable = (el) => !!el && (el.matches?.('input, textarea, select') || el.closest?.('[contenteditable="true"]'))
    function onFocusIn(e) {
      if (!isMobile || !isEditable(e.target)) return
      kbLocked = true
    }
    function onFocusOut() {
      if (!kbLocked) return
      setTimeout(() => {
        if (isEditable(document.activeElement)) return
        kbLocked = false
      }, 120)
    }

    mq.addEventListener?.('change', onResize)
    window.addEventListener('resize', onResize, { passive: true })
    window.addEventListener('mousemove', onMove, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })
    document.addEventListener('focusin', onFocusIn)
    document.addEventListener('focusout', onFocusOut)
    return () => {
      clearTimeout(peekTimer)
      mq.removeEventListener?.('change', onResize)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('scroll', onScroll)
      document.removeEventListener('focusin', onFocusIn)
      document.removeEventListener('focusout', onFocusOut)
    }
  })

  const items = [
    { path: '/', label: 'Acasă', icon: 'home' },
    { path: '/projects', label: 'Proiecte', icon: 'projects' },
    { path: '/tasks', label: 'Taskuri', icon: 'tasks' },
    /* `scurt` e eticheta de sub iconita pe telefon (desen: „Plan") — numele
       intreg ramane in aria-label si in title. */
    { path: '/plan', label: 'Planificator', scurt: 'Plan', icon: 'plan' },
    { path: '/calendar', label: 'Calendar', icon: 'calendar' },
    // Langa Calendar, nu la coada: dupa „unde sunt eu" urmeaza imediat „cine e unde".
    { path: '/departament', label: 'Departament', icon: 'departament' },
    { path: '/calculator', label: 'Calculator', icon: 'calculator' },
  ]

  // PE TELEFON, DOCK-UL TINE CINCI LUCRURI (cerinta Ion).
  //
  // Sapte iconite plus cautarea inseamna opt tinte pe latimea unui telefon: la
  // 390px raman ~44px de tinta, adica exact minimul, fara aer intre ele — si
  // tocmai degetul mare, care ajunge acolo, e cel mai gros instrument de atins.
  // Raman rutele pe care le deschizi zilnic de pe teren; Proiecte, Departament si
  // Calculator sunt lucruri pe care le faci asezat.
  //
  // Socoteala aia e in continuare corecta, si decizia ramane. Ce NU era in regula
  // e ce se intampla cu cele trei rute scoase: singurul drum spre ele era
  // butonul de cautare -> paleta de comanda -> tastatura -> scrii „proiecte".
  // Patru pasi si o tastatura ca sa ajungi la o pagina de nivel unu, pe un
  // telefon. O paleta de comanda e o unealta de TASTATURA; pe un ecran fara Ctrl
  // nu poate fi singurul drum catre o ruta.
  //
  // Al cincilea slot devine „Mai mult": o foaie cu cele trei rute la 44px
  // fiecare. Cautarea nu pleaca — urca in capul foii, deci o atingere iti da si
  // rutele, si cautarea, iar cine vrea sa scrie scrie. Pe desktop nu se schimba
  // nimic: acolo sunt toate sapte, plus Ctrl+K.
  //
  // Filtrul citeste `ecran.telefon`, sursa unica a pragului de 768px, NU o a doua
  // definitie locala: `isMobile` de mai sus include si `pointer: coarse`, fiindca
  // raspunde la alta intrebare — „ce ASCUNDE dock-ul: derularea sau cursorul", nu
  // „cate incap pe lat". Pe o tableta lata cu ecran tactil vrei ascundere la
  // derulare, dar ai loc de toate sapte.
  const PE_TELEFON = new Set(['/', '/tasks', '/plan', '/calendar'])
  const itemsVizibile = $derived(
    ecran.telefon ? items.filter((i) => PE_TELEFON.has(i.path)) : items
  )
  const itemsInFoaie = $derived(items.filter((i) => !PE_TELEFON.has(i.path)))

  // Cand esti pe o ruta din foaie, slotul activ e „Mai mult" — altfel dock-ul
  // n-ar avea NICIUN slot aprins pe /projects, /departament si /calculator, si
  // ai citi asta ca „nu esti nicaieri". Slotul e drumul catre ea, deci el o tine.
  let foaieDeschisa = $state(false)
  const inFoaie = $derived(itemsInFoaie.some((i) => isActive(i.path)))
  // O ruta noua inchide foaia — altfel ramane peste pagina in care tocmai ai intrat.
  $effect(() => { router.path; foaieDeschisa = false })

  // O ruta noua aduce dock-ul inapoi. Fara asta ramai fara navigatie pe pagina
  // urmatoare: routerul e pe hash si nu deruleaza mereu la varf, deci `scrollHidden`
  // ar ramane agatat din pagina de dinainte si n-ar exista niciun `scroll` care
  // sa-l stinga.
  $effect(() => {
    router.path
    scrollHidden = false
  })

  function isActive(path) {
    if (path === '/') return router.path === '/'
    return router.path.startsWith(path)
  }

  function openSearch() {
    foaieDeschisa = false
    deschideCautarea()
  }

  // INSTALAREA PE ECRANUL PRINCIPAL — un rand, nu o pagina de setari.
  //
  // `main.js` prindea `beforeinstallprompt`, ii dadea `preventDefault()` (deci
  // browserul nu-si mai arata singur indiciul) si expunea `window.pifInstallApp`.
  // Pe care NU-l chema nimeni: zero apelanti in tot frontendul. Rezultatul net era
  // ca aplicatia nu se putea instala nici de la noi, nici de la browser.
  //
  // Randul apare DOAR dupa `pif-install-ready`, adica doar cand exista efectiv un
  // prompt de aratat: pe iPhone, in aplicatia deja instalata, sau in WebView-ul
  // Android evenimentul nu vine niciodata, si atunci nici randul n-are ce cauta
  // acolo. Dupa instalare pleaca — `pifInstallApp()` consuma promptul, care nu se
  // mai poate folosi a doua oara.
  let potInstala = $state(false)
  onMount(() => {
    const gata = () => { potInstala = true }
    window.addEventListener('pif-install-ready', gata)
    // Evenimentul poate fi deja trecut cand dockul se monteaza (`main.js` il
    // arunca la incarcare), deci se intreaba si direct.
    if (typeof window.pifPoateInstala === 'function') potInstala = window.pifPoateInstala()
    return () => window.removeEventListener('pif-install-ready', gata)
  })

  async function instaleaza() {
    foaieDeschisa = false
    await window.pifInstallApp?.()
    potInstala = window.pifPoateInstala?.() ?? false
  }
</script>

<nav class="dock" class:hidden bind:this={dockEl} aria-label="Navigație principală">
  <button class="dock-grip" aria-label="Arată navigația" title="Navigație" onclick={revealFromPeek}></button>
  {#each itemsVizibile as item (item.path)}
    <a
      href={item.path}
      use:link
      onclick={(e) => e.currentTarget.blur()}
      class="dock-item"
      class:active={isActive(item.path)}
      aria-current={isActive(item.path) ? 'page' : undefined}
      aria-label={item.label}
      title={item.label}
    >
      <SolidIcon name={item.icon} size={marimeIcon} />
      <span class="dock-et">{item.scurt || item.label}</span>
    </a>
  {/each}
  <span class="sep" aria-hidden="true"></span>
  {#if ecran.telefon}
    <button class="dock-item" class:active={foaieDeschisa || inFoaie}
            onclick={() => (foaieDeschisa = !foaieDeschisa)}
            aria-label="Mai mult" aria-expanded={foaieDeschisa} title="Mai mult">
      <MoreHorizontal size={marimeIcon} />
      <span class="dock-et">Mai mult</span>
    </button>

    {#if foaieDeschisa}
      <!-- Foaia celor trei rute ramase. Cautarea sta in CAP, nu la coada: e
           drumul catre orice altceva, iar cine a atins „Mai mult" fara sa stie ce
           cauta o vede prima. Fiecare rand la 44px.

           E COPIL AL DOCULUI, cu `bottom: 100%`, nu un frate fixat cu o socoteala
           de genul „14 + safe + inaltimea docului + 8": ancorarea procentuala se
           lipeste de marginea lui reala, deci ramane corecta si daca dockul isi
           schimba vreodata inaltimea sau padding-ul. Prima varianta hardcoda 72px
           si a iesit cu 2px peste doc — exact bordura pe care o uitasem.

           Invelisul face centrarea, iar `fly` anima elementul dinauntru: `fly`
           scrie `transform` inline, deci ar fi SUPRASCRIS un `translateX(-50%)`
           pus pentru centrare, si foaia ar fi plecat lateral cat tine animatia. -->
      <div class="mm-ancora">
        <div class="mm-foaie" role="menu" aria-label="Mai mult"
             transition:fly={{ y: 12, duration: motionDuration(DUR_BASE), easing: EASE }}>
          <button class="mm-cauta" onclick={openSearch} role="menuitem">
            <Search size={17} /> Caută în tot dashboardul
          </button>
          <span class="mm-linie" aria-hidden="true"></span>
          {#each itemsInFoaie as item (item.path)}
            <a href={item.path} use:link class="mm-rand" class:active={isActive(item.path)}
               role="menuitem" onclick={() => (foaieDeschisa = false)}>
              <SolidIcon name={item.icon} size={18} />
              {item.label}
            </a>
          {/each}
          {#if potInstala}
            <span class="mm-linie" aria-hidden="true"></span>
            <button class="mm-rand" onclick={instaleaza} role="menuitem">
              <Download size={18} strokeWidth={1.5} /> Instalează pe ecranul principal
            </button>
          {/if}
        </div>
      </div>
    {/if}
  {:else}
    <button class="dock-item" onclick={openSearch} aria-label="Caută (Ctrl+K)" title="Caută (Ctrl+K)">
      <Search size={marimeIcon} />
    </button>
  {/if}
</nav>

{#if foaieDeschisa && ecran.telefon}
  <div class="mm-fundal" onclick={() => (foaieDeschisa = false)}
       transition:fade={{ duration: motionDuration(DUR_FAST), easing: EASE }}
       role="presentation"></div>
{/if}

<style>
  .dock {
    position: fixed;
    left: 50%;
    bottom: calc(14px + var(--safe-bottom));
    transform: translateX(-50%) translateY(var(--dock-shift, 0px));
    transition: transform var(--dur-base) var(--ease);
    display: flex;
    gap: 4px;
    padding: 12px 8px 8px;
    border-radius: var(--radius-md);
    z-index: var(--z-sticky);
    /* OPAC, cu umbra. Era semi-transparent cu `blur(18px)`, deci continutul
       paginii se plimba dedesubt ca o pata in miscare — exact sub degetul care
       cauta un tab. O suprafata flotanta se desprinde prin umbra, nu prin
       sticla; asa se desprind si modalul, si toastul, si popoverul. */
    background: var(--bg-surface);
    box-shadow: var(--shadow-md);
  }

  /* Eticheta exista doar pe telefon (blocul de 768) — pe desktop iconita ajunge,
     dock-ul tine opt lucruri si are tooltip. */
  .dock-et { display: none; }
  .dock-item {
    width: 50px;
    height: 50px;
    border-radius: var(--radius-sm);
    /* `--text-secondary`, nu `--text-faint`: o iconita de navigatie inactiva
       trebuie sa se poata CITI, nu doar sa se ghiceasca — e singura harta a
       aplicatiei. Estompatul e pentru text care insoteste, nu pentru drumuri. */
    color: var(--text-secondary);
    display: grid;
    place-items: center;
    cursor: pointer;
    background: transparent;
    border: none;
    transition: color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease),
      transform var(--dur-fast) var(--ease);
  }
  /* Ridicarea e un raspuns la cursor. Pe touch ramanea ridicata tableta atinsa
     ultima data, deci dock-ul arata mereu ca si cum ai fi peste un alt tab decat
     cel activ. */
  /* Fara ridicare la hover: „translateY" nu e in setul de miscare — el are trei
     durate si o apasare, nu o plutire. Hoverul schimba doar cerneala si fondul. */
  @media (hover: hover) {
    .dock-item:hover {
      color: var(--text);
      background: var(--bg-hover);
    }
  }
  .dock-item:active { color: var(--text); background: var(--bg-hover); transform: scale(var(--press-scale)); }
  /* Activ = TENTA de accent cu cerneala adanca, nu accentul plin.
     Fillul plin facea din slotul curent lucrul cel mai tare colorat de pe ecran
     — mai tare decat orice buton de actiune — desi el nu e o actiune, e o
     informatie despre unde esti. */
  .dock-item.active {
    color: var(--accent-deep);
    background: var(--accent-subtle);
  }
  .dock-item.active:active { background: var(--accent-subtle); }
  .dock-item.active:hover {
    transform: none;
  }

  /* Ascuns: dock-ul coboara pana ramane vizibil doar manerul-linie de sus.
     Manerul e copil al dock-ului, deci urca/coboara IMPREUNA cu el. */
  .dock.hidden {
    --dock-shift: calc(100% + 6px);
  }

  .sep {
    width: 1px;
    background: var(--border-strong);
    margin: 10px 6px;
  }

  /* ===== Foaia „Mai mult" (doar telefon) =====
     Se aseaza DEASUPRA docului, ancorata de marginea lui de jos, ca sa ramana
     sub degetul care tocmai a atins al cincilea slot. */
  /* Sub doc (care e propriul context de stivuire), peste restul paginii. */
  .mm-fundal {
    position: fixed;
    inset: 0;
    z-index: calc(var(--z-sticky) - 1);
    background: color-mix(in srgb, var(--bg) 55%, transparent);
  }
  /* Invelisul: lipit de marginea de sus a docului, centrat pe el. Nu poarta
     `transform`, ca sa nu se bata cu cel scris de `fly` pe copil. */
  .mm-ancora {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    right: 0;
    display: flex;
    justify-content: center;
    pointer-events: none;
  }
  .mm-foaie {
    pointer-events: auto;
    width: min(320px, calc(100vw - 24px));
    display: flex;
    flex-direction: column;
    padding: 6px;
    border-radius: var(--radius-md);
    background: var(--bg-overlay);
    box-shadow: var(--shadow-md);
  }
  .mm-cauta,
  .mm-rand {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: var(--tap-min);
    padding: 0 12px;
    border: none;
    background: none;
    border-radius: var(--radius-sm);
    font-size: var(--font-body);
    color: var(--text-secondary);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .mm-cauta { color: var(--text-dim); }
  .mm-cauta:active,
  .mm-rand:active { background: var(--bg-hover); color: var(--text); }
  .mm-rand.active {
    color: var(--accent-deep);
    background: var(--accent-subtle);
    font-weight: var(--fw-semibold);
  }
  .mm-linie { height: 1px; background: var(--border); margin: 5px 8px; }

  /* Manerul-linie (prezenta dock-ului). Absolut pe dock -> se misca cu dock-ul. */
  .dock-grip {
    position: absolute;
    top: 3px;
    left: 50%;
    transform: translateX(-50%);
    width: 48px;
    height: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
  }
  .dock-grip::before {
    content: '';
    width: 30px;
    height: 3px;
    border-radius: var(--radius-full);
    background: var(--border-strong);
    transition: background var(--dur-fast) var(--ease), width var(--dur-fast) var(--ease);
  }
  .dock-grip:hover::before,
  .dock-grip:focus-visible::before {
    background: var(--accent);
    width: 38px;
  }

  /* Pe touch dock-ul e fix (mereu vizibil) -> manerul de "peek" nu mai are rost.
     Conditia de latime o dubleaza pe cea de pointer fiindca JS-ul de mai sus
     considera „mobil" si o fereastra ingusta cu mouse (`innerWidth <= 768`): fara
     ea, acolo dock-ul era fix dar manerul continua sa se ofere sa-l arate. */
  @media (pointer: coarse), (max-width: 768px) {
    .dock-grip { display: none; }
    .dock { padding-top: 8px; }
  }

  /* CINCI TINTE, NU OPT — deci spatiul se duce in TINTA.
     Istoric: cu 7 tab-uri + cautare pe 375px ieseau 8 × 44 = 352px si nu incapeau,
     asa ca tintele stateau lipite (gap 0), fara separator, la exact minimul de 44.
     De cand pe telefon dock-ul tine cinci lucruri (vezi `PE_TELEFON`), incap
     confortabil 56px de tinta, cu aer intre ele si cu separatorul inapoi.
     Socoteala, pe cel mai ingust telefon testat (360px):
       5 × 56 + 4 × 4 (gap) + 12 (padding) = 308px, din 348 disponibili.
     Pragul e 768px, ACELASI cu cel care decide ca sunt cinci: daca ar fi doua
     praguri diferite, ar exista o latime la care ai opt iconite marite si dock-ul
     ar iesi din ecran. */
  @media (max-width: 768px) {
    /* FIX, JOS DE TOT (Ion, 2026-08-10): bara plina de la margine la margine,
       lipita de fundul ecranului — ca in desenele mobile — nu pastila plutitoare
       de pe desktop. Safe-area intra in padding, nu in `bottom`, ca fundalul sa
       curga pana sub gestul de sistem. */
    .dock {
      left: 0;
      right: 0;
      bottom: 0;
      transform: translateY(var(--dock-shift, 0px));
      width: 100%;
      max-width: 100%;
      gap: 4px;
      padding: 8px 6px calc(8px + var(--safe-bottom));
      border-radius: var(--radius-md) var(--radius-md) 0 0;
      justify-content: space-around;
    }
    /* ETICHETA SUB ICONITA (desenele mobile, toate cadrele): cinci cuvinte
       pentru cinci drumuri — iconita singura cere sa fi invatat deja harta.
       Doar pe telefon: pe desktop dock-ul tine opt lucruri si eticheta le-ar
       dubla latimea. Tinta creste la 56×~58, tot peste prag. */
    .dock-item {
      width: 60px;
      height: auto;
      min-height: 56px;
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      padding: 6px 2px;
    }
    .dock-et {
      display: block;
      font-size: var(--font-label);
      font-weight: var(--fw-medium);
      line-height: 1;
      letter-spacing: var(--tracking-normal);
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    /* Ascuns pe telefon inseamna ASCUNS: manerul e `display: none` aici, deci nu
       are ce ramane la vedere. `100% + 6px` (valoarea de pe desktop, calibrata ca
       sa lase manerul afara) ar lasa dock-ul sa iasa cu ~8px din marginea de jos —
       o dunga care se plimba peste continut. Il coboram cu toata distanta lui fata
       de marginea ecranului. */
    .dock.hidden {
      --dock-shift: calc(100% + 14px + var(--safe-bottom) + 6px);
    }
  }
</style>
