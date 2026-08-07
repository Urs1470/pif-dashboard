<script>
  import { onMount } from 'svelte'
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'

  // Vizibilitate dock:
  //  - DESKTOP (autohide v4): ascuns by default; apare DOAR cat timp cursorul e
  //    impins in marginea de jos (unde sta dock-ul) si se ascunde cand iesi.
  //    Manerul "peek" ramane vizibil ca linie de prezenta.
  //  - MOBIL: urmareste DERULAREA, ca bara de adresa a browserului (cerinta Ion,
  //    2026-07-31). Cobori prin lista -> pleaca si iti da ecranul intreg; urci ->
  //    revine imediat. Sus de tot si la capatul paginii sta mereu afara.
  //    ATENTIE, asta INLOCUIESTE regula veche „pe mobil dock FIX, fara autohide":
  //    daca gasesti pe undeva comentariul acela, e fosila — nu-l restaura.
  //    Se ascunde in continuare cat timp tastatura e deschisa.
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

  const hidden = $derived(
    isMobile
      ? kbLocked || scrollHidden
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
    { path: '/plan', label: 'Planificator', icon: 'plan' },
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
  // Calculator sunt lucruri pe care le faci asezat, si raman la o cautare distanta
  // (butonul de cautare NU pleaca — vezi si lista din CommandPalette, unde
  // Departament tocmai a fost adaugata ca sa nu ramana fara drum).
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
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))
  }
</script>

<nav class="dock" class:hidden aria-label="Navigație principală">
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
    </a>
  {/each}
  <span class="sep" aria-hidden="true"></span>
  <button class="dock-item" onclick={openSearch} aria-label="Caută (Ctrl+K)" title="Caută (Ctrl+K)">
    <Search size={marimeIcon} />
  </button>
</nav>

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
    border-radius: var(--radius-lg);
    z-index: var(--z-sticky);
    background: color-mix(in srgb, var(--bg-surface) 85%, transparent);
    border: 1px solid var(--border-strong);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    box-shadow: var(--shadow-lg);
  }

  .dock-item {
    width: 50px;
    height: 50px;
    border-radius: 16px;
    color: var(--text-faint);
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
  @media (hover: hover) {
    .dock-item:hover {
      color: var(--text);
      transform: translateY(-4px);
    }
  }
  .dock-item:active { color: var(--text); background: var(--bg-hover); }
  .dock-item.active:active { background: var(--accent); }
  .dock-item.active {
    color: var(--accent-text);
    background: var(--accent);
  }
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
    box-shadow: 0 1px 5px rgba(0, 0, 0, 0.4);
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
    .dock {
      gap: 4px;
      padding: 8px 6px;
      max-width: calc(100vw - 12px);
    }
    .dock-item {
      width: 56px;
      height: 56px;
      border-radius: 18px;
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
